---
title: "SwiftData + CloudKit 同期で詰まる schema 互換要件と落とし穴 (4/N)"
emoji: "☁️"
type: "tech"
topics: ["SwiftData", "CloudKit", "iOS", "macOS"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 4 回目です。
今回は、IntentTodo を CloudKit 同期対応する際に詰まったポイントを整理します。実機で iOS と macOS 間の同期確認まで済んでいる状態でまとめています。

## 結論サマリ

CloudKit 互換にするためには次を満たす必要がありました。

1. `cloudKitDatabase: .automatic` を `ModelConfiguration` に渡す
2. すべての target の entitlements に iCloud container + CloudKit services + `aps-environment` を設定する
3. **すべての属性に default value を持たせる** (もしくは Optional)
4. **すべてのリレーションを Optional にする** (to-many も `[T]?`)
5. `@Attribute(.unique)` / `DeleteRule.deny` は使わない
6. 旧スキーマで作られた既存ストアは削除する

ハマりどころは 3 と 4 と 6。順に書きます。あわせて、CloudKit とは直接関係ないけれど同じ「モデルに何を置けるか」の話として踏んだものも 2 つ足しました。

## entitlements とコード設定

まず `SharedModelContainer` の `cloudKitDatabase` を `.automatic` にします。
`.automatic` は entitlements の `com.apple.developer.icloud-container-identifiers` から container ID を自動採用するので、コード側に文字列を書かなくてよくて便利です。

```swift
public static var configuration: ModelConfiguration {
    if let containerURL = sharedContainerURL {
        let storeURL = containerURL.appendingPathComponent(databaseFilename)
        return ModelConfiguration(
            schema: schema,
            url: storeURL,
            cloudKitDatabase: .automatic
        )
    }
    // production では fatalError、DEBUG では fallback (本記事末尾)
}
```

そして全ターゲット (アプリ本体 / Widget Extension / Live Activity Extension / Watch App) の `.entitlements` にこれらを付けます。

```xml
<key>aps-environment</key>
<string>development</string>
<key>com.apple.developer.icloud-container-identifiers</key>
<array>
    <string>iCloud.dev.touyou.IntentTodo</string>
</array>
<key>com.apple.developer.icloud-services</key>
<array>
    <string>CloudKit</string>
</array>
<key>com.apple.security.application-groups</key>
<array>
    <string>group.com.touyou.IntentTodo</string>
</array>
```

`aps-environment` は CloudKit が裏で送る silent push 受信に必要なので、`.automatic` にしただけでは足りないです。

加えて、Apple Developer Portal 側で:

- CloudKit container `iCloud.dev.touyou.IntentTodo` を作成
- 各 target の Bundle ID に対して **iCloud capability + Push Notifications capability を有効化** + container を紐付け

ここをサボると、macOS native ビルドが provisioning profile レベルで失敗します。
Xcode を開いて Signing & Capabilities 画面を 1 度開くと、Automatic signing が Portal と同期してくれることが多いので、まずそれを試すのがおすすめです。

## ハマりどころ 1: schema 互換要件

`.automatic` に切り替えて起動すると、以下のようなエラーで落ちます。

```
CloudKit integration requires that all attributes be optional, or have a default value set.
The following attributes are marked non-optional but do not have a default value:
  Category: id
  Category: name
  SubTask: id
  ...
CloudKit integration requires that all relationships be optional, the following are not:
  Category: todos
  TodoItem: subTasks
```

メッセージのとおりですが、init で値を設定しているだけでは CloudKit 互換チェックを通りません。
**プロパティ宣言時にデフォルト値を持たせる** 必要があります。

```swift
@Model
public final class TodoItem {
    public var id: UUID = UUID()
    public var title: String = ""
    public var isCompleted: Bool = false
    public var isFavorite: Bool = false
    public var createdAt: Date = Date()
    public var modifiedAt: Date = Date()
    public var todoDescription: String?
    public var dueDate: Date?
    // ...
}
```

`init(title:)` で title は必須にしておきたいケースは、init 引数の方を required にしたまま、プロパティの宣言だけにデフォルト値を付ける形で両立できます。

## ハマりどころ 2: to-many リレーションは Optional 必須

属性のほうを直して再起動すると、今度はリレーション側で同じく落ちます。

```
CloudKit integration requires that all relationships be optional, the following are not:
  Category: todos
  TodoItem: subTasks
```

ここで「`= []` でデフォルト値を入れれば OK」と思いがちですが、CloudKit のチェックは **真の Optional `[T]?` を要求** していて、デフォルト空配列では通りません。

```swift
@Model
public final class TodoItem {
    @Relationship(deleteRule: .cascade, inverse: \SubTask.parentTodo)
    public var subTasks: [SubTask]? = []  // ← Optional + 空配列デフォルト
}

@Model
public final class Category {
    public var todos: [TodoItem]? = []  // ← 同じく
}
```

参照する側は `nil` を意識して読む必要が出てきます。

```swift
if let subTasks = todo.subTasks, !subTasks.isEmpty {
    SubtasksSection(subtasks: subTasks)
}
// または
let count = (category.todos ?? []).count
```

これで起動できるようになります。

## ハマりどころ 3: 旧スキーマのストアは migration で詰む

CloudKit 対応に切り替える前に既存のストアファイルがある状態だと、起動時に CoreData の migration がかかって、結局上記の schema 違反で落ちます。
**App Group container 配下の `.store` を一度削除** して、新しいスキーマで作り直すのが現実的な解決策です。

開発中なら以下で OK。

```bash
# macOS 用
rm ~/Library/Group\ Containers/group.com.touyou.IntentTodo/IntentTodo.store*

# iOS Simulator 用
find ~/Library/Developer/CoreSimulator/Devices -name "IntentTodo.store*" -delete

# iOS 実機の場合はアプリを削除 → 再インストール
```

production でユーザーに同じ問題を起こしたくない場合は、本来は migration プランを書く必要がありますが、IntentTodo は個人プロジェクトなのでこの問題は今のところ無視しています。

この「将来 migration プランを書くとき」については、WWDC 2026 の SwiftData Group Lab で 1 つ指針が示されていた、という話を見かけました。複数プロセス (アプリ本体 / Widget / Live Activity) が同じ App Group のストアを共有する構成では、**マイグレーションを担当するプロセスをアプリ本体 1 つに固定する** べき、というものです。理由は、アプリ更新直後は **アプリ本体より先に Widget / Extension プロセスが起動し得る** ため。両方がマイグレーションプランを持っていると、Extension が先に移行を試みて本体の移行と競合する危険があります。なので将来 `SchemaMigrationPlan` を導入するときは、**プランを渡すのはアプリ本体の `ModelContainer` だけ** にして、Widget / Live Activity 側はプラン無し (= 移行済みファイルを読むだけ) で構成する方針にしました。この別プロセス前提の話は [3/N](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions) 側にも要点を書いています。

ただしこの指針、**一次資料で裏を取れていません**。当初はセッション 8017 として書いていたんですが、あとで手元のアーカイブを漁り直したら書き起こしが見つかりませんでした (出てくるのは別テーマの 8011 だけです)。Group Lab はライブ Q&A なので公式の書き起こしが出ないことも多いみたいです。内容自体は SwiftData を複数プロセスで共有するときの一般則として妥当だと思うので方針は変えていませんが、「Apple がこう言った」ではなく「そう聞いた」くらいの確度で読んでもらえればと思います。実際に導入する段になったら API 名と挙動は公式ドキュメントで確認し直すつもりです。

## ハマりどころ 4: フォールバックが silently データを分裂させる

最初は `SharedModelContainer.configuration` を以下のように書いていました。

```swift
public static var configuration: ModelConfiguration? {
    if let containerURL = sharedContainerURL {
        return ModelConfiguration(...)
    } else {
        // Fallback for when App Group is not available (e.g., previews, tests)
        return ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
    }
}
```

これは「テスト / プレビューで App Group が無い時のための fallback」のつもりだったんですが、production で entitlement が壊れた場合にも同じ経路を通ってしまい、**メインアプリと Widget Extension がそれぞれ別の default ストアを開く** という silently 壊れる状態になります。
ユーザーには「Widget が壊れている」「データが反映されない」とだけ見えるパターン。

なので、production では明示的に `fatalError` で落とすように変えました。

```swift
public static var configuration: ModelConfiguration {
    if let containerURL = sharedContainerURL {
        let storeURL = containerURL.appendingPathComponent(databaseFilename)
        return ModelConfiguration(
            schema: schema,
            url: storeURL,
            cloudKitDatabase: .automatic
        )
    }
    #if DEBUG
    logger.warning("App Group container unavailable — using non-shared fallback (DEBUG only)")
    return ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
    #else
    logger.critical("App Group container unavailable in production — entitlement misconfig")
    fatalError("App Group missing in production build — check entitlements for \(appGroupIdentifier)")
    #endif
}
```

「production でだけ fatalError、DEBUG では fallback」 という分岐は、SPM テストやプレビューを動かしつつ、production の不整合は TestFlight や App Store 審査の段階で確実に表面化させたい、という意図です。

### ただしこの fallback、macOS では働かない

その後 macOS の SPM テストで引っかかって分かったんですが、上の分岐の入口になっている `FileManager.containerURL(forSecurityApplicationGroupIdentifier:)` は、**プラットフォームで挙動が違います**。iOS は entitlement が無ければ `nil` を返しますが、**macOS は entitlement の無いプロセスでもパスを返します** (`~/Library/Group Containers/<id>`。ディレクトリは存在するけれど書き込みはできない、という状態です)。

なので macOS では `sharedContainerURL` が `nil` にならず、DEBUG の fallback 経路にも入りません。開けない共有ストアをそのまま掴んで、`createContainer()` が `NSCocoaErrorDomain 256` / `SQLite 23` で throw します。「App Group が使えるかどうかの判定に `containerURL != nil` を使う」というのが、そもそも指標として成立していなかったわけです。

テスト側の扱いは 2 つに分けました。**entitlement を要する経路は SPM テストで緑にしようとしない** ことにして、共有ストアを作るテストは `withKnownIssue(isIntermittent: true)` で包んでいます (entitlement のあるホストで走れば成功して、`isIntermittent` なのでその場合も緑のままです)。ストアを実際に使うテストの方は、`SharedModelContainer.createInMemoryContainer()` に切り替えました。

テストを緑にするために production の分岐をいじると、いちばん守りたかった「production では確実に落とす」が壊れるので、テスト側を諦める方が筋がいいなと思っています。

## ハマりどころ 5: そもそも属性にできない型がある

CloudKit 互換の話とは別に、**SwiftData の属性にできない型** でも 1 回転びました。7/N で書く reminders スキーマ適合のために、Todo に繰り返しルールを持たせようとしたときです。

```swift
@Model
public final class TodoItem {
    public var recurrenceRule: Calendar.RecurrenceRule?   // ← コンパイルは通る
}
```

`Calendar.RecurrenceRule` は `Codable` なので、素直に置けそうに見えます。**コンパイルも通ります**。ところがアプリを起動すると落ちます。

```
EXC_BREAKPOINT (SIGTRAP) / libswiftCore _assertionFailure
  SwiftData ... x10
  IntentTodo one-time initialization function for schema
```

落ちる場所が `ModelContainer` 生成 **より前** の、schema の一度きりの初期化なので、症状がかなり分かりにくいです。自分の場合は UI テストが全ケース「起動直後にクラッシュ」になって、原因の当たりが全然つきませんでした。フィールドを外して単一の `testAppLaunches` を通すことで、ようやく切り分けています。

対処は、この記事でずっと書いている **CloudKit 互換 primitive + 境界で組み立て** と同じ形にすることでした。`recurrenceFrequency: String?` + `recurrenceInterval: Int = 1` で保存して、Entity の境界で `Calendar.RecurrenceRule` に組み直します。場所 (`locationName` + 緯度経度) や担当者と同じパターンです。

CloudKit 互換のために primitive に落とす、という制約が結果的にこっちの地雷も避けてくれていた、というのはちょっと面白いところでした。「モデルは枯れた primitive、リッチな型は境界で作る」を守っていれば、そもそも踏まなかったやつです。

## ハマりどころ 6: 削除済みオブジェクトの配列属性を読むと trap する

これはさらに分かりにくかったので、詳しく書いておきます。

`tags: [String]` のような **配列の属性** をモデルに足して、それを Entity や View から読むようにしたら、**削除のテストだけ** がアプリのクラッシュで落ちるようになりました。

```
libswiftCore _assertionFailure
  SwiftData x3
  TodoItem.tags.getter
  TodoAppEntity.init(from:)
```

**SwiftData は削除済みオブジェクトの配列属性を読むと trap します**。スカラーの属性は最後の値を返すので耐えるんですが、配列は駄目でした。

なぜ削除済みのオブジェクトを読むのかというと、詳細画面が削除直後にもう 1 度 body を評価するからです。そのとき `@Query` の結果にはまだ削除済みのオブジェクトが入っていて、そこで配列を読んで落ちます。

厄介なのが、**`!todoItem.isDeleted` のガードが効かない** ことでした。同じトレースで再発します。この時点で `isDeleted` はまだ `false` なんです。

効いたのは **その場のオブジェクトを読まずに、id から引き直す** 形でした。Entity 側は `@Property` をやめて `@DeferredProperty` にして (消えた Todo は「見つからない」に落ちるだけになります)、View 側は `body` の中で読まずに `@State` のスナップショットへ写して、`.task(id: todo.modifiedAt)` で更新します。契機に `modifiedAt` を使えるのは **スカラーだから** で、削除済みでも読めます。

```swift
// ❌ body の中でモデルの配列属性を読む
if !todo.tags.isEmpty { TagRow(tags: todo.tags) }

// ✅ スナップショットに写す。更新は id から引き直す
@State private var tags: [String] = []
// ...
.task(id: todo.modifiedAt) { tags = await loadTags(id: todo.id) }
```

いちばんの教訓は、**この trap は「1 回直した」では終わらない** ことでした。自分は Entity 側で直した数日後に、View 側で同じ罠を新しく作り込んでいます。読む場所を増やすたびに再発するので、**`@Model` の配列属性は `body` から読まない** をルールとして決めました。シートに渡すときも値渡しにしています (content クロージャは提示中に再評価されうるので、そこで読むと同じ口が残ります)。


## エラーログを早めに仕込む

ModelContainer の作成失敗は `SwiftDataError(_error: .loadIssueModelContainer, _explanation: nil)` のような top-level 型しか出ず、原因が見えません。
詳細を知るには **Swift の `String(reflecting:)` と `NSError.userInfo` まで吐かせる** 必要があります。

```swift
do {
    return try ModelContainer(for: schema, configurations: [Self.configuration])
} catch {
    logger.error("ModelContainer creation failed: \(String(reflecting: error))")
    if let nsError = error as NSError? {
        logger.error("NSError domain=\(nsError.domain) code=\(nsError.code) userInfo=\(nsError.userInfo)")
    }
    throw error
}
```

これで CoreData が出している `CloudKit integration requires that all attributes be optional, or have a default value set. ...` を Console.app に拾えるようになります。
詰まったらまずこれを仕込むのが回り道に見えて最短ルートでした。

## WWDC 2026 の SwiftData レビューを受けて

WWDC 2026 の SwiftData / Widget まわりのセッションと Group Lab を見直したので、この記事に効く差分を反映しておきます。マイグレーション分離は上のハマりどころ 3 に書いたとおりで、ここでは残り 2 つです。

1 つ目、**CloudKit 互換の制約は 2026 でも据え置き** でした。`@Attribute(.unique)` が enforce されない・リレーションは全部 Optional・プロパティはデフォルト値か Optional 必須、というこの記事の要件はそのまま有効です。新しい回避策が増えたわけではないので、ここで書いたワークアラウンドは引き続き必要、という確認になりました。

2 つ目は件数取得まわりの小さな整理です。未完了 Todo の件数を出すのに、もともと `fetchIncomplete().count` で **全 `TodoItem` をメモリに載せてから** 数えている箇所があったので、`ModelContext.fetchCount(_:)` に置き換えました。

```swift
public func incompleteCount() throws -> Int {
    // fetchCount は TodoItem を materialize せず、ストアレベルで件数だけ数える
    let descriptor = FetchDescriptor<TodoItem>(
        predicate: #Predicate { !$0.isCompleted }
    )
    return try modelContext.fetchCount(descriptor)
}
```

`fetchCount` はモデルを materialize せずストアレベルで件数だけ返すので、件数しか要らないところはこちらが素直です。これ自体は iOS 17 からある既存 API で WWDC 2026 の新規ではないんですが、Group Lab で「件数だけ欲しいときは件数取得 API を使う」と改めて念押しされていたので、意図を明確にするクリーンアップとして入れました。IntentTodo の場合は実データ量が小さくて体感差はほぼ無い、という正直なところも添えておきます。

## まとめ

- `cloudKitDatabase: .automatic` + entitlements に container + APS + Portal 側の capability 設定が必要
- 全属性に default value、全リレーションを Optional `[T]?` にする
- 旧スキーマのストアは削除して作り直す (開発中)
- production の fallback は silently 壊れる経路になりやすいので、`#if !DEBUG` で `fatalError` にしておく。ただし macOS は entitlement 無しでも `containerURL` がパスを返すので、この分岐自体が効かない
- `Calendar.RecurrenceRule` のように **コンパイルは通るのに schema 初期化で trap する型** がある。CloudKit 互換のために primitive へ落としていると、結果的にこれも避けられる
- **削除済みオブジェクトの配列属性は読めない** (スカラーは耐える)。`isDeleted` のガードでは防げないので、`body` から `@Model` の配列属性を読まず、id から引き直す
- ModelContainer の失敗ログは `String(reflecting:)` + `NSError.userInfo` まで吐く

次回は [App Intents 運用で踏んだ落とし穴 (5/N)](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls) (Live Activity の entity 解決クラッシュ / Control Widget の結果表示 / Spotlight 統合の実装漏れ / 無音で失敗する経路) をまとめて書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-31**: ハマりどころ 5 (`Calendar.RecurrenceRule` は SwiftData 属性にできない — コンパイルは通るが schema 初期化で trap する) と 6 (削除済みオブジェクトの配列属性を読むと trap する。`isDeleted` では防げず、id から引き直す) を追加。どちらも 7/N の reminders スキーマ適合でモデルにフィールドを足したときに踏んだもの
- **2026-08-28**: macOS では entitlement 無しでも `containerURL` がパスを返すため DEBUG フォールバックが働かない、という話を追加 (テスト側は `withKnownIssue` / in-memory コンテナへ)
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-11**: SwiftData Group Lab のマイグレーション指針について、出典 (セッション 8017) が一次資料で確認できなかったため、伝聞である旨に書き換え
- **2026-06-24**: マイグレーション担当プロセスをアプリ本体に固定する方針と、WWDC 2026 の SwiftData レビューを受けた節を追加

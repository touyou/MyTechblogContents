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

ハマりどころは 3 と 4 と 6。順に書きます。

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

(2026-06-24 追記) この「将来 migration プランを書くとき」について、WWDC 2026 の "SwiftData Group Lab" (セッション 8017) で 1 つ指針が示されていました。複数プロセス (アプリ本体 / Widget / Live Activity) が同じ App Group のストアを共有する構成では、**マイグレーションを担当するプロセスをアプリ本体 1 つに固定する** べき、というものです。理由は、アプリ更新直後は **アプリ本体より先に Widget / Extension プロセスが起動し得る** ため。両方がマイグレーションプランを持っていると、Extension が先に移行を試みて本体の移行と競合する危険があります。なので将来 `SchemaMigrationPlan` を導入するときは、**プランを渡すのはアプリ本体の `ModelContainer` だけ** にして、Widget / Live Activity 側はプラン無し (= 移行済みファイルを読むだけ) で構成する方針にしました。この別プロセス前提の話は [3/N](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions) 側にも要点を書いています。なお Group Lab はベータ時点の文字起こし要約ベースなので、実際に導入する段になったら API 名と挙動は公式ドキュメントで確認し直すつもりです。

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

## (2026-06-24 追記) WWDC 2026 の SwiftData レビューを受けて

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
- production の fallback は silently 壊れる経路になりやすいので、`#if !DEBUG` で `fatalError` にしておく
- ModelContainer の失敗ログは `String(reflecting:)` + `NSError.userInfo` まで吐く

次回は [App Intents 運用で踏んだ落とし穴 3 つ (5/N)](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls) (Primary/FromExtension 分離 / Control Widget の Dialog 非表示 / Spotlight 統合の実装漏れ) をまとめて書きます。

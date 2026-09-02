---
title: "WWDC 2026: Todo を「システムが理解できる名詞」にする — ネイティブ型とプロパティマクロ (6/N)"
emoji: "🧩"
type: "tech"
topics: ["AppIntents", "SwiftData", "iOS", "WWDC2026"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 6 回目です。

ここから数本は、WWDC 2026 で増えた App Intents まわりの新要素を IntentTodo で実際に試してみて分かったことを書いていきます。
作業は `xcode27` という別ブランチ (ベータ SDK 検証用) でやっていました。ひととおり検証が終わったので今は `main` にマージ済みで、アプリのベースラインも iOS 27 世代に上がっています。

最初に断っておくと、この WWDC 2026 編は本編より **検証の深さが浅い** です。
本編は「実機で詰まった話」に絞っていましたが、新 API は実機 (Siri / Visual Intelligence) まで通すのに端末や手動確認が必要なものが多くて、自分の手元だとビルド成立 (型レベル) と SPM / テストでの単体実行までしか到達できていないものが結構あります。
なので、この編は「実機でこう動いた」ではなく **「やってみて、この API は採用していいのか / どう設計に効くのか」という設計判断** を軸に書きます。各記事の末尾に、どこまで検証できたかを正直に書いておきます。なお検証の深さは **ビルド (B) / 単体 (U) / 実機 (R)** の 3 段階で表します（以降の記事で「実機 (R)」のように略記するときの凡例です）。

1 本目は Phase 1 としてやった、**Todo というモデルを「システムが理解できる名詞」に育てる** 話です。

## なぜ Todo を「ただの文字列の集合」にしないか

シリーズ 1/N で「Entity (名詞) と Intent (動詞) が設計の原子単位」と書きました。
ただ、本編を書いた時点での `TodoAppEntity` は、正直なところ `title` / `isCompleted` / `dueDate` くらいしか持っていない、わりと痩せた Entity でした。

WWDC 2026 のセッションを見ていて思ったのは、App Schema や Visual Intelligence、cross-app 連携みたいな「外向き」の機能を意味のあるものにするには、Todo がもっと **システム共通の型で語れる名詞** になっていないといけない、ということでした。
「担当者」を `String` で持っているうちは Siri から見れば単なる文字列ですが、`PersonNameComponents` で持てば「人」として解決できる。「所要時間」を秒数の `Double` で持つか `Duration` で持つかで、Shortcuts が出すピッカーも変わってきます。

そこで Phase 1 では、後続の WWDC 2026 要素を載せる土台として、Todo に「場所 / 担当者 / 所要時間」を足しつつ、それらを **システムのネイティブ型として公開する** ところから始めました。

## @Property でモデルの属性をシステムに公開する

まず地味ですが効くのが `@Property` です。
`AppEntity` のプロパティに `@Property(title:)` を付けると、その属性が Shortcuts のアクション出力や Siri の参照対象としてシステムに見えるようになります。

```swift
public struct TodoAppEntity: AppEntity, Hashable, SyncableEntity {
    public var id: String

    @Property(title: "Title")
    public var title: String

    @Property(title: "Completed")
    public var isCompleted: Bool

    @Property(title: "Due Date")
    public var dueDate: Date?

    /// Todo が属するカテゴリ。関連 Entity として公開しておくと、
    /// Siri / Shortcuts からカテゴリで絞り込んだり辿ったりできる。
    @Property(title: "Category")
    public var category: CategoryAppEntity?
    // ...
}
```

ポイントは、`category` のように **別の `AppEntity` を `@Property` で持てる** ことです。
これで「あるカテゴリに属する Todo」みたいな辿り方が Shortcuts 側で組めるようになります。名詞と名詞を関連でつなぐ、というのを App Intents の語彙でやっている感じです。

### @Property(indexingKey:) でセマンティック検索に載せる

この記事を公開したあと、`@Property` にはもう一段先があると知って (セッション 240)、`indexingKey:` も採用しました。
`@Property(title:indexingKey:)` の `indexingKey` に `CSSearchableItemAttributeSet` の KeyPath を渡すと、そのプロパティの値が Spotlight のセマンティックインデックスへ宣言的にマップされて、意味ベースの検索や Q&A の対象になります。5/N で書いた `CSSearchableIndex` の明示登録 (キーワード検索の経路) とは併存できて、その上にセマンティックな経路が足される形です。

```swift
#if os(iOS) || os(macOS) || os(visionOS)
/// The title of the todo item (semantically indexed via `.title`).
@Property(title: "Title", indexingKey: \.title)
public var title: String

/// A longer free-text description of the todo, if any (semantically indexed
/// via `.contentDescription`).
@Property(title: "Description", indexingKey: \.contentDescription)
public var todoDescription: String?
#else
/// The title of the todo item.
@Property(title: "Title")
public var title: String

/// A longer free-text description of the todo, if any.
@Property(title: "Description")
public var todoDescription: String?
#endif
```

やってみて分かったことが 2 つあります。

- 自然文の本文をどのキーに載せるかは少し迷いました。全文向けには `\.textContent` (`CSSearchableItemAttributeSet_Messaging.h` にある、メールやメッセージの本文全文を想定したキー) もあるんですが、Todo の詳細説明なら `CSDocuments` 側の `\.contentDescription` (「アイテムの説明文」) の方が意味的に近いと思ったので、そちらにしています。型で選べないわけではなくて、`EntityProperty.init(indexingKey:)` が取るのは `PartialKeyPath<CSSearchableItemAttributeSet>` だけなので `String?` でも `AttributedString?` でも同じオーバーロードが使えます。意味で選んだ、という話です。
- `indexingKey:` 付きのオーバーロードは **watchOS / tvOS では vend されていません**。`extra argument 'indexingKey' in call` でビルドが落ちるので、上のコードのとおり素の `@Property` にフォールバックしています。しかもこれ、iOS destination のビルドでは何も起きず、**watchOS を含むフルビルドで初めて露見** します。entity まわりを触ったら複数 destination を回す、というのはこの後も何度か出てくる教訓です。

  このガード、長らく `#if os(iOS) || os(macOS)` と書いていて、visionOS も除外していました。SDK の availability を 1 つずつ確かめ直したら **visionOS では普通に使える** (`IndexedEntity` も `CSSearchableIndex.indexAppEntities` も `IndexedEntityQuery` も visionOS SDK に居ます) と分かったので、今は `|| os(visionOS)` を足しています。visionOS の出荷メタデータにもちゃんと `Indexed` が付きました。

  ただこれ、**Apple が途中で対応を広げたのか、当時の自分の切り分けが間違っていたのか、今からは判別できません**。当時の記録に「どの SDK で、どの面がどう落ちたか」を書いていなかったからです (たぶん watchOS で落ちたのを visionOS にも広げて書きました)。availability を記録するときは **落ちた面・試した面・測った SDK を書き分ける**、というのがここでの教訓でした。

あとから 1 つ事故に気付いて直しました。`indexingKey:` はプロパティを `CSSearchableItemAttributeSet` のキーにマップするものなので、**同じキーを `IndexedEntity.attributeSet` 側でも埋めていると衝突します**。どちらが勝つかは公式に定義されていません。IntentTodo は `todoDescription` を `\.contentDescription` にマップしているのに、`attributeSet` の方でも `contentDescription = "Completed" / "Incomplete"` を上書きしていたので、**セマンティック検索に載せたかった本文が固定文に置き換わりうる** 状態でした。完了状態は `keywords` で表現する形に変えて、`attributeSet` には `indexingKey:` で表現できない属性 (期限やキーワード) だけを書くようにしています。

深さは他と同じくビルド成立 (B) までで、セマンティック検索が実際に賢くなるかは実機待ちです。

## ネイティブ型で受ける: Duration / PersonNameComponents / PlaceDescriptor

ここが Phase 1 でいちばん設計判断が要ったところでした。

WWDC 2026 で、`@Parameter` や `@Property` に `Duration` / `PersonNameComponents` / `PlaceDescriptor` (GeoToolbox) といった **システム共通のネイティブ型** をそのまま使えるようになりました。
これらを使うと、Siri / Shortcuts が型に応じた入力 UI (期間ピッカー、連絡先からの人名解決、場所の解決) を出してくれます。

ただ、ここで CloudKit と正面衝突します。
本編 4/N で書いたとおり、SwiftData + CloudKit 互換にするには **全属性が optional か default value 付きの primitive** でないといけません。`Duration` や `PlaceDescriptor` をそのまま `@Model` に持たせるのは無理があります。

そこで採った設計が、**保存層は CloudKit 互換の primitive、App Intents の境界でネイティブ型に変換する** という二重表現です。

モデル (`TodoItem`) 側は、あくまで primitive で持ちます。

```swift
@Model
public final class TodoItem {
    /// 所要時間は TimeInterval (秒) で保存。境界で Duration に橋渡し。
    public var estimatedDuration: TimeInterval?

    /// 担当者は整形済みの String で保存 (CloudKit-safe)。
    /// 入力は PersonNameComponents で受けて、ここで文字列に整形する。
    public var assigneeName: String?

    /// 場所は name + 緯度経度の primitive に分解して保存。
    public var locationName: String?
    public var locationLatitude: Double?
    public var locationLongitude: Double?
    // ...
}
```

Entity (`TodoAppEntity`) 側は、ネイティブ型で公開します。

```swift
/// 所要時間。App Intents ネイティブの Duration で公開する。
@Property(title: "Estimated Duration")
public var estimatedDuration: Duration?

/// 担当者名。
@Property(title: "Assignee")
public var assigneeName: String?

/// 関連する場所。GeoToolbox の PlaceDescriptor で公開する。
@Property(title: "Location")
public var location: PlaceDescriptor?
```

そして、入力を受ける `AddTodoIntent` の `@Parameter` はネイティブ型で受けて、`perform()` の中で primitive に落とします。

```swift
@Parameter(title: "Estimated Duration")
public var estimatedDuration: Duration?

@Parameter(title: "Assignee")
public var assignee: PersonNameComponents?

@Parameter(title: "Location")
public var location: PlaceDescriptor?

@MainActor
public func perform() async throws -> some IntentResult & ... {
    let entity = try todoService.create(
        title: title,
        // Duration → TimeInterval
        estimatedDuration: estimatedDuration.map { Double($0.components.seconds) },
        // PersonNameComponents → String
        assigneeName: assignee.map { PersonNameComponentsFormatter().string(from: $0) },
        // PlaceDescriptor → name + 緯度経度
        locationName: location.flatMap { TodoPlace.decompose($0).name },
        locationLatitude: location.flatMap { TodoPlace.decompose($0).latitude },
        locationLongitude: location.flatMap { TodoPlace.decompose($0).longitude }
    )
    // ...
}
```

場所の変換は、`PlaceDescriptor` まわりが少しややこしいので `TodoPlace` という enum に橋渡しを切り出しました。

```swift
enum TodoPlace {
    static func descriptor(name: String?, latitude: Double?, longitude: Double?) -> PlaceDescriptor? {
        if let latitude, let longitude {
            return PlaceDescriptor(
                representations: [.coordinate(CLLocationCoordinate2D(latitude: latitude, longitude: longitude))],
                commonName: name
            )
        }
        if let name {
            return PlaceDescriptor(representations: [.address(name)], commonName: name)
        }
        return nil
    }

    static func decompose(_ place: PlaceDescriptor) -> (name: String?, latitude: Double?, longitude: Double?) {
        (place.commonName, place.coordinate?.latitude, place.coordinate?.longitude)
    }
}
```

「入力と公開はシステム型、保存は primitive、境界で変換」というのは、書く前は二度手間っぽくて気が進まなかったんですが、やってみると役割がきれいに分かれて結構気持ちよかったです。
Siri に見せる顔 (リッチな型) と、CloudKit に保存する都合 (枯れた primitive) は、そもそも要求が別物なので、無理に 1 つの表現に寄せない方が素直だなと思いました。

### Transferable + ValueRepresentation で外にも書き出せる名詞にする

ネイティブ型の話には続きがあって、99/N の将来トピックに挙げていた `ValueRepresentation` (セッション 240 / 345) もその後採用しました。
`TodoAppEntity` を `Transferable` に適合させて `transferRepresentation` に表現を並べると、Todo をドラッグ / コピー / 共有で **構造化された値としてアプリの外に書き出せる** ようになります。

```swift
extension TodoAppEntity: Transferable {
    public static var transferRepresentation: some TransferRepresentation {
        ProxyRepresentation(exporting: \.title)   // タイトルを plain text で

        ValueRepresentation(exporting: { (todo: TodoAppEntity) -> IntentPerson in
            guard let name = todo.assigneeName, !name.isEmpty else {
                throw IntentError.notFound("Todo has no assignee to export")
            }
            return IntentPerson(
                identifier: .applicationDefined(todo.id),
                name: .displayName(name),
                handle: nil
            )
        })

        ValueRepresentation(exporting: { (todo: TodoAppEntity) -> PlaceDescriptor in
            guard let location = todo.location else {
                throw IntentError.notFound("Todo has no location to export")
            }
            return location
        })
    }
}
```

担当者は `IntentPerson`、場所は `PlaceDescriptor` という **システムの intent value 型** へ橋渡ししています。この節で書いた「二重表現」の外向き版で、保存は primitive でも境界でネイティブ型に揃えてあったからこそ、export がすんなり書けました。

細かい気付きも 2 つ書いておきます。

- `IntentPerson(identifier:name:handle:)` は **全引数が必須** でした。`handle` を省くと `Missing arguments for parameters 'identifier', 'handle'` になるので、無いものは明示的に `nil` を渡します。
- export closure は `async throws` なので、担当者や場所が無い Todo は **`throw` してその表現ごと出さない** 形にしました。空っぽの `IntentPerson` を返すより、「この Todo に人の表現は無い」とシステムに伝わる方が筋がいいと思います。

### SDK バグで `@Parameter` だけ `String` に退避している

ここまでさんざん「ネイティブ型で受ける」と書いておいて何なんですが、**`AddTodoIntent.location` だけは今も場所名の `String`** です。SDK のバグを踏むためで、Feedback (FB24548956) を出して待っている状態です。

きっかけは Xcode Cloud が赤くなったことでした。ログを追うと `AppIntentsSSUTraining` (Siri の音声理解の学習アセットを作るフェーズ) が、`PlaceDescriptor` のパラメータを SSU の variable に変換するときに、裏側のシステム Entity 型名 `GeoToolbox.PlaceDescriptorEntity` をそのまま variable 名に使っていて、**ドットが入っているせいで検証器の正規表現 `^[a-zA-Z_][a-zA-Z_$0-9]*$` に落ちて** いました。生成器と検証器が食い違っている形なので、アプリ側でできることは「その型を使わない」しかありません。

厄介なのが壊れ方で、手元の `xcodebuild` は exit 0 (`** BUILD SUCCEEDED **`) で返ってきます。Xcode Cloud が emitted error を失敗扱いにするので、そこで初めて表に出てきました。実害は「該当 Intent だけ」ではなく、**そのターゲットの全 App Shortcut が音声理解の学習アセットを失う** ことです (`nlu/` が丸ごと生成されなくなります)。

#### 発火条件はもっと狭く、対象の型はもっと広かった

長らく「`PlaceDescriptor` を `@Parameter` にも `@Property` にも置けない」と書いていたんですが、Feedback に出す材料を作るために最小プロジェクトで 1 条件ずつ測り直したら、**`@Property` 側は裏が取れていませんでした**。

| 形 | 結果 |
|---|---|
| `@Parameter var place: PlaceDescriptor?` + `AppShortcutsProvider` に登録 | **エラー** |
| 同じ Intent を `AppShortcutsProvider` から外す | 緑 |
| entity の `@Property var place: PlaceDescriptor` (スキーマ適合の入れ子) | 緑。`nlu/` も生成される |
| `@Parameter var place: String?` に変えただけの対照 | 緑 |

SSU の variable は「**App Shortcut が参照する Intent のパラメータ型名**」から作られるので、entity の `@Property` はそもそも variable になりません。当時「`@Property` でも発生する」と記録した probe は、`@Parameter` の probe と同居していたんだと思います。

逆に、対象の型は `PlaceDescriptor` 固有ではありませんでした。SDK の swiftinterface をなめると `_SystemIntentValue` に適合する型は 5 つあって、確かめた 4 つが全部同じ形で落ちます (`LinkPresentation.LinkMetadata` / `MediaIntents.AudioSearch` / `Photos.PHAsset` も同様)。どれも公式が「サポートされるパラメータ型」の **Other system types** として明記しているものです。

さらに、**リリース版の Xcode 26.6 でも再現しました**。`PlaceDescriptor` の `_SystemIntentValue` 適合は iOS 26 からなので、ベータ特有の話ではなく **26 世代から出荷されているバグ** だった、ということになります。Apple の公式サンプル (UnicornChat) に 13 行足すだけでも同じエラーが出ます。

#### 分かったので entity 側は戻した

というわけで、**`TodoAppEntity.location` は `PlaceDescriptor?` に戻しました**。退避が要るのは `AddTodoIntent.location` (App Shortcut に登録済み Intent の `@Parameter`) だけです。

戻したら副産物がありました。退避していた間、`ValueRepresentation` は `TodoPlace` 経由で組み直していたので `latitude` / `longitude` に `nil` を渡していて、**座標が落ちていました** (住所表現だけを export していた)。entity が `PlaceDescriptor` を持つようになったので、モデルに緯度経度があれば `.coordinate` 表現がそのまま Maps へ流れます。

不幸中の幸いだったのが、この節で書いた「入力と公開はシステム型、保存は primitive、境界で変換」の二重表現にしていたおかげで、**退避も復帰も触ったのが境界だけで済んだ** ことでした。モデルは最初から `locationName` + 緯度経度の primitive なので、`@Model` もマイグレーションも一切触っていません。ネイティブ型を保存層まで通す設計にしていたら、SDK バグひとつで永続化スキーマまで巻き添えになっていたはずです。

#### 判定は必ずクリーンビルドで

検証で 1 つ気を付けることがあって、**SSU のタスクは incremental ビルドだと前回のエラーをそのままログに再表示してきます**。`Metadata.appintents` が変わっていないとタスク自体が再実行されないためで、編集直後のビルドが緑でも、SSU セクションのタイムスタンプが編集前のままだったりします。「直った」とも「まだ落ちてる」とも誤読できる形なので、判定は DerivedData ごと消してからにしないといけません。ビルドログを再現性の判定に使うなら、**そのログがいつ生成されたものか** まで見る、というのは地味に効く教訓でした。

## `parameterSummary` は Shortcuts 編集画面の allowlist

Entity の話から少し逸れますが、`@Parameter` を足すときにセットで踏むところなので書いておきます。

`AddTodoIntent` にネイティブ型のパラメータをいろいろ足したあと、**それらが Shortcuts の編集画面に 1 つも出ていない** ことに気付きました。原因は `parameterSummary` で、Apple のガイダンスがこう明言しています。

> `ParameterSummary` is not cosmetic — it is the allowlist for which parameters the Shortcuts editor surfaces. […] every other `@Parameter` is **silently omitted** from the editor UI, even though it still exists and still resolves.

編集行になるのは **`Summary("...")` の補間に出てくるもの** と **trailing のブロックに列挙したもの** だけです。`AddTodoIntent` の summary は `Summary("Add todo titled \(\.$title)")` だけだったので、`dueDate` / `isFavorite` / `estimatedDuration` / `assignee` / `location` は **Shortcuts からそもそも設定できませんでした**。`UpdateTodoIntent` に至っては、8/N で書いた「部分更新の三状態」を作り込んだ 6 パラメータが全部隠れています。

```swift
public static var parameterSummary: some ParameterSummary {
    Summary("Add todo titled \(\.$title)") {
        \.$dueDate          // ← この列挙が無いと、どれも Shortcuts で設定できない
        \.$isFavorite
        \.$estimatedDuration
    }
}
```

見落としていたのは、**ビルドが緑で、Siri から名指しすれば動く** からでした。Shortcuts アプリを実際に開かないと気付けない類なので、判定は生成物側で機械的にやるのが良さそうです (`Metadata.appintents` の `otherParameterIdentifiers` に並びます)。

「`@Parameter` を足した」は「書き込む経路ができた」を意味しない、というのがここでの学びでした。今は **Intent が変えられるものは全部 `parameterSummary` に載せる** をルールにしています。

そして、この非対称はちょうど裏返しの形でも起きていました。**場所 (`location`) は `AddTodoIntent` では受け取れるのに、`UpdateTodoIntent` にはパラメータが無く、アプリの編集画面にも欄がありませんでした**。作成時に付けた場所を後から直す手段がまったく無かったわけです。詳細画面は「値のあるフィールドだけ」を出す作りなので、**見えるのに直せない** という状態で残っていました。

`parameterSummary` の方が「Shortcuts から書けない」で、こちらは「アプリから書けない」。どちらも **どこか 1 つの経路で書けているのを見て、書けると思い込んでいた** のが原因でした。書き込み経路は、Intent・`parameterSummary`・サービス層・UI の 4 つが揃って初めて通るので、属性を足したら 4 つ並べて確認するのが確実そうです。


## @ComputedProperty と @DeferredProperty

Entity のプロパティマクロで、もう 1 つ試したのが `@ComputedProperty` と `@DeferredProperty` です。
どちらも「スナップショットに持っていない値を、導出 / 取得してシステムに公開する」ためのものですが、性格が違います。

先に断っておくと、この 2 つは WWDC 2026 編に入れて書いていますが **出自は iOS 26 (WWDC 2025 セッション 275)** で、2026 の新 API ではありません。345 で増えているのは `RelevantEntities` まわりや `EntityCollection` などの方です。ベースラインが iOS 26 のプロジェクトに iOS 27 の新要素を足していく作り方をしていると、手元では「今の SDK で使えるか」しか見ないので、この 2 世代の境目が自分の中でもあいまいになっていました。

`@ComputedProperty` は同期 getter で、スナップショットが持っている値から軽く導出できるもの向け。
IntentTodo では「期限切れかどうか」を `dueDate` と `isCompleted` から計算しています。

```swift
@ComputedProperty(title: "Is Overdue")
public var isOverdue: Bool {
    guard !isCompleted, let dueDate else { return false }
    return dueDate < Date()
}
```

`@DeferredProperty` は非同期 getter (`get async throws`) で、**要求されたときだけ取りに行く** もの向け。
サブタスクの進捗 (「2/5 completed」みたいな文字列) は SwiftData のリレーションを引かないと作れず、軽いスナップショットには載せたくないので、こちらにしました。

```swift
@DeferredProperty(title: "Subtask Progress")
public var subtaskProgress: String {
    get async throws {
        try await Self.loadSubtaskProgress(forID: id)
    }
}
```

`@DeferredProperty` は **Spotlight の index には含まれず、Siri / Shortcuts にも自動送出されない** という契約になっていて、要求時のフェッチを前提にしています。リレーション越しの重い値をうっかり全件 index に載せてしまう事故を防げるので、棲み分けとしては納得感がありました。

この 2 つ、最初は「重い値を逃がすための道具」くらいに思っていたんですが、7/N でスキーマ適合をやったら **どちらも別の用途で効きました**。

- `@ComputedProperty` は **名前の付け替え** に使えます。スキーマが要求する綴り (`note` / `creationDate` / `isFlagged`) とアプリの既存名が違うとき、別名を足すだけで満たせるので、モデルのリネームが要りません
- `@DeferredProperty` は **その場のオブジェクトを読まずに id から引き直す** ための道具でもあります。SwiftData は削除済みオブジェクトの配列属性を読むと trap するので、`tags` / `urls` のような配列は deferred にして逃がしました (4/N)。スキーマ要求は deferred のままでも満たせます

「軽い / 重い」の軸だけで選ぶものだと思っていたら、**スナップショットに値を持たない** という性質そのものが効く場面があったわけです。

ここで 2 つハマりどころがありました。

### ハマりどころ 1: Entity は @Dependency を使えない

`subtaskProgress` の getter の中でサブタスクをフェッチしたいわけですが、`AppEntity` の中では `@Dependency` が使えません。
Apple のドキュメントいわく、dependency injection は「メインアプリから *Intent* へデータを渡すためだけ」のもので、`EntityQuery` では使えても `AppEntity` 本体では `Unknown attribute 'Dependency'` になります。

そこで、共有 `ModelContainer` をアプリ起動時に `TodoEntityStore` という `@MainActor enum` の static に登録しておいて、deferred getter からはそこを参照する形にしました。
Apple のサンプルコードにある ambient な `modelData` アクセサと同じ発想です。

```swift
@MainActor
public enum TodoEntityStore {
    public static var container: ModelContainer?

    public static func register(container: ModelContainer) {
        self.container = container
    }
}
```

```swift
private static func loadSubtaskProgress(forID id: String) async throws -> String {
    try await MainActor.run {
        guard let container = TodoEntityStore.container else {
            return String(localized: "No subtasks")
        }
        let repository = SwiftDataTodoRepository(modelContext: container.mainContext)
        // ... サブタスクを引いて "completed/total completed" を組む ...
    }
}
```

プレビューや SPM テストみたいに未登録の場面では、空の結果に degrade させて落ちないようにしています。

登録場所については、最初「deferred property が走るのはメインアプリプロセスだけだから `App.init()` で 1 回登録すれば足りる」と書いていたんですが、これは足りませんでした。2/N に書いたとおり Widget / Control の Intent は既定でどちらのプロセスでも実行されうるので、**Widget Extension 側の `WidgetBundle.init()` でも登録が要ります**。登録し忘れると、Extension プロセスで解決されたときだけ中身が空になって「Todo not found」が描かれる、という切り分けにくい症状になりました。

```swift
MainActor.assumeIsolated {
    AppDependencyManager.shared.add(dependency: todoService)
    TodoEntityStore.register(container: sharedWidgetModelContainer)   // ← これも要る
}
```

`@Dependency` (`AppDependencyManager`) への登録と `TodoEntityStore` への登録は **別々** です。前者だけ登録して満足すると、Intent は動くのに deferred property や snippet だけ空、という形で出てきます。同じ「プロセスごとに登録が要るもの」なので、片方を足したらもう片方も確認する、と覚えておくのが良さそうでした。

### ハマりどころ 2: プロパティマクロで Hashable の自動合成が壊れる

これは実装してはじめて気付いたやつです。
`@ComputedProperty` / `@DeferredProperty` (あるいは後述する App Schema のマクロ) を付けると、マクロが内部に `EntityProperty` という **非 `Hashable` な backing storage** を生やします。
その結果、`Hashable` / `Equatable` の自動合成が効かなくなって、`TodoAppEntity` を `Set` や `NavigationPath` に入れているところでビルドが通らなくなりました。

対処は `==` と `hash(into:)` を明示実装するだけです。
等価判定はスナップショットの値で、hash は安定した `id` だけで取る、という形にしました。

```swift
public static func == (lhs: TodoAppEntity, rhs: TodoAppEntity) -> Bool {
    lhs.id == rhs.id
        && lhs.title == rhs.title
        && lhs.isCompleted == rhs.isCompleted
        // ... 他のスナップショット属性も比較 ...
}

public func hash(into hasher: inout Hasher) {
    hasher.combine(id)
}
```

ちなみに `location` (`PlaceDescriptor`) は `Equatable` が保証されていないので等価比較からは外しています。保存している name / 緯度経度はモデル経由で結局反映されるので、実害は無いと判断しました。

この `Hashable` 合成の問題は Xcode 27 beta 2 でも直っていませんでした。beta 2 対応のついでに明示実装を外してビルドし直してみたら、やっぱり `does not conform to protocol 'Hashable'` で落ちたので、当面は明示実装が必要なままです。

## 関連を Entity 化する: Category / SubTask

痩せた Todo を太らせるついでに、`Category` と `SubTask` も `AppEntity` 化して、それぞれ `EntityQuery` を付けました。
これで Siri / Shortcuts から「カテゴリ」を名詞として扱えるようになり、Todo → Category の関連も辿れます。

`CategoryAppEntity` は後の記事 (7/N) で書く App Schema 適合と絡むので深入りはしませんが、こんな見た目です。

```swift
@AppEntity(schema: .reminders.list)
public struct CategoryAppEntity: Hashable {
    public var id: String
    public var name: String
    public var type: TodoListType
    // ...
}
```

## ついでに足せた SyncableEntity

WWDC 2026 の `SyncableEntity` (セッション 345) も、Phase 1 のついでに適合できました。
これは「デバイスをまたいで同じ Entity を一貫して参照できる」ためのプロトコルですが、`TodoAppEntity` の `id` が SwiftData + CloudKit のレコード id をそのまま文字列化したもので、もともとデバイス間で一致しているので、**プロトコル適合を書き足すだけ** で済みました。

```swift
public struct TodoAppEntity: AppEntity, Hashable, SyncableEntity {
    public var id: String  // CloudKit レコード id と同一。デバイス間で一貫。
    // ... 追加の変更なしで適合 ...
}
```

ローカル id と安定 id が別々のアプリだと `id` を `SyncableEntityIdentifier<Local, Stable>` 型にする必要があるみたいですが、IntentTodo はそもそも別 id を持っていないので、`String` id のまま適合できました。
「すでに正しく設計されていると、新 API への適合がタダで済む」のは結構気持ちのいい瞬間で、CloudKit の id 設計をサボらずにやっておいてよかったなと思いました。

## TransientAppEntity で集計値も名詞にする

Phase 1 で 1 つだけ手を付けられずに残していた `TransientAppEntity` (セッション 344) を、Xcode 27 beta 4 のタイミングで試しました。

これは名前のとおり **永続化されないエンティティ** で、`AppEntity` との違いはだいたいこのあたりです。

| | `AppEntity` | `TransientAppEntity` |
|---|---|---|
| `defaultQuery` | 必須 | 不要 |
| 実体 | SwiftData 等の永続データに対応 | 計算済みのスナップショット |
| 参照 | id で Siri / Shortcuts が後から引ける | Intent の戻り値としてだけ使う |
| `@Property` | 使える | 使える |

IntentTodo では「今の Todo リストの集計」を返す `TodoListSummaryEntity` を作りました。

```swift
public struct TodoListSummaryEntity: TransientAppEntity {
    public static let typeDisplayRepresentation: TypeDisplayRepresentation = "Todo List Summary"

    @Property(title: "Pending Todos")
    public var pendingCount: Int

    @Property(title: "Overdue Todos")
    public var overdueCount: Int

    // ... totalCount / completedCount / favoriteCount も同じ形

    public var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(pendingCount) pending, \(overdueCount) overdue")
    }

    public init() {}                          // システムが要求する場面がある
    public init(pendingCount: Int, ...) { }   // 値を渡す方も別に用意しておく
}
```

書いてみて気付いたところをいくつか。

- `defaultQuery` が要らないので `EntityQuery` を 1 つも書かなくていいです。クエリできない型なので `IndexedEntity` も載せません (Spotlight に出しても引く手段が無い)。
- `@Property` は `AppEntity` と同じマクロがそのまま使えて、`Int` みたいな非 Optional もそのまま持てます。
- `init()` と値を渡す `init(...)` の 2 つを用意しておくのが安全でした。プロパティマクロが `EntityProperty` の backing storage を生やす都合で、システム側が引数なし `init()` を要求してくる場面があります。
- `typeDisplayRepresentation` は `static let` で書けます。

返す側の Intent はこんな感じで、`.background` で集計だけして値と dialog を返します。

```swift
public func perform() async throws
    -> some IntentResult & ReturnsValue<TodoListSummaryEntity> & ProvidesDialog {
    let summary = try todoService.summarize()
    return .result(
        value: summary,
        dialog: IntentDialog(
            full: "You have ^[\(summary.pendingCount) pending todo](inflect: true), \(summary.overdueCount) overdue.",
            supporting: "\(summary.pendingCount) pending, \(summary.overdueCount) overdue."
        )
    )
}
```

嬉しいのは Shortcuts 側で、「Get Todo Summary → Overdue Todos が 0 より大きければ通知する」みたいな条件分岐が、`@Property` 1 つずつを変数として組めることでした。既存の `ShowTodosIntent` で Todo を全件返してもらって数を数える、みたいな遠回りをしなくて済みます。サービス層は `fetchAll()` 1 回で全部の件数を作る `summarize()` を足しただけです。

棲み分けとしては、99/N に書いた「通知の `appEntityIdentifiers` は永続 `AppEntity` 必須で `TransientAppEntity` は不可」という制約と表裏だと思っていて、**後から id で名指しされる名詞は `AppEntity`、その場で計算して返すだけの値は `TransientAppEntity`** と分かれている感じです。集計値に無理やり id を付けて永続 Entity に見せかけなくてよくなった、というのが実際に使ってみての感想でした。深さはビルド成立 (B) までで、Shortcuts で実際に条件分岐を組んで走らせるところは実機待ちです。

## 名詞の「見せ方」の作法 — 公式サンプルと突き合わせて直したところ

ここまでは Entity に何を持たせるかの話でしたが、WWDC 2026 の App Intents 系公式サンプル 4 本 (CometCal / UnicornChat / CosmoTunes / PhotosDomainExample) を落としてきて自分のコードと 1 項目ずつ突き合わせたら、**見せ方の方でいくつか間違えていた** ことが分かったので、そこも書いておきます。

### ランタイム文字列は `"\(value)"` の補間で渡す

`DisplayRepresentation(title:)` が取るのは `LocalizedStringResource` です。ここに `LocalizedStringResource(stringLiteral: todo.title)` を渡すと、**ランタイムの文字列がそのままローカライズキーになります**。翻訳テーブルに存在しないキーの引きが毎回走るし、キーが実行時に決まるので String Catalog の抽出対象にもなりません。サンプル 4 本はすべて補間形式でした。

```swift
// ❌ ランタイム値をキーにしている
DisplayRepresentation(title: LocalizedStringResource(stringLiteral: title))

// ✅ 補間形式 (キーは "%@" で、title は引数として渡る)
DisplayRepresentation(title: "\(title)")
```

同じ理由で、**表示すべき subtitle が無いときは空文字ではなく `nil`** を返します (`subtitle` は `LocalizedStringResource?`)。空の `LocalizedStringResource("")` は空キーの引きになるので。3/N に書いたパッケージのローカライズと同じ「型としては通るのに翻訳から外れる」系の話で、この手のものはビルドでは絶対に出てきません。

### Siri は subtitle を読み上げる

CosmoTunes の `TimerEntity` / `AlarmEntity` にコメントで明記してあったんですが、`DisplayRepresentation` の subtitle は **音声で読まれます**。なので `"5:00"` のような位置指定の表記を入れると「ご、コロン、ぜろ、ぜろ」と読まれてしまいます。`Duration.formatted(.units(width: .wide))` や `Date.FormatStyle` の自然文表記を使え、ということでした。

IntentTodo の `TodoAppEntity` の subtitle は `dueDate.formatted(date: .abbreviated, time: .omitted)` で最初から自然文だったのでセーフでしたが、**今後 subtitle に時刻を足すときに踏む** やつなので書き留めておきます。「表示に使う文字列」と思って書いたものが耳にも流れる、というのは Entity を Siri に見せる設計だと常に付いて回ります。

### `synonyms:` と、画像の遅延クロージャ

CosmoTunes は entity ごとに `synonyms:` を付けて Siri のマッチ幅を広げていて、画像は **トレーリングクロージャ形** で渡していました。テキストだけ必要な文脈では画像を解決させない、という意図です。

```swift
DisplayRepresentation(
    title: "\(title)",
    subtitle: "^[\(trackCount) track](inflect: true)",
    synonyms: ["\(title) mix tape", "\(title) playlist"]
) {
    DisplayRepresentation.Image(systemName: "music.note.list")
}
```

複数形は `^[\(n) track](inflect: true)` で inflection を効かせます。IntentTodo も Todo / Category / SubTask の 3 つを `synonyms:` + 遅延クロージャ形にして、集計 Entity の件数は `^[\(n) todo](inflect: true)` に直しました (それまで `count == 1 ? "todo" : "todos"` と手で書いていたところです)。

組み立ては `makeDisplayRepresentation(...)` という static 関数に寄せました。理由は次の項目です。

### `displayRepresentations(for:)` で候補一覧を軽くする

`EntityQuery` には表示表現だけをまとめて返す口があります。公式いわく "Return full representations; the system materializes only the components it needs (for example, dropping a deferred image when only text is required)" で、候補一覧の描画で entity 本体を N 回組み立てるコストを避けるためのものです。

既定の実装は `entities(for:)` を呼んでから 1 件ずつ `displayRepresentation` を読むので、IntentTodo だと「表示に使わない `CategoryAppEntity` の生成」がまるごと乗ってきます。`TodoEntityQuery` / `CategoryEntityQuery` / `SubTaskEntityQuery` の 3 つに実装して、いずれも **SwiftData のモデルから直接** `makeDisplayRepresentation(...)` を呼ぶ形にしました。表示表現の組み立てを static 関数に切り出したのは、ここで entity を作らずに同じ表現を返せるようにするためです。

### 文字列の突き合わせは全部 `localizedStandardContains(_:)`

もう 1 つ、地味だけど効く直しがありました。`EntityStringQuery.entities(matching:)` は **システムが絞り込んでくれない** ので自分でフィルタするんですが、そこに `lowercased().contains()` を使うとロケール非依存になって、かな / カナやダイアクリティカルマーク、トルコ語の I などを別物として扱います。

適用先は `EntityStringQuery` に限りませんでした。「人が読む文字列同士を突き合わせる」場所は全部同じです。

| 場所 | 突き合わせるもの |
|---|---|
| `TodoEntityQuery` / `CategoryEntityQuery` | Siri / Shortcuts が渡す文字列 ↔ タイトル・カテゴリ名 |
| `SearchEverythingIntent` | `query` パラメータ ↔ タイトル・カテゴリ名 |
| `TodoVisualIntelligenceQuery` | Visual Intelligence のラベル ↔ タイトル・カテゴリ名 |
| リスト画面の検索フィールド | 入力文字列 ↔ タイトル |

Visual Intelligence のラベルは英語主体なので最初は例外にしていたんですが、**突き合わせ先の Todo は日本語** なので例外にする理由がありませんでした。`localizedStandardContains` は自前の小文字化も要らなくなるので、10/N に書いた `labels.map { $0.lowercased() }` みたいな前処理も一緒に消えています。

### サンプルにも古い書き方は残っている

最後に、これは逆向きの学びですが、**公式サンプルを無批判に真似するのも危ない** です。UnicornChat の `DraftMessageIntent` や PhotosDomainExample の削除系 Intent は `static let openAppWhenRun = true` を使っていて、これは公式の `supportedModes` ドキュメントでは `.foreground(.immediate)` と同等の旧 API 扱いになっています。CometCal の `EventEntity.displayRepresentation` も `DateFormatter` をその都度生成していて、自分は `Date.FormatStyle` の方に寄せる派なのでそこは真似していません。サンプルは「今の推奨」ではなく「動く実例」だと思って読むくらいがちょうどよさそうです。

## 検証できた深さ

正直に書いておくと、この回の内容は以下の深さです。

- **ビルド成立 (型レベル)**: 全部 OK。`Duration` / `PersonNameComponents` / `PlaceDescriptor` / 各プロパティマクロ / `SyncableEntity` / 後から足した `TransientAppEntity` はコンパイルが通り、API 採用としては妥当だと判断しています。
- **単体 (SPM / テスト)**: Entity 変換・`ValueRepresentation` の export・`parameterSummary` の生成物は、AppIntentsTesting と出荷メタデータの検査で確認済みです (10/N)。
- **実機 (Siri が実際にネイティブ型ピッカーを出すか、deferred property がいつ呼ばれるか)**: 未確認です。ここは端末での手動確認が要るので、できたら追記します。
- `PlaceDescriptor` は entity の `@Property` としては戻していますが、`AddTodoIntent` の `@Parameter` だけは SDK バグ (FB24548956) の回避で `String` のままです。

なので本記事は「これらの API を採用して設計に組み込むと、こういう構造になる」という設計判断の記録として読んでもらえればと思います。

## まとめ

- WWDC 2026 編は `xcode27` ブランチでの検証 (現在は `main` にマージ済み) で、本編より浅い (主に型レベル + 単体)。実機可否より「採用していいか / 設計にどう効くか」を書く
- `@Property` でモデル属性をシステムに公開し、関連 (`category`) も Entity として持てる
- `Duration` / `PersonNameComponents` / `PlaceDescriptor` はネイティブ型で入力・公開し、保存は CloudKit 互換 primitive に落とす「二重表現」にする。境界で変換する
- SSU training のバグが出るのは **App Shortcut に登録した Intent の `@Parameter` に system value 型を置いたとき** だけ。entity の `@Property` は SSU の variable にならないので踏まない。`PlaceDescriptor` 固有でもベータ特有でもなく、iOS 26 世代から出荷されている (FB24548956)
- **`parameterSummary` は Shortcuts 編集画面の allowlist**。載せ忘れたパラメータは黙って編集できなくなる (ビルドは緑、Siri から名指しすれば動く)。裏返しに「Shortcuts からは書けるのにアプリからは書けない」属性も生まれる。書き込み経路は Intent・`parameterSummary`・サービス層・UI の 4 つが揃って初めて通る
- `@ComputedProperty` (同期・軽い導出) と `@DeferredProperty` (非同期・要求時フェッチ、Spotlight 非 index) を使い分ける。どちらも出自は iOS 26 で、2026 の新 API ではない。**スナップショットに値を持たない** という性質は、スキーマ要求名の付け替えや、削除済みオブジェクトを読まないための逃がしにも効く
- Entity は `@Dependency` を使えないので、共有コンテナは `TodoEntityStore` に置いて参照する。`AppDependencyManager` とは別々の登録なので、アプリと Widget Extension の両プロセスで登録する
- プロパティマクロは `Hashable` 自動合成を壊すので `==` / `hash(into:)` を明示実装する
- `SyncableEntity` は CloudKit id をそのまま使っていれば適合を書き足すだけで済む
- 集計値のように後から id で引かれないものは `TransientAppEntity` にすると、`EntityQuery` も永続化も無しで Shortcuts の条件分岐に載せられる
- 表示表現は **ランタイム値を補間形式で渡す** (`stringLiteral:` はキー扱いになる)。subtitle は Siri が読み上げるので位置指定の書式を避ける。候補一覧は `displayRepresentations(for:)` で entity を作らずに返す
- `indexingKey:` と `attributeSet` で同じ Spotlight キーを二重に埋めない。人が読む文字列の突き合わせは全部 `localizedStandardContains(_:)` に揃える

次回は、[ここで Entity 化した `Category` と Todo 本体を reminders ドメインのスキーマに適合させた話 (7/N)](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-31 (2)**: `parameterSummary` の節に、裏返しの非対称 (場所が `AddTodoIntent` では受け取れるのに `UpdateTodoIntent` とアプリの編集画面には無く、後から直せなかった) を追加
- **2026-08-31**: `PlaceDescriptor` の節を全面的に書き換え。SSU バグの発火条件は **App Shortcut 登録済み Intent の `@Parameter` だけ** と切り分けられたので、entity の `@Property` は `PlaceDescriptor?` に戻した (退避中に落ちていた座標も export されるようになった)。バグが `PlaceDescriptor` 固有でもベータ特有でもないこと、Apple へ報告済み (FB24548956) を追記。`indexingKey:` のガードに visionOS を追加 (以前の「visionOS でも落ちる」という記述は、当時どの SDK で何が落ちたかを書き残していなかったため真偽を判別できず)。`parameterSummary` が Shortcuts 編集画面の allowlist である話を新設
- **2026-08-28**: 表示表現の作法 (補間形式 / Siri が読む subtitle / `synonyms:` と遅延クロージャ / `displayRepresentations(for:)` / `localizedStandardContains`) の節を、公式サンプル 4 本との突き合わせとして追加。`indexingKey:` と `attributeSet` で同じキーを二重に埋めていたのを訂正。検証ブランチが `main` にマージされたことを反映。重複していた 1 行を削除
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: `TodoEntityStore` の登録について「`App.init()` で 1 回登録すれば足りる」と書いていたのを訂正 (Widget Extension 側でも登録が要る)
- **2026-08-11**: `\.textContent` は「SDK に露出していない」と書いていたが誤りで、実在する (`contentDescription` を選ぶ理由を型の制約から意味の制約に訂正)。`@ComputedProperty` の出自を 345 → **275** に再訂正 (2026-08-05 の訂正自体が誤りだった)。`PlaceDescriptor` の SSU バグは beta 5 でも未修正、判定は必ずクリーンビルドで行う旨を追加
- **2026-08-05**: `@ComputedProperty` / `@DeferredProperty` を「WWDC 2026 の新要素」として書いていたのを訂正
- **2026-07-28**: `TransientAppEntity` (`TodoListSummaryEntity` + `GetTodoSummaryIntent`) の節を追加。beta 3 の SSU バグで `PlaceDescriptor` を `String` に退避した経緯を追加
- **2026-07-02**: `@Property(indexingKey:)` の節と `Transferable` + `ValueRepresentation` の節を追加。`Hashable` 合成の問題が beta 2 でも継続することを確認

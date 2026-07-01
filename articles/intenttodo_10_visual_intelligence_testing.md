---
title: "WWDC 2026: Visual Intelligence 連携と AppIntentsTesting で実経路テスト (10/N)"
emoji: "👁️"
type: "tech"
topics: ["AppIntents", "VisualIntelligence", "iOS", "WWDC2026"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 10 回目です。
WWDC 2026 編 (6〜10) の最後で、`xcode27` ブランチでの検証です (前提は 6/N 冒頭)。

最後は外向きのサーフェスとして Visual Intelligence 連携 (セッション 297) と、Intent を実際の経路で動かすテスト基盤 (AppIntentsTesting / #295) を試した話です。

## カメラ/スクショから自分のアプリのコンテンツを返す: IntentValueQuery

Visual Intelligence は、カメラやスクショの visual search に対して、アプリのコンテンツを候補として出せる仕組みです。
入口になるのが `IntentValueQuery` で、システムが visual search のたびに呼んでくれます。

```swift
#if canImport(VisualIntelligence)
import AppIntents
import VisualIntelligence

public struct TodoVisualIntelligenceQuery: IntentValueQuery {
    @Dependency
    var todoService: TodoService   // ← IntentValueQuery は @Dependency が使える

    public func values(for input: SemanticContentDescriptor) async throws -> [TodoOrCategory] {
        let labels = input.labels.map { $0.lowercased() }
        guard !labels.isEmpty else { return [] }

        // TodoService は MainActor 隔離。ホップして snapshot を取り、
        // 以降は Sendable な entity 値で off-actor フィルタする。
        let todos = try await MainActor.run { try todoService.listTodos(filter: .all) }
        // ... labels を todo タイトル / カテゴリ名に部分一致させて返す ...
        return matchedTodos + matchedCategories
    }
}
#endif
```

ここがおもしろかった点をいくつか。

- **`IntentValueQuery` は `@Dependency` が使えます**。6/N で「`AppEntity` は `@Dependency` 使えない」と書きましたが、value query の方は `_SupportsAppDependencies` に適合しているので、`TodoService` を直接注入できます。entity みたいに `TodoEntityStore` を迂回しなくていいので、ここは素直でした。
- 戻り値が **単一 Entity 型に縛られない** のが `EntityQuery` との違いです。9/N で作った `@UnionValue` の `[TodoOrCategory]` をそのまま返せるので、Todo とカテゴリの混在結果を出せます。
- `SemanticContentDescriptor` は `labels: [String]` と `pixelBuffer: CVReadOnlyPixelBuffer?` を持っています。`labels` は一般的な英語ラベル (建物の固有名みたいなのは来ない、`en_US`、同義語や翻訳なし) です。本アプリは labels を Todo タイトル / カテゴリ名に部分一致させました。`pixelBuffer` で画像一致もできますが、それは ML モデルが要るので今回は見送りました。
- **並行性**: `values(for:)` は nonisolated なので、MainActor の `TodoService` は `MainActor.run { ... }` でホップして取得して、その後は Sendable な `TodoAppEntity` 値で off-actor にフィルタする、という形にしています。
- 他の query と同じで **登録は不要** で、システムが自動発見します (AppShortcut も要りません)。

そして、結果まわりは **これまでに作った部品をそのまま再利用** できました。

- 結果をタップして詳細を開く経路 → 7/N の `OpenTodoIntent` (`OpenIntent`)
- 複数結果型 → 9/N の `@UnionValue` (`TodoOrCategory`)

Visual Intelligence のために新しい Entity や型を増やさずに済んだのは、Entity と Intent を最初から「再利用できる部品」として設計してきた効果かなと思っていて、シリーズ 1/N で書いた「名詞と動詞が原子単位」という話がここで効いた感じがありました。

## 「もっと見る」: semanticContentSearch schema

visual search の結果から「More results」をタップしたときに対応する Intent も用意しました。
これは `@AppIntent(schema: .visualIntelligence.semanticContentSearch)` でスキーマに適合させます。

```swift
#if canImport(VisualIntelligence)
@AppIntent(schema: .visualIntelligence.semanticContentSearch)
public struct TodoSemanticContentSearchIntent: AppIntent {
    @Parameter(title: "Semantic Content")
    public var semanticContent: SemanticContentDescriptor

    @Dependency
    var navigationModel: NavigationModel

    @MainActor
    public func perform() async throws -> some IntentResult {
        navigationModel.navigateToRoot()
        return .result()
    }
}
#endif
```

7/N で reminder 本体スキーマに苦しんだので身構えていたんですが、こっちのスキーマは `@Parameter var semanticContent: SemanticContentDescriptor` だけを持つ形を要求してくるだけで、**entity プロパティを持たない** ので、あの `EntityProperty` init 地雷を踏みませんでした。
同じ「スキーマ適合」でも、entity プロパティを要求するかどうかで難易度が全然違う、というのが対比で見えたのは収穫でした。

なお `VisualIntelligence` は **iOS 専用** のフレームワークです。このパッケージは macOS / watchOS / visionOS / Widget Extension でもビルドするので、Visual Intelligence 関連のファイルは丸ごと **`#if canImport(VisualIntelligence)`** でガードしています。

### (2026-07-02 追記) beta 2 で「iOS 専用」ではなくなった

この「iOS 専用」、**Xcode 27 beta 2 で `VisualIntelligence` が Mac にも import 可能になって、恒久的な制約ではなくなりました**。ガードを `canImport` にしておいたおかげで、フレームワークが存在するプラットフォームでは自動的にビルド対象へ入ります (プラットフォーム名を列挙する `#if os(...)` にしていたら、ここで書き直しになっていたところでした)。

ただし Mac には追加のバリデーションがあって、visual search の `IntentValueQuery` が返す entity は **すべて openable (対応する `OpenIntent` を持つ) である必要** があります。`TodoVisualIntelligenceQuery` は `TodoOrCategory` の union を返すので、`TodoAppEntity` (7/N の `OpenTodoIntent`) に加えて **`CategoryAppEntity` にも `OpenIntent` が必要** になり、`OpenCategoryIntent` を新設しました。カテゴリ専用の画面はまだ無いので perform はアプリを開くだけ、openable にすること自体が目的の Intent です (AppShortcuts には登録しないので 10 件枠にも響きません)。

おもしろいのはこのエラーの出方で、`OpenCategoryIntent` を外しても **iOS ビルドは普通に通り**、macOS 向けビルドでだけ appintentsmetadataprocessor が `result type 'CategoryAppEntity' that is not openable ... must be associated with an OpenIntent` で止まります (手元の beta 2 で両方確認しました)。「プラットフォーム限定」が当時の SDK の都合に過ぎないこともあれば、逆にプラットフォーム固有の要求が後から増えることもあるので、SDK 更新のたびに複数 destination でフルビルドして確かめるのが結局いちばん確実だなと思います。深さはビルド成立 (B) までで、Mac の visual search で実際に Todo が出てくるかは実機待ちです。

ちなみに「期限 → カレンダー」「担当者 → 連絡先」みたいな EventKit / Contacts 連携は、別フレームワークの話で App Intents 中心設計の検証主眼からは外れるので、今回は記録だけして未実装にしています。

## AppIntentsTesting で Intent を実経路テストする

WWDC 2026 編の締めとして、Intent を **実際の経路で動かすテスト** (セッション 295) を試しました。
これまで Intent のテストは「perform の中のロジックを純関数に切り出して SPM テストする」くらいしかできていなかったんですが、AppIntentsTesting を使うと **Siri / Shortcuts が通るのと同じ経路** で intent を実行して検証できます。

### UI テストバンドル必須 (unit test では動かない)

最初に大事な制約があります。
[Apple のドキュメント](https://developer.apple.com/documentation/AppIntentsTesting/testing-your-app-intents-code) が明記していて、AppIntentsTesting は intent を **ライブのアプリプロセスで実行** するので、テストは unit test ではなく **UI テスティングバンドル** に置く必要があります。
アプリプロセスと、登録済みの `AppDependencyManager` が要るからで、SPM の Testing パッケージでは動きません。IntentTodo は既存の `IntentTodoUITest` (UI テストターゲット) に追加しました。

```swift
import AppIntents
import AppIntentsTesting
import XCTest

final class AppIntentsTestingTests: XCTestCase {
    private var app: XCUIApplication!
    private var definitions: IntentDefinitions!

    @MainActor
    override func setUp() async throws {
        app = XCUIApplication()
        app.launch()   // ← ライブ起動
        // アプリが登録している intents / entities / enums / queries を発見する
        definitions = IntentDefinitions(bundleIdentifier: "dev.touyou.IntentTodo")
    }
}
```

### 型消去 API (文字列キー)

`IntentDefinitions(bundleIdentifier:)` がアプリの intents / entities / queries を発見してくれて、あとは **型名の文字列でキー** してアクセスします。

```swift
func testAddTodoIntentRunsAndPersists() async throws {
    let title = "AITest Add \(UUID().uuidString)"

    // 型名で intent を作り、@Parameter のラベルでパラメータを渡す
    let addIntent = definitions.intents["AddTodoIntent"].makeIntent(title: title)
    try await addIntent.run()   // 実経路で実行

    // 追加した Todo が entity query で見つかるはず
    let matches = try await definitions.entities["TodoAppEntity"].entities(matching: title)
    XCTAssertFalse(matches.isEmpty)

    // 型消去された entity から動的プロパティアクセスで値を取り出す
    let matchedTitle: String = try matches[0].title
    XCTAssertEqual(matchedTitle, title)
}
```

`makeIntent(<パラメータラベル>: 値)` → `run()` で実経路実行、`entities["..."].entities(matching:)` で entity query、`valueQueries["..."].values(for:)` で value query を叩けます。
戻り値は `AnyAppEntity` のような型消去型で、`try matches[0].title` のような **動的プロパティアクセス** で値を取り出します。

アプリターゲットを import せずに文字列で参照するスタイルなので、**多くの誤りはコンパイルではなく実行時に出ます**。型名のタイポやパラメータラベルの間違いがビルドを通ってしまうので、そこは気をつけるポイントでした。

### 自己クリーンアップ設計

このテストは実際の SwiftData を変更するので、流しっぱなしだとストアがゴミだらけになります。
なので、**一意のタイトルで作成 → 操作 → 削除** という自己クリーンアップ設計にしました。

```swift
func testAddThenShowChain() async throws {
    let title = "AITest Chain \(UUID().uuidString)"
    try await definitions.intents["AddTodoIntent"].makeIntent(title: title).run()
    try await definitions.intents["ShowTodosIntent"].makeIntent().run()  // Add → Show の連鎖
    try await deleteTodos(matching: title)  // 後始末
}
```

複数 Intent の連鎖 (Add → Show) も 1 テストの中で実経路で繋げられるので、「追加したものがちゃんと一覧に出る」みたいな結合的な確認ができるのは良かったです。

### 落とし穴: ファイルのターゲット所属

最後に 1 つ。
UI テストターゲットは synchronized folder ではないので、**ファイルを置くだけでは target に入りません** (ビルドは通るのに、そのファイルは無視される)。Xcode プロジェクトに登録して `project.pbxproj` に反映させる必要がありました。
あと `@MainActor override func setUp() async` にしないと、`XCUIApplication` の MainActor 隔離で Swift 6 のエラーになります。

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: `IntentValueQuery` / `SemanticContentDescriptor` / `semanticContentSearch` スキーマ適合 / AppIntentsTesting の記述は OK。
- **AppIntentsTesting**: buildForTesting + live diagnostics 0 件まで (型・登録レベル)。実際の run はシミュレータ起動と実 SwiftData 変更を伴うので、テスト自体は自己クリーンアップ設計にしたうえで、実行は手動 / CI に委ねています。
- **実機 (実際に visual search で Todo が候補に出るか)**: 未確認です。Visual Intelligence の visual search は端末での手動確認が要るので、できたら追記します。

## WWDC 2026 編をふりかえって

6〜10 で WWDC 2026 の App Intents 系要素をひととおり試してきました。
全体を通して感じたのは、**「名詞 (Entity) と動詞 (Intent) を丁寧に設計しておくと、新しいサーフェスへの適合がだいぶ安く済む」** ということでした。
`SyncableEntity` は id 設計が効いてタダで適合できたし (6/N)、Visual Intelligence は `OpenTodoIntent` と `@UnionValue` を再利用するだけで組めた (10/N)。逆に `RelevantEntities` みたいに「API 側に自分のドメインの口が無くて適合できない」ケースもあって (9/N)、全部が嬉しい話ではなかったですが、それも含めて「やってみないと分からない採用可否」を記録できたのは良かったと思っています。

この編は実機 (R) まで通せていないものが多いので、Siri / Visual Intelligence を実際に喋らせて確認できたぶんは、おいおい各記事に追記していく予定です。
残っている検証待ち・将来トピックは [99/N](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) にまとめてあります。

## まとめ

- `IntentValueQuery` はカメラ / スクショの visual search にアプリのコンテンツを返す入口。`AppEntity` と違い `@Dependency` が使え、`@UnionValue` で複数型を返せる
- `SemanticContentDescriptor` の `labels` は一般英語ラベル。`values(for:)` は nonisolated なので MainActor へホップして fetch する
- `@AppIntent(schema: .visualIntelligence.semanticContentSearch)` は entity プロパティを持たないので reminder スキーマの init 地雷を踏まない。`VisualIntelligence` は iOS 専用なので `#if canImport` でガード (2026-07-02 追記: beta 2 で Mac にも import 可能になりました。Mac は返す entity 全部に `OpenIntent` を要求してくるので、本文の追記を見てください)
- 結果タップ (`OpenTodoIntent`) / 複数結果型 (`@UnionValue`) は既存部品を再利用できた
- AppIntentsTesting は実経路で intent を動かせるが **UI テストバンドル必須**。型消去 API + 文字列キーなので誤りは実行時に出る。自己クリーンアップ設計にする
- WWDC 2026 編全体を通して、Entity / Intent を丁寧に設計しておくほど新サーフェスへの適合が安くなる、というのが一番の実感だった

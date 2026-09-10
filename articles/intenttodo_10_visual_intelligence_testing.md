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
WWDC 2026 編 (6〜10) の最後です (前提は 6/N 冒頭)。

最後は外向きのサーフェスとして Visual Intelligence 連携 (セッション 297) と、Intent を実際の経路で動かすテスト基盤 (AppIntentsTesting / セッション 295) を試した話です。

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
        let labels = input.labels
        guard !labels.isEmpty else { return [] }

        // TodoService は MainActor 隔離。ホップして snapshot を取り、
        // 以降は Sendable な entity 値で off-actor フィルタする。
        let todos = try await MainActor.run { try todoService.listTodos(filter: .all) }
        // ... labels を todo タイトル / カテゴリ名に localizedStandardContains で
        //     部分一致させて返す ...
        return matchedTodos + matchedCategories
    }
}
#endif
```

セッションを 2022 まで遡って洗い直したので、出自も補足しておきます。入口の `IntentValueQuery` と `SemanticContentDescriptor` は iOS 26 (WWDC 2025 セッション 275) からある API で、Visual Intelligence 連携そのものはその年に始まっていました。この記事が参照しているセッション 297 ([Best practices for integrating visual intelligence in your app](https://developer.apple.com/videos/play/wwdc2026/297/)) は WWDC 2026 で Visual Intelligence 統合を単独セッションとしてまとめ直した回で、下の追記に書いた **macOS 対応** がそこで増えた分にあたります。一方 AppIntentsTesting (セッション 295) の方は 2026 の新顔で間違いないです。

ここがおもしろかった点をいくつか。

- **`IntentValueQuery` は `@Dependency` が使えます**。6/N で「`AppEntity` は `@Dependency` 使えない」と書きましたが、value query の方は `_SupportsAppDependencies` に適合しているので、`TodoService` を直接注入できます。entity みたいに `TodoEntityStore` を迂回しなくていいので、ここは素直でした。
- 戻り値が **単一 Entity 型に縛られない** のが `EntityQuery` との違いです。9/N で作った `@UnionValue` の `[TodoOrCategory]` をそのまま返せるので、Todo とカテゴリの混在結果を出せます。
- `SemanticContentDescriptor` は `labels: [String]` と `pixelBuffer: CVReadOnlyPixelBuffer?` を持っています。`labels` は一般的な英語ラベル (建物の固有名みたいなのは来ない、`en_US`、同義語や翻訳なし) です。本アプリは labels を Todo タイトル / カテゴリ名に部分一致させました。`pixelBuffer` で画像一致もできますが、それは ML モデルが要るので今回は見送りました。なお最初はラベルが英語主体だからと `lowercased()` してから `contains` していたんですが、**突き合わせ先の Todo は日本語** なので例外にする理由がなく、他の検索経路と同じ `localizedStandardContains(_:)` に揃えました (6/N)。自前の小文字化も要らなくなります。
- **並行性**: `values(for:)` は nonisolated なので、MainActor の `TodoService` は `MainActor.run { ... }` でホップして取得して、その後は Sendable な `TodoAppEntity` 値で off-actor にフィルタする、という形にしています。
- 他の query と同じで **登録は不要** で、システムが自動発見します (AppShortcut も要りません)。
- 数の制限があって、**`SemanticContentDescriptor` を受ける `IntentValueQuery` はアプリに 1 つだけ** です (セッション 297 の 11:39)。IntentTodo は `TodoVisualIntelligenceQuery` の 1 つきりなので問題になっていませんが、あとから「Todo 用と Category 用で分けよう」と思い付いていたら通らなかったことになります。複数の型を返したいときは、次の項目の `@UnionValue` で戻り値の型を混ぜて 1 つの query に集約するのが正解でした。

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

7/N で reminder 本体スキーマに手こずったので身構えていたんですが、こっちは `@Parameter var semanticContent: SemanticContentDescriptor` を持つ形を要求してくるだけで、**entity プロパティを 1 つも要求しません**。
7/N のスキーマが重かったのは、要求プロパティの型がまた別のスキーマ entity で、**適合がサブグラフ全体に及ぶ** からでした。同じ「スキーマ適合」でも、entity プロパティを要求するかどうかで難易度が全然違う、というのが対比で見えたのは収穫です。

なお `VisualIntelligence` は **iOS 専用** のフレームワークです。このパッケージは macOS / watchOS / visionOS / Widget Extension でもビルドするので、Visual Intelligence 関連のファイルは丸ごと **`#if canImport(VisualIntelligence)`** でガードしています。

### beta 2 で「iOS 専用」ではなくなった

この「iOS 専用」、**Xcode 27 beta 2 で `VisualIntelligence` が Mac にも import 可能になって、恒久的な制約ではなくなりました**。ガードを `canImport` にしておいたおかげで、フレームワークが存在するプラットフォームでは自動的にビルド対象へ入ります (プラットフォーム名を列挙する `#if os(...)` にしていたら、ここで書き直しになっていたところでした)。

ただし Mac 対応にしたことで、1 つ見えていなかった要求が表に出てきました。visual search の `IntentValueQuery` が返す entity は **すべて openable (対応する `OpenIntent` を持つ) である必要** があります。`TodoVisualIntelligenceQuery` は `TodoOrCategory` の union を返すので、`TodoAppEntity` (7/N の `OpenTodoIntent`) に加えて **`CategoryAppEntity` にも `OpenIntent` が必要** になり、`OpenCategoryIntent` を新設しました。カテゴリ専用の画面はまだ無いので perform はアプリを開くだけ、openable にすること自体が目的の Intent です (AppShortcuts には登録しないので 10 件枠にも響きません)。

この要求、最初は「Mac 固有の追加バリデーション」だと思っていたんですが、そうではありませんでした。**ルール自体は全プラットフォーム共通** です。セッション 275 (9:19) が "This `OpenIntent` must exist, otherwise your app won't show up" と言っているとおりで、`OpenIntent` の無い entity はそもそも Visual Intelligence の結果に出てきません。Mac 固有なのは **macOS 向けのビルドだけがそれをコンパイル時エラーとして弾いてくる** という enforce のされ方の方でした。

なのでこのエラーの出方がおもしろくて、`OpenCategoryIntent` を外しても **iOS ビルドは普通に通り**、macOS 向けビルドでだけ appintentsmetadataprocessor が `result type 'CategoryAppEntity' that is not openable ... must be associated with an OpenIntent` で止まります (手元の beta 2 で両方確認しました)。iOS だけ見ていると、ビルドは通るのに実機で「なぜか候補に出てこない」という形でしか気付けないことになります。SDK 更新のたびに複数 destination でフルビルドして確かめるのが結局いちばん確実だなと思うのは、こういうところです。深さはビルド成立 (B) までで、Mac の visual search で実際に Todo が出てくるかは実機待ちです。

ちなみに「期限 → カレンダー」「担当者 → 連絡先」みたいな EventKit / Contacts 連携は、別フレームワークの話で App Intents 中心設計の検証主眼からは外れるので、今回は記録だけして未実装にしています。

### `canImport` だけだと visionOS の実機ビルドで落ちた

すぐ上で「ガードを `canImport` にしておいたおかげで」と自慢げに書いたんですが、その後 **visionOS の実機ビルドだけが落ちる** という形でしっぺ返しを食らいました。

`canImport(VisualIntelligence)` が見ているのは「そのフレームワークを import できるか」だけで、「その中の API がそのプラットフォームで available か」までは面倒を見てくれません。しかも `canImport` の結果は **同じ visionOS でもシミュレータ SDK と実機 SDK で違って**、こういうことになっていました。

- visionOS シミュレータ: `canImport(VisualIntelligence)` が false → コードごと除外されてビルド成功
- visionOS 実機 (Any visionOS Device) SDK: `canImport` が true になり、`.visualIntelligence.semanticContentSearch` スキーマ (visionOS 非対応) までコンパイルされて `'visualIntelligence' is unavailable in visionOS` で失敗

なので、非対応プラットフォームは明示的に外すしかありませんでした。

```swift
// import できるか、しか見ていない
#if canImport(VisualIntelligence)

// 非対応プラットフォームは明示的に外す
#if canImport(VisualIntelligence) && !os(visionOS)
```

教訓としては 3 つで、まず `canImport` はあくまで存在チェックなので、API の対応プラットフォームが限られている機能では `&& !os(...)` を併用すること。次に **シミュレータのビルドが通ったことを「その OS で通る」根拠にしない** こと (Xcode Cloud やアーカイブは実機 SDK でビルドするので、手元でも `Any <OS> Device` を回しておくのが確実でした)。最後に、今回みたいに Intent と Query が対になっている機能では **ガードを全ファイルで揃える** こと。片方だけ外すと相互参照が dangling して別のエラーになります。

本編 5/N で `CSSearchableIndex` と `IndexedEntity` の gate を揃える話を書きましたが、あれの「揃える相手が `#if os(...)` とは限らない」版だなと思いました。

## AppIntentsTesting で Intent を実経路テストする

WWDC 2026 編の締めとして、Intent を **実際の経路で動かすテスト** (セッション 295) を試しました。
これまで Intent のテストは「perform の中のロジックを純関数に切り出して SPM テストする」くらいしかできていなかったんですが、AppIntentsTesting を使うと **Siri / Shortcuts が通るのと同じ経路** で intent を実行して検証できます。

### UI テストバンドル必須 (unit test では動かない)

最初に大事な制約があります。
[Apple のドキュメント](https://developer.apple.com/documentation/AppIntentsTesting/testing-your-app-intents-code) が明記していて、AppIntentsTesting は intent を **ライブのアプリプロセスで実行** するので、テストは unit test ではなく **UI テスティングバンドル** に置く必要があります。
アプリプロセスと、登録済みの `AppDependencyManager` が要るからで、SPM の Testing パッケージでは動きません。IntentTodo は既存の `IntentTodoUITest` (UI テストターゲット) に追加しました。

もう 1 つ、セッション 295 (2:54) が明言している要件があって、**テストランナーとアプリ本体が同じ development team で code signing されている必要があります**。同一 Apple ID でしか触っていないので「自分には関係ない要件」だと思っていたんですが、後で別の形でまともに踏みました (後述)。ランナーとアプリの紐付けを署名で確かめている、という仕組みの方を覚えておくのが正解でした。

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

### 細かいところ

`@MainActor override func setUp() async` にしないと、`XCUIApplication` の MainActor 隔離で Swift 6 のエラーになります。

ファイルのターゲット所属については、この UI テストターゲットも synchronized folder になっていたので、ファイルを置くだけで入ります (テストを分割したときに普通に認識されました)。

### テストを広げて分かったこと

公開時点では 3 テストで、しかも `buildForTesting` + live diagnostics 0 件までしか見ていませんでした。その後 **23 テストまで広げて、実際に run してグリーンにする** ところまでやったので、そこで出てきたものをまとめておきます。

まず何を足したかというと、**「落ちても他のテストでは捕まらない」経路** を優先しました。

- `entities(identifiers:)` — Live Activity や Widget のボタンが `perform()` の前に必ず通る経路
- 未知の id を渡したときに throw しないこと
- `allEntities()` / `suggestedEntities()`
- `spotlightQuery()` — ここが落ちても「検索から消える」だけで、他は正常に見えてしまう
- `viewAnnotations()` / `exported(as: IntentPerson)` / `valueState` の三状態
- `CompleteTodosIntent` (`LongRunningIntent` + `EntityCollection` + `allowedExecutionTargets`) / `DeleteTodosIntent` / `SearchEverythingIntent` (`@UnionValue`)

9/N や 6/N で「ビルド成立 (B) まで」と書いていたものが、これでだいぶ単体 (U) に上がりました。

実際に run して引っかかったところも書いておきます。

- **dynamic member lookup で見えるのは `@Property` だけ**。`entity.id` は `NSNull` が返ってきます。id が欲しいときは `entity.identifier.instanceIdentifier` から取ります
- **`makeIntent(x: nil)` は `.set(nil)` ではなく `.unset`** になります。8/N で書いた「明示クリア」を出したいときは `String?.none as any IntentValueExpressing` のように型付きの nil を渡す必要がありました。これ、最初アプリ側のバグだと誤診しかけています
- **`requestChoice` を使う Intent は run できません**。5/N の話とも繋がるんですが、対話版と非対話版を分けておくとテスト可能性が上がる、という副次効果があります
- **`IntentValueQuery` はシミュレータでテスト不可**。`VisualIntelligence.framework` が iOS Simulator SDK に無いので、シミュレータビルドから丸ごと除外されるためです
- **Spotlight の index は Intent の完了と非同期** なので、ポーリングが要ります
- `setUp` で毎回 `app.launch()` すると、テスト数が増えたときにシミュレータの起動が散発的に失敗します。起動済みなら `activate()` に分岐させて解消しました
- クリーンビルド直後の最初のテストだけ "bundle is not present" で落ちます。`setUp` で軽いクエリが通るまで待つようにしました

### 画面が publish している entity も検証できる (ただし watchOS を除く)

`AppEntityDefinition.viewAnnotations()` を使うと、**いま画面が publish している onscreen entity** を検証できます。CosmoTunes は Now Playing / ライブラリの各セグメント / Canvas / タイマーカードと **画面ごとに** テストを持っていて、IntentTodo は詳細画面 (単一 annotation) と一覧 (コレクション annotation) の 2 本にしました。一覧側は「作った 2 件が両方 annotation に出る」を superset で見ています。他のテストが残した Todo が混ざりうるので、件数の完全一致で見ると不安定になるためです。

ただし **watchOS ではこの手が使えませんでした**。`AppIntentsTesting` は watchOS SDK にも存在していて、`IntentDefinitions` の発見も `suggestedEntities()` も `viewAnnotations()` もリンク・実行ともに通るんですが、**intent の `run()` が `LNPerformActionPrebuiltErrorCodeActionNotAllowed` (`LNPerformIntentPrebuiltErrorDomain` の code 4025) で落ちます**。テストの前提データを作る `AddTodoIntent` が走らないので、annotation を読むところまで到達できません。

watch アプリの UI から前提データを作る道もあるんですが、watchOS シミュレータの `typeText` が不安定なのは既存テストで経験済みで、そちらに寄せると「落ちても理由が分からないテスト」になります。5/N に書いた条件付き assert の反省もあるので、**watchOS 側は自動化を諦めて手動確認に回しました**。実装 (annotation 自体) は 4 プラットフォームのビルドで担保しています。

切り分けで地味に困ったのが、失敗の本当の理由 (上の 4025) が `xcodebuild` の標準出力には出てこなくて、`.xcresult` の Failure Message にしか無かったことでした。`xcrun xcresulttool get test-results tests --path <xcresult>` で読みます。**テストが落ちた理由を読む経路** 自体を知らないと、こういうのは「なんか watchOS だと落ちる」で終わってしまうなと思います。

ついでに、watchOS の一覧では `.appEntityIdentifier(forSelectionType:)` (コレクション版) も効きませんでした。CosmoTunes のコメントが *"The collection-form `.appEntityIdentifier(forSelectionType:)` is only honored when applied to a `List`"* と書いていて、watch の一覧も `List` ではあるんですが、**selection を持っていません** (行が `Button(intent:)` と `NavigationLink` なので)。`forSelectionType:` は selection 値の型を手がかりにする仕組みなので、当て先が無い、ということでした。「`List` なら効く」ではなく「**selection のある `List` なら効く**」と理解を訂正して、watch では行ごとの単一 annotation (`.appEntityIdentifier(EntityIdentifier(for: entity))`) に落としています。

### Apple が想定している検証の順番

もう 1 つ、AppIntentsTesting をどこまでやればいいのかの目安が見つかりました。セッション 240 (24:13〜25:57) が **progressive validation** として順番を明示していて、`AppIntentsTesting` → Shortcuts アプリ → Spotlight → Siri、と段階を上げていく形です。

大事なのが 1 段目の位置づけで、AppIntentsTesting は "entirely in isolation. No Siri involved." と言われています。セッション 295 (24:46) も "test your intents manually with Siri" と、**Siri は手動** だと明示していました。実際 AppIntentsTesting の公開 API を全文検索しても shortcut / phrase / siri / utterance に相当するシンボルは 0 件で、型名で intent を引く設計上フレーズ経路は通りません。

なので「App Shortcut のフレーズが Siri で正しくルーティングされるか」だけは、どうやっても手で確認するしかない領域ということになります。自動化できないのが自分の怠慢に思えていたんですが、**Apple の想定どおりの分担** だと分かってちょっと安心しました。この梯子は 3/N で書いた `AppIntentsPackage` の検証でもそのまま使っています。

## テストを増やしたら、テスト基盤の方が壊れていた

AppIntentsTesting の話とは別に、テストを増やしたり日本語を入れたりする過程で **テスト基盤そのものの壊れ方** をいくつか踏んだので、そっちもまとめておきます。どれも「赤くならない」形なのが共通点でした。

### テストが「落ちる」のではなく「存在しないことになる」

いちばん効いたのがこれです。`TodoAppEntity.dueDate` の型を変えたとき、SPM パッケージ側のユニットテスト 4 箇所がコンパイルできない状態のまま `main` にマージされていました。

原因は Xcode のスキームで、テストアクションに入っている `TestableReference` が **UI テストバンドル 1 つだけ** で、SPM パッケージのテストターゲットが 1 つも入っていなかったことでした。**137 テストが `xcodebuild test` からも CI からも走らない** 状態です。テストは「落ちる」のではなく「存在しないことになる」ので、赤くなりません。

スキームに 4 ターゲットを足したら、その瞬間に 11 件落ちました (後述)。「テストがある」と「テストが走っている」は別で、後者は明示的に確かめないと分からないんだなと思います。

追加のコストは +32.5 秒 / +11% でした。見立てでは「パッケージのユニットテストは 0.2 秒程度」と書いていたんですが、それは `swift test` の数字で、Xcode のテストアクション経由だと **バンドルごとのインストールと起動** が 1 本あたり 5 秒前後乗ります。実行そのものは 241 件で 1.08 秒、残りの 19 秒は全部オーバーヘッドでした。それでも 241 件が常時走る対価としては安いので、テストプランを分けたりはしていません。

### 並列実行は速くしていなかった

UI テストが 307 秒かかっていたので、`parallelizable = "YES"` を疑って測ったら、**外した方が速い** という結果でした。

| スイート | 並列 | 直列 |
|---|---|---|
| Intent 実行テスト (10 件) | 11.98 秒 | **2.00 秒** |
| システム統合テスト (5 件) | 17.42 秒 | **6.33 秒** |
| UI テスト (16 件) | 274.6 秒 | 256.7 秒 |

UI テストのクラスが 1 つしかないので、並列にしても **クラス内は分割されません**。シミュレータのクローン起動コストと取り合いだけが乗っていた、ということでした。ついでに「重いテストを並列で回してシミュレータがウォッチドッグで落ちる」という別の問題も消えています。

ちなみに「単体 114 秒かかる」と記録していた Spotlight のテストは、直列で測ったら **0.99 秒** でした。114 秒はクローンを取り合っていたときの数字だったわけで、**遅いテストだと思っていたものが遅かったのは環境の方** だった、という落ちです。timeout の見直しもテストプランの分離もやらずに済みました。

### 直列にしたら、隠れていた待ちの甘さが出た

固定の `sleep(1)` を `waitForNonExistence(timeout: 5)` に置き換えた直後、直列の通しで 1 件だけ落ちるようになりました。単体では通ります。

原因は **テスト間でストアが積み上がること** でした。共有ストア (App Group) はプロセスを跨いで残るので、通しで走らせると後半のテストは数十件の Todo を抱えた一覧の上で動きます。シートを閉じたあとの再描画が遅くなって 5 秒に収まらない。しかも `sleep(1)` の時代は「たまたま通っていた」のではなく、**シート閉じを待つ assert 自体が無かった** ので落ちようがなかっただけでした。

timeout を伸ばすのではなく原因を消す方を採って、`-uitest-ephemeral-store` を渡したときだけ in-memory コンテナを使う分岐 (DEBUG 限定) を入れました。これで空状態が保証されるので、5/N に書いた「条件付き assert」で誤魔化していたテストも無条件にできます。AppIntents 側のテストにはこの引数を渡していません。実運用と同じ共有ストアの上で entity 解決と Spotlight index を見たいからです。

### 日本語を入れたら、緑だったテストが 2 つの理由で落ちた

アプリに ja を入れた瞬間、UI テストが 2 件落ちました。ホストの macOS が `ja-JP` なのでシミュレータのアプリも ja で起動するようになり、英語ラベルで引いていた箇所が外れたためです。

```swift
app.navigationBars["Todos"]        // 実際は「やること」
app.buttons["Delete todo"]         // 実際は「やることを削除」
```

これ自体は素直な回帰なんですが、**落ちた 2 件より、落ちなかった 3 件の方が問題でした**。条件付き assert (`if element.waitForExistence(...) { XCTAssert... }`) で書かれていて、ラベルが引けないと中身が一度も実行されないまま緑になります。5/N に書いた壊れ方がそのまま再現した形です。

対処はテスト対象アプリの言語を `-AppleLanguages (en)` で固定することにしました。ラベル引きが 7 箇所あって、個別に直すより言語を固定する方が確実だったので。

同じ「ホスト言語が ja」の事故は、上のスキーム修正でユニットテストを入れた瞬間にも 11 件出ています。`String(localized: TodoFilter.all.displayName) == "All"` の形で書かれていて、コメントには「en では key がそのまま返る」とあったんですが、**シミュレータ上では ja で解決される** ので `"すべて"` が返ります。`swift test` では通るので、スキームに入れるまで表に出ませんでした。こちらは `resource.locale = Locale(identifier: "en")` でソース言語に固定しています。

**ローカライズを入れる作業は、テストの前提を静かに変えます**。しかも壊れ方が「落ちる」と「何も検証しなくなる」の 2 種類あって、後者は自分から探しに行かないと見つかりません。


### `CODE_SIGNING_ALLOWED=NO` を流用して、SDK の退行だと誤診した

この節の締めに、いちばん最近やらかしたやつを書いておきます。**「SDK が退行した」と 1 日書いていたら、壊れていたのは自分のコマンドラインでした。**

Xcode 27 が RC まで来たので SDK 側の制約を測り直していて、その途中の話です。SSU training のバグ (6/N) が直っているかを見るのに、こういうビルドを回していました。

```
xcodebuild -project IntentTodo.xcodeproj -scheme IntentTodo \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro Max,OS=27.0' \
  -derivedDataPath /tmp/ITRCProbeDD CODE_SIGNING_ALLOWED=NO build
```

`build` にこのフラグを付けるのは正しくて、署名なしでもメタデータ抽出も SSU training も走ります。**間違えたのは、そのままコマンドラインを使い回して `test` を走らせたこと** でした。

```
Error Domain=AppIntentsServicesSecurityErrorDomain Code=803
"Unable to run internal tests on a Customer build"
```

AppIntentsTesting の 23 件が全部これで死にます。文面が "Customer build" で、しかもちょうどシミュレータのランタイムがベータ版から出荷版に切り替わった直後だったので、自分は **「RC で AppIntentsTesting が退行した」と読みました**。

理屈はこうでした。`CODE_SIGNING_ALLOWED=NO` は **UI テストランナーの再署名ごと飛ばします**。すると `XCTRunner.app` テンプレートの素性がそのまま残ります。

| | 通常のビルド | `CODE_SIGNING_ALLOWED=NO` |
|---|---|---|
| ランナーの `Identifier` | `dev.touyou.IntentTodo.IntentTodoUITest.xctrunner` | **`com.apple.XCTRunner`** |
| ランナーの署名 | ad-hoc | **未署名** |

AppIntentsTesting はテスト対象アプリの App Intents をアプリのプロセス経由で叩くので、**「このランナーはそのアプリのテストランナーである」ことを署名で確かめています**。ランナーが `com.apple.XCTRunner` のままだと紐付けが成立せず、拒否されます。上で「自分には関係ない要件」と思っていた署名チームの話が、こういう形で返ってきた格好でした。

同じデバイス・同じテストで、フラグの有無だけを変えたら一発でした。

| ビルド | 結果 |
|---|---|
| フラグなし | **23 件 passed** |
| `CODE_SIGNING_ALLOWED=NO` | 全件 skip + 803 |

自分でも情けないのが切り分けのやり方で、並列実行・デバイスの残留状態・dyld キャッシュと順番に潰して「環境ノイズではない」ところまでは確認していました。ただ **どの行でも `CODE_SIGNING_ALLOWED=NO` は付けたまま** だったんです。変数を 1 つも動かしていないので、何回やっても同じ答えしか返ってきません。切り分け表を作ると「たくさん試した」感が出るんですが、**全行に同じ誤った定数が置いてあるなら切り分けになっていない** わけで、ここは表の見た目に自分で騙されていました。同時に出ていた別のクラッシュ (シミュレータでは `XPCPeerRequirement.hasEntitlement(_:)` が未実装で trap する、というやつ) を傍証として採用してしまったのも良くなかったです。署名ありで走らせると 23 件全部通るので、あれは 803 とは無関係でした。

発覚したのは、本人が Xcode から手で実行したログに **803 が 1 件も出ていなかった** からです。教訓は「SDK の退行だ」と結論する前に **自分のコマンドラインと IDE の差分を 1 つずつ潰す**、とくに **他のコマンドから流用したフラグは真っ先に疑う** の 2 つでした。

使い分けとしてはこうです。

| 用途 | `CODE_SIGNING_ALLOWED=NO` |
|---|---|
| `build` (SSU / メタデータの確認) | ✅ 付けてよい |
| `build-for-testing` / `test` / `test-without-building` | 🚫 AppIntentsTesting が 803 で全滅する |

### 誤診が 1 日生き延びたのは、skip が緑になるから

原因が自分側だったこととは別に、**この誤診を 1 日生かしてしまった仕組み** の方が問題でした。

テストの前段に「intent がまだ発見できないなら待つ」というヘルパーを置いていて、タイムアウトしたら `XCTSkip` を投げるようにしていたんです。結果こうなります。

```
Executed 1 test, with 1 test skipped and 0 failures (0 unexpected)
Test Suite 'IntentTodoUITest.xctest' passed
```

**23 件が 1 件も実行されていないのに `TEST SUCCEEDED`** です。「まあ環境依存だし」で流せてしまう見え方なので、原因を追う優先度が上がりませんでした。

直し方として最初に考えた「skip のラベルを分かりやすくする」は意味がありません。**XCTest の skip は名前を何にしても緑** なので、同じ失敗モードがそのまま再現します。なので skip をやめて、どちらも失敗にしました。「環境依存かどうか」は挙動ではなく **原因の分類** の方に使っています。

| エラー | 挙動 |
|---|---|
| `AppIntentsServicesSecurityErrorDomain` (803 など) | **待たずに即失敗**。待っても直らない設定ミスだし、23 件 × 30 秒を捨てることになる。メッセージに「`CODE_SIGNING_ALLOWED=NO` を付けていませんか」と対処まで書く |
| それ以外 (再インストール直後のメタデータ未反映など) | 従来どおり 30 秒ポーリング。タイムアウトしたら **skip ではなく失敗** |

ついでに、自前のエラー型を `LocalizedError` にも適合させました。XCTest は `localizedDescription` 経由でも投げられたエラーを出すので、これが無いと親切に書いたメッセージが「操作を完了できませんでした」に化けます。

変更後は、署名ありなら 23 件 passed のまま、フラグ付きなら 5.6 秒で `TEST EXECUTE FAILED` になります。38 秒待って緑になるより圧倒的にましです。

### 緑になる嘘テストは、増やしたぶんだけ増える

同じ「緑になるけど何も見ていない」形を、スクリプトで全テストに当てて洗い出しました。5 件出てきて、内訳が我ながらひどかったです。

- フォールバックの連鎖の末尾が「ボタンが 2 個より多い」で、**アプリが起動していれば常に true**。メニューが開かなくても緑
- watch の空状態テストが `if allDoneText.waitForExistence { … }` の中に本体まるごと入っていて、**要素が出なければ何も検証せず緑**
- watch の完了トグルのテストが「残っていたら分岐」の形で、**そもそも完了トグルを一度も叩いていなかった**
- 「セクションがある **or** 空状態」という assert。空ストアなら必ず後者で通る
- `if favoriteToggle.exists { tap }` のせいで、お気に入り付き追加のテストが **お気に入りを一度も検証していなかった**
- `#expect(x != nil)` が非 Optional 相手で常に true

直したあと、**わざと壊して落ちることまで確認しました**。メニューを開く `tap()` を外す、期待文字列を存在しないものに差し替える、チェックボックスの `tap()` を外す。3 つとも狙ったメッセージで落ちて、戻したら緑になりました。assert に歯が生えているかどうかは、**通ることでは分からなくて、落とせることでしか分からない** んだなと思います。

watch のテストが軒並み条件付きになっていたのには理由があって、**前提データを作る手段が無かった** からでした。watchOS シミュレータの `typeText` が信用できないので、追加シート経由で行を用意できません。フィクスチャが無いから「リストが出た」しか見られなくて、その結果が「トグルを叩かないまま緑」だったわけです。ここは DEBUG 限定の起動引数を 2 つ (in-memory ストア / Todo を 1 件 seed) 足して、iOS 側と同じ土俵に乗せました。テストの言語を `en` に固定するのも、iOS 側だけやって watch 側を忘れていた分です。

その過程で watch について 2 つ分かったことも書いておきます。

- **行のタイトルは `staticText` ではなく `button`** です (`NavigationLink` のラベルなので)。`app.staticTexts["Seeded Todo"]` は永遠に解決しません。`app.debugDescription` を吐かせて確定させました
- **完了させると行はリストから消えます**。watch の `@Query` が `!isCompleted` で絞っているためで、iOS のように `Mark as incomplete` へ変わるのを待っていると来ません。最初その形で書いて落として、**アプリの挙動が正しくてテストの期待が間違っている** という順番でした

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: `IntentValueQuery` / `SemanticContentDescriptor` / `semanticContentSearch` スキーマ適合 / AppIntentsTesting の記述は OK。
- **AppIntentsTesting**: 公開時点では buildForTesting + live diagnostics 0 件まで (型・登録レベル) でした。その後 23 テストまで広げて **実 run でグリーン** にしたので、entity query / valueState / バルク処理 / ValueRepresentation まわりは単体 (U) 深度に上がっています。スキームにパッケージのユニットテスト 4 ターゲットを入れたので、iPhone / iOS 27 の通しでは 302 件が走ります (Xcode 27 RC でも 23 件そのまま緑です)。
- **実機 (実際に visual search で Todo が候補に出るか)**: 未確認です。Visual Intelligence の visual search は端末での手動確認が要るので、できたら追記します。

## WWDC 2026 編をふりかえって

6〜10 で WWDC 2026 の App Intents 系要素をひととおり試してきました。
全体を通して感じたのは、**「名詞 (Entity) と動詞 (Intent) を丁寧に設計しておくと、新しいサーフェスへの適合がだいぶ安く済む」** ということでした。
`SyncableEntity` は id 設計が効いてタダで適合できたし (6/N)、Visual Intelligence は `OpenTodoIntent` と `@UnionValue` を再利用するだけで組めた (10/N)。逆に `RelevantEntities` みたいに「API 側に自分のドメインの口が無くて適合できない」ケースもあって (9/N)、全部が嬉しい話ではなかったですが、それも含めて「やってみないと分からない採用可否」を記録できたのは良かったと思っています。

この編は実機 (R) まで通せていないものが多いので、Siri / Visual Intelligence を実際に喋らせて確認できたぶんは、おいおい各記事に追記していく予定です。
残っている検証待ち・将来トピックは [99/N](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) にまとめてあります。

## まとめ

- `IntentValueQuery` はカメラ / スクショの visual search にアプリのコンテンツを返す入口。`AppEntity` と違い `@Dependency` が使え、`@UnionValue` で複数型を返せる。`SemanticContentDescriptor` を受ける query は **アプリに 1 つだけ** なので、複数型を返したいなら `@UnionValue` に寄せる
- `SemanticContentDescriptor` の `labels` は一般英語ラベル。`values(for:)` は nonisolated なので MainActor へホップして fetch する
- `@AppIntent(schema: .visualIntelligence.semanticContentSearch)` は entity プロパティを要求しないので、reminder スキーマのように適合がサブグラフ全体へ広がらない。`VisualIntelligence` のガードは `#if canImport(VisualIntelligence) && !os(visionOS)` (beta 2 で Mac にも import 可能になり、`canImport` だけだと visionOS 実機ビルドが落ちたため)
- visual search が返す entity は全部 openable でないといけない。ルールは全プラットフォーム共通で、**macOS ビルドだけがコンパイル時に弾いてくる**
- 結果タップ (`OpenTodoIntent`) / 複数結果型 (`@UnionValue`) は既存部品を再利用できた
- AppIntentsTesting は実経路で intent を動かせるが **UI テストバンドル必須**、かつテストランナーとアプリの署名チームを揃える必要がある。型消去 API + 文字列キーなので誤りは実行時に出る。自己クリーンアップ設計にする
- `entity.id` は `NSNull` で、id は `entity.identifier.instanceIdentifier` から取る。`makeIntent(x: nil)` は `.unset` になるので明示クリアは型付き nil で渡す。`requestChoice` を使う Intent は run できない
- `viewAnnotations()` で画面が publish している entity を検証できる。ただし **watchOS では `run()` が code 4025 で落ちて前提データを作れない** ので、そこは手動確認に回す。`forSelectionType:` も「`List` なら効く」ではなく「**selection のある `List` なら効く**」
- Apple が示す検証の順番は **AppIntentsTesting → Shortcuts → Spotlight → Siri**。フレーズのルーティングだけは手動確認の領域と割り切ってよい
- テスト基盤も壊れる。**スキームに入っていないテストは「落ちる」のではなく「存在しないことになる」**。並列実行は速いとは限らず、共有ストアはテスト間で積み上がる。ローカライズを入れるとテストの前提が静かに変わる
- **`xcodebuild test` に `CODE_SIGNING_ALLOWED=NO` を付けない**。ランナーの再署名ごと飛んで AppIntentsTesting が 803 で全滅する。`build` (SSU / メタデータの確認) に付けるのは正しいので、フラグの流用が事故になる
- **この層で `XCTSkip` を使わない**。skip は名前を何にしても `TEST SUCCEEDED` なので、23 件が 1 件も走らなくても緑に見える。待っても直らない設定ミスは待たずに失敗させる
- 直した assert に歯があるかは、**通ることではなく落とせることで確かめる**。わざと壊して、狙ったメッセージで落ちるところまで見る
- WWDC 2026 編全体を通して、Entity / Intent を丁寧に設計しておくほど新サーフェスへの適合が安くなる、というのが一番の実感だった

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-09-11**: Xcode 27 RC で測り直した分を反映。`CODE_SIGNING_ALLOWED=NO` を `test` に流用して「SDK が退行した」と誤診した経緯、`XCTSkip` をやめて失敗にした話、緑になる嘘テスト 5 件を潰してわざと壊して確かめた話、watch 側のフィクスチャで分かったことを追加。テスト件数を現状 (通し 302 件 / AppIntentsTesting 23 件) に更新
- **2026-08-31**: 「テストを増やしたら、テスト基盤の方が壊れていた」の節を追加 (スキームに SPM のテストターゲットが入っておらず 137 テストが走っていなかった / 並列実行が速くなかった / 共有ストアがテスト間で積み上がる / ホスト言語が ja だと英語ラベル引きと `String(localized:)` が外れる)。テスト件数を現状に更新
- **2026-08-28**: `viewAnnotations()` による画面ごとの検証と、watchOS では `run()` が code 4025 で落ちて自動化できない話を追加。`forSelectionType:` が効く条件を「selection のある `List`」に訂正。Visual Intelligence のラベル照合も `localizedStandardContains` に揃えたことを反映。更新履歴をまとめの後ろへ移動 (他の記事と順序を揃えた)
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: AppIntentsTesting を 22 テストまで広げて実 run でグリーンにした知見を追加 (型消去 API の落とし穴 / テスト不可な経路 / 検証の梯子)。「UI テストターゲットは synchronized folder ではない」という記述が誤りだったので訂正
- **2026-08-11**: openable 要件を「Mac 固有の追加バリデーション」と書いていたのを、ルールは全プラットフォーム共通で macOS ビルドだけがコンパイル時に enforce する、と訂正。`SemanticContentDescriptor` を受ける `IntentValueQuery` はアプリに 1 つだけという制約と、AppIntentsTesting の署名チーム要件を追加。セッション 297 の正式タイトルを訂正
- **2026-08-05**: `IntentValueQuery` / `SemanticContentDescriptor` の出自 (iOS 26 / セッション 275) を補足
- **2026-07-28**: `canImport` だけだと visionOS 実機ビルドが落ちる話を追加
- **2026-07-02**: beta 2 で `VisualIntelligence` が Mac にも import 可能になった話を追加

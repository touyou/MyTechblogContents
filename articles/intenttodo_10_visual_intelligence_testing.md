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

セッションを 2022 まで遡って洗い直したので、出自も補足しておきます。入口の `IntentValueQuery` と `SemanticContentDescriptor` は iOS 26 (WWDC 2025 セッション 275) からある API で、Visual Intelligence 連携そのものはその年に始まっていました。この記事が参照しているセッション 297 ([Best practices for integrating visual intelligence in your app](https://developer.apple.com/videos/play/wwdc2026/297/)) は WWDC 2026 で Visual Intelligence 統合を単独セッションとしてまとめ直した回で、下の追記に書いた **macOS 対応** がそこで増えた分にあたります。一方 AppIntentsTesting (セッション 295) の方は 2026 の新顔で間違いないです。

ここがおもしろかった点をいくつか。

- **`IntentValueQuery` は `@Dependency` が使えます**。6/N で「`AppEntity` は `@Dependency` 使えない」と書きましたが、value query の方は `_SupportsAppDependencies` に適合しているので、`TodoService` を直接注入できます。entity みたいに `TodoEntityStore` を迂回しなくていいので、ここは素直でした。
- 戻り値が **単一 Entity 型に縛られない** のが `EntityQuery` との違いです。9/N で作った `@UnionValue` の `[TodoOrCategory]` をそのまま返せるので、Todo とカテゴリの混在結果を出せます。
- `SemanticContentDescriptor` は `labels: [String]` と `pixelBuffer: CVReadOnlyPixelBuffer?` を持っています。`labels` は一般的な英語ラベル (建物の固有名みたいなのは来ない、`en_US`、同義語や翻訳なし) です。本アプリは labels を Todo タイトル / カテゴリ名に部分一致させました。`pixelBuffer` で画像一致もできますが、それは ML モデルが要るので今回は見送りました。
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

7/N で reminder 本体スキーマに苦しんだので身構えていたんですが、こっちのスキーマは `@Parameter var semanticContent: SemanticContentDescriptor` だけを持つ形を要求してくるだけで、**entity プロパティを持たない** ので、あの `EntityProperty` init 地雷を踏みませんでした。
同じ「スキーマ適合」でも、entity プロパティを要求するかどうかで難易度が全然違う、というのが対比で見えたのは収穫でした。

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

もう 1 つ、セッション 295 (2:54) が明言している要件があって、**テストランナーとアプリ本体が同じ development team で code signing されている必要があります**。自分は同一 Apple ID でしか触っていないので踏んでいないんですが、CI や複数アカウントを切り替える環境でここがずれると、原因の見当がつきにくい失敗になりそうです。テストを足すときは最初に署名チームを揃えておくのが良さそうだなと思っています。

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

### 22 テストまで広げて分かったこと

公開時点では 3 テストで、しかも `buildForTesting` + live diagnostics 0 件までしか見ていませんでした。その後 **22 テストまで広げて、実際に run してグリーンにする** ところまでやったので、そこで出てきたものをまとめておきます。

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

### Apple が想定している検証の順番

もう 1 つ、AppIntentsTesting をどこまでやればいいのかの目安が見つかりました。セッション 240 (24:13〜25:57) が **progressive validation** として順番を明示していて、`AppIntentsTesting` → Shortcuts アプリ → Spotlight → Siri、と段階を上げていく形です。

大事なのが 1 段目の位置づけで、AppIntentsTesting は "entirely in isolation. No Siri involved." と言われています。セッション 295 (24:46) も "test your intents manually with Siri" と、**Siri は手動** だと明示していました。実際 AppIntentsTesting の公開 API を全文検索しても shortcut / phrase / siri / utterance に相当するシンボルは 0 件で、型名で intent を引く設計上フレーズ経路は通りません。

なので「App Shortcut のフレーズが Siri で正しくルーティングされるか」だけは、どうやっても手で確認するしかない領域ということになります。自動化できないのが自分の怠慢に思えていたんですが、**Apple の想定どおりの分担** だと分かってちょっと安心しました。この梯子は 3/N で書いた `AppIntentsPackage` の検証でもそのまま使っています。

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: `IntentValueQuery` / `SemanticContentDescriptor` / `semanticContentSearch` スキーマ適合 / AppIntentsTesting の記述は OK。
- **AppIntentsTesting**: 公開時点では buildForTesting + live diagnostics 0 件まで (型・登録レベル) でした。その後 22 テストまで広げて **実 run でグリーン** にしたので、上に挙げた entity query / valueState / バルク処理 / ValueRepresentation まわりは単体 (U) 深度に上がっています。
- **実機 (実際に visual search で Todo が候補に出るか)**: 未確認です。Visual Intelligence の visual search は端末での手動確認が要るので、できたら追記します。

## WWDC 2026 編をふりかえって

6〜10 で WWDC 2026 の App Intents 系要素をひととおり試してきました。
全体を通して感じたのは、**「名詞 (Entity) と動詞 (Intent) を丁寧に設計しておくと、新しいサーフェスへの適合がだいぶ安く済む」** ということでした。
`SyncableEntity` は id 設計が効いてタダで適合できたし (6/N)、Visual Intelligence は `OpenTodoIntent` と `@UnionValue` を再利用するだけで組めた (10/N)。逆に `RelevantEntities` みたいに「API 側に自分のドメインの口が無くて適合できない」ケースもあって (9/N)、全部が嬉しい話ではなかったですが、それも含めて「やってみないと分からない採用可否」を記録できたのは良かったと思っています。

この編は実機 (R) まで通せていないものが多いので、Siri / Visual Intelligence を実際に喋らせて確認できたぶんは、おいおい各記事に追記していく予定です。
残っている検証待ち・将来トピックは [99/N](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) にまとめてあります。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: AppIntentsTesting を 22 テストまで広げて実 run でグリーンにした知見を追加 (型消去 API の落とし穴 / テスト不可な経路 / 検証の梯子)。「UI テストターゲットは synchronized folder ではない」という記述が誤りだったので訂正
- **2026-08-11**: openable 要件を「Mac 固有の追加バリデーション」と書いていたのを、ルールは全プラットフォーム共通で macOS ビルドだけがコンパイル時に enforce する、と訂正。`SemanticContentDescriptor` を受ける `IntentValueQuery` はアプリに 1 つだけという制約と、AppIntentsTesting の署名チーム要件を追加。セッション 297 の正式タイトルを訂正
- **2026-08-05**: `IntentValueQuery` / `SemanticContentDescriptor` の出自 (iOS 26 / セッション 275) を補足
- **2026-07-28**: `canImport` だけだと visionOS 実機ビルドが落ちる話を追加
- **2026-07-02**: beta 2 で `VisualIntelligence` が Mac にも import 可能になった話を追加

## まとめ

- `IntentValueQuery` はカメラ / スクショの visual search にアプリのコンテンツを返す入口。`AppEntity` と違い `@Dependency` が使え、`@UnionValue` で複数型を返せる。`SemanticContentDescriptor` を受ける query は **アプリに 1 つだけ** なので、複数型を返したいなら `@UnionValue` に寄せる
- `SemanticContentDescriptor` の `labels` は一般英語ラベル。`values(for:)` は nonisolated なので MainActor へホップして fetch する
- `@AppIntent(schema: .visualIntelligence.semanticContentSearch)` は entity プロパティを持たないので reminder スキーマの init 地雷を踏まない。`VisualIntelligence` のガードは `#if canImport(VisualIntelligence) && !os(visionOS)` (beta 2 で Mac にも import 可能になり、`canImport` だけだと visionOS 実機ビルドが落ちたため)
- visual search が返す entity は全部 openable でないといけない。ルールは全プラットフォーム共通で、**macOS ビルドだけがコンパイル時に弾いてくる**
- 結果タップ (`OpenTodoIntent`) / 複数結果型 (`@UnionValue`) は既存部品を再利用できた
- AppIntentsTesting は実経路で intent を動かせるが **UI テストバンドル必須**、かつテストランナーとアプリの署名チームを揃える必要がある。型消去 API + 文字列キーなので誤りは実行時に出る。自己クリーンアップ設計にする
- `entity.id` は `NSNull` で、id は `entity.identifier.instanceIdentifier` から取る。`makeIntent(x: nil)` は `.unset` になるので明示クリアは型付き nil で渡す。`requestChoice` を使う Intent は run できない
- Apple が示す検証の順番は **AppIntentsTesting → Shortcuts → Spotlight → Siri**。フレーズのルーティングだけは手動確認の領域と割り切ってよい
- WWDC 2026 編全体を通して、Entity / Intent を丁寧に設計しておくほど新サーフェスへの適合が安くなる、というのが一番の実感だった

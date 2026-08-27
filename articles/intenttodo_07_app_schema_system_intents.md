---
title: "WWDC 2026: App Schema と system intents — 意味で適合させる効きどころと「保留」の判断 (7/N)"
emoji: "🔗"
type: "tech"
topics: ["AppIntents", "Siri", "iOS", "WWDC2026"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 7 回目です。
WWDC 2026 編の 2 本目です (この編の前提は 6/N の冒頭を見てください)。

今回は、IntentTodo の Entity を **システムのドメインに意味で適合させる** 話 (App Schema) と、「開く」「削除する」を **system intent プロトコル** に乗せた話です。
そして、適合させようとして **途中で保留にした** 部分も正直に書きます。やってみて「ここは今は無理」と分かったのも 1 つの結論だと思っているので。

## ドメインに意味で適合させると何が起きるか

App Schema (assistant schema) は、自分の Entity や Intent を `reminders` や `mail` といった **Apple が定義済みのドメイン語彙** に適合させる仕組みです。
適合させると、Siri / Apple Intelligence が「これは reminders のリストなんだな」という具合に、コンテンツを **意味的に理解** してくれます。

IntentTodo は Todo アプリなので、いちばん近いのは `reminders` ドメインです。
カテゴリは reminders で言う「リスト」、Todo 本体は「リマインダー」に対応しそう、という見立てで適合を試しました。

## 小さいスキーマは素直: Category = reminders の list

まず素直に通ったのがカテゴリです。
6/N で `Category` を `AppEntity` 化した話を書きましたが、そのとき実は `@AppEntity(schema: .reminders.list)` で **reminders のリストスキーマに適合** させています。

```swift
@AppEntity(schema: .reminders.list)
public struct CategoryAppEntity: Hashable {
    public var id: String
    public var colorHex: String?     // スキーマ外の独自プロパティは足してもいい
    public var name: String          // スキーマが要求するプロパティ
    public var type: TodoListType    // スキーマが要求するプロパティ
    // ...
}
```

リストの「種別」も `@AppEnum(schema: .reminders.listType)` で適合させます。

```swift
@AppEnum(schema: .reminders.listType)
public enum TodoListType: String {
    case standard

    public static let caseDisplayRepresentations: [TodoListType: DisplayRepresentation] = [
        .standard: "Standard"
    ]
}
```

ここで気付いたことがいくつかありました。

- **`.reminders` ドメインは iOS 27+ 限定** でした。`'reminders' is only available in iOS 27.0 or newer` というエラーが出て、採用するには deployment を 27 世代へ上げる必要がありました (この引き上げごと `main` にマージしたので、今はアプリのベースラインが iOS 27 です)。
- スキーママクロが `typeDisplayRepresentation` を生成してくれるので、自分で書いていた分は **削除** しました。
- 6/N で書いたプロパティマクロのときと同じで、スキーママクロも非 `Hashable` な backing を生やすので、`Hashable` の自動合成が壊れます。`==` / `hash(into:)` を明示実装で補いました。

「スキーマが要求するプロパティ (name / type) を満たしつつ、独自プロパティ (colorHex) は足してもいい」という塩梅は、思っていたより柔らかくて好印象でした。

### beta 2 で watchOS がサポート対象から外れた

この list / listType 適合、**Xcode 27 beta 2 で watchOS が対象から外れました**。`TodoAppIntents` パッケージは watchOS でもビルドするので、beta 2 に上げたら `'reminders' is unavailable in watchOS` / `'list' is unavailable in watchOS` でいきなり落ちるようになって気付きました。

対処は `#if os(watchOS)` で素の `AppEntity` / `AppEnum` にフォールバックする、なんですが、ここに 1 つ落とし穴があります。`@AppEntity(schema:)` のような **マクロ付きの宣言は、属性部分だけを `#if` で切り替えられません** (属性と本体を分割すると `Expected '}' in struct` になります)。なので型宣言を watchOS 用とそれ以外用の 2 系統でまるごと書き分けることになりました。

```swift
#if os(watchOS)
public struct WatchCategoryAppEntity: AppEntity, Hashable {
    public static let typeDisplayRepresentation: TypeDisplayRepresentation = "List"
    @Property(title: "Name")            // ← フォールバック側にも明示が要る (後述)
    public var name: String
    // ... スキーマ無しの素の AppEntity として全プロパティを再宣言 ...
}

/// 呼出側は共通の名前で参照できるようにしておく
public typealias CategoryAppEntity = WatchCategoryAppEntity
#else
@AppEntity(schema: .reminders.list)
public struct CategoryAppEntity: Hashable {
    // ... 本文で書いた schema 適合版 ...
}
#endif
```

幸い watchOS では Siri / Apple Intelligence のスキーマルーティング自体を使っていないので、機能的には何も失っていません。これも iOS destination だけビルドしていると露見せず、watchOS を含むフルビルドで初めて出るやつでした (ガードを外して watchOS 向けにビルドし直し、上のエラーがそのまま再現することも確認済みです)。ベータの間はこういう「後から対象プラットフォームが狭まる」変更も来るんだな、というのは学びでした。

なおこの制約、**beta 3 でも beta 5 (27A5237l) でも継続** しています。SDK が上がるたびにガードを外してビルドし直していますが、そのたびに `'reminders' is unavailable in watchOS` が同じように出るので、フォールバックは当面必要なままです。後述の `.system` ドメイン側も同様でした。

### フォールバック側は型名も分ける

上のコードで watchOS 側だけ `WatchCategoryAppEntity` という別の型名になっているのには理由があって、これを最初に書いたとき (両方 `CategoryAppEntity` にしていたとき)、**iOS アプリの出荷メタデータから `.reminders.list` の適合がまるごと消えていました**。

同じ mangled type name にスキーマ付きの形とスキーマ無しの形が両方あると、アプリの統合メタデータへのマージで **情報が少ない方が勝ちます**。iOS アプリは watchOS アプリを `IntentTodo.app/Watch/` に埋め込むので、iOS の出荷メタデータに watchOS 用のスキーマ無しの形が持ち込まれて、そちらに倒れていた、ということでした。プロパティも 0 件になります。

型名を分ければ 2 つのエントリが共存してスキーマが残るので、`public typealias CategoryAppEntity = WatchCategoryAppEntity` で呼出側の名前だけ据え置きました。あわせて、フォールバック側にも `@Property(title:)` を明示しています。スキーマ版はマクロが `name` / `type` の `@Property` を生成してくれますが、素の `AppEntity` は自分で書かないと **プロパティ 0 件の entity** になります (渡せるけれど何も読めない、という状態です)。

この壊れ方、**コンパイラにもビルド緑にも一切現れません**。切り分けの経緯と検出方法は 3/N の「統合メタデータでは『情報が少ない方』が勝つ」に書きました。ここで言いたいのは、**フォールバックを書いたら、それが本来の形を食い潰していないかまで見る** ということかなと思っています。watchOS のためのつもりで書いたものが iOS の機能を消していた、というのは想像していませんでした。

## 大きいスキーマで詰まる: Todo 本体を reminder にできなかった話

ここからが、やってみて分かった「保留」の話です。
カテゴリが素直に適合できたので、当然 **Todo 本体を `@AppEntity(schema: .reminders.reminder)` に適合させたい** と思いました。ところがこれが結構な地雷原でした。

最初に手を出したときは、自前の `init(from: TodoItem)` で順番に代入しようとして `self.images used before being initialized` で弾かれ続けました。代入順を変えたり、デフォルト値を入れたり、他のマクロを外したり、と一通り試したんですが解消せず、「マクロが生成する init と自前 init が噛み合わないんだろう」と結論して保留にしていました。

これは **誤診でした**。あとから、適合そのものには着手せず **ビルド時のスキーマ検証にわざとエラーを吐かせて要求プロパティを全部洗い出す** という probe を書いたら、前提から違っていたことが分かります。

マクロ展開を読むと、生成されるのは `AssistantSchemaEntity` と `AppEntity` の conformance 2 つだけで、**init は生成されません**。自前の `init(from:)` はそのまま使えます。当時弾かれていたのは単に **要求プロパティを全部埋めていなかったから** でした。

要求プロパティは probe で確定しています。`title` / `note` / `dueDate` (`DateComponents?`) / `isCompleted` / `completionDate` / `creationDate` (optional 必須) / `isFlagged` (optional 必須) / `tags` (`Set<String>`) / `list` (**非** optional 必須) / `recurrence` (`Calendar.RecurrenceRule?`) / `locationTrigger` / `urls`。入れ子で `.reminders.locationTrigger` (`place: PlaceDescriptor` と `event`) と `.reminders.locationTriggerEvent` (arrive / depart) の 2 つが要ります。

そのうえで残った本当の障害が 3 つです。

1. **`list` が非 optional 必須**。こちらの `category` は 4/N に書いた CloudKit 要件で optional なので、そのままでは埋まりません
2. **`dueDate` が `DateComponents`**。モデルは `Date?` なので変換が要ります (これは 6/N の二重表現と同じ話なので、まあやれば済みます)
3. **`locationTrigger` が `PlaceDescriptor` を `@Property` に強制する**

この 3 つ目が効きました。6/N に書いた `AppIntentsSSUTraining` のバグ (`GeoToolbox.PlaceDescriptorEntity` がドット入りの variable 名になって正規表現に落ちるやつ) に、正面からぶつかります。DerivedData ごと消したクリーンビルドで probe を 2 つ回して確かめました。

- `@Parameter var placeProbe: PlaceDescriptor?` → `variables.3.name` でエラー
- `.reminders.locationTrigger` 適合 entity に `@Property var place: PlaceDescriptor` → `variables.1.name` でエラー

variable の index が probe に応じて 3 → 1 と変わるので、キャッシュではなく実際に走った結果です。**`@Parameter` だけでなく `@Property` (入れ子のスキーマ entity 側) でも踏みます**。6/N では `@Parameter` を `String` に退避して回避しましたが、reminder 本体スキーマは `locationTrigger` を必須で要求して、その entity が `place: PlaceDescriptor` を要求してくるので、退避のしようがありません。

というわけで **`.reminders.reminder` 適合は SDK の SSU バグが直るまで着手不可** と確定しました。据え置きという結論自体は最初から変わっていませんが、理由が「自分の init の書き方が悪い」から「SDK 側のバグでブロックされている」に変わったので、待つ先が変わります。手を動かせば直せるものだと思って寝かせていたのが、実は待つしかないものだった、というのは早めに分かってよかったです。

検証の手順で 1 つ注意があって、**probe を消した直後のビルドでもエラーが出続けます**。`Metadata.appintents` に probe の痕跡が残っているためで、SSU の temp-dir だけ消しても metadata の再抽出は走りませんし、ターゲットの build ディレクトリを部分的に消しても Xcode は「変更なし」と判断します。判定は DerivedData ごと消してやるのが確実でした。

なお、WWDC 2026 の App Intents Group Lab で「新しい Siri との連携はいずれかの App Schema 採用が前提」という話が出ていたので、本体適合が無いと詰むのかは一度気にしました。ただ実際には、カテゴリの list 適合 + discoverable な自前 Intent 群 + 後述の system intent だけでも意味理解・検索・遷移は成立しています。本体適合が無いと新しい Siri と何も連携できない、というわけではなさそうです。

小スキーマ (list) は素直、大スキーマ (reminder) は地雷、という温度差が分かっただけでも試した価値はあったかなと思っています。「やってみて、今のモデル設計と現行 SDK のままだと適合できないと分かった」というのは、ドキュメントを読んだだけでは出てこない情報なので、保留したこと自体を記録として残しておきます。

## system intents: OpenIntent / DeleteIntent

もう 1 つの「意味で適合させる」軸が system intent です。
App Intents には「開く」「削除する」みたいな共通アクション用に、**専用のプロトコル** が用意されています。プロトコル自体は前から存在するもので、セッション 344 (Code-along) で扱われているのは同じ系統のスキーマ版 (`@AppIntent(schema: .system.open)` や `DeleteEventIntent`) の方です。
これに適合すると、システムがそのアクションを意味的に理解してくれます (たとえば Spotlight の検索結果をタップ → 開く、という経路)。
おもしろいのは、スキーママクロ (`@AppIntent(schema: .system.open)` みたいなの) を使わず、**プロトコルに直接適合するだけ** でいいところです。

「開く」は `OpenIntent` に適合させました。

```swift
public struct OpenTodoIntent: OpenIntent {
    public static let supportedModes: IntentModes = [.foreground(.immediate)]

    @Parameter(title: "Todo", description: "The todo to open")
    public var target: TodoAppEntity   // OpenIntent は `target` プロパティを要求する

    @Dependency
    var navigationModel: NavigationModel

    @MainActor
    public func perform() async throws -> some IntentResult {
        navigationModel.navigateToRoot()
        navigationModel.showDetail(for: target)
        return .result()
    }
}
```

`OpenIntent` は `var target: Target` (`Target: AppEntity`) を要求し、関連型は `target` から推論されます。
ナビゲーションは `LaunchAppIntent` と同じ cold-start に強い `@Dependency` 経由の方式で `NavigationModel` に書いています。

「削除」は `DeleteIntent` に適合させたんですが、ここで設計判断が要りました。

```swift
public struct DeleteTodosIntent: DeleteIntent {
    public static var supportedModes: IntentModes { .background }

    @Parameter(title: "Todos", description: "The todos to delete")
    public var entities: [TodoAppEntity]   // DeleteIntent は entities の「配列」を要求する

    @Dependency
    var todoService: TodoService

    @MainActor
    public func perform() async throws -> some IntentResult {
        try await requestConfirmation(dialog: IntentDialog(deletionPrompt))
        for entity in entities {
            try todoService.delete(todoId: entity.id)
            try? await IntentDonationManager.shared.deleteDonations(
                matching: .entityIdentifiers([EntityIdentifier(for: entity)])
            )
        }
        return .result()
    }
}
```

`DeleteIntent` の契約は `var entities: [Entity]` で、**複数 entity の配列** を要求してきます。
IntentTodo にはもともと UI の `Button(intent:)` から 1 件ずつ消す `DeleteTodoIntent` (単数の `todo: TodoAppEntity`) があったんですが、これは配列型じゃないので `DeleteIntent` には適合できません。
なので **単体削除はそのまま残して、`DeleteTodosIntent` というバルク削除を別に新設** しました。
「UI 駆動の単体削除」と「システムが意味的に理解するバルク削除」は、要求するシグネチャが違うので無理に 1 つにしない、という判断です。

この 2 つの system intent はどちらも **AppShortcuts には登録していません**。
本編 5/N で書いたとおり AppShortcuts は 10 件上限なので枠を温存したいのと、system intent は AppShortcut が無くてもシステム側が意味解釈してくれるので、登録しなくても効くからです。

### 検索もシステムの語彙に乗せる: .system.searchInApp

「開く」「削除する」に続けて、**検索** もシステムの語彙に乗せました (セッション 343)。適合すると、Siri / Apple Intelligence が検索語をアプリ自身の検索 UI に流して、結果をアプリ側で見せられるようになります。`ShowInAppSearchResultsIntent` 自体は iOS 16 からある型で、スキーママクロで適合させる形が新しい部分のようです。

```swift
@AppIntent(schema: .system.searchInApp)
struct ShowTodoSearchResultsIntent: ShowInAppSearchResultsIntent {
    static let searchScopes: [StringSearchScope] = [.general]

    var criteria: StringSearchCriteria   // criteria.term が検索語

    @Dependency
    var navigationModel: NavigationModel

    @MainActor
    func perform() async throws -> some IntentResult {
        navigationModel.showSearch(matching: criteria.term)
        return .result()
    }
}
```

`title` や `supportedModes` はスキーマが供給してくれるので書きません。perform は `NavigationModel` に検索語を書き込んで、リスト画面がそれを `.searchable` の検索フィールドに転写する形にしました (cold-start に強い `@Dependency` ナビ方式は `OpenTodoIntent` と同じです)。

設計判断として 1 つ迷ったのが、9/N で書いた `SearchEverythingIntent` (`@UnionValue` の混在結果を **返す** 検索) との関係です。同じ「検索」でも、このスキーマの意味は "take the person to search results"、あくまで **アプリの検索 UI へ遷移させる** ことなので、統合せず別 Intent にしました。動詞の意味が違うなら無理に 1 つにしない、というのは `DeleteIntent` のときと同じ判断です。

なおこのスキーマも beta 2 で watchOS では unavailable になった (`'system' is unavailable in watchOS`) んですが、watch アプリにはそもそも遷移先になる検索 UI が無いので、こちらは list のようなフォールバックではなく `#if !os(watchOS)` で丸ごと除外しました。深さはここもビルド成立 (B) までで、Siri が実際に検索語を流してくれるかは実機待ちです。

1 つ、ベータ中に名前が変わった経緯も書いておきます。**最初に実装したときの SDK 上の名前は `.system.search` で、Xcode 27 beta 3 で `.system.searchInApp` にリネームされました** (`'search' is deprecated: Use .system.searchInApp instead` という警告が出るようになります)。上のコードはリネーム後の名前です。

```diff
- @AppIntent(schema: .system.search)
+ @AppIntent(schema: .system.searchInApp)
struct ShowTodoSearchResultsIntent: ShowInAppSearchResultsIntent {
```

ベータの間はこうやって途中で名前が変わることもあるんだな、というのを地で行く話でした。

## 集中モードに乗せる: SetFocusFilterIntent

system intent の仲間としてもう 1 つ、**集中モードごとに一覧の見せ方を変える** `SetFocusFilterIntent` も入れました。これは WWDC 2022 (セッション 10121) からある古株ですが、「システムが決めた場に自分の Intent を差し込む」という意味では `OpenIntent` / `DeleteIntent` と同じ系統です。設定 > 集中モード にアプリのフィルタとして現れて、Focus の切り替わりでシステムが `perform()` を呼んでくれます。

IntentTodo では「カテゴリ / 急ぎのみ / 完了を隠す」の 3 パラメータにしました。書いてみると、他の Intent と性格が違うところが 4 つあります。

**1 つ目は `allowedExecutionTargets` を宣言しないこと**です。2/N で「書き込み系はアプリ本体に固定」と書いたばかりですが、Focus filter の実行先は Focus の仕組みが決めます (アプリが動いていればアプリ、そうでなければ AppIntents Extension。セッション 10121 の 9:29)。こちらから固定しても意味がないし、将来 Extension を足したときに噛み合わなくなるので、ここにはあのルールを適用しませんでした。「全部に同じルールを当てる」が正しいとは限らない例です。

**2 つ目は、AppIntents Extension が無いとアプリ未起動中の遷移を取りこぼすこと**。埋め合わせは `SetFocusFilterIntent.current` (同 11:47) で、起動時とフォアグラウンド復帰時に現在値を取り直しています。Focus filter が未設定だと throw するので、その場合は「絞り込みなし」に倒します。

**3 つ目がいちばん怖くて、`notificationFilterPredicate` に一致しない通知は黙らされます** (同 13:15)。照合相手は `UNMutableNotificationContent.filterCriteria` なんですが、**criteria を付けていない通知は述語を返した瞬間に全部消えます**。5/N に書いたとおり、このアプリではコントロールの失敗通知が唯一の伝達手段なので、これが消えると「何も起きなかった」と区別できなくなります。なので失敗通知には専用の criteria を付けて、許可リストに常に含めるようにしました。

```swift
public var appContext: FocusFilterAppContext {
    guard let allowed = resolvedFilter.allowedNotificationCriteria else {
        return FocusFilterAppContext()          // 絞っていないときは述語を返さない
    }
    return FocusFilterAppContext(
        notificationFilterPredicate: NSPredicate(format: "SELF IN %@", allowed)
    )
}
```

**4 つ目は、絞り込みの判定を 1 か所に集約すること**。読み手がリスト UI (アプリプロセス) とウィジェット (別プロセス) の 2 つに分かれるので、ウィジェットには App Group の `UserDefaults` 経由で設定だけを渡して、「どの Todo を残すか」は共通の関数を通します。ウィジェットの件数表示も絞り込み後の母数で数えないと、「表示 0 件なのに未完了 5 件」みたいな嘘になります。

UI 側では **絞り込み中であることの表示と、その場での解除手段をセットで出す** ようにしました (標準のカレンダーが同じ形をしていて、セッションでも 2:04 でそう言っています)。表示だけだと、絞られていることに気付いたユーザーが設定アプリまで行くしかなくなるので。解除は永続化せず、次の Focus 遷移で畳みます。

`displayRepresentation` は設定済みの内容を動的に反映します (同 8:07)。ここも 6/N に書いたとおり、ランタイム文字列は `"\(value)"` の補間形式で渡します。

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: カテゴリの list 適合、`TodoListType` の listType 適合、`OpenIntent` / `DeleteIntent` 適合は OK。
- **reminder 本体スキーマ適合**: 上記のとおり保留 (型レベルで通せなかった、という結論)。
- **実機 (Siri / Spotlight でこれらが意味的にどう効くか)**: 未確認です。「Spotlight 結果タップ → OpenTodoIntent」みたいな経路は端末での手動確認が要るので、できたら追記します。

なので今回も「採用してみてどうだったか / どこで詰まったか」の設計判断の記録として読んでもらえればと思います。

## まとめ

- App Schema は自分の Entity / Intent を `reminders` 等のドメイン語彙に意味で適合させる仕組み。Siri / Apple Intelligence がコンテンツを意味理解できるようになる
- 小スキーマ (`Category` = `.reminders.list` / `TodoListType` = `.reminders.listType`) は素直に適合できた。`.reminders` は iOS 27+ 限定、`Hashable` は明示実装が必要
- 大スキーマ (`.reminders.reminder`) は **保留**。当初は「マクロ生成 init と自前 init が噛み合わない」と思っていたが、probe で洗い直したら本当の障害は `list` が非 optional 必須・`dueDate` が `DateComponents`・`locationTrigger` が `PlaceDescriptor` を強制して SSU バグに正面衝突、の 3 点だった。SDK 待ちで着手不可
- watchOS 用のフォールバックは **型名も分ける**。同じ型名だと統合メタデータでスキーマ無しの側が勝って、iOS の出荷メタデータから適合が消える
- system intent (`OpenIntent` / `DeleteIntent`) はプロトコル直適合でよい。`DeleteIntent` は `entities: [Entity]` の配列要求なので、UI 駆動の単体削除とは分けてバルク削除を新設した
- system intent は AppShortcuts 無しでも意味解釈されるので、10 件枠を温存できる
- `SetFocusFilterIntent` は「実行先を選べない Intent」。`notificationFilterPredicate` を返すと **criteria の無い通知が全部消える** ので、自分の失敗通知は許可リストに常置する

次回は、[Siri 応答を賢くする対話的な Intent (`requestConfirmation` / `requestChoice` / `IntentDialog(full:supporting:)`) と、Interactive Snippet、寄付 (`IntentDonationManager`) の話 (8/N)](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-28**: watchOS フォールバックの型名を分ける話 (同名だと iOS の出荷メタデータからスキーマが消える) を追加。`SetFocusFilterIntent` の節を追加。`.reminders` の iOS 27 要件が `main` のベースラインになったことを反映
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: reminder 本体スキーマの据え置き理由を probe の実測で全面的に書き換え。「マクロ生成 init が自前 init と衝突する」は誤りで、本当の障害は `list` の非 optional 要求・`dueDate` の型・`locationTrigger` 経由の SSU バグの 3 点。SDK 待ちで着手不可と確定
- **2026-08-11**: `.system.searchInApp` の出典を **343** に再訂正 (2026-08-05 に 343 → 344 と直したのが誤りだった)。`OpenIntent` / `DeleteIntent` の「(セッション 344)」という帰属も、344 で扱われているのはスキーマ版の方だと注記。watchOS の schema unavailable が beta 5 でも継続することを確認。reminder 本体スキーマ再挑戦のリード (セッション 344 の CometCal パターン) を追加
- **2026-08-05**: `.system.searchInApp` の出典を 343 → 344 に訂正 (この訂正自体が誤りだった)
- **2026-07-08**: beta 3 で `.system.search` が `.system.searchInApp` にリネームされたのを反映
- **2026-07-02**: `.system.searchInApp` 適合の節を追加。beta 2 で watchOS が対象から外れた話と、reminder 本体スキーマ保留の再評価を追加

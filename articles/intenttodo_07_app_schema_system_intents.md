---
title: "WWDC 2026: App Schema と system intents — 意味で適合させる効きどころ (7/N)"
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

今回は、IntentTodo の Entity を **システムのドメインに意味で適合させる** 話 (App Schema) と、「開く」「削除する」「検索する」を **system intent** に乗せた話です。

App Schema はしばらく「カテゴリだけ適合できて、Todo 本体は無理」という状態が続いていたんですが、据え置きの理由を測り直したら **塞いでいると思っていたものが塞いでいなかった** ことが分かって、本体も適合できました。代わりに出てきた本当の壁が watchOS だったので、そこも書きます。

## ドメインに意味で適合させると何が起きるか

App Schema (assistant schema) は、自分の Entity や Intent を `reminders` や `mail` といった **Apple が定義済みのドメイン語彙** に適合させる仕組みです。
適合させると、Siri / Apple Intelligence が「これは reminders のリストなんだな」という具合に、コンテンツを **意味的に理解** してくれます。

IntentTodo は Todo アプリなので、いちばん近いのは `reminders` ドメインです。
カテゴリは reminders で言う「リスト」、Todo 本体は「リマインダー」に対応します。

なお App Schema は **新しい Siri への入場券** であって、既存の経路を格下げするものではありません。適合が無くても、discoverable な自前 Intent 群と後述の system intent、それに Spotlight のセマンティックインデックスで、意味理解・検索・遷移は成立します。実際このアプリは長いこと `list` だけの適合で回っていましたし、スキーマを持てない watchOS でも機能は落ちていません。

## 小さいスキーマは素直: Category = reminders の list

まず素直に通ったのがカテゴリです。
6/N で `Category` を `AppEntity` 化した話を書きましたが、そのとき `@AppEntity(schema: .reminders.list)` で **reminders のリストスキーマに適合** させています。

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

気付いたことがいくつか。

- **`.reminders` ドメインは iOS 27+ 限定** でした。採用するには deployment を 27 世代へ上げる必要があって、この引き上げごと `main` にマージしたので、今はアプリのベースラインが iOS 27 です。
- スキーママクロが `typeDisplayRepresentation` を生成してくれるので、自分で書いていた分は **削除** しました。
- 6/N で書いたプロパティマクロのときと同じで、スキーママクロも非 `Hashable` な backing を生やすので、`Hashable` の自動合成が壊れます。`==` / `hash(into:)` を明示実装で補いました。
- listType には `standard` という **case の存在が要求されます** (`conforming to 'reminders.listType' requires enum case 'standard'`)。`.reminders.list` の `type` も非 optional 必須です。

「スキーマが要求するプロパティを満たしつつ、独自プロパティは足してもいい」という塩梅は、思っていたより柔らかくて好印象でした。

## 大きいスキーマ: Todo 本体を reminder に適合させる

`.reminders.reminder` 本体への適合は、長いこと「保留」でした。据え置きの理由は 2 回書き換わっていて、最初は「マクロ生成 init と自前 init が噛み合わない」、次に「`locationTrigger` が `PlaceDescriptor` を強制するので SSU training のバグに正面衝突する」。**どちらも誤診でした**。

決着したのは、6/N で書いた SSU バグの発火条件を切り分けたときです。バグが出るのは **App Shortcut に登録した Intent の `@Parameter`** だけで、entity の `@Property` は SSU の variable にならないので踏みません。最小プロジェクトでスキーマ入れ子まで全部適合させた probe を回したら、`locationTrigger.place: PlaceDescriptor` を持ったまま `nlu/` が生成されました。つまり **SDK は塞いでいなかった** わけです。

そこで据え置きの理由をゼロから測り直したところ、残っていたのは設計判断だけでした。

### 要求プロパティは 12。名前は `@ComputedProperty` で合わせられる

空の適合体を書いてビルドすると、要求プロパティが全部エラーとして列挙されます。`title` / `note` / `dueDate` / `isCompleted` / `completionDate` / `creationDate` / `isFlagged` / `tags` / `list` / `recurrence` / `locationTrigger` / `urls` の 12 個です。

このうち `note` / `creationDate` / `isFlagged` / `list` はスキーマが要求する **綴り** で、アプリ側の既存名 (`todoDescription` / `createdAt` / `isFavorite` / `category`) とは違います。ここは `@ComputedProperty` で別名を足すだけで満たせました。

```swift
@ComputedProperty(title: "Note")
public var note: String? { todoDescription }
```

**リネームは要りません**。「破壊的リネームが必要だから重い」という見積もりを立てていたら、それは丸ごと間違いだったことになります。

例外は `dueDate` 1 つだけで、スキーマは `DateComponents?` を要求するのに対してアプリは `Date?`、**名前が衝突する** ので computed alias で逃げられません。stored を `dueDateValue: Date?` に改名して `dueDate` を computed にしました。壊れたのは 5 ファイル 12 箇所で、全部 `dueDate` → `dueDateValue` の機械的置換です。

> 測り方でひとつ引っかかったのが、**パッケージ内でコンパイルが止まると下流の consumer が見えない** ことでした。「エラーが `TodoAppEntity.swift` だけ」の時点で「他に consumer は無い」と読みかけたんですが、自ファイルを直したら UI / WidgetUI 側が出てきます。**緑になるまで潰し切ってから件数を数える** のが正しいです。

### 足りないフィールドはモデルに足した

`completionDate` / `tags` / `urls` / `recurrence` / `locationTrigger` は、そもそもアプリが持っていない情報でした。ここは「computed で nil / 空を返してスキーマ登録だけ取る」か「モデルに足す」かの product 判断で、**モデルに足す** 方を選んでいます。スキーマに嘘を並べても意味理解の役に立たないので。

追加したフィールドは全部 CloudKit 互換の primitive です (4/N に書いた要件のとおり)。ここで SwiftData 側の地雷を 2 つ踏んだんですが、モデルの話なので詳細は [4/N](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) に書きました。要点だけ:

- **`Calendar.RecurrenceRule` は SwiftData の属性にできません**。コンパイルは通るのに、起動時の schema 初期化で trap します。frequency + interval の primitive で持って、entity の境界で rule に組み直しています
- **配列属性 (`tags` / `urls`) は `@Property` ではなく `@DeferredProperty`** にしました。削除済みオブジェクトの配列属性を読むと SwiftData が trap するためです。スキーマ要求は deferred でも満たせます

`list` は非 optional 必須なので、未分類の Todo には合成の `CategoryAppEntity.uncategorized` (固定 id) を見せています。実体のカテゴリを作るとカテゴリ一覧に現れて編集対象になってしまうので、合成にしました。

### 測定で見えていなかった制約: 親の適合は子の適合も要求する

ここが今回いちばんの発見でした。`TodoAppEntity` を適合させると、watchOS ビルドがこう落ちます。

```
error: Property 'list' type does not match required AppSchemaEntity property type 'ListEntity'
error: Property 'locationTrigger' type does not match required AppSchemaEntity property type 'LocationTriggerEntity'
```

**親のスキーマ適合は、子のスキーマ適合を要求します**。つまり「reminder スキーマに適合する」は `list` / `listType` / `locationTrigger` / `locationTriggerEvent` を含む **サブグラフ全体** を適合させるという意味でした。単体の probe ではサブエンティティも全部スキーマ付きで書いていたので、この要求に気付けていません。

そして watchOS では `CategoryAppEntity` がスキーマ無しのフォールバックになっているので、**親も適合できない**。ここから watchOS の話になります。

## watchOS では App Schema が使えない (ドメインを変えても無理)

これまで自分は「`reminders` ドメインの assistant schema は watchOS で unavailable」と書いてきました。嘘ではないんですが、読んだ人が「じゃあ別ドメインなら?」と考えてしまう書き方でした。

SDK の swiftinterface を全数走査したら、**23 ドメイン全部** が watchOS / tvOS で `unavailable` です。`audio` `books` `browser` `calendar` `camera` `clock` `files` `journal` `mail` `maps` `messages` `notes` `phone` `photos` `presentation` `reader` `reminders` `spreadsheet` `system` `whiteboard` `wordProcessor`、それに `assistant` (iOS 限定) と `visualIntelligence` (visionOS も除外)。**例外ゼロ** でした。

理由も裏が取れていて、Apple Intelligence Group Lab (35:34) が「新しい Siri は iPhone / iPad / Mac / visionOS で使える。HomePod では使えない」と言っています。App Schema は **その Siri に語彙を渡す仕組み** なので、Siri の提供範囲がそのまま availability になっている、という構造でした。`assistant` が iOS だけ・`visualIntelligence` が visionOS を外す、という細かい差まで一致するので、取りこぼしではなく意図的で一貫した線引きだと思います。

ちなみに `@AppEntity(schema:)` **マクロ自体** は watchOS SDK でも available です。ただ渡せるドメインが 1 つも無いので、この availability は実質空振りでした。

なので対処は「別ドメインを探す」でも「自前スキーマを作る」でもなく、**watchOS ではスキーマ無しの型を別に持つ** ことになります。マクロ付きの宣言は属性部分だけを `#if` で切り替えられない (属性と本体を分割すると `Expected '}' in struct` になる) ので、型宣言を 2 系統でまるごと書き分けます。

| 型 | 非 watchOS | watchOS |
|---|---|---|
| `TodoAppEntity` | `@AppEntity(schema: .reminders.reminder)` | `WatchTodoAppEntity` (スキーマ無し) |
| `CategoryAppEntity` | `@AppEntity(schema: .reminders.list)` | `WatchCategoryAppEntity` |
| `TodoListType` | `@AppEnum(schema: .reminders.listType)` | `WatchTodoListType` |
| `TodoLocationTriggerEvent` | `@AppEnum(schema: .reminders.locationTriggerEvent)` | `WatchTodoLocationTriggerEvent` |
| `TodoLocationTriggerAppEntity` | `@AppEntity(schema: .reminders.locationTrigger)` | 型ごと無し |

呼出側には `public typealias CategoryAppEntity = WatchCategoryAppEntity` のように共通の名前を見せているので、UI や Query は分岐を知りません。

### なぜ型名を分けるのか (`#if` で適合だけ切るのは駄目)

最初は素直に `#if !os(watchOS)` で適合だけ切りました。ビルドは緑で、`assistantDefinedSchemas` にも `reminders.ReminderEntity` が入っています。**それでも iOS の出荷メタデータからはスキーマが消えます**。

iOS アプリは watchOS アプリを `IntentTodo.app/Watch/` に埋め込むので、iOS アプリの統合メタデータには **watchOS スライスのメタデータが入力として渡ります**。そこで同じ型名のエントリが 2 つ並ぶと、後の入力が前を丸ごと置き換えます。この壊れ方はコンパイラにもビルド緑にも現れません。詳しい実測 (何がキーで、どちらが勝って、何が失われるか) は [3/N](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions) に書きました。

型名を分ければ 2 つのエントリが共存してスキーマが残るので、こちらを採っています。副産物として、**1 つのアプリの中で同じスキーマを主張する型が 1 つずつになりました**。`#if` で切っていた頃は `CategoryAppEntity` と `WatchCategoryAppEntity` が両方 `reminders.ListEntity` を主張していて、これは検査スクリプトが `all clear` を返すので気付けない類の歪みでした。

もう 1 つ、実装で踏んだ落とし穴があります。`Transferable` / `URLRepresentableEntity` の適合を `typealias` 経由の共有 extension に置いたら、**watchOS スライスだけ** でメタデータ抽出が落ちました。

```
error: The property 'transferRepresentation' must be static, have a compile-time constant value,
and cannot be computed or dynamic
```

これらの宣言は const 抽出 (swiftconstvalues) で読まれるので、`typealias` 越しでは具象型に結び付きません。**具象型名で書く** 必要がありました。最初は「同じファイルに置けば通る」と読み違えて 1 往復しています。このエラーは「iOS では通って watchOS だけ落ちる」形で出るので、`#if` でプラットフォームを分けた直後は **エラー行だけでなくどのスライスで出たか** を読むのが大事でした。

### 寄り道: 適合を手書きしようとして、やめた

途中で 1 つ寄り道をしていて、これは記録として残す価値があると思うので書いておきます。

マクロ `@AppEntity(schema:)` が生やすものは 2 つだけです。`AssistantSchemaEntity` 適合 + `__appSchemaEntity` という文字列と、メンバへの `@Property` 付与。そして **`AssistantSchemaEntity` プロトコル自体は watchOS でも available** で、unavailable なのは `.reminders.reminder` のような **スキーマ名前空間のシンボル** だけです。スキーマ識別子は結局ただの文字列なので、こう書けば watchOS でも適合できてしまいます。

```swift
extension WatchCategoryAppEntity: AssistantSchemaEntity {
    public static let __appSchemaEntity = "reminders.list"
}
```

実際これで通って、watch のメタデータにもスキーマが載りました。でも **採ってはいけない形** です。

- **プロトコル要求ですらありません**。`AssistantSchemaEntity` は実質空のプロトコルで、`__appSchemaEntity` はどこにも要求されていない。マクロが生やし、メタデータ抽出器が読むだけの **非公開の申し合わせ** です。名前が変われば **ビルド緑のままスキーマだけ静かに消えます**
- **公開 API での抜け道もありません**。ドメイン名前空間を経由せず `AppSchema.Entity("ListEntity")` を自分で組めれば済むんですが、その `init(_:)` は internal でした
- **内容としても誤り** で、スキーマという機能が存在しないプラットフォーム向けのメタデータに「この型は `reminders.ReminderEntity` です」と書いていることになります

そして踏んでいたコンパイルエラー (`Property 'list' type does not match…`) は「スキーマに反することをしている」ではなくて、**watchOS で宣言すべきでない適合を宣言したから検証が走っただけ** でした。正しい直し方は「検証を黙らせる」ではなく「watchOS では宣言しない」です。

このアプリで一番恐れている壊れ方が「ビルドは緑なのにメタデータだけ静かに壊れる」なので、それを自分で作り込む形になっていたのは危なかったなと思います。**アンダースコア始まりのシンボルが動いてしまったときこそ疑う**、というのが教訓でした。

### Apple には報告した

「App Schema が watchOS に無い」ことと「埋め込んだ watch アプリのメタデータが iOS アプリにマージされる」ことが組み合わさると、**共有 entity を持つアプリは型を二重定義しない限りどのスキーマにも適合できません**。しかも無言で壊れます。ここは Feedback (FB24570185) を出しました。

裏付けとして、WWDC 2026 の App Intents 系公式サンプル 4 本 (Calendar / Messaging / Music / Photo) は **どれも watch ターゲットを持っていません**。この組み合わせは公式サンプルで一度も踏まれていない、ということみたいです。ドキュメントにも複数ターゲットのメタデータマージについての記述はありませんでした。

## system intents: OpenIntent / DeleteIntent

もう 1 つの「意味で適合させる」軸が system intent です。
App Intents には「開く」「削除する」みたいな共通アクション用に **専用のプロトコル** が用意されていて、適合するとシステムがそのアクションを意味的に理解してくれます (たとえば Spotlight の検索結果をタップ → 開く、という経路)。
おもしろいのは、スキーママクロを使わず **プロトコルに直接適合するだけ** でいいところです。

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
        }
        return .result()
    }
}
```

`DeleteIntent` の契約は `var entities: [Entity]` で、**複数 entity の配列** を要求してきます。
IntentTodo にはもともと UI から 1 件ずつ消す `DeleteTodoIntent` (単数の `todo: TodoAppEntity`) があったんですが、配列型じゃないので適合できません。
なので **単体削除はそのまま残して、`DeleteTodosIntent` というバルク削除を別に新設** しました。
「UI 駆動の単体削除」と「システムが意味的に理解するバルク削除」は、要求するシグネチャが違うので無理に 1 つにしない、という判断です。

この 2 つの system intent はどちらも **AppShortcuts には登録していません**。
本編 5/N で書いたとおり AppShortcuts は 10 件上限なので枠を温存したいのと、system intent は AppShortcut が無くてもシステム側が意味解釈してくれるからです。

## 検索もシステムの語彙に乗せる: .system.searchInApp

「開く」「削除する」に続けて、**検索** もシステムの語彙に乗せました (セッション 343)。適合すると、Siri / Apple Intelligence が検索語をアプリ自身の検索 UI に流して、結果をアプリ側で見せられるようになります。`ShowInAppSearchResultsIntent` 自体は iOS 16 からある型で、スキーママクロで適合させる形が新しい部分です。

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

`title` や `supportedModes` はスキーマが供給してくれるので書きません。perform は `NavigationModel` に検索語を書き込んで、リスト画面がそれを `.searchable` の検索フィールドに転写する形にしました。

設計判断として迷ったのが、9/N で書いた `SearchEverythingIntent` (`@UnionValue` の混在結果を **返す** 検索) との関係です。同じ「検索」でも、このスキーマの意味は "take the person to search results"、あくまで **アプリの検索 UI へ遷移させる** ことなので、統合せず別 Intent にしました。動詞の意味が違うなら無理に 1 つにしない、というのは `DeleteIntent` のときと同じ判断です。

`.system` も 23 ドメインの 1 つなので watchOS では使えませんが、watch アプリにはそもそも遷移先になる検索 UI が無いので、こちらは型を分けるのではなく `#if !os(watchOS)` で丸ごと除外しています。

ちなみにこのスキーマ、SDK 上の名前が途中で `.system.search` から `.system.searchInApp` に変わりました。ベータの間はこういうリネームも来ます。

## 集中モードに乗せる: SetFocusFilterIntent

system intent の仲間としてもう 1 つ、**集中モードごとに一覧の見せ方を変える** `SetFocusFilterIntent` も入れました。これは WWDC 2022 (セッション 10121) からある古株ですが、「システムが決めた場に自分の Intent を差し込む」という意味では `OpenIntent` / `DeleteIntent` と同じ系統です。設定 > 集中モード にアプリのフィルタとして現れて、Focus の切り替わりでシステムが `perform()` を呼んでくれます。

IntentTodo では「カテゴリ / 急ぎのみ / 完了を隠す」の 3 パラメータにしました。書いてみると、他の Intent と性格が違うところが 4 つあります。

**1 つ目は `allowedExecutionTargets` を宣言しないこと** です。2/N で「書き込み系はアプリ本体に固定」と書いたばかりですが、Focus filter の実行先は Focus の仕組みが決めます (アプリが動いていればアプリ、そうでなければ AppIntents Extension。セッション 10121 の 9:29)。こちらから固定しても意味がないし、将来 Extension を足したときに噛み合わなくなるので、ここにはあのルールを適用しませんでした。「全部に同じルールを当てる」が正しいとは限らない例です。

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

## 検証できた深さ

- **ビルド成立 (B)**: `.reminders.reminder` / `.reminders.list` / `.reminders.listType` / `.reminders.locationTrigger` / `.reminders.locationTriggerEvent` の適合、`OpenIntent` / `DeleteIntent` / `.system.searchInApp`、`SetFocusFilterIntent` はすべて OK。iOS / macOS / visionOS / watchOS の 4 destination でクリーンビルド緑。
- **単体 (U)**: 出荷メタデータの検査で、各スキーマを主張する型が 1 つずつ登録されていることまで確認。AppIntentsTesting のスイートも全緑です。
- **実機 (R)**: 未確認。「スキーマ適合が実際に Siri / Apple Intelligence でどう効くか」は AppIntentsTesting が型名で intent を引く都合上そこを通らないので、手動確認の領域です (10/N)。

## まとめ

- App Schema は自分の Entity / Intent を `reminders` 等のドメイン語彙に意味で適合させる仕組み。**新しい Siri への入場券** であって、適合が無くても既存の意味理解・検索・遷移は成立する
- `.reminders.reminder` 本体適合は成立した。**据え置きの理由 2 つ (マクロ生成 init / SSU バグ) はどちらも誤診** で、SDK は塞いでいなかった
- 要求プロパティ 12 個のうち、名前違いは `@ComputedProperty` の別名で満たせる。**リネームは要らない**。型が衝突する `dueDate` だけ stored 名を変える
- **親のスキーマ適合は子のスキーマ適合も要求する**。適合はサブグラフ全体に及ぶ
- **App Schema の 23 ドメイン全部が watchOS / tvOS で unavailable**。新しい Siri の提供範囲がそのまま availability になっているので、ドメインを変えても自前スキーマにしても回避できない
- watchOS 用のフォールバックは **型名も分ける**。同じ型名だと統合メタデータで後勝ちのマージが起きて、iOS の出荷メタデータからエントリごと消える (→ 3/N)
- `__appSchemaEntity` の手書きは「動くけれど採ってはいけない」形。プロトコル要求ですらない非公開の申し合わせで、名前が変われば無言で壊れる
- system intent (`OpenIntent` / `DeleteIntent` / `.system.searchInApp`) はプロトコル直適合でよく、AppShortcuts 無しでも意味解釈される
- `SetFocusFilterIntent` は「実行先を選べない Intent」。`notificationFilterPredicate` を返すと **criteria の無い通知が全部消える** ので、自分の失敗通知は許可リストに常置する

次回は、[Siri 応答を賢くする対話的な Intent (`requestConfirmation` / `requestChoice` / `IntentDialog(full:supporting:)`) と、Interactive Snippet、寄付 (`IntentDonationManager`) の話 (8/N)](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-31**: `.reminders.reminder` 本体適合が成立したので「保留」の節を全面的に書き換え。据え置きの理由だった SSU バグは発火条件が違い、本体適合は踏まないことが判明。App Schema の制約を「reminders が watchOS で使えない」から「**23 ドメイン全部が watchOS / tvOS で unavailable**」に拡張 (理由は新しい Siri の提供範囲)。親の適合が子の適合を要求すること、`__appSchemaEntity` を手書きして撤去した経緯、`Transferable` を `typealias` 越しに書くと watchOS スライスで落ちること、Apple への報告 (FB24570185) を追加
- **2026-08-28**: watchOS フォールバックの型名を分ける話 (同名だと iOS の出荷メタデータからスキーマが消える) を追加。`SetFocusFilterIntent` の節を追加。`.reminders` の iOS 27 要件が `main` のベースラインになったことを反映
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: reminder 本体スキーマの据え置き理由を probe の実測で全面的に書き換え。「マクロ生成 init が自前 init と衝突する」は誤りと判明
- **2026-08-11**: `.system.searchInApp` の出典を **343** に再訂正 (2026-08-05 に 343 → 344 と直したのが誤りだった)。`OpenIntent` / `DeleteIntent` の「(セッション 344)」という帰属も、344 で扱われているのはスキーマ版の方だと注記
- **2026-08-05**: `.system.searchInApp` の出典を 343 → 344 に訂正 (この訂正自体が誤りだった)
- **2026-07-08**: beta 3 で `.system.search` が `.system.searchInApp` にリネームされたのを反映
- **2026-07-02**: `.system.searchInApp` 適合の節を追加。beta 2 で watchOS が対象から外れた話と、reminder 本体スキーマ保留の再評価を追加

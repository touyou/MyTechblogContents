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
WWDC 2026 編の 2 本目で、引き続き `xcode27` ブランチでの検証になります (この編の前提は 6/N の冒頭を見てください)。

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

- **`.reminders` ドメインは iOS 27+ 限定** でした。`'reminders' is only available in iOS 27.0 or newer` というエラーが出て、採用するには deployment を 27 世代へ上げる必要がありました (なのでこの検証は `xcode27` ブランチに隔離しています)。
- スキーママクロが `typeDisplayRepresentation` を生成してくれるので、自分で書いていた分は **削除** しました。
- 6/N で書いたプロパティマクロのときと同じで、スキーママクロも非 `Hashable` な backing を生やすので、`Hashable` の自動合成が壊れます。`==` / `hash(into:)` を明示実装で補いました。

「スキーマが要求するプロパティ (name / type) を満たしつつ、独自プロパティ (colorHex) は足してもいい」という塩梅は、思っていたより柔らかくて好印象でした。

## 大きいスキーマで詰まる: Todo 本体を reminder にできなかった話

ここからが、やってみて分かった「保留」の話です。
カテゴリが素直に適合できたので、当然 **Todo 本体を `@AppEntity(schema: .reminders.reminder)` に適合させたい** と思いました。ところがこれが結構な地雷原でした。

reminder 本体スキーマは、要求してくるプロパティがとにかく多いです。

- `dueDate: DateComponents?` (こっちが持っている `Date?` と型が衝突する)
- 非 optional の `list`
- 再帰的な `subtasks: [Self]`
- さらに `images` / `tags` / `urls` / `recurrence` / `section` / `locationTrigger` など

そして本丸が、**マクロが生成する init が `EntityProperty<T>` を引数に取る** ことでした。
`section` や `locationTrigger` のような **入れ子のサブエンティティを再帰的に要求** してくるので、自分が持っている「モデルから組み立てる `init(from:)`」(プロパティを順番に代入していくやつ) と、まるで噛み合いません。

具体的には、自前 init で順次代入しようとすると `self.images used before being initialized` で弾かれます。
代入順を変えたり、デフォルト値を入れたり、他のマクロを外したり、と一通り試したんですが解消しませんでした。
これは SDK 27 で `@State` がマクロ化されたときの初期化規約と同じ根っこの問題っぽくて、マクロ生成の初期化フローに自前の init を後付けで合わせるのが、そもそも構造的に難しいようでした。

そこで判断したのが、**Todo 本体の reminder スキーマ適合は保留する** ことでした。

- カテゴリ (list) で適合できているので、**App Schema の仕組み自体は検証できている**
- リッチな共有 Entity を reminder 本体スキーマに無理やり押し込むのは、得られるものに対してコストが見合わない
- ここは独立タスクとして切り出して、深掘りできるタイミングで再挑戦する

「やってみて、今のモデル設計のままだと適合できないと分かった」というのは、Apple のドキュメントを読んだだけでは出てこない情報だと思うので、保留したこと自体を記録として残しておきます。
小スキーマ (list) は素直、大スキーマ (reminder) は地雷、という温度差が分かっただけでも、試した価値はあったかなと思っています。

## system intents: OpenIntent / DeleteIntent

もう 1 つの「意味で適合させる」軸が system intent です。
App Intents には「開く」「削除する」みたいな共通アクション用に、**専用のプロトコル** が用意されています (#344)。
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

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: カテゴリの list 適合、`TodoListType` の listType 適合、`OpenIntent` / `DeleteIntent` 適合は OK。
- **reminder 本体スキーマ適合**: 上記のとおり保留 (型レベルで通せなかった、という結論)。
- **実機 (Siri / Spotlight でこれらが意味的にどう効くか)**: 未確認です。「Spotlight 結果タップ → OpenTodoIntent」みたいな経路は端末での手動確認が要るので、できたら追記します。

なので今回も「採用してみてどうだったか / どこで詰まったか」の設計判断の記録として読んでもらえればと思います。

## まとめ

- App Schema は自分の Entity / Intent を `reminders` 等のドメイン語彙に意味で適合させる仕組み。Siri / Apple Intelligence がコンテンツを意味理解できるようになる
- 小スキーマ (`Category` = `.reminders.list` / `TodoListType` = `.reminders.listType`) は素直に適合できた。`.reminders` は iOS 27+ 限定、`Hashable` は明示実装が必要
- 大スキーマ (`.reminders.reminder`) は `EntityProperty<T>` init + 再帰サブエンティティ要求で自前 init と噛み合わず、**保留** にした。適合させない判断も 1 つの結論
- system intent (`OpenIntent` / `DeleteIntent`) はプロトコル直適合でよい。`DeleteIntent` は `entities: [Entity]` の配列要求なので、UI 駆動の単体削除とは分けてバルク削除を新設した
- system intent は AppShortcuts 無しでも意味解釈されるので、10 件枠を温存できる

次回は、[Siri 応答を賢くする対話的な Intent (`requestConfirmation` / `requestChoice` / `IntentDialog(full:supporting:)`) と、Interactive Snippet、寄付 (`IntentDonationManager`) の話 (8/N)](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents) を書きます。

---
title: "WWDC 2026: 対話的な Intent — 確認 / 選択 / Snippet / 寄付 (8/N)"
emoji: "💬"
type: "tech"
topics: ["AppIntents", "Siri", "iOS", "WWDC2026"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 8 回目です。
WWDC 2026 編の 3 本目で、`xcode27` ブランチでの検証です (この編の前提は 6/N 冒頭を見てください)。

今回は、Intent を **対話的・予測的に賢くする** ための新 API をまとめて試した話です。
具体的には `requestConfirmation` / `requestChoice` で perform() を一旦止めてユーザーに聞く話、`IntentDialog(full:supporting:)` で返事を出し分ける話、Interactive Snippet でその場で操作させる話、`IntentDonationManager` で寄付する話の 4 本立てです。

## perform() を止めてユーザーに聞く

これまでの自分の Intent は、`perform()` が走り出したら最後まで一気に実行する、というものばかりでした。
WWDC 2026 (セッション 343) で、`perform()` の **途中でユーザーに確認や選択を求めて、答えを待ってから続きを実行する** API が整理されました。

### requestConfirmation で破壊的操作を確認する

削除みたいな取り返しのつかない操作は、いきなり実行せず一度確認したいです。
`requestConfirmation(dialog:)` を呼ぶと perform() がそこで止まって、Siri / Shortcuts 側に確認 UI が出ます。拒否されると **cancellation error が throw されて intent ごと中断** されるので、確認が通った場合だけ削除に進めます。

```swift
@MainActor
public func perform() async throws -> some IntentResult {
    // 破壊的操作なので一度確認する。拒否されると throw して中断する。
    try await requestConfirmation(
        dialog: IntentDialog("Delete “\(todo.title)”?")
    )
    try todoService.delete(todoId: todo.id)
    // ...
    return .result()
}
```

confirm が通らなければ throw で抜けるので、`if` で分岐する必要すらなくて、書き味はかなり素直でした。

### requestChoice で選択肢を出す

`requestConfirmation` が yes/no なら、`requestChoice` はその多分岐版です。
IntentTodo では「スヌーズする時間」を選ばせるのに使いました (30 分 / 1 時間 / 1 日)。

```swift
@MainActor
public func perform() async throws -> some IntentResult & ReturnsValue<TodoAppEntity> & ProvidesDialog {
    let choice = try await requestChoice(
        between: SnoozeDuration.choiceOptions,
        dialog: IntentDialog("Snooze “\(todo.title)” for how long?")
    )
    let duration = SnoozeDuration(matching: choice)

    let result = try todoService.snooze(todoId: todo.id, by: duration.interval)
    return .result(
        value: result.entity,
        dialog: IntentDialog("Snoozed “\(result.title)” by \(duration.spokenLabel).")
    )
}
```

ここで設計判断が要ったのが、**選んだ結果をどう逆引きするか** です。
`requestChoice` の返り値は選ばれた `IntentChoiceOption` ですが、`IntentChoiceOption` は `Equatable` ではあるものの **安定した識別子を持っていません**。なので「選ばれたオプション → どの時間か」を素直に引けません。

そこで、選択肢の生成と逆引きを `SnoozeDuration` という enum に **一元化** して、ローカライズ済みのタイトルで突き合わせる形にしました。

```swift
private enum SnoozeDuration: CaseIterable {
    case thirtyMinutes, oneHour, oneDay

    var interval: TimeInterval { /* 30*60, 60*60, 24*60*60 */ }
    var optionTitle: LocalizedStringResource { /* "30 minutes" など */ }

    /// プロンプトに出す選択肢 (表示順)
    static var choiceOptions: [IntentChoiceOption] {
        allCases.map { IntentChoiceOption(title: $0.optionTitle) }
    }

    /// 選ばれたオプションを時間に逆引きする。安定 id が無いのでタイトルで照合し、
    /// 万一リストがズレても 30 分にフォールバックする。
    init(matching choice: IntentChoiceOption) {
        self = Self.allCases.first { IntentChoiceOption(title: $0.optionTitle) == choice } ?? .thirtyMinutes
    }
}
```

これで「選択肢のリスト」と「逆引きの mapping」が同じ enum から生えるので、片方だけ直してもう片方を直し忘れる、というドリフトが起きません。
`IntentChoiceOption` に id が無いという地味な制約を、enum に寄せて吸収した、という感じです。

ちなみに `requestChoice` も `requestConfirmation` も **`.background` モードの intent から呼べます** (Siri / Shortcuts の UI に surface される)。
`SnoozeTodoIntent` (Primary) は UI の Button からは呼ばれず Siri / Shortcuts 専用なので、ここに対話を置くのが安全でした。Live Activity / Widget 用の `*FromExtensionIntent` 変種は、対話を求めず固定間隔のまま据え置いています。

## 返事を出し分ける: IntentDialog(full:supporting:)

`IntentDialog` には単一文字列の `init(_:)` だけじゃなく、**`init(full:supporting:)`** があります (セッション 343)。
これは「画面が無い文脈 (音声のみ) で読み上げる完結したメッセージ」と「返した値が視覚表示される文脈で添える短い一言」を **出し分ける** ためのものです。

`ShowTodosIntent` は `[TodoAppEntity]` の一覧を返すので、ここがちょうどハマりました。

```swift
private func dialog(for entities: [TodoAppEntity]) -> IntentDialog {
    let count = entities.count
    // ... categoryLabel を filter から組む ...

    if count == 0 {
        return IntentDialog(
            full: "You have no \(categoryLabel)s.",
            supporting: "No \(categoryLabel)s."
        )
    }
    let noun = count == 1 ? categoryLabel : "\(categoryLabel)s"
    return IntentDialog(
        full: "You have \(count) \(noun).",                                  // 音声単独: 件数を完全文で
        supporting: count == 1 ? "Here is your \(categoryLabel)." : "Here are your \(categoryLabel)s."  // 視覚併用: 一覧に添える一言
    )
}
```

音声だけのときは「You have 3 incomplete todos.」と件数まで言い切って、画面に一覧が出るときは「Here are your incomplete todos.」と短く添える。
同じ Intent でも、出力先 (耳か目か) で適切な饒舌さが違う、というのを 1 つの API で表現できるのは結構気が利いてるなと思いました。

## その場で操作させる: Interactive Snippet

Interactive Snippet は、Siri / Shortcuts の応答として **SwiftUI のミニ UI** を出して、その場で操作までさせる仕組みです。
IntentTodo では、`AddTodoIntent` で Todo を追加したあとに「追加した Todo をその場で完了 / お気に入りできるスニペット」を返すようにしました。

`AddTodoIntent` の戻り値で `snippetIntent:` を渡します。

```swift
return .result(
    value: entity,
    dialog: IntentDialog("Added \"\(entity.title)\"."),
    snippetIntent: TodoSnippetIntent(todoId: entity.id)
)
```

スニペット本体は `SnippetIntent` で、`perform()` が `some IntentResult & ShowsSnippetView` を返して `.result(view:)` で SwiftUI を提示します。

```swift
public struct TodoSnippetIntent: SnippetIntent {
    public static let isDiscoverable = false   // snippetIntent: 経由でのみ提示。Shortcuts には出さない

    @Parameter(title: "Todo ID")
    public var todoId: String

    @MainActor
    public func perform() async throws -> some IntentResult & ShowsSnippetView {
        let entity = Self.fetchEntity(forID: todoId)   // 毎回最新を取り直す
        return .result(view: TodoSnippetView(entity: entity))
    }
}
```

ここで大事なのが、**ボタンを押すたびにシステムが `SnippetIntent` を再実行する** ことです。
スニペット内のボタンは、ウィジェットと同じで `Button(intent:)` で App Intent を直接実行します。

```swift
Button(intent: ToggleTodoCompletionIntent(todo: entity)) {
    Label(entity.isCompleted ? "Mark Incomplete" : "Mark Complete", systemImage: ...)
}
```

ボタンが走ると、システムがスニペットを再 perform するので、`perform()` の中で **毎回 entity を取り直して** いれば、ラベルが「Mark Complete」⇄「Mark Incomplete」と正しく切り替わります。
だから `TodoSnippetIntent.perform()` は `todoId` から `TodoEntityStore` 経由で最新を再フェッチする作りにしています (6/N で出てきた共有コンテナのアクセサです)。

なお、このスニペットは **app プロセスで提示される** ので、本編 5/N で書いた「Live Activity Extension での entity 解決クラッシュ」は該当しません。なのでここでは Primary な entity ベースの Intent を素直に使っていて、`FromExtension` 変種は新しく足していません (FromExtension はあくまで LA / Widget 専用のワークアラウンドなので、増やさない方針です)。

## 予測のために寄付する: IntentDonationManager

最後が寄付です。
アクションを `IntentDonationManager` に寄付しておくと、システムが「この人はこの時間帯によく Todo を追加するな」みたいに学習して、先回りで提案してくれるようになります。

追加のときは、`AddTodoIntent` の perform() で寄付します。失敗しても致命的じゃないので `try?` で握りつぶしています。

```swift
// Donate the action so the system can predict / proactively suggest it.
try? await donate()
```

逆に削除のときは、**寄付を消し** ます。
消した Todo を参照する寄付が残っていると、システムが「もう存在しない Todo に対するアクション」を提案してしまうので、それを防ぐためです。

```swift
try? await IntentDonationManager.shared.deleteDonations(
    matching: .entityIdentifiers([EntityIdentifier(for: todo)])
)
```

「追加で寄付、削除で寄付を消す」をペアで持っておくと、提案が実体とズレにくくなる、というのが設計上の肝でした。
寄付しっぱなしだと、消したはずの Todo がいつまでも提案に出てくる、みたいな気持ち悪さが残るので、削除側の後始末まで含めて 1 セットだと思っています。

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: `requestConfirmation` / `requestChoice` / `IntentDialog(full:supporting:)` / `SnippetIntent` / `IntentDonationManager` はすべて OK。
- **実機 (Siri が実際に確認 UI / 選択 UI を出すか、スニペットが応答に出るか、寄付で提案が変わるか)**: 未確認です。このへんは Siri を実際に喋らせて確認する必要があるので、端末で触れたら追記します。

特に寄付の効果 (提案が賢くなるか) は、しばらく使い込まないと体感できない種類のものなので、ここは長めに寝かせてから書くことになりそうです。

## まとめ

- `requestConfirmation` (yes/no) / `requestChoice` (多分岐) は perform() を止めてユーザーに聞ける。拒否 / `.cancel` は throw で中断される
- `requestChoice` の `IntentChoiceOption` は安定 id を持たないので、選択肢生成と逆引きを enum に一元化してタイトル照合 + フォールバックでドリフトを防ぐ
- `IntentDialog(full:supporting:)` で「音声単独」と「視覚併用」のメッセージを出し分ける
- Interactive Snippet はボタンを押すたびにシステムが `SnippetIntent` を再 perform するので、perform で毎回最新 entity を取り直す。app プロセス提示なので entity 解決クラッシュは無関係
- `IntentDonationManager` は「追加で `donate()`、削除で `deleteDonations(...)`」をペアにして、提案が実体とズレないようにする

次回は、[大量の Todo を一括処理する `EntityCollection` / `LongRunningIntent` / `CancellableIntent` と、「検証してみたら自分のアプリには適合しなかった」`RelevantEntities` の話 (9/N)](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis) を書きます。

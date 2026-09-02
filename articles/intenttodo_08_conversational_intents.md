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
WWDC 2026 編の 3 本目です (この編の前提は 6/N 冒頭を見てください)。

今回は、Intent を **対話的・予測的に賢くする** ための新 API をまとめて試した話です。
具体的には `requestConfirmation` / `requestChoice` で perform() を一旦止めてユーザーに聞く話、`IntentDialog(full:supporting:)` で返事を出し分ける話、Interactive Snippet でその場で操作させる話、そして `IntentDonationManager` で寄付する話 (結論としては「しない」) の 4 本立てです。

## perform() を止めてユーザーに聞く

これまでの自分の Intent は、`perform()` が走り出したら最後まで一気に実行する、というものばかりでした。
`perform()` の **途中でユーザーに確認や選択を求めて、答えを待ってから続きを実行する** API は、iOS 26 から iOS 27 にかけて一通り揃っています (セッション 275 / 343)。

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

#### 呼出元に確認を出す面が無いと失敗する

書き味は素直なんですが、**どこから呼ばれるか** を考えずに置くと事故ります。この `DeleteTodoIntent` をアプリ内の `Button(intent:)` にも繋いでいたら、押しても Todo が消えませんでした。コンソールにはこれが出ます。

```
DeleteTodoIntent failed to execute with error:
LNPerformActionErrorCodeUnsupportedValueType
```

アプリ内の `Button(intent:)` には **確認を提示する面がありません**。なので `requestConfirmation` を要求した時点で失敗して、その先の削除まで到達しない、ということでした。5/N に書いた「Control では dialog も snippet も出ない」と同じ系統の話で、**対話 API は呼出元がその対話を提示できるかに依存する** わけです。

しかも Siri / Shortcuts / AppIntentsTesting 経由では成功するので、テストは通ります。壊れていたのは UI の削除経路だけでした。対処は確認なし版の Intent を分けて、UI 側は SwiftUI の `.confirmationDialog` で確認してからそちらを呼ぶ形にしています。詳しい経緯は [5/N の落とし穴 4](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls) に書きました。

これは `requestConfirmation` に限らず、次に書く **`requestChoice` でも同じ** です。対話を求める API を `perform()` に置くなら、その Intent を UI の `Button(intent:)` から呼ばない、という線引きが要ります。

ついでに、10/N に書いた AppIntentsTesting の話とも繋がります。**`requestChoice` を使う Intent はテストから run できません**。対話版と非対話版を分けておくと、この制約を回避できてテスト可能性が上がる、という副次効果がありました。呼出元ごとに分けるのは対話のためだったんですが、結果的にテストのためにもなっていた形です。

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
`SnoozeTodoIntent` は UI の Button からは呼ばれず Siri / Shortcuts 専用なので、ここに対話を置くのが安全でした。Live Activity のボタン用には、対話を求めず既定 30 分で即実行する `QuickSnoozeTodoIntent` を別に用意しています。

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

なお、このスニペットは **app プロセスで提示される** ので、本編 5/N で書いた entity 解決クラッシュは該当しません。ここでは entity ベースの Intent を素直に使っています (そのクラッシュ自体、後日 iOS 27 では再現しないと分かって回避策ごと撤去しました)。

## 寄付はしない — ただし理由は途中で入れ替わった

最後が寄付です。アクションを `IntentDonationManager` に寄付しておくと、システムが「この人はこの時間帯によく Todo を追加するな」みたいに学習して、先回りで提案してくれるようになります。

結論から書くと、**IntentTodo の明示的な寄付はゼロ** です。ただしその理由は 2 段階で入れ替わっていて、後の方が本題なので順に書きます。

### 第 1 段階: `perform()` の中で donate するのは規約違反だった

自分は `AddTodoIntent` の `perform()` の中で `try? await donate()` を呼ぶ形で入れていました。これは間違いです。公式ドキュメント (Donations and discovery) がこう書いています。

> Restrict your donations to direct interactions with your app's interface, and **not to interactions started by Siri or the Shortcuts app**.

CosmoTunes の `DonationManager` にも同じことがコメントで書いてあります (*"Avoid issuing donations from inside an intent's `perform()`, because the framework already donates intents invoked through Siri or Shortcuts."*)。システムは自分が走らせた Intent をすでに寄付しているので、二重計上になる、ということでした。

そして **`perform()` は呼出元を判別できません**。`IntentSystemContext` が持っているのは `currentMode` と `isVoiceOnly` だけで、invocation source を知る API はありません。つまり `perform()` 内の寄付は必ず Siri / Shortcuts 経由でも走るので、分岐しようがない。撤去しました。

### 第 2 段階: `Button(intent:)` の実行は、そもそもシステムが寄付していた

じゃあ寄付する層はどこかというと「呼出元を知っている層」= UI です。ところが IntentTodo は 1/N に書いたとおり **UI も `Button(intent:)` で同じ Intent を走らせる** ので、サービス層に届いた時点で常に Intent 経由だし、`Button(intent:)` はタップのコールバックも渡してくれません。差す隙が無い。

ここで「App Intents 中心設計の趣旨なら `callAsFunction(donate:)` に切り替えるべきでは。あるいは `Button(intent:)` の内部で donate されている可能性は?」という問いが出てきて、**後者でした**。

観測には公開 API がありません (`deleteDonations` はあるのに列挙が無い) ので、シミュレータのデータコンテナにある Biome ストリームを直接読みました。スナップショットを取って、操作を 1 つだけして、差分を見る、という形です。

| 呼出元 | Donation | Intent 実行ログ |
|---|---|---|
| 何もしない (negative control) | +0 | +0 |
| アプリ内 `Button(intent: AddTodoIntent)` ×1 | **+1** | +1 |
| アプリ内 `Button(intent: ToggleTodoCompletionIntent)` ×3 | **+3** | +3 |
| Spotlight の App Shortcut から (positive control) | **+2** | +2 |

アプリは `donate()` をどこからも呼んでいないのに記録されています。つまり **アプリ内 `Button(intent:)` の実行は、システムが donation として記録している**。

これで結論の理由が入れ替わりました。「規約違反になるから寄付しない」ではなく、**アプリ内 UI が全部 `Button(intent:)` である限り、寄付すべき「Intent を通らない UI 操作」が存在しないから** です。公式サンプル 4 本が明示 donate を必要とするのは、UI が Manager を直接呼んでいるからで (`Button(` 94 件のうち `Button(intent:)` は **0 件** でした)、前提が違います。セッション 343 の "Apple Intelligence can't learn from actions people take through your app's UI without your help" も、**UI の操作が intent の実行になっていない** アプリの話だと読むのが自然でした。

設計の核 (Intent を唯一の実行経路とする) を寄付のために崩す必要は無かった、というのが今の理解です。むしろ核を守っていたから寄付が要らなかった、という順序でした。

### 測り方を 2 回間違えた

この結論に至る前に、**逆の判断を 2 回書いています**。どちらも読み方の問題で、覚えておく価値があるので残しておきます。

1. **`mtime` を信じた**。ストリームのセグメントは mtime が 1 か月以上前なのに、中身は当日まで入っています (mmap 書き込みで mtime が更新されない)。→ **中身の時刻を見る**
2. **`+0` を「書かれていない」と読んだ**。donation は派生ストリームなので **生成が遅れます**。実測で 4 分後は未反映、80 分後は反映済みでした。→ **`+0` を見たら待つ**。intent が走ったかどうかは即時反映される別のストリームで見る

5/N に書いた「まず既知の良い面 (positive control) で動かしてから疑わしい面に持っていく」は今回もやったんですが、**「待つ」が抜けていると positive control 自体が偽陰性になる** ので、そこだけでは足りませんでした。

なおこの観測パスは非公開で、OS 更新で消えます。**検証専用** であって、出荷コードから依存してよいものではありません。

### 消す側は呼出元に関係なく正しい

一方で **`deleteDonations(matching:)` の方は残しています**。消えた entity への提案を残さないための後片付けなので、誰が呼んだかに関係なく正しい処理です。しかも今はシステム側が寄付しているので、消す対象は実際にあります。

```swift
try? await IntentDonationManager.shared.deleteDonations(
    matching: .entityIdentifiers([EntityIdentifier(for: todo)])
)
```

「追加で寄付、削除で寄付を消す」をペアで持つ、と前は書いていましたが、**ペアのうち片方だけが自分の責任だった** というのが今の理解です。

まだ残っている宿題は、**Widget / Control 起点が同じように記録されるか** です。シミュレータでは合成タップでコントロールが発火せず (Intent 自体が走らない)、ホームウィジェットの行は公式推奨どおり `Link` なので `Button(intent:)` がありません。ここは実機で見るしかなさそうです。


## 「消して」と「言ってない」を区別する: IntentParameter.valueState

公開後に追加で検証した話をここに足しておきます。99/N の将来トピックに挙げていた `IntentParameter.valueState` (セッション 344) で、`UpdateTodoIntent` という部分更新の Intent を新設しました。

更新系の Intent で optional なパラメータを素直に `String?` などで受けると、「新しい値を入れたい」「今の値を明示的に消したい」「触らず据え置きたい」の 3 つのうち後ろ 2 つが同じ `nil` に潰れてしまいます。`$param.valueState` を見ると、これを `.set(value)` / `.set(nil)` / `.unset` の三値で区別できます。

```swift
// UpdateTodoIntent.perform() 内
let entity = try todoService.update(
    todoId: todo.id,
    title: Self.requiredUpdate($title.valueState),
    todoDescription: Self.optionalUpdate($todoDescription.valueState),
    dueDate: Self.optionalUpdate($dueDate.valueState),
    isFavorite: Self.requiredUpdate($isFavorite.valueState),
    // ...
)

/// optional なモデル列: .set(nil) は「明示クリア」としてそのまま通す
private static func optionalUpdate<T>(_ state: IntentParameter<T?>.ValueState) -> FieldUpdate<T?> {
    if case .set(let value) = state { return .set(value) }
    return .unchanged
}

/// 必須のモデル列 (title など): .set(nil) も据え置き扱い (必須列は空にできない)
private static func requiredUpdate<T>(_ state: IntentParameter<T?>.ValueState) -> FieldUpdate<T> {
    if case .set(let value?) = state { return .set(value) }
    return .unchanged
}
```

受け側の `TodoService.update` は `FieldUpdate<Value>` (`.unchanged` / `.set(Value)`) という enum でフィールドごとに受けるようにして、`valueState` の三値をサービス層の語彙に写しています。title のように **モデル上は必須の列** は `.set(nil)` が来ても据え置きにする、という出し分けが必要だったので、上のとおり generic なヘルパーを optional 用と必須用の 2 種に分けました。

この記事の主題 (perform() を止めて聞き返す) とは道具が違いますが、「ユーザーが『消して』と言ったのか、単に何も言わなかったのか」を区別するという意味では同じ方向の話だと思ったので、ここに追記しています。

### 三状態が要るのは Siri / Shortcuts 側だけ

あとからアプリの編集画面をこの Intent に載せたときに分かったんですが、**三状態が必要なのは Siri / Shortcuts から呼ばれる経路だけ** でした。アプリのフォームは開いた時点で全フィールドの現在値を持っているので、保存では **全部を `.set` で送ります**。部分パッチではなく todo 全体の last-write-wins になりますが、現在値から始めているので触らなかった欄には同じ値が書き戻るだけです。

そのうえで 1 つ決めたのが、**`UpdateTodoIntent` の便宜 init は全フィールドを必須にする** ことでした。デフォルト値を与えると引数を省ける分は楽になるんですが、後から Intent にフィールドが増えたときに **フォームが黙って古いままになります** (コンパイルは通るので、増えたフィールドだけ保存で消える、という壊れ方をします)。必須にしておけばコンパイルエラーで気付けるので、面倒な方を採りました。「呼出側を楽にする既定値」が、この手の *後から増える* 契約とは相性が悪いんだなと思います。

全フィールドを毎回送るようにしたことで、副作用も 1 つ出てきました。6/N に書いたとおり場所は「名前 + 座標」に分解して保存しているんですが、**名前だけ差し替えると座標が前の場所のまま残ります**。座標は解決元の名前に属するので、名前が変わったら落とす、同じなら保つ、という分岐を足しました。フォームが毎回全フィールドを送る以上、これが無いと **場所と無関係な保存で座標が消える** (あるいは古い座標が生き残る) ことになります。3 ケースともテストにしました。

深さはこのあたりまで単体 (U) で、Shortcuts の UI が実際に「クリア」と「未指定」を区別して渡してくるかは実機待ちです。

## 実行の前に止めるか、後で取り消すか: UndoableIntent

99/N に「検証候補」として置いていた `UndoableIntent` (iOS 26 / セッション 275) も入れました。削除 3 種 (確認あり / 確認なし / バルク) と完了トグルが対象です。実行前の `requestConfirmation` と実行後の取り消しをどう住み分けるのかが分からない、というのが宿題だったんですが、やってみたら **住み分けるものではなくて、呼出元の性質で自動的に決まる** という結論になりました。`undoManager` は Intent を走らせた面が用意するもので、用意しない呼出元 (ウィジェットの `Button(intent:)` など) では `nil` になるので、登録がまるごと no-op になります。これは失敗ではなく想定どおりの分岐なので、`guard let` で静かに抜けます。つまり「確認を出せる面には確認が出るし、取り消せる面では取り消せる」だけで、こちらが場合分けする話ではありませんでした。

実装で分かったことをいくつか。

- **`UndoManager.registerUndo(withTarget:handler:)` はハンドラごと `@MainActor`** です (Foundation の swiftinterface が `handler: @escaping @MainActor (TargetType) -> Void` になっています)。`Task { @MainActor in }` でホップする必要はなく、`TodoService` をそのまま呼べます
- **完了トグルの取り消しは「逆トグル」ではなく「元の値へ戻す」**。取り消すまでの間に別経路 (Siri / ウィジェット / 別デバイスの CloudKit マージ) で状態が変わっていると、トグルは意図と逆に倒れます。なので `setCompletion(todoId:isCompleted:)` という絶対値の API を呼びます。5/N に書いた `SetValueIntent` を絶対値で受ける話と同じ形が、ここでも出てきました
- **復元は冪等にする**。`restore(_:)` は同じ id の Todo が既にあればそれを返すだけにして、二重の取り消しや CloudKit が先に戻したケースで重複を作らないようにしています
- 削除はサブタスクを cascade で連れていくので、スナップショットにサブタスクも入れて **サブタスクの id も保ちます**。カテゴリはリレーションを値で持ち越せないので id だけ持って復元時に引き直し、カテゴリ自体が消えていたら関連を落として復元します (カテゴリが無いせいで Todo が戻らない方が困るので)
- `TodoItem` / `SubTask` に **id を受け取る init を別途生やしました**。通常の `init(title:)` に id を足すと、普通の作成経路が既存の Todo と衝突しうる形になるので

登録処理は `TodoUndoRegistrar` という 1 つの型に集約しています。削除系の Intent が 3 つあるので、同じ登録をそれぞれに書くと片方だけ直し忘れる形で壊れるからです。

```swift
@MainActor
static func registerRestore(
    _ snapshots: [TodoItemSnapshot],
    undoManager: UndoManager?,
    service: TodoService
) {
    guard let undoManager, !snapshots.isEmpty else { return }
    undoManager.registerUndo(withTarget: service) { service in
        for snapshot in snapshots {
            // 1 件戻せなくても残りは戻す
            _ = try? service.restore(snapshot)
        }
    }
    undoManager.setActionName(
        String(localized: "Delete ^[\(snapshots.count) Todo](inflect: true)")
    )
}
```

取り消しメニューに出る名前は inflection 付きで書けます (6/N の複数形の話と同じです)。**スナップショットは削除する前に取る** のと、**同じ id で戻す** のが要点で、後者は Spotlight の index や entity の identity を保つために効いてきます。id が変わると「戻した」ように見えて別物になるので。

## Siri に読ませるエラー文言を決める

対話まわりでもう 1 つ、失敗したときの言い方も Siri に届く経路でした。IntentTodo は `IntentError` に `CustomAppIntentErrorConvertible` を付けています。

```swift
extension IntentError: CustomAppIntentErrorConvertible {
    public var appIntentError: AppIntentError { ... }
}
```

CosmoTunes はドメインエラーの enum に `CustomLocalizedStringResourceConvertible` を付けて、throw の直前に `AppIntentError(wrapping:)` で包む形だったんですが、1 段上のこちらを選びました。理由と注意点が 4 つあります。

- **throw する側で包む必要がありません**。公式いわく *"When you throw a conforming error from a method such as `perform()` […] the framework reads the `appIntentError` property and uses it directly."* なので、`TodoService` は AppIntents を import せずに `IntentError` を投げるだけで済みます。2/N で書いた「サービス層は Intent の都合を知らない」という線を保てるのが大きいです
- `errorDescription` (開発者向けに "Validation error: …" みたいなプレフィックスを付けているやつ) と、Siri が読む文言を **別々に決められます**。前者を読み上げさせたくないので
- 「見つからない」系は `AppIntentError(predefinedError: .Unrecoverable.entityNotFound, description:)` に載せています。文言だけでなく「参照先の entity が無い」という種別がシステムに伝わります
- ただし **`init(predefinedError:description:)` は受け付けない値を渡すと実行時に `fatalError()` します** (公式に明記されています)。ビルドでは検出できないので、全ケースを 1 度組み立てるだけのテストを置きました

なお両方 (`CustomLocalizedStringResourceConvertible` と `CustomAppIntentErrorConvertible`) に準拠した場合、システムは後者だけを見ます。

## この回で使った API がいつ入ったものか

WWDC 2022 から 2026 までのセッションを網羅的に洗い直したので、この記事で扱った道具の出自を整理しておきます。WWDC 2026 編の中に置いたせいで、全部が iOS 27 の新 API のように読めてしまう書き方になっていました。

セッションの書き起こしを 1 本ずつ全文検索して「その API 名が本当にそのセッションに出てくるか」を確かめたので、**セッションで説明されているもの** と **API ドキュメントで知ったもの** を分けて書いています。

- `requestConfirmation(for:dialog:)` は WWDC 2022 (セッション 10032) からある基本 API で、当時の `confirmBeforeRunning` を置き換える形で入ったものでした。
- iOS 27 では `requestConfirmation(_:confirmLabel:cancelLabel:)` という、確認とキャンセルのボタンラベルを個別に指定できるオーバーロードが増えています。ただしこれは **どのセッションの書き起こしにも出てこなくて、API ドキュメント側で見つけたもの** です。IntentTodo は既定のラベルのままで足りているので、こちらはまだ使っていません。
- `requestChoice` と `IntentChoiceOption` は iOS 26 (WWDC 2025 セッション 275) が初出でした。SwiftUI View を添える `requestChoice(between:dialog:view:)` も同じ 275 です。なので本文の「選ばれたオプションに安定 id が無い」という制約も、iOS 26 の時点からあった話ということになります。
- `IntentDialog(full:supporting:)` はちょっとややこしくて、**型としては WWDC 2022 (セッション 10032) に登場する** けれど、`full:` と `supporting:` を分けて出し分ける **具体例が出てくるのはセッション 343 (2:45)** でした。API 自体が新しいわけではなく、使いどころを示した実例の方が 2026 側にある、という形です。
- Interactive Snippet (`SnippetIntent`) も iOS 26 (セッション 275) の機能で、`SnippetIntent.reload()` まで含めてこの年に入っています。
- `UndoableIntent` も iOS 26 (セッション 275) です。取り消しの実装形そのものは WWDC 2026 の公式サンプル (CosmoTunes の `DeleteAlarmIntent`) が見せてくれているので、API と実例の年が離れている、という点では `IntentDialog(full:supporting:)` と同じ形になっています。
- `IntentDonationManager` と、本文で `deleteDonations(matching:)` に渡している `IntentDonationMatchingPredicate` は、**どちらもセッションの書き起こしには出てこず、API ドキュメント由来** です。WWDC 2023 (セッション 10103) にあるのは `RelevantIntent` / `RelevantIntentManager` / `RelevantContext` の方で、自分は隣にあったこれらと混ぜて覚えていました。

自分のアプリに入れる分には「今の SDK で使えるか」しか見ていなかったので気にしていなかったんですが、記事として読むと「WWDC 2026 で何が増えたのか」の情報として不正確なので直しておきます。ベースラインが iOS 26 のプロジェクトに iOS 27 の新要素を足していく作り方をしていると、この 2 世代の境目は自分でも結構あいまいになるなと思いました。

そしてもう 1 つ、「API ドキュメントを読んで知ったこと」と「セッションで説明されていたこと」を、自分の中で一緒くたに『WWDC のあの回で見た』として覚えていたのが、出典を間違えた主な原因でした。出典として書くならこの 2 つは分けておかないといけないなと思います。

## 検証できた深さ

今回は以下です。

- **ビルド成立 (B)**: `requestConfirmation` / `requestChoice` / `IntentDialog(full:supporting:)` / `SnippetIntent` / `UndoableIntent` / `CustomAppIntentErrorConvertible` はすべて OK。
- **単体 (U)**: `valueState` の三状態と `UndoableIntent` の復元は AppIntentsTesting で確認済みです (10/N)。`requestChoice` を使う Intent だけはテストから run できません。
- **観測 (シミュレータ)**: `Button(intent:)` の実行がシステムの donation に記録されることは実測しました。ただし Widget / Control 起点は測れていません。
- **実機 (R)**: Siri が実際に確認 UI / 選択 UI を出すか、スニペットが応答に出るかは未確認です。端末で触れたら追記します。

## まとめ

- `requestConfirmation` (yes/no) / `requestChoice` (多分岐) は perform() を止めてユーザーに聞ける。拒否 / `.cancel` は throw で中断される
- `requestChoice` の `IntentChoiceOption` は安定 id を持たないので、選択肢生成と逆引きを enum に一元化してタイトル照合 + フォールバックでドリフトを防ぐ
- `IntentDialog(full:supporting:)` で「音声単独」と「視覚併用」のメッセージを出し分ける
- `valueState` の三状態が要るのは **Siri / Shortcuts 側だけ**。アプリのフォームは全フィールドを `.set` で送る last-write-wins にする。便宜 init に既定値を与えると、Intent にフィールドが増えたときフォームが黙って古いままになる
- Interactive Snippet はボタンを押すたびにシステムが `SnippetIntent` を再 perform するので、perform で毎回最新 entity を取り直す。app プロセス提示なので entity 解決クラッシュは無関係
- **`perform()` の中で `donate()` を呼ぶのは規約違反**。呼出元を判別する API が無いので Siri / Shortcuts 経由でも走ってしまう
- そのうえで **アプリ内 `Button(intent:)` の実行はシステムがすでに donation として記録している** (実測)。UI が全部 `Button(intent:)` である限り、自分で寄付すべき操作が残らない。明示的な寄付はゼロのままでよい。`deleteDonations(matching:)` の方は呼出元に関係なく正しいので残す
- `UndoableIntent` は「確認と取り消しの住み分け」ではなく、`undoManager` を用意する呼出元でだけ効く仕組み。復元は **同じ id で・冪等に**、完了トグルの取り消しは逆トグルではなく元の値へ戻す
- Siri に読ませるエラー文言は `CustomAppIntentErrorConvertible` で決める。サービス層が AppIntents を import せずに済む

次回は、[大量の Todo を一括処理する `EntityCollection` / `LongRunningIntent` / `CancellableIntent` と、「検証してみたら自分のアプリには適合しなかった」`RelevantEntities` の話 (9/N)](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-31 (2)**: `valueState` の節に「三状態が要るのは Siri / Shortcuts 側だけ」を追加 (アプリのフォームは全フィールド `.set` の last-write-wins / 便宜 init は全フィールド必須 / 名前だけ変えたときの座標の扱い)
- **2026-08-31**: 寄付の節を書き換え。`donate()` をどこからも呼んでいないのに **`Button(intent:)` のタップがシステムの donation に記録されている** ことを実測したので、「寄付しない」の理由を「規約違反だから」から「**Intent を通らない UI 操作が存在しないから**」へ差し替え。観測の過程で 2 回逆の結論を出した (mtime を信じた / `+0` を「書かれていない」と読んだ) 経緯も追加
- **2026-08-28**: 寄付の節を全面的に書き換え。`perform()` 内の `donate()` は公式ガイダンス違反なので撤去し、代わりの 3 案も検討のうえ「入れない」で決着した経緯に差し替え (`deleteDonations` は残す)。`UndoableIntent` と `CustomAppIntentErrorConvertible` の節を追加
- **2026-08-13**: 呼出元に対話を提示する面が無い制約は `requestChoice` でも同じ、という点を明記
- **2026-08-12**: 呼出元に確認を出す面が無いと `requestConfirmation` が失敗する話を追加。FromExtension 撤去に追随
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-11**: 出自の整理をさらに訂正。`requestConfirmation(_:confirmLabel:cancelLabel:)` / `IntentDonationManager` / `IntentDonationMatchingPredicate` はセッションではなく API ドキュメント由来、`requestChoice(between:dialog:view:)` は 343 ではなく 275 が出典
- **2026-08-05**: この回で使った API の出自を整理する節を追加 (全部が iOS 27 の新 API のように読める書き方だった)
- **2026-07-02**: `IntentParameter.valueState` を使った `UpdateTodoIntent` の節を追加

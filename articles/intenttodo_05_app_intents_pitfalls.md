---
title: "App Intents 運用の罠 — Live Activity / Control Widget / Spotlight (5/N)"
emoji: "🪤"
type: "tech"
topics: ["AppIntents", "iOS", "WidgetKit", "Spotlight"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 5 回目です。

本記事では、IntentTodo を作っていて実機で気付いた App Intents 運用上の落とし穴を 5 つまとめます。
ドキュメント上では分かりにくいけれど、実装してみてはじめて気付くタイプのものを集めました。

## 落とし穴 1: Live Activity からの AppEntity 解決でクラッシュする (していた)

まず、**すでに消えた落とし穴** から書きます。ワークアラウンドを入れて、しばらく運用して、根拠が消えたので撤去した、という一連の流れごと残しておきたいので。

`@Parameter var todo: TodoAppEntity` を持つ Intent を Live Activity のボタンから発火させると、`EXC_BREAKPOINT` で死ぬケースに何度か遭遇していました。App Intents は `perform()` の前に `TodoEntityQuery.entities(for:)` を呼んで entity を解決するんですが、その **解決フェーズの途中で SwiftData の内部 assertion を踏んで trap** します。

回避策として、**呼出元が todoId を既に持っているなら、entity 解決を経由しない `String` パラメータ版の Intent を別に用意する** という分離をしていました (Primary / FromExtension と呼んでいました)。真因が何であれ、解決フェーズそのものを踏まなくなるので効きます。

### 実測したら再現しなかったので撤去した

この「削除タイミングが分からない技術的負債」、**iOS 27 では再現しませんでした**。

やったのは、`@Parameter var todo: TodoAppEntity` を持つ probe Intent を作って Live Activity のボタンをそれに差し替え、`entities(for:)` と `perform()` の両方に pid とプロセス名を出すログを入れる、というものです。

| ケース | `entities(for:)` | `perform()` | crash |
|---|---|---|---|
| アプリ起動中 + `LiveActivityIntent` 準拠 | メインアプリ | メインアプリ | 無し |
| アプリ kill 済み (cold start) + `LiveActivityIntent` 準拠 | メインアプリ (LA タップで起動) | メインアプリ | 無し |
| アプリ kill 済み + `LiveActivityIntent` **非**準拠 | メインアプリ | メインアプリ | 無し |

効いたのが 3 ケース目で、**`LiveActivityIntent` 準拠の有無は entity 解決のプロセスに影響しませんでした**。「準拠していなかったのが原因では」という仮説を持っていたんですが、現行 SDK では成立しません。

というわけで **分離は撤去して、1 アクション 1 Intent に統一** しました。Live Activity のボタンも Siri も同じ `ToggleTodoCompletionIntent(todo:)` を呼びます。Live Activity 側が持っているのは id と title だけですが、`TodoAppEntity(id:title:)` で組んで渡せば足ります。システムが `perform()` の前に id から再解決してくれるので。

副産物で 1 つ分かったことがあって、同じログを眺めていたら **Widget のタイムライン描画では `entities(for:)` が Widget Extension プロセスで走っていました**。「entity 解決は必ずアプリで走る」わけではなくて、上の結論はあくまで Live Activity ボタン経由に限った話です。2/N に書いた「Widget Extension 側にも `AppDependencyManager` の登録が要る」という運用は、これで実測の裏が取れました。

### 分けるなら理由は「振る舞いの違い」で

撤去したあとに残した分岐もあります。判断の軸が変わったので、そこも書いておきます。

| 分けている Intent | 残した理由 |
|---|---|
| `SnoozeTodoIntent` / `QuickSnoozeTodoIntent` | 前者は `requestChoice` で期間を選ばせます。Live Activity のボタンは背景実行で問い合わせる面が無いので、後者が既定 30 分で即実行する |
| `ToggleTodoCompletionIntent` / `SetTodoCompletionIntent` | 前者はトグル、後者は絶対値セット (`SetValueIntent`)。落とし穴 2 に書いたとおり `ControlWidgetToggle` は on/off を渡してくるので、トグルでは表現できない |

`SnoozeTodoFromExtensionIntent` は `QuickSnoozeTodoIntent` に改名しました。名前に "FromExtension" と付いていると「呼出元プロセスの都合で複製したもの」に読めますが、実際に残す理由は **対話できる呼出元かどうか** という振る舞いの違いなので、名前を実態に寄せた形です。

**呼出元プロセスの都合で Intent を複製しない、分けるなら振る舞いが違うときだけ**。これが今の整理です。ワークアラウンドは消せるとき消さないと、いつのまにか「そういう設計」の顔をして居座るんだなと思いました。

ワークアラウンドを書いていた当時の反省も 1 つ。「なぜ効くのか」を無理に 1 文で言い切ろうとして、「解決が Live Activity Extension プロセスで走るからだ」という筋の悪い断定を書いていました。Apple のドキュメントは `LiveActivityIntent` の `perform()` について "the system runs the app intent in the app's process" と明言していて、噛み合いません。公式が保証しているのは `perform()` の実行プロセスだけで、**その手前の事前解決フェーズがどのプロセスで走るかはどこにも書かれていない** ので、分かっているのは「未文書化のフェーズで実際にクラッシュした実績がある」までなんです。そこから先は書かない方が誠実でした。

なお検証のときに引っかかったのが **ログの取り方** です。プロセスをまたぐ話なので Xcode の launch session のログだと足りません (アプリを kill する検証だとセッションが切れます)。`simctl spawn <udid> log config --subsystem <サブシステム> --mode "level:debug,persist:debug"` で永続化してから `log show` で読む、という形にして、ようやくアプリ再起動や Extension 側まで一続きで追えるようになりました。


## 落とし穴 2: Control Widget では dialog も snippet も表示されない

iOS 18 で追加された Control Widget (Control Center に置けるカスタムボタン / トグル) ですが、ここから発火させた Intent では **`.result(dialog:)` も `snippetIntent:` も提示されません**。
Siri / Spotlight / Shortcuts では出る結果表示の経路が、Control Center 経由だと丸ごと無い、ということになります。

dialog の方は 2026-04-14 に、snippet の方は 2026-08-12 に、それぞれ実機で確認しました。

### 呼出元別の結果表示

| 呼出元 | `.result(dialog:)` | snippet (`snippetIntent:`) | ローカル通知 |
|-------|------------------|--------------------------|------------|
| Siri | 読み上げ ✅ | 表示 ✅ | 表示 ✅ |
| Spotlight / Shortcuts | 結果欄に表示 ✅ | 表示 ✅ | 表示 ✅ |
| UI (`Button(intent:)`) | 表示なし | 表示なし | 表示 ✅ |
| Widget `Button(intent:)` | 表示なし | 表示なし | 表示 ✅ |
| **Control (`ControlWidgetButton` / `ControlWidgetToggle`)** | **表示なし** | **表示なし** | 表示 ✅ |

### snippet の方は切り分けにだいぶ遠回りした

dialog は素直に実機で分かったんですが、snippet は自分の推論が邪魔をして遠回りしました。せっかくなので失敗の経緯ごと書いておきます。

最初、AppIntents の [Visual presentation](https://developer.apple.com/documentation/AppIntents/visual-presentation) が "Siri, Spotlight, and the Shortcuts app display snippets" と書いていて、セッション 281 (0:29) も同じ 3 つを挙げているのを見て、「列挙に Control が無いから出ないんだろう」と判断しました。**これは肯定リストからの推論で、実測ではありません**。にもかかわらず dialog の実測結果と並べて書いてしまったので、あとから自分で見返したときに実測されたルールのように見えていました。

しかもこの推論、設計にも影響していました。「Control では snippet が出ない」を前提に、snippet を返す Intent を全部 Control から外して Siri 側に寄せてしまったので、**Control 経由で snippet を返す経路が 1 つも無い** 状態になっていたんです。誤った前提が、それを反証する実験の可能性ごと潰していた形でした。

疑いを持ったのは、セッション 275 (1:40〜1:59) が「コントロールをタップ → Intent 実行 → snippet 表示 → snippet 内のボタンで即更新」をそのまま実演していたからです。肯定リストと真っ向からぶつかります。

そこで **呼出元だけを変えて、同じ Intent・同じ snippet を走らせる** 比較をしました。

| 条件 | 結果 |
|---|---|
| Spotlight → `ShowTodoCountIntent` (→ `TodoSummarySnippetIntent`) | 出る ✅ |
| Control (Button) → **同じ Intent・同じ snippet** | 出ない ❌ |
| 同上 + `allowedExecutionTargets = [.main]` でアプリプロセスに固定 | 出ない ❌ |
| Control (Toggle / `SetValueIntent`) → `TodoSnippetIntent` | 出ない ❌ |

2 番目と 1 番目は Intent も snippet も同一で、違うのは呼出元だけです。これで snippet 実装の不備 / パラメータの有無 / 実行プロセス / `isDiscoverable` / コントロールの形状 / メタデータ登録が全部否定できて、**残る差分は「呼出元が Control であること」だけ** になりました。

セッションを横断して見ても矛盾しませんでした。Controls 専門のセッション 10157 は snippet にも dialog にも一度も触れず、フィードバック手段として挙げるのは後述の 3 つだけです。逆に Snippets 専門のセッション 281 は control / Control Center という語を一度も使いません。唯一の反例に見えたセッション 275 は、そもそも "Control Center" / "ControlWidget" という語を全編で一度も使っていなくて (他のセッションは Control の話をするとき必ず明示します)、あの "the control" はアプリ内 UI のボタンを指していたと読むのが自然でした。

教訓は 2 つです。**肯定リストから否定を導かない**、導いたなら推論だと明示する。そして **「どの面が何を提示するか」は呼出元だけを変えた比較が最短で確定させる**。最初に Spotlight で試していれば「実装の問題か、面の問題か」が一発で分かれて、プロセスや形状の仮説を立てる必要すらありませんでした。まず既知の良い面で動かして、次に疑わしい面に持っていく。逆順にやると変数が絡んで、いつまでも確定しません。

### Control のフィードバックはコントロール自身の再描画

では何で伝えるのかというと、Apple が Control 用に用意しているのは次の 3 つでした。

1. **`perform()` 完了時の自動リロード** による、コントロール自身の再描画
2. `controlWidgetStatus(_:)` — 操作時に Control Center へ一時表示されるステータス文字列
3. `controlWidgetActionHint(_:)` — Action button 用のヒント文 (動詞始まり)

自分は長らく「dialog が出ないからローカル通知」で通していたんですが、これは 1 番目を見落としていたせいでした。Toggle なら on/off が、件数コントロールなら未完了数が、そのままコントロール面に出ます。そこに成功通知を足すと **二重表示になるうえ通知センターに残り続ける** ので、成功通知は全廃しました。特に件数コントロールは、面に出ている数字をタップしてその数字を通知する、という完全な二重表示になっていました。

残したのは **失敗時の通知だけ** です。失敗するとコントロールは前の状態のまま再描画されるので、「何も起きなかった」と区別が付きません。ここだけは他に伝える手段がないので通知が要ります。

`controlWidgetStatus(_:)` も一度は入れたんですが、撤去しました。理由が 2 つあって、まず公式ガイダンスが "Use status text sparingly and only in situations where important information isn't conveyed by the control" と言っていて、**コントロールが既に伝えている情報には使うな** という位置づけだからです。もう 1 つが恥ずかしい方の理由で、当時の provider は predicate が `!isCompleted` で絞っていたので `snapshot.isCompleted` が常に false になっていて、`.controlWidgetStatus("Completed")` の分岐は **到達不能なデッドコード** でした。シミュレータでビルドが通ったところで満足して、実機で見ていなかったので気付けていません。

読ませたい情報は Control ではなく Siri / Spotlight / Shortcuts 側に寄せる、というのが今の整理です。件数コントロールのタップは `LaunchAppIntent.incompleteTodos()` で未完了一覧を開くようにしました。グランスは数字、タップはドリルイン、という分担です。

### Button と Toggle の使い分けは「対象が固定されているか」

Toggle 化するときに分かったことも書いておきます。Apple の線引きは **対象が固定されているか** で決まっていました。

| | 用途 | 必要な Intent |
|---|------|--------------|
| `ControlWidgetButton` | fire-and-forget。状態を持たない | `AppIntent` / `OpenIntent` |
| `ControlWidgetToggle` | 2 状態の切り替え | `SetValueIntent where ValueType == Bool` |

肝は `isOn` が **provider が次のリロードで読み戻せる永続的な bool** でなければならない、というところです。もともと持っていた「最も緊急な Todo を完了する」というコントロールは、完了させると provider が別の (未完了の) Todo を返すので on 状態が永続しません。Toggle の意味論を満たさないわけです。Apple のサンプル (TimerToggle / GarageDoorOpener) がどれも「設定で選ばれた特定の entity」に対する操作なのは、これが理由だったんだなと腑に落ちました。

なので対象を `ControlConfigurationIntent` で固定する形に変えました。

```swift
struct ToggleTodoControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        AppIntentControlConfiguration(kind: Self.kind, provider: Provider()) { snapshot in
            ControlWidgetToggle(
                snapshot.title,
                isOn: snapshot.isCompleted,
                action: SetTodoCompletionIntent(todoId: snapshot.todoId ?? "")
            ) { isOn in
                Label(isOn ? "Completed" : "To Do",
                      systemImage: isOn ? "checkmark.circle.fill" : "circle")
                    .controlWidgetActionHint(isOn ? "Complete Todo" : "Reopen Todo")
            }
        }
        .promptsForUserConfiguration()   // 対象未設定だと機能しないので
        .displayName("Complete Todo")
        .description("Complete or reopen a todo you choose.")
    }
}
```

実装で気を付けたのが 3 つです。

- **action Intent は絶対値で受ける**。`SetValueIntent` の `value` はシステムが「トグルが移った先の状態」で埋めてくれます ("Don't set or manage the value parameter")。Toggle はその状態に収束しないといけないので、flip する `toggleCompletion` ではなく `setCompletion(todoId:isCompleted:)` のような絶対値の API を呼びます。flip だと冪等になりません。
- **パラメータは `todoId: String`**。ここはトグルではなく絶対値のセットで、呼出元が対象の id を知っているためです (呼出元プロセスの都合ではありません)。
- **configuration が持っている entity のスナップショットは古い**。選んだ時点の値しか持たないので、`currentValue(configuration:)` で id からストアを引き直して title / isCompleted を取り直します。

### おまけ: Control Widget の本体実装

値を表示するタイプ (カウント表示・次の期限など) では `StaticControlConfiguration(kind:provider:)` に `ControlValueProvider` を渡し、body は受け取った値を表示するだけにする、という構造が安全です。

```swift
struct TodoCountControl: ControlWidget {
    static let kind = "dev.touyou.IntentTodo.IntentTodoWidget.TodoCountControl"

    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: Self.kind, provider: Provider()) { count in
            ControlWidgetButton(action: LaunchAppIntent.incompleteTodos()) {
                Label { Text("\(count)") } icon: { Image(systemName: "checklist") }
                    .controlWidgetActionHint("Show Incomplete Todos")
            }
        }
        .displayName("Todo Count")
        .description("Shows incomplete todo count. Tap to open the list.")
    }
}

extension TodoCountControl {
    struct Provider: ControlValueProvider {
        var previewValue: Int { 3 }
        func currentValue() async throws -> Int { ... }
    }
}
```

なぜそうするかというと、セッション 10157 (9:51 / 11:22) が **非同期のデータ取得は `ControlValueProvider` の役目で、リロード時にシステムが `ControlValueProvider` → `body` の順で実行する** という分担を明確にしているからです。body は受け取った値を同期的に描くだけの場所として設計されているので、そこで SwiftData を直接引くとこの分担から外れます。

`currentValue()` の中でエラーが出たときは、通知ではなく **throw する** のが正解でした ("You can also throw an error to tell the system that the state couldn't be computed"、セッション 10157 の 10:26)。`try?` で `0` や空に潰すと、「全部完了」「期限近い Todo なし」という嘘をコントロール面に表示することになります。

### WidgetCenter はコントロールを更新しない

実機の Control Center を触っていて見つけたバグも 1 つ書いておきます。トグルのコントロールで Todo を完了にしても、**隣に置いた件数コントロールが古い値のまま止まる** という症状でした。数秒待っても直らず、アプリを再インストールするまで残ります。

原因は `WidgetReloader.reloadAllWidgets()` が `WidgetCenter.shared.reloadAllTimelines()` しか呼んでいなかったことでした。**ホームの Widget とコントロールは別 API** で、`WidgetCenter` はコントロールを更新してくれません。

システムが自動でリロードしてくれるのは、その Intent を実行した **コントロール自身だけ** です。他のコントロールまで巻き込みたいなら `ControlCenter.shared.reloadAllControls()` を明示的に呼ぶ必要がありました (visionOS では unavailable なので `#if !os(visionOS)` で保護しています)。

```swift
public enum WidgetReloader {
    public static func reloadAllWidgets() {
        WidgetCenter.shared.reloadAllTimelines()
        #if !os(visionOS)
        ControlCenter.shared.reloadAllControls()   // ← コントロールはこちら
        #endif
    }
}
```

2/N で「mutation の末尾で必ず `reloadAllWidgets()` が走るように `defer` で集約した」と書きましたが、集約先の中身が片肺だったという話でした。呼び忘れを構造で防ぐ仕組みを作っても、集約したメソッド自体が足りていないと結局同じところに落ちるんだなと思います。


### おまけ 2: 列挙が約束した遷移先は実装とセットで

上の件数コントロールを `LaunchAppIntent.incompleteTodos()` に付け替えたときに、地味なバグが 1 つ出てきました。タップしても **ただアプリが開くだけ** で、押した数字 (未完了数) と何の関係も無い画面が出てきます。

原因は `perform()` の実装漏れでした。

```swift
switch target {
case .addTodo:
    navigationModel.showAddTodo()
case .todoList, .incompleteTodos, .favoriteTodos:
    break        // ← 何もしていない
}
```

遷移先の `AppEnum` には `.incompleteTodos` / `.favoriteTodos` を定義していて、`caseDisplayRepresentations` にも「Incomplete Todos」「Favorite Todos」と出しているので、**列挙としては遷移先を約束している** のに、`perform()` 側は素の `navigateToRoot()` しかしていませんでした。Control 経由だけでなく、Siri に「お気に入りの Todo を見せて」と言ったときも同じく絞り込まれずに開くだけになっていたので、けっこう長いこと放置していたことになります。

`NavigationModel` に filter を渡す口が無かったのが根本だったので、検索語で使っていた `pendingSearchText` と同じハンドシェイクで `pendingFilter` を新設して塞ぎました。教訓としては、**画面ターゲットの `AppEnum` に case を足すのと、`perform()` でその状態を書き込むのは別作業** ということかなと思っています。まとめ `case` + `break` は「宣言はあるが実装が無い」を静かに隠すので、`AppEnum` を足したら書き込み側もセットで、を意識しておきたいところです。

### おまけ 3: cold start の 1 行を落とすと、アプリは開くのに画面に行かない

遷移まわりでもう 1 つ。iOS / visionOS では `LaunchAppIntent` と `OpenTodoIntent` を `UISceneAppIntent` に準拠させて、`SceneDelegate` を `AppIntentSceneDelegate` にしています。狙いはマルチウィンドウではなく **cold start** の方でした。

```swift
final class SceneDelegate: NSObject, UIWindowSceneDelegate, AppIntentSceneDelegate {
    func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
               options connectionOptions: UIScene.ConnectionOptions) {
        // Intent がきっかけでシーンが作られた場合、その Intent はここに渡ってくる
        guard let appIntent = connectionOptions.appIntent else { return }
        appIntent.performNavigation(forScene: scene)
    }

    func scene(_ scene: UIScene, willPerformAppIntent appIntent: any UISceneAppIntent) {
        appIntent.performNavigation(forScene: scene)   // 起動済みのシーンに対する実行
    }
}
```

肝は `connectionOptions.appIntent` の方で、**アプリが起動していない状態から Intent で開かれたときは `willPerformAppIntent` に来ません**。この 1 行を落とすと「アプリは開くが目的の画面に行かない」が cold start のときだけ起きます。起動中に試すと普通に動くので、たちが悪いです。

実装で気を付けたのは、遷移の中身を `applyNavigation()` という 1 つのメソッドに集約して、`perform()` とシーン経由の両方からそれを呼ぶ (冪等) ようにしたことでした。別々に書くと片方だけ直す事故になって、しかも **cold start しか壊れないので気付けません**。ここもソースを走査して集約が維持されていることを見るテストを置いています。

`performNavigation(forScene:)` はプロトコル要件が nonisolated なので、`@MainActor` を付けずに実装して中で `MainActor.assumeIsolated` しています。呼び出し元をシーンデリゲート (= メインスレッド) に限っているから成立する形です。

## 落とし穴 3: `IndexedEntity` 準拠だけでは Spotlight に検索されない

`TodoAppEntity` を `IndexedEntity` に準拠させ、`attributeSet` も実装したのに **Spotlight で検索しても何も出てこない**、という現象に出会いました。

```swift
extension TodoAppEntity: IndexedEntity {
    public var attributeSet: CSSearchableItemAttributeSet {
        let attributes = CSSearchableItemAttributeSet()
        attributes.displayName = title
        attributes.contentDescription = isCompleted ? "Completed" : "Incomplete"
        // ...
        return attributes
    }
}
```

これだけだと不十分でした。
`EnumerableEntityQuery.allEntities()` を実装していると Apple Intelligence 系の用途では拾われるのですが、**Spotlight に index を投入する経路は別** で、`CSSearchableIndex.default().indexAppEntities(...)` を明示的に呼ぶ必要があります。

### 解決策: TodoService に hook を生やす

IntentTodo では `TodoService` に Spotlight 操作を hook として組み込みました。

```swift
@MainActor
public final class TodoService {
    public func create(...) throws -> TodoAppEntity {
        defer { Self.dataDidChange() }
        // ... persist ...
        let entity = TodoAppEntity(from: item)
        reindexSpotlight(entity)
        return entity
    }

    public func delete(todoId: String) throws {
        defer { Self.dataDidChange() }
        // ... persist ...
        try repository.delete(by: uuid)
        deindexSpotlight(id: todoId)
    }

    func reindexSpotlight(_ entity: TodoAppEntity) {
        #if os(iOS) || os(macOS)
        Task {
            do {
                try await TodoSpotlightIndex.index().indexAppEntities([entity])
            } catch {
                spotlightLogger.error("reindex failed: \(String(reflecting: error))")
            }
        }
        #endif
    }
    // deindex 側もほぼ同じ形 (deleteAppEntities(identifiedBy:ofType:) を呼ぶだけ)
}
```

mutation のたびに差分 index、起動時に全件 index、という構成です。

```swift
// IntentTodoApp.init() の中
let todoService = TodoService.swiftDataBacked(container: modelContainer)
AppDependencyManager.shared.add(dependency: todoService)
Task(priority: .utility) { await todoService.indexAllForSpotlight() }  // 起動時に全件投入
```

### index は名前付きにする

上のコードで `CSSearchableIndex.default()` ではなく `TodoSpotlightIndex.index()` (中身は `CSSearchableIndex(name: "dev.touyou.IntentTodo.Todos")`) を使っているのは、公式ドキュメントの Note が **"use a named `CSSearchableIndex` type and not the default index. Use the default index only for prototyping and testing your code during development."** と言っているからです。最初は default index で書いていて、あとから移しました。

移行のときに 1 つ気を付けることがあって、**旧 default index に残ったアイテムがそのまま出るので同じ Todo が二重に見えます**。初回起動で 1 度だけ `CSSearchableIndex.default().deleteAllSearchableItems()` を呼んで掃除しました (default index にはこのアプリの Todo しか入れていないので、全消しで安全です)。

### donate 側だけ書くと片手落ち

`indexAppEntities` で donate する側だけ書いていたのも足りていませんでした。公式 (Making app entities available in Spotlight) が **受け側の実装も要求** しています。

> If you donate app entities to a `CSSearchableIndex` using its `indexAppEntities(_:priority:)` method, **implement the `IndexedEntityQuery` protocol** in your entity's query object to handle reindexing.

これが無いと、Spotlight 側が index を作り直したくなったときに応答先が無くて、次にアプリが起動して全件 index が走るまで検索に出てこなくなります。`TodoEntityQuery` に `reindexEntities(for:indexDescription:)` / `reindexAllEntities(indexDescription:)` を実装しました。

書いてみて引っかかったのが 2 つ。まず **`@MainActor` を付けられません**。`CSSearchableIndexDescription` が non-Sendable なので、MainActor 隔離した実装には渡せなくて `Non-Sendable parameter type 'CSSearchableIndexDescription' cannot be sent from caller of protocol requirement` になります。同じファイルの `entities(for:)` などは `@MainActor` で問題ないので、ここだけ nonisolated にして内側で await する形にしました。もう 1 つは単体テストで直接呼びにくいことで、`CSSearchableIndexDescription` の public な init は `init(coder:)` だけなので、素直にインスタンスを作れません。

### 起動のたびの全件 index は client state で省く

全件 index を毎回やるのももったいないので、名前付き index の `beginBatch()` / `endBatch(withClientState:)` / `fetchLastClientState()` を使って、前回コミットしたダイジェストと一致していたら丸ごと飛ばすようにしました。

```swift
let state = TodoSpotlightIndex.clientState(
    for: items.map { "\($0.id.uuidString)@\($0.modifiedAt.timeIntervalSinceReferenceDate)" }
)
let index = TodoSpotlightIndex.index()
if !isRepairing, await TodoSpotlightIndex.lastClientState(of: index) == state {
    return   // 前回から変わっていないので何もしない
}
index.beginBatch()                                    // batch は index 呼び出しの前に開く
try await index.indexAppEntities(items.map { TodoAppEntity(from: $0) })
try await index.endBatch(withClientState: state)      // 全件成功したときだけコミット
```

細かいところが地味に効きます。client state は 250 バイト上限なので SHA-256 で 32 バイトに畳んでいて、入力は **必ずソートしてから** hash します (fetch 順に依存すると、同じ内容でもダイジェストがぶれて結局毎回フル再インデックスになります)。ダイジェストの材料に **id だけでなく `modifiedAt` も混ぜる** のも要点で、id の集合が同じでも中身が変わることがあります (アプリ未起動中に他デバイスの編集が CloudKit で届いた、とか)。あと Todo が 0 件のときは batch を開かずに抜けています。空の no-op バッチで `endBatch` すると state が永続化されなくて、毎回フル再インデックスになりました。なお **batching は default index では使えない** (公式ヘッダに "Batching is unsupported for the CSSearchableIndex returned by the defaultSearchableIndex method" とあります) ので、名前付き index への移行が前提です。

Swift の API 名が ObjC ヘッダと違う (`beginIndexBatch` → `beginBatch()`、`endIndexBatchWithClientState:` → `endBatch(withClientState:)`) のも、ヘッダ名のまま書いてビルドエラーになって気付きました。

### Spotlight 系のエラーは fire-and-forget、ただし数える

差分反映のエラーは Intent 呼び出し側に伝播させたくない (Todo 追加のたびに Spotlight 失敗で UI エラーが出るのは過剰) ので、Task で fire-and-forget + `Logger.error` にしています。

ところがこれ、**上の省略と組み合わさると「壊れたまま復旧しない」状態を作れてしまいます**。差分反映が失敗しても呼出側には伝わらないし、client state は差分の成否と無関係に「最新」のままなので、次回起動の全件再インデックスも省略されます。結果、index が壊れた端末は Spotlight / Siri から Todo を引けないまま放置されて、しかも **アプリ内では正常に見えます**。自分で入れた最適化が、自分で書いた fire-and-forget と噛み合って穴になっていた形でした。

なので連続失敗を数えるようにしました。

- 閾値 (3 回) に達したら `UserDefaults` に「次回起動でフル再インデックス」の要求を立てて、client state が一致していても **省略しない**
- 1 回の失敗で倒さないのは、`quotaExceeded` や一時的な `indexUnavailable` みたいなその場限りの失敗にフル再インデックスをぶつけても直らないからです
- 成功したら連続カウントを畳む。フル再インデックスが通ったら要求を降ろす

判定は全部 `UserDefaults` の読み書きなので、テスト用の suite を注入すれば実機の Spotlight を壊さずに全分岐を押さえられました。「fire-and-forget にする」と決めたなら、**その失敗をどこかで拾い直す口もセットで要る** んだなと思います。

### platform gate

`CSSearchableIndex` は `#if canImport(CoreSpotlight)` で大半の Apple platform で使えますが、`TodoAppEntity: IndexedEntity` 自体が `#if os(iOS) || os(macOS)` で限定しているので、両者の gate を **同じものに揃える** のがビルドエラー回避のコツです。
canImport に変えると visionOS で `CSSearchableIndex` は import できても `IndexedEntity` 準拠が無いのでビルドエラーになります。

この「gate を揃える」話には続きがあって、逆に `canImport` でガードしていた Visual Intelligence 側が、SDK 更新後の visionOS 実機ビルドでだけ落ちるということがありました。`canImport` は import 可否しか見ないうえ、同じ OS でもシミュレータと実機で結果が変わることがある、というのが原因です。詳しくは [10/N](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing) に書きました。

## 落とし穴 4: アプリ内の `Button(intent:)` から `requestConfirmation` は失敗する

上のコントロールを実機で確認している最中に、まったく別のバグを踏みました。**詳細画面の Delete Todo を押しても Todo が消えない** というものです。

コンソールにはこれが出ていました。

```
DeleteTodoIntent failed to execute with error:
LNPerformActionErrorCodeUnsupportedValueType
```

原因は `DeleteTodoIntent.perform()` の中で呼んでいた `requestConfirmation(dialog:)` でした。8/N で書いたとおり、これは `perform()` を止めてユーザーに確認を求める API なんですが、**アプリ内の `Button(intent:)` には確認を提示する面がありません**。要求した時点で失敗して、削除まで到達しない、ということになります。

厄介なのが、**Siri / Shortcuts / AppIntentsTesting 経由では成功する** ところです。それらには確認を出す面があるので、テストは通ります。壊れているのは UI の削除経路だけ (一覧のスワイプ / iOS 詳細 / visionOS / watchOS の 4 箇所) でした。

対処は、確認なし版の `DeleteTodoImmediatelyIntent` (`isDiscoverable = false`) を分けて、呼出元ごとに使い分ける形にしました。

- 一覧のスワイプ削除は「スワイプして Delete を押す」自体が確認になっているので、確認なし版を直接実行
- 詳細画面は SwiftUI の `.confirmationDialog` で確認してから確認なし版を実行
- `DeleteTodoIntent` (確認付き) は Siri / Shortcuts 用としてそのまま残す

落とし穴 1 で書いた「分けるなら理由は振る舞いの違いで」がここにも出ていて、**対話できる呼出元かどうか** で分ける、という同じ形です。

### 見逃していた理由は条件付き assert

もう 1 つ反省があって、この経路には UI テストがありました。それなのに緑のまま何年も気付かなかったのは、テストがこう書いてあったからです。

```swift
if deleteButton.waitForExistence(timeout: 3) {
    // ... ここで削除を確認する assert
}
```

`if` で包んであるうえ、探していたラベルが `"Delete"` (実際は `"Delete todo"`) だったので、**中身が一度も実行されないまま緑** でした。要素が見つからないときに素通りするテストは、テストが無いのと同じどころか「テストがある」という誤った安心感がある分たちが悪いなと思います。`if` を外して正しいラベルで assert し直して、詳細画面用のケースも足しました。

### 逃げ先の SwiftUI 側にも罠があった

「確認は SwiftUI 側で出す」と決めたので、その延長で **編集シートを閉じる前の確認** も SwiftUI でやろうとして、もう 1 回転びました。

SDK 27 に `dismissalConfirmationDialog(_:shouldPresent:actions:message:)` という、まさにそれ用の modifier があります。ドキュメントにも "On iOS, the dialog appears when someone swipes down on the sheet or taps outside it" と書いてあって、`@available` でも弾かれません。ところが **シミュレータで一度も発火しませんでした**。

置き場所や条件を疑って、順に潰しています。

- フォームの内側 (`Form` + toolbar) に付ける → スワイプ下げでそのまま閉じる
- シート content の根 (`presentationDetents` と同じ位置) に、`shouldPresent: true` を **固定** で付ける → それでもそのまま閉じる
- 同じ固定条件で「キャンセル」の `dismiss()` を踏む → 確認なしで閉じる

「置き場所が悪い」と「dirty 判定が false になっている」の両方を潰しても出ないので、少なくとも iOS のシートでは実装が来ていないと判断しました。macOS のウィンドウでは動く可能性が残りますが、このアプリの追加・編集はどのプラットフォームでもシートなので使い道がありません。**ビルドが通って何も起きない** という、この記事で何度も出てくる形です。

代わりに 2 段構えにしました。

- `interactiveDismissDisabled(hasChanges)` で、**変更があるときだけ** スワイプ下げと外側タップを塞ぐ (detent 間のリサイズは残るので、シートが固まったようには見えません)
- 「キャンセル」ボタンは、変更があれば `.confirmationDialog`、無ければそのまま閉じる

つまり **スワイプ下げそのものには確認を出せません**。SwiftUI には「dismiss しようとした」を観測する公開 API が無いので、塞ぐところまでが限界でした。`dismissalConfirmationDialog` はまさにその穴を埋めるための API に見えるので、動くようになったら乗り換えたいところです。

実装で 1 つ気を付けたのが、**保存経路は塞がないこと** でした。`AddTodoIntent` / `UpdateTodoIntent` は `NavigationModel` のフラグを倒してシートを閉じていて、これは presenter 側の状態なので `interactiveDismissDisabled` の対象外です。ここが噛み合っていないと「保存したのに閉じない」になるので、実機で「保存 → 閉じる」まで見ました。

dirty 判定にも地味な罠があって、フォームの下書き型を「開いた時点の値」と比較するとき、**両方を同じ値から `init` で作らないと常に dirty になります**。こちらの下書き型は既定の `init` が `dueDate` に現在時刻を入れるので、別々に作ると生成した瞬間に差が出ていました。


## 落とし穴 5: 失敗が「無音」になる経路が 3 つあった

最後は毛色の違う話で、**失敗しているのにどこにも出てこない** 経路をまとめて塞いだときの話です。クラッシュしてくれれば気付けるんですが、App Intents まわりは「静かに何も起きない」で終わる形が結構あります。

### `@Dependency` の登録漏れはクラッシュではなく無音の失敗

いちばん実害が大きかったのがこれで、**watch アプリから Todo を追加する手段が丸ごと死んでいました**。

`AddTodoIntent.perform()` は最後に `navigationModel.dismissAddTodo()` を呼ぶので `NavigationModel` に依存しているんですが、`AppDependencyManager` にそれを登録していたのは iOS / macOS のアプリだけで、watch アプリは `ModelContainer` と `TodoService` しか登録していませんでした。watchOS シミュレータで「追加 → タイトル入力 → Add」まで操作すると、コンソールにこれが出ます。

```
AddTodoIntent failed to execute with error: Failed to retrieve dependency of type NavigationModel.
Please register your dependency with AppDependencyManager before performing a dependent intent.
```

**クラッシュではありません** (`fatalError` ではなく Intent 実行の失敗)。なので画面は何も変わらず、エラー表示も出ません。ユーザーから見ると「Add を押しても何も起きない」だけです。

厄介なのは、同じパッケージが全ターゲットにリンクされているので **プラットフォームごとに Intent の集合が変わらない** ことでした。iOS 向けに書いた Intent が watch でもそのまま生えていて、そこで要求される依存も同じです。「iOS で動いているから大丈夫」は根拠にならなくて、**依存の登録はプロセスごと・プラットフォームごとに全部揃える** 必要があります (2/N の表と同じ話が、また別の形で出てきました)。

ちなみにこの経路には既存の UI テストもあったんですが、「追加画面へ遷移してボタンがあること」までしか見ていなかったので一度も踏まれていませんでした。落とし穴 4 の条件付き assert と同じで、**assert の手前で止まっているテスト** が緑を出し続けていた形です。

### 通知が拒否されていると、コントロールの失敗はどこにも出ない

落とし穴 2 に書いたとおり、Control からの失敗を伝える手段は **ローカル通知しかありません**。ということは、通知が拒否されているとその一本足が折れて、失敗が完全に無音になります。コントロールは前の状態のまま再描画されるので、「何も起きなかった」と区別が付きません。

しかも `UNUserNotificationCenter.add` は **許可が無くても error を返しません** (システムが黙って捨てます)。なので `add` の完了を見ているだけでは検出できなくて、送る前に許可状態を見るしかありませんでした。

```swift
let center = UNUserNotificationCenter.current()
let status = await center.notificationSettings().authorizationStatus
guard status == .authorized || status == .provisional else {
    logger.error("notification dropped: not authorized (status=\(status.rawValue))")
    MissedFeedback.record(.notification)   // 「伝えられなかった」ことを残す
    return
}
```

`MissedFeedback` は App Group の `UserDefaults` に「この経路で伝えられなかった」という記録を置くだけの小さな仕組みです。**書き手が Control / Widget の Extension プロセスになり得る** ので、プロセスをまたげる場所に置く必要がありました。読み手はアプリの一覧画面で、設定アプリへのリンク付きのバナーを出して、閉じたら記録を消します。

出す条件は「通知設定が無効なこと」ではなく **実際に取りこぼしたとき** にしています。ユーザーが意図的に切っている設定を毎回蒸し返したくないので、実害が出た 1 回目から出す、という線引きです。逆に経路が使えるようになったら (許可が下りた / 有効に戻った) 記録を消します。古い記録でバナーを出し続けると、それはそれで嘘になるので。

### ライブアクティビティも同じ形だった

同じ構図がもう 1 つあって、`Activity.request` の前に `ActivityAuthorizationInfo().areActivitiesEnabled` を見て抜ける、というのは必須なんですが (無効な端末で毎回 throw させるとエラーが溢れます)、**そこで無言 return すると、ユーザーは「期限が近い Todo がロック画面に出てこない」理由に到達できません**。

なので抜ける前に `logger.warning` に残して (`error` にしないのは、ユーザー設定に沿った正常系だからです)、`MissedFeedback` に記録する形に揃えました。

3 つとも「エラーは起きているのに、誰にも伝わらない」という同じ形で、しかも **アプリの中だけ見ていると全部正常に見えます**。Spotlight の自己修復もそうでしたが、伝える手段が 1 つしか無いところは、その手段が塞がれたときのことまで含めて設計しないといけないんだなと思いました。

## おまけ: 置き場を間違えると邪魔になる API — SiriTipView と ShortcutsLink

落とし穴とは毛色が違うんですが、同じ「動いてはいるのに正しくない」話なので書いておきます。

IntentTodo は長らく `SiriTipView`（「"やることを追加" と言ってください」と教えるバナー）を **一覧の `List` の 1 行目に常設** していました。「最近のアプリで使っているのを見ないし、一等地に居座っているのが気になる」という違和感から棚卸ししたら、**違和感の方が正しかった** です。

まず **まだ使えるのか** を確認しました。`SiriTipView` も `ShortcutsLink` も deprecated ではありません（`ShortcutsLink` は macOS / watchOS の SDK に宣言そのものが無いので `@available` ではなく `#if` が要る、という差はあります）。

次に **推奨が生きているのか**。ローカルの WWDC 控えを全文検索したら、この 2 つに触れているのは 2022 / 2023 のセッションだけで、2024 以降には一度も出てきません。WWDC 2026 の公式サンプル 4 本も両方 0 件使用でした。discoverability の主題は Spotlight インデックスと App Schema 側に移っている、ということみたいです。

そして決定的だったのが、**当時のガイダンスが、当時の自分の実装をすでに否定していた** ことでした。

> carefully select moments ... immediately before or after completing an action that they may want to repeat

リスト先頭への無条件常設は、これにまったく当たっていません。「使えるかどうか」と「今も推奨されているか」と「自分の使い方が推奨に沿っているか」は別の問いで、自分は 1 つ目だけ見て 8 か月放置していました。

判断は「両方消す」ではなく **「役割どおりの置き場に直す」** にしました。

- `SiriTipView` は一覧の行から外して、上端の `safeAreaInset` へ移設。表示ポリシーも決めて、**アプリ UI 起点の追加を 3 回した後** に出し、通算 2 回まで、閉じたら以後出さない。Siri / Shortcuts / ウィジェット経由の追加は数えません（既にフレーズを使える人に教える意味が無いので）
- `ShortcutsLink` は設定画面の「Siri & Shortcuts」セクションへ。macOS には出しません（`ShortcutsLink` が無いのでセクションが空になる）

行から外したことの副産物として、10/N に書く onscreen annotation やドラッグ並べ替えの対象に **異物が混ざらなくなりました**。「教育用の行」がデータの行に混ざっていたのは、そもそも構造として無理があったなと思います。

最後に切り分けで 1 つ引っかかったことも書いておくと、直したあとシミュレータで確かめたら **Tip が出ませんでした**。「配線が壊れている」と早合点しかけたんですが、原因は端末の defaults に常設していた頃のキー（`isVisible = false`）が残っていたことで、**移行ロジックが意図どおり「もう閉じた人」と判定していた** だけでした。ユニットテストが緑でシミュレータで出ないときは、まず端末に残っている永続状態を疑う、というのが正しい順番です。ちなみに `defaults write` や plist の直接編集は `cfprefsd` のキャッシュに勝てないので、状態を作り直すなら `simctl uninstall` してから入れ直す方が確実でした。


## まとめ

- **Live Activity からの AppEntity 解決でクラッシュする** → Primary / FromExtension Intent 分離で回避していたが、iOS 27 では再現しないことを実測できたので **撤去して 1 アクション 1 Intent に統一**。分けるなら理由は呼出元プロセスではなく振る舞いの違いで
- **`WidgetCenter` はコントロールを更新しない** → 他のコントロールまで反映したいなら `ControlCenter.shared.reloadAllControls()` が要る
- **Control Widget では dialog も snippet も出ない** → 成功は `perform()` 完了時の自動リロードによるコントロール自身の再描画で伝える。通知は失敗時だけ。読ませたい情報は Siri / Spotlight 側へ寄せる
- **Control の Button と Toggle は「対象が固定されているか」で選ぶ** → `isOn` は provider が読み戻せる永続的な bool が要るので、対象が動くアクションは Toggle にできない。`SetValueIntent` は絶対値で受ける
- `StaticControlConfiguration(kind:provider:)` + `ControlValueProvider` パターンで body を薄く保つ。provider のエラーは `try?` で潰さず throw する
- **Spotlight は IndexedEntity だけでは index されない** → `indexAppEntities(...)` の明示登録が必要。index は名前付きにして、受け側の `IndexedEntityQuery` もセットで実装する。起動時の全件 index は client state で省けるが、**省略と fire-and-forget を組み合わせると壊れたまま復旧しない** ので連続失敗を数える
- **アプリ内の `Button(intent:)` から `requestConfirmation` は失敗する** → 確認を提示する面が無いため。Siri / Shortcuts / AppIntentsTesting では通るので気付きにくい。確認なし版を分けて、UI 側は `.confirmationDialog` で確認する
- ただし **逃げ先の SwiftUI 側にも罠がある**。`dismissalConfirmationDialog(_:shouldPresent:)` は iOS のシートでは発火しない (ビルドは通る)。「dismiss しようとした」を観測する公開 API が無いので、`interactiveDismissDisabled` で塞ぐところまでが限界
- **失敗が無音になる経路を塞ぐ** → `@Dependency` の登録漏れはクラッシュせず「何も起きない」で終わる。通知の許可が無いと Control の失敗報告は消える (`add` は error を返さない)。伝える手段が 1 つしか無いところは、塞がれたときの記録と設定誘導までセットで作る
- **`SiriTipView` / `ShortcutsLink` は置き場を間違えると邪魔になる**。「使えるか」だけでなく「今も推奨されているか」「自分の使い方が推奨に沿っているか」まで見る

これで本編 (1〜5) は一区切りです。ここから先は [WWDC 2026 編 (6/N)](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) で、新しい App Intents の API を試してみて分かった設計判断をまとめていきます。検証待ち・将来書く予定のトピックは [番外編 (99/N)](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) に並べてあります。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-31 (2)**: 落とし穴 4 に「逃げ先の SwiftUI 側にも罠があった」を追加 (`dismissalConfirmationDialog` が iOS のシートで空振りする / 代わりの 2 段構え / 保存経路は塞がない / dirty 判定の初期値)
- **2026-08-31**: 落とし穴 1 を圧縮 (撤去済みのワークアラウンドの実装詳細を落として、実測で消えるまでの流れだけ残した)。おまけとして `SiriTipView` を一覧の一等地から降ろし `ShortcutsLink` を設定に置いた話を追加
- **2026-08-28**: 落とし穴 5 (失敗が無音になる 3 経路 — `@Dependency` 登録漏れ / 通知拒否 / ライブアクティビティ無効) を追加。Spotlight の節を名前付き index + `IndexedEntityQuery` + client state による省略と自己修復まで書き直し (「自己修復ループは今後の改善ポイント」だったものを実装済みに)。cold start でシーン経由の遷移を取りこぼす話 (おまけ 3) を追加
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12 (2)**: Live Activity の entity 解決クラッシュが iOS 27 で **再現しない** ことを実測し、Primary / FromExtension 分離を撤去した経緯を追加 (タイトルの「FromExtension」も差し替え)。`WidgetCenter` がコントロールを更新しない件と、落とし穴 4 (アプリ内 `Button(intent:)` から `requestConfirmation` が失敗する) を追加
- **2026-08-12**: 落とし穴 2 を全面的に書き直し。**Control では snippet も出ない** ことを実機 (呼出元だけを変えた比較) で確定し、切り分けの経緯と教訓を追加。Control を Toggle 化したのに伴い、Button / Toggle の使い分けと `SetValueIntent` を絶対値で受ける話を追加。前日に追記した `.controlWidgetStatus(_:)` は **撤去** した (公式ガイダンスに反していたうえ、当時の provider の predicate のせいで分岐が到達不能なデッドコードだった)。成功通知を全廃し失敗時のみに縮小。`LaunchAppIntent` の遷移先実装漏れの話を追加
- **2026-08-11**: Live Activity のクラッシュについて「Extension プロセスで解決されるから」という原因断定を取り下げ (クラッシュ自体と回避策は変わらず)。`ControlValueProvider` を使う理由を「body の過剰評価を避ける」から「取得と描画の分担モデル」に訂正
- **2026-07-28**: `canImport` だけに頼ると visionOS 実機ビルドで落ちる話への相互リンクを追加

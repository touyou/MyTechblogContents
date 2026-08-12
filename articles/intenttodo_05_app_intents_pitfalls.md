---
title: "App Intents 運用の罠 — FromExtension / Control Widget / Spotlight (5/N)"
emoji: "🪤"
type: "tech"
topics: ["AppIntents", "iOS", "WidgetKit", "Spotlight"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 5 回目です。

本記事では、IntentTodo を作っていて実機で気付いた App Intents 運用上の落とし穴を 3 つまとめます。
ドキュメント上では分かりにくいけれど、実装してみてはじめて気付くタイプのものを集めました。

## 落とし穴 1: Live Activity からの AppEntity 解決でクラッシュする

`@Parameter var todo: TodoAppEntity` を持つ Intent を Live Activity ボタン経由で発火させると、`EXC_BREAKPOINT` で死ぬケースに何度か遭遇しました。
App Intents は `perform()` の前に `TodoEntityQuery.entities(for:)` を呼んで entity を解決するのですが、その **解決フェーズの途中で SwiftData の内部 assertion を踏んで trap** します。`TodoEntityQuery.entities(for:) → SwiftDataTodoRepository.fetch → ModelContext.fetch` という経路でした。

原因の特定はできていません。最初は「解決が Live Activity Extension プロセスで走るからだ」と書いていたんですが、Apple のドキュメントは `LiveActivityIntent` について "the system runs the app intent in the app's process" と明言していて、Primary 版が `LiveActivityIntent` に準拠している以上 `perform()` はアプリプロセスで走るはずです。ここで噛み合いません。公式が保証しているのは `perform()` の実行プロセスだけで、**その手前の事前解決フェーズがどのプロセスで走るかはどこにも書かれていない** ので、そこを断定するのはやめました (セッション 345 の 7:37 も「Intent 実行の前に entity 解決が走る」とフェーズが分かれていることは言っていますが、プロセスの話はしていないです)。

直接の修正は難しい (Apple 側のバグ寄り) ので、**Primary / FromExtension Intent 分離パターン** で回避しています。真因が何であれ、解決フェーズそのものを踏まなくなるので効きます。

| 区分 | 呼出元 | パラメータ型 | `isDiscoverable` | AppShortcuts 登録 |
|------|-------|------------|------------------|--------------------|
| **Primary** | Siri / Shortcuts / UI | `TodoAppEntity` (`@Parameter`) | `true` (default) | ✅ |
| **FromExtension** | Live Activity / Widget (todoId を既に持っている) | `String` (UUID 文字列) | `false` | ❌ |

呼び出し側 (Live Activity ボタン) が todoId を既に持っているなら、entity 解決を経由しない `String` パラメータ版を別 Intent として用意すれば、entity 解決のクラッシュ経路を踏まずに済みます。

```swift
// Primary
public struct ToggleTodoCompletionIntent: AppIntent {
    @Parameter(title: "Todo") public var todo: TodoAppEntity
    @Dependency var todoService: TodoService
    // ...
}

// FromExtension (Live Activity ボタン用)
public struct ToggleTodoCompletionFromExtensionIntent: AppIntent {
    public static let isDiscoverable = false
    @Parameter(title: "Todo ID") public var todoId: String
    @Dependency var todoService: TodoService
    // ...
}
#if os(iOS)
extension ToggleTodoCompletionFromExtensionIntent: LiveActivityIntent {}
#endif
```

ビジネスロジックは前回までで紹介した `TodoService` に集約しているので、両者ともに `todoService.toggleCompletion(todoId:)` を呼ぶだけです。

### 運用ルール

このパターンは workaround 寄りなので、コード内に「いつ削除する想定か」を明記しておくのが大事だと思っています。
Apple のバグが直ったら 2 系統に分ける必要はなくなるので、削除タイミングが分からないと永久に技術的負債として残ります。

```swift
//  ⚠️ Apple bug workaround (keep until Issue #30 A-3 is verified fixed).
//
//  When an Intent with `@Parameter var todo: TodoAppEntity` runs inside the
//  Live Activity Extension process, App Intents calls TodoEntityQuery.entities(for:)
//  to resolve the entity before perform(). SwiftData then trips an internal
//  assertion and the Extension crashes with EXC_BREAKPOINT.
//
//  This variant sidesteps that path by accepting the UUID string directly.
//  Delete this file once Apple fixes the bug — do NOT introduce new
//  FromExtension variants without re-checking the issue first.
```

「コードコメントに残す」「Issue で追跡する」「`docs/insights` に記述する」の 3 点で削除タイミングを忘れないようにしています。

ワークアラウンドを書くときに「なぜ効くのか」を無理に 1 文で言い切ろうとすると、上に書いたような筋の悪い断定 (「Extension プロセスで解決されるから」) が混ざるんだな、というのはちょっと覚えておきたいところでした。分かっているのは「事前解決フェーズのプロセスが未文書化で、そこで実際にクラッシュした実績がある」までで、そこから先は書かない方が誠実だと思っています。

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
- **パラメータは `todoId: String`**。落とし穴 1 の FromExtension と同じ理由で、`TodoAppEntity` にすると事前の entity 解決フェーズを踏むためです。呼出元が id を知っているので解決自体が要りません。
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

IntentTodo では `TodoService` に Spotlight 操作を private hook として組み込みました。

```swift
@MainActor
public final class TodoService {
    public func create(...) throws -> TodoAppEntity {
        defer { WidgetReloader.reloadAllWidgets() }
        // ... persist ...
        let entity = TodoAppEntity(from: item)
        reindexSpotlight(entity)
        return entity
    }

    public func delete(todoId: String) throws {
        defer { WidgetReloader.reloadAllWidgets() }
        // ... persist ...
        try repository.delete(by: uuid)
        deindexSpotlight(id: todoId)
    }

    private func reindexSpotlight(_ entity: TodoAppEntity) {
        #if os(iOS) || os(macOS)
        Task {
            do {
                try await CSSearchableIndex.default().indexAppEntities([entity])
            } catch {
                spotlightLogger.error("reindex failed: \(String(reflecting: error))")
            }
        }
        #endif
    }

    private func deindexSpotlight(id: String) {
        #if os(iOS) || os(macOS)
        Task {
            do {
                try await CSSearchableIndex.default().deleteAppEntities(
                    identifiedBy: [id], ofType: TodoAppEntity.self
                )
            } catch {
                spotlightLogger.error("deindex failed: \(String(reflecting: error))")
            }
        }
        #endif
    }
}
```

mutation のたびに差分 index、起動時に全件 index、という構成です。

```swift
// IntentTodoApp.init() の中
let todoService = TodoService.swiftDataBacked(container: modelContainer)
AppDependencyManager.shared.add(dependency: todoService)
Task { await todoService.indexAllForSpotlight() }  // 起動時に全件投入
```

### Spotlight 系のエラーは fire-and-forget でいい

ここでのエラーは Intent 呼び出し側に伝播させたくない (Todo 追加のたびに Spotlight 失敗で UI エラーが出るのは過剰) ので、Task で fire-and-forget + Logger.error にしています。

ただし、CSSearchableIndex のエラーは `NSError(domain: CSSearchableIndexErrorDomain, code:)` で `code` を見れば `quotaExceeded` / `invalidIndexState` / `userInteractionRequired` / `indexUnavailable` が区別できるはずなので、自己修復ループ (N 回連続失敗で次回起動時に full reindex) にするとより堅牢になりそう、というのは今後の改善ポイントです。

### platform gate

`CSSearchableIndex` は `#if canImport(CoreSpotlight)` で大半の Apple platform で使えますが、`TodoAppEntity: IndexedEntity` 自体が `#if os(iOS) || os(macOS)` で限定しているので、両者の gate を **同じものに揃える** のがビルドエラー回避のコツです。
canImport に変えると visionOS で `CSSearchableIndex` は import できても `IndexedEntity` 準拠が無いのでビルドエラーになります。

(2026-07-28 追記) この「gate を揃える」話には続きがあって、逆に `canImport` でガードしていた Visual Intelligence 側が、SDK 更新後の visionOS 実機ビルドでだけ落ちるということがありました。`canImport` は import 可否しか見ないうえ、同じ OS でもシミュレータと実機で結果が変わることがある、というのが原因です。詳しくは [10/N の追記](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing) に書きました。

## まとめ

- **Live Activity からの AppEntity 解決でクラッシュする** → Primary / FromExtension Intent 分離で回避。コードコメントと issue で削除タイミングを追跡。原因は特定できていない (事前解決フェーズのプロセスが未文書化)
- **Control Widget では dialog も snippet も出ない** → 成功は `perform()` 完了時の自動リロードによるコントロール自身の再描画で伝える。通知は失敗時だけ。読ませたい情報は Siri / Spotlight 側へ寄せる
- **Control の Button と Toggle は「対象が固定されているか」で選ぶ** → `isOn` は provider が読み戻せる永続的な bool が要るので、対象が動くアクションは Toggle にできない。`SetValueIntent` は絶対値で受ける
- `StaticControlConfiguration(kind:provider:)` + `ControlValueProvider` パターンで body を薄く保つ。provider のエラーは `try?` で潰さず throw する
- **Spotlight は IndexedEntity だけでは index されない** → `CSSearchableIndex.default().indexAppEntities(...)` の明示登録が必要。TodoService の mutation hook と起動時の全件投入で組む

これで本編 (1〜5) は一区切りです。ここから先は [WWDC 2026 編 (6/N)](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) で、`xcode27` ブランチで新しい App Intents の API を試してみて分かった設計判断をまとめていきます。検証待ち・将来書く予定のトピックは [番外編 (99/N)](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) に並べてあります。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-12**: 落とし穴 2 を全面的に書き直し。**Control では snippet も出ない** ことを実機 (呼出元だけを変えた比較) で確定し、切り分けの経緯と教訓を追加。Control を Toggle 化したのに伴い、Button / Toggle の使い分けと `SetValueIntent` を絶対値で受ける話を追加。前日に追記した `.controlWidgetStatus(_:)` は **撤去** した (公式ガイダンスに反していたうえ、当時の provider の predicate のせいで分岐が到達不能なデッドコードだった)。成功通知を全廃し失敗時のみに縮小。`LaunchAppIntent` の遷移先実装漏れの話を追加
- **2026-08-11**: Live Activity のクラッシュについて「Extension プロセスで解決されるから」という原因断定を取り下げ (クラッシュ自体と回避策は変わらず)。`ControlValueProvider` を使う理由を「body の過剰評価を避ける」から「取得と描画の分担モデル」に訂正
- **2026-07-28**: `canImport` だけに頼ると visionOS 実機ビルドで落ちる話への相互リンクを追加

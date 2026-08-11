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

## 落とし穴 2: Control Widget では `.result(dialog:)` が表示されない

iOS 18 で追加された Control Widget (Control Center に置けるカスタムボタン) ですが、ここから発火させた Intent では **`.result(dialog:)` が表示されません**。
つまり、Siri や Shortcuts では表示される音声 / テキストフィードバックの経路が、Control Center 経由では完全に死んでいます。

Apple のドキュメントには明確な記述が無くて、実機で 2026-04-14 に検証して気付いたパターンです。

### 呼出元別 Dialog 表示の有無

| 呼出元 | `.result(dialog:)` | ローカル通知 |
|-------|------------------|------------|
| Siri | 読み上げ ✅ | 表示 ✅ |
| Shortcuts | 結果欄に表示 ✅ | 表示 ✅ |
| UI (`Button(intent:)`) | 表示なし | 表示 ✅ |
| Widget `Button(intent:)` | 表示なし | 表示 ✅ |
| **Control Widget (`ControlWidgetButton`)** | **表示なし** | 表示 ✅ |

### 対処: 通知 / 視覚的状態変化で代替する

Control Center から呼ばれる Intent (例: 「最も期限の近い Todo を完了する」) は、**ローカル通知** でフィードバックを返す運用にしました。

```swift
public struct ToggleUrgentTodoIntent: AppIntent {
    public static let supportedModes: IntentModes = [.background]

    @Dependency var todoService: TodoService

    public func perform() async throws -> some IntentResult {
        guard let result = try todoService.toggleMostUrgentTodo() else {
            return .result()
        }
        ControlNotificationHelper.sendToggledNotification(
            todoTitle: result.title,
            isCompleted: result.isNowCompleted
        )
        return .result()
    }
}
```

これは「by-design 寄り」と判断していて、Control Widget のグラス風ミニマム UI には dialog という重い表示は合わない、という Apple 側の意図を尊重した運用としています。

### (2026-08-11 追記) Control 用のフィードバック機構 .controlWidgetStatus を足した

「dialog が出ないからローカル通知」でずっと片付けていたんですが、Control には Control 用のフィードバック機構がちゃんと用意されていました。セッション 10157 (16:08) の `.controlWidgetStatus(_:)` で、Control のラベルに付けると Control Center 側に一時的なステータス文字列を出せます。

```swift
ControlWidgetButton(action: ToggleUrgentTodoIntent()) {
    Label {
        Text(snapshot.title ?? "No urgent todo")
    } icon: {
        Image(systemName: snapshot.isCompleted
            ? "checkmark.circle.fill"
            : "clock.badge.exclamationmark")
    }
    .controlWidgetStatus(snapshot.isCompleted ? "Completed" : "Due soon")
}
```

`ToggleUrgentTodoControl` に入れて、シミュレータ向けビルドまでは確認しました。ただ通知の置き換えにはしていなくて、併用にしています。通知はシステムの通知センターに残るので後から辿れる一方、`.controlWidgetStatus` は Control の上に一瞬出て消えるだけなので、そもそも性格が違うと思ったからです。タップした瞬間のフィードバックは status、後から「何をやったか」を辿る記録は通知、という分け方に落ち着きました。

`TodoCountControl` の方は見送っています。こっちは値を持たない fire-and-forget なボタンで、タップしても表示している未完了件数自体が変わらないので、status を足しても言うことが無いためです。

実機の Control Center で実際どう見えるか (どのくらいの時間出るのか、通知と二重で鬱陶しくないか) はまだ見られていないので、確認できたら追記します。

### おまけ: Control Widget の本体実装

Control Widget は値を表示するタイプ (カウント表示・次の期限など) では `StaticControlConfiguration(kind:provider:)` に `ControlValueProvider` を渡し、body は受け取った値を表示するだけにする、という構造が安全です。

```swift
struct TodoCountControl: ControlWidget {
    static let kind = "dev.touyou.IntentTodo.IntentTodoWidget.TodoCountControl"

    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: Self.kind, provider: Provider()) { count in
            ControlWidgetButton(action: ShowTodoCountIntent()) {
                Label { Text("\(count)") } icon: { Image(systemName: "checklist") }
            }
        }
        .displayName("Todo Count")
        .description("Shows incomplete todo count. Tap for summary.")
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
- **Control Widget では `.result(dialog:)` が出ない** → 一瞬のフィードバックは `.controlWidgetStatus(_:)`、後から辿る記録はローカル通知、と併用。`StaticControlConfiguration(kind:provider:)` + `ControlValueProvider` パターンで body を薄く保つ
- **Spotlight は IndexedEntity だけでは index されない** → `CSSearchableIndex.default().indexAppEntities(...)` の明示登録が必要。TodoService の mutation hook と起動時の全件投入で組む

これで本編 (1〜5) は一区切りです。ここから先は [WWDC 2026 編 (6/N)](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) で、`xcode27` ブランチで新しい App Intents の API を試してみて分かった設計判断をまとめていきます。検証待ち・将来書く予定のトピックは [番外編 (99/N)](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) に並べてあります。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-11**: Live Activity のクラッシュについて「Extension プロセスで解決されるから」という原因断定を取り下げ (クラッシュ自体と回避策は変わらず)。`ControlValueProvider` を使う理由を「body の過剰評価を避ける」から「取得と描画の分担モデル」に訂正。`.controlWidgetStatus(_:)` を実装した節を追加
- **2026-07-28**: `canImport` だけに頼ると visionOS 実機ビルドで落ちる話への相互リンクを追加

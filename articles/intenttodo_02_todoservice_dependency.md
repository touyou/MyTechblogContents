---
title: "TodoService と @Dependency でビジネスロジックを一元化する (2/N)"
emoji: "🎛️"
type: "tech"
topics: ["AppIntents", "SwiftData", "Swift", "iOS"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ (1/N)](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の続きです。今回は、Intent から呼ばれるビジネスロジックをどこに、どう置くかという話です。

IntentTodo では当初 `TodoActions` という enum + static func の集まりを置き、各 Intent から `TodoActions.toggleCompletion(todoId:using:)` のように呼んでいました。
これを最近 `TodoService` という `@MainActor final class` に昇格させた経緯と、その過程で得た知見をまとめます。

## なぜ最初は enum + static func だったか

当時は Primary / FromExtension の 2 系統 Intent (詳細は本シリーズ 5/N。この分離自体はのちに撤去しました) が同じビジネスロジックを呼んでいたので、共通化が必要でした。
最小コストで共通化するなら enum + static func が手早いので、まずはそうしました。

```swift
public enum TodoActions {
    @MainActor
    public static func toggleCompletion(
        todoId: String,
        using repository: any TodoRepositoryProtocol
    ) throws -> TodoToggleResult { ... }
}
```

呼び出し側はこんな感じ。

```swift
public func perform() async throws -> some IntentResult & ReturnsValue<TodoAppEntity> {
    let repository = SwiftDataTodoRepository(modelContext: modelContainer.mainContext)
    let result = try TodoActions.toggleCompletion(todoId: todo.id, using: repository)
    WidgetReloader.reloadAllWidgets()
    return .result(value: result.entity)
}
```

これでも動くのですが、いくつか負債が溜まっていきました。

- 各 Intent で `SwiftDataTodoRepository(modelContext:)` を都度生成している (DRY 違反)
- 各 Intent の最後に `WidgetReloader.reloadAllWidgets()` を呼ぶ規約がコンパイル時には強制できない (呼び忘れリスク)
- View からも将来的に `TodoActions` を呼びたくなったとき、`@Dependency` 的な注入経路がない

## class への昇格

これらをまとめて解消するために、ビジネスロジックを `TodoService` という MainActor 上のクラスに集約しました。

```swift
@MainActor
public final class TodoService {
    private let repository: any TodoRepositoryProtocol

    public init(repository: any TodoRepositoryProtocol) {
        self.repository = repository
    }

    public func toggleCompletion(todoId: String) throws -> TodoToggleResult {
        defer { Self.dataDidChange() }
        let item = try resolve(todoId: todoId)
        item.isCompleted.toggle()
        item.modifiedAt = Date()
        try repository.update(item)
        return TodoToggleResult(entity: TodoAppEntity(from: item), isNowCompleted: item.isCompleted)
    }
}
```

ポイントは 2 つ。

1. **Repository を init で注入**: 呼び出し側 (Intent) は repository を組み立てなくてよい
2. **`defer { Self.dataDidChange() }`**: mutation 系メソッドの末尾で必ずデータ変更後の後処理が走る。Intent 側で呼び忘れる心配がなくなる

副次的に、Intent の perform() がぐっと薄くなりました。

```swift
public func perform() async throws -> some IntentResult & ReturnsValue<TodoAppEntity> {
    let result = try todoService.toggleCompletion(todoId: todo.id)
    return .result(value: result.entity)
}
```

## @Dependency と AppDependencyManager

App Intents には `@Dependency` というプロパティラッパーがあり、`AppDependencyManager` に登録されたインスタンスを Intent から取得できます。
TodoService は `@MainActor final class` で `Sendable` 要件を満たすので、そのまま `@Dependency` で受け取れます。

```swift
public struct ToggleTodoCompletionIntent: AppIntent {
    @Parameter(title: "Todo") public var todo: TodoAppEntity

    @Dependency
    var todoService: TodoService

    @MainActor
    public func perform() async throws -> some IntentResult & ReturnsValue<TodoAppEntity> {
        let result = try todoService.toggleCompletion(todoId: todo.id)
        return .result(value: result.entity)
    }
}
```

肝心な「TodoService を作るのは誰か」は、`App.init()` で 1 回だけやって `AppDependencyManager` に同期登録します。

```swift
@main
struct IntentTodoApp: App {
    let modelContainer: ModelContainer
    @State private var navigationModel: NavigationModel

    init() {
        let container = try SharedModelContainer.createContainer()   // 実際は do / catch でログを残してから落とす (3/N)
        self.modelContainer = container
        AppDependencyManager.shared.add(dependency: container)

        let todoService = TodoService.swiftDataBacked(container: container)
        AppDependencyManager.shared.add(dependency: todoService)

        let navigation = NavigationModel()
        self.navigationModel = navigation
        AppDependencyManager.shared.add(dependency: navigation)
    }
}
```

`TodoService.swiftDataBacked(container:)` は IntentTodo 側で生やしたファクトリです。
理由は次回の記事 (3/N) で詳述しますが、Widget Extension や watchOS App といった、Repository パッケージを直接 link していないターゲットからも、TodoAppIntents パッケージだけを import すれば TodoService を作れるようにしておくと便利だからです。

## 実行プロセスごとに登録する

ここがハマりどころです。`AppDependencyManager.shared` はプロセス単位なので、Intent が走るプロセスごとに登録しなおす必要があります。

| 呼出元 | モード | 実行プロセス | 登録場所 |
|---|---|---|---|
| Siri / Shortcuts / UI | 全モード | メインアプリ | `App.init()` |
| Widget `Button(intent:)` | `.foreground(.immediate)` | メインアプリ | `App.init()` |
| Widget `Button` / Control Widget (読み取り系 = 未指定) | `.background` | **ヒューリスティクスで決定** (アプリ起動中はアプリ優先、未起動なら Widget Extension) | **両方** (`App.init()` と `WidgetBundle.init()`) |
| 同上 (書き込み系 = `allowedExecutionTargets = [.main]`) | `.background` | メインアプリに固定 | `App.init()` だけ |
| Live Activity ボタン | `LiveActivityIntent` | `perform()` は**メインアプリ** (Apple 公式が明言) | `App.init()` |
| watchOS の Button(intent:) | 全モード | **watchOS App** | watchApp の `App.init()` |

`.background` の行は、自分は最初「Widget から呼んだら必ず Widget Extension で実行される」という固定のものだと思っていたんですが、そうではありませんでした。セッション 345 (15:59〜16:55) によると、共有パッケージに置いた Intent がどのプロセスで実行されるかは **システムのヒューリスティクスで決まります**。アプリが既に起動していればアプリ側を優先する、そうでなければ Extension を起こす、という具合です。固定したいなら 9/N で書く `allowedExecutionTargets` (`.main` / `.appIntentsExtension` / `.widgetKitExtension`) を明示するしかありません。SDK 側を見ても `IntentExecutionTargets` は `.default` を独立したケースとして持つ `OptionSet` になっていて、「既定はシステムに委ねる」というのが型の上でもそう表現されていました。

`supportedModes` が決めているのは「フォアグラウンドに遷移するかどうか」であって、実行プロセスそのものではない、というのが正確なところです。

Live Activity の行も注釈が要ります。Apple のドキュメント ([Adding interactivity to widgets and Live Activities](https://developer.apple.com/documentation/widgetkit/adding-interactivity-to-widgets-and-live-activities)) は "the system runs the app intent in the app's process" と明言していて、`LiveActivityIntent` の `perform()` はアプリプロセスでの実行が保証されています。ただしこれには続きがあって、`@Parameter` の entity を **`perform()` の前に解決するフェーズ** がどのプロセスで走るかは公式にどこにも書かれていません。5/N で書くクラッシュはそっち側で起きています。

なので、IntentTodo では `IntentTodoApp.init()` / `IntentTodoWidgetBundle.init()` / `IntentTodoWatchApp.init()` の 3 箇所で同じ TodoService を作って登録しています。

```swift
// IntentTodoWidgetBundle.swift
@main
struct IntentTodoWidgetBundle: WidgetBundle {
    init() {
        AppDependencyManager.shared.add(dependency: sharedWidgetModelContainer)
        MainActor.assumeIsolated {
            let todoService = TodoService.swiftDataBacked(container: sharedWidgetModelContainer)
            AppDependencyManager.shared.add(dependency: todoService)
        }
    }
    // ...
}
```

`MainActor.assumeIsolated` は WidgetBundle.init が non-isolated context として評価されることがあるための保険です。

### 書き込む Intent はアプリ本体に固定して、読み取りは委ねる

この二重登録、しばらくは「実行プロセスがヒューリスティクスで決まる以上、両方に登録しておくしかない」という消極的な理由で置いていました。今は理由が変わっていて、**登録が 2 つあるのは役割が違うから** という形になっています。

きっかけはセッション 345 (16:30) を読み直したことで、そこで挙げられている動機がこのアプリの構成そのままでした。曰く「ウィジェットはアプリとデータモデルを共有しているが、2 つのプロセスが同じストアに書くと衝突しうるので、ウィジェットには読み取り専用のアクセスを与えて、書き込みは全部メインアプリに任せた」。IntentTodo も共有パッケージが Widget Extension にリンクされていて、`WidgetBundle.init()` で **読み書きできる `TodoService`** を登録していたので、アプリ未起動時に変更系 Intent が Extension へ振られると、そこが SwiftData の書き手になり得ました。3/N や 4/N で書く「マイグレーションはアプリ本体に寄せる」と同じ危うさです。

なので方針を **「`TodoService` の変更メソッドを呼ぶ Intent はすべて `allowedExecutionTargets = [.main]`、読み取り系は未指定のまま」** に決めました。現時点で固定したのは 13 個です。

```swift
public struct ToggleTodoCompletionIntent: UndoableIntent {
    public static var supportedModes: IntentModes { .background }

    /// 書き込み系。Extension プロセスが SwiftData を書かないようアプリ本体に固定する。
    /// iOS では `LiveActivityIntent` 準拠で実質アプリ実行だが、
    /// macOS / watchOS にはその保証が無いので型で明示する。
    public static var allowedExecutionTargets: IntentExecutionTargets { [.main] }
    // ...
}
```

読み取り系 (件数を返す / 集計を返す / 検索する) は **あえて固定していません**。Extension で応答できた方がアプリを起こさずに済んで速いからです。というわけで `WidgetBundle.init()` の `TodoService` 登録は残るんですが、用途が「読み取り専用の利用」に変わりました。二重登録は畳めないのではなくて、**役割が分かれた** という整理です。

宣言漏れは静かに壊れる (Extension で書けてしまうだけで、エラーは出ない) ので、テストで縛っています。①13 個の `allowedExecutionTargets == [.main]` を個別に assert、②読み取り系が `.default` のままか、③`Intents/` のソースを走査して「`todoService` の変更メソッドを呼ぶのに `allowedExecutionTargets` を宣言していないファイル」を検出、の 3 本立てです。③ は 5/N に書いた「条件付き assert で空回りしていた UI テスト」の反省があるので、わざと違反する probe intent を置いて **実際に落ちることを確認** してから入れました。

ちなみに `ExecutionTargets` は `AppIntent` だけでなく **`EntityQuery` 側にも生えています** (公式が "available on both `AppIntent` and `EntityQuery`" と書いています)。IntentTodo の entity 解決は読み取りしかしないので、こちらは未指定のままにしています。

## defer 集約の効果

`defer { Self.dataDidChange() }` を TodoService の各 mutation メソッドに置く設計、見た目は地味ですが、後から振り返るとだいぶ効いている部分です。

- mutation を増やすたびに後処理を書き忘れる、というクラスのバグがそもそも発生しない
- 「データ変更 → Widget 反映」という不変条件をコードの構造そのもので表現できる
- レビュー時に「Widget 更新の呼び忘れがないか」を確認する手間が消える

ただし注意点もあります。`defer` は throws しても発火するので、置く位置を間違えると validation エラー (空タイトルなど) で create が失敗したときにも reloadAllWidgets が走ってしまいます。
「変更が無いのに reload するのは無駄」なので、`create` では `defer` を **validation guard の後ろ** に置いて、空タイトルで弾かれたケースでは reload が走らないようにしました。

```swift
public func create(...) throws -> TodoAppEntity {
    let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else {
        throw IntentError.validation("Todo title cannot be empty")
    }
    defer { Self.dataDidChange() }   // ← guard の後ろに置く
    // ... persist ...
}
```

逆に `delete` は、あえて `defer` を unconditional に置いています。
Spotlight の deindex はそもそも idempotent だし、CloudKit の merge で既に消えていて `repository.delete` が throw したケースでも、ローカルの index と Widget は更新しておく方が整合が取れるからです。
「`defer` に何を入れるか」は副作用の冪等性しだいで変わる、というのが書いてみて分かったところでした。

### 集約点は 1 つでも、中身は育つ

この `dataDidChange()`、最初は `WidgetReloader.reloadAllWidgets()` 1 行だったんですが、今は 2 つになっています。

```swift
private static func dataDidChange() {
    WidgetReloader.reloadAllWidgets()
    AppShortcutParameterUpdater.notifyEntitiesChanged()
}
```

2 行目は App Shortcut のパラメータ候補をシステムに取り直させるためのものです。App Shortcut のフレーズに Intent のパラメータを埋める (`"Complete \(\.$todo) in IntentTodo"` みたいな形) と、システムは候補を `suggestedEntities()` から取ってくるんですが、**`updateAppShortcutParameters()` を呼んで「変わった」と伝えないと候補が古いまま** で、フレーズが一致しなくなります。呼ぶタイミングは「entity の追加 / 削除 / 表示名の変化」と、それに **アプリの初回起動時** です (セッション 10102 の 9:24〜9:52。初回については「一度もフェッチされていないとパラメータ入りフレーズは機能しない」と明言されています)。

ここで 1 つ構造的な面倒があって、`updateAppShortcutParameters()` は `AppShortcutsProvider` の **具体型に対する static メソッド** です。そしてその具体型は 3/N で書くとおりアプリターゲットにしか置けません。パッケージ側から呼びようがないので、`AppShortcutParameterUpdater` というクロージャ受けの間接層を挟んで、アプリ起動時に `{ TodoAppShortcuts.updateAppShortcutParameters() }` を登録してもらう形にしました。

言いたかったのは、**呼び忘れを構造で防ぐ集約点を作っておくと、後から足すものが 1 箇所で済む** ということです。逆に集約点が無いまま「変更系メソッド 9 箇所に 2 行ずつ足す」をやっていたら、たぶんどこかを取りこぼしていました。5/N には集約先の中身が片肺だった (ウィジェットはリロードしていたのにコントロールはしていなかった) という失敗も書いていて、集約点があること自体は正しいんだけど、中身が正しいかは別途見ないといけない、というのが今の実感です。

## ファクトリで「Repository を知らない」 caller を作る

最後に `TodoService.swiftDataBacked(container:)` ファクトリの話。

```swift
public extension TodoService {
    @MainActor
    static func swiftDataBacked(container: ModelContainer) -> TodoService {
        TodoService(repository: SwiftDataTodoRepository(modelContext: container.mainContext))
    }
}
```

何が嬉しいかというと、Widget Extension target は `Repository` パッケージを直接依存に持たなくても、`TodoAppIntents` だけを import すれば `TodoService.swiftDataBacked(container:)` で TodoService を組み立てられるようになります。

これによって、pbxproj 側の package product dependencies を増やさずに、TodoService の差し替えやテスト用の差し替えも将来的に追加しやすくなりました。

## まとめ

- `TodoActions` enum + static func から `TodoService` クラスへ昇格させると、Repository の都度生成 / Widget reload の呼び忘れリスク / View からの利用経路の 3 つを同時に解消できる
- `@Dependency` で Intent に注入する。`AppDependencyManager` への登録は **プロセスごと** に必要。`.background` の実行プロセスは未指定ならヒューリスティクスで決まる
- **SwiftData を書き換える Intent は `allowedExecutionTargets = [.main]` でアプリ本体に固定**、読み取り系は未指定のまま Extension に応答させる。Widget 側の登録は「読み取り専用の利用」として残る
- mutation には `defer { Self.dataDidChange() }` で副作用を集約すると、呼び忘れバグがコンパイル時に消せる。集約点があると、後から足す後処理 (App Shortcut のパラメータ更新) も 1 箇所で済む
- `swiftDataBacked(container:)` のような薄いファクトリを置くと、consumer 側のターゲット依存を最小化できる

次回は、[Extension target を SPM パッケージ化してマルチプラットフォーム対応を進めた話 (3/N)](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-28**: 書き込み系 13 Intent を `allowedExecutionTargets = [.main]` に固定した方針を反映。二重登録の説明を「畳めない」から「役割が分かれた (Widget 側は読み取り専用)」へ書き換え。`defer` の集約先が `dataDidChange()` に育った話 (App Shortcut のパラメータ更新) を追加
- **2026-08-12**: Primary / FromExtension 分離が撤去されたことに追随 (5/N 参照)
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-11**: 実行プロセスの表を訂正。`.background` を「必ず Widget Extension で実行」と固定的に書いていたが、実際は未指定ならヒューリスティクスで決まり、固定するには `allowedExecutionTargets` が要る。Live Activity の行も「Live Activity Extension で実行」から「`perform()` はメインアプリ (公式保証)」に訂正

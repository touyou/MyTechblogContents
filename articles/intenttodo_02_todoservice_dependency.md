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

Primary / FromExtension の 2 系統 Intent (詳細は本シリーズ 5/N) が同じビジネスロジックを呼ぶので、共通化が必要でした。
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
        defer { WidgetReloader.reloadAllWidgets() }
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
2. **`defer { WidgetReloader.reloadAllWidgets() }`**: mutation 系メソッドの末尾で必ず Widget reload が走る。Intent 側で呼び忘れる心配がなくなる

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
        let container = try! SharedModelContainer.createContainer()
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
| Widget `Button` / Control Widget | `.background` | **Widget Extension** | `WidgetBundle.init()` |
| Live Activity ボタン | `LiveActivityIntent` | **Live Activity Extension** | Extension 側 |
| watchOS の Button(intent:) | 全モード | **watchOS App** | watchApp の `App.init()` |

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

## defer 集約の効果

`defer { WidgetReloader.reloadAllWidgets() }` を TodoService の各 mutation メソッドに置く設計、見た目は地味ですが、後から振り返るとだいぶ効いている部分です。

- mutation を増やすたびに `WidgetReloader.reloadAllWidgets()` を書き忘れる、というクラスのバグがそもそも発生しない
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
    defer { WidgetReloader.reloadAllWidgets() }   // ← guard の後ろに置く
    // ... persist ...
}
```

逆に `delete` は、あえて `defer` を unconditional に置いています。
Spotlight の deindex はそもそも idempotent だし、CloudKit の merge で既に消えていて `repository.delete` が throw したケースでも、ローカルの index と Widget は更新しておく方が整合が取れるからです。
「`defer` に何を入れるか」は副作用の冪等性しだいで変わる、というのが書いてみて分かったところでした。

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
- `@Dependency` で Intent に注入する。`AppDependencyManager` への登録は **プロセスごと** に必要
- mutation には `defer { WidgetReloader.reloadAllWidgets() }` で副作用を集約すると、呼び忘れバグがコンパイル時に消せる
- `swiftDataBacked(container:)` のような薄いファクトリを置くと、consumer 側のターゲット依存を最小化できる

次回は、[Extension target を SPM パッケージ化してマルチプラットフォーム対応を進めた話 (3/N)](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions) を書きます。

---
title: "WWDC 2026: 大量処理・実行制御と「自分のアプリには適合しない API」の見極め (9/N)"
emoji: "📊"
type: "tech"
topics: ["AppIntents", "Swift", "iOS", "WWDC2026"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 9 回目です。
WWDC 2026 編の 4 本目で、`xcode27` ブランチでの検証です (前提は 6/N 冒頭)。

今回は 2 つの軸があります。
前半は「大量の Todo を一括処理する」ための実行制御系 API (`EntityCollection` / `LongRunningIntent` / `CancellableIntent` / `allowedExecutionTargets`) と `@UnionValue`。
後半は逆に、**検証してみたら自分のアプリには適合しなかった `RelevantEntities`** の話です。
個人的には、今回みたいに「使えなかった / 統合できなかった」という結論こそ、Apple のドキュメントには載らない情報で価値があると思っているので、その辺を厚めに書きます。

## 大量の Todo を一括で完了する

「選択した Todo を全部完了する」みたいなバルク操作を、WWDC 2026 (#345) の API で素直に書けるようになりました。
`CompleteTodosIntent` という 1 つの Intent で `EntityCollection` / `LongRunningIntent` / `CancellableIntent` の 3 つを同時に試しました。

```swift
public struct CompleteTodosIntent: LongRunningIntent, CancellableIntent {
    public static var supportedModes: IntentModes { .background }
    public static var allowedExecutionTargets: IntentExecutionTargets { [.main] }

    @Parameter(title: "Todos", description: "The todos to complete")
    public var todos: EntityCollection<TodoAppEntity>

    @Dependency
    var todoService: TodoService

    public func perform() async throws -> some IntentResult & ProvidesDialog {
        let ids = todos.identifiers   // ← entity を解決せず id だけ取る
        let total = ids.count

        let completed = try await performBackgroundTask {
            progress.totalUnitCount = Int64(total)
            progress.localizedDescription = "Completing todos"
            var done = 0
            for id in ids {
                try Task.checkCancellation()
                try await todoService.markCompleted(todoId: id)
                done += 1
                progress.completedUnitCount = Int64(done)
            }
            return done
        } onCancel: { reason in
            logger.notice("CompleteTodosIntent cancelled: \(String(describing: reason))")
        }

        let noun = completed == 1 ? "todo" : "todos"
        return .result(dialog: IntentDialog("Completed \(completed) \(noun)."))
    }
}
```

順番に分解します。

### EntityCollection で「解決しない」

`@Parameter` の型を `EntityCollection<TodoAppEntity>` にすると、**パラメータ解決のときに各 id を full entity へ解決しません**。
数百件を相手にするとき、全部 `TodoAppEntity` に hydrate するのはメモリも時間ももったいないので、これは効きます。

`.identifiers` で id (`[String]`) だけ取り出せて、完全な entity が要るときだけ `resolvedEntities()` を呼ぶ、という設計です。
完了処理は id さえあればできるので、今回は **entity 解決を完全に回避** できました。

### LongRunningIntent で時間を延ばす

バックグラウンド実行には 30 秒制限があるんですが、`LongRunningIntent` に適合して `performBackgroundTask { ... }` で囲むと、その制限を延長できます。

ただし注意点があって、**`progress` を定期的に更新しないとシステムが延長を打ち切ります**。
`progress.totalUnitCount` / `completedUnitCount` をループの中で逐次更新する必要があります。これをサボると、長い処理の途中で勝手に止められる、ということになりそうです。

### CancellableIntent で途中で止める

`CancellableIntent` に適合すると、`performBackgroundTask(operation:onCancel:)` で `onCancel: (IntentCancellationReason) -> Void` を渡せます。
ループの中で `try Task.checkCancellation()` を呼んでおくと、キャンセルされたときにそこで抜けてくれます。

### 並行性: perform を @MainActor にしない

ここが地味にハマるポイントでした。
`operation` クロージャは nonisolated な async なので、`perform()` 全体を `@MainActor` にする必要はありません。
SwiftData の変更は MainActor でやりたいわけですが、クロージャの中から `try await todoService.markCompleted(...)` と **await で呼べば MainActor にホップ** してくれるので、変更は安全に動きます。
「全部 MainActor に閉じる」のではなく「必要なところだけホップする」方が、バックグラウンドの長時間処理とは相性がいいなと思いました。

## 実行プロセスを固定する: allowedExecutionTargets

`allowedExecutionTargets` で、Intent をどのプロセスで実行するかを限定できます (#345)。

```swift
public static var allowedExecutionTargets: IntentExecutionTargets { [.main] }
```

選べるのは **`.main` (アプリ本体) と `.appIntentsExtension` (App Intents Extension)** だけです。
IntentTodo は App Intents Extension を持っていないし、バルクの SwiftData 変更はアプリ本体でやるのが一番確実なので、新設のバルク Intent は `[.main]` に固定しました。

### ⚠️ FromExtension 分離を統合できるか試して、無理だった

ここで自分は「もしかして `allowedExecutionTargets` を使えば、本編 5/N で書いた **Primary / FromExtension の 2 系統** を 1 つに畳めるんじゃないか?」と期待しました。
結論から言うと **できませんでした**。理由はこうです。

- FromExtension (`todoId: String`) と Primary (`todo: TodoAppEntity`) を分けているのは、**Live Activity Extension プロセスでの entity 解決クラッシュを避ける** ためでした。パラメータの「型」を変えることで、解決そのものを踏まないようにしている。
- 一方 `allowedExecutionTargets` が制御するのは **どのプロセスが perform するか** であって、entity 解決の有無ではありません。狙っているレイヤーが違う。
- しかも選択肢が `.main` / `.appIntentsExtension` だけで、そもそも **Widget / Live Activity Extension は対象外** です。
- Live Activity ボタン用の変種は `LiveActivityIntent` (Apple 保証でアプリプロセス実行) ですが、クラッシュはパラメータ解決の段で起きるので、解決を経由しない String 版が依然として必要。

というわけで、**FromExtension 分離はそのまま維持** することにしました。
新しい API が出ると「これで前の workaround を畳めるかも」とつい期待するんですが、解決している問題のレイヤーが違うと畳めない、というのを確認できたのは収穫でした。期待して、試して、畳めないと分かる、というのも 1 つの検証だと思っています。

## 複数の型を1つの結果で返す: @UnionValue

`@UnionValue` を enum に付けると、`@Parameter` や `ReturnsValue` で **複数の Entity 型を 1 つの値として扱える** ようになります。
IntentTodo では「Todo とカテゴリの混在検索結果」を返すのに使いました。

```swift
@UnionValue
public enum TodoOrCategory: Sendable {   // ← public enum は Sendable を明示する
    case todo(TodoAppEntity)
    case category(CategoryAppEntity)
}
```

ここで 1 つ落とし穴がありました。
`public enum` に `@UnionValue` を付けると、マクロ生成コードが `Sendable` を要求します。Swift は public 型の `Sendable` を自動推論しないので、**`: Sendable` を明示しない** と「Type '...' does not conform to the 'Sendable' protocol」というエラーが (自分が書いていない生成ソースの中で) 出てビルドが落ちます。
マクロが吐いたコードでエラーが出るので、最初は何が悪いのか分かりにくかったです。

これを使って、`SearchEverythingIntent` が Todo とカテゴリを混ぜて返します。

```swift
public func perform() async throws -> some IntentResult & ReturnsValue<[TodoOrCategory]> {
    // ... 名前一致で todos と categories を集めて ...
    let matchedTodos = todos.filter { ... }.map { TodoOrCategory.todo($0) }
    let matchedCategories = todos.compactMap(\.category).filter { ... }.map { TodoOrCategory.category($0) }
    return .result(value: matchedTodos + matchedCategories)
}
```

`EntityQuery` は単一の Entity 型に縛られますが、`@UnionValue` を返り値に使うと **複数種類を 1 つの結果リストに混ぜられる** のが利点です。これは次回 (10/N) の Visual Intelligence でもそのまま再利用できました。

## 検証してみたら「使えなかった」API: RelevantEntities

ここからが今回いちばん書きたかった話です。
`RelevantEntities` は「いま関連性の高い Entity」をシステムに文脈寄付するための API で、自分は「次の期限 / 緊急の Todo」を寄付して、ロック画面やシステムの提案に出せたらいいなと考えていました。
`RelevantEntities.shared.updateEntities(_:for:)` を使う想定で調べていったんですが、ここで詰まりました。

`updateEntities(_:for:)` の第二引数は `AppEntityContext` で、これが **ドメイン固有のファクトリしか持っていない** ことが分かりました。

- 提供される context は `.audio(.nowPlaying)` (`AudioContext`) と、framework overlay (HealthKit など) が定義する domain context だけ。
- **汎用 / reminders / todo 向けの context 値が存在しない** んです。
- かといって `.audio(.nowPlaying)` で Todo を寄付するのは意味的に間違っています (Todo が再生中メディア扱いになる)。

つまり、**reminders ドメインのアプリでは `RelevantEntities` は現状そもそも適合できない** という結論になりました。
Apple が todo / reminders 向けの `AppEntityContext` を追加してくれるまでは保留です。
(名前が似ている `RelevantIntent` / `RelevantIntentManager` は WidgetConfigurationIntent ベースのウィジェット提案で、別軸の API です。文脈提案がどうしても必要になったら、そっちを検討することになりそうです。)

これは「実装をミスった」のではなく「**API の設計上、自分のドメインには口が用意されていない**」という種類の壁で、ドキュメントを上から読んでいるだけだと「使えそう」に見えてしまうやつでした。
実際に適合させようと手を動かして初めて、context の選択肢が音楽再生などに限定されていると分かったので、こういうのこそ記録に残す価値があるなと思っています。

## 検証できた深さ

今回は以下です。

- **ビルド成立 (型レベル)**: `EntityCollection` / `LongRunningIntent` / `CancellableIntent` / `allowedExecutionTargets` / `@UnionValue` は OK。
- **単体**: バルク完了の id ベース処理は確認済み。
- **`RelevantEntities`**: 適合不能と結論 (型レベルで口が無い、という結論)。
- **実機 (大量件数での progress 表示やキャンセル挙動、Siri からのバルク実行)**: 未確認。件数を盛って progress が効くかは端末で見たいので、できたら追記します。

## まとめ

- `EntityCollection<T>` は `.identifiers` で id だけ取れて entity 解決を回避できる。バルク処理で効く
- `LongRunningIntent` は `performBackgroundTask` で時間を延ばせるが、`progress` を更新し続けないと打ち切られる
- `CancellableIntent` は `onCancel:` + ループ内 `try Task.checkCancellation()`。perform は `@MainActor` にせず、必要なところだけ await でホップする
- `allowedExecutionTargets` は `.main` / `.appIntentsExtension` のみ。**FromExtension 分離は解決レイヤーが違うので統合できない** と確認 (期待して試して畳めなかった)
- `@UnionValue` で複数 Entity 型を 1 つの結果に混ぜられる。`public enum` は `: Sendable` 明示が必要
- `RelevantEntities` は **reminders ドメイン向けの `AppEntityContext` が存在せず適合不能**。実装ミスではなく API 設計上の壁。保留

次回は WWDC 2026 編の最後として、[Visual Intelligence 連携 (`IntentValueQuery` / `SemanticContentDescriptor`) と、AppIntentsTesting で Intent を実経路テストした話 (10/N)](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing) を書きます。

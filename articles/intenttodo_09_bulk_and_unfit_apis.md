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
WWDC 2026 編の 4 本目です (前提は 6/N 冒頭)。

今回は 2 つの軸があります。
前半は「大量の Todo を一括処理する」ための実行制御系 API (`EntityCollection` / `LongRunningIntent` / `CancellableIntent` / `allowedExecutionTargets`) と `@UnionValue`。
後半は逆に、**検証してみたら自分のアプリには適合しなかった `RelevantEntities`** の話です。
個人的には、今回みたいに「使えなかった / 統合できなかった」という結論こそ、Apple のドキュメントには載らない情報で価値があると思っているので、その辺を厚めに書きます。

## 大量の Todo を一括で完了する

「選択した Todo を全部完了する」みたいなバルク操作を、WWDC 2026 (セッション 345) の API で素直に書けるようになりました。
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

あとから「そもそも `ProgressReportingIntent` を使っていないな」と思って調べたら、SDK が `LongRunningIntent: ProgressReportingIntent` になっていて **すでに採用済み** でした。未実装の種別ではなかった、というオチです。ただ見直したこと自体は無駄ではなくて、進捗の更新・キャンセルの観測・件数の複数形という 3 つの契約をソースで押さえるテストを足せたのと、上のコードで手書きしていた `completed == 1 ? "todo" : "todos"` を `^[\(completed) todo](inflect: true)` に直せました (6/N に書いた inflection です)。

### CancellableIntent で途中で止める

`CancellableIntent` に適合すると、`performBackgroundTask(operation:onCancel:)` で `onCancel: (IntentCancellationReason) -> Void` を渡せます。
ループの中で `try Task.checkCancellation()` を呼んでおくと、キャンセルされたときにそこで抜けてくれます。

### 並行性: perform を @MainActor にしない

ここが地味にハマるポイントでした。
`operation` クロージャは nonisolated な async なので、`perform()` 全体を `@MainActor` にする必要はありません。
SwiftData の変更は MainActor でやりたいわけですが、クロージャの中から `try await todoService.markCompleted(...)` と **await で呼べば MainActor にホップ** してくれるので、変更は安全に動きます。
「全部 MainActor に閉じる」のではなく「必要なところだけホップする」方が、バックグラウンドの長時間処理とは相性がいいなと思いました。

## 実行プロセスを固定する: allowedExecutionTargets

`allowedExecutionTargets` で、Intent をどのプロセスで実行するかを限定できます (セッション 345)。

```swift
public static var allowedExecutionTargets: IntentExecutionTargets { [.main] }
```

選べるのは **`.main` (アプリ本体) / `.appIntentsExtension` (App Intents Extension) / `.widgetKitExtension` (WidgetKit Extension)** です。
IntentTodo は App Intents Extension を持っていないし、バルクの SwiftData 変更はアプリ本体でやるのが一番確実なので、新設のバルク Intent は `[.main]` に固定しました。

### 1 件だけ試して満足していたのを、方針に格上げした

しばらくはこの `CompleteTodosIntent` 1 件だけに付けた状態で止まっていて、「API を通した」以上のことをしていませんでした。あとでセッション 345 (16:30) を読み直したら、そこで挙げられている動機が **このアプリの構成そのもの** だったので、方針として引き直しています。

> My widget shares the data model with the app — but having two processes write to the same data store can cause conflicts. So I gave the widget read-only access and the main app handles all the writes.

IntentTodo も共有パッケージが Widget Extension にリンクされていて、そこで読み書きできる `TodoService` を登録しているので、未指定のままだと **アプリ未起動時に Extension プロセスが同じストアの書き手になり得ます**。3/N や 4/N で書いた「マイグレーションはアプリ本体に寄せる」と同じ危うさです。

なので **「`TodoService` の変更メソッドを呼ぶ Intent はすべて `[.main]`、読み取り系は未指定」** に統一しました。現時点で 13 個です。読み取り系をあえて固定しないのは、Extension で応答できた方がアプリを起こさずに済んで速いからで、Widget 側の依存登録も「読み取り専用の利用」として残っています。詳しくは 2/N に書きました。

宣言漏れは静かに壊れる (Extension で書けてしまうだけでエラーは出ない) ので、`Intents/` のソースを走査して「変更メソッドを呼ぶのに `allowedExecutionTargets` を宣言していないファイル」を検出するテストを足しました。わざと違反する probe intent を置いて、**実際に落ちることを確認してから** 入れています。

ちなみに `ExecutionTargets` は `AppIntent` だけでなく **`EntityQuery` 側にも生えています** (公式が "available on both `AppIntent` and `EntityQuery`" と書いています)。IntentTodo の entity 解決は読み取りしかしないので、こちらは未指定のままです。

では **指定しなかったとき** はどうなるかというと、これが「呼出元に応じて固定的に決まる」ではありませんでした。セッション 345 (15:59〜16:55) によると、未指定の Intent は **システムのヒューリスティクス** でプロセスが選ばれます (アプリが起動中ならアプリを優先、そうでなければ Extension を起こす)。SDK 側でも `IntentExecutionTargets` は `.default` を独立したケースに持つ `OptionSet` になっていて、「既定はシステムに委ねる」が型としてそう表現されていました。2/N の実行プロセスの表もこれを前提に書いています。

### FromExtension 分離をこれで畳めるか? → 「畳めない」で確定

ここで自分は「もしかして `allowedExecutionTargets` を使えば、本編 5/N で書いた **Primary / FromExtension の 2 系統** を 1 つに畳めるんじゃないか?」と期待しました。結論から言うと **畳めません**でした。

決め手は、`allowedExecutionTargets` が制御するのはあくまで **どのプロセスが `perform()` するか** で、クラッシュが起きる **パラメータ解決 (entity resolution) を経由するかどうか** は変えられない、という点です。FromExtension (`todoId: String`) と Primary (`todo: TodoAppEntity`) を分けているのは、パラメータの「型」を変えて解決そのものを踏まないようにするためなので、実行先を動かしても解決は解決として走ります。`.widgetKitExtension` の存在を踏まえても、Live Activity Extension はそもそも指定対象に入っていません。LA のボタン用には `LiveActivityIntent` (アプリプロセスでの実行が保証されるプロトコル) もあるんですが、クラッシュは perform より手前の解決段で起きるので、解決そのものを踏まない String 版が結局必要でした。というわけで FromExtension は維持です。

新しい API が出ると「これで前の workaround を畳めるかも」とつい期待するんですが、この宿題については逆に **ちゃんと裏を取らずに一度「畳めない」と思い込んでいた** 時期もあって (`.widgetKitExtension` の存在を見落としていました)、期待する方向にも決めつける方向にも転びうるんだなというのは教訓でした。

### 分離そのものが要らなくなった

この「畳めない」という結論、**前提の方が消えました**。Live Activity のボタン経由でも entity の事前解決はメインアプリプロセスで走ってクラッシュしない、と実機で確かめられたので、そもそも分ける理由が無くなっています。FromExtension 分離は撤去して 1 アクション 1 Intent に統一しました (経緯は [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls))。

なので `allowedExecutionTargets` については「FromExtension を畳む道具にはならない」という結論だけが残ります。制御できるのは perform のプロセスであって entity 解決を踏むかどうかではない、という整理自体は変わりません。畳めたのは別の理由からだった、という格好です。

ここは自分としてはちょっと面白くて、**「この API で workaround を畳めるか」を延々考えていたけれど、答えは「workaround がもう要らない」だった** わけです。道具の側で解決しようとすると、前提が生きているかどうかを疑う機会を逃すんだなと思いました。

この「Widget / Extension からの操作はどう扱うべきか」については、WWDC 2026 のセッション 277 が WidgetKit の実行モデルを明文化していました。**ウィジェットのビューはアーカイブ済みで任意コードは走らせられない / ユーザー操作は App Intent で表現する / アプリを開くだけなら `Link` を使う**、という整理です。IntentTodo はもともと「ボタン操作は `Button(intent:)`、アプリ起動は `Link(destination:)`」という方針で書いていて、これが当時は「動作検証が必要」くらいの歯切れの悪さだったんですが、今回 **公式に正しい設計だった** と裏が取れた格好です。「ウィジェット側で entity 解決のような重い処理を踏ませない」という分離の動機自体も、この実行モデルと整合しているなと思いました。

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

セッションを洗い直したら、`@UnionValue` マクロ自体は WWDC 2024 (iOS 18、セッション 10134) からあるものでした。この記事が扱っている 345 は、`typeDisplayRepresentation` / `caseDisplayRepresentations` の実装要件を提示した回です。実際ハマったのがその細目の方だったので、体感として新機能に見えていたんだと思います。なお上に書いた `public enum` の `: Sendable` 明示は 345 で言われていることではなくて、**自分がビルドを通そうとして踏んだだけ** の話なので、そこは分けて読んでもらえればと思います。

## 検証してみたら「使えなかった」API: RelevantEntities

ここからが今回いちばん書きたかった話です。
`RelevantEntities` は「いま関連性の高い Entity」をシステムに文脈寄付するための API で、自分は「次の期限 / 緊急の Todo」を寄付して、ロック画面やシステムの提案に出せたらいいなと考えていました。
`RelevantEntities.shared.updateEntities(_:for:)` を使う想定で調べていったんですが、ここで詰まりました。

`updateEntities(_:for:)` の第二引数は `AppEntityContext` で、これが **ドメイン固有のファクトリしか持っていない** ことが分かりました。

- 提供される context は `.audio(.nowPlaying)` や `.audio(.workout(activityType:))` のような `AudioContext` と、framework overlay (HealthKit など) が定義する domain context だけ。WWDC 2026 (セッション 345) のサンプルも「ランニング開始時にランニング用プレイリストを提案」と、やはり audio ドメインの文脈でした。
- **汎用 / reminders / todo 向けの context 値が存在しない** んです。
- かといって `.audio(.nowPlaying)` で Todo を寄付するのは意味的に間違っています (Todo が再生中メディア扱いになる)。

つまり、**reminders ドメインのアプリでは `RelevantEntities` は現状そもそも適合できない** という結論になりました。
Apple が todo / reminders 向けの `AppEntityContext` を追加してくれるまでは保留です。
(名前が似ている `RelevantIntent` / `RelevantIntentManager` は WidgetConfigurationIntent ベースのウィジェット提案で、別軸の API です。文脈提案がどうしても必要になったら、そっちを検討することになりそうです。)

これは「実装をミスった」のではなく「**API の設計上、自分のドメインには口が用意されていない**」という種類の壁で、ドキュメントを上から読んでいるだけだと「使えそう」に見えてしまうやつでした。
実際に適合させようと手を動かして初めて、context の選択肢が音楽再生などに限定されていると分かったので、こういうのこそ記録に残す価値があるなと思っています。

セッション 345 を洗い直したときに、iOS 27 で `RelevantEntities.shared.removeAllEntities(for:)` / `removeEntities(_:from:)` / `removeAllEntities()` という **寄付を取り消す側** の API が増えているのを見つけました。ただ、上に書いたとおり寄付する側の context が無い以上、消す側だけ増えても出番はやっぱり無いので、結論は据え置きのままです。`AppEntityContext` の方も 345 で `.audio(.workout(activityType:))` のような拡張が入ったんですが、増えたのは audio ドメインの中身で、reminders / todo 向けの口が開いたわけではありませんでした。

## 「使えるけど使わない」を決めた API の棚卸し

`RelevantEntities` は「使いたくても口が無い」でしたが、逆に **使えるけど入れない** と決めたものもいくつかあります。判断の記録として並べておきます。

### `.foreground(.dynamic)`: 当て先が無かった

「背景で走らせて、必要になったら前面に引き上げる」という `.foreground(.dynamic)` + `continueInForeground` は、一度 `ShowTodosIntent` に入れて revert しました。`OpensIntent` と両立しないのが理由です。`OpensIntent` は返り値の型に現れるので「条件によっては開かない」を表現できず、dynamic を使うなら Intent 合成 (`ShowTodosIntent` → `LaunchAppIntent`) を外して `NavigationModel` を直に叩く形にするしかありません。

そのときは「dynamic 自体は有用なので、もっと適した Intent が出てきたら検討する」と宿題にしていたんですが、全 21 Intent の `supportedModes` と対話手段を一覧にして見直したら、**そういう Intent が無い** という結論になりました。

| やりたいこと | 使っている手段 |
|------------|--------------|
| アプリの該当画面へ送る | `OpensIntent` + `LaunchAppIntent` (`.foreground(.immediate)`) の Intent 合成 |
| 実行中に選ばせる / 確認を取る | `requestChoice` / `requestConfirmation` (8/N) |
| 結果を読ませる / 見せる | `IntentDialog(full:supporting:)` + `snippetIntent:` |
| 時間のかかる一括処理 | `LongRunningIntent` + `CancellableIntent` (この記事) |

残るのは「背景で始めて、途中で前面が必要になる」形ですが、Todo の CRUD はパラメータが揃っていれば背景で完結するし、揃わないときはパラメータ解決や `requestChoice` が拾います。当て先ができるのは「途中でカメラや地図みたいな別 UI を出さないと完了できない操作」が生えたときだな、という条件だけ書き残して閉じました。**API を使うこと自体を目的にしないための歯止め** のつもりです。

### `EntityPropertyQuery`: `EnumerableEntityQuery` で足りていた

これは前に「既存の `EntityStringQuery` で足りているから」という理由で不採用にしていたんですが、理由の方が正確ではありませんでした。正しくは **`TodoEntityQuery` が `EnumerableEntityQuery` に適合しているので、Shortcuts の Find アクションと絞り込みが自動生成される** からです (公式が "By implementing an `EnumerableEntityQuery`, you enable the Shortcuts app to generate a Find action and do filtering automatically" と書いています)。

`EntityPropertyQuery` が要るのは "many thousands of entities" 規模で全件ロードが重くなったときで、個人利用の Todo 件数では出番がありません。件数が増えたらここを再評価する、という条件付きの不採用です。

### そもそも対象外だったもの

- **`AudioPlaybackIntent`**: 再生機能が無い
- **`CustomIntentMigratedAppIntent`**: 移行元の SiriKit 資産が無い
- **`LiveActivityStartingIntent`**: iOS 17 で deprecated で、`LiveActivityIntent` が後継
- **`PredictableIntent`**: 8/N に書いたとおり寄付がゼロなので、そもそも提案が出ない

`PredictableIntent` だけは「入れられない」ではなく「別の判断の結果として使えない」なので、寄付を再訪するときに一緒に戻ってくる予定です。

### `SpotlightSearchTool`: 前提は揃ったけどスコープの外

WWDC 2026 のセッション 246 で出てきた `SpotlightSearchTool` (自分の Todo に対する会話型検索) は、前提になる「Spotlight への entity 寄付」が 5/N と 6/N で揃っているので、あと一歩ではありました。ただ残りの作業は `LanguageModelSession` と tool 登録、それに結果表示の UI で、**主体が FoundationModels 側に移ります**。このリポジトリで示したいのは「App Intents を設計の中心に据えるとどう組み立てられるか」なので、ここから先は別題材だなと思って外しました。99/N に書いた FoundationModels をやらない判断と同じ線引きです。

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
- `allowedExecutionTargets` は `.main` / `.appIntentsExtension` / `.widgetKitExtension` の 3 つ。未指定なら実行プロセスはヒューリスティクスで決まる。**FromExtension 分離はこれでは畳めなかった** — 制御できるのは perform のプロセスであって entity 解決を踏むかどうかではないため (分離自体は後日、クラッシュが再現しないと分かって撤去しました)
- 1 件だけ付けて止まっていた `allowedExecutionTargets` は、**書き込み系は全部 `[.main]` / 読み取り系は未指定** という方針に格上げした。宣言漏れはソース走査のテストで検出する
- 「使えるけど入れない」も判断として残す。`.foreground(.dynamic)` は当て先が無い、`EntityPropertyQuery` は `EnumerableEntityQuery` で足りている、`PredictableIntent` は寄付ゼロだと動かない
- `@UnionValue` で複数 Entity 型を 1 つの結果に混ぜられる。`public enum` は `: Sendable` 明示が必要
- `RelevantEntities` は **reminders ドメイン向けの `AppEntityContext` が存在せず適合不能**。実装ミスではなく API 設計上の壁。保留

次回は WWDC 2026 編の最後として、[Visual Intelligence 連携 (`IntentValueQuery` / `SemanticContentDescriptor`) と、AppIntentsTesting で Intent を実経路テストした話 (10/N)](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-28**: `allowedExecutionTargets` を「書き込み系は全部 `[.main]`」という方針に格上げした話を追加。「使えるけど使わないと決めた API」の棚卸し (`.foreground(.dynamic)` / `EntityPropertyQuery` / `PredictableIntent` / `SpotlightSearchTool` ほか) を追加。`ProgressReportingIntent` は `LongRunningIntent` 経由ですでに採用済みだったことを反映
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: FromExtension 分離そのものが不要になった (LA 経由でもクラッシュしないと実測) ことを追記。`allowedExecutionTargets` で畳めないという結論自体は不変
- **2026-08-11**: `allowedExecutionTargets` を未指定にしたときの挙動 (ヒューリスティクス) を追記。「Live Activity Extension プロセスでの entity 解決クラッシュ」という原因断定を取り下げ (結論の「畳めない」は不変)。`public enum` の `: Sendable` 明示をセッション 345 の内容として書いていたのを、手元のビルド観測だと明記
- **2026-08-05**: `@UnionValue` の出自を WWDC 2024 (セッション 10134) と訂正。`RelevantEntities` の取り消し系 API と `AppEntityContext` の拡張を確認 (結論は据え置き)
- **2026-07-02**: FromExtension 分離を `allowedExecutionTargets` で畳めるかの宿題を「畳めない」で確定
- **2026-06-24**: WidgetKit の実行モデル (セッション 277) との整合を追記
- **2026-06-19**: `allowedExecutionTargets` の選択肢を「`.main` / `.appIntentsExtension` の 2 つ」と書いていたのを、`.widgetKitExtension` を含む 3 つに訂正

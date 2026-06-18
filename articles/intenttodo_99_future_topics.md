---
title: "App Intents 中心設計シリーズ — 検証待ち・将来書く予定のトピック (99/N)"
emoji: "📝"
type: "tech"
topics: ["AppIntents", "iOS", "watchOS", "visionOS", "TODO"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の番外編です。

本編 1〜5 では、自分が IntentTodo を作る中で **実機・実体験で確証が取れた範囲** に絞って書いてきました。
一方で、検証はまだだけれど書きたいトピックや、検証待ちの状態で温めている知見もそれなりにあります。
この記事はそれらを「将来書く予定」として並べておく場所で、進捗に合わせて随時更新していきます。

なお、この記事を最初に書いたあと、[WWDC 2026 編 (6〜10/N)](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) を `xcode27` ブランチで書きました。
そちらで当時「将来トピック」に挙げていたものの一部が片付いた (あるいは「やらないと決めた」) ので、まずその差分を反映しておきます。

## なぜ未検証のものを書かないか

理由はシンプルで、**Apple のドキュメントだけ読んで書いた記事は、自分の他の記事と比べたときに情報量があまり追加されない** からです。
公式ドキュメント翻訳系は別の場 ([Liquid Glass の記事](https://zenn.dev/touyou/articles/liquid_glass_apple_doc_overview) のように) でやればいいので、IntentTodo シリーズでは「実機で詰まったところ」か「やってみて分かった設計判断」に価値を絞ろうと思っています。

ただ、WWDC 2026 編については少し方針を緩めました。
新 API は実機 (Siri / Visual Intelligence) まで通すのに端末や手動確認が要るものが多く、本編のような「実機で詰まった話」の基準だといつまでも書けないので、あちらは **「採用していいか / 設計にどう効くか」という設計判断** を軸に、検証の深さ (ビルド / 単体 / 実機) を各記事に明記する形で書いています。

## WWDC 2026 編で片付いたもの

最初にこの記事を書いた時点で「将来」に置いていたもののうち、以下は 6〜10/N で扱いました。

- **Visual Intelligence 連携** (旧トピック F の一部): `IntentValueQuery` + `SemanticContentDescriptor` でカメラ / スクショ中の対象から該当 Todo を返す入口を実装しました。詳細は 10/N に書きます。
- **Interactive Snippets** (旧トピック F の一部): `SnippetIntent` で、追加した Todo をその場で完了 / お気に入り操作できるスニペットを返すところまでやりました。8/N で触れます。

逆に、片付いたというより **「試したけど採用しなかった」「やらないと決めた」** ものもあります。

- **Intent Modes の `.foreground(.dynamic)`** (旧トピック G): `ShowTodosIntent` を一度 `[.background, .foreground(.dynamic)]` + `continueInForeground()` に寄せてみたんですが、これをやると `OpensIntent` (Intent 合成) を外すことになって、それは設計として手放したくなかったので revert しました。今の `ShowTodosIntent` は `.foreground` + `opensIntent:` のままです。`ForegroundContinuableIntent` が deprecated で `.foreground(.dynamic)` が後継、という対応関係は掴めたものの、自分のアプリでは Intent 合成を優先する判断になった、というのが結論でした。
- **FoundationModels (端末内 LLM)** (旧トピック F の一部): Todo 自動生成・サマリー・Tool Calling といった端末内 LLM 連携は、検証計画の段階で **本リポジトリの主眼から意図的に外す** ことにしました。App Intents 中心設計の実証という軸からは少しずれるのと、ここに踏み込むと検証範囲が一気に広がるからです。やらない判断をした、というのも 1 つの結論として残しておきます。

## まだ検証待ちのトピック

ここからは、今もドラフト棚上げのままのものです。

### A. watchOS App + Complication 全ファミリー検証

- WatchTodoListView での incomplete + due-soon セクション表示
- WatchAddTodoView の `Button(intent:)` 経由の Todo 追加 (`@Dependency` 解決クラッシュなく動くか)
- Complication 全 4 ファミリー (Circular / Corner / Rectangular / Inline) の表示確認
- タイムライン更新の挙動 (`Timeline.policy(.after:)` で 15 分以内に反映されるか)
- ウォッチフェイスへの登録動作

これは Apple Watch 実機を引っ張り出してペアリング状態の確認から、という腰の重さでまだ手付かず。

### B. visionOS 空間 UI 検証

- `NavigationSplitView` のサイドバー + 詳細ペインの実機での挙動
- Ornament 内の Filter / Sort / Add の使い勝手
- `glassBackgroundEffect()` のレンダリング
- `.hoverEffect(.lift)` / `.hoverEffect(.highlight)` の視線追跡反応
- `Button(intent:)` 経由の各アクション (`role:` が引数の先頭に来るシグネチャで動くか)

Vision Pro 持ってないので、シミュレータで動いた範囲だけしか言及できない状態。
visionOS でハマった「`NavigationSplitView.selection` の更新を NavigationModel に統合した」話 (本シリーズ 2/N で軽く触れた話) の続きは、実機検証ができたら書きたいです。

### C. Spotlight の iOS 反映ラグ

シリーズ 5/N で `IndexedEntity` 準拠だけでは Spotlight に出ないので `CSSearchableIndex.indexAppEntities` の明示登録が必要、という話を書きました。
macOS では即座に検索ヒットするのですが、iOS では index 反映に数分〜10 分単位のラグがあるようで、まだ実機で検索ヒットを確認できていません。
反映タイミングの再現性が取れたら、別記事で `CSSearchableIndex` の運用 Tips としてまとめたいです。

### D. macOS native の細部

- macOS native 通知をタップして AddTodo シートが立ち上がる経路
- macOS Shortcuts.app で AppShortcuts (8 件) が正しく表示されるかの細部
- Siri からの音声呼び出し
- フィルタ付き Intent (`ShowTodosIntent`) のパラメータ選択 UI

macOS native はビルドが通って起動してデータ操作までは動いているところまで確認済み。
通知周りや Siri 周りは触れていないので、検証してから書く予定です。

### E. Live Activity の AppEntity crash 再現条件

シリーズ 5/N で「Live Activity Extension で `AppEntity` 解決時にクラッシュする」と書いた話、実は **本シリーズ執筆時点では実機で再現できていません**。
Primary / FromExtension 分離パターンが効いている状態だと当然クラッシュは起きないので、workaround 無しのケースで再現する手順を書ければ、その時点で Apple Feedback Assistant に提出できる材料になります。
ただし production の workaround は維持したいので、再現コード断片だけ別ブランチで作るのが現実的です。

### F. App Schema の reminder 本体適合

WWDC 2026 編 (7/N) で `Category` を `@AppEntity(schema: .reminders.list)` に適合させた話は書けたんですが、**Todo 本体を `@AppEntity(schema: .reminders.reminder)` に適合させるのは保留** しました。
reminder スキーマがマクロ生成 init で `EntityProperty<T>` 引数を取り、さらに `section` / `locationTrigger` 等の入れ子サブエンティティを再帰的に要求してくるため、モデルから組み立てる自前 init と相性が悪い、という詰まり方をしています。
list 適合で App Schema の仕組み自体は検証できたので、本体適合は独立タスクとして切り出して、深掘りできたら追記する予定です。

### G. `.foreground(.deferred)` の細部

`.foreground(.dynamic)` は上に書いたとおり一度試して revert したんですが、`[.background, .foreground(.deferred)]` のような「初期バックグラウンド → 必要になったら自動 foreground 化」の挙動は、そもそもまだどういうケースで活きるのか手応えが無いです。
`perform()` 終了時にシステムが自動で foreground 化するタイミングの細かい semantics は公式にも明記が薄いので、実機で挙動を掴めたら書きたいトピックです。

### H. `LoadResult<T>` 型の導入

シリーズ 5/N で軽く触れた、Spotlight の fire-and-forget エラー扱いと近い話で、IntentTodo 全体に「`LoadResult<T>.success(T) | .unavailable(reason: String)` のような型で『不明』と『ゼロ』を強制区別する」リファクタを入れたい欲があります。
これがあると Provider / Intent / View 層を通じて『データが無い』と『データが取れなかった』を別の概念として扱えるようになり、ユーザーに嘘の安心感を与える silent failure が減らせるはず。
silent failure 系の個別修正は `main` 側でいくつか入れた (fetch 失敗を黙って 0 件にせず throw する、等) んですが、`LoadResult<T>` を全 layer に通すとなるとコストが大きいので、prototype 程度で試してから記事化する予定です。

### I. WWDC 2026 セッションを読み直して増えた採用候補

WWDC 2026 編を公開したあと、セッション情報 (240 / 343 / 344 / 345 / Group Lab) を読み直したら「これは IntentTodo に入れて検証したら記事になりそう」という候補がいくつか出てきました。まだ実装は追えていないので、忘れないように IntentTodo 側へ issue を立てて追跡しています。

- **`@Property(indexingKey:)` でセマンティック Spotlight インデックス** (#240): 本文を `indexingKey` 付きで公開すると、意味ベース検索 / Q&A の対象になる。今は `CSSearchableIndex` の明示登録 (5/N) だけなので、その上の経路を試したい。
- **`Transferable` + `ValueRepresentation` で構造化値エクスポート** (#345): Todo の場所を `PlaceDescriptor` として書き出すなど、cross-app の口を作る。
- **`IntentParameter.valueState` で UpdateTodoIntent** (#344): optional パラメータの「新しい値 / 明示クリア / 据え置き」を `.set(value)` / `.set(nil)` / `.unset` で区別する更新 Intent。
- **コレクション onscreen + 通知 / AlarmKit への entity アノテーション** (#343): 一覧の行に `.appEntityIdentifier(forSelectionType:)`、通知やアラームにも entity-identifier を付けて「3 番目のやつ」のような参照に対応する。
- **`.system.searchInApp` 適合** (#343): `SearchEverythingIntent` をこのスキーマに適合させ、Siri がアプリ自身の検索 UI で結果を出せるようにする。
- **`allowedExecutionTargets` の再検証** (#345): 9/N で訂正したとおり `.widgetKitExtension` も選べるので、これで Primary / FromExtension 分離を畳めないか改めて確かめる。
- **reminder 本体スキーマ適合の優先度** (Group Lab): 「新しい Siri と連携するにはいずれかの App Schema 採用が前提」とのことなので、コアの `TodoAppEntity` を意味理解させるには上記 F の本体適合がやはり要る、という位置づけが見えてきた。

## まとめ

- 本編は「実機で詰まった話」、WWDC 2026 編は「採用していいか / 設計判断」と、軸を分けて書いている
- 最初に並べた将来トピックのうち、Visual Intelligence / Interactive Snippets / Intent Modes の一部は WWDC 2026 編で片付いた
- FoundationModels (端末内 LLM) は「やらないと決めた」もの。主眼から意図的に外している
- 残りの検証待ち (watchOS / visionOS / Spotlight ラグ / macOS 細部 / LA crash 再現 / reminder 本体適合 / `.foreground(.deferred)` / `LoadResult<T>`) は、手元の機材と検証コストで順番が決まる予定

書ける段階になり次第、ここから本編へ昇格させていきます。

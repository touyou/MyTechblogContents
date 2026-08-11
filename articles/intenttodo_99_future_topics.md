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

## (2026-06-24 追記) WWDC 2026 の SwiftData レビューで整理できたもの

WWDC 2026 の SwiftData 関連セッションと Group Lab を見直したら、「これまで微妙だと思っていた / 判断を保留していた」観点のいくつかが、公式の裏付けで整理できました。本編側に反映したもの (マイグレーションをアプリ本体に一本化する話 → [4/N](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) / [3/N](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions)、WidgetKit 実行モデルの明文化 → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)) とは別に、ここに棚卸しとして残しておきます。

### View 外での SwiftData 監視に公式 API ができた

本シリーズの裏で一度、`IntentAppState` という自前の `NotificationCenter` 購読でデータ変更を拾う仕組みを入れていたんですが、プロセスを跨いだ `NotificationCenter.post` は届かず脆かったので撤去して、今は `@Query` と `NavigationModel` への直接注入に寄せています。

WWDC 2026 で `ResultsObserver` / `ModelResultsObserver` という、SwiftUI の外で SwiftData の結果変化を監視する公式 API が出てきました。今は監視を `@Query` に集約できていて即使う先は無いんですが、「非 SwiftUI レイヤで SwiftData を監視したい」が再び出てきたら、自前 `NotificationCenter` ではなく正攻法でやれる、という安心材料ができた格好です。撤去した `IntentAppState` の判断が後付けで裏付けられた、とも言えます。(API 名はベータ時点の情報なので、実際に使うときに確認し直す前提です)

### 検討したが「該当なし」だった新機能

記事で紹介されていた SwiftData の新機能のうち、IntentTodo の現状には噛み合わなくて見送ったものも書いておきます。「使わなかった」も判断の記録なので。

- **sectioned `@Query` (`sectionBy:`)**: watch 側でやっている手動 partition は「now から 1 時間以内」という **時刻依存の動的な区切り** で、`sectionBy:` が要求する保存済みの String KeyPath では表現できない → 不適合。カテゴリ別グルーピング画面を新設するなら選択肢になります。
- **`@Attribute(.codable)`**: 複雑な型を rawValue で逃がすようなワークアラウンドが今のモデルには無い (基本型に分解済み) → 出番なし。
- **`HistoryObserver`**: 自前サーバー同期をしておらず CloudKit ネイティブなので → 該当なし。
- **external storage**: バイナリ / 画像を保存していないので → 該当なし。

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
(2026-07-28 追記) 実機は相変わらず無いままなんですが、**実機 SDK 向けのビルドだけが落ちる** という別種の問題は 1 つ潰しました。`#if canImport(VisualIntelligence)` がシミュレータでは false、実機 SDK では true になってビルドが割れる話で、詳しくは [10/N の追記](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing) に書いています。シミュレータで動いた範囲しか言えない、の前に「実機向けにビルドは通るのか」という段があったんだなと反省しました。
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

(2026-07-02 追記) 下の I にも書いたとおり、Group Lab の「新 Siri 連携は App Schema 採用が前提」という話を受けて一度再評価したんですが、据え置きの結論は変わりませんでした。入れ子サブエンティティの要求仕様 (`section` / `locationTrigger` / `locationTriggerEvent`) は具体的に分かった一方で、それらを揃えてもマクロ生成 init の初期化規約問題は解消しないためです。Xcode 27 beta 2 でも当時の probe コードを復元してビルドして、同じ初期化エラーが再現することを確認しました。詳しい経緯は [7/N の追記](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents) に書いています。

### G. `.foreground(.deferred)` の細部

`.foreground(.dynamic)` は上に書いたとおり一度試して revert したんですが、`[.background, .foreground(.deferred)]` のような「初期バックグラウンド → 必要になったら自動 foreground 化」の挙動は、そもそもまだどういうケースで活きるのか手応えが無いです。
`perform()` 終了時にシステムが自動で foreground 化するタイミングの細かい semantics は公式にも明記が薄いので、実機で挙動を掴めたら書きたいトピックです。

### H. `LoadResult<T>` 型の導入

シリーズ 5/N で軽く触れた、Spotlight の fire-and-forget エラー扱いと近い話で、IntentTodo 全体に「`LoadResult<T>.success(T) | .unavailable(reason: String)` のような型で『不明』と『ゼロ』を強制区別する」リファクタを入れたい欲があります。
これがあると Provider / Intent / View 層を通じて『データが無い』と『データが取れなかった』を別の概念として扱えるようになり、ユーザーに嘘の安心感を与える silent failure が減らせるはず。
silent failure 系の個別修正は `main` 側でいくつか入れた (fetch 失敗を黙って 0 件にせず throw する、等) んですが、`LoadResult<T>` を全 layer に通すとなるとコストが大きいので、prototype 程度で試してから記事化する予定です。

### I. WWDC 2026 セッションを読み直して増えた採用候補 (すべて決着済み)

WWDC 2026 編を公開したあと、セッション情報 (240 / 343 / 344 / 345 / Group Lab) を読み直したら「これは IntentTodo に入れて検証したら記事になりそう」という候補がいくつか出てきました。その後 `xcode27` ブランチでひととおり実装・検証まで進んだので、候補と結果をまとめて置いておきます (詳細はそれぞれの記事に追記済みです)。

- **`@Property(indexingKey:)` でセマンティック Spotlight インデックス** (セッション 240) → **採用**。`\.title` / `\.contentDescription` にマップしました。`indexingKey:` のオーバーロードは iOS / macOS でしか vend されないので `#if` ガードが要ります → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- **`Transferable` + `ValueRepresentation` で構造化値エクスポート** (セッション 345) → **採用**。担当者を `IntentPerson`、場所を `PlaceDescriptor` へ export → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- **`IntentParameter.valueState` で UpdateTodoIntent** (セッション 344) → **採用**。「新しい値 / 明示クリア / 据え置き」の三値を `FieldUpdate` というサービス層の enum に写像しました → [8/N](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- **コレクション onscreen + 通知 / AlarmKit への entity アノテーション** (セッション 343) → **採用**。一覧に `.appEntityIdentifier(forSelectionType:)` (大きなリストで id を遅延マップする版)、通知に `UNMutableNotificationContent.appEntityIdentifiers` を付与しています。通知側は **永続 AppEntity が必須** で `TransientAppEntity` は不可、というのが引っかかりどころでした。これはどの記事の主題ともずれるので、記録はここだけです
- **`.system.searchInApp` 適合** (セッション 343) → **採用**。`SearchEverythingIntent` への適合ではなく、遷移専用の別 Intent (`ShowTodoSearchResultsIntent`) を新設する形になりました → [7/N](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents)
- **`TransientAppEntity`** (セッション 344) → **採用**。集計値を返す `TodoListSummaryEntity` + `GetTodoSummaryIntent` を新設して、Shortcuts で「未完了が N 件以上なら通知」のような条件分岐を組めるようにしました → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)。上の「通知の entity アノテーションは永続 `AppEntity` 必須」という制約とちょうど裏表で、id で名指しされる名詞と、その場で計算して返すだけの値が型で分かれている、という整理に落ち着きました
- **`allowedExecutionTargets` の再検証** (セッション 345) → **「FromExtension は畳めない」で確定**。制御できるのは perform のプロセスであって entity 解決の有無ではない、が理由です → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- **reminder 本体スキーマ適合の優先度** (Group Lab) → **据え置き継続**。詳細は上の F
- **`EntityPropertyQuery`** → **不採用**。既存の `TodoEntityQuery` (`EntityStringQuery`) で足りていて、入れる理由が無かったためです

ついでの話として、SDK 27 の SwiftUI 新 API (ドラッグ並べ替えの `reorderable()` / `reorderContainer`) に追従したときも、並べ替えの永続化は `ReorderTodosIntent` という Intent として定義しました。ドラッグ確定は `Button(intent:)` に載せられないので View からは Intent と同じ `TodoService.reorderTodos(orderedIDs:)` を直接呼ぶんですが、ロジックの置き場を Intent 側の語彙に寄せておくことで、「アクションはまず Intent として定義する」という 1/N の原則は崩れていません。

### (2026-08-05 追記) セッションを 2022 まで遡って洗い直した

ここまでは「WWDC 2026 のセッションを読み直して」の話でしたが、App Intents が登場した **WWDC 2022 まで遡って全セッションを洗い直し** ました。IntentTodo 側に年ごとの API 一覧と非推奨タイムラインを作ったので、そのついでに記事の記述も突き合わせています。

出てきた差分のほとんどが **年代の帰属** でした。WWDC 2026 編にまとめて書いたせいで、実際には iOS 26 以前からある API まで 2026 の新要素のように読める書き方になっていたやつです。

- `@ComputedProperty` / `@DeferredProperty` はどちらも iOS 26 (セッション 275) → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- `requestChoice` / `SnippetIntent` は iOS 26。`requestConfirmation` と `IntentDialog(full:supporting:)` の型に至っては WWDC 2022 から → [8/N](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- `@UnionValue` は WWDC 2024 (セッション 10134) で、345 は実装要件を提示した回 → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- Visual Intelligence の `IntentValueQuery` / `SemanticContentDescriptor` も iOS 26 からで、297 は macOS 対応が増えた回 → [10/N](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing)

ベースラインが iOS 26 のプロジェクトに iOS 27 の新要素を足していく作り方だと、手元では「今の SDK で使えるか」しか見ないので、この 2 世代の境目が自分の中でもあいまいになっていました。

あわせて、**API は把握したうえでこのアプリには入れないと決めたもの** も記録しておきます。`DynamicOptionsProvider` と `IntentParameterDependency` (WWDC 2022 / 2023) は、パラメータの選択肢を動的に出したり、別パラメータの現在値に依存させたりするための道具ですが、IntentTodo にはそもそも **パラメータ間の動的依存が発生するユースケースが無い** です。フィルタや並び順は `AppEnum` の静的リストで足りていて、Todo やカテゴリの選択は `EntityQuery` が引き受けています。「使える API だけど要らない」というのも判断の記録なので、ここに残しておきます。

### (2026-07-28 追記) J. `PlaceDescriptor` をネイティブ型に戻す

これは自分の検証待ちというより SDK 待ちのタスクです。
6/N で「`PlaceDescriptor` をネイティブ型のまま `@Parameter` / `@Property` で受ける」と書いた部分、Xcode 27 beta 3 から `AppIntentsSSUTraining` が `GeoToolbox.PlaceDescriptorEntity` という型名をそのまま SSU の variable 名に使ってしまい、ドット入りの名前が正規表現に落ちてビルドエラーを emit するようになったので、暫定で場所名の `String` に退避しています (beta 4 でも未修正、**beta 5 でも未修正**)。
ローカルの `xcodebuild` は exit 0 で返ってくるのに Xcode Cloud だけ失敗する、という気付きにくい壊れ方をするのも含めて、経緯は [6/N の追記](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) に書きました。
SDK が更新されたら退避コミットを revert してクリーンビルドし直す、というのを毎回の beta 追従のチェック項目にしています。緯度経度を Intent 経由で受け取る口が閉じたままなので、ここは早く戻したいところです。

### (2026-08-05 追記) K. `UndoableIntent` で取り消しに対応する

セッションを 2022 から洗い直していて、まだ手を付けていないのに気付いたのが `UndoableIntent` です。iOS 26 (セッション 275) で入っていたもので、`undoManager.registerUndo(withTarget:handler:)` と組み合わせて Intent の実行を取り消せるようにするプロトコルでした。

IntentTodo には削除・バルク完了・スヌーズと、取り消したくなりそうな破壊的アクションが一通り揃っているので、相性は悪くないはずです。ただ 8/N で書いたとおり削除には `requestConfirmation` を先に入れていて、「実行前に止める」で今のところ足りている感覚もあります。実行前の確認と実行後の取り消しをどう住み分けるか (両方あると鬱陶しいのか、それとも Siri から実行したときは取り消しの方が効くのか) は、実際に入れてみないと分からないところなので、検証候補として置いておきます。

## (2026-08-11 追記) 制約を全部洗い直した

Xcode 27 beta 5 が出たので追従したついでに、これまでとは毛色の違う作業をしました。IntentTodo のドキュメントに「プラットフォームの制約」として書き溜めてきた項目を、WWDC 2022〜2026 のセッション書き起こし 25 本と **全数突き合わせて、セッションの説明と食い違うものを片っ端から洗い出す** というやつです。

やってみて分かったのは、**自分が「制約」として記録していたもののうち、いくつかは実装の都合だったり、単なる断定しすぎだったりした** ということでした。壊れた記憶が「〜してはいけない」という強いルールとしてドキュメントに固定されて、その後は疑われないまま残り続ける、という形になっていたものが結構あります。出てきた差分は大きく 3 種類でした。

**1. 断定を取り下げたもの** (再検証したら根拠が足りなかった)

- 「アプリ側に `includedPackages` 付きの `AppIntentsPackage` を重複宣言してはいけない」→ ビルドとメタデータのレベルでは重複が起きず、むしろセッション 244 / 275 は逆にそのパターンを標準手順として紹介していました → [3/N](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions)
- 「Widget の `.background` Intent は必ず Widget Extension プロセスで実行される」→ 実際は未指定ならヒューリスティクスで、固定したいなら `allowedExecutionTargets` を明示する → [2/N](https://zenn.dev/touyou/articles/intenttodo_02_todoservice_dependency) / [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- 「Live Activity Extension プロセスで entity 解決が走ると SwiftData が trap する」→ クラッシュは実在するけれど、事前解決フェーズがどのプロセスで走るかは公式に明記が無いので原因の特定を取り下げ → [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls)
- 「`\.textContent` は SDK に露出していない」→ 普通にありました。`contentDescription` を使う結論は変わらないものの、理由が型の制約ではなく意味の制約だった → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- 「Mac だけ visual search の entity 全部に `OpenIntent` を要求する」→ 要求は全プラットフォーム共通で、Mac だけがコンパイル時に弾いてくる → [10/N](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing)

**2. 理由付けだけ差し替えたもの** (ルールは正しいが説明が違った)

- Control Widget の `ControlValueProvider`: 「body が過剰評価される」ではなく、非同期取得は Provider の役目でリロード時に Provider → body の順に走る、という分担モデルの話 → [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls)
- Widget Extension 内の `ControlConfigurationIntent` をアプリから参照できない理由: 「Name Mangling」ではなく単にターゲット/モジュール境界でした。共有したいなら SPM に出すのが公式の方法です
- 全 Intent で `WidgetReloader.reloadAllWidgets()` を呼ぶルール: Widget 内の `Button(intent:)` 起点なら **システムが自動でリロードを保証している** (セッション 10028) ので、手動が本当に要るのは Siri / Shortcuts / アプリ UI 側から変えたときだけでした。無条件に呼ぶ運用は安全側なので変えていませんが、理由は「Widget 起点は自動、それ以外の経路のために必要」が正確です
- watchOS の `Button(intent:)`: プラットフォーム別のメモに「watchOS は `role:` 付きのシグネチャが使えないから手動で `Task { try? await intent.perform() }` する」と書いてあったんですが、これは別のメモにある「手動 `perform()` は `@Dependency` がゼロ初期化のままになるのでクラッシュする、必ず `Button(intent:)` を使う」という指針と真逆でした。実際の `WatchUI` のコードを見に行ったら全部 `role:` 無しの `Button(intent:)` で書いてあって、手動 perform を勧めていた方が誤記です。使えないのは `role:` 付きのシグネチャだけでした。同じリポジトリのドキュメント同士が正反対のことを言っているのに、突き合わせるまで誰も (自分も) 気付いていなかった、というのはちょっと怖かったです
- `#Predicate` の Optional 直接比較: 「visionOS 等で」とプラットフォーム限定で書いていましたが、マクロの型推論の話なので基本は全プラットフォーム共通のはずで、当時の再現/非再現は toolchain のバージョン差だった可能性が高いです

**3. セッション番号・年代の帰属間違い**

2026-08-05 の追記でも同じことをやったんですが、今回は「その API 名が本当にそのセッションの書き起こしに出てくるか」を全文検索で機械的に確かめたので、前回の訂正そのものが間違っていた、というのが何件か出てきました。いちばん大きいのが `.system.searchInApp` で、**343 → 344 に直したのが間違いで、最初の 343 が正しかった** です (→ [7/N に追記](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents))。他にも `AppEntityContext` / `RelevantEntities` は 10133 ではなく 345、`ControlWidgetButton` / `ControlConfigurationIntent` は 10157 ではなく 10210、`@ComputedProperty` / `@DeferredProperty` は 345 ではなく 275、といった具合に、隣接するセッションや API ドキュメントと混ざっているものがまとめて出てきました。8/N の出典訂正 (`requestConfirmation` のラベル指定オーバーロードや `IntentDonationManager` は、セッションではなく API ドキュメント由来だった) も同じ流れです。

一連の作業でいちばん効いたのは、**「セッションで説明されていたこと」「API ドキュメントを読んで知ったこと」「自分がビルドして観測したこと」を、後から見分けられる形で書いていなかった** という反省でした。3 つとも自分の中では同じ「知っていること」なんですが、確度も、後から確かめる手段も全然違います。特に 3 番目の観測は SDK が更新されるたびに賞味期限が来るので、そこを混ぜて書くと、直せるはずのものが直せないまま残ります。

### 実機検証待ちに積み増しになったもの

洗い直した結果、「机上では確からしいけれど実機で確かめないと確定しない」という宿題がむしろ増えました。ここに並べておきます。

- **`AppIntentsPackage` の重複宣言**: メタデータ上の重複は無いことまで確認済み。Siri / Shortcuts の実機ルーティング (`LNContextErrorDomain` 系) が本当に壊れないかは未確認なので、現状は重複させない運用のまま
- **Live Activity の entity 事前解決**: Primary 版の Intent を LA のボタンに直結して実機で叩き、今の SDK でも trap するのかを見たい。再現しないなら FromExtension 分離を簡素化できる (上の E とつながる話)
- **`allowedExecutionTargets` 未指定の Widget / Control Intent**: 実際どちらのプロセスで perform され、entity 解決がどこで走るのかを実機ログで見たい。`CompleteTodosIntent` だけは `[.main]` に固定済み
- **`.controlWidgetStatus(_:)` の見え方**: シミュレータビルドまで。実機の Control Center でどのくらい出るのか、ローカル通知と併用して鬱陶しくないかは未確認 (→ [5/N の追記](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls))
- **`UISceneAppIntent` の `canImport` ガード**: `_AppIntents_UIKit` という独立フレームワークに属していて、iOS / watchOS / visionOS にはあるがネイティブ macOS には無い、というところまで確認済み。iOS 側で `#if canImport(_AppIntents_UIKit)` が通ることも実際に走らせて確かめました。ただマルチウィンドウの具体的な機能要求が無いので実装自体は保留
- **reminder 本体スキーマ適合の再挑戦** (上の F): セッション 344 の CometCal パターンという取っ掛かりが見つかったので、そこから試す (→ [7/N に追記](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents))
- **`.onAppIntentExecution` の cold start 問題**: そもそも今のコードベースでは `.onAppIntentExecution` をどこでも使っていない (`@Dependency` + `perform()` に完全移行済み) ので、現時点では検証対象が無い状態です。再導入するときに「`@State` の path が未構築」「シーンの activation conditions 未設定」「`supportedModes` に foreground が無い」の 3 仮説を潰す、というメモだけ残しました

## まとめ

- 本編は「実機で詰まった話」、WWDC 2026 編は「採用していいか / 設計判断」と、軸を分けて書いている
- 最初に並べた将来トピックのうち、Visual Intelligence / Interactive Snippets / Intent Modes の一部は WWDC 2026 編で片付いた
- FoundationModels (端末内 LLM) は「やらないと決めた」もの。主眼から意図的に外している
- 残りの検証待ち (watchOS / visionOS / Spotlight ラグ / macOS 細部 / LA crash 再現 / reminder 本体適合 / `.foreground(.deferred)` / `LoadResult<T>` / `PlaceDescriptor` の復帰 / `UndoableIntent`) は、手元の機材と検証コストで順番が決まる予定
- 書き溜めた「制約」をセッション書き起こしと全数突き合わせたら、断定しすぎ・理由付けの誤り・出典の取り違えがまとめて出てきた。「セッションで説明されていたこと / API ドキュメントで知ったこと / 自分がビルドして観測したこと」は、後から見分けられる形で分けて書いておかないと直せなくなる

書ける段階になり次第、ここから本編へ昇格させていきます。

## 更新履歴

本文は常に最新の状況に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-11**: 「制約を全部洗い直した」節と、実機検証待ちに積み増しになったものの一覧を追加。`.system.searchInApp` の出典を **343** に戻した (2026-08-05 に 344 と直したのが誤りだった)。`@ComputedProperty` の出自も 275 に再訂正。`PlaceDescriptor` の SSU バグが beta 5 でも未修正であることを反映。あわせて記事全体を、日付を追う書き方から「今どうなっているか」を先に書く形へ整理
- **2026-08-05**: セッションを WWDC 2022 まで遡って洗い直した節を追加。トピック K (`UndoableIntent`) を追加
- **2026-07-28**: トピック J (`PlaceDescriptor` をネイティブ型に戻す) を追加。`TransientAppEntity` の採用を反映
- **2026-07-08**: `.system.search` が `.system.searchInApp` にリネームされたのを反映
- **2026-07-02**: 採用候補 (トピック I) の検証結果を反映
- **2026-06-24**: WWDC 2026 の SwiftData レビューで整理できたものの節を追加

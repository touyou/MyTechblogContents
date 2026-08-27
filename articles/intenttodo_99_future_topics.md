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

なお、この記事を最初に書いたあと、[WWDC 2026 編 (6〜10/N)](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) を `xcode27` ブランチ (現在は `main` にマージ済み) で書きました。
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

- **Intent Modes の `.foreground(.dynamic)`** (旧トピック G): `ShowTodosIntent` を一度 `[.background, .foreground(.dynamic)]` + `continueInForeground()` に寄せてみたんですが、これをやると `OpensIntent` (Intent 合成) を外すことになって、それは設計として手放したくなかったので revert しました。今の `ShowTodosIntent` は `.foreground` + `opensIntent:` のままです。そのときは「dynamic 自体は有用なので、もっと適した Intent が出てきたら検討する」と宿題にしていたんですが、その後 **全 21 Intent を見直して「当て先が無い」で閉じました**。詳細は [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis) に書いています。
- **寄付 (`IntentDonationManager`)**: これは「片付いた」というより **入れないことに決めた** ものです。`perform()` の中で寄付するのは公式ガイダンス違反なので撤去して、代わりに UI のタップ地点で寄付する案を 3 通り検討したんですが、どれも「UI からは Intent を直接呼ぶ」前提で、`Button(intent:)` を唯一の実行経路にしている設計と両立しませんでした。再訪する条件 (Siri の予測 / 提案を機能として欲しくなったとき) だけ決めて閉じています → [8/N](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- **`SpotlightSearchTool` + `LanguageModelSession`** (セッション 246): 前提の「Spotlight への entity 寄付」は揃ったんですが、残りの作業が FoundationModels 側に寄るので **スコープ外** としました。下の FoundationModels をやらない判断と同じ線引きです → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- **FoundationModels (端末内 LLM)** (旧トピック F の一部): Todo 自動生成・サマリー・Tool Calling といった端末内 LLM 連携は、検証計画の段階で **本リポジトリの主眼から意図的に外す** ことにしました。App Intents 中心設計の実証という軸からは少しずれるのと、ここに踏み込むと検証範囲が一気に広がるからです。やらない判断をした、というのも 1 つの結論として残しておきます。

## WWDC 2026 の SwiftData レビューで整理できたもの

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

- ~~WatchAddTodoView の `Button(intent:)` 経由の Todo 追加 (`@Dependency` 解決クラッシュなく動くか)~~ → **シミュレータで確認して、実際に壊れていたので直しました**。`NavigationModel` を watch アプリ側で登録していなかったせいで、追加が **無音で失敗** していました (クラッシュしないので気付けていなかったやつです)。ついでに詳細画面への導線と onscreen annotation も入れています → [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls) / [10/N](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing)
- WatchTodoListView での incomplete + due-soon セクション表示
- Complication 全 4 ファミリー (Circular / Corner / Rectangular / Inline) の表示確認
- タイムライン更新の挙動 (`Timeline.policy(.after:)` で 15 分以内に反映されるか)
- ウォッチフェイスへの登録動作
- `OpenTodoIntent` 経由で watch の詳細画面に飛べるか (watchOS では AppIntentsTesting の `run()` が通らないので、ここは手で見るしかありません)

実機を引っ張り出してペアリング状態の確認から、というところは相変わらず腰が重いんですが、**シミュレータで一連の操作をなぞるだけでも 1 つ実害が見つかった** ので、「実機が要る」を理由に全部を寝かせるのは良くなかったなと思っています。

### B. visionOS 空間 UI 検証

- `NavigationSplitView` のサイドバー + 詳細ペインの実機での挙動
- Ornament 内の Filter / Sort / Add の使い勝手
- `glassBackgroundEffect()` のレンダリング
- `.hoverEffect(.lift)` / `.hoverEffect(.highlight)` の視線追跡反応
- `Button(intent:)` 経由の各アクション (`role:` が引数の先頭に来るシグネチャで動くか)

Vision Pro 持ってないので、シミュレータで動いた範囲だけしか言及できない状態。
実機は相変わらず無いままなんですが、**実機 SDK 向けのビルドだけが落ちる** という別種の問題は 1 つ潰しました。`#if canImport(VisualIntelligence)` がシミュレータでは false、実機 SDK では true になってビルドが割れる話で、詳しくは [10/N](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing) に書いています。シミュレータで動いた範囲しか言えない、の前に「実機向けにビルドは通るのか」という段があったんだなと反省しました。
visionOS でハマった「`NavigationSplitView.selection` の更新を NavigationModel に統合した」話 (本シリーズ 2/N で軽く触れた話) の続きは、実機検証ができたら書きたいです。

### C. Spotlight の iOS 反映ラグ

シリーズ 5/N で `IndexedEntity` 準拠だけでは Spotlight に出ないので `indexAppEntities` の明示登録が必要、という話を書きました。
macOS では即座に検索ヒットするのですが、iOS では index 反映に数分〜10 分単位のラグがあるようで、まだ実機で検索ヒットを確認できていません。
反映タイミングの再現性が取れたら、別記事で `CSSearchableIndex` の運用 Tips としてまとめたいです。

実装側はその後だいぶ育っていて、名前付き index への移行・`IndexedEntityQuery` の実装・client state による起動時全件 index の省略・連続失敗からの自己修復までは入りました (5/N)。**Spotlight の再インデックス要求 (`reindexAllEntities`) が実際にシステムから呼ばれる状況** の再現も、このラグの話と一緒に見たい項目です。手で叩く方法だけは分かっていて、macOS は `mdutil -cr <bundle id>`、iOS は 設定 → デベロッパ → CoreSpotlight Testing です。

### D. macOS native の細部

- macOS native 通知をタップして AddTodo シートが立ち上がる経路
- macOS Shortcuts.app で AppShortcuts (8 件) が正しく表示されるかの細部
- Siri からの音声呼び出し
- フィルタ付き Intent (`ShowTodosIntent`) のパラメータ選択 UI

macOS native はビルドが通って起動してデータ操作までは動いているところまで確認済み。
通知周りや Siri 周りは触れていないので、検証してから書く予定です。

### E. Live Activity の AppEntity crash 再現条件 (決着済み)

シリーズ 5/N で「Live Activity Extension で `AppEntity` 解決時にクラッシュする」と書いた話は、長らく **workaround が効いている状態なので再現手順を書けない** という宙ぶらりんのままでした。Apple Feedback Assistant に出す材料を作るつもりで、再現コード断片を別ブランチに用意しよう、というところまで考えていました。

結果は、probe 用の Intent を Live Activity のボタンに直結して iOS 27 で試したら **3 パターンとも再現しない**、でした。entity の事前解決も `perform()` もメインアプリプロセスで走っていて、`LiveActivityIntent` 準拠の有無でも変わりません。Feedback の材料を作るつもりの検証が、そもそも現行 SDK では起きないという結論になった格好です。これを受けて Primary / FromExtension 分離ごと撤去しました → [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls)

### F. App Schema の reminder 本体適合

WWDC 2026 編 (7/N) で `Category` を `@AppEntity(schema: .reminders.list)` に適合させた話は書けたんですが、**Todo 本体を `@AppEntity(schema: .reminders.reminder)` に適合させるのは保留** しています。

長らく「マクロ生成 init と自前 init が噛み合わない」のが理由だと思っていたんですが、probe で要求プロパティを洗い出したら、それは誤診でした。本当の障害は `list` が非 optional 必須 / `dueDate` が `DateComponents` / `locationTrigger` が `PlaceDescriptor` を強制して SSU training のバグに正面衝突、の 3 点です。3 つ目のせいで **SDK 側が直るまで着手できない** と確定したので、ここは待ちのタスクになりました。詳しい経緯は [7/N](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents) に書いています。

list 適合で App Schema の仕組み自体は検証できていますし、Group Lab の「新 Siri 連携は App Schema 採用が前提」という話も、list 適合 + 自前 Intent 群 + system intent で足りている感触なので、優先度としてもそこまで高くありません。

### G. `.foreground(.deferred)` の細部

`.foreground(.dynamic)` は上に書いたとおり一度試して revert したんですが、`[.background, .foreground(.deferred)]` のような「初期バックグラウンド → 必要になったら自動 foreground 化」の挙動は、そもそもまだどういうケースで活きるのか手応えが無いです。
`perform()` 終了時にシステムが自動で foreground 化するタイミングの細かい semantics は公式にも明記が薄いので、実機で挙動を掴めたら書きたいトピックです。

### H. `LoadResult<T>` 型の導入

シリーズ 5/N で軽く触れた、Spotlight の fire-and-forget エラー扱いと近い話で、IntentTodo 全体に「`LoadResult<T>.success(T) | .unavailable(reason: String)` のような型で『不明』と『ゼロ』を強制区別する」リファクタを入れたい欲があります。
これがあると Provider / Intent / View 層を通じて『データが無い』と『データが取れなかった』を別の概念として扱えるようになり、ユーザーに嘘の安心感を与える silent failure が減らせるはず。

個別修正の方はその後もいくつか入れました。fetch 失敗を黙って 0 件にせず throw する、コンテナ生成に失敗したコンプリケーションは空白ではなく「不明」を出す ([3/N](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions))、通知やライブアクティビティが設定で塞がれていたら記録して設定へ誘導する、Spotlight の差分反映が続けて失敗したら次回起動でフル再インデックスする ([5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls)) あたりです。**どれも「不明」と「ゼロ」を区別するという同じ形** をしているので、型で一発で表現したい気持ちは強くなりました。ただ `LoadResult<T>` を全 layer に通すとなるとコストが大きいので、prototype 程度で試してから記事化する予定です。

### I. WWDC 2026 セッションを読み直して増えた採用候補 (すべて決着済み)

WWDC 2026 編を公開したあと、セッション情報 (240 / 343 / 344 / 345 / Group Lab) を読み直したら「これは IntentTodo に入れて検証したら記事になりそう」という候補がいくつか出てきました。その後 `xcode27` ブランチでひととおり実装・検証まで進んだので、候補と結果をまとめて置いておきます (詳細はそれぞれの記事に反映済みです)。

- **`@Property(indexingKey:)` でセマンティック Spotlight インデックス** (セッション 240) → **採用**。`\.title` / `\.contentDescription` にマップしました。`indexingKey:` のオーバーロードは iOS / macOS でしか vend されないので `#if` ガードが要ります → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- **`Transferable` + `ValueRepresentation` で構造化値エクスポート** (セッション 345) → **採用**。担当者を `IntentPerson`、場所を `PlaceDescriptor` へ export → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- **`IntentParameter.valueState` で UpdateTodoIntent** (セッション 344) → **採用**。「新しい値 / 明示クリア / 据え置き」の三値を `FieldUpdate` というサービス層の enum に写像しました → [8/N](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- **コレクション onscreen + 通知 / AlarmKit への entity アノテーション** (セッション 343) → **採用**。一覧に `.appEntityIdentifier(forSelectionType:)` (大きなリストで id を遅延マップする版)、通知に `UNMutableNotificationContent.appEntityIdentifiers` を付与しています。通知側は **永続 AppEntity が必須** で `TransientAppEntity` は不可、というのが引っかかりどころでした。これはどの記事の主題ともずれるので、記録はここだけです
- **`.system.searchInApp` 適合** (セッション 343) → **採用**。`SearchEverythingIntent` への適合ではなく、遷移専用の別 Intent (`ShowTodoSearchResultsIntent`) を新設する形になりました → [7/N](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents)
- **`TransientAppEntity`** (セッション 344) → **採用**。集計値を返す `TodoListSummaryEntity` + `GetTodoSummaryIntent` を新設して、Shortcuts で「未完了が N 件以上なら通知」のような条件分岐を組めるようにしました → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)。上の「通知の entity アノテーションは永続 `AppEntity` 必須」という制約とちょうど裏表で、id で名指しされる名詞と、その場で計算して返すだけの値が型で分かれている、という整理に落ち着きました
- **`allowedExecutionTargets` の再検証** (セッション 345) → **「FromExtension は畳めない」で確定**。制御できるのは perform のプロセスであって entity 解決の有無ではない、が理由です。なおその FromExtension 分離自体、後日クラッシュが再現しないと分かって撤去したので、宿題ごと消えました → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- **reminder 本体スキーマ適合の優先度** (Group Lab) → **据え置き継続**。詳細は上の F
- **`EntityPropertyQuery`** → **不採用**。当初は「既存の `TodoEntityQuery` (`EntityStringQuery`) で足りている」と書いていましたが、理由の方が不正確でした。正しくは `TodoEntityQuery` が `EnumerableEntityQuery` に適合しているので **Shortcuts の Find アクションと絞り込みが自動生成される** からです。`EntityPropertyQuery` が要るのは全件ロードが重くなる規模のときで、件数が増えたら再評価します → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)

ついでの話として、SDK 27 の SwiftUI 新 API (ドラッグ並べ替えの `reorderable()` / `reorderContainer`) に追従したときも、並べ替えの永続化は `ReorderTodosIntent` という Intent として定義しました。ドラッグ確定は `Button(intent:)` に載せられないので View からは Intent と同じ `TodoService.reorderTodos(orderedIDs:)` を直接呼ぶんですが、ロジックの置き場を Intent 側の語彙に寄せておくことで、「アクションはまず Intent として定義する」という 1/N の原則は崩れていません。

### セッションを 2022 まで遡って洗い直した

ここまでは「WWDC 2026 のセッションを読み直して」の話でしたが、App Intents が登場した **WWDC 2022 まで遡って全セッションを洗い直し** ました。IntentTodo 側に年ごとの API 一覧と非推奨タイムラインを作ったので、そのついでに記事の記述も突き合わせています。

出てきた差分のほとんどが **年代の帰属** でした。WWDC 2026 編にまとめて書いたせいで、実際には iOS 26 以前からある API まで 2026 の新要素のように読める書き方になっていたやつです。

- `@ComputedProperty` / `@DeferredProperty` はどちらも iOS 26 (セッション 275) → [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- `requestChoice` / `SnippetIntent` は iOS 26。`requestConfirmation` と `IntentDialog(full:supporting:)` の型に至っては WWDC 2022 から → [8/N](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- `@UnionValue` は WWDC 2024 (セッション 10134) で、345 は実装要件を提示した回 → [9/N](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- Visual Intelligence の `IntentValueQuery` / `SemanticContentDescriptor` も iOS 26 からで、297 は macOS 対応が増えた回 → [10/N](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing)

ベースラインが iOS 26 のプロジェクトに iOS 27 の新要素を足していく作り方だと、手元では「今の SDK で使えるか」しか見ないので、この 2 世代の境目が自分の中でもあいまいになっていました。

あわせて、**API は把握したうえでこのアプリには入れないと決めたもの** も記録しておきます。`DynamicOptionsProvider` と `IntentParameterDependency` (WWDC 2022 / 2023) は、パラメータの選択肢を動的に出したり、別パラメータの現在値に依存させたりするための道具ですが、IntentTodo にはそもそも **パラメータ間の動的依存が発生するユースケースが無い** です。フィルタや並び順は `AppEnum` の静的リストで足りていて、Todo やカテゴリの選択は `EntityQuery` が引き受けています。「使える API だけど要らない」というのも判断の記録なので、ここに残しておきます。

### J. `PlaceDescriptor` をネイティブ型に戻す

これは自分の検証待ちというより SDK 待ちのタスクです。
6/N で「`PlaceDescriptor` をネイティブ型のまま `@Parameter` / `@Property` で受ける」と書いた部分、Xcode 27 beta 3 から `AppIntentsSSUTraining` が `GeoToolbox.PlaceDescriptorEntity` という型名をそのまま SSU の variable 名に使ってしまい、ドット入りの名前が正規表現に落ちてビルドエラーを emit するようになったので、暫定で場所名の `String` に退避しています (beta 4 でも未修正、**beta 5 でも未修正**)。
ローカルの `xcodebuild` は exit 0 で返ってくるのに Xcode Cloud だけ失敗する、という気付きにくい壊れ方をするのも含めて、経緯は [6/N](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros) に書きました。
SDK が更新されたら退避コミットを revert してクリーンビルドし直す、というのを毎回の beta 追従のチェック項目にしています。緯度経度を Intent 経由で受け取る口が閉じたままなので、ここは早く戻したいところです。

### K. `UndoableIntent` で取り消しに対応する (採用済み)

セッションを 2022 から洗い直していて、まだ手を付けていないのに気付いたのが `UndoableIntent` (iOS 26 / セッション 275) でした。その後、削除 3 種と完了トグルに入れています。

宿題にしていた「実行前の確認と実行後の取り消しをどう住み分けるか」は、**住み分けるものではありませんでした**。`undoManager` は Intent を走らせた面が用意するもので、用意されない呼出元では登録がまるごと no-op になるので、こちらが場合分けする話ではなかったです。実装の要点 (同じ id で戻す / 冪等にする / 完了トグルの取り消しは逆トグルではなく元の値へ) は [8/N](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents) に書きました。

## 制約を全部洗い直した

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
- `#Predicate` の Optional 直接比較: 「visionOS 等で」とプラットフォーム限定で書いていましたが、これは **マクロ固有の制約** でした。プラットフォーム差でも toolchain 差でもなくて、落ちるのは「非 Optional なプロパティ == Optional な値」の 1 パターンだけです。同じ式を `#Predicate` の外に書くと普通に通ります

**3. セッション番号・年代の帰属間違い**

以前も一度セッションを洗い直しているんですが、今回は「その API 名が本当にそのセッションの書き起こしに出てくるか」を全文検索で機械的に確かめたので、前回の訂正そのものが間違っていた、というのが何件か出てきました。いちばん大きいのが `.system.searchInApp` で、**343 → 344 に直したのが間違いで、最初の 343 が正しかった** です (→ [7/N に追記](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents))。他にも `AppEntityContext` / `RelevantEntities` は 10133 ではなく 345、`ControlWidgetButton` / `ControlConfigurationIntent` は 10157 ではなく 10210、`@ComputedProperty` / `@DeferredProperty` は 345 ではなく 275、といった具合に、隣接するセッションや API ドキュメントと混ざっているものがまとめて出てきました。8/N の出典訂正 (`requestConfirmation` のラベル指定オーバーロードや `IntentDonationManager` は、セッションではなく API ドキュメント由来だった) も同じ流れです。

一連の作業でいちばん効いたのは、**「セッションで説明されていたこと」「API ドキュメントを読んで知ったこと」「自分がビルドして観測したこと」を、後から見分けられる形で書いていなかった** という反省でした。3 つとも自分の中では同じ「知っていること」なんですが、確度も、後から確かめる手段も全然違います。特に 3 番目の観測は SDK が更新されるたびに賞味期限が来るので、そこを混ぜて書くと、直せるはずのものが直せないまま残ります。

### 4 つ目の型: 推論を実測と並べて書いてしまう

上の 3 分類にもう 1 つ足りていませんでした。**推論を、実測と同じ体裁で書いてしまう** というやつです。

Control Widget で `.result(dialog:)` が出ないのは実機で確かめた話なんですが、snippet も出ないという方は、Apple の「Siri, Spotlight, and the Shortcuts app が snippet を表示する」という **肯定リストに Control が載っていない** ことからの推論でした。それを dialog の実測結果と同じ表に並べて書いたので、あとから読むと両方とも実測されたルールに見えます。

厄介だったのは、この推論が **それを反証する実験の可能性ごと潰していた** ことでした。「Control では snippet が出ない」を前提に snippet を返す Intent を全部 Control から外したので、Control 経由で snippet を返す経路が 1 つも無い構成になっていて、「Control Center で snippet が一切出ない」のは当たり前、という検証すらできない状態になっていました。

決着させたのは **呼出元だけを変えて、同じ Intent・同じ snippet を走らせる比較** です。結果としては推論のとおり「Control では出ない」だったんですが、そこに至る過程が違います。詳しい経緯と切り分けの表は [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls) に書きました。

なので今の自分ルールは 2 つ増えました。**肯定リスト (「A・B・C が対応」) から否定 (「D は非対応」) を導かない**、導いたなら推論だと明示する。そして **「どの面が何を提示するか」は、まず既知の良い面で動かしてから疑わしい面に持っていく**。逆順にやると変数が絡んで、いつまでも確定しません。

結局そのあと、IntentTodo 側のドキュメントは **全部の記述に `[Apple]` (公式が明言) / `[measured]` (自分が実測) / `[inferred]` (そこからの推論) のラベルを付ける** 形に作り直しました。ここまで痛い目を見ておいて言うのもなんですが、機械的にラベルを打つのがいちばん確実だなと思っています。SDK が更新されたときに `[measured]` だけ優先的に洗い直せばいい、という運用上の利点も付いてきました。

### 5 つ目の型: 1 つしか見ていないのに「見た」と思う

もう 1 つ足すことになりました。**片側しか見ていないのに、確かめた気になる** というやつです。

3/N に書いた「iOS アプリの出荷メタデータからスキーマが消えていた」件で、自分は最初「マクロが `@Property` を生成してくれていないのでは」と疑っていました。実際には生成されていて、全バンドルを並べたら **落ちているのは iOS アプリの 1 つだけ** だと分かります。macOS も visionOS も、パッケージ側も正常でした。見ていたのが 1 つだったから、原因の候補がぜんぶ「マクロ側の問題」に見えていたわけです。

同じ形は前にもありました。`@Property(indexingKey:)` が iOS / macOS でしか vend されていない件は iOS destination のビルドだけ通していて気付かなかったし、`AppShortcutsProvider` がパッケージから集約されない件はパッケージ側のメタデータだけ見て「出ている」と判断していました。**片側しか見ていないと、別の原因に見えます。**

なので運用としては「entity やメタデータまわりを触ったら複数 destination を回す」に加えて、**確かめるときは正常なはずの側も一緒に並べる** ことにしました。差分が 1 行で出るので、そもそも仮説を立てる必要がなくなります。5/N の「呼出元だけを変えて同じ Intent を走らせる」と同じで、比較対象を作ると一発なんだよなと思います。

### 実機検証待ちに積み増しになったもの

洗い直した結果、「机上では確からしいけれど実機で確かめないと確定しない」という宿題がむしろ増えました。ここに並べておきます。

- **App Shortcut のフレーズ**: `AppIntentsPackage` を公式手順どおり宣言する形に切り替えたので (3/N)、残っているのは **フレーズのルーティングだけ** です。しかも今はフレーズにパラメータを埋めた (「Complete 〜 in IntentTodo」) ので、候補の解決まで含めて実機で見たいところが増えました。AppIntentsTesting は型名で intent を引くのでこの経路を通りません
- **`allowedExecutionTargets` 未指定の読み取り系 Intent**: 書き込み系は全部 `[.main]` に固定したので (2/N / 9/N)、残るのは読み取り系です。実際どちらのプロセスで perform され、entity 解決がどこで走るのかを実機ログで見たい
- **Control をアプリ完全終了状態で叩いたときの体感**: 書き込み系を `[.main]` に固定したことで、アプリのバックグラウンド起動が挟まるようになりました。dialog も snippet も出ない面なので、遅延が実用上どうかは実機で見るしかありません
- **`.reminders.list` 適合が実機の Siri / Apple Intelligence で効くか**: 統合メタデータに載っていることまでは確定しました (3/N)。AppIntentsTesting は型名で intent / entity を引くのでスキーマ経路を通らず、ここから先は手動確認の領域です
- **`UISceneAppIntent`**: `#if canImport(_AppIntents_UIKit) && !os(watchOS)` という **ガードの形さえ間違えなければ Package スコープでも置ける** ことを確認したうえで、その後 `LaunchAppIntent` / `OpenTodoIntent` に採用しました。狙いはマルチウィンドウではなく cold start です (5/N)。実機で cold start の遷移を確かめるのが残りです
- **reminder 本体スキーマ適合** (上の F): probe で要求仕様は確定したものの、`locationTrigger` が `PlaceDescriptor` を強制して SSU バグに当たるため **SDK 待ち**。実機検証というより待ちのタスク
- **`.onAppIntentExecution` の cold start 問題**: そもそも今のコードベースでは `.onAppIntentExecution` をどこでも使っていない (`@Dependency` + `perform()`、それに `AppIntentSceneDelegate` に移行済み) ので、現時点では検証対象が無い状態です。再導入するときに「`@State` の path が未構築」「シーンの activation conditions 未設定」「`supportedModes` に foreground が無い」の 3 仮説を潰す、というメモだけ残しました

このうち **Control まわりは実機で決着しました**。dialog も snippet も Control では提示されないこと、Control のフィードバックは `perform()` 完了時の自動リロードによるコントロール自身の再描画であること、それにともなって `.controlWidgetStatus(_:)` を撤去したことまで含めて [5/N](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls) に書き直しました。実機の Control Center を触って初めて分かったことが多くて、シミュレータのビルドが通ったところで満足していると、到達不能なコードにも気付けないんだなというのは反省点です。

## 公式サンプル 4 本と突き合わせた

セッションの書き起こしを洗い直したのに続いて、WWDC 2026 の App Intents 系 **公式サンプル 4 本** (CometCal / UnicornChat / CosmoTunes / PhotosDomainExample) を落としてきて、自分の実装と 1 項目ずつ突き合わせるということもやりました。

セッションとは出てくるものが違って、**セッションでは触れられない粒度の作法** がコード側に書いてあります。今回そこから拾ったのは、表示表現のローカライズ (ランタイム値をキーにしない)、Siri が subtitle を読み上げること、donation の置き場所、`attributeSet` と `indexingKey:` のキー衝突、onscreen annotation の適用先、といったあたりでした。どれも「知らないと踏むけれど、踏んでも壊れたように見えない」種類のもので、6/N と 8/N に反映しています。

一方で、**サンプルにも古い書き方は残っています**。`openAppWhenRun` のような旧 API を使っているものもあるので、「サンプルにこう書いてあるから正しい」ではなく「今のドキュメントと突き合わせてどうか」まで見る必要がありました。

取り込み方で 1 つ引っかかったのも書いておくと、**サンプルをリポジトリの中に展開してはいけません**。Xcode の同期グループがサンプルの `.xcodeproj` を拾って、追跡下の `project.pbxproj` に project reference として書き込んでしまいます (`.gitignore` は効きません)。リポジトリの外に置くのが安全でした。zip の実 URL は各ドキュメントページの JSON (`https://developer.apple.com/tutorials/data<path>.json` の `sampleCodeDownload.action.identifier`) から引けます。

## まとめ

- 本編は「実機で詰まった話」、WWDC 2026 編は「採用していいか / 設計判断」と、軸を分けて書いている
- 最初に並べた将来トピックのうち、Visual Intelligence / Interactive Snippets / Intent Modes の一部は WWDC 2026 編で片付いた
- FoundationModels (端末内 LLM) と `SpotlightSearchTool`、それに寄付 (`IntentDonationManager`) は「やらないと決めた」もの。主眼から外れるか、設計の核と両立しないため
- 残りの検証待ち (watchOS / visionOS の実機 / Spotlight ラグ / macOS 細部 / reminder 本体適合 / `.foreground(.deferred)` / `LoadResult<T>` / `PlaceDescriptor` の復帰) は、手元の機材と検証コストで順番が決まる予定
- 書き溜めた「制約」をセッション書き起こしと全数突き合わせたら、断定しすぎ・理由付けの誤り・出典の取り違えがまとめて出てきた。「セッションで説明されていたこと / API ドキュメントで知ったこと / 自分がビルドして観測したこと」、それに「そこから推論したこと」は、後から見分けられる形で分けて書いておかないと直せなくなる
- 確かめるときは **正常なはずの側も一緒に並べる**。片側だけ見ていると、同じ現象がぜんぜん違う原因に見える

書ける段階になり次第、ここから本編へ昇格させていきます。

## 更新履歴

本文は常に最新の状況に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-28**: 決着したものを反映 (`.foreground(.dynamic)` は当て先なしで終了 / `UndoableIntent` は採用 / 寄付と `SpotlightSearchTool` は「入れない」/ `UISceneAppIntent` は cold start 目的で採用 / watch の追加が無音で失敗していたのを修正)。実機検証待ちの一覧を現状に合わせて書き直し。「5 つ目の型: 片側しか見ていないのに確かめた気になる」と、公式サンプル 4 本との突き合わせの節を追加
- **2026-08-13**: `#Predicate` の Optional 制約はマクロ固有と確定 (toolchain 差ではない)。`UISceneAppIntent` は Package スコープが障壁ではないと確定し、正しいガード (`&& !os(watchOS)`) を反映。知見に根拠ラベルを付ける運用に触れた
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: 「推論を実測と並べて書いてしまう」という 4 つ目の型を追加 (Control の snippet 非対応が実測ではなく肯定リストからの推論だった件)。Control まわりの実機検証待ちが決着したので一覧から外した
- **2026-08-11**: 「制約を全部洗い直した」節と、実機検証待ちに積み増しになったものの一覧を追加。`.system.searchInApp` の出典を **343** に戻した (2026-08-05 に 344 と直したのが誤りだった)。`@ComputedProperty` の出自も 275 に再訂正。`PlaceDescriptor` の SSU バグが beta 5 でも未修正であることを反映。あわせて記事全体を、日付を追う書き方から「今どうなっているか」を先に書く形へ整理
- **2026-08-05**: セッションを WWDC 2022 まで遡って洗い直した節を追加。トピック K (`UndoableIntent`) を追加
- **2026-07-28**: トピック J (`PlaceDescriptor` をネイティブ型に戻す) を追加。`TransientAppEntity` の採用を反映
- **2026-07-08**: `.system.search` が `.system.searchInApp` にリネームされたのを反映
- **2026-07-02**: 採用候補 (トピック I) の検証結果を反映
- **2026-06-24**: WWDC 2026 の SwiftData レビューで整理できたものの節を追加

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

### I. WWDC 2026 セッションを読み直して増えた採用候補

WWDC 2026 編を公開したあと、セッション情報 (240 / 343 / 344 / 345 / Group Lab) を読み直したら「これは IntentTodo に入れて検証したら記事になりそう」という候補がいくつか出てきました。まだ実装は追えていないので、忘れないように IntentTodo 側へ issue を立てて追跡しています。

- **`@Property(indexingKey:)` でセマンティック Spotlight インデックス** (セッション 240): 本文を `indexingKey` 付きで公開すると、意味ベース検索 / Q&A の対象になる。今は `CSSearchableIndex` の明示登録 (5/N) だけなので、その上の経路を試したい。
- **`Transferable` + `ValueRepresentation` で構造化値エクスポート** (セッション 345): Todo の場所を `PlaceDescriptor` として書き出すなど、cross-app の口を作る。
- **`IntentParameter.valueState` で UpdateTodoIntent** (セッション 344): optional パラメータの「新しい値 / 明示クリア / 据え置き」を `.set(value)` / `.set(nil)` / `.unset` で区別する更新 Intent。
- **コレクション onscreen + 通知 / AlarmKit への entity アノテーション** (セッション 343): 一覧の行に `.appEntityIdentifier(forSelectionType:)`、通知やアラームにも entity-identifier を付けて「3 番目のやつ」のような参照に対応する。
- **`.system.searchInApp` 適合** (セッション 343): `SearchEverythingIntent` をこのスキーマに適合させ、Siri がアプリ自身の検索 UI で結果を出せるようにする。
- **`allowedExecutionTargets` の再検証** (セッション 345): 9/N で訂正したとおり `.widgetKitExtension` も選べるので、これで Primary / FromExtension 分離を畳めないか改めて確かめる。
- **reminder 本体スキーマ適合の優先度** (Group Lab): 「新しい Siri と連携するにはいずれかの App Schema 採用が前提」とのことなので、コアの `TodoAppEntity` を意味理解させるには上記 F の本体適合がやはり要る、という位置づけが見えてきた。

(2026-07-02 追記) この候補群、その後 `xcode27` ブランチでひととおり実装・検証まで進んだので、結果をここに書いておきます (詳細はそれぞれの記事に追記済みです)。

- `@Property(indexingKey:)`: 採用しました。`\.title` / `\.contentDescription` にマップ。`indexingKey:` のオーバーロードは iOS / macOS でしか vend されないので `#if` ガードが要ります → [6/N に追記](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- `Transferable` + `ValueRepresentation`: 採用しました。担当者を `IntentPerson`、場所を `PlaceDescriptor` へ export → 同じく [6/N に追記](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- `IntentParameter.valueState`: 採用しました。`UpdateTodoIntent` を新設して三値を `FieldUpdate` というサービス層の enum に写像 → [8/N に追記](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- コレクション onscreen + 通知: 採用しました。一覧に `.appEntityIdentifier(forSelectionType:)` (大きなリストで id を遅延マップする版)、通知に `UNMutableNotificationContent.appEntityIdentifiers` を付与しています。通知側は **永続 AppEntity が必須** で `TransientAppEntity` は不可、というのが引っかかりどころでした。これはどの記事の主題ともずれるので、記録はここだけです。
- `.system.searchInApp` 適合: 採用しました。実装してみたら SDK の正式名は **`.system.search`** で、`SearchEverythingIntent` への適合ではなく遷移専用の別 Intent (`ShowTodoSearchResultsIntent`) を新設する形になりました → [7/N に追記](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents)
- `allowedExecutionTargets` の再検証: **「FromExtension は畳めない」で確定** しました。制御できるのは perform のプロセスであって entity 解決の有無ではない、が理由です → [9/N に追記](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- reminder 本体スキーマ適合: 再評価したうえで **据え置き継続** です → 下の F に追記しました。

ついでの話として、SDK 27 の SwiftUI 新 API (ドラッグ並べ替えの `reorderable()` / `reorderContainer`) に追従したときも、並べ替えの永続化は `ReorderTodosIntent` という Intent として定義しました。ドラッグ確定は `Button(intent:)` に載せられないので View からは Intent と同じ `TodoService.reorderTodos(orderedIDs:)` を直接呼ぶんですが、ロジックの置き場を Intent 側の語彙に寄せておくことで、「アクションはまず Intent として定義する」という 1/N の原則は崩れていません。

## まとめ

- 本編は「実機で詰まった話」、WWDC 2026 編は「採用していいか / 設計判断」と、軸を分けて書いている
- 最初に並べた将来トピックのうち、Visual Intelligence / Interactive Snippets / Intent Modes の一部は WWDC 2026 編で片付いた
- FoundationModels (端末内 LLM) は「やらないと決めた」もの。主眼から意図的に外している
- 残りの検証待ち (watchOS / visionOS / Spotlight ラグ / macOS 細部 / LA crash 再現 / reminder 本体適合 / `.foreground(.deferred)` / `LoadResult<T>`) は、手元の機材と検証コストで順番が決まる予定

書ける段階になり次第、ここから本編へ昇格させていきます。

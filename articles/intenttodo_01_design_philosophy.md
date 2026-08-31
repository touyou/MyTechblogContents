---
title: "App Intents 中心設計とは何か — IntentTodo を題材に整理する (1/N)"
emoji: "🧭"
type: "tech"
topics: ["AppIntents", "SwiftUI", "iOS", "設計"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

みなさんこんにちは。

最近 [IntentTodo](https://github.com/touyou/IntentTodo) という、`App Intents 中心設計` を実践するためのマルチプラットフォーム Todo アプリを作っています。
このアプリで採用している考え方や、実装で見えてきた知見が結構な量になってきたので、自分の整理のためにシリーズとしてまとめていくことにしました。

本記事はその 1 本目で、まず `App Intents 中心設計` という言葉でなにを指しているのか、なぜ採用するのか、を整理します。

## 思想の出どころ

`App Intents 中心設計` は自分の造語ですが、以下 3 つの考え方を統合したアプローチです。

- **App Intent Driven Development** (SwiftLee): コードの再利用とシステム統合を Intent で進める
- **Action-Centered Design** (Vidit Bhargava): アクションを設計の起点にする UX
- **モデルベース UI デザイン**: ユースケース中心設計と Entity-Intent 構造の対応

そして、これは自分が以前 [Liquid Glass と App Intents 中心設計](https://goodpatch-tech.hatenablog.com/entry/liquid_glass_and_app_intents) でも書いた、Liquid Glass 時代に「コンテンツとアクションが本質となる」という話とも噛み合っていると思っています。
UI クローム (装飾) が透明化していくと、相対的に「ユーザーは何ができるか」 = アクションが目立つ存在になります。

## 核となる原則

実装に落とすときは、次の 4 つを守るようにしています。

1. **すべてのアクションは App Intent として定義する**
2. App Intents で定義したアクションは `Button(intent:)` などで直接実行する
3. ロジックの二重実装を避け、App Intents を唯一の実行経路とする
4. **アクションと情報 (Entity) が設計の原子単位**。UI やプラットフォームは二次的

特に 4 番目が大事で、アプリを「画面の集まり」ではなく「Entity (名詞) と Intent (動詞) の集合」として考えはじめると、自然に複数プラットフォーム展開につながります。

## モデルベース UI デザインとの対応

ユースケース中心設計を「誰が」「何を」「行動できる」の三要素で書くとき、これがそのまま App Intents の Entity-Intent モデルに写像できます。

- **Entity (名詞)** = ユースケースの「誰が」「何を」
- **Intent (動詞)** = ユースケースの「行動できる」

これによって、デザインドキュメントと実装の間にきれいな対応が生まれます。実装からデザインを逆算するのも、デザインから実装を起こすのもやりやすくなる、というのがこのアプローチを採用するモチベーションでした。

## 設計プロセス: 最小のスクリーンから始める

`App Intents 中心設計` でアプリを作るとき、自分は以下の順序で進めています。

1. **最小のスクリーンから設計開始**: Apple Watch など、もっとも制約の厳しい環境で本質的なアクションを特定する
2. **アクションを Intent 化**: 特定したアクションを App Intent として定義する
3. **プラットフォーム固有の実装へ展開**: Widget / Live Activity / Control Center / メインアプリへ
4. **メインアプリ UI は最後**: 複数のアクションをクラスター化してスクリーンを設計

iPhone やデスクトップから設計を始めると、画面の中に置きたい要素を全部詰め込みがちで、本質的な「これは Apple Watch でも一発で操作できるか?」という問いを立てにくくなります。
逆に Watch から始めると、自然に「最も大事なアクション 1 つ」に絞らざるを得ず、それを各プラットフォームに展開していく流れに変わります。

## アクションをどこに置くか: 展開先の指針

特定したアクションや情報をどのプラットフォーム / サーフェスに展開するかは、特性に応じて選びます。
IntentTodo で参考にしている指針は以下です。

| コンテンツ / アクションの特性 | 展開先 | 例 |
|---|---|---|
| 毎日確認する情報 | Widget | 今日の Todo 一覧 |
| 頻繁に変わる情報 | watchOS Complication | 次の期限 |
| 繰り返しのアクション | Shortcuts / Siri | Todo 追加 |
| 常時追跡が必要な情報 | Live Activity | 期限 1 時間以内の Todo |
| 素早いアクセスが必要 | Control Center | クイック追加 |
| 物理的なトリガーが自然 | Action Button | 新規 Todo 作成 |
| 没入型・空間的な体験 | visionOS | 空間 UI |

ここで大事なのは、「全部のサーフェスに同じ Intent を実装する」必要はないということです。
「期限が来そうな Todo を完了する」というアクションは Live Activity と Control Center には合いますが、メインアプリの中ではタップで完了できるので Intent からの呼び出しは不要、というように、アクションごとに展開先を選びます。

## 何が嬉しいか

実際にこの設計で IntentTodo を作ってきて、いま実感している「効いている」ポイントは:

- **ロジックの単一経路化**: たとえば `toggleCompletion(todoId:)` 1 つを Siri / Shortcuts / UI Button / Widget Button / Live Activity Button / Control Widget の **6 系統が呼ぶ**。UseCase 層をパッケージとして別に立てるアプローチでは得にくい密度
- **Apple Intelligence との接続が自然**: Intent と Entity を定義しておくと、将来 Apple Intelligence が拡張されたときの恩恵を受けやすい
- **プラットフォーム展開のコスト低減**: 新しいサーフェスが追加されたとき、既存の Intent を呼ぶだけで済むケースが多い

逆に **払っている税** もあります。

- Intent ファイルの数が増えがち
- 同じアクションでも、呼出元によって別の Intent を用意したくなる場合がある (本シリーズで後述)
- 1 アクション追加のセレモニー (Repository → Service → Intent → AppShortcut) の段数が多い

このトレードオフは、今のところメリット側に振り切れていますが、設計を「とりあえず Intent にする」と機械的に当てはめるのではなく、本質的なアクションだけを Intent 化するという判断は引き続き必要です。

## Layered / Clean Architecture の言葉で説明しようとすると

この設計を人に説明するとき、Clean Architecture の同心円の図を借りようとして毎回うまくいきませんでした。`AppIntent` をどのリングに置いても嘘になるので、そのたびに図を描き直していたんですが、最近ようやく「そもそも軸が違う」という整理に落ち着いたので書いておきます。

同心円が成立しているのは、レイヤーが **1 本の軸 (依存方向 = 抽象 ← 具体) だけ** で切られているからです。層の順序が一意に決まることに全面的に依存しています。ところが `App Intents 中心設計` はそこに「**誰が呼ぶか**」という別の軸を持ち込みます。

| | Clean Architecture | App Intents 中心 |
|---|---|---|
| 切っている軸 | 抽象度・依存方向 | **呼出面 (誰が呼ぶか)** |
| 最外周の想定 | Presentation は「自分が書くドライバ」1 個 | UI / Siri / Spotlight / Widget / Control / Live Activity / 他アプリ の **N 個。しかも能力が違う** |
| 境界の性質 | 内部の継ぎ目 (自由にリファクタできる) | **公開契約** (ユーザーのショートカットに焼き付く) |

軸が 2 本あるものを同心円 1 枚に押し込もうとしていたので、`AppIntent` の置き場所が決まらなかったわけです。実際 `AppIntent` は Clean Architecture の語彙で言うと 3 役を同時に担っています。

- **Controller** (入力アダプタ): `@Parameter`、`EntityQuery` による解決、曖昧性の解消
- **Presenter** (出力): `IntentDialog` / Snippet / `DisplayRepresentation`
- **UseCase の入力ポート**: 名前と signature、つまりユースケースの同一性そのもの

そして「UseCase の本体 (手続き)」だけは `AppIntent` に入っていなくて、それが 2/N で書く `TodoService` です。

なので言い方も直しました。自分は長らく「**UseCase 層を廃止した**」と書いていたんですが、これは正確ではなくて、**UseCase の宣言が Intent に、実装が Service に分かれた** というのが実態です。`Packages/` に `UseCase/` が無いのは層が消えたからではなく、宣言側が `TodoAppIntents/Intents/`、実装側が `TodoAppIntents/Services/TodoService.swift` に同居しているから、という話でした。

| Clean Architecture | IntentTodo での実体 |
|---|---|
| Entity | `Domain` (`@Model TodoItem` / `Category` / `SubTask`) |
| UseCase の**宣言** (入力ポート・名前・引数) | `AppIntent` 型 + `@Parameter` |
| UseCase の**実装** (interactor の中身) | `TodoService` のメソッド |
| Controller | `perform()` の前半 + `EntityQuery` |
| Presenter / ViewModel | `IntentDialog` / Snippet / `DisplayRepresentation` / SwiftUI View |
| Gateway (Repository interface) | `TodoRepositoryProtocol` |
| DB / Framework | `SwiftDataTodoRepository` |

図にするなら同心円ではなく **砂時計 (bowtie)** だなと思っています。同心円は「リング」を強調しますが、この設計で言いたいのは真ん中の **くびれ** の方なので、形が合いません。

```
 UI  Siri  Spotlight  Widget  Control  LiveActivity  他アプリ   ← 呼出面 (対等・能力が違う)
  \    \      |         |        |          /          /
   ────────── Intent + Entity ──────────                      ← くびれ = 公開契約 (最も凍る)
                    │  ┊
              TodoService  ┊                                  ← 1 行為の不変条件・副作用
                    │      ┊ ← 読み取り (EntityQuery) は直通
           TodoRepositoryProtocol
                    │      ┊
              SwiftData / CloudKit
```

この形にすると、同心円では言えなかったことが 2 つ言えます。**UI は特権的な最上層ではなく、Siri と対等な呼出面の一つ** だということ (`Button(intent:)` を必須にしている理由がそのまま図から出ます) と、**呼出面ごとに能力が違う** ということです。後者は 5/N で書く「Control では dialog も snippet も出ない」「アプリ内の `Button(intent:)` からは `requestConfirmation` が呼べない」みたいな話で、同心円だと外側が全部同じ Presentation に見えてしまって、この差が図から消えます。

コードの置き場を決めるときは、この 3 つで判定しています。

1. **ユーザーやシステムが名前で呼べる行為か** → Intent (宣言)
2. **「1 行為の完了」に紐づく不変条件・副作用があるか** → `TodoService`
3. **1 レコードの永続化の言い換えか** → Repository

Layered の説明が「UseCase と Repository の使い分けが分からない」と言われがちなのは、例として `createTodo()` → `repository.create()` みたいな **素通し** を出してしまうからだと思っていて、差が出るものを並べた方が早いです。`toggleMostUrgentTodo()` は fetch + mutate の 2 呼び出しがユーザーには 1 行為だし、undo 用の `snapshot()` / `restore()` は「**同じ id で**戻す」という不変条件を持っていて、Repository は id の意味論を知りません。いちばん強いのが変更後の後処理 (`dataDidChange()`) で、**「1 行為が完了した」ことを知っているのは UseCase 層だけ** です。Repository の `update()` は自分が行為の途中なのか終端なのかを判別できません。

最後に、Clean Architecture と本質的に反転しているところが 2 つあります。1 つは **凍る方向が逆** なこと。Clean Architecture は「内側 = 安定した方針、外側 = 揺れる詳細」ですが、App Intents 中心だと外周の Intent 型名・parameter 名・`AppEnum` の raw value が **ユーザーのショートカットに永続化されていて、いちばんリファクタできません**。内側の `TodoService` の方がよっぽど自由に触れます。もう 1 つは **依存逆転の目的** で、Clean Architecture の「DB を差し替えられる」はほぼ使われない口実になりがちですが、ここでは `TodoRepositoryProtocol` が **プロセス境界** で効きます (Widget Extension とメインアプリで同じロジックが別プロセスに載る、という 2/N の話です)。層の対価が実際に回収されている感じがあります。

正直に残る非対称も 1 つ書いておくと、`TodoEntityQuery` のような **読み取り経路は `TodoService` も Repository も飛ばして** ストアに直接到達しています。書き込み経路は必ず `TodoService` を通るので、実態は「書き込み側だけ層が厚い」CQRS 的な非対称です。理由は 9/N で書く「読み取り系 Intent は実行プロセスを固定せず Extension で応答させたい」なので、図でも読みは細い直通線、書きは Service 経由、と分けて描いています。同心円 1 枚だとこの線が引けないのも、砂時計にした理由のひとつでした。

## 次回以降

このシリーズは、本編と WWDC 2026 編の 2 部構成になっています。

本編 (1〜5) は、IntentTodo で実際に踏んだ落とし穴とその設計判断を 1 トピックずつ取り上げます。

- [(2) TodoService と @Dependency: ビジネスロジックの一元化](https://zenn.dev/touyou/articles/intenttodo_02_todoservice_dependency)
- [(3) マルチプラットフォーム Extension の構成 — SPM 化と Delegate 分離](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions)
- [(4) SwiftData + CloudKit 同期 — 互換 schema と落とし穴](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit)
- [(5) App Intents 運用の罠 — Live Activity / Control Widget / Spotlight](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls)

WWDC 2026 編 (6〜10) は、新しい App Intents の API を試してみて分かった設計判断をまとめます。
検証は `xcode27` という別ブランチでやっていましたが、ひととおり終わったので `main` にマージ済みです。
こちらは本編と違って実機まで通せていないものが多いので、「採用していいか / 設計にどう効くか」を軸に、検証の深さ (ビルド / 単体 / 実機) を各記事に明記して書きます。

- [(6) Todo を「システムが理解できる名詞」にする — ネイティブ型とプロパティマクロ](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- [(7) App Schema と system intents — 意味で適合させる効きどころ](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents)
- [(8) 対話的な Intent — requestConfirmation / requestChoice / IntentDialog](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- [(9) 大量処理・実行制御と「適合しない API」の見極め](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- [(10) Visual Intelligence 連携と AppIntentsTesting](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing)

そして [(99) 検証待ち・将来書く予定のトピック](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) は、棚卸しの番外編です。

引き続きどうぞよろしくお願いします。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-28**: Layered / Clean Architecture との対比 (同心円ではなく砂時計) の節を追加。「UseCase 層を廃止した」という言い方を「宣言が Intent に、実装が Service に分かれた」へ訂正。WWDC 2026 編の検証ブランチ (`xcode27`) が `main` にマージされたことを反映
- **2026-08-12**: Primary / FromExtension の 2 系統を持つ話が撤去されたことに追随し、5/N のタイトル表記もあわせて更新

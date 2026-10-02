---
title: "IntentTodo を題材に App Intents 中心設計とは何かを整理する (1/N)"
emoji: "🧭"
type: "tech"
topics: ["AppIntents", "SwiftUI", "iOS", "設計"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

みなさんこんにちは。

最近 [IntentTodo](https://github.com/touyou/IntentTodo) という、`App Intents 中心設計` を実践するためのマルチプラットフォーム Todo アプリを作っています (App Store には `Intento` という名前で出しています)。
このアプリで採用している考え方や、実装で見えてきた知見が結構な量になってきたので、自分の整理のためにシリーズとしてまとめていくことにしました。

本記事はその 1 本目で、まず `App Intents 中心設計` という言葉でなにを指しているのか、なぜ採用するのか、を整理します。

## 思想の出どころ

`App Intents 中心設計` は自分の造語ですが、以下 3 つの考え方を統合したアプローチです。

- **App Intent Driven Development** (SwiftLee): コードの再利用とシステム統合を Intent で進める
- **Action-Centered Design** (Vidit Bhargava): アクションを設計の起点にする UX
- **モデルベース UI デザイン**: ユースケース中心設計と Entity-Intent 構造の対応

そして、これは自分が以前 [Liquid Glass と App Intents 中心設計](https://goodpatch-tech.hatenablog.com/entry/liquid_glass_and_app_intents) でも書いた、Liquid Glass 時代に「コンテンツとアクションが本質となる」という話とも噛み合っていると思っています。
UI クローム (装飾) が透明化していくと、相対的に「ユーザーは何ができるか」 = アクションが目立つ存在になります。

このシリーズの内容は iOSDC Japan 2026 で [世界の中心でAI（App Intents）を叫ぶ](https://speakerdeck.com/touyou/sekai-no-chuushin-de-ai-app-intents-o-sakebu-app-intents-chuushin-sekkei-no-jissen-gaido) として話していて、そのあと [登壇ブログ](https://goodpatch-tech.hatenablog.com/entry/iosdc2026_speaker_blog) でこの Liquid Glass の話をもう少し詰めました。Liquid Glass が当たる UI 部分は、見せ方の責任がどんどん Apple 側に移っています。であれば、そこでインタラクションしたときに何をするか、はアプリの UI に閉じて考えるものではなく、App Intents のようにあらゆる面から使われることが想定された手段で保証しておくべきだよね、というのが自分の言いたかったことです。

## 核となる原則

実装に落とすときは、次の 4 つを守るようにしています。

1. **すべてのアクションは App Intent として定義する**
2. App Intents で定義したアクションは `Button(intent:)` などで直接実行する
3. ロジックの二重実装を避け、App Intents を唯一の実行経路とする
4. **アクションと情報 (Entity) が設計の原子単位**。UI やプラットフォームは二次的

特に 4 番目が大事で、アプリを「画面の集まり」ではなく「Entity (名詞) と Intent (動詞) の集合」として考えはじめると、自然に複数プラットフォーム展開につながります。

逆に 2 番目と 3 番目は、自分が一貫性を守るために選んだ手段です。IntentTodo ではこのプロセス自体を Claude Code の Skills にまとめていますが、それも含めて真似しなくても大丈夫で、ユーザーに届けたい価値が App Intents で表現できていれば、ユーザーはどの面からでもその価値に辿り着けます。守ってほしい理想というより、そうしておくと勝手に価値の届く先が増える近道くらいに思ってもらえればと思います。

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

実際にこの設計で IntentTodo を作ってきて、いま実感している「良かった」ポイントは:

- **ロジックの単一経路化**: たとえば `toggleCompletion(todoId:)` 1 つを Siri / Shortcuts / UI Button / Widget Button / Live Activity Button / Control Widget の **6 系統が呼ぶ**。UseCase 層をパッケージとして別に立てるアプローチでは得にくい密度
- **Apple Intelligence との接続が自然**: Intent と Entity を定義しておくと、将来 Apple Intelligence が拡張されたときの恩恵を受けやすい
- **プラットフォーム展開のコスト低減**: 新しいサーフェスが追加されたとき、既存の Intent を呼ぶだけで済むケースが多い

逆に **払っている税** もあります。

- Intent ファイルの数が増えがち
- 同じアクションでも、呼出元によって別の Intent を用意したくなる場合がある (本シリーズで後述)
- 1 アクション追加のセレモニー (Repository → Service → Intent → AppShortcut) の段数が多い
- `perform()` を手で呼べない (`@Dependency` はシステム経由の実行でしか注入されない) ので、確定は `Button(intent:)` を押す形になる (ドラッグの並べ替えのように Button に載せられないものは例外で、`TodoService` を直接呼んでいる)。たとえば「return で確定して次の行へ」というインライン編集は `onSubmit` に確定を載せられないので成立しない
- `Button(intent:)` は完了を教えてくれないので、シートを出すと閉じる責任の置き場に困る。IntentTodo は `NavigationModel` 経由で Intent に閉じさせるか、どのボタンでも自分で閉じる `.alert` の中に `Button(intent:)` を置く形で逃げている

このトレードオフは、今のところメリット側に振り切れていますが、設計を「とりあえず Intent にする」と機械的に当てはめるのではなく、本質的なアクションだけを Intent 化するという判断は引き続き必要です。

## 実プロダクトでどう優先度を上げるか

この話をすると、いちばん多く返ってくるのが「実プロダクトだと優先度を上げられない」という悩みです。iOSDC Japan 2026 の Siri AI のアンカンファレンスや Ask the Speaker でも、ほとんどこの話でした。Siri AI の登場で対応した方がいいだろうとはみんな思っている、でも Siri がどの程度使われるかは分からないし、Siri AI の日本語対応はまだ先の話なので優先度を上げられない、でも対応しないと Siri から来るユーザーを失いかねない、というジレンマです。

自分はこれをアクセシビリティの話として説明するのがいちばん通るんじゃないかなと思っています。同じ iOSDC であった 2 つのセッションが、この見方を補強してくれました。

[noppe さんのセッション](https://speakerdeck.com/noppefoxwolf/iosdc26) では、ユーザーが価値を受け取る形を決める変数は目的、コンテキスト、インターフェイスの 3 つで、Figma は目的とコンテキストが固定されたインターフェイスを 1 つしか表現できないから、エンジニアがそれ以外の目的やコンテキストに合うようにインターフェイスを柔軟にしていくべき、という話がされていました。セッション自体は UI の話に進んでいくんですが、提供する価値をぶらさずにいろんな手段で届ける、という意味では App Intents がいちばん低コストに実現できる手段なのかなと思います。

[まつじさんのセッション](https://speakerdeck.com/matsuji/small-touches-that-make-your-app-feel-more-like-an-ios-app) は iOS アプリらしくするための細かい工夫の話で、質疑応答での回答 (意訳です) が印象に残っています。Apple の UI が全部素晴らしいわけではないけれど、ユーザーは普段いろんなアプリを使っていて、そのたびにインタラクションがバラバラだと摩擦が起きる。だから iOS らしくすることは UI を素晴らしくするためではなく、その摩擦を最小化するために価値がある、というものでした。App Intents も同じで、フレームワークは完璧じゃないかもしれないし、優先度が下がるこだわりの部分に見えるかもしれない。でもユーザーが Siri や Spotlight を使ったときに対応していなければ、そのアプリは使われないものになってしまいます。

重要性は分かるのに対象が少なく見えて優先度が下がる、でも対応するとあらゆる人にとっての価値につながる、という構造はアクセシビリティそのものです。Liquid Glass に対応することも、iOS らしさを出すことも、柔軟な UI でいろんなデバイスファクタに対応することも、App Intents で Siri や Spotlight からアプリの外に価値を届けることも、全部「ユーザーが価値にアクセスできる可能性を増やす」という同じところに並んでいます。そしてこのときのアクセシビリティは、一部の人や一部の状況にいる人のためのものではなく全ユーザーのためのものなので、App Intents 対応を後回しにする理由にはならないと思っています。

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

最後に、Clean Architecture と本質的に反転しているところが 2 つあります。1 つは **凍る方向が逆** なこと。Clean Architecture は「内側 = 安定した方針、外側 = 揺れる詳細」ですが、App Intents 中心だと外周の Intent 型名・parameter 名・`AppEnum` の raw value が **ユーザーのショートカットに永続化されていて、いちばんリファクタできません**。内側の `TodoService` の方がよっぽど自由に触れます。もう 1 つは **依存逆転の目的** で、Clean Architecture の「DB を差し替えられる」はほぼ使われない口実になりがちですが、ここでは `TodoRepositoryProtocol` が **プロセス境界** で意味を持ちます (Widget Extension とメインアプリで同じロジックが別プロセスに載る、という 2/N の話です)。層の対価が実際に回収されている感じがあります。

正直に残る非対称も 1 つ書いておくと、`TodoEntityQuery` のような **読み取り経路は `TodoService` も Repository も飛ばして** ストアに直接到達しています。書き込み経路は必ず `TodoService` を通るので、実態は「書き込み側だけ層が厚い」CQRS 的な非対称です。理由は 9/N で書く「読み取り系 Intent は (App Shortcut に登録したもの以外は) 実行プロセスを固定せず Extension で応答させたい」なので、図でも読みは細い直通線、書きは Service 経由、と分けて描いています。同心円 1 枚だとこの線が引けないのも、砂時計にした理由のひとつでした。

## 次回以降

このシリーズは、本編と WWDC 2026 編の 2 部構成になっています。

本編 (1〜5) は、IntentTodo で実際に踏んだ落とし穴とその設計判断を 1 トピックずつ取り上げます。

- [(2) TodoService と @Dependency: ビジネスロジックの一元化](https://zenn.dev/touyou/articles/intenttodo_02_todoservice_dependency)
- [(3) Extension の SPM 化と Delegate 分離で組むマルチプラットフォームの App Intents](https://zenn.dev/touyou/articles/intenttodo_03_multiplatform_extensions)
- [(4) SwiftData + CloudKit 同期で詰まる schema 互換要件と落とし穴](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit)
- [(5) Live Activity / Control Widget / Spotlight / Siri で踏んだ App Intents 運用の罠](https://zenn.dev/touyou/articles/intenttodo_05_app_intents_pitfalls)

WWDC 2026 編 (6〜10) は、新しい App Intents の API を試してみて分かった設計判断をまとめます。
検証は `xcode27` という別ブランチでやっていましたが、ひととおり終わったので `main` にマージ済みです。
こちらは本編と違って実機まで通せていないものが多いので、「採用していいか / 設計をどう変えるか」を軸に、検証の深さ (ビルド / 単体 / 実機) を各記事に明記して書きます。

- [(6) Todo を「システムが理解できる名詞」にするネイティブ型とプロパティマクロ](https://zenn.dev/touyou/articles/intenttodo_06_native_types_property_macros)
- [(7) App Schema と system intents で Todo を意味で適合させる](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents)
- [(8) 確認 / 選択 / Snippet / 寄付で Intent を対話的にする](https://zenn.dev/touyou/articles/intenttodo_08_conversational_intents)
- [(9) 大量処理・実行制御と「適合しない API」の見極め](https://zenn.dev/touyou/articles/intenttodo_09_bulk_and_unfit_apis)
- [(10) Visual Intelligence 連携と AppIntentsTesting](https://zenn.dev/touyou/articles/intenttodo_10_visual_intelligence_testing)

そして [(99) 検証待ち・将来書く予定のトピック](https://zenn.dev/touyou/articles/intenttodo_99_future_topics) は、棚卸しの番外編です。

引き続きどうぞよろしくお願いします。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-10-02**: iOSDC Japan 2026 の登壇とその後の登壇ブログを受けて更新。Liquid Glass の話を「見せ方の責任が Apple 側に移るので、操作したときに何をするかは App Intents で保証する」と言い直した。「実プロダクトでどう優先度を上げるか」の節を新設 (アクセシビリティとして説明する / noppe さんとまつじさんのセッションとの接続)。核となる原則の 2 番目と 3 番目は手段であって必須ではない、という補足を追加
- **2026-10-01**: 払っている税に 2 つ追加 (`onSubmit` に確定を載せられない / `Button(intent:)` は完了を教えてくれない)。CQRS 的な非対称の理由に「App Shortcut に登録した読み取り系は固定する」例外を反映。App Store での名前 (`Intento`) を追記。タイトルと目次の表記からダッシュを外した
- **2026-08-28**: Layered / Clean Architecture との対比 (同心円ではなく砂時計) の節を追加。「UseCase 層を廃止した」という言い方を「宣言が Intent に、実装が Service に分かれた」へ訂正。WWDC 2026 編の検証ブランチ (`xcode27`) が `main` にマージされたことを反映
- **2026-08-12**: Primary / FromExtension の 2 系統を持つ話が撤去されたことに追随し、5/N のタイトル表記もあわせて更新

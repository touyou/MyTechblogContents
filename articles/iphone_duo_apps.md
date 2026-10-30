---
title: "個人開発の 8 アプリを iPhone Duo に合わせたときに考えたこと"
emoji: "📖"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["iOS", "SwiftUI", "iPhoneDuo", "Foldable"]
published: false
---

個人で出している iOS アプリを、iPhone Duo に合わせて順番に直していきました。対象は Intento（IntentTodo）、GRAPHICA、Graphica Playground、Toreta、Programming Quiz、チェケラ、FFMultiplier の 7 本と、Duo のために新しく作った月屏風の計 8 本です。

やってみると、直したことはアプリごとにばらばらに見えて、実は同じいくつかの論点に集まっていました。この記事では、アプリ別ではなく論点別に「何が起きて、どう考えて、どう直したか」をまとめます。

先に書いておくと、**Duo の実機は持っていません**。確認はすべてシミュレータと TestFlight で、スクショも撮影スクリプトで撮ったものです。その事情も最後の章にまとめています。

## 閉じた画面は「細くて背の高い iPhone」

閉じた Duo の外側の画面は、普通の iPhone よりずっと幅が細く、縦に長い形です。最初に崩れたのは、固定サイズで組んでいた部分と、横に 1 行で並べていたボタンでした。

![閉じた Duo のチェケラ録音パネル](/images/iphone_duo_apps/checkitout-closed-record.jpg =300x)
*チェケラの録音パネル。今はアイコンだけのボタンに切り替わる*

- **チェケラ**: REC / STOP / PLAY / SAVE の文字が単語の途中で折り返しました。1 行に収まらないときは、大きいアイコンだけのボタンに切り替えるようにしました
- **Programming Quiz**: クイズと結果の画面が縦に入りきらないことがあったので、入りきらないときだけスクロールに逃がすようにしました。上の safe area が 0 になる場面でも、閉じるボタンが画面の端に付かないようにしています
- **FFMultiplier**: チュートリアルの固定サイズをやめました

![閉じた Duo の Programming Quiz](/images/iphone_duo_apps/quiz-closed-question.jpg =300x)

どれも「普通の iPhone の幅なら収まる」前提が隠れていた箇所です。Duo 専用の分岐を足したのではなく、狭いときにどう縮むかを決めただけなので、Split View や大きい文字サイズでも同じように効きます。

## 閉じるとツールバーが右の縦のバーへ移る

閉じた Duo では、ナビゲーションバーの項目が画面の横の縦のバーに並びます。ここで問題になったのは 2 つです。アイコンだけの項目は意味が伝わらないこと、そして入りきらない項目がメニューへ回ることです。

![閉じた Duo の Intento](/images/iphone_duo_apps/intento-closed-list.jpg =300x)

Tech Talk「Raise the bar with iPhone Duo」の指針と照らし合わせて、Intento・GRAPHICA・Playground・Toreta・FFMultiplier で次の 4 つをそろえました。

| やったこと | 中身 |
|---|---|
| タイトルを持たせる | 画像だけのボタンを `Label` にする。見た目は `.labelStyle(.iconOnly)` で同じ |
| role を付ける | 閉じる = `.close`、キャンセル = `.cancel`、保存・追加 = `.confirm`、全消去 = `.destructive` |
| あふれる順を決める | `visibilityPriority` で、最後まで残す項目と先にメニューへ送る項目を決める |
| 自前の ⋯ をやめる | 自作のメニューを `ToolbarOverflowMenu` に入れる |

一番効いたのは 1 つ目でした。Intento では、**アイコンだけのボタンはオーバーフローメニューに載らず、畳まれる代わりに消えていました**。タイトルの無い項目はメニューの行を描けないので、メニューに入れずに捨てられます。`accessibilityLabel` を付けていても、この穴は埋まりません。

あふれる順は、アプリごとに「この画面で何をしに来たか」で決めました。Playground は Parameters / Export / Favorites を最後まで残し、設定と Pro を先に送ります。FFMultiplier は全削除と共有を先に送ります。

role を付けたことで、普通の iPhone では閉じるボタンの × が右上から左上へ移りました。Duo のための変更が、ほかの端末の見た目も少し変えます。

![閉じた Duo の Graphica Playground](/images/iphone_duo_apps/playground-closed-editor.jpg =300x)

## 左右で違う safe area は contentMargins に任せる

Duo は safe area が左右で違います。中身に `padding` を直接付けていると、片側だけ詰まって見えます。

![閉じた Duo の Toreta コレクション](/images/iphone_duo_apps/toreta-closed-collection.jpg =300x)

Toreta と GRAPHICA では、スクロールの外周の余白を `padding` から `contentMargins` に寄せました。余白の量だけ伝えて、safe area の内側でそろえるのはシステムに任せる形です。Toreta のチップの列だけは、余白を打ち消して今までどおり端まで流しています。

![開いた Duo の Toreta コレクション](/images/iphone_duo_apps/toreta-open-collection.jpg)

## 開くと regular 幅の横長（951×669pt）

開いた Duo は 951×669pt、regular 幅になります。iPad に近い扱いです。

Intento では「開くと追加ボタンが無くなる」という報告から調べ始めて、原因が 3 つ重なっていました。

1. `NavigationSplitView` の `columnVisibility` が `.automatic` のままで、この幅ではシステムが `.detailOnly` を選んでいた。ツールバー項目はリスト列に付けていたので、まとめて画面から消えた
2. リスト列を出しても、320pt のバーに 4 項目は入らない。タイトルまでオーバーフローに押し出されていた
3. 上に書いた、アイコンだけのボタンがメニューに載らない問題

3 つ目は自分では見つけられず、「メニューにフィルタだけ残って追加が消える」という使う側の観察が決め手でした。

![開いた Duo の Intento](/images/iphone_duo_apps/intento-open-detail.jpg)

最終的には、起動時の `columnVisibility` を `.all` にし、リスト列のバーを 2 項目に減らし、regular 幅では追加ボタンを詳細列の右下に置きました。`.bottomBar`、`.topBarPinnedTrailing`、`visibilityPriority(.high)` も試しましたが、この幅のバーが持てるのはシステムのサイドバー切替を含めて 2〜3 個で、項目を減らす以外に手がありませんでした。

もう 1 つ、GRAPHICA と Playground でルールにしたのが、**画面を左右に分けるかどうかは `horizontalSizeClass` と縦横で決め、ピクセル幅の閾値では決めない**ことです。開いた Duo を縦に持つと regular でも縦長なので、左右に分けるのは「regular かつ横長」のときだけにしています。判定は 1 か所に置いて子には結果を渡し、子が size class を読み直さないようにしました。

## 折り目で「見る側」と「触る側」を分ける

ここからは、崩れたところを直すのではなく、Duo の形を生かす話です。

iOS 27.1 の `ArrangementView`（split スタイル）を使うと、表示する部分と操作する部分をシステムが分けて配置してくれます。横長なら左右、縦なら上下、半開きなら折り目の両側です。27.1 未満は従来の `VStack` のままにしています。

![開いた Duo の Programming Quiz](/images/iphone_duo_apps/quiz-open-question.jpg)

- **Programming Quiz**: 問題と選択肢を分けました。積んだときは問題を中身の高さに保ち、残りを選択肢に回します。「次の問題へ」ボタンの場所は常に確保して、答えても高さが変わらないようにしました。のちに、折り返した問題文がカードからはみ出す不具合が出ました。はみ出しを測るときの幅を、折り返す前の幅で見積もっていたためで、実際の幅で高さを測って直しています
- **FFMultiplier**: ゲーム画面の数字の表示と、入力のボタンを分けました
- **チェケラ**: 半開きのときは、パッドを折り目の片側に、ロゴ・リスト・操作をもう片側に置きます。形が変わるときは `matchedGeometryEffect` で部品がつながって動くようにしました

![開いた Duo の FFMultiplier](/images/iphone_duo_apps/ffmultiplier-open-game.jpg)

![開いた Duo のチェケラ](/images/iphone_duo_apps/checkitout-open-play.jpg)

<!-- TODO: 半開きの状態のスクショ（チェケラ・FFMultiplier・Quiz）を撮って差し込む -->

## ヒンジの角度そのものを体験にする（月屏風）

7 本を直したあと、Duo でしかできないものを 1 本作りました。月屏風は、ヒンジの角度を月の満ち欠けに対応させたアプリです。0° が新月、180° が満月で、二曲の屏風を開くように月が満ちていきます。

![開いた Duo の月屏風](/images/iphone_duo_apps/tsukibyobu-open.jpg)

- **折り目の余白**: 平らに近づくほど、二扇の間の余白を詰めます。詰め方は描画のパッケージ（ByobuRenderer）に置き、アプリとストア画像の書き出しで同じものを使っています

![折り目の余白の比較](/images/iphone_duo_apps/tsukibyobu-gap-compare.jpg)

- **性能**: 描画を、角度で変わらない層と角度で変わる層に分けました。ヒンジを動かしている間は軽い層だけを描き直すので、1 フレーム約 2ms で済んでいます
- **横持ち**: 上に屏風、下に黒漆の床を置き、ヒンジの角度で床への映り込み方が変わります
- **OS**: 最低 iOS は 27.0 にして、ヒンジと折り目の API は `#available(iOS 27.1, *)` で囲いました。Duo 以外の端末ではスライダーで角度を変えます

![横持ちの Duo と黒漆の床](/images/iphone_duo_apps/tsukibyobu-landscape-floor.jpg =400x)

## 実機なしで確かめる・撮る

最後に、実機を持っていない状態でどう確かめたかです。ここが一番時間を使ったかもしれません。

- **開閉は手で切り替える**: Xcode 27 には Simulator.app が無く、Duo シミュレータの開閉は DeviceHub から手で切り替えます。`simctl` からはできません
- **`simctl io screenshot` は真っ黒**: XCUITest の `XCUIScreen.main.screenshot()` なら撮れます。メニューを開いた状態も写ります
- **開閉の判定**: 開いていても外側の画面を返すことがあるので、画面サイズでは見分けられませんでした。閉じている間の内側の画面はまっ黒で PNG が 100KB ほどに縮むので、それで判定しています
- **向きの情報**: 開いた画面の画像は「表示時に 90° 回す」印（EXIF orientation）を持っているので、消してから使います
- **並列テストは切る**: 並列テストはシミュレータの複製で走り、複製は必ず閉じた状態になります
- **戻るボタンの場所**: 閉じた Duo では戻るボタンも縦のバーに移るので、撮影の台本は識別子でも探すようにしました

開いた画面は内側を横向きの 2853×2007、閉じた画面は 1398×2034 で撮り、ストア画像にも Duo の帯を足しています。

## まとめ

<!-- TODO: まとめを書く -->

- 閉じた画面では、普通の iPhone の幅を前提にしていた箇所が崩れる
- ツールバーは「縦のバーに移る」「入りきらないとメニューへ回る」前提で、タイトル・role・あふれる順を決めておく
- 開いた画面の構成は size class と縦横で決める
- そのうえで、折り目やヒンジ角度を生かす余地がある

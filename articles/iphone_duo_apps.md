---
title: "個人開発の 8 アプリを iPhone Duo に合わせたときに考えたこと"
emoji: "📖"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["iOS", "SwiftUI", "iPhoneDuo", "Foldable"]
published: true
---

個人で出している iOS アプリを iPhone Duo に合わせて順番に直していきました。対象は Intento、Graphica、Graphica Playground、Toreta、Programming Quiz、チェケラ、FFMultiplier の 7 本と、Duo のために新しく作った月屏風の計 8 本です。

この記事では、アプリ別ではなく論点別に「何を前提にして、どう組み直したか」をまとめます。

## 公式ワークショップのすゝめ

実のことを言うと、Duo の実機を自分は買っていません。iPhone は 2 年に 1 回だけ買い替えようと考えており、しかもかなり高いので今回は見送っていました。そのため確認はシミュレータで行い、記事中のスクショも撮影スクリプトで撮っています。

ただ Apple が開催した開発者向けのワークショップで、実機に触れる機会がありました。ワークショップの間は、公式アプリが閉じた画面・開いた画面・折り目まわりでどう振る舞うかを見ながら、Graphica や Graphica Playground、Intento を実機にビルドして調整していました。それでもどうしても決めきれなかったところは、その場で Apple の方に直接聞いています。

シミュレータだけでは開閉の途中や折り目の上にコンテンツが来たときの見え方までは実感できません。一度手に持って動かしてみたことで、この記事にまとめているポイントのほとんどに気づくことができました。

## 閉じた画面で考慮すること

Duo の外側ディスプレイはふつうの iPhone と比べると幅はあまり変わらず、**背がぐっと低い**形です。その分ツールバーやタブバーは画面の下や上ではなく、**右端の縦の列**に移ります。ステータスバーも同じ列に入るので、右側にだけ太い Safe Area ができます。

![Duo の外側ディスプレイの Intento](/images/iphone_duo_apps/intento-closed-list.jpg =300x)
*外側ディスプレイ。ツールバーの項目とステータスバーが右の列に並ぶ*

つまり閉じた画面では縦も横も通常より短い領域になるわけです。最初に崩れたのはこの 2 つをうまく考慮できていなかった箇所でした。

- **Programming Quiz**: 問題文が長いと、問題と選択肢が 1 画面に収まらなくなりました。収まるときはこれまでどおり 1 画面で見せ、収まらないときだけスクロールできるようにしています（`ViewThatFits`）。結果の画面も同じです
- **FFMultiplier**: チュートリアルを固定サイズで組んでいたので、縦に収まりませんでした。なので固定サイズをやめました
- **チェケラ**: 右の列の分横幅が減り、録音パネルの REC / STOP / PLAY の文字が単語の途中で折り返しました。1 行に収まらないときは、文字を外してアイコンを大きくしたボタンに切り替えます

![外側ディスプレイのチェケラ録音パネル（文字サイズ最大）](/images/iphone_duo_apps/checkitout-record-icons-expanded.jpg =300x)
*文字サイズを最大にした外側ディスプレイ。REC / STOP / PLAY が入りきらず、アイコンだけのボタンになる*

どれも Duo 専用の分岐ではなく、「縦が足りないとき」「横が足りないとき」にどう縮むかを決めただけです。なので横向きの iPhone や Split View でも同じように縮んでくれます。

チェケラの録音パネルは、文字付きのボタンが 1 行に入らなければアイコンだけの版に切り替えています。`ViewThatFits` は候補を上から順に試して、最初に収まったものを表示するので、同じボタンの並びを 2 つ渡しています。

```swift
ViewThatFits(in: .horizontal) {
    // 1 つ目: 文字付きのボタン。横 1 行に収まればこちらを表示する
    transportButtons
    // 2 つ目: 収まらないときは、同じボタンを文字なし・大きめにして表示する
    transportButtons
        .labelStyle(.iconOnly)
        .controlSize(.large)
}
```

## ツールバーは右の列に移る前提で整理する

バーが右の縦の列に移ると、項目は上から下へ 1 列に並びます。並べられる数は少なく、入りきらない項目はメニュー（⋯）へ回ります。

最初から全部を決めていたわけではありません。文字だけのボタンが上に取り残されることも理解はしていました。ですがある程度整理したつもりで外側ディスプレイを見てみると、右の列に移らず**上のバーに取り残される**ボタンがあって、そこがどうにも浮いて見えました。

一番気になったのは Intento の詳細画面の編集ボタンです。参考になるアプリを公式で探していたところ、ジャーナルのアプリが編集をツールバーの ⋯ に収めていて、同じようにできるのでは？と思いつきました。そこで、もともと画面の中にあったお気に入りや削除のボタンもまとめてツールバーに寄せ、入りきらなければ ⋯ に畳まれるようにしました。⋯ に畳まれる形にしておけば、タイトル付きのボタンでも右の列に移ります。お気に入りがメイン、編集と削除は ⋯ の中でサブ、とアクションの優先度も見た目で分かるようになったので、この形を採用しています。

![外側ディスプレイの Intento の詳細](/images/iphone_duo_apps/intento-closed-detail.jpg =300x)
*お気に入りと ⋯（編集・削除）が右の列に入る*

ほかのアプリも Tech Talk「Raise the bar with iPhone Duo」の指針と照らし合わせて、次の 4 つをそろえました。

| やったこと | 中身 |
|---|---|
| タイトルを持たせる | 画像だけのボタンを `Label` にする。見た目は `.labelStyle(.iconOnly)` で同じ |
| role を付ける | 閉じる = `.close`、キャンセル = `.cancel`、保存・追加 = `.confirm`、全消去 = `.destructive` |
| 優先度を決める | `visibilityPriority` で、最後まで残す項目と先にメニューへ畳まれる項目を決める |
| 自前の ⋯ をやめる | 自作のメニューを `ToolbarOverflowMenu` に入れる |

Intento の詳細画面は、だいたい次のような形です。

```swift
.toolbar {
    ToolbarItem(placement: .primaryAction) {
        Button(intent: ToggleFavoriteIntent(todo: entity)) {
            // 見た目はアイコンだけでも、Label でタイトルを持たせておく（⋯ に畳まれたときの行になる）
            Label("お気に入り", systemImage: entity.isFavorite ? "star.fill" : "star")
                .labelStyle(.iconOnly)
        }
    }
    // 編集と削除はお気に入りより優先度が低いので、1 つのメニューにまとめる
    ToolbarOverflowMenu {
        Button {
            navigationModel.showAttributeEditor()
        } label: {
            Label("編集", systemImage: "pencil")
        }
        Divider()
        Button(role: .destructive) {
            isConfirmingDelete = true  // 確認ダイアログを出してから消す
        } label: {
            Label("削除", systemImage: "trash")
        }
    }
}
```

タイトルが要るのは、**アイコンだけのボタンはメニューに載らない**からです。タイトルの無い項目はメニューの行を描けないので、畳まれる代わりに捨てられます。`accessibilityLabel` を付けていても、捨てられる挙動は変わりません。

チェケラの録音パネルは、もとは自作のシートで、× と SAVE をパネルの中に置いていました。これをシステムのシートに変え、× には `.close`、SAVE には `.confirm` の role とタイトルを付けてシートのツールバーに載せると、外側ディスプレイでは 2 つとも右の列に移ります。シートにしたことで、下にスワイプして閉じることも可能になりました。

```swift
.toolbar {
    // role を付けると、グリフと置き場所をシステムが決めてくれる
    ToolbarItem(placement: .cancellationAction) {
        Button("閉じる", systemImage: "xmark", role: .close) { onClose() }
    }
    // 保存はこのシートの主役なので、畳まれない位置に固定する（iOS 27 から）
    ToolbarItem(placement: .topBarPinnedTrailing) {
        Button("保存", systemImage: "square.and.arrow.down", role: .confirm) { onSave(title) }
    }
}
```

![外側ディスプレイのチェケラ録音パネル](/images/iphone_duo_apps/checkitout-closed-record.jpg =300x)
*× と保存がシートのツールバーに載り、右の列に移る*

Programming Quiz の閉じるボタンも、画面の左上に自前で置いていたものをツールバーに移し、`.close` の role とタイトルを付けました。外側ディスプレイでは右の列に入るので、問題文の上の行が丸ごと空きます。Intento の設定画面の閉じるボタンも `.close` にしたところ、ふつうの iPhone でも × が右上から左上へ移りました。Duo のために整理したことで、ほかの端末の見た目も少し変わりますが、これはネイティブの推奨レイアウトに従った形になったとみてポジティブに受け止めました。

![外側ディスプレイの Programming Quiz](/images/iphone_duo_apps/quiz-closed-question.jpg =300x)

優先度はアプリごとに「この画面で何をしに来たか」で決めました。Playground のエディタは Parameters / Export / Favorites の優先度を高くして最後まで右の列に残し、設定と Pro は優先度を下げて先に ⋯ へ畳まれるようにしています。FFMultiplier は、全削除と共有の優先度を下げました。

Playground ではこの指定を小さな extension にまとめて、画面ごとに「最後まで残す／先に畳む」だけを書くようにしています（`visibilityPriority` は iOS 27 から）。

```swift
extension ToolbarContent {
    @MainActor @ToolbarContentBuilder
    func overflowOrder(_ order: ToolbarOverflowOrder) -> some ToolbarContent {
        // .last = 最後まで右の列に残す、.first = 先に ⋯ へ畳む
        if #available(iOS 27.0, *) {
            visibilityPriority(order == .last ? .high : .low)
        } else {
            // iOS 26 以前は順序を指定できないので、何もしない
            self
        }
    }
}
```


![外側ディスプレイの Graphica Playground](/images/iphone_duo_apps/playground-closed-editor.jpg =300x)

Intento の追加ボタンは、一番よく押すのでフローティングボタンのように使いたく、どこに置くかを何度か試しました。リスト列のバーに置くと、この幅で持てる 2〜3 個に埋もれてメニューに畳まれます。リスト列の下に置くと、リスト列を閉じたときに一緒に消えます。最終的に、広い画面では**詳細の列の下のツールバーの右端に、目立つ丸い `+`** を置く形に落ち着きました。リスト列を閉じても届き、詳細の中身にも重なりにくい位置です。

![開いた Duo の Intento](/images/iphone_duo_apps/intento-open-list.jpg)
*追加は詳細の列の右下に置く*

## 左右で違う Safe Area は contentMargins に任せる

右の列があるので、Duo は Safe Area が左右で違います。中身に `padding` を直接付けていると、片側だけ詰まって見えます。Toreta・Graphica・Playground ではスクロールの外周の余白を `padding` から `contentMargins` に寄せました。余白の量だけ伝えて、Safe Area の内側でそろえるのはシステムに任せる形です。

```swift
ScrollView {
    // 中身には padding を付けない
}
// 余白はスクロールに伝える。左右で違う Safe Area の内側にそろえるのはシステムに任せる
.contentMargins(.horizontal, Self.contentMargin, for: .scrollContent)
.contentMargins(.bottom, 24, for: .scrollContent)
```

横スクロールの列は扱いを分けました。Toreta のコレクション画面のチップの列は、余白を打ち消して右の列の下まで流しています。見出しやカードは Safe Area の内側に置いたままです。

ただ右の列の下に潜った部分は、そのままだとツールバーとチップが重なって読みにくくなります。そこで**右の列に近づくほど強くなるぼかし**（**Progressive Blur**）をかけました。SwiftUI には場所によって強さが変わるぼかしが無いので、Metal の `layerEffect` で画面上の位置に応じてぼかしています。レイヤーに焼いてから処理するので、中にガラスのビューを入れるとガラスが描かれない点には注意が要ります。Playground のヒントのチップの列も同じ仕組みです。

![外側ディスプレイの Toreta コレクション](/images/iphone_duo_apps/toreta-closed-collection.jpg =300x)
*チップの列は右の列の下まで流し、潜った部分をぼかす*

## 折り目を避けてレイアウトする

折り目が問題になるのは平らに開いたときではありません。**本のように半開きにした状態**（**Book Posture**）です。平らに開いていれば画面は 1 枚の広い画面として見えるので、ふつうに並べれば大丈夫です。半開きにすると折り目の部分が奥へ引っ込み、そこにかかった文字やカードが読みにくくなります。

ワークショップで公式アプリを見ていて、この扱いは一番真似したいと思いました。たとえばフィットネスアプリでは半開きのときにコンテンツが折り目をまたがないように避けるような実装がされていました。Graphica の作品一覧と Playground のレッスン一覧では、これを真似しました。

![平らに開いた Duo の Playground 学ぶ](/images/iphone_duo_apps/playground-learn-flat.jpg)
*平らに開いたとき。ふつうの 2 列で並べる*

![半開きの Duo の Playground 学ぶ](/images/iphone_duo_apps/playground-learn-book.jpg)
*半開きのとき。列の間を折り目の幅まで広げ、カードが折り目をまたがないようにする*

### 折り目の位置は reservedRegions で取る

`LazyVGrid` や `GridItem` には、折り目を避ける指定がありません。ワークショップで聞いて、ネイティブには無いことを確かめました。なので格子は自前の `Layout` で組んでいます。

折り目の位置は iOS 27.1 の `GeometryProxy.reservedRegions(kind: .division)` で取れます。Duo 以外の端末では nil、避ける必要がない状態では幅 0 で返ってくると教わったので、それを使いました。端末や状態ごとに分岐を書かなくても、格子の計算に共通で挟んでおくだけで、半開きのときだけ折り目の幅が列の間の隙間に入ります。

Playground では `GeometryProxy` に、このビューの中を縦に通る折り目だけを取り出す extension を足しています。

```swift
extension GeometryProxy {
    /// このビューの中を縦に通る折り目の左右端。無いときは nil
    var verticalFold: ClosedRange<CGFloat>? {
        guard #available(iOS 27.1, *) else { return nil }
        return reservedRegions(kind: .division)
            // 有効で、縦長で、このビューの内側にある折り目だけを拾う
            .first { region in
                let frame = region.frame
                return region.isActive && frame.height > frame.width
                    && frame.minX > 0 && frame.maxX < size.width
            }
            // 折り目の左端〜右端。格子はこの幅をそのまま列の間の隙間にする
            .map { $0.frame.minX...$0.frame.maxX }
    }
}
```

- **格子は列の間を折り目にする**: Playground のレッスン一覧（学ぶ）と、Graphica の作品一覧（ギャラリー・マイページ）の格子は、開いたときに 2 列にします。折り目があれば、その幅をそのまま列の間の隙間にします
- **分かれ目は割合で持つ**: 折り目の値は、配置の 1 フレーム後にしか届きません。最初は列の幅を絶対値で持っていたら、開閉のたびに左の列だけガタつきました。分かれ目を幅に対する割合で持つと、幅のアニメーションに両方の列が追従し、遅れて届く補正もアニメーションでならせます
- **はみ出すものは止める**: Playground のトップのガラスのカードは、折り目の手前で止めます

![半開きの Duo の Graphica ギャラリー](/images/iphone_duo_apps/graphica-gallery-book.jpg)
*Graphica のギャラリーも、半開きでは列の間が折り目に来る*

### バランスより「かぶせない」、Posture に寄せすぎない

ワークショップではこの対応について Apple の方に相談もしました。左右の列の幅のバランスを完璧にそろえるより、**半開きのときに折り目にコンテンツをかぶせないことのほうが大事なので、いい対応ですよ**、と言ってもらえました。折り目を列の間に合わせると、左右の列の幅に差が出ることがあり、そこに悩んでいたので、優先順位がはっきりして助かりました。

そのとき、**特定の Posture（閉じた・半開き・平ら、といった形）に最適化しすぎないほうがいい**という考え方も教えてもらいました。1 つの形でだけ完璧な比率を作り込むと、ほかの形や開閉の途中で崩れます。どの形でも成り立つ最低限のこと、ここでは「折り目にコンテンツをかぶせない」を守り、細部のバランスは追いすぎないようにしました。左右の差を許容してよいと判断できたのは、この考え方があったからです。

一方で、**横スクロールの列は折り目を避けなくてよい**そうです。横に流れるものは指で動かせるので、折り目の上に来ても、ずらせば読めます。実際 App Store やミュージックのアプリはもともと横スクロールの列が多いレイアウトなので、折り目の問題を避けられていました。Playground のホーム画面も、ヒントのチップやプリセットのカードを横スクロールで流していて、こちらは折り目を気にせずそのまま流しています。

![開いた Duo の Playground ホーム](/images/iphone_duo_apps/playground-open-home.jpg)
*横スクロールの列は、折り目をまたいでもよい*

## 画面を分けるかは Size Class と縦横比で決める

開いた Duo は横が regular になり、iPad に近い扱いです。広い画面では表示できるコンテンツを増やしたいので、「左右に分けるか、1 カラムに積むか」を決める必要があります。これはもともと Size Class で決めるつもりでした。ところが実装を AI に任せてみると、2 か所で意図とずれていました。

1 つはピクセル幅の閾値で決めていたことです。Graphica では幅が一定以上なら広い画面として扱う形で書かれていました。でも Duo の開いた幅や iPad の 2/3 幅のように、閾値の前後に来る形は増え続けます。ここは Size Class に直しました。

もう 1 つは**一方向の Size Class だけで決めると崩れる**場面があったことです。Playground のレッスン画面は、広い画面では「説明と絵」を左、「コードとヒント」を右に分けます。ところが、開いた Duo や iPad を**縦に持つと、regular なのに縦長**です。親の画面は「regular かつ横長」で判定して 1 本のスクロールに積んでいたのに、その中の子ビューが Size Class だけを見て絵とコードを左右に並べていました。結果、**1 本のスクロールの中に左右の列ができる**中途半端な画面になりました。

![開いた Duo の Playground レッスン](/images/iphone_duo_apps/playground-open-lesson.jpg)
*横に持ったとき（regular かつ横長）だけ左右に分ける*

ここから、次のルールにしました。

- 構成の切り替えは `horizontalSizeClass` を起点にし、ピクセル幅の閾値は使わない
- regular でも、左右に分けるのは**横長のときだけ**。縦横比は Safe Area を足し戻したウィンドウ全体の寸法で見る
- 判定は 1 か所に置き、子には結果（Bool）だけを渡す。子が Size Class を読み直すと、親と条件がずれる
- 幅で決めてよいのは、格子の列数のような**中身の詰め方**だけ

Playground のレッスン画面では、判定はこの 1 か所だけです。

```swift
@Environment(\.horizontalSizeClass) private var sizeClass
@State private var isWiderThanTall = false

// 左右に分けるのは「regular かつ横長」のときだけ。子ビューにはこの結果だけを渡す
private var usesSplitPanes: Bool {
    sizeClass == .regular && isWiderThanTall
}

// body の中で、Safe Area を足し戻した寸法で縦横を測る
.onGeometryChange(for: Bool.self) { proxy in
    let size = proxy.size
    let insets = proxy.safeAreaInsets
    return size.width + insets.leading + insets.trailing
        > size.height + insets.top + insets.bottom
} action: { isWiderThanTall = $0 }
```

Safe Area を足し戻しているのは、キーボードが出て高さが縮んだだけで、入力中に左右分割へ切り替わらないようにするためです。

### 分ける画面は ArrangementView に任せる

2 つに分けたい画面は、iOS 27.1 の `ArrangementView`（split スタイル）に任せました。`ArrangementView` は横長なら左右、縦なら上下に分け、半開きの Duo では分かれ目を折り目に合わせてくれる仕様です。なので自分は、それに従って表示する部分と操作する部分にコンテンツを割り振っただけです。

FFMultiplier のゲーム画面はこれだけです。

```swift
if #available(iOS 27.1, *) {
    ArrangementView {
        displaySection      // 表示する部分（問題の数字）
    } secondary: {
        keypadSection       // 操作する部分（入力のキー）
    }
    // 左右か上下か、半開きの分かれ目をどこにするかはシステムに任せる
    .arrangementViewStyle(.split)
} else {
    // iOS 27.1 より前は従来どおり縦に積む
    VStack(spacing: 0) {
        displaySection
        keypadSection
    }
}
```

- **Programming Quiz**: 問題と選択肢を分けました。「次の問題へ」ボタンの場所は常に確保して、答えても高さが変わらないようにしています
- **FFMultiplier**: ゲーム画面の数字の表示と、入力のボタンを分けました
- **チェケラ**: 半開きのときは、パッドを折り目の片側に、ロゴ・リスト・操作をもう片側に置きます。形が変わるときは `matchedGeometryEffect` で部品がつながって動きます
- **Graphica / Playground**: 作品の詳細と Create、レッスンを左右に分けました

![半開きの Duo の Programming Quiz](/images/iphone_duo_apps/quiz-book.jpg)
*Programming Quiz。問題と選択肢が折り目の左右に分かれる*

![半開きの Duo の FFMultiplier](/images/iphone_duo_apps/ffmultiplier-book.jpg)
*FFMultiplier。問題と入力のキーを分ける*

![半開きの Duo のチェケラ](/images/iphone_duo_apps/checkitout-book.jpg)
*チェケラ。パッドとリスト・操作を分ける*

## ヒンジの角度そのものを体験にする（月屏風）

7 本を直したあと、折り目とヒンジを避けるのではなく**主役にする**ものを 1 本作りました。月屏風はヒンジの角度を月の満ち欠けに対応させたアプリです。0° が新月、180° が満月で、二曲の屏風を開くように月が満ちていきます。

![開いた Duo の月屏風](/images/iphone_duo_apps/tsukibyobu-open.jpg)

折り目は屏風の二扇のつなぎ目として描きます。平らに近づくほど、二扇の間の余白を詰めます。

![折り目の余白の比較](/images/iphone_duo_apps/tsukibyobu-gap-compare.jpg)

描画は角度で変わらない層と角度で変わる層に分けました。ヒンジを動かしている間は軽い層だけを描き直すので、1 フレーム約 2ms で済んでいます。Duo 以外の端末ではスライダーで角度を変えます。

角度は iOS 27.1 の `onHingeChange` で受け取っています。

```swift
if #available(iOS 27.1, *) {
    // ヒンジが動くたびに呼ばれる。角度は 0°（閉じた状態）〜180°（平ら）
    content.onHingeChange { _, context in
        // ヒンジの無い端末では nil。そのときはスライダーの値を使う
        hinge.hardwareDegrees = context.hinge?.angle.degrees
    }
}
```

### 縦向きの Duo には床を敷いて映り込ませる

開いた Duo を縦向きに持つと、扇が上下に並びます。最初は横に広い屏風の絵をそのまま上下の扇に分けて描いていました。でもこれだと、上の扇に月と空、下の扇に手前の景色、と絵が折り目で横に切れて、屏風を開いているようには見えません。

そこで**上の扇に二曲の屏風を立て、下の扇には黒漆の床を敷きました**。床には屏風が上下反転して映り込みます。映りは足元がいちばん濃く、離れるほど薄く、ぼかしを強くしています。舞う花びらや雪も映ります。床はボタンの置き場にもなりました。

![縦向きの Duo の月屏風。左が前、右が床を敷いたあと](/images/iphone_duo_apps/tsukibyobu-duo-floor-before-after.jpg)
*左: 絵を上下の扇に分けていたころ / 右: 上の扇に屏風を立て、下の扇を床にした*

床の見え方もヒンジの角度で変わります。**閉じ気味ほど映りが縦に縮んで濃く、平らに開くほど伸びて薄く**なります。

![縦向きの Duo と黒漆の床](/images/iphone_duo_apps/tsukibyobu-landscape-floor.jpg =400x)

## まとめ

8 本を直してみて、Duo 対応のポイントは大きく 3 つあったと思います。

- **公式の仕様にいかに従うか**: ツールバーはタイトルと role と優先度を持たせて、右の列への移動や ⋯ への畳み込みをシステムに任せる。余白は `contentMargins`、画面の分割は `ArrangementView` に任せる。自前で組んでいたボタンやメニューほど、Duo の画面で浮いていました
- **表示するコンテンツをどう増やしてあげるか**: 外側ディスプレイでは縦も横も短くなるので、収まらないときの縮み方を決める。開いたときは Size Class と縦横比で左右に分け、見せられる量を増やす。判定は 1 か所に置き、ピクセル幅の閾値は使わない
- **折り目という独自の要素にいかに対応するか**: 問題になるのは半開きのとき。`reservedRegions` を共通で挟んで、コンテンツを折り目にかぶせない。左右の比率は追いすぎず、特定の Posture に最適化しすぎない。横スクロールなら避けなくてもよい。月屏風のように、ヒンジそのものを主役にすることもできます

実機を持っていなくても、一度触って公式アプリの振る舞いを見て、迷ったところを聞けたことが一番大きかったです。折りたたみの端末に合わせる機会があれば、まず半開きにして、折り目に何が乗っているかを見てみてください。

今回紹介したアプリは [touyou.dev/bento](https://touyou.dev/bento) にまとめていて、それぞれの LP へのリンクもあります。Duo をお持ちの方も、そうでない方も、よければ触ってみてください。

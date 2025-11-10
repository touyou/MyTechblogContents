---
title: "Skip Fuseが無料化したので再入門してみた"
emoji: "🙌"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["SwiftUI", "Skip", "SkipFuse", "iOS", "Android"]
published: true
---

2025年11月5日、AndroidをSwiftUIで書けるようにするSkipのうちの、ネイティブコンパイルをする[Skip Fuseがインディー開発者向けに無料になりました！](https://skip.tools/blog/skip-fuse-free-for-indies/)

自分はベータ（アルファ？）版の頃からSkipのことは追いつつ、今年春頃からSkip Liteは使えてもSkip Fuseが使えない、課金に踏み切れるほど開発するネタもない...ということでしばらく離れる結果となっていました。

SwiftのAndroidワークグループがSkipの開発者起点ではじまったことが[Swift SDK for Androidリリースに関するブログ](https://skip.tools/blog/official-swift-sdk-for-android/)で明らかになってからまだ日が浅いですが、これによってますますSwiftでAndroidアプリを作る動きが加速していきそうと思います。

というわけでせっかくなのでこのタイミングで自分もSkipに再入門してみようと思いこの記事に書き始めました。

## インストール方法

まずはインストール方法です。ドキュメントはこちら。

https://skip.tools/docs/gettingstarted/

Xcode、Android Studio、Homebrewが事前に必要になります。

走らせる必要があるスクリプトを抜き出すと以下です。ステップバイステップの注意点はドキュメントを参照してください。ちなみに自分は最初のcheckupはXcode26.1をインストールしたばかりでPlatform Supportの最新版が入っておらず怒られました笑

```fish
$ brew install skiptools/skip/skip
$ skip checkup
$ skip android sdk install
$ skip checkup --native
```

その後アクティベーションを行なっておきます。以下がインディー開発者向けのフォームなので`skip hostid`を実行して取得したHost Identifierを元に申請しましょう。

https://skip.tools/purchase/indie/

こちらに書かれている通り、インディーとして認められる条件は

- 2名までの開発者
- 利益が年間30000米ドル未満

であり、クローズドソースにできるのは一つまでとなっています。

話を戻すと以下のようなメールが来るのでSKIPKEY以下をコピーして`~/.skiptools/skipkey.env`に貼り付けます。元からファイルは作成されていると思うので全て削除してから`SKIPKEY:`の行も含めて全て貼り付けてください。

![](/images/skip_retry_entry/skip_mail.png)

こちらのキーの有効期限は6ヶ月になるようです。

## 最初のアプリを作ってみる

ここまできたら最初のアプリを作ってみましょう。
こちらもGetting Startedに載っていますが、以下のコマンドで作ることができます。

```fish
$ skip init --open-xcode --native-app --appid=[バンドルID] [プロジェクト名] [アプリ名]
```

ですのでたとえばバンドルIDを`dev.touyou.SuperTodo`、プロジェクト名を`super-todo`、アプリ名を`SuperTodo`とする場合は次のようになります。

```fish
skip init --open-xcode --native-app --appid=dev.touyou.SuperTodo super-todo SuperTodo
```

こうすると`super-todo`フォルダが作られ、その中に必要なものが作成され、Xcodeが開きます。Xcodeの開き方が若干迷う構成にはなっているかと思うので`--open-xcode`をつけておいて全体像などを把握することが結構おすすめです。

これだけでもいいのですが、最近はマルチモジュールが流行りですね。
それに乗っかりたい場合は以下のコマンドにしてみましょう。三つモジュールができることはもちろんなのですが、謎の力によって名前に応じたいい感じのテンプレートが吐き出されます。

```fish
skip init --open-xcode --native-app --appid=dev.touyou.SuperTodo super-todo SuperTodo SuperTodoModel SuperTodoCore
```

この際、特定の文言を入れてしまうと途中でエラーになります。例えば今使ってきた`SuperTodo`も実は悪い例です。途中で名前からよしなにJavaのパッケージネームになるため、Javaの予約語が入っていると以下のようなエラーになります。（もちろんこの例にしたのはわざとですよ...うん）

```fish
Initializing Skip application super-todo
[✗] The module name "SuperTodo" is invalid because the derived Java package name "super.todo" contains a reserved keyword: "super"
[✗] Skip 1.6.28 init failed with 1 error
See https://skip.tools/docs/faq and https://community.skip.tools for help
See output log for error details: /tmp/skip-init-2025-11-10T05:27:39Z.txt
Error: 2 errors
```

というわけでJavaの予約語が含まれないよう注意を払っていきましょう。
iOSとAndroid向けなのでそうですね...今回は`AporoidTodo`にしておきましょうか。

```fish
skip init --open-xcode --native-app --appid=dev.touyou.AporoidTodo aporoid-todo AporoidTodo AporoidTodoModel AporoidTodoCore
```

というわけで以下のようなプロジェクトが生成されました。

![](/images/skip_retry_entry/first_xcode.png)

なおこのテンプレートプロジェクトは最初からある程度実行することが可能です。この際Androidのシミュレータも起動しておくことで両方にビルドされます。

![](/images/skip_retry_entry/first_simu.png)

実質Todoのようになっているのはあくまで偶然ですが、充実しているため、どう発展させていくかの指針にはなるかと思います。

## 少しいじってみる

それではテンプレートを少し改変してみましょう。
Liquid Glass時代にはタブは`Tab`を、タイトルは`inlineLarge`を採用したいところです。対応しているかわかりませんが`ContentView.swift`の中身を編集してみます。

元々プロジェクトのminimumがiOS 17に設定されていたのでこれを変更して進めます。Xcodeのプロジェクト設定を切り替えるのはもちろんのこと、SPM構成なのでPackage.swift、さらにSkip.envファイルの下にあるAporoidTodoというファイルにもターゲット周りの設定が書いてあるので三箇所を修正しました。

![](/images/skip_retry_entry/target.png)

エラーがなくなったので改修を進めます。コードは以下のように改変しました。

```swift
struct ContentView: View {
    var body: some View {
        TabView(selection: $tab) {
            Tab("Welcome", systemImage: "heart.fill", value: .welcome) {
                NavigationStack {
                    WelcomeView(welcomeName: $welcomeName)
                }
            }

            Tab("Home", systemImage: "house.fill", value: .home) {
                NavigationStack {
                    ItemListView()
                        .navigationTitle(Text("\(viewModel.items.count) Items"))
                        .toolbarTitleDisplayMode(.inlineLarge)
                }
            }

            Tab("Settings", systemImage: "gearshape.fill", value: .settings) {
                NavigationStack {
                    SettingsView(appearance: $appearance, welcomeName: $welcomeName)
                        .navigationTitle("Settings")
                        .toolbarTitleDisplayMode(.inlineLarge)
                }
            }
        }
    }
}
```

実行してみると、無事動きました。どうやらインラインラージはAndroid側では今のところただのラージタイトルのままとして扱われているようですね。

![](/images/skip_retry_entry/new_title.png)

このようにSwiftUIの比較的新しいAPIを使ってもよしなにしてくれるのがSkipのかなりの強みかなと思います。

さりげないところですが、多くのSF SymbolsとMaterial Iconsの対応がとられているため、`systemImage`などで設定したアイコンがしっかり両方のプラットフォームに適した形で出力されているのも重要な特徴です。

Jetpack Composeを併用したい場合や分岐させたい場合は、テンプレートの最下部に例が載っています。

```swift
/// A view that shows a blue heart on iOS and a green heart on Android.
struct PlatformHeartView : View {
    var body: some View {
        #if os(Android)
        ComposeView {
            HeartComposer()
        }
        #else
        Text(verbatim: "💙")
        #endif
    }
}

#if SKIP
/// Use a ContentComposer to integrate Compose content. This code will be transpiled to Kotlin.
struct HeartComposer : ContentComposer {
    @Composable func Compose(context: ComposeContext) {
        androidx.compose.material3.Text("💚", modifier: context.modifier)
    }
}
#endif
```

ここら辺については以下の記事が詳しいので参考にしてください。

https://qiita.com/yamakentoc/items/2a1368fc74a871b73ca9

## まとめ

さわりの部分のみになりましたが、Skipに再入門してみた様子をお届けしました。
離れている間にも進化を続けていたりする部分もあるので、Skip Fuseの有料ライセンスでモチベを砕かれていた自作アプリのSkip化などにも今後挑戦してみたいなと思います。

Kotlin MultiplatformやFlutter/React Nativeなどと比べるとまだ日の浅い技術ではありますが、Swift SDK for Androidの発展と合わさって今後どんどんと進化を続けていくであろうSkip。
ネイティブの手触り感を失わずに両方のネイティブアプリを実装する手段としてかなり有用なので今後も期待していきたいですね。

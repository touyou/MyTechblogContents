---
title: "FlutterでApp Intents/AppFunctionsを構築するライブラリを公開しました"
emoji: "🤖"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["Flutter", "AppIntents", "AppFunctions", "iOS", "Android"]
published: true
---

みなさんこんにちは。

みなさんはiOS/AndroidにおけるMCPをご存知でしょうか？
数年前からiOSでは[App Intents](https://developer.apple.com/documentation/appintents)という仕組みが公開され、これがアプリにMCP的な仕組みを取り入れる先駆けのようなものになっています。
あまり知られていないかもしれませんが、一部の方が使っている[ショートカットアプリ](https://support.apple.com/ja-jp/guide/shortcuts/welcome/ios)、ここで操作できるさまざまなアクションはこのApp Intentsによって実現されるものです。これをSiriなどのAIからも活用できるため、App IntentsがあればアプリのAI活用を一気に進めることができる（かもしれない）というものになります。

自分はこれに直近注目していたのですが、これと似た仕組みがAndroid 16から使えるようになっていると[先日Googleから発表がありました](https://android-developers.googleblog.com/2026/02/the-intelligent-os-making-ai-agents.html)。[AppFunctions](https://developer.android.com/ai/appfunctions)です。

そこで元々App Intentsとの連携をよりやりやすくするために書いてたライブラリを拡張して、iOS/Androidのこれらの仕組みを一括で管理できるライブラリを作ったのでこちらを紹介したいと思います。

https://pub.dev/packages/app_intents

## どんなライブラリ？

ざっくりは紹介したのですが、改めてどういうライブラリか？というとDartでApp Intents / AppFunctionsが書ける、というのがコンセプトになります。

自分は元々iOS畑出身なので、もちろんSwiftで書くこと自体に抵抗感はないのですが、結局Flutter側との連携などをしなければならず往復するのが微妙だなという気持ちがありました。

そこでこのライブラリではベースをDartで書き、コード生成を使ってネイティブ部分は楽をしようというものになっています。

## 使い方

基本的にはREADMEのクイックスタートに従ってもらえばOKです。サンプルアプリとしてTODOアプリを用意しているため、こちらを参考にしていただくことも可能です。

https://github.com/touyou/flutter_intents

リポジトリでわかることを再度説明してももったいないのでここでは実際のプロジェクトで活用した例を紹介したいと思います。

たとえばタブごとに起動するものを用意したい場合は次のように書きます。

```dart
@IntentSpec(
  identifier: 'com.example.openApp',
  title: 'Open App',
  description: 'OPEN_APP_INTENT_DESCRIPTION',
  supportedModes: IntentMode.foreground,
  parameterSummary: 'Open {tab}',
)
class OpenAppIntent extends IntentSpecBase {
  @IntentParam(title: 'Tab', enumType: 'RootTabEnum')
  final String tab;

  const OpenAppIntent({required this.tab});
}

/// ナビゲーション処理は onIntentExecution で行う
Future<void> openAppIntentHandler({required String tab}) async {}
```

enumはこんな感じに定義しておけば良いです。

```dart
@EnumSpec(identifier: 'com.example.rootTab', title: 'Tab')
enum RootTabEnum {
  @EnumCaseDisplay(title: 'Home', imageName: 'home')
  home,
  @EnumCaseDisplay(title: 'Search', imageName: 'search')
  search,
  @EnumCaseDisplay(title: 'Notifications', imageName: 'notification')
  notifications,
  @EnumCaseDisplay(title: 'Profile', imageName: 'profile')
  profile,
}
```

そして、実際の処理はDart側で`onIntentExecution`を定義しておきます。

```dart
void handleIntentExecution(IntentExecutionRequest request) async {
  switch (request.identifier) {
    case 'com.example.openApp':
      final tab = request.params['tab'] as String?;
      switch (tab) {
        case 'home':
           navigationShell.goBranch(0, initialLocation: true);
           break;
        case 'search':
          navigationShell.goBranch(1, initialLocation: true);
          break;
        case 'notifications':
          navigationShell.goBranch(2, initialLocation: true);
          break;
        case 'profile':
          navigationShell.goBranch(3, initialLocation: true);
          break;
        default:
          appLogger.w('Unknown tab: $tab');
          break;
      }
  }
}

// ...
useEffect(() {
  final subscription = AppIntents().onIntentExecution.listen(
    handleIntentExecution,
  );
  return () {
    subscription.cancel();
  };
}, [])
```

ここら辺は各プロジェクトに合わせてください。

なお今回は`IntentExecutionRequest`で値を受け取っていますが、これにはディープリンクで受け取る方式もあります。
重要なのはApp Intentsなどは利用方法によっては実行タイミングでFlutterが起動していない場合があるということです。そのためFlutterがなくても成立する処理にする必要があります。
できることはその分限られてしまうのですが、そこらへんをうまいことコード生成で行えるようにしてあるのもこのライブラリの強みです。

## まとめ

ざっくりにはなってしまいましたがapp_intentsパッケージに関しての紹介をさせていただきました。
まだまだ対応できる機能はあるかと思いますし、AppFunctions側は資料が少なすぎてとりあえず生成できるようにしてみた程度ではあります。

ぜひ気になった方は使ってみてissueでのフィードバックやコントリビュートをお待ちしております。

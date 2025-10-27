---
title: "Swift for Androidがファーストプレビューリリースしたので触ってみる"
emoji: "📱"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["Swift", "Android", "モバイル開発"]
published: true
---

WWDC2025やその後の発表でワーキンググループが結成され話題になっていたSwift for Androidですが、2025年10月24日に初のプレビューリリースが公開されたため、早速触ってみました。

動かすまでに少しつまづくところがあったので、注意点等を紹介します。

## 動かすもの

今回リリース記事として以下の記事が公開されています。


https://www.swift.org/blog/nightly-swift-sdk-for-android/

この記事と同時に、サンプルプロジェクトも公開されており、今回はこれを動かしていきます。

https://github.com/swiftlang/swift-android-examples

## 環境構築について

それでは環境構築です。普段からiOSなどAppleのエコシステムを開発している方でも追加で工程が必要になりそうなので、順を追って説明します。

### Swift SDK / Swiftlyについて

今回のサンプルを動かすには、全体としてSwiftlyというSwift公式のツールと、それで管理できるSwift SDKが必要になります。

インストール手順は以下のドキュメントにあります。

https://www.swift.org/install/macos/

ページトップにある以下のコマンドをコピーして実行しましょう。

```fish
curl -O https://download.swift.org/swiftly/darwin/swiftly.pkg && \
installer -pkg swiftly.pkg -target CurrentUserHomeDirectory && \
~/.swiftly/bin/swiftly init --quiet-shell-followup && \
set -q SWIFTLY_HOME_DIR && source "$SWIFTLY_HOME_DIR/env.fish" || source ~/.swiftly/env.fish
```

### Swift SDK for Androidについて

続いてSwift SDK for Androidをインストールしていきます。
先ほど紹介したページの下部にはインストールコマンドをコピーするボタンがありますが、サンプルプロジェクトで扱えるのは2025/10/16版のSDKで、今コピーできる2025/10/17版ではないので注意が必要です（これはもちろんおいおい変わってくるとは思います。）

実際のインストールはInstructionsというリンクに飛ぶことで出てくるこの記事に従います。

https://www.swift.org/documentation/articles/swift-sdk-for-android-getting-started.html

Android NDKとの連携などもあるので、この記事に出てくる手順は基本的に全て踏むと考えてもらって大丈夫です。最低限を抜き出すと以下のような形です。

```fish
$ swiftly install main-snapshot-2025-10-16
$ swiftly use main-snapshot-2025-10-16
$ swift sdk install https://download.swift.org/development/android-sdk/swift-DEVELOPMENT-SNAPSHOT-2025-10-16-a/swift-DEVELOPMENT-SNAPSHOT-2025-10-16-a_android-0.1.artifactbundle.tar.gz --checksum 451844c232cf1fa02c52431084ed3dc27a42d103635c6fa71bae8d66adba2500
$ mkdir ~/android-ndk
$ cd ~/android-ndk
$ curl -fSLO https://dl.google.com/android/repository/android-ndk-r27d-$(uname -s).zip
$ unzip -q android-ndk-r27d-*.zip
$ export ANDROID_NDK_HOME=$PWD/android-ndk-r27d
$ cd ~/Library/org.swift.swiftpm || cd ~/.swiftpm
$ ./swift-sdks/swift-DEVELOPMENT-SNAPSHOT-2025-10-16-a-android-0.1.artifactbundle/swift-android/scripts/setup-android-sdk.sh
```

ここまでで完了です。残りは自分でプロジェクトを作る場合の話が書かれているので、適宜参考にしてください。

## サンプルプロジェクトを動かす

今回自分はサンプルプロジェクトに関してはAndroid Studioで開いて動かしてみました。
通常のAndroidプロジェクトなどと同様に開いてgradle syncを実行します。

終わったら準備完了です。実行可能な対象としては以下が定義されていました。

- hashing-app
- hello-swift
- hello-swift-callback
- native-activity

hashing-app以外はここまで紹介してきたセットアップのみで動かせるはずです。
hashing-appは追加でswift-javaを利用するため、READMEに書かれているセットアップを追加で行う必要がありそうです。
ただこちら実行してみたのですが、Invalid manifestエラーが出てしまい現状動かせませんでした。

## まとめ

以上、Swift for Androidを触ってみた様子を紹介しました。
コードを見てみると、まだまだJavaやCが露出している味と言いますか、Kotlin MultiplatformでSwiftを利用する際と同じようなぎこちなさを感じるのですが、そこも今後Swiftyに改善されていくところだと思うので引き続き注目していきたいと思います。

そのうちUIはSwiftUIとJetpack Composeで、裏側をSwiftもしくはKotlin好きな方で書くみたいな、そんな世界観が来ると面白そうと思います。

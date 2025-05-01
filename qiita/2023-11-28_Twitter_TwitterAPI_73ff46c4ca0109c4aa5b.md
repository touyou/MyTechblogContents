<!--
title:   1分ナレッジ（2023/11/28 18時現在）ー X（旧Twitter）のシェアリンクバグについて
tags:    Twitter,TwitterAPI
id:      73ff46c4ca0109c4aa5b
private: false
-->
## 何が起こったか？

2023/11/28、X（旧Twitter）の一部のシェアリンクが動かなくなりました。

一例として以下のリンクをXログイン済みのブラウザで開いてみてください。

`https://twitter.com/share?text=helloworld&url=https%3A%2F%2Fgoogle.com`

https://twitter.com/share?text=helloworld&url=https%3A%2F%2Fgoogle.com

すると以下のような画面が出てきます。

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/17dffb94-026e-5ddd-59e2-9a0a6ed48270.png)

謎のCSSが文字として表示されてしまっている上、テキストが空の投稿画面が出てきてしまいました。

## 原因

先ほどのページのURLは以下のようになっています。

`https://twitter.com/intent/tweet?text&#x3D;helloworld&amp;url&%23x3D;https%3A%2F%2Fgoogle.com`

https://twitter.com/intent/tweet?text&#x3D;helloworld&amp;url&%23x3D;https%3A%2F%2Fgoogle.com

このように/shareに飛ぶと、/intent/tweetにリダイレクトで飛ばすという処理がX（旧Twitter）側でなされているようです。今まではここが正しく動いていたはずなのですが、少なくとも本日2023/11/28時点では本来エンコードされるべきでない=や&などもエンコードされてしまい、正しいシェアページに飛べなくなってしまいました。

## 直し方

リダイレクトが壊れているので、リダイレクトさせない（直接リダイレクト先に飛ばす）ようにすれば治ります。

`https://twitter.com/intent/tweet?text=helloworld&url=https%3A%2F%2Fgoogle.com`

https://twitter.com/intent/tweet?text=helloworld&url=https%3A%2F%2Fgoogle.com

以上です。無事正しく内容が入力された状態で開きました🎉

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/4e9f43a1-90d6-dcb4-9738-22d11909e474.png)

## まとめ

明らかにX（旧Twitter）の落ち度ですが、影響範囲がかなり大きいのでみなさん注意しましょう。
なお主要メディアのシェアボタンはすでに正しく飛ぶ方のリンクになるようになっているようでした。

もし過去にTwitterシェアボタンを実装したなぁという方がいれば一度コードでtwitter.com/shareを検索してみることをおすすめします。

## p.s.

Twitterの方が呼びやすいのでいつか戻って欲しいです笑
<!--
title:   UIButtonの画像をUIButtonに対してAspectFitする方法
tags:    Swift,Xcode,iOS,swift3
id:      4fdad9d7b6c6eb5cdccf
private: false
-->
UIButtonに表示させる画像にcontentModeを設定する時、思い通りにいかない人が多いと思うのですが、色々調べていくうちにようやく正解がみえたので共有したいと思います。コードはSwift3ですがSwift2以前でも適切に変更してやれば動きます。

## どうやってボタンにAspectFitを設定するか

UIButtonへのcontentModeの設定、これに関してはいろんな人が書いていて

```swift
btn.imageView?.contentMode = .scaleAspectFit
```

のように書けばもちろんUIButtonの中に入っているImageViewに対してAspectFitになります。ですがこれはあくまで**UIButtonの中に入っているImageViewに対して**というところに注意しなければなりません。もちろんこれで上手くいくこともありますが、AutoLayoutなどで引き伸ばした時に思っていたサイズよりかなり小さくなるケースがあります。

この原因はUIButtonという親クラスに対して中のUIImageViewのサイズ指定が適切に働いていないことが原因です。つまりUIButtonは大きくなっているのに、中のImageViewが小さいままということがおきてしまうのです。



これを避けるためには`contentHorizontalAlignment`と`contentVerticalAlignment`というプロパティを設定します。

以上まとめるとUIButtonに画像をめいっぱいアスペクト比を保ったまま表示するには以下の三行が必要になります。

```swift
btn.imageView?.contentMode = .scaleAspectFit
btn.contentHorizontalAlignment = .fill
btn.contentVerticalAlignment = .fill
```

これを盛り込んだ自作クラスとして予め`@IBDesignable`などを作っておくといいかもしれませんね。
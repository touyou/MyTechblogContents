<!--
title:   [Swift3] UIImageを切り抜く（とおまけ）
tags:    Swift,UIImage,Xcode,iOS,swift3
id:      46fab5a9c0fc38ab48fa
private: false
-->
[こちらのStackOverflow](http://stackoverflow.com/questions/38568288/swift-3-0-how-to-call-cgimagecreatewithimageinrect)で既出ですが、Swift3でUIImageを特定の大きさに切り抜く方法が変わったのでメモしておきます。

### Swift2まで
Swift2までは以下のようなコードで切り抜くことができました。

```swift
let imageRef = CGImageCreateWithImageInRect(image.CGImage, CGRect)
let image = UIImage(CGImage: imageRef)
```

### Swift3から
Swift3では次のように変わります。

```swift
let imgRef = image.cgImage?.cropping(to: CGRect)
let image = UIImage(cgImage: imgRef!, scale: image.scale, orientation: image.imageOrientation)
```

## おまけ
この変更とともに、CGほにゃらら系の宣言の仕方が変わっています。いままでは`CGRectMake`や`CGSizeMake`などでも宣言できていましたがこれが廃止されました。またイニシャライザについて少し種類が増えているようです（？）

### 最後に
Swift3やXcode8について他にも記事を書いているので参考にしてください。

- [[iOS10][Xcode8] あらたにinfo.plistに追記が必要になった項目まとめ](http://qiita.com/touyoubuntu/items/a86da98528b24880f590)
- [各種ライブラリのSwift3での変更点](http://qiita.com/touyoubuntu/items/d40d2603aa066d48887e)
- [有名ライブラリのXcode8 GM対応ブランチ早見表](http://qiita.com/touyoubuntu/items/8359967cdd40c120ef69)
<!--
title:   Swiftで競技プログラミングを実際にやってみたところ予想以上につまづいた話
tags:    Swift,競技プログラミング
id:      1ecc57efd6abbe53bfb6
private: false
-->
# きっかけ
朝方、なんとなくAtCoderをみてみたところSwiftが使えるようになっていたことに気付いたので早速ABCの問題をSwiftで解いてみることにしました。そのときめちゃくちゃつまづいたのでそれをまとめます。

ちなみに４月に関連した記事を書いているのでそちらもどうぞ

- [Swiftで競技プログラミング](http://qiita.com/touyoubuntu/items/1d8a9c00a283e98bc8e4)

# つまづいたとこ
## 手元でテストが出来ない問題
まず第一の問題としてOS Xでは`Darwin`、Linuxでは`Glibc`と異なる標準ライブラリを使わなければいけないので、手元でも実行しようとすると当然こういうのを毎回書かなければなりません。

```swift
#if os(Linux)
    import Glibc
#else
    import Darwin
#endif
```

そしてなんとか実行出来るようになったのはいいのですが、`swift file.swift`がコンパイルエラーはすぐに出すのになかなか実行ファイルをつくるのが遅い...というかもはや固まったみたいになって全然出来る気配がないので、結局AtCoderのコードテスト機能を使うほかなくなってしまいました。

## Paizaで実行できてたはずのテンプレートがいろんな要素で動かない問題
Paizaのコンパイルエラーを通ったような気がする４月につくったテンプレートを動かしてみたところ、めちゃくちゃ怒られました。
### substringWithRangeなんてないよ
こちらOS Xなら普通に使えるはずのStringのメソッドですが、Linux環境では無いと怒られ使えませんでした。。。
### Range<T>のTちゃんと定義して
これは僕の知識不足なところもあるのですが、最初

```swift
var indices: Range {
    return self.characters.indices
}
```

とStringのextensionに書いていたら怒られました。正しくは

```swift
var indices: Range<String.CharacterView.Index> {
    return self.characters.indices
}
```

## いろんな実装がめんどくさい問題
テンプレートに普通の言語ならいらないようなこと一杯書いているあたりからお察しなのですが、いろんな実装がかなりめんどくさいです。
### 入力をするためにはStringのextension文書かなきゃ不便
Swiftの入力は`readLine()`関数なんですが、これ空白区切りなどを入力するときは`split()`が必須ですよね。ですがこれは`CollectionType`のもっているメソッドなので必ず

```swift
extension String: CollectionType {}
```

とかかなくてはなりません。
### Stringのsubscriptの仕様めんどくさい
いちおう上とあわせてテンプレートで解決していることは解決しているんですが、`s[i]`といったようなアクセスの仕方がString型の場合非常にめんどくさいです。以下のように書きます。

```swift
s[s.startIndex.advancedBy(i)]
```
### Optionalが返ってくるところと普通に返ってくるところに見分けがむずかしい
Xcode使えって話になってしまうのですが、他のエディタを使っていると当然その関数の仕様とか見ることはできません。なのでおなじ`Int()`関数でも使うところによってOptional返したり返さなかったりですごく面倒でした。

## 地味に標準ライブラリが遅い問題
これが一番でした。問題となったのは`sortInPlace`というソート関数です。

ABC#041のCの問題、ネタバレしてしまうとMapやらDictionaryで対応表をつくっておいて背の順にソートして出力するというのがシンプルかつおそらく模範解答です。

実際C++やHaskell、Python、Javaといろんな言語で書かれていますがみんな一様にそれぞれの言語のライブラリにあるソート関数をつかってACしていました。


僕も例にもれず、Swiftで以下のような感じに実装しました。

```swift
#if os(Linux)
    import Glibc
#else
    import Darwin
#endif
extension String: CollectionType {}
 
var N: Int = Int(readLine()!)!
var a: [Int] = readLine()!.split(" ").map { Int($0)! }
var res = Dictionary<Int, Int>()
 
for i in 0 ..< N {
    res[a[i]] = i+1
}
 
a.sortInPlace(>)
 
for i in 0 ..< N {
    print(res[a[i]]!)
}
```

~~ですが、返ってきたのはTLE。たしかにほとんどのケースはACしているのですがおそらく入力がとても大きいケース四つでTLEをおこしてしまったのです。~~

~~PythonやHaskellにさえ負けてしまうって一体なんのアルゴリズム使っているんですかね...Swift Algorithm Clubの人にsort関数のプルリク送ってもらいたいです......~~

ここのTLEの原因はAtCoder側が最適化オプションをなにも設定していないせいでした。語弊があったので修正しておきます。monoさん情報提供ありがとうございました！

# 結論
Swiftで競技プログラミングやるの、とてもつらいものがあるということが分かってしまいました。よっぽどの変わり者でない限り、たとえSwiftしか書けない人でもC++とかを勉強して書くほうが楽なのではないかなと思います。

まぁでもSwiftの言語自体の勉強にはなると思うので興味あるかたがぜひAtCoderやPaizaにチャレンジしてみてください！
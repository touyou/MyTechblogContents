<!--
title:   Gemini Pro APIをiOSで
tags:    Gemini,GeminiPro,SwiftUI,iOS
id:      6bab84e6c93ae24e4d89
private: false
-->
Gemini Pro API公開されましたね

精度的にはGemini Ultraからかなり機能が絞られているだけあってGPT-4よりは劣ることが公式ベンチマークなどからもわかっていますが、一方で以下のようなメリットもあると思います。

- Google AI Studioですぐ試せる
- プレビュー版なのでまだ無料（ただし商用利用は不可）
- 画像を使ったマルチモーダルプロンプトも無料で試せる
- 各プラットフォームのライブラリとクイックスタートガイドが日本語で用意されている

最も注目すべきはもちろん一番最後、各プラットフォームのライブラリとクイックスタートガイドが日本語で用意されているというところです！

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/4ea25b08-f2c7-6bc4-8c59-4f8cf29eded1.png)

これは試しやすさに関して200点満点！

というわけで早速試してみたところを簡単に共有します。

## 動作の様子

<iframe width="478" height="850" src="https://www.youtube.com/embed/a33z9QYiPsI" title="iOS Gemini Sample" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

アプリとしてはSwiftDataやSwiftUIを使ってプロンプトを実行したり、その結果を保存したりできる形にしました。

## やり方

やり方は公式のドキュメントがすでに充実しているのでそちらにお任せします。

https://ai.google.dev/tutorials/swift_quickstart?hl=ja

## 工夫ポイント・つまりポイント

とりあえず自分のコードがこちら

https://github.com/touyou/GeminiPlayground

Geminiの呼び出し部分は、画像のある無しでモデルを変える必要があったため以下のようにしました。

```swift
func execute(_ parts: [PartsRepresentable], hasImage: Bool) async throws -> String? {
    let modelName = hasImage ? "gemini-pro-vision" : "gemini-pro"
    let model = GenerativeModel(name: modelName, apiKey: GeminiAPIKey.default)
    let response = try await model.generateContent(parts)
    print(response.candidates)
    print("FB: ", response.promptFeedback ?? "none")
    return response.text
}
```

また、APIからの一個のプロンプトは合わせて4MB以下にする必要があるため、画像は以下のように圧縮して持つようにし

```swift
.onChange(of: selectedItems) {
    Task {
        selectedImages.removeAll()

        var datas = [Data]()
        for item in selectedItems {
            if let imageData = try? await item.loadTransferable(type: Data.self),
               let uiImage = UIImage(data: imageData),
               let compressionData = uiImage.jpegData(compressionQuality: 0.25) {
                selectedImages.append(Image(uiImage: uiImage))
                datas.append(compressionData)
            }
        }
        promptImages = datas
    }
}
```

また編集画面に今のサイズをステータス表示するようにしています。

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/3ada2536-fd7e-30f8-ed45-3beb2cc75850.png)

実際はさまざまなPayload含めて4MBなのでギリギリを攻めることはできませんでした。

## まとめ

以上めちゃくちゃクイックにですが、iOSでGemini Pro APIを使ったら、を紹介しました。
速度重視記事ということで最低限の内容でしたが、参考にしてもらえれば嬉しいです。
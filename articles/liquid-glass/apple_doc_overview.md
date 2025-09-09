---
title: "Liquid Glassに関するメモ：Appleドキュメントを読む"
emoji: "💧"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["Liquid Glass", "Apple", "Document"]
published: false
---

ドキュメントを適宜読み翻訳しつつ、要約しつつ、Liquid Glassについて理解を深めていくためのメモになります。
今回対象にするのは以下の記事になります。

https://developer.apple.com/documentation/technologyoverviews/liquid-glass

https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass

# 概要ページについて

## イントロダクション

Liquid Glassは、Appleのプラットフォーム間で一貫して提供される、動的なマテリアルのことで、ガラスと液体の特性をあわせ持っています。
Liquid Glassに適合しAppleのデザイン原則に従うことで、階層・調和・一貫性を美しいインターフェイスで実現することが可能になります。

SwiftUI / UIKit / AppKitを使っていればLiquid Glassが適用されるべきコントロールやナビゲーションには自動で適用されます。
カスタマイズしたインターフェイス要素にエフェクトを適用することも可能です。

## 適合の仕方

Liquid Glassに適合することは、今までのアプリをゼロから作り直すことを意味しません。
まずは最新のXcodeで動かして変化を見てから、ベストプラクティスに沿ってAppleプラットフォームらしく調整していく形になります。

挙げられているベストプラクティスとしては

- マテリアル・コントロール・アプリアイコンに新しいビジュアルエフェクトを取り入れる
- プラットフォームを跨いで統一されたナビゲーションと検索体験を提供する
- インターフェイスの構成とレイアウトが他のアプリやシステム体験と一貫して見えるようにする
- ウィンドウ・モーダル・メニュー・ツールバーのベストプラクティスを採用する
- プラットフォームをまたいで優れた体験を提供できていることを確認する

詳細は後述します。

## 公式のサンプルコード

公式のサンプルコードとしては以下が提供されています。

https://developer.apple.com/documentation/SwiftUI/Landmarks-Building-an-app-with-Liquid-Glass

このサンプルコードでは以下の要素が確認できます。

- Icon Comopserによるアプリアイコンの設定
- background extension effectを適用したedge-to-edgeの体験の提供
- 横向きスクロールビューでのedge-to-edgeの体験の提供
- ウィンドウサイズの変更に応じたレイアウトの調整
- プラットフォームをまたいだ検索機能
- カスタムインターフェイス要素やアニメーションへのLiquid Glassエフェクトの適用

## HIGで定義されたデザイン原則

Human Interface Guidelinesで定義されたLiquid Glassに関するデザイン原則としては以下のようなものがあります。

- 最も重要なコンテンツに焦点を当てられるように、レイアウトを定義し、ナビゲーション構造を選ぶ
- シンプルで力強いレイヤーを用いて再設計し、デバイスや表示を問わず立体感と一貫性を持たせる
- コントロールやナビゲーションでの色の使用は控えめにし、可読性を保ちながらコンテンツ自体が際立つようにする
- インターフェイス要素がデバイス間でソフトウェアとハードウェアのデザインに調和するようにする
- 標準的なアイコン表現と予測可能なアクション配置を採用し、プラットフォームまたいで一貫性を持たせる

詳細はHuman Inteface Guidelinesに記載されています。この内容に関しては別途まとめていこうと思います。

https://developer.apple.com/design/human-interface-guidelines

# Liquid Glassへの適合方法について

## ビジュアルのアップデート

Liquid Glassという新しいマテリアルはコントロールとナビゲーション要素のための明確な機能レイヤーを作ります。
Liquid Glassはインターフェイスの見た目や質感、動きに影響を与え、さまざまな要因に応じて変化し、基盤となるコンテンツへの注目をうながします。

### システムフレームワークを活用することでLiquid Glassを自動的に適用する

システムフレームワークは、標準コンポーネントが自動的かつさまざまな要因を考慮してLiquid Glassに動的に適用されるようになっています。
SwiftUI, UIKit, AppKitの標準コンポーネントがこれに該当します。

### コントロールやナビゲーション要素でのカスタム背景の使用を減らす

コントロールやナビゲーション要素にはLiquid Glassやシステムが提供する他の効果（スクロールエッジエフェクトなど）とコンフリクトする可能性が高いため、カスタム背景の使用は避けるべきです。
特に以下の要素での使用は推奨されません。

SwiftUI | UIKit | AppKit
------- | ----- | -----
`NavigationStack` | `UINavigationBar` | `NSToolbar`
`NavigationSplitView` | `UITabBar` | `NSSplitView`
`titleBar` | `UIToolbar` |
`toolbar(content:)` | `UISplitViewController` |

### アクセシビリティ設定でインターフェイスをテストする

Liquid Glassの半透明表現や流動的なモーフィングアニメーションは、すべてのユーザーにとって最適とは限らないため、アクセシビリティ設定に応じて除去・変更されることがあります。
システムフレームワーク標準のコンポーネントを使用している場合は自動的に適用されますが、カスタム要素やアニメーションを使用する場合もこれらの設定に適応した体験を提供できるようにしましょう。

### Liquid Glassエフェクトの過剰使用を避ける

カスタムコントロール要素にLiquid Glassエフェクトを適用する場合は控えめにしましょう。
コンテンツへと注意を向けることがLiquid Glassの目的であるため、複数あるとかえってコンテンツからそらしてしまう可能性があります。
最も重要な機能要素に限定して適用することが大事で、詳しくは別ドキュメントで解説されています。

https://developer.apple.com/documentation/SwiftUI/Applying-Liquid-Glass-to-custom-views

利用できるコードは以下です。

SwiftUI | UIKit | AppKit
------- | ----- | -----
`glassEffect(_:in:)` | `UIGlassEffect` | `NSGlassEffectView`

## アプリアイコン

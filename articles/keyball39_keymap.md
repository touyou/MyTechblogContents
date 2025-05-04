---
title: "Keyball39のキーマップ ver.0.1"
emoji: "🗺️"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["Keyball39", "Keyball", "キーボード"]
published: true
---

Keyball39 のキーマップが定まってきたので紹介です。
またその過程で少しファームウェアのカスタマイズも行ったので紹介します。

# Keyball39 のキーマップ

まずキーマップはファームを少しいじって、6 レイヤーにして以下のような役割分担にしました。

| レイヤー | 役割                                                   |
| -------- | ------------------------------------------------------ |
| 0        | 通常、アルファベットと一部記号、言語切り替えなど       |
| 1        | 記号エリア                                             |
| 2        | Auto Mouse Layer、マウス操作とテンキーを入れてます     |
| 3        | 数字エリア、キー配置はレイヤー 2 と同等にしています    |
| 4        | ファンクションエリア、スクロールはここに割り当てました |
| 5        | 予備のレイヤー、標準のレイヤー 3 をそのままにしてます  |

実際のキーマップはこちらです。

![](/images/keyball39_keymap/keymaps.png)

将来的に conductor を手に入れたい気持ちもあるので、そちらに少しインスパイアを受けつつ、HHKB の配列も意識してといった感じにまとめてます。
このあと触れるファームウェアカスタマイズの記事を参考にしつつレイヤー順は決めました。

# ファームウェアのカスタマイズ

ファームウェアのカスタマイズには以下の記事を参考にしました。

- [Keyball44 v1.3.2 でレイヤー数を増やす(QMK 環境不要)](https://zenn.dev/yamavel/articles/4d68ba3c8f01c4)
- [自作キーボード「Keyball61」：おれのファームまとめ前編](https://mazcon.hatenablog.com/entry/2023/11/10/080000)
- [自作キーボード「Keyball61」：おれのファームまとめ後編](https://mazcon.hatenablog.com/entry/2023/11/20/022521)
- [Keyball を縦に回して横スクロールする](https://zenn.dev/yoichi/articles/keyball-horizontal-scroll-by-vertical-motion)

ポイントごとに紹介していきます。

## キーマップの変更

デフォルトのキーマップを現時点での最適状態になるように変更していました。
その際の指定方法は記事などを参考にしているとなかなか書いてくれている人がいないのですが、QMK のリポジトリと Keyball のリポジトリを見ることで使える全機能がわかります。

- [qmk_firmware/docs/keycodes.md at master · qmk/qmk_firmware](https://github.com/qmk/qmk_firmware/blob/master/docs/keycodes.md)
- [keyball/qmk_firmware/keyboards/keyball/lib/keyball/keycodes.md at main · Yowkees/keyball](https://github.com/Yowkees/keyball/blob/main/qmk_firmware/keyboards/keyball/lib/keyball/keycodes.md#japanese)

これらを見ながら Remap で考えていたキーマップをもとにコードに反映していきました。

## デフォルト設定の変更

デフォルトの設定は自分なりの考えでいくつかの変更を行いました。
行った変更箇所は以下です。

- OLED の消灯時間を延ばす
- AML の対象レイヤーを変更、タイムアウト時間も変更
- レイヤー数の増加
- デフォルトのトラボ設定を変更
- LED 関連は使っていないので全てコメントアウト

抜粋すると以下のような感じです。

```c
#define OLED_TIMEOUT 120000

#define TAP_CODE_DELAY 5

#define POINTING_DEVICE_AUTO_MOUSE_ENABLE
#define AUTO_MOUSE_DEFAULT_LAYER 2
#define AUTO_MOUSE_TIME 500

#define DYNAMIC_KEYMAP_LAYER_COUNT 6

#define KEYBALL_CPI_DEFAULT 1000
#define KEYBALL_SCROLL_DIV_DEFAULT 6
```

## トラックボール関連の調整

トラックボール周りでは AML について挙動を一部参考記事に合わせて修正したのと、スクロールが常に縦に固定されるようにしました。
横スクロールは Shift を押せばどうにかなるのでこのようにしています。

```c
layer_state_t layer_state_set_user(layer_state_t state) {
  // Auto enable scroll mode when the highest layer is 4
  keyball_set_scroll_mode(get_highest_layer(state) == 4);
  keyball_set_scrollsnap_mode(KEYBALL_SCROLLSNAP_MODE_VERTICAL);

// Disable auto mouse when the layer is 1
#ifdef POINTING_DEVICE_AUTO_MOUSE_ENABLE
  switch (get_highest_layer(remove_auto_mouse_layer(state, true))) {
  case 1:
    state = remove_auto_mouse_layer(state, false);
    set_auto_mouse_enable(false);
    break;
  default:
    set_auto_mouse_enable(true);
    break;
  }
#endif
  return state;
}
```

## OLED のカスタマイズ

一番こだわったのはこちらです。
レイヤーのわかりやすさと可愛い・かっこいい OLED を目指すため参考記事を発展させて自分なりに作りました。

少しここも詳細の解説をしている記事がなかったので実験しながらだったのですが、OLED は以下の図のように縦にすると、px にして 128×32、文字数にして 16×5 文字の表示が可能なのでこれにどう当てはめるかを考えます。
![](/images/keyball39_keymap/oled.jpg)

今回自分は基本参考記事をベースにしつつ、自分なりにカスタマイズしています。

- ロック状態は自分が普段ほとんど使わない上に、Keyball で誤爆することがなさそうなので省略しました
- ステータス表示も自分は使わないので、デフォルトのものをメイン OLED に、バージョン表示をサブ OLED に表示することにしました
- レイヤー表示は猫のものをお借りしつつ、もう少しわかりやすくするために各レイヤーの役割を三文字で表したものも表示するようにしました
- バージョン表示にはロゴを入れ、独自にハードコーディングしたものを表示するようにしました。また QMK のバージョンは重要かと思うのでこちらは残しました

画像に関しては参考記事のものを画像編集して使っています。

| ![](/images/keyball39_keymap/cat0.png) | ![](/images/keyball39_keymap/cat1.png) | ![](/images/keyball39_keymap/cat2.png) | ![](/images/keyball39_keymap/cat3.png) | ![](/images/keyball39_keymap/cat4.png) | ![](/images/keyball39_keymap/cat5.png) |
| :------------------------------------: | :------------------------------------: | :------------------------------------: | :------------------------------------: | :------------------------------------: | :------------------------------------: |

ドット絵ツールではなく、Affinity Designer を使っています。そのため追加した文字もフォントのままですが、しっかりレンダリングされました。
同様にロゴもベクターデータをビットマップに書き出せば問題ないので、こちらを使っています。

![](/images/keyball39_keymap/logo.png)

画像ができたら以下のサイトを使って変換します。

https://javl.github.io/image2cpp/

向きはもちろんのこと、背景色も正しく指定しないと表示が崩れるようなので注意しましょう。

これらを終えてしっかりオリジナルの表示ができました。

![](/images/keyball39_keymap/layer.jpg)
![](/images/keyball39_keymap/ver.jpg)

## その他の工夫

その他には開発面で工夫をしました。

- コードがわかりにくいのでできる限りのコメントを追記しました
- lib 配下のコードには触らないようにしました。これによって Keyball 側のファームウェアに更新があった際に追従しやすくしています
- GitHub Actions のアーティファクトに cflags.txt を追加して VS Code の警告を減らすことを試みました

最後の観点については参照先に QMK のビルドフォルダが必要になるため最小限でしかできませんでしたがある程度は快適になるかと思います。

以上対応を行なったのがこちらのリポジトリです。

https://github.com/touyou/keyball

# まとめ

今回はキーマップに加えて、自分なりのカスタマイズにも挑戦してみました。
個人的に OLED のカスタマイズができたのがとても良かったです。自分だけのものという気持ちが増しました。

無線分割になっても OLED したいなとも思いつつ、ここからもっと分割キーボードに慣れていければと思います。

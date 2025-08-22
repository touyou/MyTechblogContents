---
title: "OSSメンテナ入門のためのメモ：ローカルでレビュー編"
emoji: "🤖"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["OSS", "fish", "GitHub"]
published: true
---

最近OSSメンテナとして初めて活動する機会があり、フォークたものをレビューする際に詰まったのでそのメモです。

## 結論

ghコマンドでチェックアウトする。ターミナル上であればfzfなどを併用すると便利。
ちなみにGitHub Desktopでもできるそうです。

### 準備

```sh
brew install gh fzf
```

### スクリプト

fishのものになります。書き換え方をChatGPTに相談していたらちょっとリッチになりました。

```sh
function pr_checkout
  set pr (gh pr list --json number,title --jq '.[] | "\(.number)\t\(.title)"' \
      | fzf --delimiter='\t' --with-nth=2.. \
      | cut -f1)
  test -n "$pr"; and gh pr checkout $pr
end
```

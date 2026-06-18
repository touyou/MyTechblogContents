# .claude/ — このリポジトリの Claude Code 設定

技術記事の校正・執筆に使う writing 系スキルを、`touyou/skills` マーケットプレイスから
**plugin として** このリポジトリにスコープして参照するための設定。

## 何を参照しているか

- マーケットプレイス: `touyou-skills`（GitHub: [`touyou/skills`](https://github.com/touyou/skills)）
- プラグイン: `writing-pack`
- 収録スキル: `proofread-touyou`（今後 writing 系スキルが増えれば自動でここに増える）

`settings.json` の `enabledPlugins` でこのリポジトリだけで有効化している:

```json
{
  "enabledPlugins": {
    "writing-pack@touyou-skills": true
  }
}
```

## 初回セットアップ（マシンごとに1回）

`enabledPlugins` が効くには、先にマーケットプレイスをそのマシンに登録しておく必要がある:

```sh
# Claude Code 内で実行（built-in スラッシュコマンド）
/plugin marketplace add touyou/skills
```

登録後、このリポジトリを開けば `settings.json` により `writing-pack` が有効になる。
`/plugin` で writing-pack が enabled になっているか確認できる。enabled にならない場合は:

```sh
/plugin install writing-pack@touyou-skills   # スコープを「このプロジェクト」にして導入
```

## 最新版に更新する

公開済みの最新版（GitHub `main`）を取り込む:

```sh
/plugin marketplace update touyou-skills
```

> `writing-pack` に新しい writing スキルを追加したいときは、`touyou/skills` 側で
> `skills/<name>/SKILL.md` を追加し `.claude-plugin/marketplace.json` の `writing-pack.skills`
> に登録 → push → 上記 update、で取り込まれる。

## 既存のグローバル symlink との関係

別途、開発用に `~/.claude/skills → ~/.agents/skills → ~/Developer/Private/skills/...` の
グローバル symlink で `proofread-touyou` を全プロジェクトに出している（手元チェックアウトを
即反映する著者向けの経路）。これは**意図的に残している**。

そのためこのリポジトリでは `proofread-touyou` がグローバル symlink と plugin の
両経路から来る（同一内容なので実害はない）。役割分担は:

- グローバル symlink … 手元で編集中のスキルを即試す「著者モード」
- plugin（このディレクトリ） … 公開済み最新を取り込む「消費モード」＋将来の writing スキル自動追加

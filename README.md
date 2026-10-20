# MyTechblogContents

![Qiita Sync](https://github.com/touyou/MyTechblogContents/actions/workflows/qiita_sync_check.yml/badge.svg)

Qiita と Zenn のコンテンツ管理リポジトリ

## /dev/null への投稿

`.github/workflows/devnull.yml` が [dev-null.sh/@touyou](https://dev-null.sh/@touyou) に投稿する。

- `main` への push で、公開状態になった記事(`published: true` になった、または公開済みで追加された記事)を「記事を書きました」として投稿する。予約公開(`published_at` が未来)は投稿しない
- 記事の更新は自動では投稿しない。Actions の「/dev/null」→ Run workflow で slug と更新内容を入れると「記事を更新しました」として投稿する
- リポジトリ変数 `DEVNULL_ENABLED=true` とシークレット `DEVNULL_SSH_KEY`(GitHub に署名鍵として登録した CI 専用の鍵の秘密鍵)が揃うまでは何もしない

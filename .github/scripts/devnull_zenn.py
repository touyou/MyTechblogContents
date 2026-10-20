"""Zenn の記事から /dev/null に投稿する本文を作る。

new:    push の前後を比べ、published が false/未作成 → true になった記事を新着として拾う
update: 指定した slug の記事を「更新しました」として告知する
結果は GITHUB_OUTPUT に bodies (JSON 配列) として書く。
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ZENN_USER = "touyou"
JST = timezone(timedelta(hours=9))


def front_matter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.split(" #", 1)[0].strip()
        meta[key.strip()] = value
    return meta


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def topics(value: str) -> list[str]:
    value = value.strip().strip("[]")
    return [unquote(t.strip()) for t in value.split(",") if t.strip()]


def is_published(meta: dict) -> bool:
    if meta.get("published", "").lower() != "true":
        return False
    # 予約公開 (published_at が未来) はまだ Zenn に出ていないので告知しない
    published_at = unquote(meta.get("published_at", ""))
    if published_at:
        try:
            at = datetime.strptime(published_at, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        except ValueError:
            return True
        return at <= datetime.now(JST)
    return True


def git_show(rev: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def body_for(slug: str, meta: dict, headline: str, note: str = "") -> str:
    parts = [headline, "", f"{unquote(meta.get('emoji', '📝'))} {unquote(meta.get('title', slug))}"]
    if note:
        parts += ["", note]
    tags = topics(meta.get("topics", ""))
    if tags:
        parts += ["", " / ".join(tags)]
    parts += ["", f"https://zenn.dev/{ZENN_USER}/articles/{slug}"]
    return "\n".join(parts)


def new_articles(before: str, after: str) -> list[str]:
    if set(before) <= {"0"}:
        return []
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AMR", before, after, "--", "articles/*.md"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    bodies = []
    for path in diff:
        current = git_show(after, path)
        if current is None:
            continue
        meta = front_matter(current)
        if not is_published(meta):
            continue
        previous = git_show(before, path)
        if previous is not None and is_published(front_matter(previous)):
            continue
        slug = os.path.splitext(os.path.basename(path))[0]
        bodies.append(body_for(slug, meta, "Zenn に記事を書きました"))
    return bodies


def updated_article(slug: str, note: str) -> list[str]:
    path = f"articles/{slug}.md"
    if not os.path.exists(path):
        sys.exit(f"{path} がありません")
    meta = front_matter(open(path, encoding="utf-8").read())
    if not is_published(meta):
        sys.exit(f"{slug} はまだ公開されていません")
    return [body_for(slug, meta, "Zenn の記事を更新しました", note)]


def main() -> None:
    mode = sys.argv[1]
    if mode == "new":
        bodies = new_articles(os.environ["BEFORE"], os.environ["AFTER"])
    else:
        bodies = updated_article(os.environ["SLUG"].strip(), os.environ.get("NOTE", "").strip())
    for body in bodies:
        print(body, end="\n---\n")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write(f"bodies={json.dumps(bodies, ensure_ascii=False)}\n")


if __name__ == "__main__":
    main()

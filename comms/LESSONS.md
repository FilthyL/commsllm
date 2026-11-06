# Lessons (curated by the Lead, under 60 lines, read at every cold start)

One line per gotcha. Newest at the top. Delete a line once it stops being true.

- 2026-11-06: The GitHub MCP `search_*` tools aren't available in Claude cloud sessions. Use `gh api search/...` for search only.
- 2026-11-06: Pushes and comments made with `GITHUB_TOKEN` don't start other workflows (except `workflow_dispatch` / `repository_dispatch`). Route through dispatch.
- 2026-11-06: claude-code-action ignores bot-authored comments unless the bot is listed in `allowed_bots`. codex-action needs `allow-bot-users`. Never use `*`.
- 2026-11-06: Codex cloud takes `@codex review` as a review request (P0/P1 only), and any other `@codex ...` as a general task in the PR or issue context.

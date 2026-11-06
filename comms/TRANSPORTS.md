# Transport matrix

These are empirical facts about which wake paths actually work. **The Lead runs these tests during bootstrap** (on the bus PR, or on a throwaway PR) and fills in the table below. The router and the runner choice in `comms/config.yml` follow from the results. Until a row says ✅, assume it doesn't work and use the next tier (ARCHITECTURE §4).

| # | Test | How | Result | Latency | Date | Notes |
|---|---|---|---|---|---|---|
| T1 | Codex cloud acts on an `@codex` comment that **Claude** posted through its GitHub identity | Lead posts `@codex` + `COMMS/1 type=ping from=claude to=codex task=bus next=codex` + "reply with type=pong; do not push" on the bus PR | ⏳ | | | Record which login the comment showed as. |
| T2 | `@codex` + `type=task` on a spec-first PR makes Codex **push to that PR's branch** (rather than open a new PR) | first real task (cl-002 or cl-003) | ⏳ | | | If it opens a new PR, the Lead closes the spec PR. Protocol unchanged. |
| T3 | Codex's reply comment wakes the subscribed Claude session | observe after T1 | ⏳ | | | |
| T4 | A CI result (check run completed) wakes the subscribed Claude session | first PR with CI | ⏳ | | | |
| T5 | A `github-actions[bot]` comment (announcer `notify`) on the bus PR wakes the Claude session | after cl-001 merges, open any PR | ⏳ | | | |
| T6 | Codex cloud acts on an `@codex` comment from `github-actions[bot]` (watchdog pings) | after cl-004, the watchdog ping | ⏳ | | | If ❌, the watchdog dispatches codex-action instead (needs Tier B). |
| T7 | `@codex review` produces a review. Record its native format. | Lead opens one `owner: claude` PR | ⏳ | | | Confirms the parsing rule in PROTOCOL §7.7. |
| T8 | claude-code-action triggers on `@claude` from `chatgpt-codex-connector[bot]` (`allowed_bots`) | after cl-005 and the secrets are added | ⏳ | | | Tier B for Claude |
| T9 | codex-action dispatched by the router pushes commits **and CI runs on them** | after cl-005 | ⏳ | | | Pushes made with GITHUB_TOKEN don't trigger `pull_request` workflows. Needs an explicit dispatch of `ci.yml`, or an App token. |

Legend: ✅ works · ❌ doesn't · ⚠️ works with caveats · ⏳ not tested yet

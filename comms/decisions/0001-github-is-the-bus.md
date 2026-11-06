# 0001: GitHub is the message bus

- **Status:** accepted
- **Date:** 2026-11-06
- **Decider:** Lead (Claude), with the owner's request as input

## Context
Claude (in a Claude Code cloud session) and Codex (Codex cloud) need to exchange tasks, reviews and questions quickly, durably and without a human. Both run in ephemeral cloud sandboxes. Neither can reach a server on the owner's machine, and neither keeps memory between runs.

## Decision
Use GitHub as the only bus. Messages are PR and issue comments with a `COMMS/1` header line. Contracts are files under `comms/`. Wake-ups come from `@codex` mentions (Codex cloud), PR subscriptions (the Claude session), and GitHub Actions (the router, the watchdog, and the headless runners for both agents).

## Alternatives rejected
- **A local MCP mailbox (e.g. mcp_agent_mail).** Needs an always-on host that both cloud agents can reach, which means extra infrastructure and a single point of failure.
- **A chat bridge (Slack or Discord bots).** No code context, no diffs or CI, and a second source of truth.
- **Direct agent-to-agent API calls.** No durable state, no audit trail, and complex auth.
- **One shared `handoff.md` board file.** Constant merge conflicts when lanes run in parallel. We use one file per task plus a comment thread instead.

## Consequences
- We get identity, ordering, durability, notifications, CI and an audit log for free.
- Latency is bounded by GitHub event delivery and agent start-up, roughly seconds to a few minutes, which is fine at this scale.
- Behaviour depends on how the vendor integrations handle bot-authored mentions. Mitigated by the tiered transports and the empirical matrix in `comms/TRANSPORTS.md`.

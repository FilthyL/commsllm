# commsllm

Two or more LLM agents (Claude and Codex) working together on GitHub repos, with the human out of the loop.

**GitHub is the message bus. The repo is the memory. The PR thread is the state.** Every message is a PR comment carrying a one-line `COMMS/1 ...` header. Every contract (task spec, decision, lesson) is a file under `comms/`. Agents wake on `@codex` mentions, Claude's PR subscriptions, and GitHub Actions.

```
Owner ──goal issue──▶ Claude (Lead) ──spec-first PR + @codex──▶ Codex (Builder)
                         ▲                                         │
                         └──── COMMS/1 type=ready / review / fixed ◀┘   → merge on green
```

## Start here

| You are | Read |
|---|---|
| the owner | [`docs/CODEX_KICKOFF.md`](docs/CODEX_KICKOFF.md): the one-time checklist and the prompt to paste into Codex |
| Codex | [`AGENTS.md`](AGENTS.md) |
| Claude | [`CLAUDE.md`](CLAUDE.md), then [`AGENTS.md`](AGENTS.md) |
| curious | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (why it's built this way), [`docs/PROTOCOL.md`](docs/PROTOCOL.md) (wire format) |

## Layout

```
AGENTS.md                  shared rules, Builder loop, review guidelines, human gates (Codex auto-loads it)
CLAUDE.md                  Lead loop: planning, review, steering, merging (Claude auto-loads it)
docs/ARCHITECTURE.md       actors, transports, state model, reliability, autonomy ladder, prior art
docs/PROTOCOL.md           COMMS/1 envelope, message types, state machine, task files, timing
docs/CODEX_KICKOFF.md      owner checklist and the kickoff prompt
comms/config.yml           runtime switches: phase, runners, merge policy, limits, kill switch
comms/tasks/               one file per task (contract): cl-* by Claude, cx-* by Codex
comms/decisions/           ADRs, so decisions aren't argued twice
comms/TRANSPORTS.md        empirical matrix of which wake paths work
comms/LESSONS.md           curated gotchas, read at every cold start
comms/labels.json          label set (synced by a workflow)
.github/                   PR template, Goal issue form, and later the workflows
```

## Status

Phase 0 (relay). The bootstrap backlog `comms/tasks/cl-001…cl-006` builds the automation: the announcer, CI, the `comms` CLI, the router and watchdog, the headless runners, and a portable installer for other repos.

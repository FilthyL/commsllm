# Kickoff: getting Claude and Codex talking (Phase 0)

About 15 minutes of owner time, once. After this, the owner only merges PRs (Phase 1) and later only opens Goal issues (Phase 2).

## Owner checklist (one time)

1. **Merge the protocol PR** (the branch that added this file) into `main`. Codex reads `AGENTS.md` from the branch it works on, so the files need to be on `main`.
2. **Codex cloud** ([chatgpt.com/codex](https://chatgpt.com/codex)):
   - Connect GitHub and give it access to `FilthyL/commsllm`.
   - Create an environment for the repo. Defaults are fine. Python 3 is enough for the bootstrap.
   - In Codex settings, turn on **Code review** for the repo so `@codex` mentions work on PRs. Leave **automatic reviews off**: the agents request reviews explicitly, and auto-reviewing every spec PR would be noise.
3. **Claude**: tell the Claude session "go". It will:
   - open the bus PR (branch `comms/bus`, draft, never merged) and subscribe to it;
   - subscribe to every PR Codex opens.
4. **Paste the kickoff prompt below into Codex.** If Codex cloud asks you to click "Create PR" at the end of a task, click it. That's only needed until cl-001 merges.
5. Until cl-001 (the announcer) is merged, tell Claude the PR numbers Codex opens ("Codex opened #3 #4"). After that, announcements are automatic.
6. **Later, for Phase 1** (Claude will ping you with `needs:owner` when it's time):
   - Branch protection on `main`: require the `ci` check, and block force-pushes. Don't require approvals (ARCHITECTURE §9).
   - Repo secrets for the headless runners: `CLAUDE_CODE_OAUTH_TOKEN` (run `claude setup-token`) or `ANTHROPIC_API_KEY`, and `OPENAI_API_KEY`. See `docs/RUNNERS.md` once cl-005 lands.
7. **To go hands-off (Phase 2):** comment `autonomy on` on the bus PR, and merge the config PR that Claude opens in response. From then on Claude merges on approve plus green CI.

---

## Kickoff prompt: paste this into Codex

```text
You are Codex, the Builder, in a two-agent team with Claude (the Lead) on the GitHub repo FilthyL/commsllm (base branch: main). The owner (FilthyL) is leaving the loop. You and Claude coordinate only through GitHub PR comments that use the COMMS/1 protocol.

1. Read, in this order: AGENTS.md (all of it), comms/config.yml, comms/LESSONS.md. Skim docs/PROTOCOL.md; it's reference material.
2. Implement comms/tasks/cl-001.md exactly as specified. Change only the paths in its `scope`, plus the task file itself. Run its Verify commands. If a tool isn't available in your sandbox (e.g. actionlint), say so under Assumptions instead of stopping.
3. In the same change, set `status: done` in comms/tasks/cl-001.md.
4. Open a PR against main titled "[cl-001] Wire the bus (PR announcer and label sync)". Use .github/pull_request_template.md for the body.
5. End your final message with this block, filled in:

   COMMS/1 type=ready from=codex to=claude task=cl-001 round=1 next=claude
   ## Summary
   <2-4 lines>
   ## Evidence
   - <command> → <result>
   ## Assumptions
   - <anything you decided on your own>

6. If you can run tasks in parallel, do cl-002 and cl-003 the same way, as separate PRs. Their scopes don't overlap with cl-001. Otherwise stop after cl-001. Claude will send you the next tasks with @codex comments.
7. From now on, whenever you are @mentioned on a PR or issue, follow AGENTS.md §3 (Builder loop). The last COMMS/1 header in the thread is your instruction.

Don't ask the owner questions. If something is ambiguous, choose the most reasonable option, write it under Assumptions, and continue. Stop only for the human gates in AGENTS.md §7.
```

---

## Resume prompt: paste this into a new Claude Code session (only if the old one is gone)

```text
You are Claude, the Lead, on FilthyL/commsllm. Read CLAUDE.md and follow "Cold start": subscribe to the bus PR and every open [cl-*]/[cx-*] PR, then act on every thread whose last COMMS/1 header has next=claude. Keep the Builder's lanes full.
```

## What happens next (no owner needed)

1. Claude reviews cl-001…cl-003 as they arrive. It sends `@codex` with findings, or approves. In Phase 0–1 the owner presses merge.
2. After cl-001 merges, Claude runs the transport smoke tests T1, T3 and T5 on the bus PR and records them in `comms/TRANSPORTS.md`.
3. Claude dispatches cl-004, cl-005 and cl-006 as **spec-first PRs**: it opens the PR with the task file, then comments `@codex` + `COMMS/1 type=task ... next=codex`. Codex pushes to that branch. That covers T2.
4. When the bootstrap is done (Phase 1 exit criteria, ARCHITECTURE §10), Claude asks the owner for `autonomy on`.

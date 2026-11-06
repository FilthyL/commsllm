---
id: cl-000
title: Imperative short title
status: draft          # draft | ready | active | done | dropped
owner: codex           # implementer: codex | claude
reviewer: claude
goal: bootstrap        # goal-<issue#> or a short tag
size: S                # S <150 changed lines | M <400 | L = split it
priority: P1           # P0 now | P1 next | P2 later
depends_on: []
scope:                 # file lease: the only paths this task may change (plus this task file)
  - path/or/glob/**
---

## Goal
One or two sentences: what exists after this task that didn't before, and why.

## Acceptance criteria
- [ ] Concrete, checkable statement.
- [ ] Another one. Each criterion should map to a Verify line or an observable behaviour.

## Verify
```bash
# copy-pasteable commands, each followed by its expected result
python3 -m unittest discover -s tests   # → OK
```

## Out of scope
- Things a builder might be tempted to do here, but shouldn't.

## Notes
- Hints, links, gotchas. Decisions made while building get added here.

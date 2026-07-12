# Agent Coordination

This directory contains durable coordination state for Codex and human maintainers. These
files are versioned so a new conversation can continue from repository evidence.

| File | Purpose | Update rule |
| --- | --- | --- |
| `PROJECT_STATUS.md` | Last verified product, test, and repository state | Replace stale facts after verification |
| `NEXT_ACTIONS.md` | Prioritized executable backlog | Keep short; remove completed implementation detail |
| `HANDOFF.md` | Active cross-session task handoff | Update before ending non-trivial work |
| `DECISIONS.md` | Durable architecture decision log | Append only |

Stable engineering rules belong in the root `AGENTS.md`. Product contracts belong in
`docs/`. Generated agent transcripts, model outputs, and temporary review notes do not belong
in this directory.

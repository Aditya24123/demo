# RTK - Rust Token Killer

Token-optimized CLI proxy for shell commands. Installed as `rtk` (`rtk 0.42.0+`).

## Rule (Grok / this project)

When using the **shell** tool (`run_terminal_command`), prefer RTK wrappers for noisy commands so context stays small.

**Always prefer:**

| Instead of bare? | Use? |
|---|---|
| `git status` / `git log` / `git diff` | `rtk git status` / `rtk git log` / `rtk git diff` |
| `gh ?` | `rtk gh ?` |
| `npm run build` / `pnpm ?` | `rtk npm run build` / `rtk pnpm ?` |
| `pytest ?` | `rtk test pytest ?` or `rtk pytest ?` when available |
| `tsc` / `eslint` | `rtk tsc` / `rtk lint` |
| `docker ?` / `kubectl ?` | `rtk docker ?` / `rtk kubectl ?` |
| raw dumps of JSON/env/deps | `rtk json` / `rtk env` / `rtk deps` |
| noisy find/grep in shell | Prefer Grok `grep` / `list_dir` tools; if shell is needed: `rtk find` / `rtk grep` |
| full command logs | `rtk err <cmd>` (errors only) or `rtk summary <cmd>` |

**Do not wrap** when:

- Running long-lived servers (`python -m catalyst.local_api`, `npm run dev`)
- Commands need unfiltered streaming output for debugging
- Using Grok **dedicated tools** (`read_file`, `grep`, `search_replace`, `list_dir`) ? those are already efficient
- Running `graphify query|path|explain|update` (already compact)

Escape hatch:

```text
rtk proxy <raw-command>
```

## Catalyst-oriented examples

```powershell
rtk git status
rtk git diff
rtk test pytest -q code/backend/tests
rtk npm run build --prefix code/frontend
rtk err python code/backend/pipeline/scripts/check_ship_ready.py
rtk ls code/backend/pipeline/catalyst
rtk gain
```

## Meta

```text
rtk gain            # Token savings analytics
rtk gain --history  # Recent command savings
rtk --version
rtk config          # Show/create RTK config
```

On Windows PowerShell, chain with `;` not `&&`.

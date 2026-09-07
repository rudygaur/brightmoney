# CLAUDE.md — Brightmoney APM KYC Case Study

Working context for this project. **For a human collaborator (not Claude), [README.md](README.md)
is the better starting point.**

## What this is

A take-home case study for a **Back-end Product Management (APM) track** role: a US FinTech verifies
every user through a KYC **waterfall** (primary provider → secondary providers → manual review) over
2.5M synthetic user rows, and non-verification runs above the brief's 5% acceptable bar. The job is
to diagnose why, and design a fix. It is *not* a software project — the deliverables are analysis and
product documents, and the code exists only to make the numbers defensible.

Brief: [APM KYC_Design_Project_Assignment_Instructions.md](APM%20KYC_Design_Project_Assignment_Instructions.md)

Graded on: structure & communication (answer first, MECE), data rigor (correct denominators, honest
caveats), product judgment (explicit cost/latency/friction/risk trade-offs), and ownership (every
number and design decision defensible under probing, live).

## Where everything lives

This project keeps **no separate audit-trail or cheat-sheet file** — every loading decision,
assumption, defect found, and data caveat is documented inline in the notebooks, in the markdown
cells right next to the code and query it explains. There is deliberately no `AUDIT_LOG.md` or
`IMPORTANT.md`; if you're looking for that kind of detail, it's in the notebook.

| | |
|---|---|
| Load + clean + validate | [notebooks/01_kyc_load_and_setup.ipynb](notebooks/01_kyc_load_and_setup.ipynb) |
| Task 1 — funnel analysis (incl. the full flow-path audit used by Task 2) | [notebooks/02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb) |
| Task 1 — presentation | [Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018) |
| Task 2 — redesigned waterfall (text) | [TASK2_WATERFALL_DESIGN.md](TASK2_WATERFALL_DESIGN.md) |
| Task 2 — presentation | [The Waterfall, Rebuilt](https://claude.ai/code/artifact/49e52e3d-08f8-49bc-a5ee-2dc1a300051d) |
| Task 3 — PRD | **[reports/Task3a_PRD_KYC_Waterfall_v2.docx](reports/Task3a_PRD_KYC_Waterfall_v2.docx)** · [source](TASK3_PRD.md) · [published](https://claude.ai/code/artifact/43613d78-705d-46f2-b0a7-47d3216a6c3b) |
| Task 3 — ARD / monitoring plan | **[reports/Task3b_ARD_Monitoring_Plan.docx](reports/Task3b_ARD_Monitoring_Plan.docx)** · [source](TASK3_ARD.md) · [published](https://claude.ai/code/artifact/04ceac23-6b23-40a2-afa1-a2a8da69e6f5) |
| Task 3 — project plan | **[reports/Task3c_Project_Plan.docx](reports/Task3c_Project_Plan.docx)** · [source](TASK3_PROJECT_PLAN.md) · [published](https://claude.ai/code/artifact/27f7a568-f2cb-4285-bc97-041bc4077127) |
| Setup, file map, for a human reader | [README.md](README.md) |

**Do not recompute or restate specific numbers here.** If you need a figure, get it from a fresh run
of the relevant notebook cell, or read it off the published artifact — both are kept correct and
re-verified there; this file is not the place to duplicate them, since duplicated numbers are exactly
what has gone stale and drifted out of sync in the past on this project.

## Deliverables — status

| | Deliverable | Status |
|---|---|---|
| Task 0 | Load + profile the dataset into Postgres (self-imposed, not in the brief) | Done, 11/11 validation gates pass |
| Task 1 | Funnel analysis — headline rate, causes, highest-leverage problems, as a presentation | Done |
| Task 2 | Redesigned waterfall — diagram, decision logic, rationale, every change tied to a Task 1 finding | Done |
| Task 3 | PRD + ARD/monitoring plan + project plan | Done |

## Environment, in short

Runs against **Docker or a native Postgres install** — the notebooks connect over plain TCP and
stream the CSV load from the client, so nothing about the code is Docker-specific; only `.env`
changes between machines. Full setup: [README.md](README.md#setup--works-with-docker-or-a-native-postgres-install).

```bash
cd /Users/rudransh/d_drive/GITHUB/brightmoney
# make sure your Postgres server is up (docker start postgres, or however your native install runs)
.venv/bin/jupyter lab notebooks/01_kyc_load_and_setup.ipynb
```

- Database `study` (pre-existing, shared — not created by this work), schema `kyc`.
- Credentials in `.env` (git-ignored, chmod 600) — see `.env.example`.
- The repo root is resolved at runtime by walking up from the notebook's cwd looking for `.git` —
  no hardcoded path, so this runs unmodified from any clone or machine.
- Git repository, remote `origin` at `github.com/rudygaur/brightmoney`. `.env` and the 272 MB CSV are
  git-ignored.

## Conventions worth knowing before touching this project

- **Rows are never dropped.** Every exclusion (test accounts, unprocessed users) is a flag on the
  row, not a deleted row — the analyst picks the denominator, the loader never does.
- **Test accounts (107 `Test_user` rows) are excluded from every calculation, everywhere**, via a
  `where not is_test_user` filter — flagged, never deleted.
- **Corrections are made in place and explained, not silently overwritten** — if a notebook cell's
  narrative says something was fixed, the "before" is still described, not erased.
- Both notebooks are **idempotent** — re-running `01_kyc_load_and_setup.ipynb` drops and rebuilds
  `kyc_raw` / `ref_state` / `kyc_users` from scratch. It refuses to run if schema `kyc` contains any
  table it didn't create, since `study` is a shared database (override: `ALLOW_FOREIGN_OVERWRITE`
  in that notebook's setup cell).

## Open threads carried into Task 3 (now addressed there — WS0, WS7, WS5)

- The reason classifier that Task 2's redesign depends on (L1.5, distinguishing an SSN mismatch from
  an identity-attribute mismatch from a sanctions hit) is an assumption about what Idology's API can
  return, not a confirmed capability — the first thing to verify before building.
- The manual-review volume increase in Task 2's design needs a phased rollout, not a day-one flip.
- No provider cost or latency data exists in this dataset — Task 2's cost figures used illustrative
  unit costs on real volumes; Task 3's monitoring plan should specify what real numbers to collect.

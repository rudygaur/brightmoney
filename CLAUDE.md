# CLAUDE.md — Brightmoney APM KYC Case Study

Working context for this project. Read this first in any new session. **For a human collaborator
(not Claude), [README.md](README.md) is the better starting point** — this file is terser and
assumes more context.

## What this is

A take-home case study for a **Back-end Product Management (APM) track** role. It is *not* a
software project — the deliverables are analysis and product documents, and the code exists only to
make the numbers defensible.

Brief: [APM KYC_Design_Project_Assignment_Instructions.md](APM%20KYC_Design_Project_Assignment_Instructions.md)
Setup (Docker or native Postgres): [README.md](README.md)
Data-loading record: [AUDIT_LOG.md](AUDIT_LOG.md)
Load code: [notebooks/01_kyc_load_and_setup.ipynb](notebooks/01_kyc_load_and_setup.ipynb)
Task 1 analysis: [notebooks/02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb)
Published report: [Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018)

The scenario: a US FinTech verifies every user through a KYC **waterfall** (primary provider →
secondary providers → manual review). 2.5M synthetic user rows. An acceptable non-verification rate
in the US is stated as **5% or lower**. The job is to diagnose why it isn't, and design a fix.

Graded on four things, in the brief's own words:
- **Structure & communication** — answer first, then support it. MECE.
- **Data rigor** — correct denominators, honest caveats, numbers you can stand behind.
- **Product judgment** — explicit trade-offs across cost, latency, friction, risk.
- **Ownership** — every choice defensible in a live interview. "The tool produced it" is not an answer.

Format target: **CEO-level presentation**. Depth over length. AI use is expected and allowed; the
constraint is that every number and design decision must be explainable under probing.

## Deliverables — status

| | Deliverable | Status |
|---|---|---|
| Task 0 | Load + profile the dataset into Postgres (self-imposed, not in the brief) | **Done, 11/11 validation gates pass** |
| Task 1 | Funnel analysis — headline rate, causes, 2–3 highest-leverage problems. **As a presentation.** | **Done** — [notebook](notebooks/02_task1_funnel_analysis.ipynb), [published report](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018) |
| Task 2 | Redesigned waterfall — diagram + decision logic + rationale. Every change tied to a Task 1 finding. | **Done** — [doc](TASK2_WATERFALL_DESIGN.md), [diagram](https://claude.ai/code/artifact/49e52e3d-08f8-49bc-a5ee-2dc1a300051d) |
| Task 3 | PRD + ARD/monitoring plan + project plan. | **Not started** |

## Environment

This project is **not tied to Docker** — the notebooks connect over plain TCP and load the CSV by
streaming it from the client, so the identical code runs against a Dockerised Postgres or a native
install (Postgres.app, Homebrew, apt, the EDB installer, ...). Only `.env` changes between machines.
Full setup for both cases: [README.md](README.md#setup--works-with-docker-or-a-native-postgres-install).

```bash
cd /Users/rudransh/d_drive/GITHUB/Brightmoney
# make sure your Postgres server is up (docker start postgres, or however your native install runs)
.venv/bin/jupyter lab notebooks/01_kyc_load_and_setup.ipynb
```

- **Server (this dev machine, at last run):** PostgreSQL 18.1 in a Docker container named `postgres`,
  published on `0.0.0.0:5432`. *Not a requirement of the code* — see README for a native setup.
- **Database:** `study` (pre-existing and shared — *not* created by this work). **Schema: `kyc`.**
- **Client:** `.venv/` — Python 3.13, psycopg 3.3.5, pandas 3.0.5, jupyterlab, python-dotenv.
- **Credentials:** `.env` (chmod 600, git-ignored, see `.env.example`) holds `PGHOST`/`PGPORT`/
  `PGUSER`/`PGPASSWORD`/`PGDATABASE`; all optional with sensible defaults. `PGPASSWORD` may be left
  unset for a native install using peer/trust auth — the notebooks pass `None`, not `''`, so psycopg
  falls back to `~/.pgpass`/peer auth instead of sending an empty password. Never print the password
  or write it to a file.
- `PROJECT` (the repo root) is resolved at runtime by walking up from the notebook's cwd looking for
  `AUDIT_LOG.md` — no hardcoded absolute path, so this also runs unmodified from a different clone
  or a different machine.
- Git repository with remote `origin` at `github.com/rudygaur/brightmoney`. `.env` and the 272 MB
  CSV are git-ignored — never `git add -f` either.

**Two environment traps hit while building this — both now handled generically, not worked around:**

1. A macOS EDB PostgreSQL **17** install at `/Library/PostgreSQL/17` is what a bare `psql` resolves
   to on this dev machine. It was not the server actually in use; its v17 client binaries will
   connect to a v18 server but `pg_dump` from them will refuse. If `psql` behaves unexpectedly,
   check `psql --version` against the server's actual `select version()` before assuming a bug.
2. A containerised server cannot see the host filesystem at all, and a *native* server process
   commonly runs as its own OS user with no access to your home directory either (this dev machine's
   EDB v17 install's data directory belonged to a separate `postgres` OS user) — so server-side
   `COPY ... FROM '<path>'` isn't reliable on either kind of setup. The load always streams from the
   client with `COPY ... FROM STDIN` in 4 MB chunks instead, which sidesteps the question entirely.

**Roles:** `kyc_ro` (SELECT — the right role for ad-hoc analysis), `kyc_rw`, `kyc_owner`. All NOLOGIN
group roles granted to the connecting user. `ALTER DEFAULT PRIVILEGES` is set, so new tables in `kyc`
inherit.

## Data model

Two-layer load, deliberately split so cleaning is reviewable rather than baked into the import:

```
KYC_Synthetic_Dataset.csv (272 MB, 2,515,262 records)
   │  COPY ... FROM STDIN (format csv, header true)   ← no transformation
   ▼
kyc.kyc_raw     all TEXT, no constraints, verbatim    (347 MB)
   │  INSERT ... SELECT with explicit casts           ← every transformation visible here
   ▼
kyc.kyc_users   typed, constrained, indexed           (624 MB)  ← ANALYSE FROM HERE
kyc.ref_state   USPS code ↔ full-name lookup (56 rows)
```

`kyc.kyc_users` — one row per user, same row count as raw (**rows are never dropped**):

- **Identity:** `user_id` (PK), `email_token`, `ssn_masked`, `ssn_last4`
- **Dates:** `enrolled_date` (date, 2023-01-01 … 2026-05-31), `dob_raw`, `dob_year`, `dob_month`,
  `dob_month_start`, `age_at_enrollment` (**approximate, ±1 yr** — dob is month-precision only)
- **Geo:** `state_raw`, `state_code` (normalised), `state_unmapped` (bool, currently 0 rows)
- **Partners:** `onboarded_bank_partner` (4 clean values), `checking_bank_partner` (**5,747 distinct
  values, free text, deliberately not normalised**)
- **Providers:** `kyc_source`, `idology_result`, `lexis_nexis_result`, `persona_idv_result`,
  `persona_ssn_result`, `acro_result`, `manual_review_result` — all upper/trimmed, `PASS`/`FAIL`/NULL
  (Persona columns are `PASS`-or-NULL only; enforced by validated CHECK constraints)
- **Derived flags:** `is_verified` (bool), `overall_kyc_status_raw`, `is_test_user`,
  `checks_run` (0–6, count of non-null provider results), `reviewer_comment`, `has_reviewer_comment`

Indexed on: `is_verified`, `kyc_source`, `enrolled_date`, `state_code`, `idology_result`,
`onboarded_bank_partner`, `checks_run`, and a partial index on `is_test_user`.

## Established numbers — do not recompute from scratch, and do not contradict without evidence

Verified by 11 validation gates plus VALIDATEd CHECK constraints across all 2.5M rows. These are the
**final, post-bugfix** figures (see Traps #2 below) — if you see `101,159` / `50.7%` anywhere, that's
the stale pre-fix number; the corrected one is `101,201` / `50.8%`.

**Headline: non-verification runs at 7.93%** (199,515 of 2,515,262) against the brief's 5% bar.
7.90% if the 843 never-processed users are excluded. **The gap is real, not a denominator artefact.**

Non-verifications split into genuine rejection vs avoidable process loss (excludes 107 test accounts):

| Bucket | Users | % of non-verified |
|---|---:|---:|
| A. No check ever ran | 843 | 0.4% |
| B. **Failed Idology, never routed onward** | **101,325** | **50.8%** |
| C. Ran 2+ automated checks, never reached manual review | 48,598 | 24.4% |
| D. Genuine rejection — assessed incl. manual review, still failed | 48,655 | 24.4% |

A+B are process losses (~51.2%), C is partly avoidable (~24.4%), D is the irreducible floor
(~24.4%). **Over half of all non-verifications never reached a second provider at all**, against a
brief describing a multi-step waterfall. That routing gap is the highest-leverage Task 1 finding —
confirmed with a like-for-like comparison: users who failed Idology and *were* routed onward
recovered at **48.09%**; those left stranded recovered at **0.01%** (12 of 101,201).

Waterfall depth (`checks_run`): 87.3% of users get exactly 1 check (95.4% of them verify); 10.2% get
2 (75.8% verify); 2.3% get 3 (43.7%); 0.18% get 4; 2 users get 5. Nobody gets 6.

Outcome by `kyc_source`: IDOLOGY 2,078,101 users / 0.02% not verified · NULL 197,314 / **99.99%** ·
ProviderA_Lexis_Nexis 149,364 / 0.45% · ACRO 44,563 / 0.60% · MANUAL_REVIEW 22,156 / 0.14% ·
ProviderB_Lexis_Nexis 15,998 / **1.54%** · PERSONA_SSN 5,146 / 2.93% · PERSONA_IDV 2,513 / **14.37%** ·
Test_user 107 / 87.85%.

Raw result columns: idology PASS 2,132,944 / FAIL 288,134 / null 94,184 · lexis PASS 183,408 / FAIL
93,591 · persona_idv PASS 2,595 · persona_ssn PASS 10,733 · acro PASS 51,189 / FAIL 63,038 ·
manual PASS 24,032 / FAIL 50,396 · overall true 2,315,747 / false 199,515.

## Traps — each of these has already bitten, or would have

1. **`kyc_source` NULL is by design, not missing data.** It names the provider that *cleared* a user,
   so it is empty precisely when nobody did. Confirmed: **zero `PASS` values anywhere** among those
   197,314 rows. Filtering them out as "bad data" deletes 98.9% of all rejections and reports 0.09%.
   That denominator is **circular and must never be a headline** — it is documented in the audit log
   only to show the trap was considered and rejected.
2. **Three-valued logic on `is_test_user`.** A bare `(kyc_source = 'Test_user')` evaluates to NULL —
   not false — wherever `kyc_source` is NULL, and `WHERE NOT is_test_user` then silently drops
   197,314 rows. Fixed with `coalesce(..., false)`, `NOT NULL` on every boolean flag, and a
   dedicated validation gate. **Apply the same care to any new derived boolean.**
3. **`wc -l` overstates the row count.** It reports 2,515,291; the true record count is **2,515,262**.
   Eight `reviewer_comment` values contain embedded newlines inside quoted fields. Always use a real
   CSV parser and `FORMAT csv`.
4. **`state` mixes `OH` with `Ohio`** — 103 distinct values for 50-odd states. A naive `GROUP BY state`
   understates every affected state and invents duplicate rows. Use `state_code`. (Worth a sanity
   check: if verification rates differ sharply between `OH` and `Ohio`, the capture route is itself a
   signal, not noise.)
5. **`age_at_enrollment` is approximate.** `dob` is `MM/YYYY`; casting to a full date would invent a
   day and imply precision that does not exist. The 1922 tail (age ~104) deserves an outlier check
   before age is used as a driver.
6. **107 `Test_user` rows are flagged, not deleted** — deleting would hard-code a denominator choice.

## How this project works — conventions to keep

These were chosen deliberately; keep them unless there's a reason not to.

- **Answer first, then support it.** Every deliverable leads with the number or the recommendation.
- **Rows are never dropped.** Every exclusion is a *flag*, so the analyst picks the denominator, not
  the loader. Report candidate denominators side by side with the reasoning visible.
- **The audit log is the deliverable's backbone.** Every loading and cleaning decision, every
  assumption, every quirk, and every defect is recorded in [AUDIT_LOG.md](AUDIT_LOG.md) so any
  downstream number can be traced to a decision and defended or revised. **Corrections are marked in
  place, not overwritten** (see Defect 2 there for the pattern).
- **Constraints are assertions, not decoration.** CHECK constraints are added `NOT VALID` then
  explicitly `VALIDATE`d, which tests every one of 2.5M rows against the domain the brief claims. If
  the data contradicts the brief, the load fails loudly.
- **The notebook is idempotent** — a re-run drops and rebuilds `kyc_raw` / `ref_state` / `kyc_users`
  and appends a timestamped run record to the audit log automatically (last cell, `RUN-HISTORY` marker).
- **Safety rail:** the notebook refuses to run if schema `kyc` contains any table it did not create
  (anything outside `{kyc_raw, ref_state, kyc_users}`), because `study` is a shared database.
  Override with `ALLOW_FOREIGN_OVERWRITE = True` in cell 4. *Note: AUDIT_LOG.md §"Reproducing this"
  calls this flag `ALLOW_SCHEMA_REBUILD` and describes it as blocking any non-empty schema — the
  code is the accurate version; fix the log when next editing it.*

## Task 1 findings, in brief

Done — full reasoning in [notebooks/02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb)
and AUDIT_LOG.md §9, presentation-ready version at
[Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018).

- **Waterfall reconstructed from column co-occurrence** (a non-null provider column = that check
  ran). The brief's described flow mostly holds, with five confirmed divergences: an undocumented
  second entry point at `ProviderA_Lexis_Nexis` (3.7% of traffic, skips Idology, ~100% pass — a
  control question, not just a routing one); Idology passes that still get a non-blocking LexisNexis
  check; the 35.1%-of-failures routing gap (bucket B above, the main finding); the "older accounts →
  Persona-SSN" rule showing **no** age or vintage signal in the data (not reproducible, said so
  honestly rather than guessed); manual review reaching only 30.2% of eligible users.
- **The two LexisNexis routes are confirmed to play different roles**, not the same check twice:
  ProviderA sits in *primary* position (93,319 of 149,364 users never saw Idology), ProviderB in
  *secondary/SSN* position (11,677 of 15,998 arrive after an Idology failure).
- **SSN vs non-SSN failure classification**: `reviewer_comment` (74,428 rows, 2.96%) was pattern-matched
  into a reason taxonomy — usable for the *reviewed* population only, explicitly not extrapolated to
  the whole book (stated as caveat, since the stranded population has zero comments).
- **PERSONA_IDV** clears 86.3% of the failures it's tried on (vs 30.7% without it) but runs on <1%
  of Idology failures — flagged as under-deployed, not as a quality problem.
- **The prize is quantified**, not guessed: the 101,201 stranded users, routed at the *observed*
  recovery rate of comparable routed-onward users (48.09%), would recover ~48,649 people, taking the
  rate from 7.93% to ~6.0%. Stated plainly as a comparison-group estimate, not a guarantee.

## Task 2 findings, in brief

Done — full logic and every number's derivation in
[TASK2_WATERFALL_DESIGN.md](TASK2_WATERFALL_DESIGN.md), diagram version at
[The Waterfall, Rebuilt](https://claude.ai/code/artifact/49e52e3d-08f8-49bc-a5ee-2dc1a300051d).
Design exercise built on Task 1's findings — no new tables, no notebook, one supporting SQL check
(AUDIT_LOG.md §11; §10 there is a full audit of every flow in the data, valid vs invalid — see
"Task 2 findings" below).

- **The core move:** a reason classifier (new L1.5) tags every Idology FAIL as `SSN_MISMATCH` /
  `IDENTITY_ATTR_MISMATCH` / `SANCTIONS_HIT` / `NO_DATA`, and the routing tree guarantees every class
  reaches a defined fallback and, if that fails too, manual review. "Stranded" (Finding 1) becomes
  structurally impossible rather than merely less likely.
- **New evidence found while building this, not in the original Task 1 pass:** all 9,994
  sanctions/PEP/watchlist mentions in `reviewer_comment` sit inside an `idology_result='FAIL'`, and
  **zero** of the 101,201 stranded users have any reviewer comment at all — so today's design has no
  way to know whether any stranded user carried an undetected sanctions signal. Sanctions/PEP is
  therefore split into its own always-checked flag with a **hard, immediate** route to
  compliance — skipping automated fallbacks rather than waiting for them to fail first. This is why
  the redesign is risk-**positive**, not merely risk-neutral.
- **Removed:** the `ProviderA_Lexis_Nexis` undocumented-bypass entry point (Finding 5) and the
  unreproducible "older accounts → Persona-SSN" rule (Finding 4) — both retired rather than
  preserved-with-caveats, since neither could be defended if probed.
- **Modelled effect:** 7.93% → ~6.0% from routing the stranded population alone, at the *observed*
  48.09% recovery rate (not the pre-existing 48,649-person estimate re-derived, the same one, reused
  with its caveat carried forward).
- **The real trade-off, stated plainly:** manual review volume goes up ~2.4× (illustrative ~$238K/yr,
  ~8 FTE) to make this work — the single biggest number in the design, sized from real Task 1
  proportions but illustrative unit costs, and the first thing to challenge with real ops numbers.

## Open threads for Task 3 (build docs)

- **The reason classifier (L1.5) is the load-bearing engineering dependency** the whole Task 2 design
  assumes — confirming what Idology's actual API response contains (or can be made to contain) is
  the first build item, before anything else in the PRD is actionable.
- **The ~2.4× manual review increase needs a phased rollout**, not a day-one flip — Task 3's rollout
  plan should size a ramp, not a single cutover.
- No provider **cost or latency** data exists in this dataset — Task 2's figures used illustrative
  unit costs on real volumes; Task 3's ARD/monitoring plan should specify what real numbers to
  instrument and collect, not assume Task 2's placeholders.
- Both the 48,649-person recovery estimate (Task 1) and the ~2.4× review-volume estimate (Task 2)
  are comparison-group projections, not controlled results — carry that caveat every time either is
  quoted, not just the first time.

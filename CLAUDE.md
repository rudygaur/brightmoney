# CLAUDE.md — Brightmoney APM KYC Case Study

Working context for this project. Read this first in any new session.

## What this is

A take-home case study for a **Back-end Product Management (APM) track** role. It is *not* a
software project — the deliverables are analysis and product documents, and the code exists only to
make the numbers defensible.

Brief: [APM KYC_Design_Project_Assignment_Instructions.md](APM%20KYC_Design_Project_Assignment_Instructions.md)
Data-loading record: [AUDIT_LOG.md](AUDIT_LOG.md)
Load code: [notebooks/01_kyc_load_and_setup.ipynb](notebooks/01_kyc_load_and_setup.ipynb)

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
| Task 1 | Funnel analysis — headline rate, causes, 2–3 highest-leverage problems. **As a presentation.** | **Not started** (evidence largely gathered, see below) |
| Task 2 | Redesigned waterfall — diagram + decision logic + rationale. Every change tied to a Task 1 finding. | **Not started** |
| Task 3 | PRD + ARD/monitoring plan + project plan. | **Not started** |

## Environment

```bash
cd /Users/rudransh/d_drive/GITHUB/Brightmoney
docker start postgres                       # server must be up on :5432
.venv/bin/jupyter lab notebooks/01_kyc_load_and_setup.ipynb
```

- **Server:** PostgreSQL **18.1** in Docker container named `postgres`, published `0.0.0.0:5432`.
- **Database:** `study` (pre-existing and shared — *not* created by this work). **Schema: `kyc`.**
- **Client:** `.venv/` — Python 3.13, psycopg 3.3.5, pandas 3.0.5, jupyterlab, python-dotenv.
- **Credentials:** `.env` holds **only** `PGPASSWORD` (chmod 600, git-ignored). Everything else falls
  back to `localhost` / `5432` / `postgres` / `study`. Never print the password or write it to a file.
- Not a git repository. `.gitignore` exists in anticipation.

**Two environment traps, both already hit once:**

1. A macOS EDB PostgreSQL **17** install at `/Library/PostgreSQL/17` is what bare `psql` resolves to.
   It is **not running**. Its v17 client binaries will connect to the v18 container but `pg_dump`
   from them will refuse. Use the venv/psycopg path, or the container's own `psql`.
2. The server is in a container, so it **cannot see `/Users/rudransh/...`**. Server-side
   `COPY ... FROM '<path>'` is impossible regardless of privileges. The load streams from the client
   with `COPY ... FROM STDIN` in 4 MB chunks.

**Roles:** `kyc_ro` (SELECT — the right role for ad-hoc analysis), `kyc_rw`, `kyc_owner`. All NOLOGIN
group roles granted to `postgres`. `ALTER DEFAULT PRIVILEGES` is set, so new tables in `kyc` inherit.

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

Verified by 11 validation gates plus VALIDATEd CHECK constraints across all 2.5M rows.

**Headline: non-verification runs at 7.93%** (199,515 of 2,515,262) against the brief's 5% bar.
7.90% if the 843 never-processed users are excluded. **The gap is real, not a denominator artefact.**

Non-verifications split into genuine rejection vs avoidable process loss:

| Bucket | Users | % of non-verified |
|---|---:|---:|
| 1. No check ever ran | 843 | 0.4% |
| 2. **Failed Idology, never routed onward** | **101,159** | **50.7%** |
| 3. Ran 2+ checks, failed them all | 97,419 | 48.9% |

Buckets 1 and 2 are process losses. **Over half of all non-verifications never reached a second
provider at all**, against a brief describing a multi-step waterfall. That routing gap is the
highest-leverage Task 1 finding.

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

## Open threads for Task 1

Evidence still to gather before the Task 1 presentation can be written:

- **Reconstruct the actual waterfall from the data** — which checks fire, in what order, and how
  users route between SSN and non-SSN paths. The brief's described flow (Idology → split by failure
  type → LexisNexis / Persona-SSN vs ACRO / Persona-IDV → manual review) is a *hypothesis to confirm*,
  and the `checks_run` distribution above already suggests it largely does not run as described.
- **The two LexisNexis routes.** `ProviderA_Lexis_Nexis` (149,364) and `ProviderB_Lexis_Nexis`
  (15,998) both write to `lexis_nexis_result` but are different integration paths. ProviderB's
  non-verification rate is 3.4× ProviderA's. Working out how each is routed and whether they behave
  differently is explicitly part of Task 1.
- **SSN vs non-SSN failure classification.** The brief says Idology failures are logged by reason,
  but there is no reason column. `reviewer_comment` is populated on only 74,428 rows (2.96%) and is
  the only free-text signal available — check whether it can classify failure type, and say so
  honestly if it cannot.
- **PERSONA_IDV's 14.37% non-verification rate** is the worst of any named source, on a small
  population (2,513). Worth explaining before Task 2 leans on document/selfie verification.
- **Quantify the prize:** of the 101,159 users who failed Idology and were never routed onward, how
  many would plausibly have cleared a secondary check? Pass rates of the secondary providers on
  comparable populations are the input. This estimate is what sizes the Task 2 recommendation.
- Also owed by the brief: name the data caveats hit and how they were handled (§Traps above covers
  this — it needs writing up for the presentation, not re-discovering).

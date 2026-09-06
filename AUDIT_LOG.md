# KYC Dataset — Audit Log

Record of every step taken to load `KYC_Synthetic_Dataset.csv` into PostgreSQL, including the
assumptions made and the decisions that could reasonably have gone another way.

Maintained so that any number produced downstream can be traced back to a specific loading or
cleaning decision, and defended or revised.

| | |
|---|---|
| **Dataset** | `KYC_Synthetic_Dataset.csv` — 273,899,427 bytes (272 MB) |
| **Records** | 2,515,262 (see Q1 — this is *not* `wc -l`) |
| **Target** | PostgreSQL 18.1, database `study`, schema `kyc` |
| **Code** | [01_kyc_load_and_setup.ipynb](notebooks/01_kyc_load_and_setup.ipynb) (load) · [02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb) (Task 1) |
| **Started** | 2026-09-06 |
| **Status** | Loaded and validated (11/11 checks) · **Task 1 complete** · Tasks 2–3 outstanding |
| **Quick reference** | [IMPORTANT.md](IMPORTANT.md) — headline numbers, traps and judgement calls |
| **New to this project?** | [README.md](README.md) has the one-paragraph summary and setup |

**In a hurry?** Read [Status and headline findings](#status-and-headline-findings) just below, then
jump straight to whichever numbered section you need — everything here is written to be read out of
order.

<details>
<summary><b>Contents</b> (click to expand)</summary>

- [Status and headline findings](#status-and-headline-findings) — the short version, for anyone skimming
- [1. Environment](#1-environment) — what server this ran against, and why the code doesn't care
- [2. Credentials](#2-credentials)
- [3. Profiling before loading](#3-profiling-before-loading) — what the CSV actually contains
- [4. Load design — two layers](#4-load-design--two-layers)
- [5. Transformations](#5-transformations-applied-between-kyc_raw-and-kyc_users) — raw → analysis-ready
- [6. Roles and grants](#6-roles-and-grants)
- [7. Validation gates](#7-validation-gates) — the 11 checks that must pass
- [8. Defects found and fixed](#8-defects-found-and-fixed-during-this-work) — two real bugs, caught and corrected
- [9. Task 1 — funnel analysis](#9-task-1--funnel-analysis-method-and-findings) — the actual answer
- [Open questions, quirks and how they were handled](#open-questions-quirks-and-how-they-were-handled) — **Q1–Q8, the traps in this dataset**
- [Reproducing this](#reproducing-this) — how to re-run it yourself
- [Run history](#run-history) — timestamped log auto-appended by the notebooks

</details>

---

## Status and headline findings

The load is complete and reconciled. `kyc.kyc_users` holds all 2,515,262 users, typed, constrained
and indexed, and is ready to analyse.

Three things the data already says, before any Task 1 work:

1. **Non-verification runs at 7.93%** (199,515 of 2,515,262), against the brief's 5% acceptable bar.
   Excluding test users and the 843 users no check ever ran on moves it to 7.90% — the gap is real,
   not a denominator artefact. See Q5 for the denominators considered and why one of them is a trap.

2. **Over half of all non-verifications never reached a second check.** 101,162 users (50.8% of
   non-verifications) failed Idology and then had *nothing* else run — no LexisNexis, no ACRO, no
   Persona, no manual review — against a brief that describes a multi-step waterfall. This is an
   avoidable process loss, not a genuine rejection, and it is the largest single bucket in the file.
   Users who failed the same check and *were* routed onward recovered at 48.09%; these recovered at
   0.01%. See Q4 and §9.

3. **`kyc_source` is null by design, not missing.** It names the provider that *cleared* a user, so
   it is empty precisely when nobody did — confirmed by zero `PASS` values anywhere among those
   197,314 rows. Any analysis that filters them out as "bad data" deletes 98.9% of the rejections and
   reports ~0.1%. See Q4 and Defect 2.

Two data quirks that will corrupt results if not handled: `state` mixes `OH` with `Ohio` (Q2), and
`wc -l` overstates the row count because of embedded newlines (Q1).

---

## 1. Environment

Established by inspection, not assumption — the first attempt was aimed at the wrong server. Kept
here as the record of *this run*; none of it is a requirement of the code, which is written to be
generic (see the callout below and README's Setup section).

| Item | Value (this run) |
|---|---|
| Server | PostgreSQL **18.1** (Debian 18.1-1.pgdg13+2), aarch64 Linux |
| Deployment | Docker container `postgres`, image `postgres`, `0.0.0.0:5432->5432/tcp` |
| Client | psycopg 3.3.5 on Python 3.13.15, in project venv `.venv/` |
| Database | `study` (pre-existing — **not** created by this work) |
| Schema | `kyc` (created by this work; `public` was left untouched) |

**Note on a false start.** This dev machine also has a macOS EDB PostgreSQL 17 install at
`/Library/PostgreSQL/17`, and its client binaries are what a bare `psql` resolves to. It was **not**
running, and its data directory is owned by a separate `postgres` OS user — not the account doing
this work. The server actually listening on 5432 turned out to be the Docker container above, on a
*different major version*. This matters beyond this one project: `/Library/PostgreSQL/17/bin/psql`
will happily connect to a v18 server, but `pg_dump` from those v17 binaries against it will refuse.
**General lesson:** don't assume `psql`/`pg_dump` on `PATH` belong to the server you're actually
talking to — check `psql --version` against the server's own `select version()` first, on any
machine, Docker or native.

**Consequence for loading — and why the code is generic, not Docker-specific.** A containerised
server cannot see the host filesystem at all, so server-side `COPY ... FROM '<path>'` was never
going to work here. But that same command is *also* unreliable on a plain native install, for a
different reason: the Postgres server process commonly runs as its own OS user (`postgres`), which
has no access to *your* home directory either — exactly the EDB v17 situation above. Since neither
environment can be trusted to read an arbitrary local path, the load streams the file from the
*client* with `COPY ... FROM STDIN` instead (see §4), which works identically on Docker, a native
install, or a remote server. This project's own notebooks connect over TCP via `.env` and never
special-case which kind of Postgres is on the other end — see
[README.md](README.md#setup--works-with-docker-or-a-native-postgres-install) for both setups.

---

## 2. Credentials

- Password supplied by the user in `.env` at the project root, as `PGPASSWORD` (this run's Docker
  container required one). `PGPASSWORD` is **not mandatory** in general, though — the notebooks pass
  `None` rather than an empty string when it's unset, so a native install using peer/trust auth
  (common on a fresh local Postgres.app or Homebrew setup) works with `.env` omitting it entirely.
  See `.env.example` for both cases.
- `.env` is **git-ignored** (`.gitignore` created) and set to `chmod 600` (it was world-readable `644`).
- The notebook reads it via `python-dotenv`. Everything else (`PGHOST`, `PGPORT`, `PGUSER`,
  `PGDATABASE`) falls back to `localhost` / `5432` / `postgres` / `study`.
- The password does not appear in the notebook, in this log, or in any committed file.

Connecting as superuser `postgres` — required to create roles. Day-to-day analysis should use the
`kyc_ro` role (§6). On a native install this may instead be your OS username acting as superuser.

---

## 3. Profiling before loading

The CSV was parsed in full **before** any DDL was written, so column types were chosen from what the
file contains rather than from what the brief describes. This also produced an independent record
count used to reconcile the load (§7).

Findings that shaped the schema:

| Finding | Effect |
|---|---|
| 2,515,262 records, 17 columns, **zero ragged rows** | Clean structure; no repair logic needed. |
| `Fabricated_UID` unique across all rows, no nulls | Usable as the primary key. |
| Quoted fields containing commas **and newlines** | Must use a real CSV parser, and `FORMAT csv` on load. See Q1. |
| `Fabricated_SSN` is `*****NNNN` in 100% of rows | Safe to derive `ssn_last4`; no full SSNs present. |
| `enrolled_date` uniformly `YYYY-MM-DD`, range 2023-01-01 … 2026-05-31, no bad values | Direct cast to `date`. |
| `dob` is `MM/YYYY` (month precision only), range 1922-05 … 2008-05, 868 empty | Stored as year + month + month-start date. See D3. |
| `state` mixes USPS codes **and** full names — 103 distinct values | Normalisation required. See Q2. |
| `kyc_source` contains `Test_user` (107 rows) | Flagged, not deleted. See Q3. |
| `overall_kyc_status` is the *string* `'true'`/`'false'` | Cast to `boolean`. See D1. |
| Persona columns only ever `PASS` or null — no `FAIL` | Matches the brief; enforced by CHECK constraint. |
| `checking_bank_partner` has **5,747** distinct values | Left as free text; not an enum. See D5. |

Null rates per column (empty string in the file):

| Column | Empty | % |
|---|---:|---:|
| `dob` | 868 | 0.03% |
| `state` | 878 | 0.03% |
| `onboarded_bank_partner` | 12,857 | 0.51% |
| `checking_bank_partner` | 101,091 | 4.02% |
| `kyc_source` | 197,314 | 7.84% |
| `idology_result` | 94,184 | 3.74% |
| `lexis_nexis_result` | 2,238,263 | 88.99% |
| `persona_idv_result` | 2,512,667 | 99.90% |
| `persona_ssn_result` | 2,504,529 | 99.57% |
| `acro_result` | 2,401,035 | 95.46% |
| `manual_review_result` | 2,440,834 | 97.04% |
| `reviewer_comment` | 2,440,834 | 97.04% |

`Fabricated_UID`, `Fabricated_Email`, `Fabricated_SSN`, `enrolled_date` and `overall_kyc_status` are
100% populated.

---

## 4. Load design — two layers

Deliberately split so cleaning is reviewable rather than baked into the import.

```
KYC_Synthetic_Dataset.csv
        │  COPY ... FROM STDIN (format csv, header true)   ← no transformation
        ▼
kyc.kyc_raw      all TEXT, no constraints, verbatim
        │  INSERT ... SELECT with explicit casts           ← every transformation visible here
        ▼
kyc.kyc_users    typed, constrained, indexed               ← analyse from here
```

- **`kyc_raw` is all `TEXT` on purpose.** A bad value cannot abort a 2.5M-row load; it survives as a
  visible data-quality finding instead. The raw layer stays available to re-check any cleaning call.
- **Streamed client-side in 4 MB chunks**, for the container reason in §1.
- **`kyc.ref_state`** — USPS code ↔ name lookup, supporting the `state` normalisation in Q2.

---

## 5. Transformations applied between `kyc_raw` and `kyc_users`

Rows are never dropped. `kyc_users` has exactly the same row count as `kyc_raw`; every exclusion is
expressed as a *flag* so the analyst chooses the denominator, not the loader.

| # | Transformation | Rationale |
|---|---|---|
| D1 | `overall_kyc_status` `'true'`/`'false'` → `is_verified boolean` | Stored as text in the CSV. Boolean makes rate arithmetic safe and lets `count(*) filter (...)` work. Original kept as `overall_kyc_status_raw`. |
| D2 | `enrolled_date` → `date` | Uniform format, zero bad values, so a plain cast is safe. |
| D3 | `dob` → `dob_year`, `dob_month`, `dob_month_start` | The source has **month precision only**. Casting to a full `date` would invent a day-of-month and imply precision that does not exist. `dob_month_start` (1st of month) exists purely for date arithmetic. |
| D4 | `state` → `state_code` via `ref_state` | See Q2. `state_raw` preserved; `state_unmapped` flags any value that matched neither a code nor a name. |
| D5 | Provider result columns → `upper(btrim(...))` | Guards against case and whitespace drift. `checking_bank_partner` deliberately **not** normalised — 5,747 distinct values is a free-text field, and collapsing it would be a judgement call belonging to analysis, not loading. |
| D6 | `kyc_source = 'Test_user'` → `is_test_user boolean`, built with `coalesce(..., false)` | See Q3. The `coalesce` is load-bearing, not defensive habit — without it the flag is `NULL` wherever `kyc_source` is, and `WHERE NOT is_test_user` drops those rows silently. See Defect 1 in §8. |
| D7 | `ssn_last4` from the `*****NNNN` mask | Convenience only; mask kept verbatim as `ssn_masked`. |
| D8 | `age_at_enrollment` derived | Useful cut for diagnosing failures. **Approximate** — month precision means it can be off by up to a year. |
| D9 | `checks_run` — count of non-null provider result columns | The basis for waterfall-depth analysis (how deep each user travelled). |
| D10 | `has_reviewer_comment boolean` | `reviewer_comment` is 97% null; a flag makes the populated subset easy to isolate. |

**Constraints as assertions.** The CHECK constraints on the result columns are added `NOT VALID` and
then explicitly `VALIDATE`d. This is not decoration — validating them is a test that every value in
2.5M rows falls inside the domain the brief claims (`PASS`/`FAIL`, and `PASS`-only for Persona). If
the data contradicted the brief, the load would fail loudly here.

---

## 6. Roles and grants

Three `NOLOGIN` group roles, so privileges can be handed out without sharing the superuser:

| Role | Privileges on schema `kyc` |
|---|---|
| `kyc_ro` | `USAGE` on schema, `SELECT` on all tables — **the right role for ad-hoc analysis** |
| `kyc_rw` | above plus `INSERT`/`UPDATE`/`DELETE`, sequence usage |
| `kyc_owner` | `ALL PRIVILEGES`, plus `CREATE` on the schema |

`ALTER DEFAULT PRIVILEGES` is set so tables created in `kyc` later inherit the same grants without a
manual re-grant. All three roles are granted to the connecting user (`postgres`).

---

## 7. Validation gates

The notebook asserts all of the following and raises if any fails; the load is not considered done
unless they pass. Current status: **11/11 PASS**.

1. Rows loaded into `kyc_raw` **equal** the record count from the independent Python CSV parse.
   (Guards against the `wc -l` trap in Q1 and against silent truncation.)
2. `kyc_users` row count equals `kyc_raw` row count — proof no rows were dropped in cleaning.
3. `user_id` unique and non-null (enforced by primary key).
4. No nulls in `user_id`, `enrolled_date`, `is_verified`.
5. **No nulls in any boolean flag** — the three-valued-logic guard added after Defect 1 below.
6. Every non-null `state` mapped to a USPS code — `state_unmapped` count is zero.
7. `overall_kyc_status` only ever `'true'`/`'false'`.
8. Verified count identical before and after the boolean cast.
9. `is_test_user` count matches a direct `Test_user` count against the raw layer.
10. The test / no-source / sourced populations partition the table with nothing unaccounted for.
11. Per-column null counts in the database reconcile against the pre-load CSV profile.

Separately, the `CHECK` constraints on the six provider columns are added `NOT VALID` and then
explicitly `VALIDATE`d, which asserts across all 2.5M rows that every value falls inside the domain
the brief claims (`PASS`/`FAIL`, and `PASS`-only for Persona). All validated clean.

---

## 8. Defects found and fixed during this work

Recorded because both were caught by the checks rather than by reading the code, and both would have
changed the answer rather than crashed.

### Defect 1 — `is_test_user` was NULL, not false, for 197,314 rows
**Introduced:** first version of the `kyc_users` build, as `(kyc_source = 'Test_user')`.
**Effect:** `kyc_source` is NULL for 7.84% of rows, so that expression evaluated to `NULL` — not
`false` — on every one of them. A later `WHERE NOT is_test_user` therefore discarded 197,314 users
*silently*, alongside the 107 genuine test accounts. In SQL's three-valued logic `NOT NULL` is `NULL`,
and `WHERE NULL` excludes the row.
**How it surfaced:** the §8 smoke test printed two populations that were supposed to differ by 107
rows and instead showed byte-identical counts (2,317,841 / 2,123 for both).
**Severity:** high. The rows it dropped are 98.9% of all non-verifications — the headline number
would have been wrong, and wrong in the flattering direction.
**Fix:** `coalesce(kyc_source = 'Test_user', false)`, plus `NOT NULL` on every boolean flag and a
dedicated validation gate (#5), so a recurrence fails the load instead of skewing a result.

### Defect 2 — wrong hypothesis recorded for the null-`kyc_source` population
**Introduced:** this log's first draft, which named "users who never entered the waterfall" as the
leading explanation.
**Effect:** would have justified excluding ~197k rows and reporting ~0.1% instead of 7.93%.
**How it surfaced:** adding the fourth denominator (exclude only users where no check actually ran)
produced 7.90%, nowhere near the ~0.1% the hypothesis predicted. Breaking the group down by
provider-result pattern then showed zero `PASS` values anywhere in it.
**Fix:** Q4 rewritten with the evidence and the correction marked in place rather than overwritten.

---

## Open questions, quirks and how they were handled

### Q1 — `wc -l` overstates the row count
`wc -l` reports 2,515,291 lines; the true record count is **2,515,262**. Eight `reviewer_comment`
values contain embedded newlines inside quoted fields, and a further set contain embedded commas
(naive comma-splitting yields rows of 18–23 fields, and some of 1–2).

**Handled:** parsed with a real CSV reader in Python, and loaded with `FORMAT csv` so PostgreSQL
applies the same quoting rules. The two counts are asserted equal (gate 1).
**Assumption:** RFC-4180 quoting throughout — supported by zero ragged rows under a proper parser.

### Q2 — `state` mixes two formats
103 distinct values: USPS codes *and* full names, for the same states. `OH` appears 76,705 times and
`Ohio` a further 26,219; `VA` and `Virginia`, `AL` and `Alabama`, and ~48 others likewise. Naive
`GROUP BY state` **understates every affected state** and invents duplicate rows per state.

**Handled:** `kyc.ref_state` lookup; `state_code` resolves either form to a single USPS code.
`state_raw` is preserved and `state_unmapped` flags anything unresolved.
**Assumption:** the two forms are the same population, differing only in capture format (plausibly
two onboarding paths), and are safe to merge. Worth a sanity check during analysis — if verification
rates differ sharply between `OH` and `Ohio`, the capture route may itself be a signal rather than
noise. 878 rows (0.03%) have no state at all; left as `NULL`.

### Q3 — `Test_user` rows
`kyc_source = 'Test_user'` on 107 rows (94 not verified, 13 verified). These are almost certainly
internal test accounts, not real users, and including them inflates the rejection rate very slightly.

**Handled:** flagged as `is_test_user`, **not deleted**. Deleting would hard-code a denominator
choice into the data.
**Assumption:** they are non-production accounts and should be excluded from headline rates. Flagging
keeps that reversible, and lets the exclusion be stated openly rather than hidden.

### Q4 — 197,314 rows have no `kyc_source` — and 197,298 of them are unverified
7.84% of users carry a null `kyc_source`, and **99.99% of them are unverified**. This single group is
~98.9% of all non-verifications (197,298 of 199,515), so what it represents decides the headline rate.

Three readings were possible: users who never entered the waterfall; users who exhausted it; or a
logging gap where `kyc_source` was simply not written back.

**Resolved — it is exhaustion, not a data artefact.** Breaking the group down by provider-result
pattern (notebook §8) shows that **not one of these 197,314 users has a single `PASS` on any
provider**. Every recorded result is `FAIL`. `kyc_source` is therefore not missing data: it names the
provider that *cleared* a user, so it is null by design whenever nobody did.

> **Correction.** An earlier revision of this log recorded the leading hypothesis as "users who never
> entered the waterfall". That was wrong, and the evidence above overturned it. Only 843 users
> (0.4% of non-verifications) genuinely had no check run. The distinction matters: had it stood, it
> would have argued for excluding ~197k rows from the denominator and reporting a rejection rate near
> 0.1% instead of 7.93%.

**The finding this exposes.** Within that group, the single largest pattern is users who failed
Idology and then had **nothing else run at all** — no LexisNexis, no ACRO, no Persona, no manual
review. Splitting all non-verifications (excluding test users):

| Bucket | Users | % of non-verified |
|---|---:|---:|
| 1. No check ever ran | 843 | 0.4% |
| 2. **Failed Idology, never routed onward** | **101,159** | **50.7%** |
| 3. Ran 2+ checks, failed them all | 97,419 | 48.9% |

Buckets 1 and 2 are process losses — the waterfall never finished running on them. Bucket 3 is where
genuine rejection lives. **Over half of all non-verifications never reached a secondary provider at
all**, against a brief that describes a multi-step waterfall with SSN and non-SSN paths. Closing that
routing gap is the highest-leverage lead for Task 1; quantifying how many of those 101,159 would have
cleared a secondary check is the analysis that follows.

### Q5 — which denominator for the rejection rate?
Four candidate populations, reported side by side rather than silently picked (figures from the run
below, not hand-computed):

| Population | Users | Not verified | Rate |
|---|---:|---:|---:|
| All rows | 2,515,262 | 199,515 | **7.93%** |
| Excluding test users | 2,515,155 | 199,421 | **7.93%** |
| Excluding test users **and** null `kyc_source` | 2,317,841 | 2,123 | 0.09% |
| Excluding test users **and** rows where no check ran | 2,514,312 | 198,578 | **7.90%** |

**Use 7.93%** (or 7.90% if the 843 never-processed users are excluded). Either way the dataset sits
well above the brief's 5% bar.

The third row is **circular and must not be used as a headline**: per Q4, `kyc_source` is null exactly
when no provider passed, so excluding those rows excludes almost every rejection by construction and
manufactures a 0.09% rate. It is listed only to document that the trap was considered and rejected —
it is the kind of denominator that looks defensible until you ask what the column means.

**Handled:** the notebook prints all four with this reasoning inline, so the choice is visible and
arguable rather than buried in the loader.

### Q6 — `dob` has only month precision
`MM/YYYY`, so exact age is unknowable. Range 1922-05 to 2008-05; the 1922 tail implies age ~104 at
enrolment, which is possible but sparse — worth an outlier check before using age as a driver.
**Handled:** `age_at_enrollment` derived from the month start and documented as approximate (±1 year).

### Q7 — `checking_bank_partner` has 5,747 distinct values
Unlike `onboarded_bank_partner` (4 clean values), this is long-tailed: `Bank A`…`Bank N` cover the
bulk, then thousands of rare labels. 4.02% are null.
**Handled:** loaded as free text, not normalised. Any grouping (e.g. top-N plus "other") is an
analysis decision, and doing it here would silently discard the tail.

### Q8 — empty string vs true NULL
The brief states nulls are stored as empty strings. In `FORMAT csv`, PostgreSQL's default NULL marker
*is* an unquoted empty field, so these land as real SQL `NULL`s automatically.
**Assumption:** empty means "check did not run", per the brief — there is no separate "ran and
returned nothing" state. Every empty is therefore a genuine `NULL`. `nullif(btrim(...), '')` is also
applied in the typed layer to catch any whitespace-only value that quoting might have preserved.

---

## 9. Task 1 — funnel analysis: method and findings

Code: [notebooks/02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb).
**Read-only** — no DDL, no writes to `kyc`. A summary for recall is in `IMPORTANT.md`.

### Method, in order

1. **Settled the denominator before quoting any rate.** Four candidate populations computed side by
   side. Three are defensible; the fourth (excluding null `kyc_source`) is circular and was rejected
   with evidence rather than by preference — see Q5.
2. **Reconstructed the waterfall from column co-occurrence.** A non-null provider column means that
   check ran for that user, so which columns are populated together *is* the routing evidence. No
   event log is needed.
3. **Tested each documented rule against the data instead of assuming it.** This is what surfaced the
   undocumented second entry point, the non-blocking post-PASS checks, and the unreproducible
   "older accounts" rule. Confirming the design was explicitly part of the brief.
4. **Checked whether each defect was targeted or systematic** by cutting it against partner and
   enrolment year. Uniformity is itself a finding: it rules out one bad integration or one bad
   release, and points at the routing logic.
5. **Classified non-verifications by how far the waterfall actually got**, not by failure reason —
   because the question asked is genuine rejection vs avoidable process loss.
6. **Sized the opportunity from an observed comparison group**, not an assumption: users who failed
   the same check and *were* routed onward.

### Headline findings

| | |
|---|---:|
| Non-verification rate | **7.93%** (199,515 of 2,515,262) |
| Bar | 5% (budget 125,763) |
| Users over budget | **73,752** |
| Trend | Flat across all 41 months — structural, not a regression |

**Non-verifications classified** (199,421, excluding test accounts):

| Bucket | Users | % |
|---|---:|---:|
| A. Avoidable — no check ever ran | 843 | 0.4% |
| B. Avoidable — failed 1st check, never routed on | 101,325 | 50.8% |
| C. Partly avoidable — 2+ checks failed, no manual review | 48,598 | 24.4% |
| D. Genuine — assessed incl. manual review, still failed | 48,655 | 24.4% |

**~51% avoidable, ~24% genuine.**

**The central evidence** — both cohorts failed Idology; the only difference is whether they were
routed onward:

| Cohort | Users | Recovered | Rate |
|---|---:|---:|---:|
| Routed onward | 186,866 | 89,860 | **48.09%** |
| Stranded | 101,162 | 12 | **0.01%** |

Modelled impact of routing the stranded population at the observed rate: **~48,649 users recovered,
7.93% → ~6.0%**. Flagged as an estimate, not a guarantee — see caveat 8 below.

### Waterfall discrepancies vs the documented design

| Documented | Observed |
|---|---|
| Idology is the primary check | 94,184 users (3.74%) never see it; they enter at ProviderA_LexisNexis, which passes ~100% |
| Pass Idology ⇒ verified, exit | 130,713 passed and had LexisNexis run anyway; 57,822 failed it and were still verified (~99.6%) |
| Fail ⇒ route by SSN / non-SSN reason | 35.1% of failures routed nowhere |
| SSN path splits on "older accounts" | No age or vintage signal — rule not reproducible |
| Two LexisNexis routes differ | Confirmed: ProviderA sits in primary position, ProviderB in secondary/SSN position |
| Manual review catches all-fail users | 148,713 eligible users (69.8%) never reached it |

### Analytical caveats added by this stage

7. The `reviewer_comment` reason taxonomy covers ~3% of users and is skewed toward manual review. It
   describes the reviewed population only and must not be extrapolated — the stranded users have no
   comments at all.
8. The ~48,649 recovery figure assumes stranded users resemble routed users. Supported by stranding
   being uniform across partners and years, but it is a projection. Confirm by routing a sample.
9. No provider cost or latency data exists in this extract, so Task 2's cost/friction trade-offs
   cannot be quantified from this dataset.

### Defect 3 — misleading claim about waterfall depth (found and fixed)

**Introduced:** narrative accompanying the "verification rate by number of checks" table, which
claimed users receiving 2+ checks verify at higher rates.
**Effect:** the table shows the opposite (95% → 76% → 44%), because users only go deeper when they
have already failed something. The claim inverted a selection effect and the supporting table
visibly contradicted it.
**Fix:** narrative rewritten to name the selection effect explicitly, and a like-for-like cohort
comparison added that holds "failed Idology" constant — which is the comparison that actually
isolates the effect of routing.

---

## Reproducing this

Full setup for either a Docker or a native Postgres install is in
[README.md](README.md#setup--works-with-docker-or-a-native-postgres-install) — this load does not
assume either one. Once Postgres is up and `.env` is filled in:

```bash
cd /Users/rudransh/d_drive/GITHUB/Brightmoney
.venv/bin/jupyter lab notebooks/01_kyc_load_and_setup.ipynb
```

Run the cells top to bottom. They are idempotent — a re-run drops and rebuilds `kyc_raw` and
`kyc_users` and re-appends a run record below.

The notebook refuses to run if the `kyc` schema contains any table it did not create itself (i.e.
anything other than `kyc_raw`, `ref_state`, `kyc_users`) unless `ALLOW_FOREIGN_OVERWRITE` is set to
`True` in that cell, so it cannot silently overwrite someone else's work in the shared `study`
database. Its own three tables *are* dropped and rebuilt on every run — that's the idempotency.

## Run history

<!-- RUN-HISTORY: appended automatically by notebooks/01_kyc_load_and_setup.ipynb -->

### Run — 2026-09-06 23:43:26 IST

- **Server:** PostgreSQL 18.1 (Debian 18.1-1.pgdg13+2) on aarch64-unknown-linux-gnu
- **Target:** `postgres@localhost:5432/study`, schema `kyc`
- **Source file:** `KYC_Synthetic_Dataset.csv` (273,899,427 bytes)
- **Records parsed from CSV:** 2,515,262
- **Rows in `kyc.kyc_raw`:** 2,515,262
- **Rows in `kyc.kyc_users`:** 2,515,262
- **Validation:** ALL CHECKS PASSED

| Step | Detail | Seconds |
|---|---|---|
| Profiled CSV | 2,515,262 records, 17 columns | 9.10 |
| Created roles kyc_owner / kyc_rw / kyc_ro |  | 0.02 |
| Created schema kyc |  | 0.01 |
| Created kyc.kyc_raw (landing table) |  | 0.01 |
| Created and populated kyc.ref_state |  | 0.01 |
| Loaded CSV into kyc.kyc_raw | 2,515,262 rows | 2.06 |
| Built kyc.kyc_users (typed analytical table) |  | 3.39 |
| Added primary key and CHECK constraints to kyc.kyc_users |  | 1.99 |
| Created indexes on kyc.kyc_users |  | 3.40 |
| ANALYZE kyc.kyc_users |  | 0.26 |
| Granted privileges on schema kyc to kyc_ro / kyc_rw / kyc_owner |  | 0.01 |
| Granted kyc_owner/kyc_rw/kyc_ro to postgres |  | 0.01 |

### Run — 2026-09-06 23:47:30 IST

- **Server:** PostgreSQL 18.1 (Debian 18.1-1.pgdg13+2) on aarch64-unknown-linux-gnu
- **Target:** `postgres@localhost:5432/study`, schema `kyc`
- **Source file:** `KYC_Synthetic_Dataset.csv` (273,899,427 bytes)
- **Records parsed from CSV:** 2,515,262
- **Rows in `kyc.kyc_raw`:** 2,515,262
- **Rows in `kyc.kyc_users`:** 2,515,262
- **Validation:** ALL CHECKS PASSED

| Step | Detail | Seconds |
|---|---|---|
| Profiled CSV | 2,515,262 records, 17 columns | 9.67 |
| Created roles kyc_owner / kyc_rw / kyc_ro |  | 0.02 |
| Created schema kyc |  | 0.00 |
| Created kyc.kyc_raw (landing table) |  | 0.04 |
| Created and populated kyc.ref_state |  | 0.01 |
| Loaded CSV into kyc.kyc_raw | 2,515,262 rows | 1.96 |
| Built kyc.kyc_users (typed analytical table) |  | 3.20 |
| Added primary key, NOT NULLs and CHECK constraints to kyc.kyc_users |  | 2.03 |
| Created indexes on kyc.kyc_users |  | 3.62 |
| ANALYZE kyc.kyc_users |  | 0.28 |
| Granted privileges on schema kyc to kyc_ro / kyc_rw / kyc_owner |  | 0.01 |
| Granted kyc_owner/kyc_rw/kyc_ro to postgres |  | 0.01 |

### Run — 2026-09-06 23:49:51 IST

- **Server:** PostgreSQL 18.1 (Debian 18.1-1.pgdg13+2) on aarch64-unknown-linux-gnu
- **Target:** `postgres@localhost:5432/study`, schema `kyc`
- **Source file:** `KYC_Synthetic_Dataset.csv` (273,899,427 bytes)
- **Records parsed from CSV:** 2,515,262
- **Rows in `kyc.kyc_raw`:** 2,515,262
- **Rows in `kyc.kyc_users`:** 2,515,262
- **Validation:** ALL CHECKS PASSED

| Step | Detail | Seconds |
|---|---|---|
| Profiled CSV | 2,515,262 records, 17 columns | 9.55 |
| Created roles kyc_owner / kyc_rw / kyc_ro |  | 0.01 |
| Created schema kyc |  | 0.01 |
| Created kyc.kyc_raw (landing table) |  | 0.03 |
| Created and populated kyc.ref_state |  | 0.01 |
| Loaded CSV into kyc.kyc_raw | 2,515,262 rows | 2.01 |
| Built kyc.kyc_users (typed analytical table) |  | 3.57 |
| Added primary key, NOT NULLs and CHECK constraints to kyc.kyc_users |  | 2.04 |
| Created indexes on kyc.kyc_users |  | 3.68 |
| ANALYZE kyc.kyc_users |  | 0.26 |
| Granted privileges on schema kyc to kyc_ro / kyc_rw / kyc_owner |  | 0.01 |
| Granted kyc_owner/kyc_rw/kyc_ro to postgres |  | 0.00 |

### Task 1 analysis run — 2026-09-07 00:05:13 IST

- **Notebook:** `notebooks/02_task1_funnel_analysis.ipynb` (read-only; no DDL, no writes to `kyc`)
- **Headline:** 7.93% not verified (199,515 of 2,515,262) vs a 5% bar — 73,752 users over budget
- **Largest single cause:** 101,162 users failed Idology and had no second check run (50.7% of all non-verifications)
- **Observed recovery rate of comparable routed users:** 48.09%
- **Modelled impact of fixing routing alone:** ~48,649 users recovered, rate 7.93% -> ~6.0%

| Non-verification bucket | Users |
|---|---:|
| A. Avoidable — no check ever ran | 843 |
| B. Avoidable — failed 1st check, never routed on | 101,325 |
| C. Partly avoidable — 2+ checks failed, no manual review | 48,598 |
| D. Genuine — assessed incl. manual review, still failed | 48,655 |

**Waterfall discrepancies found vs the documented design:** undocumented second entry point at
ProviderA_LexisNexis (3.7% of traffic, ~100% pass); non-blocking LexisNexis checks after an
Idology PASS; 35% of Idology failures routed nowhere; the "older accounts to Persona-SSN" rule
not reproducible from the data; manual review under-triggered.

### Task 1 analysis run — 2026-09-07 00:06:31 IST

- **Notebook:** `notebooks/02_task1_funnel_analysis.ipynb` (read-only; no DDL, no writes to `kyc`)
- **Headline:** 7.93% not verified (199,515 of 2,515,262) vs a 5% bar — 73,752 users over budget
- **Largest single cause:** 101,162 users failed Idology and had no second check run (50.7% of all non-verifications)
- **Observed recovery rate of comparable routed users:** 48.09%
- **Modelled impact of fixing routing alone:** ~48,649 users recovered, rate 7.93% -> ~6.0%

| Non-verification bucket | Users |
|---|---:|
| A. Avoidable — no check ever ran | 843 |
| B. Avoidable — failed 1st check, never routed on | 101,325 |
| C. Partly avoidable — 2+ checks failed, no manual review | 48,598 |
| D. Genuine — assessed incl. manual review, still failed | 48,655 |

**Waterfall discrepancies found vs the documented design:** undocumented second entry point at
ProviderA_LexisNexis (3.7% of traffic, ~100% pass); non-blocking LexisNexis checks after an
Idology PASS; 35% of Idology failures routed nowhere; the "older accounts to Persona-SSN" rule
not reproducible from the data; manual review under-triggered.

### Run — 2026-09-07 00:49:32 IST

- **Server:** PostgreSQL 18.1 (Debian 18.1-1.pgdg13+2) on aarch64-unknown-linux-gnu
- **Target:** `postgres@localhost:5432/study`, schema `kyc`
- **Source file:** `KYC_Synthetic_Dataset.csv` (273,899,427 bytes)
- **Records parsed from CSV:** 2,515,262
- **Rows in `kyc.kyc_raw`:** 2,515,262
- **Rows in `kyc.kyc_users`:** 2,515,262
- **Validation:** ALL CHECKS PASSED

| Step | Detail | Seconds |
|---|---|---|
| Profiled CSV | 2,515,262 records, 17 columns | 9.08 |
| Created roles kyc_owner / kyc_rw / kyc_ro |  | 0.01 |
| Created schema kyc |  | 0.00 |
| Created kyc.kyc_raw (landing table) |  | 0.04 |
| Created and populated kyc.ref_state |  | 0.01 |
| Loaded CSV into kyc.kyc_raw | 2,515,262 rows | 1.99 |
| Built kyc.kyc_users (typed analytical table) |  | 3.11 |
| Added primary key, NOT NULLs and CHECK constraints to kyc.kyc_users |  | 2.29 |
| Created indexes on kyc.kyc_users |  | 3.62 |
| ANALYZE kyc.kyc_users |  | 0.25 |
| Granted privileges on schema kyc to kyc_ro / kyc_rw / kyc_owner |  | 0.01 |
| Granted kyc_owner/kyc_rw/kyc_ro to postgres |  | 0.00 |

### Task 1 analysis run — 2026-09-07 00:49:53 IST

- **Notebook:** `notebooks/02_task1_funnel_analysis.ipynb` (read-only; no DDL, no writes to `kyc`)
- **Headline:** 7.93% not verified (199,515 of 2,515,262) vs a 5% bar — 73,752 users over budget
- **Largest single cause:** 101,162 users failed Idology and had no second check run (50.7% of all non-verifications)
- **Observed recovery rate of comparable routed users:** 48.09%
- **Modelled impact of fixing routing alone:** ~48,649 users recovered, rate 7.93% -> ~6.0%

| Non-verification bucket | Users |
|---|---:|
| A. Avoidable — no check ever ran | 843 |
| B. Avoidable — failed 1st check, never routed on | 101,325 |
| C. Partly avoidable — 2+ checks failed, no manual review | 48,598 |
| D. Genuine — assessed incl. manual review, still failed | 48,655 |

**Waterfall discrepancies found vs the documented design:** undocumented second entry point at
ProviderA_LexisNexis (3.7% of traffic, ~100% pass); non-blocking LexisNexis checks after an
Idology PASS; 35% of Idology failures routed nowhere; the "older accounts to Persona-SSN" rule
not reproducible from the data; manual review under-triggered.

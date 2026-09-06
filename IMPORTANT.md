# IMPORTANT — key points, numbers and steps

The short version of everything. `AUDIT_LOG.md` has the full trail; this file is what you should be
able to recall and defend without looking anything up. **New to this project entirely?**
[README.md](README.md) is one paragraph plus setup — start there instead.

Every number here is produced by [notebooks/02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb)
against `kyc.kyc_users`. Nothing is hardcoded or estimated except where marked **[estimate]**. If a
term below is unfamiliar (Idology, waterfall, SSN path...), §3's table names the role of each check,
or see the glossary in notebook 01's opening cell.

---

## 1. The one-sentence answer

**7.93% of users are not verified, against a 5% bar — and just over half of those failures are users
who failed the first check and were never given a second one.**

---

## 2. Numbers to know cold

### The headline
| | |
|---|---:|
| Total enrolled users | 2,515,262 |
| Verified | 2,315,747 |
| **Not verified** | **199,515** |
| **Non-verification rate** | **7.93%** |
| Budget at the 5% bar | 125,763 |
| **Users over budget** | **73,752** |

Rate is **flat across all 41 months** (2023-01 to 2026-05). Not a regression — steady-state design behaviour.

### The main defect
| | |
|---|---:|
| Users who failed Idology | 288,134 |
| ...of whom **stranded** (no second check ran) | **101,162 (35.1%)** |
| Stranded users who got verified | 12 (**0.01%**) |
| ...of whom routed onward | 186,866 |
| Routed users who got verified | 89,860 (**48.09%**) |

**The like-for-like comparison — the strongest single slide you have:**
everyone in both rows failed Idology. The only difference is whether the system routed them onward.

| Cohort | Users | Recovered | Rate |
|---|---:|---:|---:|
| Routed onward after failing Idology | 186,866 | 89,860 | **48.09%** |
| Stranded after failing Idology | 101,162 | 12 | **0.01%** |

### The prize **[estimate]**
101,162 × 48.09% ≈ **48,649 users recoverable** → non-verification **7.93% → ~6.0%**.
About two-thirds of the gap to 5%, with **no control weakened**.

### Non-verifications classified (199,421, excl. test accounts)
| Bucket | Users | % |
|---|---:|---:|
| A. Avoidable — no check ever ran | 843 | 0.4% |
| **B. Avoidable — failed 1st check, never routed on** | **101,325** | **50.8%** |
| C. Partly avoidable — 2+ checks failed, never saw manual review | 48,598 | 24.4% |
| D. Genuine — assessed incl. manual review, still failed | 48,655 | 24.4% |

**~51% avoidable, ~24% genuine.** That is the answer to "separate genuine rejections from avoidable losses".

---

## 3. Waterfall: documented vs what the data shows

| Documented | Observed | Verdict |
|---|---|---|
| Idology is the primary check | 94,184 users (3.74%) never see it — they enter at ProviderA_LexisNexis, which passes ~100% | **Undocumented 2nd entry point** |
| Pass Idology ⇒ verified, exit | 130,713 passed Idology and had LexisNexis run anyway; 57,822 FAILED it and were still verified (~99.6%) | **Non-blocking extra check** |
| Fail ⇒ route by SSN / non-SSN reason | **35% of failures routed nowhere** | **The main defect** |
| SSN path: LexisNexis, or legacy Persona-SSN for "older accounts" | No age or vintage signal at all | **Rule not reproducible** |
| Two LexisNexis routes are different integrations | Confirmed — opposite roles | **Confirmed** |
| Manual review catches those who fail everything | 148,713 eligible users never reached it (69.8%) | **Under-triggered** |

### The two LexisNexis routes — know this one, it's explicitly asked
| | ProviderA | ProviderB |
|---|---:|---:|
| Users | 149,364 | 15,998 |
| Never saw Idology | 93,319 | 1 |
| After an Idology FAIL | 5,522 | 11,677 |

**ProviderA is acting as an alternative PRIMARY route. ProviderB is a SECONDARY, SSN-path check.**
Same column, opposite roles — grouping on `lexis_nexis_result` alone merges them and misleads.

---

## 4. Traps — the things that would make the analysis wrong

**Trap 1 — the `kyc_source` denominator (this is the big one).**
`kyc_source` is null for 197,314 users (7.84%), and 99.99% of them are unverified. It looks like
missing data. Drop those rows and you get **0.09%** instead of 7.93%.
**It is not missing data.** `kyc_source` names the provider that *cleared* a user, so it is null
exactly when nobody did. **Proof: zero of those 197,314 rows has a `PASS` on any provider.**
Excluding them excludes ~99% of the rejections *by construction*.

**Trap 2 — `WHERE NOT is_test_user` silently dropping 197k rows.**
`(kyc_source = 'Test_user')` evaluates to `NULL`, not `false`, wherever `kyc_source` is null — and
`WHERE NULL` excludes the row. Must be `coalesce(kyc_source = 'Test_user', false)`.
This was a live bug in the load; it is why every boolean flag is now `NOT NULL`.
**General rule: never build a boolean flag off a nullable column without `coalesce`.**

**Trap 3 — "more checks = lower verification rate" (95% → 76% → 44%).**
True in the raw table, and it does *not* mean extra checks hurt. It is selection: users only go
deeper because they already failed something. Always compare *within* "failed the first check".

**Trap 4 — `wc -l` gives 2,515,291; the real count is 2,515,262.**
Eight `reviewer_comment` values contain embedded newlines inside quoted fields.

**Trap 5 — `state` mixes `OH` (76,705) and `Ohio` (26,219).**
51 full names alongside USPS codes. Naive `GROUP BY state` splits every affected state in two.
Doesn't affect the headline, would wreck any geographic cut.

**Trap 6 — reviewer comments cover only ~3% of users**, skewed toward manual review. Describes the
*reviewed* population, not all failures. The stranded users have **zero** comments.

---

## 5. The three problems to lead with

**1. The waterfall stops after one check for a third of failures** — 101,162 users, ~51% of all
non-verifications, 0.01% verified vs 48% for comparable routed users. ~48,649 recoverable.
*Why first: it is a routing bug, not a risk decision. Costs provider calls, not control strength.
Uniform across every partner and year, so it is one systematic gap, not many small ones.*

**2. Manual review is under-triggered** — 48,598 users failed 2+ automated checks and never reached
a human. Review clears ~32% of what reaches it. *Bounded by analyst capacity → needs a triage rule,
not "send everything".*

**3. Persona IDV is barely deployed** — runs on 0.87% of Idology failures, and those users verify at
**86.3%** vs 30.7% for those without it. Directly targets the name/DOB/address failures.
*But it is the highest-friction, highest-cost check → belongs last in the waterfall.*

**Deliberately NOT on the list: SSN mismatches.** Large category (12,788 comments) but verifies at
~0.1% even after human review. That is what a *genuine* rejection looks like. Chasing it means
weakening a control that is working.

---

## 6. Steps taken (the method, in order)

1. **Profiled the CSV before writing any DDL** — column types chosen from what the file contains,
   not what the brief claims. Produced an independent record count to reconcile the load against.
2. **Loaded in two layers** — `kyc_raw` (verbatim, all `TEXT`, no constraints, so a bad value becomes
   a finding rather than an aborted load) → `kyc_users` (typed, cleaned, constrained). Every
   transformation happens between the two and is reviewable.
3. **Streamed `COPY ... FROM STDIN`** client-side — works identically whether Postgres is in Docker
   (can't see the host filesystem at all) or natively installed (the server process often runs as a
   different OS user with no access to *your* files either — this project hit that exact wall on its
   own native macOS Postgres install). Streaming sidesteps the question on either setup.
4. **11 validation gates**, all asserted: row counts reconcile against the independent parse, no rows
   dropped in cleaning, no NULL booleans, verified count survives the boolean cast, null counts match
   the pre-load profile.
5. **`CHECK` constraints added `NOT VALID` then `VALIDATE`d** — an assertion across 2.5M rows that
   every provider value is in the domain the brief claims.
6. **Reconstructed the waterfall from column co-occurrence** — a non-null provider column means that
   check ran, so which columns are populated together *is* the routing evidence.
7. **Tested the documented rules rather than assuming them** — which is how the second entry point,
   the non-blocking checks, and the unreproducible "older accounts" rule were found.
8. **Sized the opportunity off an observed comparison group**, not an assumption — users who failed
   the same check and *were* routed.

---

## 7. Be ready to defend these judgement calls

| Call | Defence |
|---|---|
| Reporting 7.93%, not 0.09% | The 0.09% denominator is circular — see Trap 1. Zero PASS values proves it. |
| Calling bucket B "avoidable" | The system never finished asking the question. Comparable users routed onward recover at 48%. |
| Calling bucket D "genuine" | Assessed by 2+ providers *and* a human, still declined. That is the irreducible floor. |
| The 48,649 estimate | It is an **estimate** from a like-for-like comparison group. Stranding is uniform across partners and years, so the cohorts should be comparable — but the honest confirmation is to route a sample and measure. Do not present it as guaranteed. |
| Flagging 100% pass on ProviderA | A primary check that filters nothing is either pre-screened upstream or under-controlled. The data cannot distinguish the two — that is a question for engineering, and it is a *risk* question, not a conversion one. |
| Not fixing SSN mismatches | They verify at ~0.1% after review. Working control, not a leak. |

## 8. Honest limits of the analysis

- No provider **cost or latency** data exists in this dataset — Task 2's cost/friction trade-offs
  cannot be made rigorous without it.
- The **"older accounts ⇒ Persona-SSN"** routing rule cannot be reproduced; the driving field is not
  in the extract.
- Whether the **3.7% Idology bypass** is a deliberate holdout, an A/B test, or a fallback is not
  determinable from data alone.
- The recovery estimate is a **comparison-group projection**, not an experiment.
- `reviewer_comment` is free text and was classified with pattern matching, so the reason taxonomy is
  approximate at the margins.

---

## 9. Where things are

| File | What |
|---|---|
| [README.md](README.md) | Start here if you're new — summary, file map, setup |
| [notebooks/01_kyc_load_and_setup.ipynb](notebooks/01_kyc_load_and_setup.ipynb) | Load, clean, constrain, grant, validate |
| [notebooks/02_task1_funnel_analysis.ipynb](notebooks/02_task1_funnel_analysis.ipynb) | Task 1 analysis, in reading order |
| [AUDIT_LOG.md](AUDIT_LOG.md) | Full trail: env, decisions, defects, caveats, run history |
| [Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018) | Published report — the same story as charts, no code |
| `IMPORTANT.md` | This file |

**DB:** Postgres, database `study`, schema `kyc` — works against **Docker or a native install**, see
[README.md's Setup section](README.md#setup--works-with-docker-or-a-native-postgres-install).
Tables: `kyc_raw` (verbatim), `kyc_users` (**analyse from here**), `ref_state`.
Roles: `kyc_ro` / `kyc_rw` / `kyc_owner`. Credentials in `.env` (git-ignored, chmod 600) — copy
`.env.example` and fill in your setup (it has a block for each).

```bash
cd /Users/rudransh/d_drive/GITHUB/Brightmoney
# make sure your Postgres server is running (docker start postgres, or however your native install runs)
.venv/bin/jupyter lab
```

**Still to do:** Task 2 (redesigned waterfall) and Task 3 (PRD, ARD, project plan).

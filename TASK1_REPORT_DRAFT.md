# Task 1 report — draft (working doc, not the report)

Building this question by question. Nothing here goes into the published report or
`reports/task1_where_the_funnel_breaks.html` until you sign off on it — this file is just where we
park the answer while it's still moving.

Source for every number below: `notebooks/02_task1_funnel_analysis.ipynb`, Parts 1–4, re-run live
against `kyc.kyc_users` (2,515,155 rows, test accounts excluded via `where not is_test_user`).

---

## Q1. What is the current rejection rate, and why are users not getting verified?

### The rate

**7.93% of users are not verified (199,421 of 2,515,155)** — against the brief's 5% acceptable bar.
That's 2.93 percentage points over, or **73,663 users too many**.

| | |
|---|---|
| Total users (test accounts excluded) | 2,515,155 |
| Verified | 2,315,734 |
| Not verified | 199,421 (7.93%) |
| Budget at 5% | 125,758 |
| Users over budget | 73,663 |

Checked whether this is a recent regression: it isn't. The rate is flat — between the lowest and
highest monthly figures across the full 3.5-year window — so this is steady-state behavior of the
system as designed, not a bad month or a broken release. (notebook Part 1, cell 5)

### Why — the single biggest cause

**Not that users fail checks. It's that 101,162 users failed the primary check (Idology) and then
had no second check run at all** — they were never routed onward into the waterfall at all.
Essentially none of them verified (101,159 of 101,162 — the 3 who did are a data quirk, noted but
not load-bearing). That's **50.7% of every non-verification in the dataset** — call it just over half
the whole problem, from one routing gap.

Evidence this is a routing failure rather than a harder population: users who failed Idology and
*were* routed onward recovered at **48.09%**. Same starting point (failed the first check). The
stranding rate is also flat at ~35% across every partner and every enrollment year (notebook Part
2.3, cell 11) — that's consistent with the stranded group not being a specially hard segment, but it
is not a direct test of verification difficulty (no secondary check ever ran on them to measure that
against), so it's supporting evidence, not proof. Applying that same recovery
rate to the stranded population projects to **~48,649 recoverable users**, which would take the rate
from 7.93% to about **6.0%** — roughly two-thirds of the gap to the 5% bar, from fixing routing alone,
with no control loosened. (notebook Part 4, cell 17 — explicitly flagged there as an estimate, not a
guarantee: "the honest way to confirm it is to route a sample and measure.")

### The rest of the "why" — classifying every non-verification

Beyond the routing gap, every non-verified user was bucketed by how much of the waterfall actually
ran for them, using the rule: *2+ checks that all failed = genuine rejection; failed once and never
routed on = avoidable loss* (notebook Part 4, cell 16):

| Bucket | Users | % of non-verified | What it means |
|---|---:|---:|---|
| A. No check ever ran | 843 | 0.4% | Never entered the waterfall at all |
| B. Exactly one check ran, then stopped | 101,325 | 50.8% | The routing gap above — see breakdown below, it's not 100% "failed Idology" |
| C. 2+ checks ran, no manual review | 48,598 | 24.4% | Exhausted automated checks, never got the human safety net |
| D. Genuine — assessed incl. manual review, still failed | 48,655 | 24.4% | Properly assessed, correctly declined |

Read together: **75.6% of non-verification (A+B+C) is process failure, not a correct decision** —
either the waterfall never finished running, or it finished without ever reaching the human backstop
the design promises. Only the D bucket, just under a quarter, looks like the system doing its job.

> **Note on how this table was built:** the boundary between buckets uses `checks_run`, and I confirmed
> directly (not assumed) that `checks_run` = (number of provider columns populated) + 1 if manual review
> also ran. Checked by comparing `checks_run` to the actual count of non-null provider columns across
> the whole dataset: they disagree on exactly 74,400 rows, and every one of those 74,400 is a row where
> manual review ran — none unexplained. So "checks_run = 1" reliably means exactly one provider ran and
> manual review did not, for every row, not just the common case.

#### Bucket B in detail — I initially described this as "failed Idology," that's not fully accurate

> **Correction:** a reader flagged that a "went directly to Persona-IDV, Idology never ran, not
> verified" population wasn't showing up anywhere in this draft. It wasn't an omission from a
> table — it was missing from the underlying categorization. Bucket B's label ("failed 1st check")
> assumed the one check that ran was always Idology and always a FAIL. Checked directly: it isn't
> either, for a small fraction of the bucket.

Full MECE split of bucket B (101,325 users, exactly one check ran, no manual review), by **which**
check ran and **what it said**:

| Sole check that ran | Result | Users | % of bucket B |
|---|---|---:|---:|
| Idology | FAIL | 101,159 | 99.836% |
| Idology | **PASS** | 146 | 0.144% |
| Persona-IDV | **PASS** | 18 | 0.018% |
| LexisNexis | FAIL | 2 | 0.002% |

Four genuinely different populations, not one:

1. **101,159 — the core finding, unchanged.** Failed Idology, nothing else ran. This is what "the
   routing gap" refers to everywhere else in this draft.
2. **146 — Idology PASSed, nothing else ran, user still not verified.** This contradicts the
   documented design (Idology PASS ⇒ verified, exit) and doesn't fit "never routed on" either — there
   was nothing to route to, since Idology said PASS. This is a distinct anomaly, not a routing gap.
3. **18 — the population flagged above.** Never went through Idology at all (`idology_result` is
   null); Persona-IDV ran directly, PASSed, and the user is still not verified. This is a *third*
   undocumented entry point, on top of the LexisNexis one already documented below — and same as #2,
   the check said PASS, so this isn't "never routed on," it's "routed, passed, not verified anyway."
4. **2 — entered via LexisNexis (Idology never ran), FAILed, stranded.** Same shape as the core
   finding (#1), just via the undocumented second entry point instead of Idology.

Sub-populations #2 and #3 (164 users total, 0.16% of bucket B) are a **PASS that didn't convert to
verified** — the same anomaly shape already found in bucket C (1,131 users). See the unified census
below for the full picture of that pattern across the whole non-verified population, not just this
bucket.

#### The "PASS, but still not verified" pattern — full census across all of non-verification

Once found in two places, I checked everywhere rather than assume it's confined to buckets B and C:

| Bucket | Users with ≥1 provider PASS, still not verified | % of that bucket |
|---|---:|---:|
| A. No check ever ran | 0 | 0% (can't happen — no check ran, so no PASS is possible) |
| B. Exactly one check ran | 164 | 0.16% |
| C. 2+ checks ran, no manual review | 1,131 | 2.33% |
| D. Assessed incl. manual review | 798 | 1.64% |
| **Total** | **2,093** | **1.05% of all 199,421 non-verified users** |

Bucket D's 798 is a different kind of case from B and C's: manual review *did* run for those users, so
a human seeing an automated PASS and still declining is the system's intended override, not obviously
a defect — a compliance or sanctions reviewer overruling a provider PASS is expected behavior, not an
anomaly, though I haven't pulled reviewer comments for this specific slice to confirm that's actually
what's happening in each case (open, not yet checked). B and C's 164 + 1,131 = 1,295 users are the
part of this pattern with **no human involved and no documented reason** — those are the ones worth
treating as a genuine, if small, defect: 0.65% of all non-verification.

#### Full population census — every combination that occurs in the data, MECE, sums to the whole dataset

For completeness, and so nothing else is sitting uncounted in an "other" bucket anywhere in this
draft: every distinct combination of (which checks ran) × (verified or not) in the full 2,515,155-user
population, test accounts excluded. 45 combinations occur; none were pre-selected or filtered out.

| Idology | Lexis | ACRO | P-IDV | P-SSN | Manual | Verified | Users |
|---|---|---|---|---|---|---|---:|
| ran | – | – | – | – | – | **yes** | 2,001,263 |
| ran | ran | – | – | – | – | **yes** | 137,723 |
| ran | – | – | – | – | – | no | 101,305 |
| – | ran | – | – | – | – | **yes** | 93,320 |
| ran | – | ran | – | – | – | **yes** | 42,280 |
| ran | – | ran | – | – | ran | no | 27,865 |
| ran | – | ran | – | – | – | no | 24,960 |
| ran | ran | – | – | – | – | no | 22,038 |
| ran | – | – | – | – | ran | no | 14,591 |
| ran | – | ran | – | – | ran | **yes** | 10,292 |
| ran | – | – | – | – | ran | **yes** | 10,202 |
| ran | ran | – | – | ran | – | **yes** | 8,653 |
| ran | ran | – | – | – | ran | no | 3,329 |
| ran | ran | – | – | – | ran | **yes** | 3,106 |
| ran | ran | ran | – | – | – | **yes** | 3,022 |
| ran | ran | ran | – | – | ran | no | 2,600 |
| ran | – | – | – | ran | – | **yes** | 1,857 |
| ran | – | – | ran | – | – | **yes** | 1,803 |
| ran | ran | ran | – | – | ran | **yes** | 1,716 |
| ran | ran | ran | – | – | – | no | 1,370 |
| – | – | – | – | – | – | no | 843 |
| ran | – | – | ran | – | ran | **yes** | 351 |
| ran | – | – | ran | – | ran | no | 228 |
| ran | – | – | ran | – | – | no | 112 |
| ran | – | – | – | ran | – | no | 111 |
| ran | ran | – | – | ran | ran | **yes** | 38 |
| ran | – | – | – | ran | ran | no | 34 |
| ran | ran | – | ran | – | ran | **yes** | 26 |
| ran | ran | – | ran | – | – | **yes** | 22 |
| ran | – | ran | ran | – | – | **yes** | 21 |
| ran | ran | ran | – | ran | – | **yes** | 19 |
| – | – | – | ran | – | – | no | **18** |
| ran | – | – | – | ran | ran | **yes** | 7 |
| ran | – | ran | – | ran | – | **yes** | 5 |
| ran | – | ran | ran | – | ran | no | 5 |
| ran | ran | – | – | ran | – | no | 4 |
| ran | – | ran | ran | – | ran | **yes** | 4 |
| ran | – | ran | – | ran | ran | no | 3 |
| ran | ran | – | ran | – | – | no | 2 |
| – | ran | – | – | – | – | no | 2 |
| ran | – | ran | ran | – | – | no | 1 |
| ran | – | ran | – | ran | ran | **yes** | 1 |
| ran | ran | ran | – | ran | ran | **yes** | 1 |
| ran | ran | ran | ran | – | – | **yes** | 1 |
| ran | ran | ran | ran | – | ran | **yes** | 1 |

**45 rows, sums to exactly 2,515,155** (verified by direct sum, not estimated). The row in **bold** is
the population originally asked about. Everything above the "0.4%-or-smaller" tail is already covered
by the buckets and flows described elsewhere in this draft; the tiny rows (down to single users) are
included here so the analysis can be shown to be exhaustive, even though several of them are too small
to change any conclusion — flagging that per your instruction, rather than quietly rounding them away.

#### Bucket C in detail — which flows, and what failed

> **Correction from the first pass of this draft:** the table originally here labeled every flow
> "both FAIL" based only on which columns were non-null, without checking the actual result values.
> That was wrong — re-checked directly below, split by actual PASS/FAIL values, not just presence.

Split by whether every provider that ran actually said FAIL, vs. at least one said PASS despite the
user still showing `is_verified = false`:

| | Users | % of bucket C |
|---|---:|---:|
| Every provider that ran said FAIL | 47,467 | 97.67% |
| At least one provider PASSed, user still not verified | 1,131 | 2.33% |

**The 97.67% "clean" majority** — everything ran, everything genuinely failed, nobody escalated to
manual review — breaks down as:

| Flow (all results FAIL) | Users | % of bucket C |
|---|---:|---:|
| Non-SSN path — Idology FAIL, ACRO FAIL | 24,921 | 51.28% |
| SSN path — Idology FAIL, LexisNexis FAIL | 21,447 | 44.13% |
| Mixed — Idology FAIL, LexisNexis FAIL, ACRO FAIL | 1,099 | 2.26% |

That's the finding as originally stated, just with the numbers corrected: the waterfall *did* run the
documented second check for the great majority of this bucket, it genuinely failed, and step 3
(manual review) never fired even though the design says it's the catch-all for exactly this case.

**The 2.33% that doesn't fit that story** — 1,131 users where at least one provider actually said
PASS, yet the user is still marked not verified and never reached manual review:

| Exact result combination | Users |
|---|---:|
| Idology FAIL, LexisNexis PASS | 493 |
| Idology FAIL, LexisNexis PASS, ACRO FAIL | 180 |
| Idology FAIL, Persona-SSN PASS | 111 |
| Idology FAIL, Persona-IDV PASS | 107 |
| Idology PASS, LexisNexis FAIL | 98 |
| Idology PASS, LexisNexis FAIL, ACRO FAIL | 91 |
| Idology FAIL, ACRO PASS | 21 |
| Idology PASS, ACRO FAIL | 18 |
| Idology PASS, Persona-IDV PASS | 5 |
| Idology FAIL, LexisNexis FAIL, Persona-SSN PASS | 3 |
| Idology FAIL, LexisNexis FAIL, Persona-IDV PASS | 2 |
| Idology FAIL, LexisNexis PASS, Persona-SSN PASS | 1 |
| Idology FAIL, ACRO FAIL, Persona-IDV PASS | 1 |

This is a genuinely different problem from the rest of bucket C, and from the rest of the report: it's
not "the waterfall stopped too early," it's **a provider said PASS and the user was still declined
with nobody reviewing it.** To know whether that's rare or common, I queried the verification rate for
each exact provider-result combination across the *whole dataset* (not just bucket C), rather than
reuse a stat from a different combination:

| Population (whole dataset, not just bucket C) | Users | % verified | Bucket C's share of the non-verified tail |
|---|---:|---:|---:|
| Idology PASS, LexisNexis FAIL | 57,822 | 99.64% | 189 of the 210 not verified |
| Idology PASS, ACRO FAIL | 783 | 83.52% | 109 of the 129 not verified |
| Idology FAIL, LexisNexis PASS | 17,197 | 94.66% | 674 of the 919 not verified |
| Idology FAIL, ACRO PASS | 51,050 | 99.44% | 21 of the 284 not verified |
| Idology FAIL, Persona-SSN PASS | 10,730 | 98.58% | 115 of the 152 not verified |
| Idology FAIL, Persona-IDV PASS | 2,507 | 86.32% | 110 of the 343 not verified |

(Each row's "bucket C share" counts every row from this section's earlier result-combination table that
matches *at least* this 2-provider condition — e.g. "Idology PASS, LexisNexis FAIL" includes both the
98 users where only those two ran and the 91 where ACRO also ran and failed. The per-condition
row-sums above don't add cleanly to bucket C's 1,131 total because a user can appear in more than one
row here — e.g. someone with Idology FAIL + LexisNexis PASS + Persona-SSN PASS is counted in two rows.)

Two corrections to what I first wrote here:

- I'd claimed a PASS "not converting to verified is the exception, not the rule," citing a Part 2.3
  stat for a different check combination. Checked directly instead: that holds for ACRO and
  Persona-SSN passes (>98.5% verify overall), but **Persona-IDV passing after an Idology FAIL only
  converts to verified 86.32% of the time, and an Idology PASS followed by an ACRO FAIL only converts
  83.52% of the time** — both are a meaningfully weaker signal than the >99% seen for the
  LexisNexis-involving combinations, not just noise.
- I'd also claimed, citing Part 2.2, that an Idology PASS with a later FAIL "verifies ~99.6% of the
  time elsewhere in the dataset" and applied that to all 116 Idology-PASS users in this anomaly.
  That figure is only true for the LexisNexis-FAIL half (99.64%, matches Part 2.2 exactly). The
  ACRO-FAIL half is a different, much weaker 83.52% — Part 2.2 never covered ACRO, so extending its
  number to this group was an unverified assumption, not a checked fact.

Three more things worth calling out about bucket C as a whole:

1. **Uniform across partners, not concentrated in one.** As a share of each partner's own population,
   bucket C sits at 1.78%–1.94% everywhere (Bank A 1.94%, Bank B 1.89%, Bank C 1.79%, no-partner
   1.78%) — the same "systemic, not targeted" signature as the routing gap in bucket B and the Idology
   bypass in Part 2.1, not a single misconfigured partner integration.
2. **Zero reviewer comments in this entire bucket** (checked directly) — consistent with "never
   reached manual review": nothing ever looked at any of these 48,598 people, same as the stranded
   population in bucket B.
3. **Open question, not yet answered:** whether the 1,131-user PASS anomaly is a data-extract artifact
   (e.g., a decision made on a later re-run of a check that overwrote an earlier PASS) or a genuine
   decisioning-logic gap. Haven't chased this further in this draft — flagging it rather than guessing,
   since it changes the story from "process was too slow" to "the pass/fail wiring itself has a hole"
   if it turns out to be the latter.

Two secondary, structural causes behind why the waterfall doesn't finish running for so many people:

- **The manual-review safety net has a coverage hole, not a quality problem.** Of users who failed
  every automated check that ran on them, most never reach manual review at all; when it *is* reached,
  it clears roughly a third of what lands on it. The net works — it's just not there for most of the
  people the design says it should catch. (notebook Part 2.6)
- **Undocumented entry points that bypass Idology — there are three of them, not one.** 94,183 users
  (3.7%) have a null `idology_result` — Idology never ran for them at all. Broken out by the actual
  result column populated (not `kyc_source` — see the audit below for why that distinction matters):

  | What actually ran (by result column) | Users | Verified | % verified |
  |---|---:|---:|---:|
  | `lexis_nexis_result` populated | 93,322 | 93,320 | 99.998% |
  | Nothing — every result column null | 843 | 0 | 0% |
  | `persona_idv_result` populated (nothing else) | 18 | 0 | 0% |

  The LexisNexis route is materially not "~100%" — it fails to verify **2 of 93,322** (99.998%, not
  100%; both are stranded the same way the Idology-FAIL population is). A check that clears
  essentially everything it sees still isn't filtering meaningfully; either these users are
  pre-screened elsewhere the data can't see, or the route is weaker than the documented primary.
  (notebook Part 2.1–2.2, cross-checked against result columns directly — see audit below)

### Auditing `kyc_source` against the actual result columns

> **Why this section exists:** a reader pointed out that a claim in this draft ("LexisNexis passes
> ~100% of what it sees") didn't match a case they could see directly in the data — 2 records where
> `lexis_nexis_result = FAIL`. That claim traced back to `kyc_source`, a separate column recording
> *who is credited with clearing the user*, not the same thing as *which result columns say PASS*.
> Rather than patch the one number, I cross-checked every row in the dataset where the two could
> disagree, in both directions. From here on, every claim in this document about a check passing or
> failing names the specific result column (`idology_result`, `lexis_nexis_result`, `acro_result`,
> `persona_idv_result`, `persona_ssn_result`) — never `kyc_source` alone, and never "a check" or "one
> check" without naming which one.

**Direction 1 — does `kyc_source` ever name a provider whose own result column is NOT `PASS`?**
Checked every row (excluding `kyc_source = MANUAL_REVIEW`, which isn't a claim about a specific
provider's column). Two rows, out of 2,515,155:

| user_id | kyc_source | idology | lexis_nexis | acro | persona_idv | persona_ssn | manual_review | is_verified |
|---|---|---|---|---|---|---|---|---|
| A33539E8024957AA | ProviderA_Lexis_Nexis | FAIL | FAIL | – | – | – | FAIL | **True** |
| 5826A2080EC89ED8 | ProviderA_Lexis_Nexis | FAIL | FAIL | – | – | – | FAIL | False |

Both: `kyc_source` names ProviderA_Lexis_Nexis as the clearing provider, but **every single result
column that ran for these two users — including manual review — says FAIL.** No PASS exists anywhere
in either row. One of the two is nonetheless marked `is_verified = True`. This is a genuine data
contradiction, not an artifact of multi-check overlap: 2 users, vanishingly small against 2.5M, but a
real anomaly, not explained by anything else found so far. Flagged, not resolved.

**Chasing direction 1 further — is `is_verified = True` with zero PASS anywhere limited to those 2
rows?** No. Widened the check to the whole dataset: every user marked verified where *none* of the 5
provider columns, and manual review either, ever recorded a PASS.

| user_id | kyc_source | Which columns say FAIL (rest null) | manual_review | checks_run |
|---|---|---|---|---|
| 1C63E968D12F2F90 | (null) | idology, acro | FAIL | 3 |
| 1FFA98FF9E26C0EA | (null) | idology, acro | FAIL | 3 |
| E3182B0A22D6CF24 | (null) | idology, lexis_nexis | FAIL | 3 |
| 0C390B94AFD56645 | (null) | idology, lexis_nexis, acro | FAIL | 4 |
| E85715A842D10A98 | (null) | idology | (didn't run) | 1 |
| 55CC477465BFC676 | (null) | idology, lexis_nexis | (didn't run) | 2 |
| 883344E1461CD71D | (null) | idology, lexis_nexis, acro | FAIL | 4 |
| E9B780C803C3644D | (null) | idology, lexis_nexis | (didn't run) | 2 |
| CA1D9947AD59F07E | (null) | idology | (didn't run) | 1 |
| A33539E8024957AA | ProviderA_Lexis_Nexis | idology, lexis_nexis | FAIL | 3 |
| 44E6FDAE8C3C1F8D | (null) | idology | (didn't run) | 1 |
| A84C71A16C654033 | (null) | idology, acro | (didn't run) | 2 |
| 63FA516955B1A7BF | (null) | idology, lexis_nexis, acro | FAIL | 4 |
| 46D43E70D924671B | (null) | idology, lexis_nexis | FAIL | 3 |
| 8A347FFE8862393C | (null) | idology | FAIL | 2 |
| 67DCE2839C9A3DBA | (null) | idology, lexis_nexis | FAIL | 3 |
| 2D7034A9ADE43DBA | (null) | idology, lexis_nexis | FAIL | 3 |

**17 users, out of 2,515,155 (0.0007%).** Every one of these is marked `is_verified = True` with no
PASS recorded anywhere — not from a provider, not from manual review. 16 have `kyc_source` null (which
the report elsewhere states means "nobody cleared them" — true for these 16 in every column *except*
`is_verified` itself); the 17th is the `A33539E8024957AA` row already found in direction 1. This is
small enough to be inconsequential to every headline number in this report, and I'm not speculating
about the cause (most plausible: a manual override or exception process not captured in any of these
columns) — but it's real, it's exhaustively counted, and it belongs in the record rather than being
invisible inside a 2,315,734-verified total that looks clean from a distance.

**Direction 2 — does any result column say `PASS` while `kyc_source` names someone else (or nobody)?**
85,172 users, all traceable to a documented, expected cause: `kyc_source` records a single "official
clearing provider" — the one whose PASS the workflow acted on — even when other checks also ran and
also independently returned PASS (this is exactly the "Idology PASS but further checks still ran"
behavior already documented in notebook Part 2.2). Example: 18,046 users have `idology_result = PASS`
**and** `lexis_nexis_result = PASS`, with `kyc_source = IDOLOGY` in every one of them — Idology's PASS
is recorded as the reason, LexisNexis's independent PASS is real but not the credited one. This is not
a data error; it means **`kyc_source` cannot be used as a census of which checks passed** — only the
result columns can, which is why every count in this document is now built from those columns
directly, not from grouping on `kyc_source`.

### Caveats on these specific numbers

- All figures exclude the 107 internal `Test_user` QA fixtures — flagged via `is_test_user`, never
  deleted, filtered out of every query. Including them barely moves anything at this scale, but they
  aren't real applicants.
- The 48,649 "recoverable" figure is a **projection from an observed comparison group's recovery
  rate**, not a measured outcome — stated as an estimate in the notebook, not a guarantee.
- The reviewer-comment reason taxonomy (SSN vs. address vs. DOB vs. sanctions) that explains the
  *character* of genuine rejections covers only ~74k users (comments exist for ~3% of the book,
  skewed toward manual review) — it describes the reviewed population, not the whole book, and
  notably has zero coverage of the stranded population, since nothing ever looked at them.
- `kyc_source` and the per-provider result columns are **not interchangeable** (see the audit above)
  — `kyc_source` names one credited clearing provider per user, not every check that ran or passed.
  Every figure in this document that says a specific check passed or failed is built from that
  check's own result column, never from `kyc_source`.

---

*Next: once this is confirmed, we fold it into the published report. Not touching the HTML/artifact
until you say go.*

# ARD & Monitoring Plan — KYC Verification Waterfall v2

| | |
|---|---|
| **Document** | Analytics Requirements Document (2 of 3: PRD · ARD/Monitoring Plan · Project Plan) |
| **Owner** | Data & Analytics |
| **Primary audience** | Analytics Engineering, Data Science |
| **Consumers** | Product, Backend Engineering, Review Ops, Compliance |
| **Status** | Ready for build |
| **Version / date** | v2.0 — September 2026 |

> **This document is self-contained.** §1 gives the system context an analyst needs; §2 specifies the
> instrumentation everything else reads from; §3 defines every metric with an explicit numerator,
> denominator, baseline and threshold. Baselines are measured over 2,515,155 applications enrolled
> Jan 2023 – May 2026, with 107 internal test accounts excluded.

---

## 1. What we are measuring, and why

**The system.** Every applicant for our US consumer product must clear identity verification (KYC),
which runs as a waterfall: a primary provider (**Idology**), then secondary providers
(**LexisNexis** and **Persona-SSN** on the SSN path; **ACRO** and **Persona IDV** on the non-SSN
path), then **manual review** by a human analyst. The field recording the final outcome is
`overall_kyc_status`.

**The problem v2 fixes.** 7.93% of applicants end up not verified against a 5% bar. The dominant cause
is not that people fail checks — it is that the waterfall stops running:

| Defect | Volume | Verified |
|---|---:|---:|
| **Stranded** — primary check failed, nothing else ever ran | 101,162 (4.02% of book, 50.7% of all non-verifications) | 0.003% |
| **Primary bypassed** — Idology never ran | 94,183 (3.74%) | 99.08% |
| **PASS did not exit** — clean PASS, further checks ran anyway | 131,538 (5.23%) | 99.81% (247 lost) |
| **Safety net missed** — automation exhausted, no human review | 48,598 non-verified | 0% |

Comparable applicants who *were* routed onward after a primary failure recovered at **48.09%**.
75.6% of all non-verification is process failure rather than a correct decision.

**What v2 changes.** Every primary-check failure is classified into one reason
(`SANCTIONS_HIT` / `SSN_MISMATCH` / `IDENTITY_ATTR_MISMATCH` / `NO_DATA`), every reason has a defined
path, a clean PASS terminates the flow unconditionally, and every application ends in exactly one of
three terminal states: `VERIFIED`, `HARD_REJECT`, `IN_MANUAL_REVIEW`. No verification standard or
threshold changes. Full design in the companion **PRD**.

**What this plan must prove.** Three things, in order: (1) the waterfall's structural promises hold —
these are invariants, not KPIs; (2) the recovery is real and the routing is sane; (3) **we did not buy
the rate by weakening a control.**

---

## 2. Instrumentation

### 2.1 The event log

Every metric below reads from one new **append-only** table, `kyc_decision_event` — one row per check
attempt and per routing decision:

| Column | Type | Notes |
|---|---|---|
| `event_id` | uuid | Primary key |
| `application_id` | uuid | Grain for all rate metrics |
| `attempt_seq` | int | Monotonic within an application |
| `tier` | enum | `L1` `L1.5` `L2a` `L2b` `L2` `L3` `L4` |
| `provider` | enum | `IDOLOGY` `LEXISNEXIS` `PERSONA_SSN` `ACRO` `PERSONA_IDV` `MANUAL` `NONE` |
| `reason_class` | enum | `SANCTIONS_HIT` `SSN_MISMATCH` `IDENTITY_ATTR_MISMATCH` `NO_DATA` `NULL` |
| `decision` | enum | `PASS` `FAIL` `ERROR` `TIMEOUT` `SKIPPED` |
| `routed_to` | enum | Next tier, or `TERMINAL` |
| `terminal_state` | enum | `VERIFIED` `HARD_REJECT` `IN_MANUAL_REVIEW` `NULL` |
| `latency_ms` | int | Provider round-trip |
| `cost_cents` | int | Populated from the contracted rate card |
| `rollout_cohort` | enum | `TREATMENT` `CONTROL` `SHADOW` |
| `flag_state` | jsonb | Which feature flags were on for this application |
| `event_ts` | timestamptz | |

Plus a satellite table `kyc_idv_funnel` — one row per IDV `invitation`, `start`, `completion`,
`abandonment` — because an abandoned document-and-selfie flow currently reads as "not verified" and is
indistinguishable from a decline.

**This is not optional plumbing.** The baseline analysis could only reconstruct paths by *inferring*
them from per-provider result columns, and the `kyc_source` field turned out not to be a substitute —
it names one credited clearing provider per applicant, not every check that ran. v2 must not be
auditable only by inference.

### 2.2 Rules that apply to every metric

1. **Grain is the application, not the check.** An applicant is counted once per application.
2. **Exclude internal test accounts** (`is_test_user`) from every numerator and denominator, always.
3. **Cohort every rate.** Treatment vs. control, from the same time window, using the sticky
   application-id hash. Absolute rates without a cohort split are not decision-grade during rollout.
4. **Completed applications only** for outcome metrics — an application still inside its retry window
   is neither verified nor rejected. Maturity window: 72h for automated paths, 14d where L4 is involved.
5. **State the denominator in the metric name.** Every definition below names both sides of the ratio.

---

## 3. Metrics

### Tier 1 — do the design's structural promises hold?

| # | Metric | Definition (numerator ÷ denominator) | Baseline | Target | Alert |
|---|---|---|---:|---:|---|
| **M1** | Non-verification rate | applications not `VERIFIED` ÷ all completed applications | **7.93%** | ≤6.3%; 5.0% stretch | P2: >6.5% sustained 7d |
| **M2** | **Stranded rate** | applications with ≥1 FAIL, no pending check and no terminal state ÷ all applications | **4.02%** (101,162) | **0** | **P1: >0.1% over 1h** |
| **M3** | L1 coverage | applications with an `L1` event ÷ all applications | **96.26%** | 100% | P1: <99.9% over 1h |
| **M3b** | Ex-bypass cohort verification | `VERIFIED` ÷ applications that would have skipped L1 under the old rules | 99.08% | ≥97% | P2: <95% |
| **M4** | PASS-exit integrity | clean-PASS applications with ≥1 downstream event ÷ clean-PASS applications | **5.23%** (131,538) | **0** | P1: >0.05% over 1h |
| **M5** | Manual-review coverage | applications with an `L4` event ÷ applications that exhausted their automated path | **30.2%** (64,414 of 213,048) | 100% | P1: <99% over 24h |
| **M6** | Terminal-state completeness | applications in exactly one terminal state at 72h ÷ all applications | not measurable pre-v2 | 100% | P1: <99.95% |

> **M2, M4 and M6 are invariant checks, not KPIs.** A non-zero M2 or M4, or an M6 below 100%, is a
> **bug**, not a bad week. They alert on any breach, not on a trend, and they map directly to the
> PRD's FR-1 / FR-2 / FR-3 assertions.

### Tier 2 — is the routing sane?

| # | Metric | Definition | Baseline | Target | Alert |
|---|---|---|---:|---:|---|
| **M7** | Sanctions routing SLA | `SANCTIONS_HIT` applications reaching the compliance queue ÷ all such applications; and time-to-queue | no distinct route today | 100%, p95 ≤4h | P1 on any miss |
| **M8** | `NO_DATA` share | L1 FAILs classed `NO_DATA` ÷ all L1 FAILs | n/a | ≤10% | P2: >20% for 24h |
| **M8b** | Classifier agreement | classifier class matching the reviewer-assigned class ÷ L4 cases with a reviewer class | n/a | ≥90% | P2: <85% weekly |
| **M9** | Fallback recovery rate | `VERIFIED` ÷ applications entering any L2/L3 tier | 48.09% observed | ≥45% | P2: <35% for 7d |
| **M9b** | Crossover recovery rate | `VERIFIED` ÷ applications taking the SSN→non-SSN crossover | 55.0% (8,605 cases) | ≥50% | P3 |
| **M9c** | IDV effectiveness | `VERIFIED` ÷ applications reaching L3 | 86.3% (on 2,507 cases, 0.87% of failures) | ≥70% at volume | P2: <60% |
| **M10** | Per-tier pass rate | PASS ÷ attempts, by provider, daily | per-provider trailing | within ±5pp of 28d trailing | P2 on drift |

> **M9c deserves scepticism, not celebration.** 86.3% is measured on 0.87% of eligible volume — an
> unrepresentative, probably self-selected sample. Expect regression at 10–20× volume. Its target is
> set well below its baseline for exactly this reason.

### Tier 3 — guardrails: did we weaken a control?

| # | Metric | Definition | Baseline | Target | Alert |
|---|---|---|---:|---:|---|
| **G-a** | Manual-review decline rate | `HARD_REJECT` ÷ L4 cases decided | pre-rollout trailing | within ±5pp | P2 on breach |
| **G-b** | Sanctions true-hit rate | confirmed hits ÷ `SANCTIONS_HIT` cases | ≈21% (79.0% of 9,994 cleared as false positives) | ±5pp | P1 on a sharp drop — implies over-firing or mis-routing |
| **G-c** | Post-verification fraud / chargeback rate | fraud-flagged ÷ verified, 90-day cohort | current trailing | no increase vs. control | P1 on any increase |

> **G-c is the metric that decides whether v2 was actually a good idea.** Every other metric can read
> green while we verify people we should not have. It lags 90 days — which is precisely why the
> control cohort must survive to P4. Cut over to 100% early and the comparison is gone permanently.

### Tier 4 — cost, latency, friction

| # | Metric | Definition | Baseline | Target | Alert |
|---|---|---|---:|---:|---|
| **C1** | Provider spend per verified applicant | Σ `cost_cents` ÷ `VERIFIED` | illustrative | ≤ +20% vs. baseline | P2 on breach |
| **C2** | L4 case volume | L4 cases per week | ~21,900/yr (74,400 cases over the window) | ≤ modelled 2.4× (~51,600/yr) | P1: >3.0× — capacity breach |
| **C3** | L4 turnaround | queue-entry → decision | current trailing | p50 <24h, p90 <72h | P1: p90 >120h |
| **C4** | **IDV completion** | completions ÷ invitations (`kyc_idv_funnel`) | **unmeasurable today** | ≥70% | P2: <60% |
| **C5** | End-to-end decision latency | submit → terminal state | p50 <2s | p50 unchanged; p90 <5s excl. L3/L4 | P2 on p50 regression |

> **C4 is the friction metric we currently cannot see at all.** A 10–20× increase in IDV volume into a
> 60–120 second document-and-selfie flow is a real abandonment risk, and today an abandoned IDV is
> recorded identically to a decline. Without the separate invitation/start/completion instrumentation,
> C4 is unmeasurable and we will misread drop-off as rejection.

---

## 4. Measurement design

**Assignment.** Sticky hash of `application_id`, fixed at first submission. Applications never change
cohort mid-flight, so no applicant experiences two routing regimes.

**Primary readout.** Difference in M1 between treatment and control, on applications *submitted* within
the phase window and matured to the 14-day boundary. Report the absolute difference in percentage
points with a 95% interval, never a relative "x% better".

**Sample adequacy.** At 5% traffic (P1) the cohort is too small to resolve a ~1.9pp move in M1 within
two weeks — P1 is a **correctness** phase, and its exit gates are invariants (M2, M6) and queue health
(C3), not conversion. M1 becomes readable at P2 (25%) and decision-grade at P3 (50%).

**Three effects must be reported separately, never netted:**

| Effect | Why it must be isolated |
|---|---|
| **Routing fix** (the stranded population) | The genuine win. This is what "did v2 work?" means. |
| **Bypass retirement** (M3b) | Expected to *reduce* verification rate — it forces 94,183 applicants/window who currently verify at 99.08% through a real primary check. Bundled into M1, it hides a real win under a control improvement. |
| **Stranded backlog migration** | A one-off recovery batch, not steady-state behaviour. Its recoveries are excluded from the M1 series, or the running system looks better than it is. |

**Attribution.** With per-change feature flags (PRD FR-11), `flag_state` on every event allows M1 to be
decomposed by flag combination. Analysts should decompose before attributing any movement.

---

## 5. Dashboards

| Dashboard | Audience | Refresh | Contents |
|---|---|---|---|
| **Funnel Health** | Exec / Product | Daily | M1 against the 5% bar, treatment vs. control; verification by tier; week-over-week trend; the A–D process-failure bucket mix restated on live data |
| **Routing Integrity** | Backend Eng | 5 min | M2, M3, M4, M5, M6 as **invariant panels — green/red, not trend lines**; per-tier volume; error and timeout rates |
| **Ops Capacity** | Review Ops | Hourly | C2 queue depth, C3 turnaround by percentile, arrival vs. completion rate, backlog burn-down, analyst utilisation, **compliance queue shown separately** from identity review |
| **Provider & Cost** | Product / Finance / Vendor mgmt | Weekly | C1, per-provider volume · pass rate · latency · spend, C4 IDV funnel, cost per incremental verification |
| **Rollout Scorecard** | Everyone, P0–P4 | Daily | Every phase-gate metric, treatment vs. control side by side, with the gate threshold drawn on each chart |

The Rollout Scorecard exists so each phase-gate decision is made against a **pre-agreed panel** rather
than re-argued from scratch. It is retired at P4.

---

## 6. Alerts

| Sev | Trigger | Route | Response |
|---|---|---|---|
| **P1** | An invariant is broken or a control is at risk — M2, M3, M4, M5, M6, M7, G-b, G-c, C2, C3 | Page on-call engineer; Compliance also paged for M7 / G-b | Assess within 15 min. **Any unresolved P1 for >1h auto-halts the ramp** — freeze at the current percentage, do not auto-revert. |
| **P2** | A KPI or trade-off is off target — M1, M3b, M8, M8b, M9, M9c, M10, C1, C4, G-a | Slack to Product + Eng + Ops | Triage same business day; **blocks the next phase gate until explained** |
| **P3** | Informational drift — M9b, minor provider variance | Weekly digest | Reviewed at the weekly rollout stand-up |

**Why halt rather than auto-revert:** flipping routing mid-application is its own failure mode. Rollback
is a human decision, with the legacy path kept warm through P4.

**Two alerts that must exist and are easy to forget:**

- **Silence alert.** If `kyc_decision_event` volume for any tier drops >50% hour-over-hour, page. A tier
  that has stopped firing looks identical to a tier with nothing to do — and the stranding defect went
  unnoticed for three and a half years precisely because *absence generates no signal.*
- **Reconciliation alert.** Daily comparison of v2 terminal states against the legacy result columns
  (both are written through P4). Any divergence outside the expected treatment effect is an
  integration bug, not a product result.

---

## 7. What we watch in each phase

| Phase | The question being answered | Watch | Stop / do not proceed if |
|---|---|---|---|
| **P0 Shadow** (100% mirrored, 0% acting) | Would v2 have decided differently, and can the classifier be trusted? | M8b agreement on the reviewer-labelled subset; projected L4 volume vs. model; shadow M2 / M4 | Agreement <95%, or projected L4 volume >1.2× model |
| **P1 Canary** (5%) | Does it work at all, and does the queue hold? | M2 (must be 0), M6, C3, every P1 alert | Any P1 alert; C3 p90 >72h |
| **P2 Ramp** (25%) | Is the recovery real, and what does IDV friction actually cost? | M1 in cohort, M9, M9c, **C4**, C1 | M1 not improving vs. control; C4 <60% |
| **P3 Majority** (50%) | Are the guardrails holding, and is the cost defensible? | G-a, G-b, early G-c signal, C1, C2 | G-a moves >5pp; G-c shows any fraud increase |
| **P4 Full** (100%) | Did we hit the goal, and can we prove it? | M1 full population, re-baselined target, 90-day G-c readout | — |

**Two things are deliberately not ramped with the main flag** and are measured on their own series:
bypass retirement (M3b, expected to cost rate) and the stranded-backlog migration (a one-off, excluded
from the steady-state M1 series).

---

## 8. Honest limits of this plan

- **The 48.09% recovery figure is a comparison-group estimate, not a measured outcome.** Stranded
  applicants never received a second check, so their true recoverability is unobserved; the comparison
  group may be an easier population. P1 and P2 exist to measure it. If M9 lands materially below 45%,
  the ≤6.3% target is **wrong and gets re-baselined at P3** — stated now, not discovered late.
- **M9c's 86.3% IDV effectiveness rests on 2,507 cases, 0.87% of eligible volume.** Treat it as a
  hypothesis to be tested at P2, not an input to a forecast.
- **All C1/C2 cost figures use illustrative unit costs applied to real volumes.** The volumes are
  load-bearing; the unit costs are not. Contracted rates go in before any threshold is treated as a
  budget commitment.
- **G-c lags 90 days.** For its first quarter, v2 is judged on process-integrity metrics (Tier 1) plus
  the best available proxy — manual-review decline-rate stability (G-a). We should say plainly that the
  outcome question is open until the first fraud cohort matures.
- **M8b needs ground truth that does not exist yet.** Classifier agreement is measured against
  reviewer-assigned classes, which requires reviewers to record a class on every L4 case from P0
  onward. If that field is not populated, M8b is unmeasurable and the P0 exit gate cannot be evaluated.

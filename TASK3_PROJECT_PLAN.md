# Project Plan — KYC Verification Waterfall v2

| | |
|---|---|
| **Document** | Project Plan (3 of 3: PRD · ARD/Monitoring Plan · Project Plan) |
| **Owner** | Product Manager, KYC |
| **Primary audience** | Business stakeholders, Compliance, Finance, Review Ops leadership |
| **Status** | For approval |
| **Version / date** | v2.0 — September 2026 |

> **This document is self-contained.** It states the problem, the fix, what it costs, who does what,
> in what order, and how the rollout limits risk. The **PRD** holds the design and requirements; the
> **ARD / Monitoring Plan** holds metric definitions. Neither is needed to read this.

---

## 1. The ask, in one page

**The problem.** Every applicant for our US consumer product must pass identity verification (KYC).
Verification runs as a waterfall — a primary provider, then secondary providers, then a human
reviewer. **7.93% of applicants end up not verified, against a 5% bar.** Across 2,515,155
applications (Jan 2023 – May 2026) that is 199,421 people, roughly **73,663 more than the bar allows.**

**The cause is not that people fail checks — the waterfall stops running.** 101,162 applicants (half of
all non-verifications) failed the primary check and then had **no second check of any kind**. Nobody
looked at them again. Comparable applicants who *were* routed onward recovered at **48%**. Three
quarters of all non-verification is process failure, not a correct decision.

**The fix.** Rebuild the routing so every failure has a defined path and no applicant can leave the
system undecided. **No verification standard, threshold, or control is loosened** — the entire
improvement comes from making the waterfall finish. Two changes actually *strengthen* controls: every
applicant now gets the primary check (today 3.74% bypass it), and sanctions/PEP screening becomes a
distinct, fast-routed signal instead of being folded into an ordinary failure.

**What it buys, what it costs.**

| | |
|---|---|
| **Expected outcome** | Non-verification **7.93% → ~6.0%**; committed target **≤6.3%**, re-baselined on live data at 50% rollout |
| **Principal cost** | Human review volume rises **~2.4×** (~21,900 → ~51,600 cases/yr) — **≈8 additional analyst FTE** |
| **Provider spend** | Roughly **+$120K–240K/yr** in additional secondary checks *(illustrative unit costs on real volumes; contracted rates pending)* |
| **Timeline** | ~10 weeks to build · ~12 weeks to ramp · **~22 weeks end to end** |
| **Critical path** | **Analyst hiring, not code.** Engineering is ramp-ready around week 13; review capacity is not ready for 100% until roughly week 22. |

**The honest headline for this committee:** *we are proposing to recover roughly 49,000 wrongly-lost
applicants a cycle by asking human reviewers to do about 2.4× the work.* That is a staffing decision
as much as an engineering one, and the plan is built so that the ramp moves at the speed of the queue,
not the speed of the build.

---

## 2. Objectives and success criteria

| # | Objective | Today | Target |
|---|---|---:|---:|
| 1 | No applicant leaves the waterfall undecided | 101,162 stranded | **0** |
| 2 | Reduce non-verification | 7.93% | **≤6.3%** (5.0% stretch) |
| 3 | Every applicant gets the primary check | 3.74% bypass it | **100%** |
| 4 | A clean pass is final | 5.23% got extra checks anyway | **0** |
| 5 | The human safety net actually catches | reaches 30.2% of eligible cases | **100%** |
| 6 | Sanctions/PEP routed to compliance fast | no distinct route | **100%, within 4h** |
| 7 | **No control weakened to buy the rate** | — | Fraud, decline-rate and sanctions guardrails all within tolerance |

**Objective 3 will cost us rate, and we are doing it anyway.** Applicants who bypass the primary check
today verify at 99.08%. Forcing them through a real check will fail some of them. It is measured on its
own line so it is never confused with the routing improvement — and it is a control fix, not a
conversion play.

---

## 3. Workstreams

| WS | Workstream | Owner | Depends on | Deliverable |
|---|---|---|---|---|
| **WS0** | **Discovery & vendor confirmation** | PM + Backend Eng Lead | — | A signed answer to: *does our primary provider return structured failure-reason codes and a separable sanctions flag?* Plus contracted provider unit costs and latency SLAs. **Go/no-go on the classifier design.** |
| **WS1** | Reason classifier | Backend Eng | WS0 | Deterministic rule layer mapping provider responses to one of four reason classes, plus the secondary-issue signal |
| **WS2** | Orchestration engine | Backend Eng | WS1 (interface only) | Routing tree, mandatory primary check, unconditional pass-exit, guaranteed terminal state, retry/timeout handling, per-change feature flags |
| **WS3** | Provider integration cleanup | Integrations Eng | WS0 | Duplicate LexisNexis integrations unified into one secondary role; Persona SSN and IDV modes exposed as distinct tiers; the undocumented primary entry point removed |
| **WS4** | Sanctions/PEP split & compliance path | Compliance Ops Lead + Backend | WS1 | Independent flag, immediate compliance route, compliance queue separated from identity review, audit trail |
| **WS5** | **Review capacity & tooling** | Review Ops Manager | WS0 volume model | Phased hiring plan (≈8 FTE), case UI showing reason class and full path, SLA definitions, escalation policy |
| **WS6** | Data & monitoring | Data & Analytics | WS2 event schema | Decision-event table, five dashboards, alert rules, daily reconciliation job |
| **WS7** | "Legacy account" definition | PM + Account Services | — | An operational rule for the legacy-SSN route. **Currently undefined** — no signal in our data (age, vintage, or partner) reproduces it |
| **WS8** | Stranded backlog migration | Review Ops + Backend + Legal | WS2, WS5, Legal sign-off | Throttled re-processing of the 101,162 existing stranded applicants, with notification copy cleared by Legal |
| **WS9** | Rollout & measurement | PM + Data | WS6 | Cohort assignment, phase gates, rollout scorecard, go/no-go decisions |

---

## 4. Sequencing

```
Week:  1  2 │ 3  4  5  6  7  8  9 10 │11 12│13 14│15 16 17│18 19 20 21 22
       ─────┼────────────────────────┼─────┼─────┼────────┼──────────────
WS0   ████  │                        │     │     │        │                 ◄ gate: classifier go/no-go (wk 2)
WS7   ██████████                     │     │     │        │                 ◄ gate: legacy route buildable (wk 4)
WS1        │ ████████                │     │     │        │
WS2        │ ████████████████        │     │     │        │
WS3        │     ████████            │     │     │        │
WS4        │       ██████            │     │     │        │
WS6        │     ████████████        │     │     │        │
WS5   ████████████████████████████████████████████████████████████████      ◄ hiring runs continuously
WS8        │                         │     │     │  ███████████████████     ◄ after 25% ramp only
WS9        │                         │ P0  │ P1  │   P2   │  P3  │  P4
                                       0%    5%     25%     50%    100%
```

**Critical path:** WS0 → WS1 → WS2 → WS6 → shadow → ramp.
**Parallel, off the critical path:** WS3, WS4, WS7.
**Paces the second half:** WS5. Engineering is ready to ramp around week 13; analyst capacity is not
ready for 100% traffic until roughly week 22. **We ramp at the speed of the queue.**

---

## 5. Dependencies, and what breaks if they slip

| Dependency | Owner | Risk if unresolved | Mitigation |
|---|---|---|---|
| **Primary provider returns structured reason codes** | WS0 | The classifier — and with it the whole routing design — cannot be built as specified. This is the single load-bearing assumption in the programme and it is **unconfirmed**. | A fallback design is already specified: on any failure, run the SSN-path check and the secondary identity check in parallel, then document verification, then human review. It still delivers objectives 1, 3, 4 and 5; it costs more per failed applicant and loses the sanctions fast-path. **Decide by end of week 2** — do not start WS1 on an assumption. |
| **"Legacy account" has a definition** | WS7 | The legacy SSN route has no evaluable gate | If unresolved by week 4, ship v1 routing all SSN mismatches to LexisNexis, logged as a documented, accepted deviation. Add the legacy route when Account Services can define it. |
| **≈8 analyst FTE hired and trained** | WS5 | Ramping past 25% creates a review backlog — a worse applicant experience than today's stranding | **Ramp gates are tied to headcount, not sprint completion.** Contract/BPO capacity as a bridge if hiring lags. |
| **Legal sign-off on backlog notification** | WS8 | The 101,162 stranded applicants cannot be re-processed | WS8 is sequenced last by design so it never blocks the main rollout. |
| **Contracted provider unit costs** | WS0 | Every cost figure in this plan stays illustrative | Contract data in by week 2; cost thresholds re-set before the 25% ramp. |

---

## 6. Rollout, and how it limits risk

| Phase | Traffic | Duration | Gate to enter | Gate to exit |
|---|---|---|---|---|
| **P0 Shadow** | 100% mirrored, **0% acting** | 2 wks | Built, dashboards live | Classifier ≥95% agreement with human-labelled cases; projected review volume within ±20% of model |
| **P1 Canary** | 5% | 2 wks | +2 analysts onboarded | Zero stranded applicants in cohort; no critical alerts; review turnaround p90 <72h |
| **P2 Ramp** | 25% | 3 wks | +3 analysts | Non-verification in cohort ≤6.5%; document-verification completion ≥65%; guardrails flat |
| **P3 Majority** | 50% | 3 wks | +3 analysts; queue turnaround stable | Guardrails within tolerance; **target re-baselined on live data** |
| **P4 Full** | 100% | — | All gates green | Legacy path deleted after 30 days dark |

**Five deliberate risk controls:**

1. **Shadow before acting.** P0 runs the new system on all traffic while making zero real decisions —
   the only phase where a wrong classifier costs nothing. Given the unconfirmed vendor dependency,
   skipping shadow would be the worst decision available to us.
2. **One switch per change.** Routing, pass-exit, bypass retirement and document-verification promotion
   each ship behind their own flag. Bypass retirement is *expected* to cost verification rate; bundled
   with the routing fix it would mask a genuine win and we would draw the wrong conclusion about the
   whole programme.
3. **Halt, don't auto-rollback.** An unresolved critical alert freezes the ramp at its current
   percentage. It does not automatically revert — flipping routing mid-application is its own failure
   mode. Rollback is a human decision, with the old path kept warm through P4.
4. **A control group survives to 100%.** The metric that ultimately decides whether this was a good
   idea is post-verification fraud rate, and it lags 90 days. Cutting over early destroys the
   comparison and leaves the question permanently unanswerable.
5. **The backlog migration is throttled and reported separately.** Re-processing the 101,162 stranded
   applicants is capped at 20% of daily review capacity, and its recoveries are excluded from the
   steady-state rate so the running system is not flattered by a one-off.

---

## 7. Cost and resourcing

| Item | Basis | Estimate |
|---|---|---|
| Additional human review | ~29,700 extra cases/yr at ~$8/case | **≈ +$238K/yr** |
| Additional review headcount | 15 cases/analyst/day | **≈ 8 FTE**, hired in three tranches gated to the ramp |
| Additional provider calls | ~100K–160K extra secondary checks/yr at a blended ~$1.00–1.50 | **≈ +$120K–240K/yr** |
| Engineering | 2 backend, 1 integrations, 1 analytics engineer | ~10 weeks |
| **Ongoing run-rate increase** | | **≈ $360K–480K/yr** |

**All unit costs above are illustrative; the volumes are real and measured.** Contracted vendor rates
and true per-case ops costs land in week 2 (WS0) and every figure here is restated before the 25% ramp.
No budget commitment should be made against these numbers until then.

**The structural answer to this cost is out of v1 scope, on purpose.** A risk-based auto-decline layer
— scoring which automated failures are safe to reject without a human look — is the lever that would
cut most of the 2.4× review increase. It needs labelled outcome data that this build will itself
generate, which is why it is scoped as the v2.1 fast-follow rather than guessed at now.

---

## 8. Top risks

| Risk | Likelihood | Impact | Owner | Response |
|---|---|---|---|---|
| Classifier not buildable as designed | **Medium** | High | WS0 | Fallback design pre-specified; decision forced at week 2 |
| Review queue overruns | **Medium** | High | WS5 | Capacity-gated ramp; BPO bridge; auto-decline layer as the structural fix (v2.1) |
| Document-verification abandonment at 10–20× volume | **Medium** | Medium | PM | Invitation / start / completion instrumented separately; the step is placed last in the path; ships on its own flag |
| Recovery lands below the modelled 48% | Medium | Medium | PM + Data | Target re-baselined at 50% rollout on live data — stated up front, not discovered late |
| Bypass retirement measurably lowers the rate | **High** | Low–Med | PM | Expected. Isolated on its own flag and reported on its own line. It is a control fix; we ship it and report it honestly rather than trading it for headline rate. |
| A control weakens invisibly | Low | **Severe** | Compliance | Three guardrail metrics; sanctions guardrail paged as critical; control group held to 100% |

---

## 9. Decisions needed from this group

| # | Decision | Needed by |
|---|---|---|
| 1 | Approve ≈8 additional review FTE and the ~$360–480K/yr run-rate increase, phased against the ramp | **Week 1** — hiring is the critical path |
| 2 | Accept **≤6.3%** as the committed target, with re-baselining at 50% rollout, rather than committing to 5.0% on day one | Week 1 |
| 3 | Account Services to define "legacy account", or accept shipping without that route as a documented deviation | Week 4 |
| 4 | Legal/Compliance to approve re-contacting the 101,162 stranded applicants | Before week 15 |
| 5 | Accept that the primary-check bypass retirement will likely *reduce* headline verification rate, as the price of closing a control gap | Week 1 |

---

## 10. Definition of done

- Zero stranded applicants, zero checks after a clean pass, and 100% terminal-state completeness held
  for **30 consecutive days at full traffic**.
- Non-verification rate re-baselined and reported against the 5% bar, with the treatment/control
  comparison shown.
- Decline-rate and sanctions guardrails within tolerance; the first 90-day post-verification fraud
  cohort read out.
- Stranded backlog fully re-processed; legacy routing path deleted.
- The "legacy account" question either implemented or closed as an accepted, documented deviation.
- Auto-decline layer scoped for v2.1 using the outcome data this build has by then generated — the
  lever that pays back the review cost this design deliberately took on.

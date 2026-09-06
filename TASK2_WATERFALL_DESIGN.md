# Task 2 — Redesigned KYC Waterfall

**New here?** [README.md](README.md) for setup, [IMPORTANT.md](IMPORTANT.md) for the Task 1 numbers
this design builds on, [Where the Funnel Breaks](https://claude.ai/code/artifact/e9f9cc6d-f995-4873-9db2-f6bb36b16018)
for the Task 1 report. **Diagram version of this document:** [The Waterfall, Rebuilt](https://claude.ai/code/artifact/49e52e3d-08f8-49bc-a5ee-2dc1a300051d).

---

## Answer first

**Route everyone who fails the first check — that alone closes most of the gap.** Task 1 found that
101,201 users (50.8% of every non-verification) failed the primary check and were simply never given
a second one; users who *were* routed onward recovered at 48.09% against 0.01% for those left
stranded. This redesign makes "never routed" structurally impossible: every failure gets a reason
class and a defined path, and nobody exits the waterfall without either verifying or being seen by a
human. Modelled effect: **7.93% → roughly 6.0%**, most of the way to the 5% bar, with the remaining
gap closed by two smaller, lower-confidence changes (deploying Persona IDV properly, and retiring an
undocumented bypass) rather than by loosening anything.

Every change below is tied to a numbered Task 1 finding. None of them weaken a fraud, sanctions, or
PEP control — two of them **strengthen** one, and the reasoning for that is new evidence found while
building this design (see Finding 6).

---

## 1. The current flow, audited

This document originally jumped straight to the redesign. It shouldn't have — a redesign is only as
credible as the audit of what it's replacing. So: every distinct path actually taken through today's
system was enumerated (all 37 of them, no volume threshold) and checked against the brief's literal
rules, not just the headline "stranded" finding from Task 1. Full method, the complete 37-path table,
and the SQL: [AUDIT_LOG.md §10](AUDIT_LOG.md#10-full-flow-audit--every-path-in-the-data-classified-valid-or-invalid).

**85.67% of today's flow volume already matches the documented design exactly.** The other 14.33%
splits into one small, mostly-benign undocumented pattern and four real problems — this is exactly
where the redesign below is aimed, and nowhere else.

| Flow category | Users | % | Verified |
|---|---:|---:|---:|
| **Valid** — matches a documented rule, incl. the "crucial rule" crossover | 2,154,745 | 85.67% | 96.17% |
| **Undocumented, not broken** — SSN or non-SSN double-check cascade | 8,748 | 0.35% | 99.89% |
| **Leak — stranded:** Idology FAIL, nothing else ran | 101,162 | 4.02% | 0.00% |
| **Leak — Idology skipped:** the undocumented bypass entry point | 94,183 | 3.74% | 99.08% |
| **Leak — PASS didn't exit:** waterfall continued after a clean pass | 131,538 | 5.23% | 99.81%\* |
| **Borderline — Step 2 skipped:** FAIL routed straight to manual, no automated attempt first | 24,779 | 0.99% | 41.14% |
| **Total** | 2,515,155 | 100% | 92.07% |

\* Hides a sharp tail: 201 of these 131,538 users passed Idology, had further checks or manual review
run anyway, and only 37.3% (75 of 201) ended up verified — a direct contradiction of "if the user
passes, they are verified," not merely wasted processing. See Finding 7.

**Reading the "undocumented, not broken" row carefully, since it's the one most likely to be
misread as a problem:** it's users who failed one SSN-path check and then also had the *other*
SSN-path check run (LexisNexis and Persona-SSN both), or the equivalent on the non-SSN side (ACRO and
Persona IDV both). The brief presents each pair as alternatives chosen by account segment, not a
retry chain, so this isn't literally the documented design — but it isn't a leak either: it resolves
at a 99.89% rate, among the best in the entire funnel. §2 below turns exactly this pattern into
official policy (L2a→L2b, L2→L3) rather than removing it.

**Every leak and the borderline case is addressed in the redesign below** — three were already fixed
in earlier drafts of this document; the "PASS didn't exit" leak surfaced only during this audit and
adds one new rule (Finding 7, §5).

---

## 2. The provider roster, redefined

| Tier | Check | Role in the redesign | What changes vs. today |
|---|---|---|---|
| **L1** | Idology | Mandatory identity check (name/DOB/address/SSN) **for 100% of applicants, no exceptions.** Also the current carrier of sanctions/PEP signal (see Finding 6) — that signal is split out into its own always-checked flag rather than left folded into a bare PASS/FAIL. | Closes the 3.7% undocumented bypass (Finding 5). |
| **L1.5** | Reason classifier *(new — a rule layer, not a vendor)* | Tags every Idology FAIL with one of: `SANCTIONS_HIT`, `SSN_MISMATCH`, `IDENTITY_ATTR_MISMATCH` (name/address/DOB), `NO_DATA`. Drives all routing below. | This is the single engineering prerequisite the whole redesign depends on — see Finding 1 and the Open Items section. |
| **L2a** | LexisNexis (one integration) | Secondary SSN/identity check for `SSN_MISMATCH`. | Unifies `ProviderA_Lexis_Nexis` and `ProviderB_Lexis_Nexis` into one documented secondary role — no more silent primary-position usage (Finding 5). |
| **L2b** | Persona — SSN mode | Second SSN-path fallback, for anyone who fails L2a. | Currently gated by an undocumented "older accounts" rule that isn't reproducible from the data (Task 1, §2.5). Redesign makes it a standard fallback for **everyone** on the SSN path, dropping the unexplained carve-out. |
| **L2** | ACRO | Secondary identity-attribute check for `IDENTITY_ATTR_MISMATCH` — automated, cheap, fast. | Unchanged in role; now reliably reached (Finding 1) instead of reached only when volume happened to be routed. |
| **L3** | Persona — IDV mode (document + selfie) | Highest-assurance automated check: the fallback for anyone who fails L2 (ACRO) *or* whose reason is `NO_DATA`. | Promoted from "almost never used" (<1% of Idology failures, Task 1 §4.1) to "the standard second non-SSN fallback" — deliberately still placed *after* the cheaper ACRO check, not before, because it is the highest-cost, highest-friction step in the whole waterfall (Finding 3). |
| **L4** | Manual / compliance review | Two entry points: (a) anyone who exhausts every automated fallback on their assigned path, (b) **immediately** for any `SANCTIONS_HIT`, bypassing further automated attempts entirely. Final decision authority. | Today reaches only 30.2% of users who exhausted automation (Task 1 §2.6). Redesign makes reaching L4 a *guarantee*, not a possibility — the safety net actually catches everyone it's meant to. |

---

## 3. Routing logic

```
                                    ┌─────────────────────┐
                                    │   L1 — Idology       │   100% of applicants, no exceptions
                                    │  (identity + SSN +   │
                                    │   sanctions signal)  │
                                    └──────────┬───────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
              SANCTIONS_HIT               PASS, clean               FAIL, no sanctions
                    │                          │                          │
                    ▼                          ▼                          ▼
          ┌──────────────────┐        ┌──────────────┐        ┌─────────────────────┐
          │  L4 — Manual /    │        │   VERIFIED    │        │  Reason classifier   │
          │  compliance       │        │    (exit)     │        │  (L1.5)              │
          │  — immediate,     │        └──────────────┘        └──────────┬───────────┘
          │  no automated     │                                            │
          │  fallback         │                     ┌──────────────────────┼──────────────────────┐
          └────────┬──────────┘                     │                      │                      │
                    │                          SSN_MISMATCH        IDENTITY_ATTR_MISMATCH        NO_DATA
              PASS  │  FAIL                          │                      │                      │
                    │                                ▼                      ▼                      ▼
                    ▼                        ┌───────────────┐      ┌───────────────┐   ┌─────────────────────┐
          ┌──────────────┐                   │ L2a LexisNexis │      │  L2 ACRO       │   │ Run L2a + L2 in     │
          │   VERIFIED    │                   └───────┬────────┘      └───────┬────────┘   │ parallel (both      │
          │  (if PASS)    │                     PASS   │  FAIL           PASS  │  FAIL      │ cheap/automated)    │
          │      or       │                            │                      │            └──────────┬───────────┘
          │ HARD REJECT   │                            ▼                      ▼                        │
          │ (if FAIL —    │                     ┌───────────────┐      ┌───────────────┐          any PASS → VERIFIED
          │  genuine      │                     │ L2b Persona-SSN│      │ L3 Persona IDV │          both FAIL ↓
          │  decline)     │                     └───────┬────────┘      └───────┬────────┘   ┌─────────────────────┐
          └──────────────┘                        PASS   │  FAIL           PASS  │  FAIL      │  L3 Persona IDV      │
                                                    ▼      ▼                 ▼      ▼          └──────────┬───────────┘
                                              VERIFIED   L4 Manual    VERIFIED   L4 Manual         PASS │      │ FAIL
                                                          review                  review               ▼      ▼
                                                             │                       │             VERIFIED  L4 Manual
                                                             ▼                       ▼                          review
                                                     PASS→VERIFIED           PASS→VERIFIED
                                                     FAIL→HARD REJECT        FAIL→HARD REJECT
```

**In words, in priority order:**

1. **Idology runs on every applicant.** No exceptions, no bypass.
2. **Sanctions/PEP flag present → straight to manual/compliance review**, regardless of the identity
   match result, skipping every automated fallback. Compliance decides; a FAIL there is a hard reject.
3. **Idology PASS, no sanctions flag → verified, exit — no exceptions.** (Unchanged in intent — this
   path already works for 84.8% of applicants — but now an explicit, enforced rule rather than an
   implicit one. See Finding 7: today, 131,538 users get a clean PASS and the waterfall runs further
   checks on them anyway, and 201 of those end up *not verified* despite having passed. That cannot
   happen once PASS terminates the flow unconditionally.)
4. **Idology FAIL → the reason classifier assigns a class**, which sets the path:
   - `SSN_MISMATCH` → LexisNexis → (if fail) Persona-SSN → (if fail) manual review.
   - `IDENTITY_ATTR_MISMATCH` → ACRO → (if fail) Persona IDV → (if fail) manual review.
   - `NO_DATA` (the classifier can't confidently bucket it) → LexisNexis and ACRO both run → any
     PASS verifies; if both fail, Persona IDV as a single highest-assurance attempt → (if fail)
     manual review.
5. **Manual review is the last stop for every path.** PASS verifies; FAIL is a hard reject.

---

## 4. Stop conditions — where a user is hard-rejected, and why

| # | Condition | Why it's final |
|---|---|---|
| 1 | Confirmed sanctions/PEP/OFAC match, after compliance review | Never resolved by routing to a friendlier automated check — a true match is a legal/compliance decline, not a conversion problem. This is the brief's non-negotiable, made explicit as a rule rather than an emergent behaviour. |
| 2 | Exhausted every automated check on the assigned path, and manual review declines | The genuine-rejection floor. Task 1 quantified this population at 48,655 users (24.4% of all non-verifications) who were already assessed by 2+ providers and a human — this redesign does not try to shrink it, because Task 1 found no evidence it's addressable without weakening a control. |

**Not a stop condition, deliberately:** an automated FAIL alone, on its own, at any tier. Every path
in this design reaches a human before a final no — which is a strengthening of today's control
posture, not just a conversion fix (see Finding 6).

**A rule that isn't a stop condition, but is just as non-negotiable:** a clean Idology PASS also
ends the flow, unconditionally, in the other direction. Today's data shows 131,538 users where it
doesn't (§1's audit) — including 201 who passed and still weren't verified. Under this design a PASS
is as final as a hard reject; nothing downstream may re-open it (Finding 7).

---

## 5. Every change, tied to a Task 1 finding

| # | Task 1 finding | Redesign response |
|---|---|---|
| **1** | 101,201 users (50.8% of all non-verifications) failed Idology and were never routed onward; comparable routed users recovered at 48.09% vs. 0.01% stranded. **The single highest-leverage finding.** | The reason classifier (L1.5) and the routing tree above guarantee every failure gets a path. "Stranded" becomes structurally impossible. |
| **2** | Manual review reached only 30.2% of users eligible for it (Task 1 §2.6) — the safety net had a hole exactly where the design says it should catch people. | Every path now terminates at manual review if automation doesn't resolve it. Coverage goes from "sometimes" to "always." |
| **3** | Persona IDV clears 86.3% of the failures it's tried on vs. 30.7% without it, but ran on under 1% of Idology failures (Task 1 §4.1) — the best tool, barely used. | Promoted to the standard second non-SSN fallback (L3) — but deliberately kept *after* the cheaper ACRO check, because it's also the highest-cost, highest-friction step (see §6). |
| **4** | The documented "older accounts → legacy Persona-SSN" rule showed no age or account-vintage signal anywhere in the data (Task 1 §2.5) — not reproducible, and reported honestly as unresolved rather than guessed. | Retired. Persona-SSN (L2b) is now a standard fallback for every SSN-path failure, not a segment nobody can define. |
| **5** | `ProviderA_Lexis_Nexis` was acting as an undocumented second primary entry point — 94,184 users (3.7%) never saw Idology at all, and this route passed ~99% of what it saw (Task 1 §2.1, §2.4) — flagged as a control question, not just a routing curiosity. | Idology becomes the sole, mandatory L1. `ProviderA`/`ProviderB` are unified into one documented secondary role (L2a), reached only *after* a real primary check. |
| **6** | *New evidence, found while building this design* (§ below) — sanctions/PEP screening rides entirely on the same undifferentiated Idology FAIL signal as ordinary identity mismatches, and **zero of the 101,201 stranded users have any reviewer comment at all** — meaning today's design has no visibility into whether any of them included an undetected sanctions or PEP signal. | Sanctions/PEP is split into its own always-checked flag (L1.5) with a **hard, immediate route to compliance** — skipping automated fallbacks rather than waiting for them to fail first. This is why the redesign is risk-*positive*, not just risk-neutral: it closes a blind spot the current design has no way to even measure. |
| **7** | *New evidence, from the §1 flow audit* — 131,538 users get a clean Idology PASS and the waterfall runs further checks on them anyway, contradicting "if the user passes, they are verified and exit the waterfall" outright. A small tail of 201 of them end up **not verified despite having passed.** | PASS becomes an unconditional stop, symmetric with the hard-reject stop conditions in §4. No downstream check — automated or manual — may run once Idology returns a clean PASS. |

### Finding 6, in detail

This wasn't in the Task 1 notebook — it came from checking whether "route everyone" could
inadvertently touch sanctions/PEP handling before proposing it as the headline fix. The check:

- **9,994 users** have a reviewer comment mentioning sanctions, a watchlist, PEP, or OFAC.
- **Every one of them** — 9,994 of 9,994 — has `idology_result = 'FAIL'`. There is no observed case
  in this dataset of a sanctions/PEP mention against an Idology PASS.
- **All 9,994** were routed to a human (`manual_review_result` is populated for all of them), and
  79.0% were subsequently cleared as false positives — consistent with name-matching screening being
  noisy by nature, and with manual review correctly separating true hits from false positives when it
  gets the chance.
- **Zero of the 101,201 stranded users have a reviewer comment of any kind.** Structurally, nobody —
  human or system — has ever recorded why they failed beyond the bare Idology FAIL, because they
  never reached the point (a secondary check, or manual review) where that would happen.

**The honest claim this supports:** not "N sanctions hits are being missed" — that's unprovable from
this data, since a stranded user's true status is unobserved by definition. The defensible claim is
narrower and still consequential: *today's design has zero visibility into this population's risk
profile*, because sanctions signal and generic identity-mismatch signal are folded into one
undifferentiated FAIL, and the stranded state skips every point where that signal could otherwise
surface. Closing "stranded" — this design's central move — closes that visibility gap as a side
effect, and decoupling the sanctions flag from PASS/FAIL is what makes closing it a *hard* rule
instead of a lucky accident of the sequencing.

### Finding 7, in detail

Found while auditing the current flow (§1), not in the original Task 1 pass. 131,538 users — 5.23%
of everyone in the dataset — get a clean `idology_result = 'PASS'` and the system runs at least one
further automated check, manual review, or both, on them anyway. That is a direct contradiction of
the brief's own sentence: *"If the user passes, they are verified and exit the waterfall."*

For the overwhelming majority of these 131,538, the extra processing is harmless — 130,419 of the
130,517 who *only* pick up a redundant LexisNexis call still end up verified (99.9%), so the leak is
mostly wasted provider spend, not a broken outcome. But a small, sharp tail is not harmless:

| Extra checks that ran | Users | Verified | Rate |
|---|---:|---:|---:|
| LexisNexis + ACRO | 154 | 63 | 40.9% |
| Manual review only | 14 | 7 | 50.0% |
| LexisNexis + ACRO + manual review | 14 | 1 | 7.1% |
| LexisNexis + manual review | 12 | 4 | 33.3% |
| ACRO + manual review | 7 | 0 | 0.0% |
| **Subtotal** | **201** | **75** | **37.3%** |

These 201 users passed the primary identity check and were *still not verified* — automated
processing or a human reviewer, running on someone who should already have exited the waterfall,
overturned a PASS. Whatever caused these extra checks to fire (a logging quirk, a race condition, an
integration that doesn't respect an upstream PASS), the fix is the same regardless of cause: **make
PASS an unconditional exit**, not just a default one. §4 states this as a rule with the same weight
as a hard-reject stop condition.

---

## 6. Cost, latency, and friction — explicit trade-offs

**No provider unit costs or latencies exist in this dataset** (flagged in Task 1's caveats too). The
figures below use clearly-labelled illustrative unit costs, applied to the *real* Task 1 volumes, to
make the trade-offs concrete rather than hand-wavy. Swap in real vendor/ops numbers before this goes
into a budget conversation — the volumes are load-bearing, the unit costs are not.

| Check | Illustrative unit cost | Illustrative latency | Friction |
|---|---:|---:|---|
| Idology (L1) | $0.60 | <1s | None — invisible to the user |
| LexisNexis (L2a) | $1.20 | ~2s | None |
| Persona SSN (L2b) | $1.00 | ~2s | None |
| ACRO (L2) | $0.90 | ~2s | None |
| Persona IDV (L3) | $3.50 | 60–120s of active user time | **High** — document capture + selfie; the step most likely to cause drop-off |
| Manual review (L4) | ~$8 / case | Hours, not seconds | N/A (user doesn't see it directly, but wait time does affect experience) |

**Where the cost actually goes — three effects, sized against Task 1's real numbers:**

1. **More automated secondary calls.** Routing the 101,201 stranded users through 1–2 automated
   fallbacks each, in roughly the same proportions Task 1 observed among comparable *already-routed*
   failures (57.3% non-SSN / 29.4% SSN / 13.3% manual-only) — that's on the order of **100,000–160,000
   additional provider calls**. At a blended illustrative $1.00–1.50/call: **roughly +$120K–240K per
   year** (annualised over the dataset's ~3.4-year window). This is cheap relative to the next two
   effects, and it's the direct cost of Finding 1's fix.

2. **A large jump in manual review volume — the real trade-off.** Every path in this redesign
   terminates at manual review instead of sometimes reaching it. Adding Task 1's Bucket C (48,598
   users who already exhausted automation but never got a human look) to the portion of the newly-
   routed stranded population that still fails its automated path (≈52,552, using the observed
   48.09% recovery rate) gives roughly **101,150 additional manual review cases** over the dataset's
   window — about **+29,750/year**, on top of a current baseline of ~21,890/year. That's **roughly a
   2.4× increase in review volume.** At the illustrative $8/case and 15 cases/analyst/day (3,750/year):
   **≈+$238K/year and ≈8 additional analyst FTEs.** This is the single biggest number in this whole
   design, and the one most worth challenging with real ops data before committing to it.

3. **A large friction increase from Persona IDV.** Today it runs on 2,595 users total (≈763/year).
   Promoted to the standard non-SSN second fallback, it would plausibly serve a meaningful share of
   the ~58,000 non-SSN-path stranded users plus overflow from ACRO failures already in the funnel — a
   **10–20× volume increase**, into the tens of thousands per year. It's both the most expensive
   automated check ($3.50 vs. $0.60–1.20 for everything else) and by far the highest-friction one
   (document + selfie vs. invisible for everything else). This is exactly the step the brief's
   "adding checks is not free" warning is about, and it's why it sits *last* in the non-SSN path
   rather than earlier — every user who resolves at the cheaper, frictionless ACRO step never sees it.

**The trade-off in one sentence:** this design recovers most of the gap to 5% largely by asking human
reviewers to do a lot more work — call it roughly 2.4× today's volume — which is a real staffing and
budget decision, not a free routing fix, and it should be sized with actual ops numbers before
anyone commits to a headcount plan.

---

## 7. What's preserved, changed, and removed

| | |
|---|---|
| **Preserved** | Idology as the universal L1. Manual review as final decision authority. The brief's four-tier L1→L2/L3→L4 structure. The genuine-rejection floor (Bucket D, ~24.4%) — not targeted for reduction, because Task 1 found no evidence it's addressable without weakening a control. |
| **Changed** | LexisNexis unified into one documented SSN-path role. Persona-SSN loses its unreproducible "legacy" gate. Sanctions/PEP becomes an always-checked, independently-routed flag rather than a signal folded into ordinary FAILs. Manual review triage is made a guarantee, not a possibility. The undocumented SSN and non-SSN double-check cascades (§1, "undocumented, not broken") become official policy instead of an unexplained ~8,700-user subset. |
| **Removed** | The 3.7% Idology-skip entry point (`ProviderA` acting as an undocumented primary). The unexplained "older accounts" Persona-SSN carve-out. The possibility of a check running after a clean PASS (Finding 7). |

---

## 8. Open items for Task 3

- **The reason classifier (L1.5) is the load-bearing engineering dependency.** This design assumes
  Idology's response carries (or can be made to carry) structured fields distinguishing an SSN
  mismatch from a name/address/DOB mismatch from a sanctions hit. Task 1 found this classification
  isn't reliably reconstructable from the data as it stands today (`reviewer_comment` covers only
  2.96% of users). Confirming what Idology's actual API response contains is the first build item.
- **The manual review volume increase (~2.4×) is the biggest open risk in this design.** It's sized
  from Task 1's real proportions but illustrative unit costs — the actual staffing plan needs real
  numbers, and probably a phased rollout (Task 3) rather than turning this on for 100% of traffic on
  day one.
- **A risk-based auto-decline layer** (scoring which automated-fail cases are safe to hard-reject
  without a human look, vs. which need one) could meaningfully cut the manual review increase in (2)
  above — not designed here, since it would need labelled outcome data this dataset doesn't provide,
  but worth flagging as the natural next optimisation once this design is live and generating its own
  outcome data.
- **Persona IDV's friction cost isn't just financial** — a 10–20× volume increase into a 60–120s
  document-and-selfie flow is a real drop-off risk that this design can't quantify from KYC outcome
  data alone (it would need funnel/conversion telemetry from the *product*, not the *verification*
  system). Worth an explicit A/B or phased rollout rather than a flip of the switch.

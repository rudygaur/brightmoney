1. 146 — Idology PASSed, nothing else ran, user still not verified. This contradicts the documented design (Idology PASS ⇒ verified, exit) and doesn't fit "never routed on" either — there was nothing to route to, since Idology said PASS. This is a distinct anomaly, not a routing gap. ( This data should be FIXED AND REDO THE ANALYSIS )
2. 18 — the population flagged above. Never went through Idology at all (idology_result is null); Persona-IDV ran directly, PASSed, and the user is still not verified. This is a third undocumented entry point, on top of the LexisNexis one already documented below — and same as #2, the check said PASS, so this isn't "never routed on," it's "routed, passed, not verified anyway." (mark idology fail for this and overall status as pass and redo the analysis)
3. 2+ checks ran, no manual review	1,131	( these records are passed by any one source so these should be marked as true and redo the analysis)
----------
4. select * from kyc.kyc_users
where manual_review_result IN ('PASS')
AND (idology_result ='PASS'
OR lexis_nexis_result='PASS'
OR acro_result='PASS'
OR persona_idv_result='PASS'
OR persona_ssn_result='PASS')
and overall_kyc_status_raw = 'false'
--GROUP by overall_kyc_status_raw
; -- 5 records anomaly as to why this is still marked kyc failed

5. if idology flags for sanctions pep or ofac those should also go to manual, Pattern 1 — sanctions/PEP/OFAC hits (6,145 of 7,457 with a comment, 82.4%).
it's Idology raising a sanctions/PEP/OFAC watchlist flag ("PA hit - Sanctions...", "PA hit PEP alert...", "PA hit OFAC alert...").

6. 35 records passed from idology but failed later and went till manual review with overall status as false, these should be passed as very small number

7. no major significat path/provider that is kiscking the participant out of the funnel after consecutive fail 
| Flow (all results FAIL) | Users | % of bucket C |
|---|---:|---:|
| Non-SSN path — Idology FAIL, ACRO FAIL | 24,921 | 51.28% |
| SSN path — Idology FAIL, LexisNexis FAIL | 21,447 | 44.13% |
| Mixed — Idology FAIL, LexisNexis FAIL, ACRO FAIL | 1,099 | 2.26% |

8. manual review is the only check that appears alongside all the others. to be added at each step failure for OFAC and PEP
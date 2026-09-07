# -*- coding: utf-8 -*-
"""Renders the three Task 3 markdown documents as Word .docx files."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2docx import convert

REPO = "/Users/anu/Documents/brightmoney/brightmoney-repo"
OUT = os.path.join(REPO, "reports")

DOCS = [
    dict(
        md="TASK3_PRD.md",
        out="Task3a_PRD_KYC_Waterfall_v2.docx",
        title="KYC Verification Waterfall v2 - PRD",
        subtitle=("The waterfall that finishes running. 7.93% of applicants are not verified against a "
                  "5% bar, and half of that is applicants the waterfall simply stopped processing. "
                  "Thirteen requirements, three of them invariants, and a capacity-gated rollout."),
        eyebrow="Product Requirements Document  |  Owner: PM (KYC)  |  For: Backend, Integrations, Review Ops",
        skip_until="This document is self-contained",
    ),
    dict(
        md="TASK3_ARD.md",
        out="Task3b_ARD_Monitoring_Plan.docx",
        title="KYC Verification Waterfall v2 - ARD",
        subtitle=("Proving the waterfall works. Twenty metrics in four tiers, each with a numerator, a "
                  "denominator, a baseline and an alert threshold - three of them invariants, not KPIs, "
                  "plus the guardrails that prove we did not buy the rate by weakening a control."),
        eyebrow="Analytics Requirements & Monitoring Plan  |  Owner: Data & Analytics",
        skip_until="This document is self-contained",
    ),
    dict(
        md="TASK3_PROJECT_PLAN.md",
        out="Task3c_Project_Plan.docx",
        title="KYC Verification Waterfall v2 - Project Plan",
        subtitle=("We ramp at the speed of the queue. Ten workstreams over twenty-two weeks, "
                  "~8 additional review FTE, and a five-phase rollout - the critical path runs "
                  "through analyst hiring, not code."),
        eyebrow="Project Plan  |  Owner: PM (KYC)  |  ~10 wks build, ~12 wks ramp  |  For approval",
        skip_until="This document is self-contained",
    ),
]

if __name__ == "__main__":
  for d in DOCS:
    p = convert(os.path.join(REPO, d["md"]), os.path.join(OUT, d["out"]),
                d["title"], d["subtitle"], d["eyebrow"], skip_until=d["skip_until"])
    print("%-46s %7d bytes" % (os.path.basename(p), os.path.getsize(p)))

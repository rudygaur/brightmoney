# -*- coding: utf-8 -*-
"""Renders the three KYC Waterfall v2 build documents as PDFs.

Shares its document metadata with build_docx.py so both formats stay in sync.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2pdf import convert
from build_docx import DOCS, REPO, OUT

for d in DOCS:
    out = os.path.splitext(d["out"])[0] + ".pdf"
    p = convert(os.path.join(REPO, d["md"]), os.path.join(OUT, out),
                d["title"], d["subtitle"], d["eyebrow"], skip_until=d["skip_until"])
    print("%-46s %7d bytes" % (os.path.basename(p), os.path.getsize(p)))

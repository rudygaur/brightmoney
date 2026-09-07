# -*- coding: utf-8 -*-
"""Measures how tall each page sheet wants to be in the MEASURE build.

Renders the measure build at exactly one sheet-width, then finds each white sheet
by scanning a column that always falls inside the sheet's left padding. Prints the
natural height of every sheet against the 11in page box, so the zoom factors in
build_task1_combined.py are set from measurement, not guesswork.
"""
import os, subprocess, sys
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else "/tmp", "measure.png")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, PAGE = 900, 1056          # 900px window -> 816px (8.5in) sheet; 11in = 1056px

subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                "--window-size=%d,26000" % W, "--screenshot=" + SHOT,
                "--virtual-time-budget=9000",
                "file://" + os.path.join(REPO, "reports/task1_combined_MEASURE.html")],
               capture_output=True)

im = Image.open(SHOT).convert("RGB")
w, h = im.size
x = (w - 816) // 2 + 20                      # inside the sheet's 0.6in left padding
col = [im.getpixel((x, y)) for y in range(h)]

runs, start = [], None
for y, p in enumerate(col):
    white = p[0] > 246 and p[1] > 246 and p[2] > 246
    if white and start is None:
        start = y
    elif not white and start is not None:
        if y - start > 200:
            runs.append((start, y - start))
        start = None

print("%-6s %8s %8s   %s" % ("sheet", "height", "of 11in", "fit"))
for i, (y0, ht) in enumerate(runs, 1):
    r = ht / PAGE
    fit = "fits" if r <= 1.0 else "OVER by %d px  -> zoom %.2f" % (ht - PAGE, PAGE / ht)
    print("%-6d %8d %7.0f%%   %s" % (i, ht, r * 100, fit))
print("\n%d sheets found" % len(runs))

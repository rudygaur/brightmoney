# -*- coding: utf-8 -*-
"""Builds the four-slide Task 1 funnel deck: headline rate, causes, priorities.

Every figure is lifted from the two reviewed reports - reports/task1_rate_and_drivers.html
and reports/task1b_where_the_funnel_breaks.html - so nothing here is a fresh calculation.

Fonts: the report family uses Archivo / IBM Plex, which are webfonts and are NOT installed
on this machine or on most reviewers' machines - a .pptx cannot fall back, it substitutes
silently. So the deck is set in Arial / Arial Black, which render identically on Windows,
macOS and Google Slides. Mono label rows are Arial uppercase with letter-spacing instead of
Courier, which keeps the report's typographic voice without a dated typewriter face.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "reports", "task1_where_the_funnel_breaks.pptx")

# ---------------------------------------------------------------- palette
INK     = RGBColor(0x12, 0x16, 0x1D)
SOFT    = RGBColor(0x4C, 0x57, 0x68)
FAINT   = RGBColor(0x8A, 0x94, 0xA6)
ACCENT  = RGBColor(0x1D, 0x5A, 0xAD)
CRIT    = RGBColor(0xC9, 0x36, 0x36)
CRITSOF = RGBColor(0xF6, 0xDA, 0xDA)
WARN    = RGBColor(0xC9, 0x85, 0x00)
WARNSOF = RGBColor(0xFB, 0xF1, 0xDE)
PAPER   = RGBColor(0xF5, 0xF6, 0xF9)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
SURF2   = RGBColor(0xEE, 0xF0, 0xF4)
LINE    = RGBColor(0xDD, 0xE1, 0xE8)
NODE    = RGBColor(0x3A, 0x42, 0x56)

DISPLAY, BODY = "Arial Black", "Arial"
W, H = 13.333, 7.5
ML, MR = 0.62, 0.62
CW = W - ML - MR                     # content width

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers
def slide():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.055))
    plain(bar, ACCENT)
    return s


def plain(shape, fill, line=None, lw=0.75):
    """A rectangle with no preset shadow and, by default, no outline."""
    shape.shadow.inherit = False
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(lw)
    return shape


def box(s, l, t, w, h, fill=WHITE, line=LINE, radius=None):
    shp = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(l), Inches(t), Inches(w), Inches(h))
    if radius:
        shp.adjustments[0] = radius
    return plain(shp, fill, line)


def rule(s, l, t, w, color=LINE, weight=0.75):
    ln = s.shapes.add_connector(1, Inches(l), Inches(t), Inches(l + w), Inches(t))
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    return ln


def tf_of(s, l, t, w, h):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, first=False):
    return tf.paragraphs[0] if first else tf.add_paragraph()


def run(p, text, size, color=INK, bold=False, font=BODY, spc=None, italic=False):
    r = p.add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.italic = Pt(size), bold, italic
    r.font.name = font
    r.font.color.rgb = color
    if spc:
        r.font._rPr.set("spc", str(int(spc * 100)))
    return r


def text(s, l, t, w, h, chunks, size=11, color=SOFT, align=PP_ALIGN.LEFT,
         line_spacing=1.32, space_after=0, font=BODY, bold=False, spc=None):
    """chunks: a string, or a list of (text, {overrides}) for inline emphasis."""
    tf = tf_of(s, l, t, w, h)
    p = tf.paragraphs[0]
    p.alignment, p.line_spacing, p.space_after = align, line_spacing, Pt(space_after)
    if isinstance(chunks, str):
        chunks = [(chunks, {})]
    for txt, ov in chunks:
        run(p, txt,
            ov.get("size", size), ov.get("color", color), ov.get("bold", bold),
            ov.get("font", font), ov.get("spc", spc), ov.get("italic", False))
    return tf


def label(s, l, t, w, txt, color=ACCENT, size=9.5):
    return text(s, l, t, w, 0.22, txt.upper(), size=size, color=color, bold=True, spc=1.4)


def head(s, eyebrow, title, lede=None, tw=None):
    label(s, ML, 0.42, CW, eyebrow)
    text(s, ML, 0.70, CW, 0.5, title, size=25, color=INK, font=DISPLAY, line_spacing=1.06)
    if lede:
        text(s, ML, 1.30, tw or 10.4, 0.6, lede, size=11.5, color=SOFT, line_spacing=1.4)


def foot(s, txt):
    rule(s, ML, H - 0.62, CW)
    text(s, ML, H - 0.53, CW, 0.35, txt, size=8, color=FAINT, line_spacing=1.35)


def statnum(s, l, t, w, value, lab, sub, color=INK, align=PP_ALIGN.LEFT):
    text(s, l, t, w, 0.2, lab.upper(), size=8.5, color=FAINT, bold=True, spc=1.2, align=align)
    text(s, l, t + 0.22, w, 0.42, value, size=24, color=color, font=DISPLAY, align=align)
    text(s, l, t + 0.66, w, 0.3, sub, size=9, color=FAINT, align=align, line_spacing=1.3)


# ================================================================ SLIDE 1
s = slide()
label(s, ML, 0.42, CW, "Task 1 · Funnel analysis — the answer")
text(s, ML, 0.68, 11.0, 0.7, "7.93% of users never verify.",
     size=40, color=INK, font=DISPLAY, line_spacing=1.0)
text(s, ML, 1.42, 10.9, 0.7,
     [("The bar is 5%. We are ", {}), ("2.93 points over", {"bold": True, "color": INK}),
      (" it — ", {}), ("73,663 people", {"bold": True, "color": INK}),
      (" beyond budget. Three quarters of that loss is process, not risk: the waterfall "
       "stops before it finishes asking.", {})],
     size=12.5, color=SOFT, line_spacing=1.42)

# gauge — scale 0-10%, shaded panel = the 5% budget, full red bar = actual
GT, GL, GW, GH = 2.42, ML, CW, 0.40
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(GL), Inches(GT), Inches(GW), Inches(GH)), SURF2)
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(GL), Inches(GT), Inches(GW * 0.500), Inches(GH)), CRITSOF)
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(GL + GW * 0.500), Inches(GT),
                         Inches(GW * 0.293), Inches(GH)), CRIT)
text(s, GL + 0.16, GT + 0.11, 4.0, 0.22, "WITHIN THE 5% BUDGET — 125,758 USERS",
     size=9, color=CRIT, bold=True, spc=1.1)
text(s, GL + GW * 0.500 + 0.16, GT + 0.11, 3.6, 0.22, "OVER — 73,663 USERS",
     size=9, color=WHITE, bold=True, spc=1.1)
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                         Inches(GL + GW * 0.500 - 0.008), Inches(GT - 0.09),
                         Inches(0.016), Inches(GH + 0.18)), NODE)
text(s, GL + GW * 0.500 - 1.3, GT + GH + 0.14, 1.24, 0.2, "5.00%",
     size=10.5, color=NODE, bold=True, align=PP_ALIGN.RIGHT)
text(s, GL + GW * 0.500 - 1.3, GT + GH + 0.32, 1.24, 0.2, "acceptable bar",
     size=8.5, color=FAINT, align=PP_ALIGN.RIGHT)
text(s, GL + GW * 0.793 - 1.3, GT + GH + 0.14, 1.24, 0.2, "7.93%",
     size=10.5, color=CRIT, bold=True, align=PP_ALIGN.RIGHT)
text(s, GL + GW * 0.793 - 1.3, GT + GH + 0.32, 1.24, 0.2, "observed",
     size=8.5, color=FAINT, align=PP_ALIGN.RIGHT)
text(s, GL + GW - 0.9, GT + GH + 0.14, 0.9, 0.2, "10%", size=8.5, color=FAINT, align=PP_ALIGN.RIGHT)

# three tiles
TT, TW = 3.62, (CW - 0.36) / 3
for i, (val, lab, sub, col) in enumerate([
        ("199,421", "Not verified", "of 2,515,155 enrolled users", CRIT),
        ("125,758", "Budget at 5%", "what the bar allows", INK),
        ("73,663",  "Over budget",  "the size of the job", CRIT)]):
    l = ML + i * (TW + 0.18)
    box(s, l, TT, TW, 1.16, WHITE, LINE, radius=0.06)
    statnum(s, l + 0.24, TT + 0.19, TW - 0.48, val, lab, sub, color=col)

# steady state
ST = 5.06
box(s, ML, ST, CW, 1.30, SURF2, None, radius=0.05)
label(s, ML + 0.24, ST + 0.18, 6.0, "Not a regression — steady state", color=SOFT, size=9)
BX, BW = ML + 0.24, 3.5
for i, (yr, rate, frac) in enumerate([("2023", "7.97%", .797), ("2024", "7.89%", .789),
                                      ("2025", "7.93%", .793), ("2026", "7.93%", .793)]):
    y = ST + 0.48 + i * 0.185
    text(s, BX, y - 0.015, 0.42, 0.16, yr, size=8.5, color=FAINT, bold=True, spc=0.8)
    plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(BX + 0.46), Inches(y), Inches(BW), Inches(0.10)), LINE)
    plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(BX + 0.46), Inches(y),
                             Inches(BW * frac), Inches(0.10)), NODE)
    plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(BX + 0.46 + BW * 0.5 - 0.006),
                             Inches(y - 0.035), Inches(0.012), Inches(0.17)), ACCENT)
    text(s, BX + 0.46 + BW + 0.14, y - 0.045, 0.6, 0.16, rate, size=9, color=INK, bold=True)
text(s, ML + 5.4, ST + 0.46, CW - 5.9, 0.8,
     [("Across all 41 months on record the rate stays between 7.67% and 8.22%, and between "
       "7.89% and 7.97% in every year. ", {}),
      ("Nothing broke.", {"bold": True, "color": INK}),
      (" This is steady-state design behaviour — it will not fix itself, and a rollback has "
       "nothing to roll back to.", {})],
     size=10.5, color=SOFT, line_spacing=1.4)

foot(s, "Denominator 2,515,155 = all enrolled users less 107 flagged Test_user QA accounts (flagged, never deleted).   ·   "
        "kyc_source is null for 197,314 users, almost all unverified. Kept in: the field names the provider that CLEARED a user, "
        "so it is null precisely when nobody did — dropping those rows would report 0.09% instead of 7.93%.")


# ================================================================ SLIDE 2
s = slide()
head(s, "Breaking down the causes", "Three quarters of it is process, not risk",
     "Genuine rejection and avoidable loss look identical in the outcome field. They separate on how much "
     "assessment the user actually received before the system said no — which is recorded, check by check, "
     "for every row. Every non-verified user falls into exactly one of four buckets.", tw=11.6)

# stacked bar, to scale across all 199,421
SBT, SBH = 2.06, 0.46
segs = [("A", 0.0042, NODE, ""), ("B", 0.5081, CRIT, "B · 50.8%"),
        ("C", 0.2437, WARN, "C · 24.4%"), ("D", 0.2440, SOFT, "D · 24.4%")]
x = ML
for key, frac, col, lab in segs:
    w = CW * frac
    plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(SBT), Inches(w), Inches(SBH)), col)
    if lab:
        text(s, x, SBT + 0.13, w, 0.24, lab, size=10, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    x += w
# brace row
for lab, frac, off, col in [("Avoidable — 51.2%", 0.5123, 0.0, CRIT),
                            ("Partly avoidable — 24.4%", 0.2437, 0.5123, WARN),
                            ("Genuine — 24.4%", 0.2440, 0.7560, SOFT)]:
    l, w = ML + CW * off, CW * frac
    plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(l), Inches(SBT + SBH + 0.07),
                             Inches(w), Inches(0.028)), col)
    text(s, l, SBT + SBH + 0.15, w, 0.22, lab.upper(), size=8.5, color=col, bold=True,
         spc=1.0, align=PP_ALIGN.CENTER)

# bucket table
TT = 3.02
cols = [(ML, 2.55), (ML + 2.70, 6.35), (ML + 9.25, 1.30), (ML + 10.70, 1.39)]
for (l, w), hd, al in zip(cols, ["Bucket — how far it got", "What it means", "Users", "Share"],
                          [PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT]):
    text(s, l, TT, w, 0.2, hd.upper(), size=8.5, color=FAINT, bold=True, spc=1.0, align=al)
rule(s, ML, TT + 0.24, CW)

rows = [(NODE, "A · Never started", "Enrolled, not one check of any kind ever ran. Zero verified.", "843", "0.4%"),
        (CRIT, "B · One check, stopped", "A single check ran and the waterfall halted. No secondary provider, no human.", "101,325", "50.8%"),
        (WARN, "C · Automated only", "Two or more automated checks failed, but the case never reached a reviewer — though the design says it should have.", "48,598", "24.4%"),
        (SOFT, "D · Fully assessed", "Multiple providers AND a human analyst. Still declined.", "48,655", "24.4%")]
y = TT + 0.36
for col, name, meaning, users, share in rows:
    plain(s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cols[0][0]), Inches(y + 0.055),
                             Inches(0.10), Inches(0.10)), col)
    text(s, cols[0][0] + 0.19, y, cols[0][1] - 0.19, 0.24, name, size=10.5, color=INK, bold=True)
    text(s, cols[1][0], y, cols[1][1], 0.4, meaning, size=10, color=SOFT, line_spacing=1.3)
    text(s, cols[2][0], y, cols[2][1], 0.24, users, size=10.5, color=INK, bold=True, align=PP_ALIGN.RIGHT)
    text(s, cols[3][0], y, cols[3][1], 0.24, share, size=10.5, color=SOFT, align=PP_ALIGN.RIGHT)
    y += 0.50
    rule(s, ML, y - 0.10, CW)
text(s, cols[0][0], y, 3.0, 0.24, "Total not verified", size=10.5, color=INK, bold=True)
text(s, cols[2][0], y, cols[2][1], 0.24, "199,421", size=10.5, color=INK, bold=True, align=PP_ALIGN.RIGHT)
text(s, cols[3][0], y, cols[3][1], 0.24, "100%", size=10.5, color=SOFT, align=PP_ALIGN.RIGHT)

VT = y + 0.44
VH = 0.86
box(s, ML, VT, CW, VH, WHITE, LINE, radius=0.10)
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(ML), Inches(VT), Inches(0.05), Inches(VH)), CRIT)
text(s, ML + 0.26, VT + 0.16, CW - 0.55, 0.6,
     [("75.6%", {"bold": True, "color": CRIT, "size": 12.5}),
      (" of non-verification — buckets A, B and C, 150,766 users — is the waterfall failing to finish, "
       "not a correct decision. Only bucket D, just under a quarter, is the system doing its job. ", {}),
      ("Bucket C is the honest middle", {"bold": True, "color": INK}),
      (": those users did fail two or more checks, but the design routes anyone who fails everything to "
       "a human, and these never got there — so it is sized conservatively, not claimed in full.", {})],
     size=10, color=SOFT, line_spacing=1.32)

foot(s, "Bucket boundary uses checks_run, verified against the count of populated provider columns on every row; "
        "the two disagree only where manual review ran, with no unexplained cases.   ·   "
        "Bucket B is almost entirely one thing: 101,159 users who failed Idology and had nothing else run at all.")


# ================================================================ SLIDE 3
s = slide()
head(s, "Highest leverage", "The three problems worth fixing, in order",
     "Ranked by recoverable users per unit of change, and by how little control has to be given up to get them.",
     tw=11.0)

CT, CH2 = 1.72, 5.02
CDW = (CW - 0.44) / 3
cards = [
    (CRIT, "1", "The waterfall stops after one check",
     [("101,162 users failed Idology and no second check ever ran — ", {}),
      ("50.8% of every non-verification in the book", {"bold": True, "color": INK}),
      (". The single largest cause by a wide margin, and the cheapest to fix, because it is a "
       "routing defect rather than a risk decision.", {})],
     [("Affected", "101,162", INK), ("Recovery today", "0.00%", CRIT),
      ("Comparable routed users", "48.09%", INK), ("Recoverable", "~48,647", ACCENT)],
     "Why first:", "It costs provider calls, not control strength — no threshold moves, no check is weakened, "
     "nobody who should be rejected gets through. Stranding is uniform across every partner "
     "(35.1 / 35.2 / 36.0 / 35.9%) and every year, so one fix addresses all of it."),
    (WARN, "2", "Manual review is under-triggered",
     [("53,312 users failed two or more automated checks and never reached a human, though the design says "
       "they should have. Where a human ", {}), ("does", {"italic": True}),
      (" see a comparable case the outcome is measurably better.", {})],
     [("Missed the human", "53,312", INK), ("Verified without review", "10.44%", CRIT),
      ("Verified with review", "17.84%", INK), ("Recoverable", "~3,945", ACCENT)],
     "Sized honestly:", "The recoverable figure is the incremental 7.40-point lift, not review's headline 32.30% "
     "clear rate — crediting that would double-count users who already verify by other means. Bounded by analyst "
     "capacity, so it needs a triage rule, not “send everything.”"),
    (ACCENT, "3", "Persona IDV is barely deployed, and it works",
     [("Document-and-selfie verification runs on ", {}),
      ("0.87% of Idology failures", {"bold": True, "color": INK}),
      (" — 2,507 users out of 288,028. It directly targets the name, DOB and address mismatches the cheaper "
       "automated checks cannot resolve.", {})],
     [("Deployment", "0.87%", CRIT), ("With Persona-IDV", "86.32%", INK),
      ("Without", "30.72%", INK), ("Confidence", "Directional", WARN)],
     "Read this one carefully:", "The 86% is heavily selected — IDV is offered to users someone already expected "
     "to complete it, so the gap overstates the causal lift and I put no recovery number on it. It is also the "
     "highest-friction, highest-cost check, so it belongs last in the waterfall."),
]
for i, (col, num, title, blurb, metrics, why_lab, why) in enumerate(cards):
    l = ML + i * (CDW + 0.22)
    box(s, l, CT, CDW, CH2, WHITE, LINE, radius=0.045)
    plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(l), Inches(CT), Inches(CDW), Inches(0.055)), col)
    pad = 0.28
    iw = CDW - 2 * pad
    badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(l + pad), Inches(CT + 0.30), Inches(0.34), Inches(0.34))
    plain(badge, col)
    text(s, l + pad, CT + 0.365, 0.34, 0.26, num, size=13, color=WHITE, font=DISPLAY, align=PP_ALIGN.CENTER)
    text(s, l + pad, CT + 0.74, iw, 0.6, title, size=14.5, color=INK, font=DISPLAY, line_spacing=1.14)
    text(s, l + pad, CT + 1.42, iw, 1.2, blurb, size=10, color=SOFT, line_spacing=1.38)

    my = CT + 2.50
    rule(s, l + pad, my - 0.12, iw)
    for k, v, vc in metrics:
        text(s, l + pad, my, iw * 0.62, 0.22, k, size=9.5, color=FAINT)
        text(s, l + pad + iw * 0.55, my - 0.015, iw * 0.45, 0.22, v, size=11, color=vc,
             bold=True, align=PP_ALIGN.RIGHT)
        my += 0.285
        rule(s, l + pad, my - 0.085, iw)

    wy = my + 0.12
    box(s, l + pad, wy, iw, CT + CH2 - wy - 0.22, SURF2, None, radius=0.06)
    text(s, l + pad + 0.16, wy + 0.13, iw - 0.32, 1.1,
         [(why_lab + " ", {"bold": True, "color": INK}), (why, {})],
         size=9, color=SOFT, line_spacing=1.34)

foot(s, "Recovery figures are projections from an observed comparison group, not experiments — the honest confirmation "
        "is to route a sample and measure. Sizing, not a commitment.   ·   Routing figures use the 288,028 Idology failures.")


# ================================================================ SLIDE 4
s = slide()
head(s, "What it adds up to", "Fixing one and two gets most of the way there",
     "Neither change weakens a control, moves a threshold, or lets through anybody who should be rejected. "
     "Both cost provider calls and analyst capacity, not risk appetite.", tw=11.0)

TT = 1.84
for l, w, hd, al in [(ML + 0.28, 7.7, "Change", PP_ALIGN.LEFT),
                     (ML + 8.3, 1.8, "Users", PP_ALIGN.RIGHT),
                     (ML + 10.35, 1.7, "Rate", PP_ALIGN.RIGHT)]:
    text(s, l, TT, w, 0.2, hd.upper(), size=8.5, color=FAINT, bold=True, spc=1.0, align=al)

steps = [(WHITE, "Today", " — 199,421 users not verified", "", "7.93%", CRIT),
         (WHITE, "Route every Idology failure onward.",
          "  Applies the observed 48.09% recovery rate to the stranded users.", "−48,647", "5.99%", INK),
         (WHITE, "Triage the 2+-failure cases to review.",
          "  53,312 users who failed two or more automated checks never reached a human.", "−3,945", "5.84%", INK),
         (SURF2, "Remaining gap to the 5% bar", " — 21,071 users", "0.84 pp", "5.00%", ACCENT)]
y = TT + 0.30
for fill, bold_part, rest, delta, rate, rc in steps:
    box(s, ML, y, CW, 0.62, fill, LINE, radius=0.05)
    text(s, ML + 0.28, y + 0.19, 7.7, 0.34,
         [(bold_part, {"bold": True, "color": INK}), (rest, {})], size=10.5, color=SOFT,
         line_spacing=1.24)
    text(s, ML + 8.3, y + 0.19, 1.8, 0.3, delta, size=11.5, color=SOFT, align=PP_ALIGN.RIGHT)
    text(s, ML + 10.35, y + 0.15, 1.7, 0.34, rate, size=16, color=rc, font=DISPLAY, align=PP_ALIGN.RIGHT)
    y += 0.70

text(s, ML, y + 0.06, CW, 0.5,
     [("Routing alone moves 7.93% to roughly 6.0%", {"bold": True, "color": INK}),
      (" — two-thirds of the gap, nothing loosened. The last 0.84 points has to come from the redesign "
       "in Task 2, and Problem 3 is where it most plausibly lives.", {})],
     size=11.5, color=SOFT, line_spacing=1.4)

NT = y + 0.54
NH = 1.14
NW = (CW - 0.24) / 2
box(s, ML, NT, NW, NH, WHITE, LINE, radius=0.05)
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(ML), Inches(NT), Inches(0.045), Inches(NH)), WARN)
text(s, ML + 0.26, NT + 0.18, NW - 0.5, 0.24, "These are projections, not experiments",
     size=10.5, color=INK, bold=True)
text(s, ML + 0.26, NT + 0.44, NW - 0.5, 0.8,
     "They assume stranded users behave like routed users who failed the same check — defensible because "
     "stranding is uniform across every partner and year, but no secondary check ever ran on the stranded "
     "group, so there is nothing to measure against. Route a sample and confirm.",
     size=9, color=SOFT, line_spacing=1.32)

box(s, ML + NW + 0.24, NT, NW, NH, WHITE, LINE, radius=0.05)
plain(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(ML + NW + 0.24), Inches(NT), Inches(0.045), Inches(NH)), NODE)
text(s, ML + NW + 0.50, NT + 0.18, NW - 0.5, 0.24,
     "The big category I am deliberately not chasing", size=10.5, color=INK, bold=True)
text(s, ML + NW + 0.50, NT + 0.44, NW - 0.5, 0.8,
     [("SSN mismatches — 13,266 flagged cases. Largest named rejection reason in the reviewer comments, so it "
       "looks like a target. Of those, ", {}),
      ("18 cleared manual review — 0.136%", {"bold": True, "color": INK}),
      (". A control a human upholds 99.9% of the time is working; weakening it to buy a few hundred users is "
       "the wrong trade.", {})],
     size=9, color=SOFT, line_spacing=1.32)

foot(s, "All figures re-queried live against kyc.kyc_users (2,515,262 rows, 11 validation gates, less 107 test accounts).   ·   "
        "Companions: The Waterfall As Built (reconstruction) and The Waterfall, Rebuilt (Task 2 redesign).")

prs.save(OUT)
print("wrote %s  (%d slides, %d bytes)" % (OUT, len(prs.slides.__iter__.__self__._sldIdLst), os.path.getsize(OUT)))

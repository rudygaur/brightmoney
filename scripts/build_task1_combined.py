# -*- coding: utf-8 -*-
"""Merges two existing Task 1 reports into one paginated HTML file, content unchanged.

Part 1  = 'The Waterfall As Built' sections, reordered to the deck's slide sequence
          (slide 1 - the title card - dropped), plus the data-caveats section that
          closes the deck.
Part 2  = 'The 7.93% Problem' (task1_rate_and_drivers.html), verbatim.

Both parts render as Letter-proportioned page sheets. Part 2 already carried that
chrome in its own stylesheet; Part 1's sections are dropped into a matching sheet
built in a neutral namespace, so no rule from one document can reach the other.

Both stylesheets are namespaced (.doc-a / .doc-b) because they use the same custom
property NAMES with different VALUES. No markup text is edited anywhere.

  MEASURE=1 python3 scripts/build_task1_combined.py   ->  sheets grow to fit their
  content instead of being clipped, so scripts/measure_pages.py can size them.
"""
import re, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(REPO, "reports")
MEASURE = bool(os.environ.get("MEASURE"))


def split(path):
    s = open(os.path.join(R, path), encoding="utf-8").read()
    a, b = s.index("<style>"), s.index("</style>")
    return s[a + 7:b], s[b + 8:]


# --------------------------- CSS namespacing ---------------------------
def _blocks(css):
    """Yield (prelude, body_or_None) for each top-level rule/at-rule."""
    out, buf, depth, i = [], "", 0, 0
    while i < len(css):
        c = css[i]
        if c == "{":
            if depth == 0:
                prelude, start = buf, i + 1
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                out.append((prelude, css[start:i]))
                buf = ""
                i += 1
                continue
        elif depth == 0 and c == ";":
            out.append((buf + ";", None)); buf = ""; i += 1; continue
        if depth == 0:
            buf += c
        i += 1
    if buf.strip():
        out.append((buf, None))
    return out


def _sel(sel, ns):
    sel = sel.strip()
    if not sel:
        return sel
    if sel == "html":
        return None                                   # hoisted globally
    if sel == "*":
        return ".%s, .%s *" % (ns, ns)
    if sel == "body":
        return ".%s" % ns
    if sel.startswith("body "):
        return ".%s %s" % (ns, sel[5:])
    if sel.startswith(":root"):
        m = re.match(r"^(:root[^\s>+~]*)(.*)$", sel)
        return "%s .%s%s" % (m.group(1), ns, m.group(2))
    return ".%s %s" % (ns, sel)


def scope(css, ns):
    out = []
    for prelude, body in _blocks(css):
        # comments ride along in the prelude; emit them separately so they can never
        # end up glued to the front of an at-rule.
        for c in re.findall(r"/\*.*?\*/", prelude, re.S):
            out.append(c)
        p = re.sub(r"/\*.*?\*/", " ", prelude, flags=re.S).strip()
        if body is None:
            out.append(p)
            continue
        if p.startswith("@media") or p.startswith("@supports"):
            out.append("%s{\n%s\n}" % (p, scope(body, ns)))
        elif p.startswith("@page") or p.startswith("@font-face") or p.startswith("@keyframes"):
            out.append("%s{%s}" % (p, body))
        else:
            sels = [x for x in (_sel(y, ns) for y in p.split(",")) if x]
            if sels:
                out.append("%s{%s}" % (", ".join(sels), body))
    return "\n".join(out)


# --------------------------- source material ---------------------------
css_a, body_a = split("task1a_the_waterfall_as_built.html")
css_b, body_b = split("task1_rate_and_drivers.html")
css_c, body_c = split("task1b_where_the_funnel_breaks.html")

secs_a = re.findall(r"<section>.*?</section>", body_a, re.S)
BY = lambda frag: next(s for s in secs_a if frag in s)

entry   = BY("Where users enter the waterfall")
routing = BY("How users route between the SSN and non-SSN paths")
lexis   = BY("The two LexisNexis routes are not the same check")
inv     = BY("Which checks fire, and how often")
summary = BY("Documented design vs the system that runs")
caveats = next(s for s in re.findall(r"<section>.*?</section>", body_c, re.S)
               if "Data caveats, and how each was handled" in s)

# the deck's header block, kept for its denominator table only: the title card is
# dropped per the deck, and the scope-note paragraph described a section order this
# document no longer uses.
mast = re.search(r"<header class=\"masthead\">(.*?)</header>", body_a, re.S).group(1)
denom = re.search(r"<table class=\"scope-table\">.*?</table>", mast, re.S).group(0)

# .caveat rules live in task1b's sheet only - lift them into the Part 1 namespace
cav_css = css_c[css_c.index("/* ---------------- caveats"):]
cav_css = cav_css[:cav_css.index("footer{")]

deck = re.search(r"<div class=\"deck\">.*</div>", body_b, re.S).group(0)


# --------------------------- Part 1 pagination ---------------------------
RUNHEAD = "Task 1 · Part A — the waterfall as built"

def sheet(inner, n, total, zoom=None):
    z = "" if not zoom else ' style="zoom:%s"' % zoom
    return (
        '<section class="mx-sheet">\n'
        '  <div class="mx-rule"><span class="d">%s</span>'
        '<span class="f">Page %d / %d</span></div>\n'
        '  <div class="mx-body"%s><div class="doc-a">%s</div></div>\n'
        '</section>' % (RUNHEAD, n, total, z, inner)
    )

# One section per page, in the deck's order. The denominator table opens page 1.
# The zoom column is measured, not guessed: scripts/measure_pages.py reports each
# sheet's natural height, and only the one section that will not fit an 11in page
# at full size is scaled - see its note below.
PAGES = [
    ('<div class="mx-scope">%s</div>' % denom + entry, None),   # 93% of the page
    (routing,       None),   # 74%
    (lexis,         None),   # 80%
    (inv,           None),   # 79%
    (summary,       0.90),   # 108% at full size - the only page that needs scaling
    (caveats,       None),   # 78%
]
part1 = "\n".join(sheet(inner, i + 1, len(PAGES), z)
                  for i, (inner, z) in enumerate(PAGES))


# --------------------------- assemble ---------------------------
SHELL = """<title>Task 1 — The Waterfall As Built, and the 7.93% Problem</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
/* ==================================================================
   COMBINED TASK 1 REPORT
   Part 1 and Part 2 are two previously separate documents. Each keeps
   its own stylesheet, namespaced to .doc-a / .doc-b, because both use
   the same custom-property NAMES with different VALUES. Nothing in the
   markup of either was edited.
   ================================================================== */

/* ---- global shell (the only unscoped rules) ---- */
*{ box-sizing:border-box; }
html{ -webkit-text-size-adjust:100%; }
body{ margin:0; background:#e9ebf0; }
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]) body{ background:#0a0c11; } }
:root[data-theme="dark"] body{ background:#0a0c11; }

/* ==================================================================
   PAGE CHROME for Part 1 — a neutral namespace holding the same sheet
   geometry Part 2's own stylesheet already defines, so the two parts
   paginate identically without either stylesheet reaching the other.
   ================================================================== */
.mx-deck{
  --mx-ink:#12161d; --mx-faint:#8a94a6; --mx-surface:#ffffff;
  --mx-line:#dde1e8; --mx-accent:#1d5aad;
  --mx-shadow: 0 1px 2px rgba(18,22,29,.04), 0 10px 30px -14px rgba(18,22,29,.22);
  display:flex; flex-direction:column; align-items:center; gap:26px; padding:0 16px 26px;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]) .mx-deck{
    --mx-ink:#eef1f6; --mx-faint:#77839a; --mx-surface:#171b24;
    --mx-line:#2a3040; --mx-accent:#5b98e6;
    --mx-shadow: 0 1px 2px rgba(0,0,0,.3), 0 10px 30px -14px rgba(0,0,0,.6);
  }
}
:root[data-theme="dark"] .mx-deck{
  --mx-ink:#eef1f6; --mx-faint:#77839a; --mx-surface:#171b24;
  --mx-line:#2a3040; --mx-accent:#5b98e6;
  --mx-shadow: 0 1px 2px rgba(0,0,0,.3), 0 10px 30px -14px rgba(0,0,0,.6);
}
.mx-sheet{
  width:100%; max-width:8.5in; aspect-ratio:8.5/11;
  background:var(--mx-surface); border:1px solid var(--mx-line); border-radius:3px;
  box-shadow:var(--mx-shadow); padding:0.52in 0.6in 0.44in;
  display:flex; flex-direction:column;
}
@media (max-width:820px){ .mx-sheet{ aspect-ratio:auto; padding:30px 22px; } }
.mx-rule{ display:flex; align-items:baseline; justify-content:space-between; gap:16px;
  border-bottom:1px solid var(--mx-line); padding-bottom:7px; flex:none; }
.mx-rule .d{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:9.5px;
  font-weight:500; letter-spacing:.15em; text-transform:uppercase; color:var(--mx-faint); }
.mx-rule .f{ font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:9.5px;
  font-weight:600; letter-spacing:.1em; color:var(--mx-accent); white-space:nowrap; }
.mx-body{ flex:1 1 auto; min-height:0; padding-top:20px; }

/* Part 1's sections were written to flow down a continuous page. These rules only
   change how they are FRAMED - they strip the standalone document's own page
   furniture (its own background, gutters, section rules) so the sheet supplies it. */
.mx-body .doc-a{ background:none; }
.mx-body .doc-a .wrap{ max-width:none; margin:0; padding:0; }
.mx-body .doc-a section{ padding:0; border-bottom:none; }
.mx-body .doc-a header.masthead{ padding:0 0 26px; margin-bottom:26px; }
.mx-body .doc-a .scope-table{ margin-top:0; max-width:none; }
/* the denominator table opens page 1; a rule keeps it distinct from the section under it */
.mx-scope{ padding-bottom:20px; margin-bottom:26px; border-bottom:1px solid var(--mx-line); }
.mx-body .doc-a .fig-frame{ overflow-x:visible; }
.mx-body .doc-a .fig-frame svg{ min-width:0; }
/* A page body is ~200px narrower than the standalone document's column, so three
   places that were comfortable there need the space returned: the inventory table's
   right-hand columns, and the two provider cards, whose rows only line up if both
   verdict headings reserve the same height. */
.mx-body .doc-a .inv thead th + th,
.mx-body .doc-a .inv tbody td + td{ padding-left:20px; }
.mx-body .doc-a .inv .fire-track{ width:70px; }
.mx-body .doc-a .ln-verdict{ min-height:3.2em; }

/* ---- part divider ---- */
.mx-part{
  max-width:8.5in; margin:0 auto; padding:52px 16px 26px;
  font-family:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,sans-serif;
}
.mx-part .mx-num{
  font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace; font-size:11px; font-weight:600;
  letter-spacing:.16em; text-transform:uppercase; color:#1d5aad; display:block;
}
.mx-part .mx-q{
  font-family:'Archivo',"Arial Narrow",sans-serif; font-weight:800; letter-spacing:-.01em;
  font-size:clamp(21px,3.1vw,29px); line-height:1.22; margin:10px 0 0; color:#12161d;
  text-wrap:balance;
}
.mx-part hr{ border:none; border-top:2px solid #1d5aad; margin:0 0 18px; width:56px; }
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]) .mx-part .mx-q{ color:#eef1f6; }
  :root:not([data-theme="light"]) .mx-part .mx-num{ color:#5b98e6; }
  :root:not([data-theme="light"]) .mx-part hr{ border-top-color:#5b98e6; }
}
:root[data-theme="dark"] .mx-part .mx-q{ color:#eef1f6; }
:root[data-theme="dark"] .mx-part .mx-num{ color:#5b98e6; }
:root[data-theme="dark"] .mx-part hr{ border-top-color:#5b98e6; }

/* ---- print: one sheet per physical page, both parts alike ---- */
@media print{
  .mx-deck{ display:block; padding:0; gap:0; }
  .mx-sheet{ max-width:none; width:100%; height:11in; aspect-ratio:auto;
    border:none; border-radius:0; box-shadow:none; break-after:page; page-break-after:always; }
  .mx-part{ max-width:none; padding:0.6in 0.6in 0; break-after:page; page-break-after:always; }
}
@@MEASURE@@

/* ================= PART 1 stylesheet, namespaced ================= */
@@CSS_A@@

/* ---- caveat rules, lifted from the companion sheet they came from ---- */
@@CAV@@

/* ================= PART 2 stylesheet, namespaced ================= */
@@CSS_B@@
</style>

<div class="mx-part">
  <hr>
  <span class="mx-num">Question 1</span>
  <h2 class="mx-q">Reconstruct how the waterfall runs today: which checks fire, in what
    order, and how users route between the SSN and non-SSN paths.</h2>
</div>

<div class="mx-deck">
@@PART1@@
</div>

<div class="mx-part">
  <hr>
  <span class="mx-num">Question 2</span>
  <h2 class="mx-q">Measure the overall non-verification rate and compare it to the 5% bar.
    Diagnose the drivers — separate genuine rejections from avoidable losses, and quantify
    the largest of each.</h2>
</div>

<div class="doc-b">
@@DECK@@
</div>
"""

MEASURE_CSS = """
/* MEASURE BUILD - sheets grow to their content so page fit can be measured. */
.mx-sheet, .doc-b .sheet{ aspect-ratio:auto !important; }
"""

subs = dict(
    CSS_A=scope(css_a, "doc-a"),
    CAV=scope(cav_css, "doc-a"),
    CSS_B=scope(css_b, "doc-b"),
    PART1=part1,
    DECK=deck,
    MEASURE=MEASURE_CSS if MEASURE else "",
)
html = SHELL
for k, v in subs.items():
    html = html.replace("@@%s@@" % k, v)

name = "task1_combined_MEASURE.html" if MEASURE else "task1_combined_waterfall_and_drivers.html"
out = os.path.join(R, name)
open(out, "w", encoding="utf-8").write(html)
print("wrote %s  (%d bytes)" % (out, len(html)))

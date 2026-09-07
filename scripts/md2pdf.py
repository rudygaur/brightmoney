# -*- coding: utf-8 -*-
"""Markdown -> print-styled HTML -> PDF (Chrome headless).

Same source-of-truth .md files and the same design tokens as md2docx.py, so the
.docx and .pdf deliverables stay visually consistent.
"""
import html as _html
import os
import re
import shutil
import subprocess
import tempfile
import time

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ACCENT, ACCENT_D = "#0b5d66", "#084a52"
INK, MUTED, CRIT = "#131a1c", "#5a686c", "#a63a32"
HDR_FILL, ZEBRA, RULE = "#eaf1f1", "#f8fafa", "#dbe4e5"

CSS = f"""
@page {{ size: Letter; margin: 16mm 14mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Calibri, "Helvetica Neue", Arial, sans-serif; color: {INK};
        font-size: 9.6pt; line-height: 1.45; margin: 0; }}
.cover {{ break-after: page; padding-top: 52mm; }}
.cover .eyebrow {{ font-size: 8.2pt; letter-spacing: .09em; text-transform: uppercase;
        color: {ACCENT}; font-weight: 700; margin-bottom: 10mm; }}
.cover h1 {{ font-size: 30pt; line-height: 1.12; margin: 0 0 6mm; color: {ACCENT_D};
        letter-spacing: -.01em; }}
.cover .rule {{ width: 26mm; height: 3px; background: {ACCENT}; margin: 0 0 6mm; }}
.cover .sub {{ font-size: 12pt; line-height: 1.5; color: {MUTED}; max-width: 135mm; }}
h2 {{ font-size: 15pt; color: {ACCENT_D}; margin: 9mm 0 2.5mm; padding-bottom: 1.6mm;
      border-bottom: 1.5px solid {ACCENT}; break-after: avoid; letter-spacing: -.005em; }}
h3 {{ font-size: 11.6pt; color: {ACCENT_D}; margin: 6mm 0 2mm; break-after: avoid; }}
h4 {{ font-size: 10.2pt; color: {INK}; margin: 5mm 0 1.5mm; break-after: avoid; }}
p {{ margin: 0 0 2.6mm; }}
ul, ol {{ margin: 0 0 2.8mm; padding-left: 6.5mm; }}
li {{ margin-bottom: 1.2mm; }}
li > ul, li > ol {{ margin: 1.2mm 0 0; }}
a {{ color: {ACCENT}; text-decoration: none; border-bottom: .5px solid {ACCENT}; }}
code {{ font-family: Consolas, "SF Mono", Menlo, monospace; font-size: .9em; color: {ACCENT_D};
        background: {ZEBRA}; padding: .3mm 1mm; border-radius: 2px; }}
pre {{ font-family: Consolas, "SF Mono", Menlo, monospace; font-size: 6.6pt; line-height: 1.28;
       background: {ZEBRA}; border: .5px solid {RULE}; border-left: 2.5px solid {ACCENT};
       padding: 3mm 3.5mm; margin: 0 0 3.5mm; white-space: pre; overflow: hidden;
       break-inside: avoid; }}
blockquote {{ margin: 0 0 3.2mm; padding: 2.6mm 4mm; background: {ZEBRA};
       border-left: 2.5px solid {ACCENT}; break-inside: avoid; }}
blockquote p:last-child {{ margin-bottom: 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 0 0 4mm; font-size: 8.4pt; }}
thead th {{ background: {HDR_FILL}; color: {ACCENT_D}; font-weight: 700; text-align: left;
       border-bottom: 1.2px solid {ACCENT}; }}
th, td {{ padding: 1.5mm 2mm; vertical-align: top; border-bottom: .5px solid {RULE}; }}
tbody tr:nth-child(even) {{ background: {ZEBRA}; }}
tr {{ break-inside: avoid; }}
thead {{ display: table-header-group; }}
td.r, th.r {{ text-align: right; }}
td.c, th.c {{ text-align: center; }}
hr {{ border: 0; border-top: .5px solid {RULE}; margin: 6mm 0; }}
strong {{ font-weight: 700; }}
"""

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]*\)|(?<!\*)\*(?!\*)[^*]+\*(?!\*))")


def inline(text):
    text = text.replace("\\*", "").replace("<br>", " ")
    out = []
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append("<strong>%s</strong>" % _html.escape(part[2:-2]))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append("<code>%s</code>" % _html.escape(part[1:-1]))
        elif part.startswith("[") and "](" in part:
            label = part[1:part.index("](")]
            href = part[part.index("](") + 2:-1]
            out.append('<a href="%s">%s</a>' % (_html.escape(href), _html.escape(label)))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append("<em>%s</em>" % _html.escape(part[1:-1]))
        else:
            out.append(_html.escape(part))
    return "".join(out)


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def align_classes(sep_cells):
    cls = []
    for c in sep_cells:
        c = c.strip()
        if c.startswith(":") and c.endswith(":"):
            cls.append(" class=\"c\"")
        elif c.endswith(":"):
            cls.append(" class=\"r\"")
        else:
            cls.append("")
    return cls


def render(md_lines):
    out, i, n = [], 0, len(md_lines)
    list_stack = []  # (tag, indent)

    def close_lists(to_indent=-1):
        while list_stack and list_stack[-1][1] > to_indent:
            out.append("</%s>" % list_stack.pop()[0])

    while i < n:
        raw = md_lines[i].rstrip()
        s = raw.strip()

        if s.startswith("```"):
            close_lists()
            i += 1
            block = []
            while i < n and not md_lines[i].strip().startswith("```"):
                block.append(md_lines[i].rstrip("\n"))
                i += 1
            i += 1
            out.append("<pre>%s</pre>" % _html.escape("\n".join(block)))
            continue

        if not s:
            close_lists()
            i += 1
            continue

        if set(s) <= set("-") and len(s) >= 3:
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            close_lists()
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            i += 1
            continue
        if s.startswith("# "):
            i += 1
            continue

        # pipe table
        if s.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|$", md_lines[i + 1].strip()):
            close_lists()
            head = split_row(s)
            cls = align_classes(split_row(md_lines[i + 1]))
            cls += [""] * (len(head) - len(cls))
            i += 2
            body = []
            while i < n and md_lines[i].strip().startswith("|"):
                body.append(split_row(md_lines[i].strip()))
                i += 1
            has_head = any(c for c in head)
            t = ["<table>"]
            if has_head:
                t.append("<thead><tr>" + "".join(
                    "<th%s>%s</th>" % (cls[j] if j < len(cls) else "", inline(c))
                    for j, c in enumerate(head)) + "</tr></thead>")
            t.append("<tbody>")
            for row in body:
                t.append("<tr>" + "".join(
                    "<td%s>%s</td>" % (cls[j] if j < len(cls) else "", inline(c))
                    for j, c in enumerate(row)) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        if s.startswith(">"):
            close_lists()
            block = []
            while i < n and md_lines[i].strip().startswith(">"):
                block.append(md_lines[i].strip().lstrip(">").strip())
                i += 1
            paras, cur = [], []
            for b in block:
                if b:
                    cur.append(b)
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
            if cur:
                paras.append(" ".join(cur))
            out.append("<blockquote>" + "".join("<p>%s</p>" % inline(p) for p in paras) + "</blockquote>")
            continue

        m = re.match(r"^(\s*)([-*])\s+(.*)$", raw)
        if m:
            indent = len(m.group(1))
            while list_stack and list_stack[-1][1] > indent:
                out.append("</%s>" % list_stack.pop()[0])
            if not list_stack or list_stack[-1][1] < indent:
                out.append("<ul>")
                list_stack.append(("ul", indent))
            body = [m.group(3)]
            i += 1
            while i < n:
                nxt = md_lines[i].rstrip()
                if nxt.strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", nxt) \
                        and (len(nxt) - len(nxt.lstrip())) > indent:
                    body.append(nxt.strip())
                    i += 1
                else:
                    break
            out.append("<li>%s</li>" % inline(" ".join(body)))
            continue

        m = re.match(r"^(\s*)(\d+)\.\s+(.*)$", raw)
        if m:
            indent = len(m.group(1))
            while list_stack and list_stack[-1][1] > indent:
                out.append("</%s>" % list_stack.pop()[0])
            if not list_stack or list_stack[-1][1] < indent:
                out.append("<ol>")
                list_stack.append(("ol", indent))
            body = [m.group(3)]
            i += 1
            while i < n:
                nxt = md_lines[i].rstrip()
                if nxt.strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", nxt) \
                        and (len(nxt) - len(nxt.lstrip())) > indent:
                    body.append(nxt.strip())
                    i += 1
                else:
                    break
            out.append("<li>%s</li>" % inline(" ".join(body)))
            continue

        close_lists()
        para = [s]
        i += 1
        while i < n:
            nxt = md_lines[i].rstrip()
            if not nxt.strip() or nxt.strip().startswith(("|", ">", "#", "```", "- ", "* ")) \
                    or re.match(r"^\s*\d+\.\s", nxt) or (set(nxt.strip()) <= set("-") and len(nxt.strip()) >= 3):
                break
            para.append(nxt.strip())
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(para)))

    close_lists()
    return "\n".join(out)


def convert(md_path, pdf_path, title, subtitle, eyebrow, skip_until=None):
    lines = open(md_path, encoding="utf-8").read().split("\n")
    if skip_until is not None:
        for k, ln in enumerate(lines):
            if skip_until in ln:
                lines = lines[k:]
                break
    cover = ('<div class="cover"><div class="eyebrow">%s</div>'
             '<h1>%s</h1><div class="rule"></div><div class="sub">%s</div></div>'
             % (_html.escape(eyebrow), _html.escape(title), _html.escape(subtitle)))
    doc = ("<!doctype html><html><head><meta charset='utf-8'><title>%s</title>"
           "<style>%s</style></head><body>%s%s</body></html>"
           % (_html.escape(title), CSS, cover, render(lines)))

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    profile = tempfile.mkdtemp(prefix="chrome-pdf-")
    if os.path.exists(pdf_path):
        os.unlink(pdf_path)
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--user-data-dir=" + profile, "--no-pdf-header-footer",
         "--print-to-pdf=" + pdf_path, "--virtual-time-budget=4000",
         "file://" + tmp],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Chrome writes the PDF then sometimes fails to exit; poll for a stable file
    # rather than waiting on the process.
    size, stable, waited = -1, 0, 0.0
    try:
        while waited < 90:
            if proc.poll() is not None:
                break
            cur = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else -1
            stable = stable + 1 if cur == size and cur > 0 else 0
            size = cur
            if stable >= 3:
                break
            time.sleep(0.5)
            waited += 0.5
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.unlink(tmp)
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        raise RuntimeError("Chrome produced no PDF for " + md_path)
    return pdf_path

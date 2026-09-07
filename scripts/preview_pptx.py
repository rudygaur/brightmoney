# -*- coding: utf-8 -*-
"""Renders a .pptx to PNGs so a deck can be proofed without PowerPoint installed.

Reads the SAVED file back with python-pptx and re-lays every shape out as absolutely
positioned HTML at true scale (1in = 96px), then screenshots it headless. Text wrapping
is the browser's rather than PowerPoint's, but at these sizes in Arial the two agree
closely enough to catch the things that actually go wrong in a generated deck: text
overflowing its box, shapes colliding, and anything pushed off the slide.

    .venv/bin/python scripts/preview_pptx.py <file.pptx> <out_dir>
"""
import os, sys, html, subprocess
from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE

EMU_IN = 914400.0
PX = 96.0
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

src = sys.argv[1]
out_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp"
prs = Presentation(src)
SW, SH = prs.slide_width / EMU_IN * PX, prs.slide_height / EMU_IN * PX


def rgb(c):
    try:
        return "#%02X%02X%02X" % (c[0], c[1], c[2]) if not isinstance(c, str) else c
    except Exception:
        return None


def fill_of(sh):
    try:
        if sh.fill.type is not None and sh.fill.type == 1:      # solid
            return "#" + str(sh.fill.fore_color.rgb)
    except Exception:
        pass
    return None


def line_of(sh):
    try:
        if sh.line.fill.type == 1:
            w = sh.line.width.pt if sh.line.width else 1
            return "%.2fpx solid #%s" % (max(w * PX / 72.0, 0.6), sh.line.color.rgb)
    except Exception:
        pass
    return None


ALIGN = {1: "left", 2: "center", 3: "right", 4: "justify"}


def shape_html(sh):
    l, t = sh.left / EMU_IN * PX, sh.top / EMU_IN * PX
    w, h = sh.width / EMU_IN * PX, sh.height / EMU_IN * PX
    css = ["position:absolute", "left:%.2fpx" % l, "top:%.2fpx" % t,
           "width:%.2fpx" % w, "height:%.2fpx" % h, "box-sizing:border-box"]
    f, b = fill_of(sh), line_of(sh)
    if f:
        css.append("background:%s" % f)
    if b:
        css.append("border:%s" % b)
    try:
        if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and sh.auto_shape_type is not None:
            n = str(sh.auto_shape_type)
            if "OVAL" in n:
                css.append("border-radius:50%")
            elif "ROUNDED" in n:
                css.append("border-radius:6px")
    except Exception:
        pass

    inner = ""
    if sh.has_text_frame and sh.text_frame.text.strip():
        tf = sh.text_frame
        css.append("overflow:visible")
        paras = []
        for p in tf.paragraphs:
            ls = p.line_spacing or 1.2
            pcss = ["margin:0", "text-align:%s" % ALIGN.get(p.alignment, "left"),
                    "line-height:%s" % (ls if isinstance(ls, float) else "normal")]
            runs = []
            for r in p.runs:
                fsz = (r.font.size.pt if r.font.size else 12) * PX / 72.0
                rc = ["font-family:'%s',Arial,sans-serif" % (r.font.name or "Arial"),
                      "font-size:%.2fpx" % fsz]
                if r.font.bold:
                    rc.append("font-weight:700")
                if r.font.italic:
                    rc.append("font-style:italic")
                try:
                    if r.font.color and r.font.color.rgb:
                        rc.append("color:#%s" % (r.font.color.rgb,))   # RGBColor is a tuple: pass it as one arg
                except Exception:
                    pass
                spc = r.font._rPr.get("spc")
                if spc:
                    rc.append("letter-spacing:%.2fpx" % (int(spc) / 100.0 * PX / 72.0))
                runs.append('<span style="%s">%s</span>' % (";".join(rc), html.escape(r.text)))
            paras.append('<p style="%s">%s</p>' % (";".join(pcss), "".join(runs) or "&nbsp;"))
        inner = "".join(paras)
    return '<div style="%s">%s</div>' % (";".join(css), inner)


parts = []
for i, s in enumerate(prs.slides, 1):
    body = "".join(shape_html(sh) for sh in s.shapes)
    parts.append('<div class="slide" id="s%d">%s</div>' % (i, body))

doc = """<style>
*{box-sizing:border-box} body{margin:0;background:#333;font-family:Arial,sans-serif}
.slide{position:relative;width:%.0fpx;height:%.0fpx;background:#fff;margin:0 auto 24px;overflow:hidden}
p{margin:0}
</style>%s""" % (SW, SH, "".join(parts))

tmp = os.path.join(out_dir, "_pptx_preview.html")
open(tmp, "w", encoding="utf-8").write(doc)
subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                "--window-size=%d,%d" % (SW, (SH + 24) * len(prs.slides) + 24),
                "--screenshot=" + os.path.join(out_dir, "deck.png"),
                "--virtual-time-budget=6000", "file://" + tmp], capture_output=True)

from PIL import Image
im = Image.open(os.path.join(out_dir, "deck.png"))
for i in range(len(prs.slides.__iter__.__self__._sldIdLst)):
    y = i * (SH + 24)
    im.crop((0, int(y), int(SW), int(y + SH))).save(os.path.join(out_dir, "slide%d.png" % (i + 1)))
print("rendered %d slides to %s" % (len(prs.slides.__iter__.__self__._sldIdLst), out_dir))

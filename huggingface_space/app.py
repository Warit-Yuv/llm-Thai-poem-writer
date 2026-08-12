from __future__ import annotations

import base64
import csv
from html import escape
import io
import json
import math
from pathlib import Path
import re
import sys

import streamlit as st
import streamlit.components.v1 as components


UI_ROOT = Path(__file__).resolve().parent
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

from checker import (  # noqa: E402
    check_klon,
    compare_rhyme,
    parse_waks,
    pronounce_word,
    tokenize_editor_units,
)


LIVE_PREVIEW_BRIDGE = components.declare_component(
    "live_preview_bridge",
    path=str(UI_ROOT / "live_preview_bridge"),
)


EXAMPLE_POEMS = {
    4: """ฉันชื่อหมูกรอบ
ฉันชอบกินไก่
แล้ววิ่งตามไป
ไล่หมาน้ำทอง""",
    8: """บาทหลวงงกตกประหม่าให้ล่าทัพ
จะย้อนกลับไปไม่ได้ดั่งใจหมาย
ให้รีบเร่งพวกพหลพลนิกาย
ไปหาดทรายเต็มกลัวหนังหัวพอง""",
}
KLON_NAMES = {4: "กลอนสี่", 8: "กลอนแปด"}
WAK_NAMES = ("วรรคสดับ", "วรรครับ", "วรรครอง", "วรรคส่ง")
WORD_SLOTS = {4: 4, 8: 8}
EDITOR_SCHEMA_VERSION = 10
MAX_PREVIEW_TEXT_LENGTH = 100_000
EDITOR_LINE_SEPARATOR = re.compile(r"\r\n?|\n")

# ponytail: copied verbatim from core.KhaveeVerifier.check_klon's docstring
# rather than parsed out of it at runtime — core.py is vendored third-party, so
# reformatting upstream would silently break a regex but cannot touch a literal.
KLON_MAPS = {
    4: """วรรคที่ ๑ (สดับ)    วรรคที่ ๒ (รับ)
วรรคที่ ๓ (รอง)    วรรคที่ ๔ (ส่ง)

      ┏━━━━━━━━┯━┓    [สัมผัสคำที่ 1 หรือ 2]
O O O X        X X O O
      ┏━━━━━━━━┯━┳━━━┛
O O O X        X X O X ━┓
      ┏━━━━━━━━┯━┓      ┃ สัมผัสระหว่างบท (Inter-stanza rhyme)
O O O X        X X O O ━┛
      ┏━━━━━━━━┯━┳━━━┛
O O O X        X X O X""",
    8: """วรรคที่ ๑ (สดับ)    วรรคที่ ๒ (รับ)
วรรคที่ ๓ (รอง)    วรรคที่ ๔ (ส่ง)

              ┏━━━━━━━━┯━┯━┳━┯━┑    [สัมผัสคำที่ 3 หรือ 5 / อนุโลม 1,2,4]
O O O O O O O X        O O X O O O O X
              ┏━━━━━━━━┯━┯━┳━┯━━━━━━━┛
O O O O O O O X        O O X O O O O X ━┓
              ┏━━━━━━━━┯━┯━┳━┯━┑        ┃ สัมผัสระหว่างบท (Inter-stanza rhyme)
O O O O O O O X        O O X O O O O X ━┛
              ┏━━━━━━━━┯━┯━┳━┯━━━━━━━┛
O O O O O O O X        O O X O O O O X""",
}


def decorative_font_css() -> str:
    """Embed the licensed SOV font when the user places it in ui/assets/fonts."""
    font_dir = UI_ROOT / "assets" / "fonts"
    candidates = sorted(font_dir.glob("SOV_sannoga2467*.*")) if font_dir.exists() else []
    supported = [path for path in candidates if path.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2"}]
    if supported:
        font_path = supported[0]
        formats = {".ttf": "truetype", ".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}
        mime_types = {
            ".ttf": "font/ttf",
            ".otf": "font/otf",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }
        suffix = font_path.suffix.lower()
        encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
        return (
            "@font-face{font-family:'SOV Sannoga 2467';"
            f"src:url(data:{mime_types[suffix]};base64,{encoded}) format('{formats[suffix]}');"
            "font-display:swap;}"
        )
    return (
        "@font-face{font-family:'SOV Sannoga 2467';"
        "src:local('SOV_sannoga2467'),local('SOV sannoga2467'),local('สญฺโญค๒๔๖๗');}"
    )


st.set_page_config(
    page_title="KLON PAD RHYME CHECKER",
    page_icon="๏",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
:root { --ink:#342821; --muted:#77685d; --vermilion:#b73527; --vermilion-dark:#812219; --paper:#f5efe2; --paper-light:#fffdf8; --line:#d9c9b7; }
__FONT_FACE__
html, body, [class*="css"] { font-family:Tahoma,"Noto Sans Thai",sans-serif; }
.stApp {
  background-color:var(--paper);
  background-image:radial-gradient(circle at 15% 10%,rgba(255,255,255,.72),transparent 28%),linear-gradient(90deg,rgba(126,69,38,.025) 1px,transparent 1px);
  background-size:auto,32px 32px;
  color:var(--ink);
}
[data-testid="stSidebar"], [data-testid="collapsedControl"] { display:none; }
.st-key-live_preview_bridge { display:none !important; height:0 !important; margin:0 !important; }
.block-container { max-width:940px; padding-top:2.2rem; padding-bottom:4rem; }
h1,h2,h3 { color:var(--ink); letter-spacing:-.02em; }
.hero { position:relative; overflow:hidden; display:flex; flex-direction:column; align-items:center; text-align:center; background:rgba(255,253,248,.82); border:1px solid var(--line); border-radius:8px; padding:1.05rem 1.75rem 1rem; margin-bottom:1.45rem; box-shadow:0 9px 24px rgba(77,43,28,.07); }
.hero::before,.hero::after { content:""; position:absolute; width:3.8rem; height:3.8rem; }
.hero::before { top:.7rem; left:.7rem; border-top:1px solid rgba(183,53,39,.38); border-left:1px solid rgba(183,53,39,.38); }
.hero::after { right:.7rem; bottom:.7rem; border-right:1px solid rgba(183,53,39,.38); border-bottom:1px solid rgba(183,53,39,.38); }
.hero .thai-mark { width:100%; color:var(--vermilion); font-family:'SOV Sannoga 2467','TH Sarabun New',serif; font-size:clamp(3.8rem,9vw,5.8rem); font-weight:400; line-height:.68; margin:0; }
.hero h1 { margin:0; line-height:1.05; overflow-wrap:anywhere; }
.hero h1.thai-mark { margin:0; line-height:.68; }
.hero .project-link { display:inline-block; color:var(--vermilion); text-decoration:none; font-family:Georgia,'Times New Roman',serif; font-size:clamp(1.05rem,3.2vw,1.48rem); font-weight:700; line-height:1.3; letter-spacing:.065em; }
.hero .project-link:hover { color:var(--vermilion-dark); }
.hero .project-link:focus-visible { outline:3px solid rgba(169,47,33,.35); outline-offset:.3rem; }
.stApp a[href^="#"], [data-testid="stMarkdownContainer"] :is(h1,h2,h3,h4,h5,h6) > a { display:none !important; }
[data-testid="InputInstructions"] { display:none !important; }
.hero .ornament { display:flex; align-items:center; gap:.7rem; width:min(100%,260px); margin:.5rem auto .48rem; color:var(--vermilion); }
.hero .ornament::before,.hero .ornament::after { content:""; flex:1; height:1px; background:currentColor; opacity:.72; }
.hero .seal-dot { position:relative; width:.72rem; height:.72rem; flex:none; border:2px solid currentColor; border-radius:50%; }
.hero .seal-dot::after { content:""; position:absolute; inset:50% auto auto 50%; width:.2rem; height:.2rem; background:currentColor; border-radius:50%; transform:translate(-50%,-50%); }
.step { position:relative; display:inline-flex; align-items:center; justify-content:center; width:1.8rem; height:1.8rem; flex:none; margin-right:.38rem; color:transparent; font-size:0; vertical-align:middle; transform:translateY(-.08rem); }
.step::before,.step::after { content:""; position:absolute; top:50%; left:50%; border:3px solid var(--vermilion); border-radius:50%; box-sizing:border-box; transform:translate(-50%,-50%); }
.step::before { width:1.38rem; height:1.38rem; }
.step::after { width:.62rem; height:.62rem; }
.inspection-grid { display:grid; grid-template-columns:minmax(0,3.2fr) minmax(10.5rem,1.15fr); gap:.8rem 1.25rem; align-items:stretch; margin:.55rem 0 1.85rem; }
.mobile-summary-strip { display:none; }
.inspection-heading { align-self:end; margin:0; color:var(--ink); font-size:1.42rem; line-height:1.35; letter-spacing:-.02em; }
.summary-column-heading { align-self:center; padding:0 .2rem; color:var(--vermilion); font-size:1.05rem; font-weight:700; line-height:1.35; letter-spacing:.01em; text-align:center; }
.line-card { display:grid; grid-template-columns:minmax(0,1fr) minmax(7.4rem,8.5rem); gap:1rem; min-height:8.8rem; height:100%; background:var(--paper-light); border:1px solid var(--line); border-radius:9px; padding:1rem 1.05rem 1rem 1.15rem; }
.line-main { min-width:0; align-self:center; }
.line-title { display:flex; align-items:center; justify-content:flex-start; flex-wrap:wrap; gap:.42rem; color:var(--muted); font-size:.92rem; }
.line-title strong { padding:.2rem .5rem; border-radius:5px; font-size:.8rem; line-height:1.35; }
.line-title strong.pass { color:#176443; background:#e3f1e8; border:1px solid #c8e2d2; }
.line-title strong.review { color:#80520d; background:#fbefd7; border:1px solid #ead2a4; }
.line-title strong.fail { color:#8e2929; background:#f7e1e1; border:1px solid #e7bcbc; }
.line-text { font-size:1.18rem; font-weight:600; margin:.6rem 0; line-height:1.65; }
.line-meta { color:#4f433c; font-size:.94rem; line-height:1.55; }
.line-meta .word-fail { color:#8e2929; font-weight:700; }
.line-notes { margin-top:.65rem; display:grid; gap:.35rem; }
.line-note { color:#71372f; background:#fbebe6; border:1px solid #efcec4; border-radius:4px; padding:.42rem .6rem; font-size:.88rem; line-height:1.5; }
.beats { align-self:center; display:grid; gap:.42rem; margin:0; }
.beat { display:flex; align-items:center; justify-content:center; min-height:2.1rem; background:#f7e8e1; color:#68231d; border:1px solid #dfb6a8; border-radius:7px; padding:.34rem .52rem; font-size:.86rem; font-weight:600; line-height:1.35; text-align:center; }
.summary-tile { position:relative; overflow:hidden; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:8.8rem; height:100%; background:rgba(255,253,248,.9); border:1px solid var(--line); border-radius:9px; padding:.9rem; text-align:center; }
.summary-tile-label { color:var(--ink); font-size:.94rem; font-weight:700; line-height:1.35; }
.summary-tile-value { margin-top:.55rem; color:#18110e; font-family:Georgia,'Times New Roman',serif; font-size:2.05rem; font-weight:700; line-height:1; }
.klon-map { overflow-x:auto; white-space:nowrap; background:var(--paper-light); border:1px solid var(--line); border-radius:9px; padding:.9rem 1.05rem; margin:.1rem 0 1rem; color:#4f433c; font-family:Consolas,"Courier New",monospace; font-size:.74rem; font-variant-ligatures:none; line-height:1.6; scrollbar-color:#c9a895 #f4ece3; scrollbar-width:thin; }
.rule { background:var(--paper-light); border:1px solid var(--line); border-radius:7px; padding:.9rem 1rem; margin:.55rem 0; line-height:1.65; }
.rule > strong { font-size:.98rem; }
.rule-pair { color:#493d36; font-size:.94rem; }
.pass { color:#16704d; } .review { color:#9a6411; } .fail { color:#ad3434; }
.small-note { color:#6a5b52; font-size:.88rem; }
.research-result { background:var(--paper-light); border:1px solid var(--line); border-radius:10px; padding:.85rem 1rem; margin-top:.7rem; line-height:1.65; }
.poem-editor-heading { display:flex; align-items:baseline; justify-content:space-between; gap:1rem; margin:.15rem 0 .35rem; }
.poem-editor-heading strong { color:var(--vermilion); font-size:.92rem; letter-spacing:.025em; }
.st-key-poem_grid {
  position:relative;
  overflow-x:clip;
  overflow-y:visible;
  margin:.45rem 0 1.05rem;
  padding:1rem 4.45rem .85rem;
  background:rgba(255,253,248,.78);
  border:1px solid var(--line) !important;
  border-radius:12px !important;
  box-shadow:0 7px 20px rgba(77,43,28,.045);
  scrollbar-color:#c9a895 #f4ece3;
  scrollbar-width:thin;
}
[class*="st-key-poem_cell_"] { position:relative; z-index:3; }
.poem-rhyme-overlay {
  position:absolute; inset:0; z-index:2; width:100%; height:100%;
  overflow:visible; pointer-events:none;
}
.poem-rhyme-overlay path {
  fill:none; stroke:#342821; stroke-width:1.6;
  stroke-linecap:butt; stroke-linejoin:miter;
  vector-effect:non-scaling-stroke;
}
.poem-rhyme-overlay path.optional { stroke-dasharray:2.5 2.5; }
[class*="st-key-stanza_"] { position:relative; }
[class*="st-key-baht_row_"] { position:relative; min-height:5.35rem; }
.stanza-bracket { position:absolute; z-index:4; left:-4.05rem; top:.28rem; bottom:.24rem; width:3.55rem; color:#55483f; pointer-events:none; }
.stanza-bracket span { position:absolute; left:0; top:50%; width:2.45rem; transform:translateY(-50%); color:#574a42; font-size:.7rem; font-weight:700; line-height:1.35; text-align:center; white-space:nowrap; }
.stanza-bracket i { position:absolute; right:0; top:0; bottom:0; width:.82rem; border-left:1.4px solid rgba(52,40,33,.78); border-radius:10px 0 0 10px; }
.stanza-bracket i::before,.stanza-bracket i::after { content:""; position:absolute; left:0; width:.66rem; height:1px; background:rgba(52,40,33,.78); }
.stanza-bracket i::before { top:0; } .stanza-bracket i::after { bottom:0; }
.baht-label {
  position:absolute; z-index:4; left:50%; bottom:.05rem;
  transform:translateX(-50%); box-sizing:border-box;
  padding:0; background:transparent;
  color:#574a42; font-size:.7rem; font-weight:700;
  line-height:1.35; text-align:center; white-space:nowrap;
  pointer-events:none;
}
.rhyme-wire { position:relative; color:#342821; pointer-events:none; }
.rhyme-wire .wire { display:none; }
.rhyme-wire.top { height:1.65rem; margin:-.15rem 0 -.15rem; }
.rhyme-wire.top .wire-main {
  left:var(--source); width:calc(var(--target) - var(--source)); bottom:2px; height:calc(1.3rem - 2px);
  border-left:1.6px solid currentColor; border-right:1.6px solid currentColor; border-top:1.6px solid currentColor;
}
.rhyme-wire.top .wire-option {
  top:.35rem; bottom:2px; border-left:1.6px dotted currentColor;
}
.rhyme-wire.top .wire-extension {
  left:var(--target); width:calc(var(--extension) - var(--target)); top:.35rem;
  border-top:1.6px dotted currentColor;
}
.rhyme-wire.middle { height:2.25rem; margin:-1.2rem 0 -.2rem; }
.rhyme-wire.middle .wire-start {
  right:var(--edge); top:2px; height:calc(2.45rem - 2px); border-right:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-bridge {
  left:var(--source); width:calc(var(--target) - var(--source)); top:2.45rem;
  border-top:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-extension {
  left:var(--target); width:calc(var(--solid-resume) - var(--target)); top:2.45rem;
  border-top:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-tail {
  left:var(--solid-resume); right:var(--edge); top:2.45rem;
  border-top:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-end {
  left:var(--source); top:2.45rem; height:calc(3.5rem - 2px); border-left:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-target {
  left:var(--target); top:2.45rem; height:calc(3.5rem - 2px); border-left:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-option {
  top:2.45rem; height:calc(3.5rem - 2px); border-left:1.6px dotted currentColor;
}
.rhyme-wire.inter-stanza { height:1.75rem; margin:-.15rem 0 -.1rem; }
.rhyme-wire.inter-stanza .wire-main {
  left:calc(100% - var(--edge) + 1rem + 2px); top:-3.37rem; width:calc(1.05rem - 2px); height:10.35rem;
  border-right:1.6px solid currentColor; border-top:1.6px solid currentColor; border-bottom:1.6px solid currentColor;
}
.stanza-title { display:flex; align-items:center; gap:.65rem; margin:.1rem 0 .15rem; color:var(--vermilion); font-size:.8rem; font-weight:700; }
.stanza-title::after { content:""; flex:1; height:1px; background:rgba(183,53,39,.18); }
.wak-label { display:flex; align-items:center; margin:.26rem 0 .18rem; color:var(--ink); font-size:.76rem; font-weight:700; }
.wak-label.right { justify-content:flex-end; text-align:right; }
.wak-label.baht-ek { transform:translateY(1.5rem); }
.rhyme-route { position:relative; width:max-content; margin:-.05rem auto .08rem; padding:0 .55rem; color:#9b7568; background:#fffdf8; font-size:.66rem; line-height:1.4; }
.rhyme-route::before,.rhyme-route::after { content:""; position:absolute; top:50%; width:2.1rem; height:1px; background:rgba(183,53,39,.3); }
.rhyme-route::before { right:100%; } .rhyme-route::after { left:100%; }
[class*="st-key-poem_cell_"] { min-width:2.45rem; }
[class*="st-key-poem_cell_"] [data-testid="stTextAreaRootElement"] {
  min-height:2.45rem !important;
  border:1px solid #ddcdbd !important;
  border-radius:999px !important;
  background:#fffdfa !important;
}
[class*="st-key-poem_cell_"] [data-testid="stTextAreaRootElement"]:focus-within {
  border-color:var(--vermilion) !important;
  box-shadow:0 0 0 2px rgba(183,53,39,.1) !important;
}
[class*="st-key-poem_cell_"] textarea {
  min-height:2.45rem !important;
  height:2.45rem !important;
  padding:.5rem .2rem !important;
  overflow-x:auto !important;
  overflow-y:hidden !important;
  resize:none !important;
  white-space:pre !important;
  word-break:normal !important;
  text-align:center;
  color:var(--ink) !important;
  font-size:.72rem !important;
  line-height:1.35 !important;
  scrollbar-width:none;
}
[class*="st-key-poem_cell_"] textarea::-webkit-scrollbar { display:none; }
[class*="st-key-poem_cell_"] textarea::placeholder { color:#a8998e; opacity:1; }
.st-key-add_baht button {
  display:flex; align-items:center; justify-content:center;
  box-sizing:border-box !important; flex:0 0 2.75rem !important;
  width:2.75rem !important; min-width:2.75rem !important; max-width:2.75rem !important;
  height:2.75rem !important; min-height:2.75rem !important; max-height:2.75rem !important;
  aspect-ratio:1 / 1 !important;
  margin:.28rem auto 0; padding:0 !important;
  border:2px solid #d8c6b3 !important; border-radius:999px !important;
  background:#fffdf8 !important; color:var(--vermilion) !important;
  font-size:1.45rem !important; box-shadow:none !important;
}
.st-key-add_baht [data-testid="stButton"] { display:flex; justify-content:center; width:100%; min-width:2.75rem; overflow:visible; }
.st-key-add_baht button:hover { border-color:var(--vermilion) !important; background:#fff7ef !important; transform:none !important; }
.st-key-add_baht button p { color:var(--vermilion) !important; font-size:1.45rem !important; line-height:1 !important; }
.input-workbench { margin-top:.2rem; }
.workbench-title { margin:0 0 .48rem; color:var(--vermilion); font-size:1.08rem; font-weight:700; line-height:1.45; }
.rhyme-lab-result { display:grid; grid-template-columns:minmax(8.4rem,.72fr) minmax(0,1.55fr); gap:.65rem; margin-top:.65rem; }
.rhyme-verdict { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:7rem; padding:.72rem; border:1px solid var(--line); border-radius:10px; background:#fffdf9; text-align:center; }
.rhyme-verdict.pass { border-color:#b9dccb; background:#f3fbf6; color:#176443; }
.rhyme-verdict.fail { border-color:#e7bcbc; background:#fff7f5; color:#8e2929; }
.rhyme-verdict strong { font-size:1rem; line-height:1.4; }
.rhyme-verdict span { margin-top:.25rem; color:var(--ink); font-size:.8rem; }
.rhyme-sound-table { width:100%; border-collapse:separate; border-spacing:0; overflow:hidden; border:1px solid #eadace; border-radius:10px; background:#fff; font-size:.72rem; }
.rhyme-sound-table th { padding:.46rem .4rem; background:var(--vermilion); color:#fff; font-weight:700; text-align:left; }
.rhyme-sound-table td { padding:.42rem .4rem; border-top:1px solid #eee3d8; background:#fff; vertical-align:top; }
.rhyme-sound-table td:first-child { color:#6f2e25; font-weight:700; }
.rhyme-sound-table .rhyme-pronunciation small { display:block; margin-top:.14rem; color:var(--muted); font-size:.68rem; font-weight:400; }
.result-section { margin-top:.35rem; }
.result-heading-row { display:flex; align-items:center; flex-wrap:wrap; gap:.65rem; margin:0 0 1rem; }
.result-heading-row h2 { display:flex; align-items:center; margin:0 .35rem 0 0; font-size:1.75rem; line-height:1.25; }
.result-status-pill { display:inline-flex; align-items:center; gap:.58rem; min-height:2.75rem; padding:.42rem .78rem .42rem 1rem; background:#fff; border:1px solid rgba(91,66,51,.08); border-radius:17px; font-size:1rem; font-weight:700; line-height:1.2; box-shadow:0 3px 10px rgba(77,43,28,.035); }
.result-status-pill.pass { color:#176d4a; }
.result-status-pill.review { color:#95610e; }
.result-status-pill.fail { color:#bd3026; }
.result-status-icon { display:inline-flex; align-items:center; justify-content:center; width:1.45rem; height:1.45rem; border:2px solid currentColor; border-radius:50%; font-size:.95rem; font-weight:700; line-height:1; }
.result-status-pill.fail .result-status-icon { font-size:1.15rem; }
.result-overview { display:grid; grid-template-columns:minmax(0,1.7fr) minmax(16rem,1.25fr); gap:1rem; align-items:stretch; margin-bottom:1rem; }
.result-structure-card { display:grid; grid-template-columns:5rem minmax(0,1fr); gap:1rem; align-items:center; min-height:8.25rem; padding:1rem 1.15rem; background:#fffdf9; border:1px solid var(--line); border-radius:12px; box-shadow:0 5px 14px rgba(77,43,28,.045); }
.result-score-ring { display:flex; flex-direction:column; align-items:center; justify-content:center; box-sizing:border-box; width:4.45rem; height:4.45rem; border:2px solid #dc7468; border-radius:50%; color:var(--vermilion); background:#fffaf5; line-height:1; }
.result-score-ring strong { font-family:Georgia,'Times New Roman',serif; font-size:1.42rem; }
.result-score-ring span { margin-top:.2rem; color:#765f54; font-size:.64rem; font-weight:700; }
.result-structure-copy small { display:block; color:var(--vermilion); font-size:.72rem; font-weight:700; letter-spacing:.035em; }
.result-structure-copy h3 { margin:.24rem 0 .34rem; color:var(--ink); font-size:1.08rem; line-height:1.4; }
.result-structure-copy p { margin:0; color:var(--muted); font-size:.82rem; line-height:1.55; }
.result-counts { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.72rem; }
.result-count-card { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:8.25rem; padding:.75rem .45rem; background:#fffdf9; border:2px solid #e3d8cc; border-radius:14px; text-align:center; }
.result-count-card strong { color:#17110e; font-size:1.08rem; line-height:1.2; }
.result-count-card span { margin-top:.42rem; color:#17110e; font-family:Georgia,'Times New Roman',serif; font-size:1.65rem; line-height:1; }
.result-poem-card { margin:.3rem 0 1.15rem; padding:1.15rem 1.25rem 1.35rem; background:#fff; border:2px solid #e4d8ca; border-radius:15px; }
.result-stanza { min-height:17rem; }
.result-stanza + .result-stanza { margin-top:1.2rem; padding-top:1.15rem; border-top:1px solid #eadfd4; }
.result-stanza-title { margin:0 0 .75rem; color:var(--ink); font-size:.86rem; font-weight:700; }
.result-rhyme-warning { display:flex; align-items:center; justify-content:center; gap:.5rem; margin:-.05rem 0 .5rem; color:#c83a30; font-size:1rem; font-weight:700; }
.result-rhyme-warning strong { color:currentColor; text-decoration:underline dotted currentColor; text-underline-offset:.2em; }
.result-rhyme-warning-icon { width:1.7rem; height:1.7rem; flex:none; overflow:visible; }
.result-rhyme-warning-icon path,.result-rhyme-warning-icon line { fill:none; stroke:currentColor; stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
.result-poem-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); column-gap:2.25rem; row-gap:1.1rem; align-items:start; }
.result-wak { display:flex; flex-direction:column; justify-content:center; min-width:0; min-height:4.4rem; padding:.05rem .8rem .15rem; text-align:center; }
.result-wak-label { margin-bottom:.22rem; color:#cf3b2f; font-size:.76rem; font-weight:700; text-align:left; }
.result-wak.right .result-wak-label { text-align:right; }
.result-wak-text { color:#15110f; font-size:clamp(1rem,2.5vw,1.6rem); font-weight:500; line-height:1.58; letter-spacing:-.018em; white-space:nowrap; }
.result-wak-text .rhyme-a { color:#efa72f; font-weight:700; }
.result-wak-text .rhyme-b { color:#04a767; font-weight:700; }
.result-wak-text .rhyme-fail { color:#c83a30; font-weight:700; text-decoration:underline dotted currentColor; text-underline-offset:.18em; }
.result-baht-label { grid-column:1 / -1; margin:-.25rem 0 -.15rem; color:#0757b2; font-size:.82rem; font-weight:700; text-align:center; }
.result-issue-section { margin:1.1rem 0; }
.result-issue-heading { display:flex; align-items:center; gap:.58rem; width:max-content; max-width:100%; margin:0 0 .7rem; padding:.42rem .9rem .42rem .58rem; background:#fff; border-radius:999px; color:#d33b30; font-size:1.08rem; font-weight:700; line-height:1.35; white-space:nowrap; }
.result-issue-heading span { display:inline-flex; align-items:center; justify-content:center; box-sizing:border-box; width:1.75rem; height:1.75rem; border:2px solid currentColor; border-radius:50%; font-size:1.12rem; line-height:1; }
.result-issue-list { display:grid; gap:.65rem; }
.result-issue-card { padding:.8rem 1rem; background:#fffdf9; border:1px solid #e3d7ca; border-radius:9px; box-shadow:0 3px 9px rgba(77,43,28,.03); }
.result-issue-card.review { border-color:#ead4aa; }
.result-syllable-card { display:block; min-height:5.4rem; padding:1rem 1.2rem; }
.result-syllable-detail { display:flex; align-items:baseline; flex-wrap:wrap; gap:.35rem .8rem; margin-top:.42rem; }
.result-issue-meta { color:var(--muted); font-size:.72rem; }
.result-issue-body { display:flex; align-items:baseline; justify-content:space-between; gap:1rem; margin-top:.24rem; }
.result-issue-text { color:var(--ink); font-size:.94rem; font-weight:600; line-height:1.5; }
.result-issue-reason { color:#ce3d31; font-size:.88rem; font-weight:700; line-height:1.45; text-align:right; }
.result-syllable-card .result-issue-text { font-size:.96rem; }
.result-syllable-card .result-issue-meta { color:#99918b; font-size:.82rem; }
.result-syllable-card .result-issue-reason { margin:0; color:#d33b30; font-size:1.08rem; text-align:left; }
.result-syllable-card .result-issue-reason span { margin-right:.3rem; font-size:1.2rem; font-weight:500; }
.result-rhyme-rule { color:#c83a30; font-size:.9rem; font-weight:700; line-height:1.45; }
.result-rhyme-detail { margin-top:.26rem; color:#5f5047; font-size:.8rem; line-height:1.55; }
.result-rhyme-detail strong { color:var(--ink); }
div[data-baseweb="modal"], div[data-testid="stDialog"] { background:rgba(42,40,39,.34) !important; backdrop-filter:blur(2px) saturate(.72); }
div[data-testid="stDialog"] div[role="dialog"] { background:#fffdf9 !important; border:1px solid #ded2c5; box-shadow:0 18px 48px rgba(45,38,34,.2) !important; }
.stButton>button { border-radius:10px; min-height:2.6rem; font-size:.9rem; font-weight:600; }
.stButton>button p { font-size:.9rem; }
.stButton>button[kind="primary"] { background:var(--vermilion); border-color:var(--vermilion); color:#fff !important; }
.stButton>button[kind="primary"] * { color:#fff !important; }
.stButton>button[kind="primary"]:hover { background:var(--vermilion-dark); border-color:var(--vermilion-dark); }
[data-testid="stFormSubmitButton"] button { border-radius:10px; min-height:2.6rem; font-size:.9rem; font-weight:600; }
[data-testid="stFormSubmitButton"] button[kind="primary"] { background:var(--vermilion); border-color:var(--vermilion); color:#fff !important; }
[data-testid="stFormSubmitButton"] button[kind="primary"] * { color:#fff !important; }
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover { background:var(--vermilion-dark); border-color:var(--vermilion-dark); }
[data-testid="stTextAreaRootElement"] { overflow:hidden; background:var(--paper-light) !important; border:1px solid var(--line) !important; border-radius:8px !important; box-shadow:none !important; }
[data-testid="stTextAreaRootElement"]:focus-within { border-color:var(--line) !important; box-shadow:none !important; }
[data-testid="stTextArea"] textarea { background:var(--paper-light) !important; border:0 !important; border-radius:0 !important; outline:0 !important; box-shadow:none !important; }
[data-testid="stCaptionContainer"] { color:#6b5c52; font-size:.9rem; line-height:1.6; }
[data-testid="stTextArea"] textarea { font-size:1rem; line-height:1.65; }
[data-testid="stButtonGroup"] { width:min(100%,650px); margin:.25rem 0 .35rem; }
[data-testid="stButtonGroup"] > label {
  color:var(--ink);
  font-size:.96rem;
  font-weight:700;
  margin-bottom:.45rem;
}
[data-testid="stButtonGroup"] div[role="radiogroup"] {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:.75rem;
  width:100%;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
  position:relative;
  overflow:hidden;
  display:flex;
  align-items:center;
  width:100%;
  min-height:3.55rem;
  margin:0;
  padding:.62rem .85rem;
  border:1px solid var(--line) !important;
  border-radius:16px !important;
  outline:none !important;
  background:rgba(255,253,248,.86);
  box-shadow:0 5px 14px rgba(77,43,28,.055);
  cursor:pointer;
  transition:border-color .16s ease,background-color .16s ease,box-shadow .16s ease,transform .16s ease;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:nth-child(1)::before,
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:nth-child(2)::before {
  position:absolute;
  top:50%;
  left:1.15rem;
  transform:translateY(-50%);
  color:rgba(183,53,39,.14);
  font-family:Tahoma,"Noto Sans Thai",sans-serif;
  font-size:2.55rem;
  font-weight:700;
  line-height:1;
  pointer-events:none;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:nth-child(1)::before { content:"๔"; }
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:nth-child(2)::before { content:"๘"; }
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] [data-testid="stMarkdownContainer"] {
  width:100%;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover {
  border-color:rgba(183,53,39,.62);
  background:#fffaf2;
  box-shadow:0 8px 18px rgba(109,42,27,.1);
  transform:translateY(-1px);
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-focus-visible] {
  outline:3px solid rgba(183,53,39,.24);
  outline-offset:2px;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected] {
  border:1px solid var(--vermilion-dark) !important;
  outline:none !important;
  background:linear-gradient(135deg,var(--vermilion),#a72d21) !important;
  box-shadow:0 5px 12px rgba(129,34,25,.14) !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected][data-focus-visible] {
  outline:2px solid rgba(183,53,39,.24) !important;
  outline-offset:2px !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected]::before {
  color:rgba(255,255,255,.3);
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] p {
  position:relative;
  z-index:1;
  width:calc(100% - 3.7rem);
  margin:0 0 0 3.7rem;
  text-align:center;
  color:var(--ink);
  font-size:1.08rem;
  font-weight:700;
  line-height:1.45;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected] p,
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected] * { color:#fff !important; }
@media (max-width:640px) {
  .block-container { padding-top:1rem; }
  .hero { padding:1.15rem 1rem 1.05rem; }
  .hero .project-link { letter-spacing:.025em; }
  .result-heading-row { gap:.5rem; }
  .result-heading-row h2 { width:100%; font-size:1.55rem; }
  .result-status-pill { flex:1; justify-content:center; min-width:8.5rem; font-size:.84rem; }
  .result-overview { grid-template-columns:1fr; }
  .result-structure-card { min-height:7.5rem; }
  .result-count-card { min-height:5.3rem; }
  .result-count-card strong { font-size:.9rem; }
  .result-count-card span { font-size:1.42rem; }
  .result-poem-card { padding:.85rem .45rem 1rem; }
  .result-stanza { min-height:14rem; }
  .result-poem-grid { column-gap:.35rem; row-gap:.7rem; }
  .result-wak { padding:.05rem .25rem .1rem; }
  .result-wak-text { font-size:clamp(.78rem,3.55vw,1rem); }
  .result-issue-body { display:block; }
  .result-issue-reason { margin-top:.35rem; text-align:left; }
  .result-syllable-card .result-issue-reason { font-size:1rem; }
  .klon-map { font-size:.6rem; padding:.7rem .8rem; }
  .mobile-summary-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.42rem; margin:.55rem 0 1rem; }
  .inspection-grid { grid-template-columns:1fr; gap:.65rem; margin-top:0; }
  .inspection-heading { grid-column:auto; margin-top:.35rem; }
  .summary-column-heading { display:none; }
  .inspection-grid > .summary-tile { display:none; }
  .mobile-summary-strip .summary-tile { min-height:5.35rem; height:auto; padding:.62rem .25rem; text-align:center; }
  .summary-tile-label { font-size:clamp(.68rem,2.2vw,.78rem); }
  .summary-tile-value { margin-top:.38rem; font-size:1.55rem; }
  .line-card { grid-column:auto; height:auto; }
  .st-key-poem_grid { padding:.8rem; }
  .stanza-bracket { position:relative; left:auto; top:auto; bottom:auto; width:auto; height:1.25rem; margin:0 0 .15rem; }
  .stanza-bracket span { position:static; display:block; width:auto; transform:none; color:var(--vermilion); text-align:left; }
  .stanza-bracket i { display:none; }
  .baht-label { position:relative; left:auto; bottom:auto; display:table; transform:none; margin:.15rem auto 0; color:var(--muted); }
  .rhyme-lab-result { grid-template-columns:1fr; }
  [data-testid="stButtonGroup"] div[role="radiogroup"] { grid-template-columns:1fr; }
}
@media (max-width:480px) {
  .line-card { grid-template-columns:1fr; min-height:0; }
  .beats { grid-template-columns:repeat(3,minmax(0,1fr)); }
}
</style>
""".replace("__FONT_FACE__", decorative_font_css()),
    unsafe_allow_html=True,
)


def clear_analysis() -> None:
    st.session_state.pop("report", None)
    st.session_state.pop("analyzed_input", None)
    st.session_state.pop("analyzed_klon_type", None)
    st.session_state.pop("analysis_error", None)


def poem_cell_key(klon_type: int, line_index: int, slot_index: int) -> str:
    return f"poem_cell_{klon_type}_{line_index}_{slot_index}"


def _clear_poem_cells(klon_type: int | None = None) -> None:
    prefix = "poem_cell_" if klon_type is None else f"poem_cell_{klon_type}_"
    for key in list(st.session_state):
        if key.startswith(prefix):
            del st.session_state[key]


def parse_editor_waks(poem_text: str) -> list[str]:
    """Use Enter as the only UI line boundary.

    Punctuation and ordinary spaces remain inside their source line and are
    discarded later by the project's Thai tokenizer. This keeps visual word
    cells stable while users type natural spacing or commas.
    """
    return [
        line.strip()
        for line in EDITOR_LINE_SEPARATOR.split(poem_text)
        if line.strip()
    ]


def _fit_words_to_slots(words: list[str], slot_count: int) -> list[str]:
    """Preserve pasted text even when tokenization produces extra UI cells."""
    if len(words) <= slot_count:
        return words + [""] * (slot_count - len(words))
    return words[: slot_count - 1] + ["".join(words[slot_count - 1 :])]


def poem_from_grid(klon_type: int) -> str:
    slot_count = WORD_SLOTS[klon_type]
    baht_count = max(2, int(st.session_state.get("editor_baht_count", 2)))
    rows = []
    for line_index in range(baht_count * 2):
        words = [
            st.session_state.get(poem_cell_key(klon_type, line_index, slot_index), "").strip()
            for slot_index in range(slot_count)
        ]
        rows.append("".join(word for word in words if word))
    return "\n".join(rows).rstrip()


def load_poem_into_grid(
    poem_text: str,
    klon_type: int,
    *,
    normalize_text: bool = True,
) -> None:
    """Normalize pasted punctuation/spacing and distribute text into word cells."""
    waks = parse_editor_waks(poem_text)
    baht_count = max(2, math.ceil(len(waks) / 2))
    st.session_state.editor_baht_count = baht_count
    # The text box is the canonical poem.  Remove both klon layouts so an old
    # inactive grid can never reappear after the user changes poem type.
    _clear_poem_cells()
    slot_count = WORD_SLOTS[klon_type]
    normalized_waks: list[str] = []
    for line_index in range(baht_count * 2):
        wak = waks[line_index] if line_index < len(waks) else ""
        words = tokenize_editor_units(wak)
        fitted = _fit_words_to_slots(words, slot_count)
        for slot_index, word in enumerate(fitted):
            st.session_state[poem_cell_key(klon_type, line_index, slot_index)] = word
        if wak:
            normalized_waks.append("".join(words) or wak.strip())
    if normalize_text:
        st.session_state.poem_input = "\n".join(normalized_waks)
    st.session_state.editor_klon_type = klon_type


def submit_poem_for_analysis() -> None:
    """Copy the latest text into the grid before the explicit analysis run."""
    klon_type = st.session_state.get("klon_type", 8)
    load_poem_into_grid(st.session_state.get("poem_input", ""), klon_type)
    clear_analysis()


def preview_poem_from_text() -> None:
    """Refresh only the editable diagram; never run the poem checker here."""
    klon_type = st.session_state.get("klon_type", 8)
    load_poem_into_grid(
        st.session_state.get("poem_input", ""),
        klon_type,
        normalize_text=False,
    )
    clear_analysis()


def apply_live_preview_bridge() -> None:
    """Accept raw text only; Python remains the sole tokenization authority."""
    payload = st.session_state.get("live_preview_bridge")
    if not isinstance(payload, dict):
        return
    raw_text = payload.get("text")
    if not isinstance(raw_text, str):
        return
    raw_text = raw_text[:MAX_PREVIEW_TEXT_LENGTH]
    if raw_text == st.session_state.get("poem_input", ""):
        return

    klon_type = int(st.session_state.get("klon_type", 8))
    st.session_state.poem_input = raw_text
    load_poem_into_grid(raw_text, klon_type, normalize_text=False)
    clear_analysis()


def sync_cell_to_text(cell_key: str, line_index: int, slot_index: int, klon_type: int) -> None:
    raw_value = st.session_state.get(cell_key, "")
    if EDITOR_LINE_SEPARATOR.search(raw_value):
        # A complete multiline poem can be pasted into any word cell. Only an
        # explicit Enter starts a new วรรค; spaces and commas stay in the line.
        load_poem_into_grid(raw_value, klon_type)
        clear_analysis()
        return

    words = tokenize_editor_units(raw_value)
    slot_count = WORD_SLOTS[klon_type]
    if len(words) > 1:
        fitted = _fit_words_to_slots(words, slot_count - slot_index)
        for offset, word in enumerate(fitted):
            st.session_state[poem_cell_key(klon_type, line_index, slot_index + offset)] = word
    else:
        st.session_state[cell_key] = words[0] if words else ""
    st.session_state.poem_input = poem_from_grid(klon_type)
    clear_analysis()


def add_baht() -> None:
    st.session_state.editor_baht_count = max(
        2, int(st.session_state.get("editor_baht_count", 2))
    ) + 1
    clear_analysis()


def use_example() -> None:
    klon_type = st.session_state.get("klon_type", 8)
    load_poem_into_grid(EXAMPLE_POEMS[klon_type], klon_type)
    clear_analysis()


def clear_input() -> None:
    st.session_state.poem_input = ""
    st.session_state.editor_baht_count = 2
    _clear_poem_cells()
    clear_analysis()


def rhyme_wire_html(kind: str, klon_type: int) -> str:
    """Draw one exact route from the traditional rhyme diagram.

    Solid lines mark the conventional target; dotted branches mark accepted
    alternatives.  The positions differ by form so the diagram does not teach
    klon-si users the klon-paet candidate range.
    """
    if klon_type == 4:
        source = 41.6
        target = 70.6  # คำที่ 2 ตามผังกลอนสี่
        alternatives = (58.7, 82.5)  # คำที่ 1; คำที่ 3 เมื่อวรรคมี 5 พยางค์
        solid_resume = 82.5
    else:
        # Compensate for Streamlit's column gap so every stem meets the exact
        # horizontal centre of its circular word cell.
        source = 44.5
        target = 68.6  # คำที่ 3 เป็นตำแหน่งหลัก
        alternatives = (56.6, 62.6, 74.6, 80.6)  # คำที่ 1, 2, 4, 5
        solid_resume = 74.6  # ช่วงคำที่ 4 → คำที่ 8 ของวรรคส่งเป็นเส้นทึบ

    edge = 1.7 if klon_type == 4 else 1.2

    extension = max((target, *alternatives))
    if kind == "middle":
        option_wires = "".join(
            f'<span class="wire wire-option" style="left:{position}%"></span>'
            for position in alternatives
        )
        wire_parts = (
            '<span class="wire wire-start"></span>'
            '<span class="wire wire-bridge"></span>'
            '<span class="wire wire-extension"></span>'
            '<span class="wire wire-tail"></span>'
            '<span class="wire wire-end"></span>'
            '<span class="wire wire-target"></span>'
            f'{option_wires}'
        )
    elif kind in {"top", "bottom"}:
        option_wires = "".join(
            f'<span class="wire wire-option" style="left:{position}%"></span>'
            for position in alternatives
        )
        extension_wire = (
            '<span class="wire wire-extension"></span>' if extension > target else ""
        )
        wire_parts = (
            '<span class="wire wire-main"></span>'
            f'{option_wires}{extension_wire}'
        )
    else:
        wire_parts = '<span class="wire wire-main"></span>'
    return (
        f'<div class="rhyme-wire {kind}" '
        f'style="--source:{source}%;--target:{target}%;--extension:{extension}%;'
        f'--solid-resume:{solid_resume}%;--edge:{edge}%;" aria-hidden="true">'
        f'{wire_parts}'
        '</div>'
    )


def render_poem_editor(klon_type: int) -> None:
    slot_count = WORD_SLOTS[klon_type]
    baht_count = max(2, int(st.session_state.get("editor_baht_count", 2)))
    with st.container(border=True, key="poem_grid"):
        stanza_count = math.ceil(baht_count / 2)
        for stanza_index in range(stanza_count):
            first_baht = stanza_index * 2
            with st.container(key=f"stanza_{stanza_index}"):
                st.markdown(
                    f'<div class="stanza-bracket" aria-label="บทที่ {stanza_index + 1}">'
                    f'<span>บทที่ {stanza_index + 1}</span><i aria-hidden="true"></i></div>',
                    unsafe_allow_html=True,
                )
                for local_baht_index in range(2):
                    baht_index = first_baht + local_baht_index
                    if baht_index >= baht_count:
                        break
                    baht_name = "บาทเอก" if local_baht_index == 0 else "บาทโท"
                    with st.container(key=f"baht_row_{baht_index}"):
                        label_columns = st.columns(2, gap="large")
                        for column_offset, label_column in enumerate(label_columns):
                            line_index = baht_index * 2 + column_offset
                            wak_name = WAK_NAMES[line_index % 4]
                            label_class = "right" if column_offset else "left"
                            baht_class = "baht-ek" if local_baht_index == 0 else "baht-tho"
                            with label_column:
                                st.markdown(
                                    f'<div class="wak-label {label_class} {baht_class}">{wak_name}</div>',
                                    unsafe_allow_html=True,
                                )

                        # The first row of each stanza carries the upper สดับ → รับ route.
                        if local_baht_index == 0:
                            st.markdown(rhyme_wire_html("top", klon_type), unsafe_allow_html=True)

                        wak_columns = st.columns(2, gap="large")
                        for column_offset, wak_column in enumerate(wak_columns):
                            line_index = baht_index * 2 + column_offset
                            wak_name = WAK_NAMES[line_index % 4]
                            with wak_column:
                                for slot_index in range(slot_count):
                                    key = poem_cell_key(klon_type, line_index, slot_index)
                                    if key not in st.session_state:
                                        st.session_state[key] = ""
                                word_columns = st.columns(slot_count, gap="small")
                                for slot_index, column in enumerate(word_columns):
                                    key = poem_cell_key(klon_type, line_index, slot_index)
                                    value = st.session_state.get(key, "")
                                    spoken, _ = pronounce_word(value) if value else ((), "—")
                                    column.text_area(
                                        f"{wak_name} คำที่ {slot_index + 1}",
                                        key=key,
                                        height=38,
                                        placeholder=f"คำ{slot_index + 1}",
                                        help=(f"อ่านว่า {'-'.join(spoken)}" if len(spoken) > 1 else None),
                                        label_visibility="collapsed",
                                        on_change=sync_cell_to_text,
                                        args=(key, line_index, slot_index, klon_type),
                                    )

                        st.markdown(
                            f'<div class="baht-label">{baht_name}</div>',
                            unsafe_allow_html=True,
                        )

                    if local_baht_index == 0 and baht_index + 1 < baht_count:
                        # ท้ายวรรครับ → ท้ายวรรครอง
                        st.markdown(rhyme_wire_html("middle", klon_type), unsafe_allow_html=True)

            if first_baht + 2 < baht_count:
                # ท้ายวรรคส่งของบทก่อน → ท้ายวรรครับของบทถัดไป
                st.markdown(
                    rhyme_wire_html("inter-stanza", klon_type),
                    unsafe_allow_html=True,
                )
        add_left, add_center, add_right = st.columns([1, .13, 1])
        add_center.button(
            "＋",
            key="add_baht",
            on_click=add_baht,
        )


def rhyme_lab_html(comparison: dict) -> str:
    passed = comparison["passed"]
    verdict_class = "pass" if passed else "fail"
    verdict = "สัมผัสกัน" if passed else "ไม่สัมผัสกัน"
    rows = []
    for analysis_key in ("first_analysis", "second_analysis"):
        analysis = comparison[analysis_key]
        rhyme_detail = (analysis["sound_details"] or [
            {"syllable": "—", "vowel": "—", "final_class": "—"}
        ])[-1]
        pronunciation_note = ""
        if len(analysis.get("syllables", [])) > 1:
            pronunciation_note = (
                f'<small>ตรวจเสียงสัมผัสที่ “{escape(analysis["rhyme_syllable"])}”</small>'
            )
        rows.append(
            "<tr>"
            f'<td class="rhyme-pronunciation">{escape(analysis["pronunciation"])}{pronunciation_note}</td>'
            f"<td>{escape(rhyme_detail['vowel'])}</td>"
            f"<td>{escape(rhyme_detail['final_class'])}</td>"
            "</tr>"
        )
    return f"""
      <div class="rhyme-lab-result">
        <div class="rhyme-verdict {verdict_class}">
          <strong>{verdict}</strong>
          <span>{escape(comparison['first'])} ↔ {escape(comparison['second'])}</span>
        </div>
        <table class="rhyme-sound-table" aria-label="ผลวิเคราะห์เสียงของคำทดลอง">
          <thead><tr><th>คำอ่าน</th><th>สระ</th><th>มาตรา</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def report_csv(report: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["klon_type", "line", "wak_name", "text", "syllables", "rhythm", "status"])
    for line in report["lines"]:
        writer.writerow(
            [
                report["klon_type"],
                line["index"] + 1,
                line["wak_name"],
                line["text"],
                line["syllable_count"],
                line["rhythm_text"],
                line["meter_status"],
            ]
        )
    return "\ufeff" + output.getvalue()


def _result_status(kind: str, label: str) -> str:
    icon = "✓" if kind == "pass" else ("!" if kind == "review" else "×")
    return (
        f'<div class="result-status-pill {kind}"><span>{escape(label)}</span>'
        f'<span class="result-status-icon" aria-hidden="true">{icon}</span></div>'
    )


def _spoken_word_location(line: dict, position: int) -> tuple[int, int] | None:
    """Map a one-based spoken position to (written word, syllable in word)."""
    cursor = 0
    for word_index, word in enumerate(line.get("words", [])):
        syllable_count = int(word.get("syllables", 0))
        if cursor < position <= cursor + syllable_count:
            return word_index, position - cursor - 1
        cursor += syllable_count
    return None


def _rhyme_highlights(report: dict) -> dict[int, dict[tuple[int, int], set[str]]]:
    """Map every detected rhyme route—including failed endpoints—to written words."""
    highlights: dict[int, dict[tuple[int, int], set[str]]] = {}
    for check in report.get("rhyme_checks", []):
        source_line = int(check["source_line"]) - 1
        target_line = int(check["target_line"]) - 1
        source_position = len(report["lines"][source_line].get("spoken_syllables", []))
        if "target" in check:
            target_positions = [len(report["lines"][target_line].get("spoken_syllables", []))]
        else:
            matches = check.get("matched_positions", [])
            if matches:
                # Show every candidate that KhaveeVerifier actually accepts.
                # Positions 3 and 5 remain preferred in the report, but 1, 2,
                # and 4 are valid visual destinations when they truly rhyme.
                target_positions = list(matches)
            else:
                candidate_positions = [item["position"] for item in check.get("candidates", [])]
                target_positions = [3 if 3 in candidate_positions else candidate_positions[0]]

        rule_position = source_line % 4
        css_class = "rhyme-a" if rule_position == 0 else "rhyme-b"
        if target_line // 4 != source_line // 4:
            # Inter-stanza rhyme continues the same green rhyme chain. A third
            # pass colour made one continuous rule look like a separate state.
            css_class = "rhyme-b"
        classes = {css_class}
        if not check["passed"]:
            classes.add("rhyme-fail")
        endpoints = [(source_line, source_position)] + [
            (target_line, target_position) for target_position in target_positions
        ]
        for line_index, position in endpoints:
            location = _spoken_word_location(report["lines"][line_index], position)
            if location is not None:
                highlights.setdefault(line_index, {}).setdefault(location, set()).update(classes)
    return highlights


def _highlighted_line_text(
    line: dict,
    highlights: dict[tuple[int, int], set[str]],
) -> str:
    text = line.get("text", "")
    words = line.get("words", [])
    if not words:
        return escape(text)

    pieces: list[str] = []
    cursor = 0
    for word_index, word_data in enumerate(words):
        word = str(word_data.get("word", ""))
        start = text.find(word, cursor)
        if start < 0:
            continue
        pieces.append(escape(text[cursor:start]))
        word_highlights = {
            syllable_index: classes
            for (highlight_word, syllable_index), classes in highlights.items()
            if highlight_word == word_index
        }
        written_syllables = tokenize_editor_units(word)
        can_split = (
            len(written_syllables) == int(word_data.get("syllables", 0))
            and "".join(written_syllables) == word
        )
        if word_highlights and can_split:
            for syllable_index, written_syllable in enumerate(written_syllables):
                css_classes = " ".join(sorted(word_highlights.get(syllable_index, set())))
                safe_syllable = escape(written_syllable)
                pieces.append(
                    f'<span class="{css_classes}">{safe_syllable}</span>'
                    if css_classes
                    else safe_syllable
                )
        elif word_highlights:
            css_classes = " ".join(
                sorted({css_class for classes in word_highlights.values() for css_class in classes})
            )
            pieces.append(f'<span class="{css_classes}">{escape(word)}</span>')
        else:
            pieces.append(escape(word))
        cursor = start + len(word)
    pieces.append(escape(text[cursor:]))
    return "".join(pieces)


def _stanza_rhyme_failed(report: dict, first_line: int) -> bool:
    last_line = first_line + 3
    relevant = [
        check
        for check in report.get("rhyme_checks", [])
        if first_line <= int(check["source_line"]) - 1 <= last_line
        and int(check["target_line"]) - 1 <= last_line
    ]
    return len(relevant) < 3 or any(not check["passed"] for check in relevant)


def result_dashboard_html(report: dict) -> str:
    summary = report["summary"]
    meter_total = int(summary["meter_total"])
    meter_passed = int(summary["meter_passed"])
    meter_states = {line.get("meter_status") for line in report["lines"]}
    if meter_total and meter_passed == meter_total:
        meter_kind, meter_label = "pass", "พยางค์ผ่าน"
    elif "ควรตรวจ" in meter_states and "ไม่ผ่าน" not in meter_states:
        meter_kind, meter_label = "review", "พยางค์ควรตรวจ"
    else:
        meter_kind, meter_label = "fail", "พยางค์ไม่ผ่าน"

    rhyme_total = int(summary["rhyme_total"])
    rhyme_passed = int(summary["rhyme_passed"])
    rhyme_kind = "pass" if rhyme_total and rhyme_passed == rhyme_total else "fail"
    rhyme_label = "สัมผัสผ่าน" if rhyme_kind == "pass" else "สัมผัสไม่ผ่าน"

    stanza_count = max(1, math.ceil(report["line_count"] / 4))
    baht_count = math.ceil(report["line_count"] / 2)
    highlights = _rhyme_highlights(report)
    stanza_cards: list[str] = []
    for stanza_index in range(stanza_count):
        first_line = stanza_index * 4
        stanza_lines = report["lines"][first_line : first_line + 4]
        warning = ""
        if _stanza_rhyme_failed(report, first_line):
            warning = (
                '<div class="result-rhyme-warning">'
                '<svg class="result-rhyme-warning-icon" viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M12 3 22 21H2L12 3Z"></path><line x1="12" y1="9" x2="12" y2="14"></line>'
                '<line x1="12" y1="18" x2="12.01" y2="18"></line></svg>'
                "<strong>ไม่สามารถตรวจจับสัมผัสได้ครบ</strong></div>"
            )
        wak_cards: list[str] = []
        for local_index, line in enumerate(stanza_lines):
            side_class = " right" if local_index % 2 else ""
            wak_cards.append(
                f'<div class="result-wak{side_class}">'
                f'<div class="result-wak-label">วรรคที่ {line["index"] + 1}</div>'
                f'<div class="result-wak-text">{_highlighted_line_text(line, highlights.get(line["index"], {}))}</div>'
                "</div>"
            )
            if local_index in {1, 3}:
                wak_cards.append(
                    f'<div class="result-baht-label">บาทที่ {(line["index"] // 2) + 1}</div>'
                )
        stanza_cards.append(
            '<section class="result-stanza">'
            f'<div class="result-stanza-title">บทที่ {stanza_index + 1} --</div>'
            f'{warning}<div class="result-poem-grid">{"".join(wak_cards)}</div>'
            "</section>"
        )

    return f"""
    <section class="result-section" aria-label="ผลการตรวจ">
      <div class="result-heading-row">
        <h2><span class="step">2</span> ผลการตรวจ</h2>
        {_result_status(meter_kind, meter_label)}
        {_result_status(rhyme_kind, rhyme_label)}
      </div>
      <div class="result-overview">
        <div class="result-structure-card">
          <div class="result-score-ring"><strong>{summary['structural_score']}%</strong><span>โครงสร้าง</span></div>
          <div class="result-structure-copy">
            <small>สรุปการตรวจโครงสร้าง</small>
            <h3>ผ่าน {summary['passed_checks']} จาก {summary['total_checks']} กฎที่ตรวจ</h3>
            <p>คิดเป็น {summary['structural_score']}% ของกฎด้านจำนวนพยางค์ จังหวะ และสัมผัสที่ระบบตรวจได้</p>
          </div>
        </div>
        <div class="result-counts" aria-label="จำนวนบท บาท และวรรค">
          <div class="result-count-card"><strong>บท</strong><span>{stanza_count}</span></div>
          <div class="result-count-card"><strong>บาท</strong><span>{baht_count}</span></div>
          <div class="result-count-card"><strong>วรรค</strong><span>{report['line_count']}</span></div>
        </div>
      </div>
      <div class="result-poem-card">{"".join(stanza_cards)}</div>
    </section>
    """


def result_issues_html(report: dict) -> str:
    syllable_issues = [
        line for line in report["lines"] if line.get("meter_status") != "ผ่าน"
    ]
    rhyme_issues = [
        check for check in report.get("rhyme_checks", []) if not check.get("passed")
    ]
    sections: list[str] = []

    if syllable_issues:
        cards: list[str] = []
        for line in syllable_issues:
            review_class = " review" if line.get("meter_status") == "ควรตรวจ" else ""
            status_text = "ควรตรวจ" if review_class else "ไม่ผ่านเกณฑ์"
            cards.append(
                f'<div class="result-issue-card result-syllable-card{review_class}">'
                f'<div class="result-issue-reason"><span aria-hidden="true">×</span>จำนวนทั้งหมด {line["syllable_count"]} พยางค์ / {status_text}</div>'
                '<div class="result-syllable-detail">'
                f'<div class="result-issue-text">{escape(line["text"])}</div>'
                f'<div class="result-issue-meta">วรรค {line["index"] + 1} · {escape(line["wak_name"])}</div>'
                "</div>"
                "</div>"
            )
        sections.append(
            '<section class="result-issue-section"><div class="result-issue-heading">'
            '<span aria-hidden="true">!</span> พยางค์ที่ต้องตรวจ</div>'
            f'<div class="result-issue-list">{"".join(cards)}</div></section>'
        )

    if rhyme_issues or not report.get("rhyme_checks"):
        cards = []
        for check in rhyme_issues:
            if "target" in check:
                pair = f'{check["source"]} ↔ {check["target"]}'
            else:
                candidates = ", ".join(
                    f'{item["position"]}:{item["syllable"]}' for item in check.get("candidates", [])
                )
                pair = f'{check["source"]} → [{candidates}]'
            cards.append(
                '<div class="result-issue-card">'
                f'<div class="result-rhyme-rule">× {escape(check["rule"])}</div>'
                f'<div class="result-rhyme-detail"><strong>{escape(pair)}</strong> · วรรค {check["source_line"]} → {check["target_line"]} · ไม่พบเสียงสัมผัส</div>'
                "</div>"
            )
        if not cards:
            cards.append(
                '<div class="result-issue-card"><div class="result-rhyme-rule">× ไม่พบจุดสัมผัสที่ตรวจได้</div>'
                '<div class="result-rhyme-detail">ระบบไม่พบพยางค์ที่เพียงพอสำหรับตรวจสัมผัสของบทนี้</div></div>'
            )
        sections.append(
            '<section class="result-issue-section"><div class="result-issue-heading">'
            '<span aria-hidden="true">!</span> สัมผัสที่ต้องตรวจ</div>'
            f'<div class="result-issue-list">{"".join(cards)}</div></section>'
        )
    return "".join(sections)


st.markdown(
    """
<section class="hero">
  <h1 class="thai-mark">ผังกลอน</h1>
  <div class="ornament" aria-hidden="true"><span class="seal-dot"></span></div>
  <a class="project-link" href="https://github.com/Warit-Yuv/llm-Thai-poem-writer" target="_blank" rel="noopener noreferrer">KLON PAD RHYME CHECKER</a>
</section>
""",
    unsafe_allow_html=True,
)

st.markdown("## <span class='step'>1</span> ใส่กลอน", unsafe_allow_html=True)
if "poem_input" not in st.session_state:
    st.session_state.poem_input = ""
if "editor_baht_count" not in st.session_state:
    st.session_state.editor_baht_count = 2

klon_type = st.segmented_control(
    "เลือกรูปแบบคำประพันธ์",
    options=[4, 8],
    default=8,
    required=True,
    format_func=lambda value: KLON_NAMES[value],
    key="klon_type",
    width="stretch",
)
klon_name = KLON_NAMES[klon_type]

if (
    st.session_state.get("editor_klon_type") != klon_type
    or st.session_state.get("editor_schema_version") != EDITOR_SCHEMA_VERSION
):
    # Rebuild only after Streamlit has received the latest text-area value.
    # Doing this in the selector callback can race with a just-pasted poem.
    load_poem_into_grid(st.session_state.poem_input, klon_type)
    st.session_state.editor_schema_version = EDITOR_SCHEMA_VERSION
    clear_analysis()

# The hidden bridge sends only the latest raw textarea value after a short
# debounce. Its callback runs before this script rerenders, so the visible grid
# is always populated by the project's Python/pyThaiNLP pipeline. JavaScript
# never segments Thai text or decides whether a poem passes.
LIVE_PREVIEW_BRIDGE(
    canonical_text=st.session_state.poem_input,
    debounce_ms=450,
    default=None,
    key="live_preview_bridge",
    on_change=apply_live_preview_bridge,
)

st.markdown(
    '<div class="poem-editor-heading"><strong>ตารางคำและเส้นทางสัมผัส</strong></div>',
    unsafe_allow_html=True,
)
render_poem_editor(klon_type)

with st.container(key="input_workbench"):
    text_column, sound_column = st.columns([.9, 1.35], gap="large")
    with text_column:
        st.markdown('<div class="workbench-title">วางหรือพิมพ์กลอน</div>', unsafe_allow_html=True)
        poem = st.text_area(
            "ข้อความกลอน",
            key="poem_input",
            height=165,
            placeholder="วางกลอนที่นี่",
            label_visibility="collapsed",
            on_change=preview_poem_from_text,
        )
        action_left, action_right = st.columns(2)
        action_left.button(
            "ใช้กลอนตัวอย่าง",
            key="use_example",
            on_click=use_example,
            width="stretch",
        )
        action_right.button(
            "ล้างทั้งหมด",
            key="clear_input",
            on_click=clear_input,
            width="stretch",
        )
    with sound_column:
        st.markdown(
            '<div class="workbench-title">ทดลองคำสัมผัสและวิเคราะห์เสียง</div>',
            unsafe_allow_html=True,
        )
        rhyme_columns = st.columns(2)
        first_word = rhyme_columns[0].text_input(
            "คำที่ 1",
            key="rhyme_first",
            placeholder="เช่น หมาย",
        )
        second_word = rhyme_columns[1].text_input(
            "คำที่ 2",
            key="rhyme_second",
            placeholder="เช่น กาย",
        )
        if first_word.strip() and second_word.strip():
            st.markdown(
                rhyme_lab_html(compare_rhyme(first_word, second_word)),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="rhyme-verdict"><strong>รอทดลองเสียง</strong>'
                '<span>ใส่คำให้ครบทั้งสองช่อง</span></div>',
                unsafe_allow_html=True,
            )

waks = parse_waks(poem)
line_count = len(waks)
valid_input = line_count > 0 and line_count % 4 == 0

if poem.strip() and valid_input:
    st.success(f"พร้อมตรวจ: {line_count} วรรค ({line_count // 4} บท)")
elif poem.strip():
    missing = 4 - (line_count % 4)
    st.warning(f"ขณะนี้มี {line_count} วรรค กรุณาเพิ่มอีก {missing} วรรคให้ครบบท")

analyze = st.button(
    f"ตรวจ{klon_name}",
    key="analyze",
    type="primary",
    width="stretch",
    on_click=submit_poem_for_analysis,
)

if analyze and valid_input:
    with st.spinner(f"กำลังตรวจคำอ่าน พยางค์ และสัมผัสของ{klon_name}..."):
        try:
            st.session_state.report = check_klon(poem, k_type=klon_type)
            st.session_state.analyzed_input = poem
            st.session_state.analyzed_klon_type = klon_type
            st.session_state.pop("analysis_error", None)
        except Exception as exc:
            st.session_state.pop("report", None)
            st.session_state.analysis_error = (
                "ระบบไม่สามารถวิเคราะห์ข้อความนี้ได้ กรุณาตรวจรูปแบบกลอนแล้วลองอีกครั้ง "
                f"(รหัสข้อผิดพลาด: {type(exc).__name__})"
            )

if st.session_state.get("analysis_error"):
    st.error(st.session_state.analysis_error)

report = st.session_state.get("report")
if (
    report
    and st.session_state.get("analyzed_input") == poem
    and st.session_state.get("analyzed_klon_type") == klon_type
):
    st.markdown('<span id="analysis-results-anchor"></span>', unsafe_allow_html=True)
    st.markdown(result_dashboard_html(report), unsafe_allow_html=True)
    issues_html = result_issues_html(report)
    if issues_html:
        st.markdown(issues_html, unsafe_allow_html=True)

    with st.expander("ดาวน์โหลดผลการตรวจ"):
        download_cols = st.columns(2)
        download_cols[0].download_button(
            "ดาวน์โหลด JSON",
            json.dumps(report, ensure_ascii=False, indent=2),
            file_name=f"klon_{klon_type}_report.json",
            mime="application/json",
            width="stretch",
        )
        download_cols[1].download_button(
            "ดาวน์โหลด CSV",
            report_csv(report),
            file_name=f"klon_{klon_type}_lines.csv",
            mime="text/csv",
            width="stretch",
        )

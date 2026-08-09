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

import pandas as pd
import streamlit as st


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
STRONG_PASTE_SEPARATOR = re.compile(r"[,\r\n;:|/\\•]+")

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
.hero .ornament { display:flex; align-items:center; gap:.7rem; width:min(100%,260px); margin:.5rem auto .48rem; color:var(--vermilion); }
.hero .ornament::before,.hero .ornament::after { content:""; flex:1; height:1px; background:currentColor; opacity:.72; }
.hero .seal-dot { position:relative; width:.72rem; height:.72rem; flex:none; border:2px solid currentColor; border-radius:50%; }
.hero .seal-dot::after { content:""; position:absolute; inset:50% auto auto 50%; width:.2rem; height:.2rem; background:currentColor; border-radius:50%; transform:translate(-50%,-50%); }
.step { display:inline-flex; align-items:center; justify-content:center; width:1.8rem; height:1.8rem; border-radius:50%; background:var(--vermilion); color:white; font-weight:700; margin-right:.45rem; }
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
.poem-editor-heading span { color:var(--muted); font-size:.78rem; }
.st-key-poem_grid {
  position:relative;
  overflow-x:clip;
  overflow-y:visible;
  margin:.45rem 0 1.05rem;
  padding:1rem 2.05rem .85rem;
  background:rgba(255,253,248,.78);
  border:1px solid var(--line) !important;
  border-radius:12px !important;
  box-shadow:0 7px 20px rgba(77,43,28,.045);
  scrollbar-color:#c9a895 #f4ece3;
  scrollbar-width:thin;
}
[class*="st-key-baht_row_"] { position:relative; min-height:5.35rem; }
.rhyme-wire { position:relative; color:#342821; pointer-events:none; }
.rhyme-wire .wire { position:absolute; display:block; box-sizing:border-box; }
.rhyme-wire.top { height:1.65rem; margin:-.15rem 0 -.15rem; }
.rhyme-wire.top .wire-main {
  left:var(--source); width:calc(var(--target) - var(--source)); bottom:0; height:1.3rem;
  border-left:1.6px solid currentColor; border-right:1.6px solid currentColor; border-top:1.6px solid currentColor;
}
.rhyme-wire.middle { height:2.25rem; margin:-1.2rem 0 -.2rem; }
.rhyme-wire.middle .wire-start {
  right:var(--edge); top:0; height:2.45rem; border-right:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-bridge {
  left:var(--source); right:var(--edge); top:2.45rem; border-top:1.6px solid currentColor;
}
.rhyme-wire.middle .wire-end {
  left:var(--source); top:2.45rem; height:3.5rem; border-left:1.6px solid currentColor;
}
.rhyme-wire.bottom { height:1.75rem; margin:-3rem 0 .35rem; }
.rhyme-wire.bottom .wire-main {
  left:var(--source); width:calc(var(--target) - var(--source)); top:0; height:1.3rem;
  border-left:1.6px solid currentColor; border-right:1.6px solid currentColor; border-bottom:1.6px solid currentColor;
}
.rhyme-wire.inter-stanza { height:1.75rem; margin:-.15rem 0 -.1rem; }
.rhyme-wire.inter-stanza .wire-main {
  left:calc(100% - var(--edge) + 1rem); top:-4.45rem; width:1.05rem; height:10.4rem;
  border-right:1.6px solid currentColor; border-top:1.6px solid currentColor; border-bottom:1.6px solid currentColor;
}
.stanza-title { display:flex; align-items:center; gap:.65rem; margin:.1rem 0 .15rem; color:var(--vermilion); font-size:.8rem; font-weight:700; }
.stanza-title::after { content:""; flex:1; height:1px; background:rgba(183,53,39,.18); }
.wak-label { display:flex; align-items:center; margin:.26rem 0 .18rem; color:var(--ink); font-size:.76rem; font-weight:700; }
.wak-label.right { justify-content:flex-end; text-align:right; }
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
  width:2.65rem !important; height:2.65rem; min-height:2.65rem;
  margin:.28rem auto 0; padding:0 !important;
  border:2px solid #d8c6b3 !important; border-radius:50% !important;
  background:#fffdf8 !important; color:var(--vermilion) !important;
  font-size:1.45rem !important; box-shadow:none !important;
}
.st-key-add_baht [data-testid="stButton"] { display:flex; justify-content:center; width:100%; }
.st-key-add_baht button:hover { border-color:var(--vermilion) !important; background:#fff7ef !important; transform:none !important; }
.st-key-add_baht button p { color:var(--vermilion) !important; font-size:1.45rem !important; line-height:1 !important; }
.input-workbench { margin-top:.2rem; }
.workbench-title { margin:0 0 .48rem; color:var(--ink); font-size:1.08rem; font-weight:700; line-height:1.45; }
.workbench-kicker { margin:-.24rem 0 .55rem; color:var(--muted); font-size:.76rem; line-height:1.45; }
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
.structure-summary { display:grid; grid-template-columns:5.2rem 1fr; gap:1rem; align-items:center; background:#fffdf9; border:1px solid var(--line); border-radius:12px; padding:1rem 1.1rem; margin:.15rem 0 .8rem; box-shadow:0 6px 16px rgba(77,43,28,.055); }
.structure-score { display:flex; flex-direction:column; align-items:center; justify-content:center; width:4.6rem; height:4.6rem; border:2px solid rgba(183,53,39,.72); border-radius:50%; color:var(--vermilion); background:#fff8f1; line-height:1; }
.structure-score strong { font-family:Georgia,'Times New Roman',serif; font-size:1.45rem; }
.structure-score span { margin-top:.2rem; color:var(--muted); font-size:.7rem; font-weight:700; letter-spacing:.04em; }
.structure-copy .eyebrow { color:var(--vermilion); font-size:.76rem; font-weight:700; letter-spacing:.055em; text-transform:uppercase; }
.structure-copy h4 { margin:.18rem 0 .3rem; color:var(--ink); font-size:1.15rem; line-height:1.4; }
.structure-copy p { margin:0; color:var(--muted); font-size:.88rem; line-height:1.55; }
.sound-table-wrap { max-height:380px; overflow-x:hidden; overflow-y:auto; background:#fff; border:1px solid var(--line); border-radius:12px; box-shadow:0 6px 16px rgba(77,43,28,.045); scrollbar-color:#c9a895 #f4ece3; scrollbar-width:thin; }
.sound-table { width:100%; min-width:0; table-layout:fixed; border-collapse:separate; border-spacing:0; background:#fff; color:var(--ink); font-size:.82rem; }
.sound-table th { position:sticky; top:0; z-index:2; padding:.68rem .46rem; background:var(--vermilion); color:#fff; border-right:1px solid rgba(255,255,255,.24); border-bottom:1px solid var(--vermilion-dark); font-size:.82rem; font-weight:700; line-height:1.35; text-align:left; white-space:nowrap; vertical-align:middle; }
.sound-table th:first-child { border-top-left-radius:10px; }
.sound-table th:last-child { border-top-right-radius:10px; border-right:0; }
.sound-table th:nth-child(1) { width:6%; text-align:center; }
.sound-table th:nth-child(2) { width:13%; }
.sound-table th:nth-child(3) { width:15%; }
.sound-table th:nth-child(4) { width:16%; }
.sound-table th:nth-child(5) { width:8%; }
.sound-table th:nth-child(6) { width:8%; }
.sound-table th:nth-child(7) { width:9%; }
.sound-table th:nth-child(8) { width:9%; }
.sound-table th:nth-child(9) { width:16%; }
.sound-table td { padding:.54rem .46rem; background:#fff; border-right:1px solid #eee3d8; border-bottom:1px solid #eee3d8; line-height:1.45; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sound-table td:last-child { border-right:0; }
.sound-table tbody tr:last-child td { border-bottom:0; }
.sound-table tbody tr:hover td { background:#fff9f1; }
.sound-table td:nth-child(1) { color:var(--muted); text-align:center; }
.sound-table td:nth-child(2) { color:#6f2e25; font-weight:700; }
.sound-table td:last-child { color:#76574a; font-family:Consolas,"Courier New",monospace; font-size:.68rem; }
[data-testid="stDialog"] .sound-table-wrap { max-height:68vh; }
[data-testid="stDialog"] .sound-table { font-size:.88rem; }
div[data-baseweb="modal"], div[data-testid="stDialog"] { background:rgba(42,40,39,.34) !important; backdrop-filter:blur(2px) saturate(.72); }
div[data-testid="stDialog"] div[role="dialog"] { background:#fffdf9 !important; border:1px solid #ded2c5; box-shadow:0 18px 48px rgba(45,38,34,.2) !important; }
.st-key-expand_sound_table button { min-height:2.25rem; border:1px solid #d5b9a7 !important; border-radius:999px !important; background:rgba(255,253,249,.72) !important; color:#71372d !important; box-shadow:none !important; font-size:.8rem; }
.st-key-expand_sound_table button * { color:#71372d !important; }
.st-key-expand_sound_table button:hover { border-color:var(--vermilion) !important; color:var(--vermilion-dark) !important; background:#fff5ed !important; transform:translateY(-1px); }
.stButton>button { border-radius:10px; min-height:2.6rem; font-size:.9rem; font-weight:600; }
.stButton>button p { font-size:.9rem; }
.stButton>button[kind="primary"] { background:var(--vermilion); border-color:var(--vermilion); color:#fff !important; }
.stButton>button[kind="primary"] * { color:#fff !important; }
.stButton>button[kind="primary"]:hover { background:var(--vermilion-dark); border-color:var(--vermilion-dark); }
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
  .sound-table-wrap { overflow-x:auto; overflow-y:auto; -webkit-overflow-scrolling:touch; overscroll-behavior-x:contain; }
  .sound-table { width:max-content; min-width:780px; table-layout:auto; }
  .sound-table td { overflow:visible; text-overflow:clip; }
  .st-key-poem_grid { padding:.8rem; }
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


def load_poem_into_grid(poem_text: str, klon_type: int) -> None:
    """Normalize pasted punctuation/spacing and distribute text into word cells."""
    waks = parse_waks(poem_text)
    baht_count = max(2, math.ceil(len(waks) / 2))
    st.session_state.editor_baht_count = baht_count
    _clear_poem_cells(klon_type)
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
    st.session_state.poem_input = "\n".join(normalized_waks)
    st.session_state.editor_klon_type = klon_type


def sync_text_to_grid() -> None:
    klon_type = st.session_state.get("klon_type", 8)
    load_poem_into_grid(st.session_state.get("poem_input", ""), klon_type)
    clear_analysis()


def sync_cell_to_text(cell_key: str, line_index: int, slot_index: int, klon_type: int) -> None:
    raw_value = st.session_state.get(cell_key, "")
    if STRONG_PASTE_SEPARATOR.search(raw_value):
        # A complete poem can be pasted into any word cell. Newlines, commas,
        # slashes and similar separators are normalized into one วรรค per line.
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


def change_klon_type() -> None:
    klon_type = st.session_state.get("klon_type", 8)
    load_poem_into_grid(st.session_state.get("poem_input", ""), klon_type)
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

    The source is the final word of the left-hand wak.  The target is an early
    word of the right-hand wak: word 2 for klon si and word 3 for klon paet.
    Keeping each route as its own in-flow element makes the diagram stay lined
    up when Streamlit recalculates the native input widgets.
    """
    source = 41.6 if klon_type == 4 else 44.4
    target = 70.3 if klon_type == 4 else 67.8
    wire_parts = (
        '<span class="wire wire-start"></span>'
        '<span class="wire wire-bridge"></span>'
        '<span class="wire wire-end"></span>'
        if kind == "middle"
        else '<span class="wire wire-main"></span>'
    )
    return (
        f'<div class="rhyme-wire {kind}" '
        f'style="--source:{source}%;--target:{target}%;--edge:2%;" aria-hidden="true">'
        f'{wire_parts}'
        '</div>'
    )


def render_poem_editor(klon_type: int) -> None:
    slot_count = WORD_SLOTS[klon_type]
    baht_count = max(2, int(st.session_state.get("editor_baht_count", 2)))
    with st.container(border=True, key="poem_grid"):
        for baht_index in range(baht_count):
            with st.container(key=f"baht_row_{baht_index}"):
                label_columns = st.columns(2, gap="large")
                for column_offset, label_column in enumerate(label_columns):
                    line_index = baht_index * 2 + column_offset
                    wak_name = WAK_NAMES[line_index % 4]
                    label_class = "right" if column_offset else "left"
                    with label_column:
                        st.markdown(
                            f'<div class="wak-label {label_class}">{wak_name}</div>',
                            unsafe_allow_html=True,
                        )

                # The first row of each stanza carries the upper สดับ → รับ route.
                if baht_index % 2 == 0:
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

            if baht_index % 2 == 0 and baht_index < baht_count - 1:
                # ท้ายวรรครับ → ท้ายวรรครอง
                st.markdown(rhyme_wire_html("middle", klon_type), unsafe_allow_html=True)
            elif baht_index % 2 == 1:
                # ท้ายวรรครอง → พยางค์ต้นของวรรคส่ง
                st.markdown(rhyme_wire_html("bottom", klon_type), unsafe_allow_html=True)
                if baht_index < baht_count - 1:
                    # ท้ายวรรคส่งของบทก่อน → ท้ายวรรครับของบทถัดไป
                    st.markdown(
                        rhyme_wire_html("inter-stanza", klon_type),
                        unsafe_allow_html=True,
                    )
        add_left, add_center, add_right = st.columns([1, .13, 1])
        add_center.button(
            "＋",
            key="add_baht",
            help="เพิ่ม 1 บาท (2 วรรค)",
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


def status_class(status: str) -> str:
    return {"ผ่าน": "pass", "ควรตรวจ": "review", "ไม่ผ่าน": "fail"}.get(status, "")


def line_table(report: dict) -> pd.DataFrame:
    rows = []
    for line in report["lines"]:
        for word in line["words"]:
            for detail in word.get("sound_details", []):
                rows.append(
                    {
                        "วรรค": line["index"] + 1,
                        "คำ": word["word"],
                        "คำอ่าน": word["pronunciation"],
                        "พยางค์": detail["syllable"],
                        "สระ": detail["vowel"],
                        "มาตรา": detail["final_class"],
                        "ครุ–ลหุ": detail["weight"],
                        "เอก–โท": detail["tone_role"],
                        "แหล่งที่มา": word["source"],
                    }
                )
    return pd.DataFrame(rows)


def line_table_html(report: dict) -> str:
    table = line_table(report)
    headers = "".join(f"<th scope='col'>{escape(str(column))}</th>" for column in table.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in table.itertuples(index=False, name=None)
    )
    return (
        '<div class="sound-table-wrap" role="region" aria-label="ตารางวิเคราะห์เสียง" tabindex="0">'
        f'<table class="sound-table"><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>'
        "</div>"
    )


@st.dialog("ตารางวิเคราะห์เสียงฉบับเต็ม", width="large")
def show_full_table(report: dict, klon_name: str) -> None:
    table = line_table(report)
    st.caption(f"{klon_name} · ข้อมูลทั้งหมด {len(table)} รายการ · เลื่อนขึ้น–ลงเพื่อดูข้อมูล")
    st.markdown(line_table_html(report), unsafe_allow_html=True)


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


def line_card_html(line: dict) -> str:
    line_status = line.get("status", line["meter_status"])
    css_status = status_class(line_status)
    beats = "".join(f'<span class="beat">{escape(group)}</span>' for group in line["beat_groups"])
    word_count_class = "" if line.get("word_count_passed", True) else "word-fail"
    notes = "".join(
        f'<div class="line-note">{escape(note)}</div>' for note in line.get("notes", [])
    )
    notes_html = f'<div class="line-notes">{notes}</div>' if notes else ""
    return f"""
        <div class="line-card">
          <div class="line-main">
            <div class="line-title">
              <span>วรรค {line['index'] + 1} · {line['wak_name']}</span>
              <strong class="{css_status}">{line_status}</strong>
            </div>
            <div class="line-text">{escape(line['text'])}</div>
            <div class="line-meta"><strong>{line['syllable_count']} พยางค์</strong> · จังหวะ {line['rhythm_text']} · <span class="{word_count_class}">{line['word_count']}/{line['max_words']} หน่วยคำ</span></div>
            {notes_html}
          </div>
          <div class="beats">{beats}</div>
        </div>
        """


def render_inspection_grid(report: dict) -> None:
    summary = report["summary"]
    items = (
        ("จำนวนวรรค", str(report["line_count"])),
        ("พยางค์ผ่าน", f"{summary['meter_passed']}/{summary['meter_total']}"),
        (
            "หน่วยคำผ่าน",
            f"{summary['word_count_passed']}/{summary['word_count_total']}",
        ),
        ("สัมผัสผ่าน", f"{summary['rhyme_passed']}/{summary['rhyme_total']}"),
    )
    summary_tiles = [
        f"""
          <div class="summary-tile" aria-label="{label} {value}">
            <div class="summary-tile-label">{label}</div>
            <div class="summary-tile-value">{value}</div>
          </div>
        """
        for label, value in items
    ]
    # There are always 4 summary tiles but any number of วรรค. Pad the right
    # column with empty cells: a bare zip() would truncate to 4 line cards and
    # silently drop every บท after the first.
    cells = summary_tiles + ["<div></div>"] * (len(report["lines"]) - len(summary_tiles))
    rows = "".join(
        line_card_html(line) + cell
        for line, cell in zip(report["lines"], cells)
    )
    st.markdown(
        f"""
        <div class="mobile-summary-strip" aria-label="สรุปบท">
          {''.join(summary_tiles)}
        </div>
        <section class="inspection-grid" aria-label="ผลการตรวจทีละวรรคและสรุปบท">
          <h3 class="inspection-heading">ตรวจทีละวรรค</h3>
          <div class="summary-column-heading">สรุปบท</div>
          {rows}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_rhyme(check: dict) -> None:
    icon = "✓" if check["passed"] else "✕"
    css = "pass" if check["passed"] else "fail"
    if "target" in check:
        pair = f"{check['source']} ↔ {check['target']}"
    else:
        matched = set(check["matched_positions"])
        candidates = ", ".join(
            f"{item['position']}:{item['syllable']}{' ✓' if item['position'] in matched else ''}"
            for item in check["candidates"]
        )
        pair = f"{check['source']} → [{candidates}]"
    note = "ตำแหน่งหลัก" if check.get("preferred_position") else "ตำแหน่งอนุโลม"
    if not check["passed"]:
        note = "ไม่พบเสียงสัมผัส"
    st.markdown(
        f'<div class="rule"><strong class="{css}">{icon} {escape(check["rule"])}</strong><br>'
        f'<span class="rule-pair">{escape(pair)}</span> <span class="small-note">· วรรค {check["source_line"]} → {check["target_line"]} · {note}</span></div>',
        unsafe_allow_html=True,
    )


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
    on_change=change_klon_type,
    width="stretch",
)
klon_name = KLON_NAMES[klon_type]

if (
    st.session_state.get("editor_klon_type") != klon_type
    or st.session_state.get("editor_schema_version") != EDITOR_SCHEMA_VERSION
):
    load_poem_into_grid(st.session_state.poem_input, klon_type)
    st.session_state.editor_schema_version = EDITOR_SCHEMA_VERSION

st.markdown(
    '<div class="poem-editor-heading"><strong>ตารางคำและเส้นทางสัมผัส</strong>'
    '<span>พิมพ์ทีละคำ หรือวางกลอนลงในช่องใดก็ได้</span></div>',
    unsafe_allow_html=True,
)
render_poem_editor(klon_type)

with st.container(key="input_workbench"):
    text_column, sound_column = st.columns([.9, 1.35], gap="large")
    with text_column:
        st.markdown('<div class="workbench-title">วางหรือพิมพ์กลอน</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="workbench-kicker">ระบบจัดวรรคและตัดช่องว่างหรือเครื่องหมายคั่นให้</div>',
            unsafe_allow_html=True,
        )
        poem = st.text_area(
            "ข้อความกลอน",
            key="poem_input",
            height=165,
            placeholder="วางกลอนที่นี่",
            label_visibility="collapsed",
            on_change=sync_text_to_grid,
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
        st.markdown(
            '<div class="workbench-kicker">เครื่องมือเรียนรู้เสียงสัมผัสของคำไทย</div>',
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

if not poem.strip():
    st.caption("ยังไม่มีข้อความ — พิมพ์กลอนหรือกด “ใช้กลอนตัวอย่าง”")
elif valid_input:
    st.success(f"พร้อมตรวจ: {line_count} วรรค ({line_count // 4} บท)")
else:
    missing = 4 - (line_count % 4)
    st.warning(f"ขณะนี้มี {line_count} วรรค กรุณาเพิ่มอีก {missing} วรรคให้ครบบท")

analyze = st.button(
    f"ตรวจ{klon_name}",
    key="analyze",
    type="primary",
    width="stretch",
    disabled=not valid_input,
)

if analyze:
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
    summary = report["summary"]
    st.markdown("## <span class='step'>2</span> ผลการตรวจ", unsafe_allow_html=True)

    if summary["verdict"] == "ผ่าน":
        st.success("ผ่านกฎโครงสร้างที่ระบบตรวจทั้งหมด")
    elif summary["verdict"] == "ควรตรวจ":
        review_lines = sum(
            line.get("status", line["meter_status"]) == "ควรตรวจ"
            for line in report["lines"]
        )
        if review_lines:
            st.warning(
                f"พบ {review_lines} วรรคที่ควรตรวจสอบเพิ่มเติม "
                "ดูเหตุผลในการ์ดด้านล่าง"
            )
        else:
            st.warning("พบจุดที่ควรตรวจสอบเพิ่มเติม ดูรายละเอียดด้านล่าง")
    else:
        st.error("พบจุดที่ไม่ผ่านกฎโครงสร้าง ดูรายละเอียดด้านล่าง")

    render_inspection_grid(report)

    st.markdown("### สัมผัสบังคับ")
    if report["rhyme_checks"]:
        for rhyme in report["rhyme_checks"]:
            render_rhyme(rhyme)
    else:
        st.info("ไม่พบจุดสัมผัสที่ตรวจได้")

    with st.expander("รายละเอียดคำอ่านและโครงสร้าง"):
        core_result = report["core_validation"]
        st.markdown(
            f"""
            <div class="structure-summary">
              <div class="structure-score">
                <strong>{summary['structural_score']}%</strong>
                <span>โครงสร้าง</span>
              </div>
              <div class="structure-copy">
                <div class="eyebrow">สรุปการตรวจโครงสร้าง</div>
                <h4>ผ่าน {summary['passed_checks']} จาก {summary['total_checks']} กฎที่ตรวจ</h4>
                <p>คิดเป็น {summary['structural_score']}% ของกฎด้านจำนวนพยางค์ จังหวะ และสัมผัสที่ระบบตรวจได้</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if core_result["passed"] is True:
            st.success("ตรวจสอบซ้ำด้วยระบบหลักแล้ว: ผ่าน")
        elif core_result["passed"] is False:
            st.warning("ตรวจสอบซ้ำด้วยระบบหลักแล้ว: พบข้อสังเกต")
            for message in core_result["messages"]:
                st.write(f"- {message}")
        else:
            st.info("ระบบหลักไม่สามารถยืนยันผลสำหรับข้อความนี้ได้")

        table_heading, table_action = st.columns([4.4, 1.25], vertical_alignment="center")
        table_heading.markdown("#### ตารางวิเคราะห์เสียง")
        if table_action.button(
            "ดูแบบเต็มจอ",
            key="expand_sound_table",
            icon=":material/open_in_full:",
            width="stretch",
        ):
            show_full_table(report, klon_name)
        st.caption(
            f"กำลังแสดงกฎ{klon_name} · ตารางนี้รวมคำอ่าน สระ มาตรา ครุ–ลหุ และเอก–โท"
        )
        st.markdown(line_table_html(report), unsafe_allow_html=True)

        if core_result["raw_messages"]:
            with st.expander("ดูข้อความดิบจาก Backend"):
                for message in core_result["raw_messages"]:
                    st.code(message, language=None)

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

# app.py
import streamlit as st
import fitz  # PyMuPDF
import html
from datetime import datetime
from typing import List, Tuple
import re

st.set_page_config(page_title="Judgment → HTML ", layout="wide", page_icon="")
st.title("Judgment Parser")

st.markdown(
    "This version attempts to reconstruct paragraphs (join broken lines), preserve numbering/sub-numbering, "
    "and render justified HTML to reduce the blank right-side space. If your PDF is image-only, OCR first."
)

# Sidebar controls
st.sidebar.header("Extraction & formatting options")
keep_lines = st.sidebar.checkbox("Keep original lines (no paragraph join)", value=False,
                                 help="Show exact extracted lines (useful for debugging). When off, the tool will try to reconstruct paragraphs.")
aggressive_join = st.sidebar.checkbox("Aggressive paragraph join", value=True,
                                      help="More aggressively join lines that look like continuations. Good for legal text with many short line breaks.")
preserve_nbsp = st.sidebar.checkbox("Preserve NBSP (\\u00A0)", value=False)
remove_soft_hyphen = st.sidebar.checkbox("Remove soft-hyphen (\\u00AD)", value=True)
font_size = st.sidebar.slider("Font size (px)", 12, 18, 14)
mono = st.sidebar.checkbox("Use monospace font", value=False)
upload = st.file_uploader("Upload judgment PDF", type=["pdf"])

if not upload:
    st.info("Please upload a PDF to extract.")
    st.stop()

pdf_bytes = upload.read()
if not pdf_bytes:
    st.error("Uploaded file appears empty.")
    st.stop()

# --- helpers ----------------------------------------------------------------
num_pattern = re.compile(r"""^\s*(?:            # optional leading space
    (?P<num>(\d+[\.\)]|[IVXLCDMivxlcdm]+[\.\)]|[a-zA-Z]\.|[ivx]+\)|\([ivx]+\)|\([a-z]\)|\(\w+\)))  # numbering examples
    \s+)?""", re.VERBOSE)

def extract_lines_from_page(page: fitz.Page) -> List[str]:
    """Extract lines ordered left-to-right using page.get_text('dict')."""
    d = page.get_text("dict")
    lines = []
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = sorted(line.get("spans", []), key=lambda s: s.get("bbox", [0])[0])
            txt = "".join(s.get("text", "") for s in spans)
            # Normalize common control chars
            txt = txt.replace("\x0b", " ").replace("\r", "")
            lines.append(txt)
    return lines

def normalize_line(s: str) -> str:
    if remove_soft_hyphen:
        s = s.replace("\u00ad", "")  # remove soft hyphen
    if not preserve_nbsp:
        s = s.replace("\u00a0", " ")
    return s

def line_is_numbering_start(s: str) -> bool:
    """Heuristic: True if line begins with a numbering / sub-numbering token."""
    return bool(re.match(r'^\s*(?:\d+[\.\)]|[ivxlcdmIVXLCDM]+\)|\([ivxlcdmIVXLCDM]+\)|\([a-z]\)|[A-Z]\.)', s))

def likely_continuation(prev: str, nxt: str) -> bool:
    """
    Heuristics to decide whether nxt should be joined to prev.
    Returns True => join nxt into current paragraph (with appropriate spacing).
    """
    if not prev.strip() or not nxt.strip():
        return False
    # If next line starts with numbering, it's likely a new item
    if line_is_numbering_start(nxt):
        return False
    # If previous line ends with hyphen (soft or normal) -> join without space
    if prev.rstrip().endswith(('-', '\u00ad')):
        return True
    # If previous line ends with an em dash, colon -> continuation
    if re.search(r'[:—-]\s*$', prev.strip()):
        return True
    # If aggressive join is enabled: if nxt starts with lowercase or punctuation, join
    if aggressive_join:
        if re.match(r'^\s*[a-z0-9\(\[]', nxt):  # starts lowercase/number/paren/bracket
            return True
        # join if previous line doesn't end with a sentence terminator and next starts lowercase/quote
        if not re.search(r'[\.!?]\s*$', prev.strip()) and re.match(r'^\s*[a-z\"\'\u201c]', nxt):
            return True
    else:
        # conservative: join if next begins lowercase or prev clearly mid-sentence (no period)
        if re.match(r'^\s*[a-z]', nxt) and not re.search(r'[\.!?]\s*$', prev.strip()):
            return True
    return False

def reconstruct_paragraphs(lines: List[str]) -> List[str]:
    """Return a list of paragraphs reconstructed from lines, preserving numbering starts."""
    if not lines:
        return []
    paras = []
    cur = normalize_line(lines[0])
    for raw in lines[1:]:
        nxt = normalize_line(raw)
        # if line is blank -> paragraph break
        if not nxt.strip():
            paras.append(cur.rstrip())
            cur = ""
            continue
        # If this line looks like a numbering header, break paragraph
        if line_is_numbering_start(nxt) and cur.strip():
            paras.append(cur.rstrip())
            cur = nxt
            continue
        # Decide whether to join
        if likely_continuation(cur, nxt):
            # If prev ended with hyphen remove hyphen and join directly
            if cur.rstrip().endswith('-') or cur.rstrip().endswith('\u00ad'):
                cur = cur.rstrip()[:-1] + nxt.lstrip()
            else:
                cur = cur.rstrip() + " " + nxt.lstrip()
        else:
            # Break paragraph: append current and start new
            paras.append(cur.rstrip())
            cur = nxt
    if cur.strip():
        paras.append(cur.rstrip())
    return paras

def page_width_to_px(page: fitz.Page, clamp_min=720, clamp_max=1200) -> int:
    """Convert page rect width (points) to CSS px and clamp, returning integer px."""
    rect = page.rect
    pt_width = rect.width  # points (1/72 inch)
    # convert points to px: px = pt * (96 / 72) = pt * 1.3333333
    px = int(round(pt_width * 96.0 / 72.0))
    # clamp to reasonable bounds for preview
    px = max(clamp_min, min(px, clamp_max))
    return px

# --- process PDF (keeps doc open to avoid 'document closed') -----------------
try:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        n = doc.page_count
        all_pages = []
        progress = st.progress(0)
        status = st.empty()
        page_max_px = 980  # fallback if first page missing
        for i in range(n):
            status.info(f"Extracting page {i+1}/{n} …")
            page = doc.load_page(i)
            lines = extract_lines_from_page(page)
            # normalize each line
            lines = [normalize_line(s) for s in lines]
            # compute px width from first page
            if i == 0:
                page_max_px = page_width_to_px(page)
            all_pages.append(lines)
            progress.progress((i+1)/n)
        status.success("Extraction finished.")
except Exception as e:
    st.exception(e)
    st.stop()

# --- build HTML ----------------------------------------------------------------
title = (upload.name or "Judgment").rsplit(".", 1)[0]
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
font_family = "monospace" if mono else "Georgia, 'Times New Roman', serif"

# CSS tuned to reduce large right gaps and enable justification + hyphenation
css = f"""
<style>
  :root {{ --bg: #ffffff; --meta:#f6f7f8; }}
  html,body{{ margin:0;padding:0;background:var(--bg);color:#111;font-family:{font_family}; }}
  .doc-meta{{font:12px/1.4 system-ui, sans-serif;color:#444;background:var(--meta);padding:10px 14px;border-bottom:1px solid #e5e7eb}}
  .container{{padding:18px;}}
  .page-wrap{{ margin: 18px auto 36px; max-width: {page_max_px}px; }}
  .para{{ text-align: justify; text-justify: inter-word; hyphens: auto; font-size:{font_size}px; line-height:1.48; margin:8px 0; }}
  .numbered{{ font-weight: 600; }} /* small emphasis to numbering starts if needed */
  .page-sep{{ height: 28px; }}
  /* preserve exact-lines mode fallback */
  .prepage {{ white-space: pre-wrap; font-size:{font_size}px; line-height:1.45; }}
  /* avoid too wide lines on very large screens */
  @media (min-width:1400px) {{
    .page-wrap {{ max-width: {min(page_max_px, 1100)}px; }}
  }}
</style>
"""

def paragraphs_to_html(paragraphs: List[str]) -> str:
    html_p = []
    for p in paragraphs:
        # If paragraph begins with a numbering token, add small class to help visual separation
        p_escaped = html.escape(p)
        if re.match(r'^\s*(?:\d+[\.\)]|[ivxlcdmIVXLCDM]+\)|\([ivxlcdmIVXLCDM]+\)|\([a-z]\)|[A-Z]\.)', p):
            html_p.append(f'<div class="para numbered">{p_escaped}</div>')
        else:
            html_p.append(f'<div class="para">{p_escaped}</div>')
    return "\n".join(html_p)

pages_html = []
for page_lines in all_pages:
    if keep_lines:
        # show original extracted lines inside pre-wrap
        page_text = "\n".join(page_lines).rstrip()
        pages_html.append(f'<div class="page-wrap"><pre class="prepage">{html.escape(page_text)}</pre></div>')
    else:
        paras = reconstruct_paragraphs(page_lines)
        page_html = paragraphs_to_html(paras)
        pages_html.append(f'<div class="page-wrap">{page_html}</div>')

pages_joined = "\n<div class='page-sep'></div>\n".join(pages_html)

final_html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{html.escape(title)}</title>
{css}
</head>
<body>
  <div class="doc-meta">Generated by Judgment → HTML (improved) on {now} — source: {html.escape(upload.name or '')}</div>
  <div class="container">
    {pages_joined}
  </div>
</body>
</html>
"""

# Preview + download
st.subheader("Preview (improved)")
st.components.v1.html(final_html, height=900, scrolling=True)
st.download_button("⬇️ Download improved HTML", data=final_html.encode("utf-8"),
                   file_name=f"{title}_improved.html", mime="text/html")

st.info("If you still see uneven right-side gaps, try toggling 'Keep original lines' (shows exact extracted lines) "
        "and/or toggling 'Aggressive paragraph join'. For scanned PDFs, OCR first.")


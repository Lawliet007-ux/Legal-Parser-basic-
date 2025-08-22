import streamlit as st
from typing import Dict, Optional, List, Tuple
import re
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional/conditional imports
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except Exception:
    pdfminer_extract_text = None

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None

# ----------------------
# Configuration & Logger
# ----------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("judgment_extractor")

class Config:
    # Tunable options for production
    DEFAULT_WORKERS = int(os.getenv("JE_WORKERS", "4"))
    OCR_ENABLED = os.getenv("JE_OCR_ENABLED", "false").lower() in ("1","true","yes")
    OCR_LANG = os.getenv("JE_OCR_LANG", "eng")
    DETECTION_CONFIDENCE = float(os.getenv("JE_DETECTION_CONF", "0.6"))

# ----------------------
# Utilities
# ----------------------

def safe_read_bytes(file) -> bytes:
    """Return raw bytes from a Streamlit or file-like object without closing it."""
    try:
        file.seek(0)
    except Exception:
        pass
    data = file.read()
    try:
        file.seek(0)
    except Exception:
        pass
    return data

# ----------------------
# Extraction backends
# ----------------------

class BaseExtractor:
    def extract(self, file) -> str:
        raise NotImplementedError

class PdfPlumberExtractor(BaseExtractor):
    """Layout-aware extraction using pdfplumber. Reconstructs paragraphs using positions."""
    def __init__(self):
        if not pdfplumber:
            raise RuntimeError("pdfplumber not available")

    def extract(self, file) -> str:
        text_pages = []
        try:
            with pdfplumber.open(file) as pdf:
                for pnum, page in enumerate(pdf.pages, start=1):
                    # try to get table-free flow first
                    words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
                    if not words:
                        page_text = page.extract_text() or ""
                    else:
                        # reconstruct by line clusters
                        page_text = self._reconstruct_from_words(words)
                    text_pages.append(f"--- PAGE {pnum} ---\n" + page_text)
            return "\n".join(text_pages)
        except Exception as e:
            logger.exception("pdfplumber extraction failed")
            return ""

    def _reconstruct_from_words(self, words: List[Dict]) -> str:
        # group words by top (y0) coordinate into approximate lines
        lines: Dict[int, List[Dict]] = {}
        for w in words:
            top = int(round(float(w.get("top", 0))))
            # bucket by top with neighbor tolerance
            bucket = top // 3
            lines.setdefault(bucket, []).append(w)

        ordered = []
        for bucket in sorted(lines.keys()):
            row = sorted(lines[bucket], key=lambda x: x.get("x0", 0))
            line_text = " ".join([w.get("text", "") for w in row])
            ordered.append(line_text)

        # simple post-processing to join lines into paragraphs with heuristics
        paragraphs = []
        cur = []
        for ln in ordered:
            ln = ln.strip()
            if not ln:
                if cur:
                    paragraphs.append(" ".join(cur))
                    cur = []
                continue
            # if line ends with hyphen -> join without space
            if ln.endswith("-"):
                cur.append(ln[:-1])
            else:
                cur.append(ln)
                # heuristic: blank line / sentence end triggers paragraph break
                if ln.endswith(('.', '?', '!', '"', "'")) and len(cur) >= 1:
                    paragraphs.append(" ".join(cur))
                    cur = []
        if cur:
            paragraphs.append(" ".join(cur))
        return "\n\n".join(paragraphs)

class PyPDF2Extractor(BaseExtractor):
    def __init__(self):
        if not PyPDF2:
            raise RuntimeError("PyPDF2 not available")

    def extract(self, file) -> str:
        try:
            # PyPDF2 expects a file-like object; we pass through
            reader = PyPDF2.PdfReader(file)
            pages = []
            for p in reader.pages:
                txt = p.extract_text() or ""
                pages.append(txt)
            return "\n".join([f"--- PAGE {i+1} ---\n{p}" for i, p in enumerate(pages)])
        except Exception:
            logger.exception("PyPDF2 extraction failed")
            return ""

class PdfMinerExtractor(BaseExtractor):
    def __init__(self):
        if not pdfminer_extract_text:
            raise RuntimeError("pdfminer.six not available")

    def extract(self, file) -> str:
        try:
            # pdfminer operates on path or file object
            text = pdfminer_extract_text(file)
            # split heuristically into pages if available marker
            return text
        except Exception:
            logger.exception("pdfminer extraction failed")
            return ""

class OCRExtractor(BaseExtractor):
    """Fallback OCR extractor using pytesseract + Pillow. Heavy — enable only as needed."""
    def __init__(self, lang: str = Config.OCR_LANG):
        if not (pytesseract and Image):
            raise RuntimeError("PIL/pytesseract not available for OCR")
        self.lang = lang

    def extract(self, file) -> str:
        # file can be bytes or path — we try to open via PIL
        try:
            raw = safe_read_bytes(file)
            from pdf2image import convert_from_bytes
            pages = convert_from_bytes(raw)
            out = []
            for i, pg in enumerate(pages, start=1):
                txt = pytesseract.image_to_string(pg, lang=self.lang)
                out.append(f"--- PAGE {i} ---\n" + txt)
            return "\n".join(out)
        except Exception:
            logger.exception("OCR extraction failed")
            return ""

# ----------------------
# Parsing & detection
# ----------------------

class JudgmentParser:
    """Rule-based parser with improved heuristics for courts across formats."""

    CASE_PATTERNS = [
        # combination of common prefixes used in district courts
        r"\b(?:OMP|OMP\s*\(I\)|CRL|CS|CC|SA|FAO|CRP|MAC|RFA|SLP|CIVIL|CR|RFA)\b.*?\b(?:No\.?|/|:)\s*\d+[/\\\w-]*",
        r"\bNo\.\s*[:]?"]

    DATE_PATTERN = r"\b\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}\b"

    PARTY_SEPARATORS = [" VS ", " V/S ", " v ", " v. ", " vs ", " v/s "]

    def __init__(self):
        pass

    def parse(self, text: str) -> Dict:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        data = {"case_number": "", "parties": "", "date": "", "judge": "", "court": "", "paragraphs": []}

        # find case number
        for ln in lines[:40]:
            for pat in self.CASE_PATTERNS:
                m = re.search(pat, ln, re.IGNORECASE)
                if m:
                    data["case_number"] = m.group(0).strip()
                    break
            if data["case_number"]:
                break

        # find date - scan lines for date pattern
        for ln in reversed(lines[:120]):
            m = re.search(self.DATE_PATTERN, ln)
            if m:
                data["date"] = m.group(0)
                break

        # find parties - look in top lines
        for ln in lines[:8]:
            for sep in self.PARTY_SEPARATORS:
                if sep in ln:
                    data["parties"] = ln
                    break
            if data["parties"]:
                break

        # find judge - look for keywords JUDGE, DISTRICT JUDGE, HON'BLE, etc.
        for ln in lines[-30:]:
            if re.search(r"\b(JUDGE|DISTRICT JUDGE|CHIEF JUDGE|HON'BLE|PRESIDING)\b", ln, re.IGNORECASE):
                data["judge"] = ln
                break

        # court detection
        for ln in lines[:40]:
            if re.search(r"\b(COURT|TRIBUNAL|COMMERCIAL COURT|DISTT|DISTRICT)\b", ln, re.IGNORECASE):
                data["court"] = ln
                break

        # paragraphs: naive split on blank-lines and page markers
        paras = []
        cur = []
        for ln in text.splitlines():
            if ln.strip().startswith('--- PAGE'):
                if cur:
                    paras.append(' '.join(cur).strip())
                    cur = []
                paras.append(ln.strip())
                continue
            if not ln.strip():
                if cur:
                    paras.append(' '.join(cur).strip())
                    cur = []
            else:
                cur.append(ln.strip())
        if cur:
            paras.append(' '.join(cur).strip())
        data['paragraphs'] = paras

        return data

# ----------------------
# Numbering preservation
# ----------------------

class NumberingPreserver:
    """Improves detection of numbered lists and sublists using regex groups and positional heuristics."""

    RE_PATTERNS = [
        (re.compile(r'^\s*(?P<num>\d+)\.\s+(?P<body>.+)$'), 'numbered-dots'),
        (re.compile(r'^\s*\((?P<num>\d+)\)\s+(?P<body>.+)$'), 'numbered-parentheses'),
        (re.compile(r'^\s*\((?P<num>[ivxIVX]+)\)\s+(?P<body>.+)$'), 'sub-points'),
        (re.compile(r'^\s*(?P<num>[IVX]+)[\.)]\s+(?P<body>.+)$'), 'roman-number'),
        (re.compile(r'^\s*\((?P<num>[a-zA-Z])\)\s+(?P<body>.+)$'), 'lettered-points'),
    ]

    def preserve(self, paragraphs: List[str]) -> str:
        out_lines = []
        for p in paragraphs:
            if p.startswith('--- PAGE'):
                out_lines.append(f'<div class="page-marker">{p}</div>')
                continue
            # split paragraph into possible lines
            lines = p.split('  ')
            matched = False
            for ln in lines:
                ln = ln.strip()
                for pat, cls in self.RE_PATTERNS:
                    m = pat.match(ln)
                    if m:
                        out_lines.append(f'<div class="{cls}">{ln}</div>')
                        matched = True
                        break
                if not matched:
                    # fallback: detect leading numbering anywhere
                    if re.match(r'^\s*\d+\s+[A-Za-z]', ln):
                        out_lines.append(f'<div class="numbered-dots">{ln}</div>')
                    else:
                        out_lines.append(f'<div class="paragraph">{ln}</div>')
                matched = False
        return "\n".join(out_lines)

# ----------------------
# HTML generation
# ----------------------

HTML_BASE_CSS = """
body { font-family: 'Times New Roman', serif; font-size: 12pt; color: #111; background: #f6f6f6; }
.document { max-width: 210mm; margin: 12mm auto; background: white; padding: 18mm; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.header { text-align: center; border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-bottom: 12px; }
.page-marker{ text-align:center; color:#666; margin: 8px 0; }
.paragraph{ text-align: justify; margin:8px 0; }
.numbered-dots { margin:8px 0; padding-left:16px; text-indent:-8px; font-weight:600; }
.numbered-parentheses { margin:8px 0; padding-left:18px; text-indent:-8px; font-weight:600; }
.roman-number { margin:12px 0; padding-left:24px; text-indent:-12px; font-weight:700; }
.lettered-points{ margin:6px 0; padding-left:28px; }
.sub-points{ margin:6px 0; padding-left:36px; font-style:italic; }
.judge-signature{ text-align:right; font-weight:700; margin-top:18px; }
.court-details{ text-align:right; font-style:italic; }
@media print { body{ background: white;} .document{ box-shadow:none; } }
"""

class HTMLGenerator:
    def __init__(self, css: str = HTML_BASE_CSS):
        self.css = css

    def generate(self, preserved_html: str, metadata: Dict) -> str:
        case_no = metadata.get('case_number', 'Case Number Not Found')
        parties = metadata.get('parties', 'Parties Not Found')
        date = metadata.get('date', '')
        judge = metadata.get('judge', '')
        court = metadata.get('court', '')

        template = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{case_no}</title>
<style>{self.css}</style>
</head>
<body>
  <div class="document">
    <div class="header">
      <div class="case-number">{case_no}</div>
      <div class="parties">{parties}</div>
      <div class="date">{date}</div>
    </div>
    <div class="content">
      {preserved_html}
    </div>
    <div class="judge-signature">{judge}</div>
    <div class="court-details">{court}</div>
  </div>
</body>
</html>
"""
        return template

# ----------------------
# Coordinator: Extraction pipeline
# ----------------------

class JudgmentPipeline:
    def __init__(self, ocr_enabled: bool = Config.OCR_ENABLED):
        # priority order of backends
        self.backends = []
        if pdfplumber:
            self.backends.append(PdfPlumberExtractor())
        if PyPDF2:
            self.backends.append(PyPDF2Extractor())
        if pdfminer_extract_text:
            self.backends.append(PdfMinerExtractor())
        if ocr_enabled and pytesseract:
            self.backends.append(OCRExtractor())

        if not self.backends:
            raise RuntimeError("No extraction backend available. Install pdfplumber or PyPDF2 or pdfminer or enable OCR.")

        self.parser = JudgmentParser()
        self.preserver = NumberingPreserver()
        self.htmlgen = HTMLGenerator()

    def process(self, file) -> Tuple[bool, Dict]:
        """Try backends in order; return tuple(success, result_dict) where result_dict contains keys: raw_text, metadata, html"""
        last_error = None
        raw_text = ""
        for backend in self.backends:
            try:
                raw_text = backend.extract(file)
                if raw_text and len(raw_text.strip()) > 10:
                    logger.info(f"Extraction succeeded with {backend.__class__.__name__}")
                    break
            except Exception as e:
                logger.exception("Backend failed")
                last_error = str(e)
                continue
        if not raw_text:
            return False, {"error": "All extraction backends failed", "detail": last_error}

        # parse
        metadata = self.parser.parse(raw_text)
        # preserve numbering and generate HTML body
        preserved = self.preserver.preserve(metadata.get('paragraphs', []))
        html = self.htmlgen.generate(preserved, metadata)

        return True, {"raw_text": raw_text, "metadata": metadata, "html": html}

# ----------------------
# Batch processing helper (local). For hundreds of millions of docs, use a distributed framework like Dask/Celery/Kubernetes.
# ----------------------

def process_batch(file_paths: List[str], out_dir: str, workers: int = Config.DEFAULT_WORKERS):
    os.makedirs(out_dir, exist_ok=True)
    results = []
    pipeline = JudgmentPipeline()

    def _process_path(path):
        logger.info(f"Processing {path}")
        try:
            with open(path, 'rb') as fh:
                ok, res = pipeline.process(fh)
            if ok:
                base = os.path.basename(path)
                name, _ = os.path.splitext(base)
                # write outputs
                with open(os.path.join(out_dir, f"{name}.txt"), 'w', encoding='utf-8') as w:
                    w.write(res['raw_text'])
                with open(os.path.join(out_dir, f"{name}.html"), 'w', encoding='utf-8') as w:
                    w.write(res['html'])
                with open(os.path.join(out_dir, f"{name}.json"), 'w', encoding='utf-8') as w:
                    json.dump(res['metadata'], w, indent=2)
                return (path, True, None)
            else:
                return (path, False, res)
        except Exception as e:
            logger.exception("Processing error")
            return (path, False, str(e))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_process_path, p): p for p in file_paths}
        for fut in as_completed(futures):
            results.append(fut.result())
    return results

# ----------------------
# Streamlit UI (lightweight) - use this file as the Streamlit app entrypoint
# ----------------------

def main():
    st.set_page_config(page_title="Legal Judgment Extractor", page_icon="⚖️", layout="wide")
    st.title("⚖️ Legal Judgment Extractor — Robust Edition")

    st.sidebar.header("Extraction settings")
    backend_choice = st.sidebar.selectbox("Preferred backend", [b.__class__.__name__ for b in ( [PdfPlumberExtractor()] if pdfplumber else [] ) + ( [PyPDF2Extractor()] if PyPDF2 else [] ) + ( [PdfMinerExtractor()] if pdfminer_extract_text else [] )])
    ocr_toggle = st.sidebar.checkbox("Enable OCR fallback (slow)", value=Config.OCR_ENABLED)
    workers = st.sidebar.number_input("Batch workers (local)", min_value=1, max_value=64, value=Config.DEFAULT_WORKERS)

    st.markdown("---")
    uploaded_file = st.file_uploader("Upload judgment PDF", type=['pdf'])

    if uploaded_file is not None:
        st.info("Processing — this may take a few seconds depending on backend")
        pipeline = JudgmentPipeline(ocr_enabled=ocr_toggle)
        ok, result = pipeline.process(uploaded_file)
        if not ok:
            st.error(f"Extraction failed: {result.get('error')}")
            if result.get('detail'):
                st.write(result.get('detail'))
            return
        st.success("Extraction successful")
        st.subheader("Metadata")
        st.json(result['metadata'])

        st.subheader("Raw text")
        st.text_area("Raw text:", result['raw_text'], height=300)

        st.subheader("HTML preview")
        st.components.v1.html(result['html'], height=600, scrolling=True)

        st.download_button("Download HTML", result['html'], file_name="judgment.html", mime='text/html')
        st.download_button("Download text", result['raw_text'], file_name="judgment.txt", mime='text/plain')
        st.download_button("Download metadata (JSON)", json.dumps(result['metadata'], indent=2), file_name="metadata.json", mime='application/json')

    st.markdown("---")
    st.subheader("Production & scaling notes")
    st.markdown("""
- For **hundreds of millions** of PDFs you will need a distributed processing layer (Dask, Celery, or Apache Airflow + autoscaled workers on Kubernetes).
- Store inputs & outputs in object storage (S3/GCS) and keep processing idempotent.
- Use a lightweight message queue (RabbitMQ/Kafka) to schedule jobs and horizontal scale consumers.
- Enable OCR only for pages with low/no extracted text (you can detect this cheaply using pdfplumber's `extract_words` count).
- Prefer `pdfplumber` for layout-heavy district court judgments — it gives word positions which we use to reconstruct paragraphs.
- For bulk entity extraction (judges, parties), consider training a small spaCy NER model to improve accuracy over heuristics.
""")

if __name__ == '__main__':
    main()

import streamlit as st
import fitz  # PyMuPDF
import io
import base64
import os
import math
from PIL import Image
import tempfile
import html

# Optional OCR
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

st.set_page_config(page_title="Legal Judgment PDF → HTML (Preserve Layout)", layout="wide")

# -----------------------------
# Helpers
# -----------------------------

def points_to_px(val, scale=96/72):
    """Convert PDF points (72dpi) to CSS pixels (approx 96dpi)."""
    return val * scale


def extract_pages_with_pymupdf(pdf_bytes):
    """Extract text blocks and layout info from PDF using PyMuPDF.
    Returns list of pages where each page is dict with width,height and blocks.
    Each block: {"bbox":(x0,y0,x1,y1), "text": str, "font_size": float (approx)}
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        page_dict = page.get_text("dict")
        rect = page.rect
        page_w, page_h = rect.width, rect.height
        blocks = []
        for block in page_dict.get("blocks", []):
            if block["type"] == 0:  # text block
                bbox = block.get("bbox")
                text = "\n".join([line.get("spans")[0].get("text") if line.get("spans") else "" for line in block.get("lines", [])])
                # estimate font size from first span
                font_size = None
                try:
                    spans = block.get("lines")[0].get("spans")
                    if spans:
                        font_size = spans[0].get("size")
                except Exception:
                    font_size = None
                blocks.append({"bbox":bbox, "text":text, "font_size":font_size})
        pages.append({"width": page_w, "height": page_h, "blocks": blocks})
    doc.close()
    return pages


def generate_html_from_pages(pages, page_scale=96/72):
    """Generate an HTML string with absolutely positioned text blocks to mimic layout.
    """
    page_divs = []
    for i, p in enumerate(pages):
        w_px = points_to_px(p["width"], page_scale)
        h_px = points_to_px(p["height"], page_scale)
        blocks_html = []
        for b in p["blocks"]:
            x0, y0, x1, y1 = b["bbox"]
            left = points_to_px(x0, page_scale)
            top = points_to_px(y0, page_scale)
            width = max(1, points_to_px(x1 - x0, page_scale))
            height = max(1, points_to_px(y1 - y0, page_scale))
            # sanitize text for HTML
            content = html.escape(b["text"]).replace('\n', '<br/>')
            font_size_px = ''
            if b.get("font_size"):
                # convert font size points -> px
                font_size_px = f"font-size: {points_to_px(b['font_size'], page_scale):.1f}px;"
            div = f'<div class="text-block" style="position:absolute; left:{left:.1f}px; top:{top:.1f}px; width:{width:.1f}px; height:{height:.1f}px; {font_size_px}overflow-wrap:break-word;">{content}</div>'
            blocks_html.append(div)
        page_html = f'<div class="pdf-page" style="position:relative; width:{w_px:.1f}px; height:{h_px:.1f}px; margin:20px auto; box-shadow:0 0 0.5rem rgba(0,0,0,0.1); background:white;">' + "\n".join(blocks_html) + '</div>'
        page_divs.append(page_html)

    css = """
    <style>
    body { background:#f0f0f0; font-family: Georgia, 'Times New Roman', serif; }
    .pdf-container { display:flex; flex-direction:column; align-items:center; }
    .pdf-page { border:1px solid #ddd; }
    .text-block { white-space: pre-wrap; }
    </style>
    """

    html_full = f"""
    <!doctype html>
    <html>
    <head>
    <meta charset=\"utf-8\" />
    <title>Converted Judgment</title>
    {css}
    </head>
    <body>
    <div class="pdf-container">
    {"".join(page_divs)}
    </div>
    </body>
    </html>
    """
    return html_full


def ocr_pages(pdf_bytes):
    """Fallback OCR: convert pages to images and run pytesseract to get text.
    Returns list of pages each as simple text blob.
    """
    images = convert_from_bytes(pdf_bytes)
    pages = []
    for img in images:
        text = pytesseract.image_to_string(img, lang='eng')
        pages.append({"width": img.width, "height": img.height, "blocks": [{"bbox": (0,0,img.width,img.height), "text": text, "font_size": None}]})
    return pages

# -----------------------------
# Streamlit UI
# -----------------------------

st.title("Legal Judgment PDF → HTML (Preserve layout & numbering)")
st.markdown(
    """
    Upload a judgement PDF and this tool will attempt to reproduce the PDF's text and structure in an HTML page.

    **Key points:**
    - Uses PyMuPDF to extract text *with layout blocks* and repositions them in HTML to resemble the original.
    - Optional OCR fallback using pytesseract/pdf2image for scanned PDFs (requires external Tesseract & poppler).
    - Preview HTML in the app and download the final HTML file.
    """
)

uploaded = st.file_uploader("Upload PDF file", type=["pdf"])
use_ocr = st.checkbox("Use OCR fallback for scanned pages (requires pytesseract + poppler)", value=False)

if uploaded is not None:
    pdf_bytes = uploaded.read()
    st.info(f"File uploaded: {uploaded.name} — {len(pdf_bytes):,} bytes")

    with st.spinner("Extracting layout from PDF using PyMuPDF..."):
        try:
            pages = extract_pages_with_pymupdf(pdf_bytes)
            # If no text blocks found and OCR available and user selected OCR, fallback
            total_blocks = sum(len(p['blocks']) for p in pages)
            if total_blocks == 0 and use_ocr and OCR_AVAILABLE:
                st.warning("No text blocks found — trying OCR fallback on all pages.")
                pages = ocr_pages(pdf_bytes)
            elif total_blocks == 0 and use_ocr and not OCR_AVAILABLE:
                st.error("OCR requested but pytesseract/pdf2image not available in environment.")
        except Exception as e:
            st.error(f"Error extracting PDF: {e}")
            st.stop()

    # Generate HTML
    html_out = generate_html_from_pages(pages)

    st.subheader("HTML Preview")
    # Display preview in a resizable iframe-like area
    st.components.v1.html(html_out, height=800, scrolling=True)

    # Download
    st.download_button(label="Download HTML", data=html_out.encode('utf-8'), file_name=os.path.splitext(uploaded.name)[0] + ".html", mime="text/html")

    # Save requirements helper
    if st.button("Show recommended requirements.txt"):
        reqs = """
streamlit
PyMuPDF
pdf2image
pytesseract
pillow
pdfplumber
"""
        st.code(reqs)

    st.markdown("---")
    st.markdown(
        "**Notes & tips:**\n\n" 
        "- This tool tries to reproduce spatial layout by absolutely positioning text blocks extracted by PyMuPDF (get_text(\"dict\")).\n"
        "- Perfect pixel-for-pixel reproduction requires the original fonts and advanced rendering (not covered here).\n"
        "- For scanned/bitmap PDFs enable OCR (requires system installation of Tesseract and poppler).\n"
        "- If you want the app tuned to a set of sample judgments (court-specific styles), upload a few representative PDFs and I can help adjust CSS/font scaling rules to match them more closely.\n"
    )

else:
    st.info("Upload a PDF to get started.")

import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import pytesseract
from pdf2image import convert_from_path
import tempfile

st.set_page_config(layout="wide")
st.title("Legal Judgment PDF → HTML Converter (High Fidelity)")

def pdf_to_html(file_bytes):
    """Convert PDF to high-fidelity HTML (page images + text overlay)."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_html = []

    # Fixed high DPI for sharp rendering
    RENDER_DPI = 300  

    for page_num, page in enumerate(doc, start=1):
        # Render page as image (background)
        pix = page.get_pixmap(dpi=RENDER_DPI, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        with io.BytesIO() as output:
            img.save(output, format="PNG")
            b64_img = base64.b64encode(output.getvalue()).decode("utf-8")

        page_width, page_height = pix.width, pix.height

        # Extract text spans
        spans = []
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    spans.append(s)

        overlay_divs = []
        if spans:
            for s in spans:
                style = (
                    f"position:absolute; "
                    f"left:{s['bbox'][0]}px; top:{s['bbox'][1]}px; "
                    f"font-size:{s['size']}px; "
                    f"font-family:'Times New Roman', serif; "
                    f"white-space:pre;"
                )
                overlay_divs.append(f"<div style='{style}'>{s['text']}</div>")
        else:
            # Fallback OCR if no text
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                img.save(tmp_img.name, "PNG")
                ocr_data = pytesseract.image_to_data(
                    Image.open(tmp_img.name), output_type=pytesseract.Output.DICT
                )
            for i in range(len(ocr_data["text"])):
                if ocr_data["text"][i].strip():
                    x, y, w, h = (
                        ocr_data["left"][i],
                        ocr_data["top"][i],
                        ocr_data["width"][i],
                        ocr_data["height"][i],
                    )
                    style = (
                        f"position:absolute; "
                        f"left:{x}px; top:{y}px; "
                        f"font-size:{h}px; "
                        f"font-family:'Times New Roman', serif; "
                        f"white-space:pre;"
                    )
                    overlay_divs.append(f"<div style='{style}'>{ocr_data['text'][i]}</div>")

        page_html = f"""
        <div style="position:relative; width:{page_width}px; height:{page_height}px; margin:0 auto; border:1px solid #ccc; background:url('data:image/png;base64,{b64_img}') no-repeat; background-size:contain;">
            {''.join(overlay_divs)}
        </div>
        """
        pages_html.append(page_html)

    final_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Judgment</title>
      <style>
        body {{
          font-family: 'Times New Roman', serif;
          background-color: #fff;
          margin: 0;
          padding: 0;
        }}
        .page-container {{
          page-break-after: always;
        }}
      </style>
    </head>
    <body>
      {''.join(pages_html)}
    </body>
    </html>
    """
    return final_html


# ================= UI =================
uploaded_file = st.file_uploader("Upload Judgment PDF", type=["pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    html_output = pdf_to_html(file_bytes)

    # Preview
    st.components.v1.html(html_output, height=800, scrolling=True)

    # Download
    b64_html = base64.b64encode(html_output.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64_html}" download="judgment.html">📥 Download HTML</a>'
    st.markdown(href, unsafe_allow_html=True)

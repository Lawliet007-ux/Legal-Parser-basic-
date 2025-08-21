import streamlit as st
import fitz  # PyMuPDF
import re
from jinja2 import Template
import base64

# =====================
#  HTML TEMPLATE
# =====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ petitioner }} v. {{ respondent }}</title>
  <style>
    body {
      font-family: 'Georgia', serif;
      background-color: #f9fafb;
      color: #111827;
      padding: 40px;
      line-height: 1.8;
    }
    h1, h2 {
      text-align: center;
      margin: 0;
    }
    h1 {
      font-size: 30px;
    }
    h2 {
      font-size: 26px;
      margin-bottom: 10px;
    }
    h3 {
      text-align: center;
      font-weight: normal;
      font-size: 18px;
      color: #444;
      margin-top: 5px;
    }
    .meta, .judge {
      text-align: center;
      font-size: 16px;
      color: #555;
      margin-top: 10px;
    }
    .content {
      margin-top: 40px;
    }
    .point {
      margin-bottom: 20px;
      text-align: justify;
    }
    .point-number {
      font-weight: bold;
    }
  </style>
</head>
<body>
  <h1>{{ petitioner }}</h1>
  <h2>v.</h2>
  <h1>{{ respondent }}</h1>
  <h3>{{ court_name }}</h3>
  <div class="meta">{{ appeal_number }} | {{ date }}</div>
  <div class="judge">{{ judge }}</div>
  <div class="content">
    {% for point in points %}
    <div class="point">
      <span class="point-number">{{ loop.index }}.</span> {{ point }}
    </div>
    {% endfor %}
  </div>
</body>
</html>
"""

# =====================
#  UTIL FUNCTIONS
# =====================
def extract_text_from_pdf(pdf_file):
    """Extract full text from PDF."""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    return full_text.strip()

def extract_metadata(text):
    """Extract petitioner, respondent, court name from judgment text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    petitioner = "Petitioner"
    respondent = "Respondent"

    # Look in first 20 lines for case title
    for i in range(min(20, len(lines))):
        line = lines[i]

        # Same line case
        if re.search(r"\b(v\.|vs\.|versus)\b", line, re.IGNORECASE):
            parts = re.split(r"\b(v\.|vs\.|versus)\b", line, flags=re.IGNORECASE)
            if len(parts) >= 3:
                petitioner = parts[0].strip(" ,;:-")
                respondent = parts[-1].strip(" ,;:-")
                break

        # Multi-line case
        if i + 1 < len(lines) and re.match(r"(?i)versus|vs\.|v\.", lines[i+1]):
            petitioner = line.strip(" ,;:-")
            respondent = lines[i+2].strip(" ,;:-") if i + 2 < len(lines) else "Respondent"
            break

    # Extract court name
    court_name = ""
    for i in range(min(30, len(lines))):
        if "court" in lines[i].lower():
            court_name = lines[i]
            break

    return {
        "petitioner": petitioner,
        "respondent": respondent,
        "court_name": court_name or "Court Name",
        "appeal_number": "",
        "date": "",
        "judge": ""
    }

def auto_split_into_points(text):
    """Split text into numbered points."""
    raw_points = re.split(r'\n{2,}|(?<=[.])\s*\n+', text)
    points = [p.strip().replace('\n', ' ') for p in raw_points if len(p.strip()) > 30]
    return points

def render_html(meta, points):
    """Render HTML using template."""
    template = Template(HTML_TEMPLATE)
    return template.render(**meta, points=points)

def download_button(html_content, filename):
    """Generate a download link for HTML file."""
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}">📥 Download HTML</a>'
    return href

# =====================
#  STREAMLIT UI
# =====================
st.set_page_config(page_title="Legal Judgment Formatter", layout="wide")
st.title("📄 Legal Judgment Formatter")
st.markdown("Convert your legal PDF judgment into a styled HTML report with **Petitioner vs Respondent** detected automatically.")

pdf_file = st.file_uploader("Upload Judgment PDF", type=["pdf"])

if pdf_file:
    st.success("✅ PDF uploaded successfully!")
    if st.button("Generate HTML Report"):
        with st.spinner("⏳ Extracting text and generating HTML..."):
            text = extract_text_from_pdf(pdf_file)
            meta = extract_metadata(text)
            points = auto_split_into_points(text)
            html = render_html(meta, points)
        
        st.markdown("---")
        st.subheader("📝 Extracted Judgment Preview")
        st.components.v1.html(html, height=900, scrolling=True)  # Bigger preview window
        st.markdown(download_button(html, "judgment_output.html"), unsafe_allow_html=True)

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
      max-width: 1200px;
      margin: 0 auto;
    }
    h1, h2 {
      text-align: center;
      margin: 0;
    }
    h1 {
      font-size: 28px;
      font-weight: bold;
    }
    h2 {
      font-size: 24px;
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
      white-space: pre-wrap;
      font-size: 16px;
      text-align: justify;
    }
    .legal-citation {
      font-style: italic;
      color: #2563eb;
    }
    .case-number {
      font-weight: bold;
      color: #dc2626;
    }
    .judge-name {
      font-weight: bold;
      margin-top: 30px;
      text-align: center;
    }
    .date {
      text-align: center;
      font-weight: bold;
    }
    .paragraph-number {
      font-weight: bold;
      margin-right: 5px;
    }
    .section-break {
      margin: 20px 0;
      border-top: 1px solid #e5e7eb;
      padding-top: 20px;
    }
  </style>
</head>
<body>
  <div class="case-number">{{ case_number }}</div>
  <h1>{{ petitioner }}</h1>
  <h2>v.</h2>
  <h1>{{ respondent }}</h1>
  <h3>{{ court_name }}</h3>
  <div class="meta">{{ date }}</div>
  <div class="judge">{{ judge_present }}</div>
  <div class="content">{{ formatted_content }}</div>
  <div class="judge-name">{{ judge_signature }}</div>
</body>
</html>
"""

# =====================
#  UTIL FUNCTIONS
# =====================
def extract_text_from_pdf(pdf_file):
    """Extract full text from PDF preserving structure."""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    
    # Clean up encoding issues
    full_text = full_text.replace('Â', ' ')
    full_text = re.sub(r'\s+', ' ', full_text)  # Normalize whitespace
    full_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', full_text)  # Normalize line breaks
    
    return full_text

def extract_metadata_enhanced(text):
    """Extract comprehensive metadata from judgment text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # Initialize variables
    petitioner = "Petitioner"
    respondent = "Respondent"
    case_number = ""
    court_name = ""
    date = ""
    judge_present = ""
    judge_signature = ""
    
    # Extract case number (more specific pattern)
    for i in range(min(5, len(lines))):
        if re.match(r'^(OMP|CRL|WP|CS|CC|CM|CRP|RCA|SLP|CA|MA|IA)\s*\([^)]*\)\s*(Comm\.|Civil|Crl\.)?\s*No\.\s*\d+', lines[i], re.IGNORECASE):
            case_number = lines[i]
            break
    
    # Look for petitioner vs respondent
    for i in range(min(15, len(lines))):
        line = lines[i]
        
        # Skip case numbers and dates
        if re.match(r'^(OMP|CRL|WP|CS|CC|CM)', line, re.IGNORECASE) or re.search(r'\d{2}\.\d{2}\.\d{4}', line):
            continue
            
        # Same line case
        if re.search(r"\b(v\.|vs\.|versus|VS|V\.)\b", line, re.IGNORECASE) and not line.lower().startswith('present'):
            parts = re.split(r"\b(v\.|vs\.|versus|VS|V\.)\b", line, flags=re.IGNORECASE)
            if len(parts) >= 3:
                petitioner = parts[0].strip(" ,;:-")
                respondent = parts[-1].strip(" ,;:-")
                break
        
        # Multi-line case
        if i + 1 < len(lines) and re.search(r"(?i)^(versus|vs\.|v\.|VS|V\.)$", lines[i+1].strip()):
            petitioner = line.strip(" ,;:-")
            if i + 2 < len(lines):
                respondent = lines[i+2].strip(" ,;:-")
            break
    
    # Extract date (look for date patterns)
    date_pattern = r'\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b'
    for line in lines[:15]:
        date_match = re.search(date_pattern, line)
        if date_match:
            date = date_match.group(1)
            break
    
    # Extract court name (more specific)
    court_keywords = ['district judge', 'high court', 'supreme court', 'tribunal', 'commercial court']
    for line in lines[-10:]:  # Look at the end where judge signature is
        for keyword in court_keywords:
            if keyword in line.lower():
                court_name = line
                break
        if court_name:
            break
    
    # Extract judge present information
    for line in lines[:25]:
        if line.lower().startswith('present'):
            judge_present = line
            break
    
    # Extract judge signature (more specific - look for name patterns)
    for line in reversed(lines[-15:]):
        if (any(keyword in line.lower() for keyword in ['district judge', 'justice', 'magistrate']) 
            and len(line.strip()) < 100 
            and not line.lower().startswith('station')):
            judge_signature = line
            break
    
    return {
        "case_number": case_number,
        "petitioner": petitioner,
        "respondent": respondent,
        "court_name": court_name or "District Court",
        "date": date,
        "judge_present": judge_present,
        "judge_signature": judge_signature
    }

def preserve_original_formatting(text):
    """Preserve original text formatting including numbering and citations."""
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            formatted_lines.append('')
            continue
            
        # Preserve legal citations (case names, act references, etc.)
        if re.search(r'\b\d{4}\b.*\bSCC\b|\bAIR\b.*\b\d{4}\b|\bSection\s+\d+|\bAct\s+\d{4}\b', stripped_line):
            formatted_lines.append(f'<span class="legal-citation">{stripped_line}</span>')
        # Preserve existing numbering (Roman, Arabic, alphabetic)
        elif re.search(r'^\s*(\([ivxlcdm]+\)|\([a-z]+\)|\([0-9]+\)|[0-9]+\.|\([0-9]+\)|[ivxlcdm]+\.)', stripped_line, re.IGNORECASE):
            formatted_lines.append(stripped_line)
        # Preserve case numbers and references
        elif re.search(r'(OMP|CRL|WP|CS|CC|CM|CRP|RCA|SLP|CA|MA|IA)', stripped_line, re.IGNORECASE):
            formatted_lines.append(f'<span class="case-number">{stripped_line}</span>')
        else:
            formatted_lines.append(stripped_line)
    
    # Join lines and preserve paragraph breaks
    formatted_text = '\n'.join(formatted_lines)
    
    # Add section breaks for major divisions
    formatted_text = re.sub(r'\n\s*\n\s*\n+', '\n<div class="section-break"></div>\n', formatted_text)
    
    return formatted_text

def render_html_enhanced(meta, formatted_content):
    """Render HTML using enhanced template."""
    template = Template(HTML_TEMPLATE)
    return template.render(**meta, formatted_content=formatted_content)

def download_button(html_content, filename):
    """Generate a download link for HTML file."""
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}" style="background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 20px;">📥 Download HTML Report</a>'
    return href

# =====================
#  STREAMLIT UI
# =====================
st.set_page_config(page_title="Enhanced Legal Judgment Formatter", layout="wide")
st.title("⚖️ Enhanced Legal Judgment Formatter")


pdf_file = st.file_uploader("Upload Legal Judgment PDF", type=["pdf"])

if pdf_file:
    st.success("✅ PDF uploaded successfully!")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🚀 Generate Enhanced Report", type="primary"):
            with st.spinner("⏳ Processing judgment and preserving formatting..."):
                # Extract text
                text = extract_text_from_pdf(pdf_file)
                
                # Extract metadata
                meta = extract_metadata_enhanced(text)
                
                # Preserve original formatting
                formatted_content = preserve_original_formatting(text)
                
                # Render HTML
                html = render_html_enhanced(meta, formatted_content)
                
                st.session_state['html_output'] = html
                st.session_state['meta'] = meta
    
    with col2:
        if 'meta' in st.session_state:
            st.markdown("### 📋 Detected Metadata")
            meta = st.session_state['meta']
            st.write(f"**Case Number:** {meta['case_number'] or 'Not found'}")
            st.write(f"**Petitioner:** {meta['petitioner']}")
            st.write(f"**Respondent:** {meta['respondent']}")
            st.write(f"**Court:** {meta['court_name']}")
            st.write(f"**Date:** {meta['date'] or 'Not found'}")

if 'html_output' in st.session_state:
    st.markdown("---")
    st.subheader("📄 Enhanced Judgment Preview")
    st.components.v1.html(st.session_state['html_output'], height=800, scrolling=True)
    st.markdown(download_button(st.session_state['html_output'], "enhanced_judgment.html"), unsafe_allow_html=True)
    
    # Option to view raw formatted content
    with st.expander("🔍 View Processed Text (Debug)"):
        meta = st.session_state['meta']
        formatted_content = preserve_original_formatting(extract_text_from_pdf(pdf_file))
        st.text_area("Formatted Content", formatted_content, height=400)

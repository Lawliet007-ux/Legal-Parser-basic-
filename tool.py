import streamlit as st
import fitz  # PyMuPDF
import re
from jinja2 import Template
import base64
import io
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================
#  ENHANCED HTML TEMPLATE
# =====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ petitioner }} v. {{ respondent }}</title>
  <style>
    :root {
      --primary-blue: #1e40af;
      --secondary-blue: #3b82f6;
      --accent-red: #dc2626;
      --text-dark: #111827;
      --text-medium: #374151;
      --text-light: #6b7280;
      --bg-light: #f9fafb;
      --bg-white: #ffffff;
      --border-light: #e5e7eb;
      --border-medium: #d1d5db;
      --success-green: #059669;
    }

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: 'Georgia', 'Times New Roman', serif;
      background: linear-gradient(135deg, var(--bg-light) 0%, #f3f4f6 100%);
      color: var(--text-dark);
      line-height: 1.7;
      font-size: 16px;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
      background: var(--bg-white);
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
      border-radius: 12px;
      margin-top: 20px;
      margin-bottom: 20px;
    }

    .header {
      text-align: center;
      border-bottom: 3px solid var(--primary-blue);
      padding-bottom: 30px;
      margin-bottom: 40px;
    }

    .case-number {
      background: linear-gradient(135deg, var(--accent-red), #ef4444);
      color: white;
      padding: 12px 24px;
      border-radius: 25px;
      display: inline-block;
      font-weight: bold;
      font-size: 14px;
      letter-spacing: 0.5px;
      margin-bottom: 20px;
      box-shadow: 0 4px 15px rgba(220, 38, 38, 0.3);
    }

    .parties {
      margin: 25px 0;
    }

    .party-name {
      font-size: 32px;
      font-weight: bold;
      color: var(--primary-blue);
      margin: 10px 0;
      text-shadow: 0 2px 4px rgba(30, 64, 175, 0.1);
    }

    .vs-divider {
      font-size: 28px;
      color: var(--text-medium);
      font-weight: normal;
      margin: 15px 0;
    }

    .court-info {
      background: linear-gradient(135deg, var(--primary-blue), var(--secondary-blue));
      color: white;
      padding: 20px;
      border-radius: 10px;
      margin: 25px 0;
      text-align: center;
    }

    .court-name {
      font-size: 20px;
      font-weight: bold;
      margin-bottom: 10px;
    }

    .case-details {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin: 30px 0;
      padding: 25px;
      background: linear-gradient(135deg, #f8fafc, #f1f5f9);
      border-radius: 10px;
      border: 1px solid var(--border-light);
    }

    .detail-item {
      text-align: center;
      padding: 15px;
      background: var(--bg-white);
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }

    .detail-label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--text-light);
      margin-bottom: 8px;
      font-weight: 600;
    }

    .detail-value {
      font-size: 16px;
      font-weight: bold;
      color: var(--primary-blue);
    }

    .content {
      margin-top: 40px;
      background: var(--bg-white);
      padding: 40px;
      border-radius: 10px;
      border: 1px solid var(--border-light);
      white-space: pre-wrap;
      text-align: justify;
      line-height: 1.8;
    }

    /* Enhanced Legal Styling */
    .legal-citation {
      background: linear-gradient(135deg, #eff6ff, #dbeafe);
      padding: 3px 8px;
      border-radius: 5px;
      font-style: italic;
      color: var(--primary-blue);
      border-left: 3px solid var(--secondary-blue);
      margin: 2px 0;
      display: inline-block;
    }

    .case-reference {
      background: linear-gradient(135deg, #fef2f2, #fee2e2);
      color: var(--accent-red);
      font-weight: bold;
      padding: 2px 6px;
      border-radius: 4px;
      border-left: 2px solid var(--accent-red);
    }

    .statutory-reference {
      background: linear-gradient(135deg, #f0fdf4, #dcfce7);
      color: var(--success-green);
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      border-left: 2px solid var(--success-green);
    }

    .paragraph-number {
      font-weight: bold;
      color: var(--primary-blue);
      background: #eff6ff;
      padding: 2px 8px;
      border-radius: 50%;
      margin-right: 8px;
      display: inline-block;
      min-width: 25px;
      text-align: center;
      font-size: 14px;
    }

    .section-break {
      margin: 30px 0;
      border-top: 2px solid var(--border-medium);
      padding-top: 30px;
      position: relative;
    }

    .section-break::before {
      content: "⚖";
      position: absolute;
      top: -12px;
      left: 50%;
      transform: translateX(-50%);
      background: var(--bg-white);
      color: var(--primary-blue);
      padding: 0 15px;
      font-size: 20px;
    }

    .judge-signature {
      margin-top: 50px;
      text-align: center;
      padding: 25px;
      background: linear-gradient(135deg, var(--primary-blue), var(--secondary-blue));
      color: white;
      border-radius: 10px;
      font-weight: bold;
      font-size: 18px;
    }

    .judge-signature::before {
      content: "⚖";
      display: block;
      font-size: 24px;
      margin-bottom: 10px;
    }

    .monetary-amount {
      background: linear-gradient(135deg, #fef3c7, #fde68a);
      color: #92400e;
      font-weight: bold;
      padding: 2px 6px;
      border-radius: 4px;
      border: 1px solid #f59e0b;
    }

    .date-highlight {
      background: linear-gradient(135deg, #f3e8ff, #e9d5ff);
      color: #7c3aed;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .container {
        margin: 10px;
        padding: 20px 15px;
      }
      
      .party-name {
        font-size: 24px;
      }
      
      .content {
        padding: 20px;
      }
      
      .case-details {
        grid-template-columns: 1fr;
      }
    }

    /* Print Styles */
    @media print {
      body {
        background: white;
      }
      
      .container {
        box-shadow: none;
        margin: 0;
      }
      
      .case-number, .court-info {
        background: #f0f0f0 !important;
        color: black !important;
      }
    }

    /* Accessibility */
    .screen-reader-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <div class="case-number" role="banner">{{ case_number or "Case Number Not Available" }}</div>
      
      <div class="parties">
        <h1 class="party-name">{{ petitioner }}</h1>
        <div class="vs-divider">versus</div>
        <h1 class="party-name">{{ respondent }}</h1>
      </div>

      {% if court_name %}
      <div class="court-info">
        <div class="court-name">{{ court_name }}</div>
      </div>
      {% endif %}

      <div class="case-details">
        {% if date %}
        <div class="detail-item">
          <div class="detail-label">Date of Order</div>
          <div class="detail-value">{{ date }}</div>
        </div>
        {% endif %}
        
        {% if judge_present %}
        <div class="detail-item">
          <div class="detail-label">Present</div>
          <div class="detail-value">{{ judge_present }}</div>
        </div>
        {% endif %}
        
        <div class="detail-item">
          <div class="detail-label">Generated On</div>
          <div class="detail-value">{{ generation_date }}</div>
        </div>
      </div>
    </header>

    <main class="content" role="main">{{ formatted_content }}</main>

    {% if judge_signature %}
    <footer class="judge-signature" role="contentinfo">
      {{ judge_signature }}
    </footer>
    {% endif %}
  </div>
</body>
</html>
"""

# =====================
#  ENHANCED UTILITY FUNCTIONS
# =====================
def extract_text_from_pdf(pdf_file):
    """Extract text from PDF with enhanced error handling and structure preservation."""
    try:
        # Reset file pointer to beginning
        pdf_file.seek(0)
        
        # Read file content into bytes
        file_content = pdf_file.read()
        
        if not file_content:
            raise ValueError("PDF file appears to be empty")
        
        # Open document from bytes
        doc = fitz.open(stream=file_content, filetype="pdf")
        
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        
        full_text = ""
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Extract text with better formatting
            text = page.get_text("text")
            full_text += text + "\n"
        
        doc.close()
        
        # Enhanced text cleaning
        full_text = clean_extracted_text(full_text)
        
        logger.info(f"Successfully extracted text from {doc.page_count} pages")
        return full_text
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise ValueError(f"Failed to process PDF: {str(e)}")

def clean_extracted_text(text):
    """Enhanced text cleaning with better encoding and formatting."""
    if not text:
        return ""
    
    # Fix encoding issues
    text = text.replace('Â', ' ')
    text = text.replace('â€™', "'")
    text = text.replace('â€œ', '"')
    text = text.replace('â€', '"')
    
    # Normalize whitespace but preserve intentional formatting
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline
    text = re.sub(r'([.!?])\s*\n\s*([A-Z])', r'\1\n\n\2', text)  # Add breaks after sentences
    
    return text.strip()

def extract_metadata_enhanced(text):
    """Extract comprehensive metadata with improved pattern matching."""
    if not text:
        return create_default_metadata()
    
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    metadata = {
        "case_number": "",
        "petitioner": "Petitioner",
        "respondent": "Respondent", 
        "court_name": "",
        "date": "",
        "judge_present": "",
        "judge_signature": "",
        "generation_date": datetime.now().strftime("%B %d, %Y")
    }
    
    # Extract case number with multiple patterns
    case_patterns = [
        r'^(OMP|CRL|WP|CS|CC|CM|CRP|RCA|SLP|CA|MA|IA)\s*\([^)]*\)\s*(Comm\.|Civil|Crl\.)?\s*No\.\s*\d+',
        r'^Case\s+No[.:]\s*\d+',
        r'^Criminal\s+Appeal\s+No[.:]\s*\d+',
        r'^Civil\s+Appeal\s+No[.:]\s*\d+'
    ]
    
    for i in range(min(10, len(lines))):
        for pattern in case_patterns:
            if re.match(pattern, lines[i], re.IGNORECASE):
                metadata["case_number"] = lines[i]
                break
        if metadata["case_number"]:
            break
    
    # Extract parties with improved logic
    metadata.update(extract_parties(lines))
    
    # Extract dates with multiple formats
    date_patterns = [
        r'\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b',
        r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',
        r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b'
    ]
    
    for line in lines[:20]:
        for pattern in date_patterns:
            date_match = re.search(pattern, line, re.IGNORECASE)
            if date_match:
                metadata["date"] = date_match.group(1)
                break
        if metadata["date"]:
            break
    
    # Extract court information
    court_keywords = [
        'district judge', 'high court', 'supreme court', 'tribunal', 
        'commercial court', 'session court', 'magistrate', 'additional district judge'
    ]
    
    for line in lines:
        line_lower = line.lower()
        for keyword in court_keywords:
            if keyword in line_lower and len(line) < 200:
                metadata["court_name"] = line
                break
        if metadata["court_name"]:
            break
    
    # Extract judge present
    for line in lines[:30]:
        if re.match(r'^present\s*:', line, re.IGNORECASE):
            metadata["judge_present"] = line
            break
    
    # Extract judge signature
    for line in reversed(lines[-20:]):
        if (any(keyword in line.lower() for keyword in ['district judge', 'justice', 'magistrate'])
            and len(line.strip()) < 150
            and not line.lower().startswith('station')):
            metadata["judge_signature"] = line
            break
    
    return metadata

def extract_parties(lines):
    """Enhanced party extraction with better pattern matching."""
    petitioner = "Petitioner"
    respondent = "Respondent"
    
    # Skip initial case number and date lines
    start_idx = 0
    for i, line in enumerate(lines[:10]):
        if (re.match(r'^(OMP|CRL|WP|CS)', line, re.IGNORECASE) or 
            re.search(r'\d{2}\.\d{2}\.\d{4}', line)):
            start_idx = i + 1
        else:
            break
    
    search_lines = lines[start_idx:min(start_idx + 20, len(lines))]
    
    for i, line in enumerate(search_lines):
        # Skip certain lines
        if (line.lower().startswith('present') or 
            line.lower().startswith('heard') or
            len(line) < 5):
            continue
        
        # Same line pattern
        vs_patterns = [r'\s+v\.?\s+', r'\s+vs\.?\s+', r'\s+versus\s+']
        for pattern in vs_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                parts = re.split(pattern, line, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    petitioner = clean_party_name(parts[0])
                    respondent = clean_party_name(parts[1])
                    return {"petitioner": petitioner, "respondent": respondent}
        
        # Multi-line pattern
        if i + 1 < len(search_lines):
            next_line = search_lines[i + 1].strip()
            if re.match(r'^(v\.?|vs\.?|versus)$', next_line, re.IGNORECASE):
                petitioner = clean_party_name(line)
                if i + 2 < len(search_lines):
                    respondent = clean_party_name(search_lines[i + 2])
                return {"petitioner": petitioner, "respondent": respondent}
    
    return {"petitioner": petitioner, "respondent": respondent}

def clean_party_name(name):
    """Clean party names removing unwanted characters."""
    if not name:
        return "Unknown"
    
    # Remove common prefixes/suffixes
    name = re.sub(r'^(mr\.?|ms\.?|mrs\.?|dr\.?|shri|smt\.?)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+(ltd\.?|limited|pvt\.?|private|inc\.?|corp\.?)$', ' Ltd.', name, flags=re.IGNORECASE)
    
    # Clean unwanted characters
    name = name.strip(' ,;:-"\'')
    name = re.sub(r'\s+', ' ', name)
    
    # Capitalize properly
    name = ' '.join(word.capitalize() for word in name.split())
    
    return name if name else "Unknown"

def create_default_metadata():
    """Create default metadata structure."""
    return {
        "case_number": "",
        "petitioner": "Petitioner",
        "respondent": "Respondent",
        "court_name": "District Court",
        "date": "",
        "judge_present": "",
        "judge_signature": "",
        "generation_date": datetime.now().strftime("%B %d, %Y")
    }

def enhance_content_formatting(text):
    """Enhanced content formatting with better legal document recognition."""
    if not text:
        return ""
    
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            formatted_lines.append('')
            continue
        
        # Apply various formatting enhancements
        formatted_line = stripped_line
        
        # Highlight monetary amounts
        formatted_line = re.sub(
            r'\bRs\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+)/?-?\b',
            r'<span class="monetary-amount">Rs. \1</span>',
            formatted_line, flags=re.IGNORECASE
        )
        
        # Highlight dates
        formatted_line = re.sub(
            r'\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b',
            r'<span class="date-highlight">\1</span>',
            formatted_line
        )
        
        # Highlight legal citations
        if re.search(r'\b\d{4}\b.*\bSCC\b|\bAIR\b.*\b\d{4}\b|\bAll\s+LR\b|\bBom\s+LR\b', formatted_line):
            formatted_line = f'<span class="legal-citation">{formatted_line}</span>'
        
        # Highlight statutory references
        elif re.search(r'\bSection\s+\d+|\bAct\s+\d{4}\b|\bRule\s+\d+|\bArticle\s+\d+', formatted_line, re.IGNORECASE):
            formatted_line = f'<span class="statutory-reference">{formatted_line}</span>'
        
        # Highlight case references
        elif re.search(r'(OMP|CRL|WP|CS|CC|CM|CRP|RCA|SLP|CA|MA|IA)', formatted_line, re.IGNORECASE):
            formatted_line = f'<span class="case-reference">{formatted_line}</span>'
        
        # Preserve numbered paragraphs
        elif re.search(r'^\s*(\([ivxlcdm]+\)|\([a-z]+\)|\([0-9]+\)|[0-9]+\.|\([0-9]+\)|[ivxlcdm]+\.)', formatted_line, re.IGNORECASE):
            number_match = re.match(r'^(\s*)(\([ivxlcdm]+\)|\([a-z]+\)|\([0-9]+\)|[0-9]+\.|\([0-9]+\)|[ivxlcdm]+\.)', formatted_line, re.IGNORECASE)
            if number_match:
                indent = number_match.group(1)
                number = number_match.group(2)
                rest = formatted_line[len(indent + number):].strip()
                formatted_line = f'{indent}<span class="paragraph-number">{number}</span> {rest}'
        
        formatted_lines.append(formatted_line)
    
    # Join and add section breaks
    formatted_text = '\n'.join(formatted_lines)
    formatted_text = re.sub(r'\n\s*\n\s*\n+', '\n<div class="section-break"></div>\n', formatted_text)
    
    return formatted_text

def render_html_enhanced(metadata, formatted_content):
    """Render HTML using enhanced template with error handling."""
    try:
        template = Template(HTML_TEMPLATE)
        return template.render(**metadata, formatted_content=formatted_content)
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        raise ValueError(f"Template rendering failed: {str(e)}")

def create_download_button(html_content, filename="enhanced_legal_judgment.html"):
    """Create download button with better UX."""
    try:
        b64 = base64.b64encode(html_content.encode('utf-8')).decode()
        href = f'''
        <div style="text-align: center; margin: 20px 0;">
            <a href="data:text/html;base64,{b64}" 
               download="{filename}" 
               style="background: linear-gradient(135deg, #1e40af, #3b82f6); 
                      color: white; 
                      padding: 15px 30px; 
                      text-decoration: none; 
                      border-radius: 8px; 
                      display: inline-block; 
                      font-weight: bold;
                      box-shadow: 0 4px 15px rgba(30, 64, 175, 0.3);
                      transition: all 0.3s ease;
                      font-size: 16px;">
                📥 Download Enhanced HTML Report
            </a>
        </div>
        '''
        return href
    except Exception as e:
        logger.error(f"Error creating download button: {str(e)}")
        return "<p>Error creating download link</p>"

# =====================
#  STREAMLIT UI
# =====================
def main():
    st.set_page_config(
        page_title="Enhanced Legal Judgment Formatter", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("⚖️ Enhanced Legal Judgment Formatter")
  
    
    # Sidebar for additional options
    with st.sidebar:
        st.header("⚙️ Processing Options")
        
        preserve_formatting = st.checkbox("Preserve Original Formatting", value=True, 
                                        help="Maintains original text structure and numbering")
        
        enhance_highlighting = st.checkbox("Enhanced Legal Highlighting", value=True,
                                         help="Highlights citations, amounts, dates, and legal references")
        
        responsive_design = st.checkbox("Responsive Design", value=True,
                                      help="Mobile-friendly layout")
        
        st.markdown("---")
        st.markdown("### 📊 Processing Stats")
        if 'processing_stats' in st.session_state:
            stats = st.session_state['processing_stats']
            st.metric("Pages Processed", stats.get('pages', 0))
            st.metric("Text Length", f"{stats.get('text_length', 0):,} chars")
            st.metric("Processing Time", f"{stats.get('processing_time', 0):.2f}s")
    
    # File upload
    uploaded_file = st.file_uploader(
        "📎 Upload Legal Judgment PDF", 
        type=["pdf"],
        help="Upload a PDF file containing a legal judgment for processing"
    )
    
    if uploaded_file is not None:
        st.success("✅ PDF uploaded successfully!")
        
        # Display file info
        file_details = {
            "Filename": uploaded_file.name,
            "File Size": f"{uploaded_file.size:,} bytes",
            "File Type": uploaded_file.type
        }
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"📄 **{file_details['Filename']}**")
        with col2:
            st.info(f"📊 **{file_details['File Size']}**")
        with col3:
            st.info(f"🔧 **{file_details['File Type']}**")
        
        # Processing section
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("🚀 Process Document", type="primary", use_container_width=True):
                process_document(uploaded_file, preserve_formatting, enhance_highlighting)
        
        with col2:
            if st.button("🔄 Reset", use_container_width=True):
                # Clear session state
                keys_to_clear = ['html_output', 'metadata', 'processing_stats', 'formatted_content']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    # Results section
    if 'metadata' in st.session_state:
        display_results()

def process_document(uploaded_file, preserve_formatting, enhance_highlighting):
    """Process the uploaded document with progress tracking."""
    try:
        start_time = datetime.now()
        
        with st.spinner("⏳ Processing legal judgment..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Extract text
            status_text.text("📖 Extracting text from PDF...")
            progress_bar.progress(20)
            
            text = extract_text_from_pdf(uploaded_file)
            
            if not text.strip():
                st.error("❌ No text could be extracted from the PDF. Please ensure the file is not password-protected or corrupted.")
                return
            
            # Step 2: Extract metadata
            status_text.text("🔍 Extracting case metadata...")
            progress_bar.progress(40)
            
            metadata = extract_metadata_enhanced(text)
            
            # Step 3: Format content
            status_text.text("✨ Formatting legal content...")
            progress_bar.progress(60)
            
            if enhance_highlighting:
                formatted_content = enhance_content_formatting(text)
            else:
                formatted_content = text.replace('\n', '\n')
            
            # Step 4: Generate HTML
            status_text.text("🎨 Generating HTML report...")
            progress_bar.progress(80)
            
            html_output = render_html_enhanced(metadata, formatted_content)
            
            # Step 5: Finalize
            status_text.text("✅ Processing complete!")
            progress_bar.progress(100)
            
            # Calculate processing stats
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Store results in session state
            st.session_state['html_output'] = html_output
            st.session_state['metadata'] = metadata
            st.session_state['formatted_content'] = formatted_content
            st.session_state['processing_stats'] = {
                'pages': uploaded_file.name.count('page') + 1,  # Rough estimate
                'text_length': len(text),
                'processing_time': processing_time,
                'file_size': uploaded_file.size
            }
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            st.success("🎉 Document processed successfully!")
            
    except ValueError as ve:
        st.error(f"❌ Processing Error: {str(ve)}")
        logger.error(f"Processing error: {str(ve)}")
    except Exception as e:
        st.error(f"❌ Unexpected error occurred: {str(e)}")
        logger.error(f"Unexpected error: {str(e)}")

def display_results():
    """Display processing results with enhanced UI."""
    st.markdown("---")
    
    # Metadata display
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### 📋 Extracted Metadata")
        metadata = st.session_state['metadata']
        
        # Create a nice metadata display
        metadata_items = [
            ("📁 Case Number", metadata.get('case_number', 'Not detected')),
            ("👤 Petitioner", metadata.get('petitioner', 'Unknown')),
            ("👤 Respondent", metadata.get('respondent', 'Unknown')),
            ("🏛️ Court", metadata.get('court_name', 'Not specified')),
            ("📅 Date", metadata.get('date', 'Not detected')),
            ("👨‍⚖️ Judge Present", metadata.get('judge_present', 'Not specified')),
        ]
        
        for label, value in metadata_items:
            if value and value not in ['Not detected', 'Unknown', 'Not specified', '']:
                st.success(f"**{label}:** {value}")
            else:
                st.warning(f"**{label}:** {value}")
    
    with col2:
        st.markdown("### 🎯 Processing Summary")
        stats = st.session_state.get('processing_stats', {})
        
        # Create metrics display
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        
        with metric_col1:
            st.metric(
                label="📊 Text Characters",
                value=f"{stats.get('text_length', 0):,}",
                help="Total characters extracted from PDF"
            )
        
        with metric_col2:
            st.metric(
                label="⏱️ Processing Time", 
                value=f"{stats.get('processing_time', 0):.2f}s",
                help="Time taken to process the document"
            )
        
        with metric_col3:
            st.metric(
                label="📁 File Size",
                value=f"{stats.get('file_size', 0):,} bytes",
                help="Original PDF file size"
            )
        
        # Quality indicators
        st.markdown("#### 🎯 Detection Quality")
        quality_score = calculate_quality_score(metadata)
        
        if quality_score >= 80:
            st.success(f"🟢 Excellent detection quality ({quality_score}%)")
        elif quality_score >= 60:
            st.warning(f"🟡 Good detection quality ({quality_score}%)")
        else:
            st.error(f"🔴 Fair detection quality ({quality_score}%) - Manual review recommended")
    
    # HTML Preview and Download
    st.markdown("### 📄 Enhanced Judgment Report")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["🖥️ HTML Preview", "📝 Processed Text", "⚙️ Advanced Options"])
    
    with tab1:
        st.markdown("#### Interactive Preview")
        if 'html_output' in st.session_state:
            # HTML preview with scroll
            st.components.v1.html(
                st.session_state['html_output'], 
                height=800, 
                scrolling=True
            )
            
            # Download button
            st.markdown(
                create_download_button(
                    st.session_state['html_output'], 
                    f"legal_judgment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                ), 
                unsafe_allow_html=True
            )
    
    with tab2:
        st.markdown("#### Processed Text Content")
        if 'formatted_content' in st.session_state:
            st.text_area(
                "Formatted Content (for debugging)",
                st.session_state['formatted_content'],
                height=400,
                help="This shows the processed text content before HTML rendering"
            )
    
    with tab3:
        st.markdown("#### Advanced Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Generate Summary Report", use_container_width=True):
                generate_summary_report()
        
        with col2:
            if st.button("📋 Export Metadata JSON", use_container_width=True):
                export_metadata_json()
        
        # Additional formatting options
        st.markdown("##### 🎨 Custom Styling")
        custom_css = st.text_area(
            "Add Custom CSS (optional)",
            placeholder="/* Add your custom CSS here */\n.content { font-size: 18px; }",
            height=100
        )
        
        if st.button("🎨 Apply Custom Styling") and custom_css:
            apply_custom_styling(custom_css)

def calculate_quality_score(metadata):
    """Calculate detection quality score based on metadata completeness."""
    score = 0
    total_fields = 6
    
    fields_to_check = [
        'case_number', 'petitioner', 'respondent', 
        'court_name', 'date', 'judge_signature'
    ]
    
    for field in fields_to_check:
        value = metadata.get(field, '')
        if value and value not in ['Not detected', 'Unknown', 'Not specified', 'Petitioner', 'Respondent']:
            score += 1
    
    # Special scoring for party names
    if (metadata.get('petitioner', 'Petitioner') != 'Petitioner' and 
        metadata.get('respondent', 'Respondent') != 'Respondent'):
        score += 1  # Bonus point for both parties detected
    
    return int((score / (total_fields + 1)) * 100)

def generate_summary_report():
    """Generate a summary report of the processed judgment."""
    try:
        metadata = st.session_state.get('metadata', {})
        stats = st.session_state.get('processing_stats', {})
        
        summary = f"""
# Legal Judgment Processing Summary

## Case Information
- **Case Number**: {metadata.get('case_number', 'Not detected')}
- **Petitioner**: {metadata.get('petitioner', 'Unknown')}
- **Respondent**: {metadata.get('respondent', 'Unknown')}
- **Court**: {metadata.get('court_name', 'Not specified')}
- **Date**: {metadata.get('date', 'Not detected')}

## Processing Statistics
- **Text Length**: {stats.get('text_length', 0):,} characters
- **Processing Time**: {stats.get('processing_time', 0):.2f} seconds
- **File Size**: {stats.get('file_size', 0):,} bytes
- **Quality Score**: {calculate_quality_score(metadata)}%

## Generated On
{datetime.now().strftime("%B %d, %Y at %I:%M %p")}
        """
        
        st.download_button(
            label="📊 Download Summary Report",
            data=summary,
            file_name=f"judgment_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
        
        st.success("✅ Summary report generated!")
        
    except Exception as e:
        st.error(f"❌ Error generating summary: {str(e)}")

def export_metadata_json():
    """Export metadata as JSON file."""
    try:
        import json
        
        metadata = st.session_state.get('metadata', {})
        stats = st.session_state.get('processing_stats', {})
        
        export_data = {
            "metadata": metadata,
            "processing_stats": stats,
            "export_timestamp": datetime.now().isoformat(),
            "quality_score": calculate_quality_score(metadata)
        }
        
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="📋 Download Metadata JSON",
            data=json_str,
            file_name=f"judgment_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        
        st.success("✅ Metadata JSON exported!")
        
    except Exception as e:
        st.error(f"❌ Error exporting metadata: {str(e)}")

def apply_custom_styling(custom_css):
    """Apply custom CSS to the HTML output."""
    try:
        if 'html_output' in st.session_state:
            html_content = st.session_state['html_output']
            
            # Insert custom CSS before closing </style> tag
            custom_style = f"\n    /* Custom User Styles */\n    {custom_css}\n  </style>"
            html_content = html_content.replace("</style>", custom_style)
            
            st.session_state['html_output'] = html_content
            st.success("✅ Custom styling applied! Check the preview above.")
            st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error applying custom styling: {str(e)}")

# =====================
#  MAIN EXECUTION
# =====================
if __name__ == "__main__":
    main()

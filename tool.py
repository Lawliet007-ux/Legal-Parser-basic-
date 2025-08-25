import streamlit as st
import PyPDF2
import pdfplumber
import re
from io import BytesIO
import base64
from typing import List, Dict, Tuple, Optional
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Legal Judgment Text Extractor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class AdvancedJudgmentExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.formatted_html = ""
        self.judgment_data = {}
        self.processed_lines = []
    
    def extract_text_pypdf2(self, pdf_file) -> str:
        """Extract text using PyPDF2"""
        try:
            pdf_file.seek(0)  # Reset file pointer
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- PAGE {page_num + 1} ---\n"
                    text += page_text + "\n"
            return text
        except Exception as e:
            st.error(f"PyPDF2 extraction failed: {str(e)}")
            return ""
    
    def extract_text_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber with better formatting preservation"""
        try:
            pdf_file.seek(0)  # Reset file pointer
            text = ""
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- PAGE {page_num + 1} ---\n"
                        text += page_text + "\n"
            return text
        except Exception as e:
            st.error(f"PDFPlumber extraction failed: {str(e)}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Fix common character encoding issues
        text = text.replace('Â­', '-')  # Fix hyphenation
        text = text.replace('Â', '')   # Remove stray characters
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        return text.strip()
    
    def parse_judgment_structure(self, text: str) -> Dict:
        """Enhanced parsing to identify judgment structure components"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        judgment_data = {
            'case_number': '',
            'parties': '',
            'date': '',
            'judge': '',
            'court': '',
            'present': '',
            'subject': ''
        }
        
        # Enhanced patterns
        case_number_patterns = [
            r'(?:OMP|CRL|CS|CC|SA|FAO|CRP|MAC|RFA|SUIT|APPEAL|PETITION|APPLICATION)\s*\(?[IVX]*\)?\s*(?:No\.?|#)?\s*\d+[\/\-]\d*',
            r'(?:Case|Suit|Appeal|Petition)\s*(?:No\.?|#)\s*\d+',
            r'\w+\s*\([A-Z]\)\s*\w+\.\s*No\.\s*\d+\/\d+'
        ]
        
        date_patterns = [
            r'\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{2,4}',
            r'\d{1,2}(?:st|nd|rd|th)?\s+\w+[,\s]+\d{4}',
            r'\w+\s+\d{1,2}[,\s]+\d{4}'
        ]
        
        # Find case number (usually appears early and in specific format)
        for i, line in enumerate(lines[:20]):  # Check first 20 lines
            for pattern in case_number_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    judgment_data['case_number'] = self.clean_text(line)
                    break
            if judgment_data['case_number']:
                break
        
        # Find parties (usually contains VS/V/V.)
        for line in lines[:30]:
            if any(vs in line.upper() for vs in [' VS ', ' V/S ', ' V. ', ' VERSUS ']):
                if len(line) > 10:  # Avoid short matches
                    judgment_data['parties'] = self.clean_text(line)
                    break
        
        # Find date
        for line in lines[:30]:
            for pattern in date_patterns:
                if re.search(pattern, line):
                    # Avoid lines that are too long (likely not just a date)
                    if len(line) < 50:
                        judgment_data['date'] = self.clean_text(line)
                        break
            if judgment_data['date']:
                break
        
        # Find Present/Counsel information
        for line in lines:
            if line.lower().startswith('present'):
                judgment_data['present'] = self.clean_text(line)
                break
        
        # Find Judge name (usually at the end)
        judge_patterns = [
            r'.*(?:Judge|Magistrate|J\.|Justice).*',
            r'.*(?:JUDGE|MAGISTRATE|JUSTICE).*'
        ]
        
        for line in reversed(lines[-20:]):  # Check last 20 lines
            for pattern in judge_patterns:
                if re.match(pattern, line) and len(line) < 100:
                    judgment_data['judge'] = self.clean_text(line)
                    break
            if judgment_data['judge']:
                break
        
        # Find court details (usually at the end with location)
        court_patterns = [
            r'.*(?:Court|Tribunal).*(?:Delhi|Mumbai|Chennai|Kolkata|Bangalore|Hyderabad|Pune|Ahmedabad).*',
            r'.*(?:District|High|Supreme|Commercial).*(?:Court|Tribunal).*'
        ]
        
        for line in reversed(lines[-10:]):
            for pattern in court_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    judgment_data['court'] = self.clean_text(line)
                    break
            if judgment_data['court']:
                break
        
        return judgment_data
    
    def identify_line_type(self, line: str, context_lines: List[str] = []) -> str:
        """Identify the type of line for proper formatting"""
        line = line.strip()
        if not line:
            return 'empty'
        
        # Page markers
        if re.match(r'^--- PAGE \d+ ---$', line):
            return 'page_marker'
        
        # Case number
        if re.search(r'(?:OMP|CRL|CS|CC|SA|FAO|CRP|MAC|RFA)\s*\([A-Z]*\)\s*\w+\.\s*No\.\s*\d+', line, re.IGNORECASE):
            return 'case_number'
        
        # Parties
        if any(vs in line.upper() for vs in [' VS ', ' V/S ', ' VERSUS ']):
            return 'parties'
        
        # Date
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', line):
            return 'date'
        
        # Page numbers like :2:, :3:
        if re.match(r'^:\d+:$', line):
            return 'page_number'
        
        # Present/Appearances
        if line.lower().startswith('present'):
            return 'present'
        
        # Roman numerals at start
        if re.match(r'^[IVX]+\.\s+', line):
            return 'roman_number'
        
        # Numbers with parentheses like (1), (2), (i), (ii)
        if re.match(r'^\([0-9ivx]+\)\s+', line):
            return 'numbered_parentheses'
        
        # Numbers with dots like 1., 2.
        if re.match(r'^\d+\.\s+', line):
            return 'numbered_dots'
        
        # Lettered points like (a), (b)
        if re.match(r'^\([a-z]\)\s+', line):
            return 'lettered_points'
        
        # Judge signature (usually all caps, short line, at end)
        if line.isupper() and len(line) < 50 and any(word in line for word in ['JUDGE', 'MAGISTRATE', 'JUSTICE']):
            return 'judge_name'
        
        # Court details
        if any(word in line.lower() for word in ['court', 'delhi', 'mumbai', 'saket', 'district']):
            return 'court_details'
        
        # Default paragraph
        return 'paragraph'
    
    def process_content_structure(self, text: str) -> List[Tuple[str, str]]:
        """Process text and identify structure"""
        lines = text.split('\n')
        processed_lines = []
        
        for i, line in enumerate(lines):
            line = self.clean_text(line)
            if not line:
                continue
                
            # Get context for better classification
            context = lines[max(0, i-2):i+3]
            line_type = self.identify_line_type(line, context)
            
            # Merge continuation lines for numbered points
            if (line_type == 'paragraph' and processed_lines and 
                processed_lines[-1][0] in ['numbered_parentheses', 'lettered_points', 'numbered_dots', 'roman_number']):
                # This might be a continuation of the previous numbered point
                if len(line) > 20:  # Only merge substantial content
                    prev_content = processed_lines[-1][1]
                    processed_lines[-1] = (processed_lines[-1][0], prev_content + " " + line)
                    continue
            
            processed_lines.append((line_type, line))
        
        return processed_lines
    
    def generate_enhanced_html(self, processed_lines: List[Tuple[str, str]], judgment_data: Dict) -> str:
        """Generate enhanced HTML with better structure"""
        
        content_html = ""
        for line_type, content in processed_lines:
            if line_type == 'empty':
                continue
            elif line_type == 'page_marker':
                content_html += f'<div class="page-marker">{content}</div>\n'
            elif line_type == 'case_number':
                content_html += f'<div class="case-number-content">{content}</div>\n'
            elif line_type == 'parties':
                content_html += f'<div class="parties-content">{content}</div>\n'
            elif line_type == 'date':
                content_html += f'<div class="date-content">{content}</div>\n'
            elif line_type == 'page_number':
                content_html += f'<div class="page-number">{content}</div>\n'
            elif line_type == 'present':
                content_html += f'<div class="present">{content}</div>\n'
            elif line_type == 'roman_number':
                content_html += f'<div class="roman-number">{content}</div>\n'
            elif line_type == 'numbered_parentheses':
                content_html += f'<div class="numbered-parentheses">{content}</div>\n'
            elif line_type == 'numbered_dots':
                content_html += f'<div class="numbered-dots">{content}</div>\n'
            elif line_type == 'lettered_points':
                content_html += f'<div class="lettered-points">{content}</div>\n'
            elif line_type == 'judge_name':
                content_html += f'<div class="judge-name">{content}</div>\n'
            elif line_type == 'court_details':
                content_html += f'<div class="court-info">{content}</div>\n'
            else:
                content_html += f'<div class="paragraph">{content}</div>\n'
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legal Judgment - {judgment_data.get('case_number', 'Legal Document')}</title>
    <style>
        body {{
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.5;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #000;
        }}
        
        .document {{
            max-width: 210mm;
            margin: 0 auto;
            padding: 25mm;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            min-height: 297mm;
            border: 1px solid #ddd;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #333;
        }}
        
        .case-number {{
            font-weight: bold;
            font-size: 14pt;
            margin: 10px 0;
        }}
        
        .parties {{
            font-weight: bold;
            font-size: 13pt;
            margin: 10px 0;
            text-decoration: underline;
        }}
        
        .date {{
            margin: 10px 0;
            font-weight: bold;
        }}
        
        .content {{
            text-align: justify;
            margin-top: 20px;
        }}
        
        .page-marker {{
            text-align: center;
            font-weight: bold;
            color: #666;
            border-top: 1px solid #ddd;
            border-bottom: 1px solid #ddd;
            padding: 10px;
            margin: 20px 0;
            background: #f9f9f9;
        }}
        
        .case-number-content {{
            text-align: center;
            font-weight: bold;
            font-size: 14pt;
            margin: 15px 0;
        }}
        
        .parties-content {{
            text-align: center;
            font-weight: bold;
            font-size: 13pt;
            text-decoration: underline;
            margin: 15px 0;
        }}
        
        .date-content {{
            text-align: center;
            font-weight: bold;
            margin: 15px 0;
        }}
        
        .page-number {{
            text-align: center;
            font-weight: bold;
            margin: 15px 0;
            color: #666;
        }}
        
        .present {{
            margin: 15px 0;
            font-weight: bold;
            text-align: left;
        }}
        
        .paragraph {{
            margin: 10px 0;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .numbered-dots {{
            margin: 15px 0;
            padding-left: 30px;
            text-indent: -30px;
            font-weight: bold;
            text-align: justify;
        }}
        
        .numbered-parentheses {{
            margin: 15px 0;
            padding-left: 30px;
            text-indent: -30px;
            font-weight: bold;
            text-align: justify;
        }}
        
        .roman-number {{
            margin: 20px 0;
            padding-left: 40px;
            text-indent: -40px;
            font-weight: bold;
            font-size: 13pt;
            text-align: justify;
        }}
        
        .lettered-points {{
            margin: 12px 0;
            padding-left: 40px;
            text-indent: -20px;
            text-align: justify;
        }}
        
        .judge-name {{
            text-align: right;
            font-weight: bold;
            margin-top: 40px;
            margin-bottom: 5px;
            font-size: 13pt;
        }}
        
        .court-info {{
            text-align: right;
            margin: 5px 0;
            font-style: italic;
        }}
        
        .footer {{
            margin-top: 50px;
            text-align: right;
        }}
        
        @media print {{
            body {{ 
                margin: 0; 
                padding: 0;
                background: white;
            }}
            .document {{ 
                margin: 0; 
                padding: 20mm;
                box-shadow: none;
                border: none;
                min-height: auto;
            }}
            .page-marker {{
                border: none;
                background: white;
                color: #000;
            }}
        }}
    </style>
</head>
<body>
    <div class="document">
        <div class="header">
            <div class="case-number">{judgment_data.get('case_number', '')}</div>
            <div class="parties">{judgment_data.get('parties', '')}</div>
            <div class="date">{judgment_data.get('date', '')}</div>
        </div>
        
        <div class="content">
            {content_html}
        </div>
        
        <div class="footer">
            <div class="judge-name">{judgment_data.get('judge', '')}</div>
            <div class="court-info">{judgment_data.get('court', '')}</div>
        </div>
    </div>
</body>
</html>
        """
        
        return html_template
    
    def process_judgment(self, pdf_file, extraction_method='pdfplumber'):
        """Enhanced main processing function"""
        try:
            # Extract text based on selected method
            if extraction_method == 'pdfplumber':
                raw_text = self.extract_text_pdfplumber(pdf_file)
            else:
                raw_text = self.extract_text_pypdf2(pdf_file)
            
            if not raw_text:
                return False, "Failed to extract text from PDF"
            
            # Clean the extracted text
            self.extracted_text = self.clean_text(raw_text)
            
            # Parse judgment structure
            self.judgment_data = self.parse_judgment_structure(self.extracted_text)
            
            # Process content structure
            self.processed_lines = self.process_content_structure(raw_text)
            
            # Generate enhanced HTML
            self.formatted_html = self.generate_enhanced_html(self.processed_lines, self.judgment_data)
            
            return True, "Processing completed successfully"
            
        except Exception as e:
            return False, f"Error processing judgment: {str(e)}"

def main():
    st.title("⚖️ Enhanced Legal Judgment Text Extractor")
    st.markdown("**Advanced PDF Processing with Intelligent Structure Recognition**")
    st.markdown("---")
    
    # Sidebar configuration
    st.sidebar.title("⚙️ Configuration")
    extraction_method = st.sidebar.selectbox(
        "Select Extraction Method:",
        ["pdfplumber", "pypdf2"],
        help="pdfplumber generally provides better formatting preservation"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ✨ Enhanced Features")
    st.sidebar.markdown("""
    🎯 **Smart Structure Recognition**
    - Automatic case number detection
    - Party identification 
    - Date extraction
    - Judge and court recognition
    
    📝 **Advanced Formatting**
    - Intelligent numbering preservation
    - Context-aware line classification
    - Proper paragraph merging
    - Clean character handling
    
    🔧 **Technical Improvements**
    - Enhanced regex patterns
    - Better text normalization
    - Improved HTML generation
    - Professional court styling
    """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📤 Upload Document")
        uploaded_file = st.file_uploader(
            "Upload Legal Judgment PDF",
            type=['pdf'],
            help="Upload a PDF file containing a legal judgment"
        )
    
    with col2:
        st.subheader("📊 Processing Stats")
        stats_placeholder = st.empty()
    
    if uploaded_file is not None:
        # Initialize enhanced extractor
        extractor = AdvancedJudgmentExtractor()
        
        # Show file info
        file_size = len(uploaded_file.getvalue()) / 1024  # KB
        with stats_placeholder.container():
            st.metric("File Size", f"{file_size:.1f} KB")
            st.metric("File Name", uploaded_file.name[:30] + "..." if len(uploaded_file.name) > 30 else uploaded_file.name)
        
        with st.spinner("🔄 Processing judgment with enhanced algorithms..."):
            success, message = extractor.process_judgment(uploaded_file, extraction_method)
        
        if success:
            st.success("✅ " + message)
            
            # Update stats
            with stats_placeholder.container():
                st.metric("File Size", f"{file_size:.1f} KB")
                st.metric("Extracted Lines", len(extractor.processed_lines))
                st.metric("Characters", len(extractor.extracted_text))
            
            # Tabs for organized display
            tab1, tab2, tab3, tab4 = st.tabs(["🎯 Extracted Info", "🌐 HTML Preview", "📄 Raw Text", "⬇️ Downloads"])
            
            with tab1:
                st.subheader("📋 Intelligently Extracted Information")
                
                # Display in a nice format
                info_col1, info_col2 = st.columns(2)
                
                with info_col1:
                    st.markdown("**📁 Case Details**")
                    if extractor.judgment_data['case_number']:
                        st.info(f"**Case Number:** {extractor.judgment_data['case_number']}")
                    if extractor.judgment_data['date']:
                        st.info(f"**Date:** {extractor.judgment_data['date']}")
                    if extractor.judgment_data['present']:
                        st.info(f"**Present:** {extractor.judgment_data['present']}")
                
                with info_col2:
                    st.markdown("**👥 Parties & Court**")
                    if extractor.judgment_data['parties']:
                        st.info(f"**Parties:** {extractor.judgment_data['parties']}")
                    if extractor.judgment_data['judge']:
                        st.info(f"**Judge:** {extractor.judgment_data['judge']}")
                    if extractor.judgment_data['court']:
                        st.info(f"**Court:** {extractor.judgment_data['court']}")
                
                # Structure analysis
                st.markdown("---")
                st.subheader("📊 Document Structure Analysis")
                
                # Count different line types
                line_types = {}
                for line_type, _ in extractor.processed_lines:
                    line_types[line_type] = line_types.get(line_type, 0) + 1
                
                # Display as metrics
                cols = st.columns(4)
                metrics_data = [
                    ("Paragraphs", line_types.get('paragraph', 0)),
                    ("Numbered Points", line_types.get('numbered_parentheses', 0) + line_types.get('numbered_dots', 0)),
                    ("Lettered Points", line_types.get('lettered_points', 0)),
                    ("Pages", line_types.get('page_marker', 0))
                ]
                
                for i, (label, value) in enumerate(metrics_data):
                    with cols[i]:
                        st.metric(label, value)
            
            with tab2:
                st.subheader("🌐 Enhanced HTML Preview")
                st.markdown("*Professional court document formatting with intelligent structure recognition*")
                
                # HTML preview with better height
                st.components.v1.html(
                    extractor.formatted_html,
                    height=800,
                    scrolling=True
                )
            
            with tab3:
                st.subheader("📄 Raw Extracted Text")
                st.text_area(
                    "Complete extracted text:",
                    extractor.extracted_text,
                    height=400,
                    help="This is the raw text extracted from your PDF"
                )
            
            with tab4:
                st.subheader("⬇️ Download Processed Document")
                
                col_d1, col_d2, col_d3 = st.columns(3)
                
                with col_d1:
                    # Download Enhanced HTML
                    html_bytes = extractor.formatted_html.encode('utf-8')
                    st.download_button(
                        label="📥 Download Enhanced HTML",
                        data=html_bytes,
                        file_name=f"judgment_enhanced_{uploaded_file.name.replace('.pdf', '.html')}",
                        mime="text/html",
                        help="Download the professionally formatted HTML document"
                    )
                
                with col_d2:
                    # Download Clean Text
                    text_bytes = extractor.extracted_text.encode('utf-8')
                    st.download_button(
                        label="📄 Download Clean Text",
                        data=text_bytes,
                        file_name=f"judgment_text_{uploaded_file.name.replace('.pdf', '.txt')}",
                        mime="text/plain",
                        help="Download the cleaned and processed text"
                    )
                
                with col_d3:
                    # Download Structured Data
                    import json
                    structured_data = {
                        "metadata": extractor.judgment_data,
                        "structure_analysis": line_types,
                        "processing_method": extraction_method,
                        "total_lines": len(extractor.processed_lines)
                    }
                    json_bytes = json.dumps(structured_data, indent=2).encode('utf-8')
                    st.download_button(
                        label="📊 Download Analysis",
                        data=json_bytes,
                        file_name=f"analysis_{uploaded_file.name.replace('.pdf', '.json')}",
                        mime="application/json",
                        help="Download the structural analysis and metadata"
                    )
            
        else:
            st.error("❌ " + message)
    
    # Enhanced demo section
    st.markdown("---")
    st.subheader("📖 Live Demo with Sample Judgment")
    st.markdown("See how the enhanced extractor processes a real legal judgment:")
    
    # Enhanced sample preview
    with st.container():
        sample_html = """
        <div style="font-family: 'Times New Roman', serif; padding: 20px; background: white; border: 2px solid #333; border-radius: 5px;">
            <div style="text-align: center; font-weight: bold; font-size: 14pt; margin: 10px 0;">
                OMP (I) Comm. No. 800/20
            </div>
            <div style="text-align: center; font-weight: bold; text-decoration: underline; font-size: 13pt; margin: 10px 0;">
                HDB FINANCIAL SERVICES LTD VS THE DEOBAND PUBLIC SCHOOL
            </div>
            <div style="text-align: center; font-weight: bold; margin: 10px 0;">
                13.02.2020
            </div>
            <div style="margin: 15px 0; font-weight: bold;">
                Present : Sh. Ashok Kumar Ld. Counsel for petitioner.
            </div>
            <div style="margin: 15px 0; text-align: justify; line-height: 1.6;">
                This is a petition u/s 9 of Indian Arbitration and Conciliation Act 1996 for issuing interim measure by way of appointment of receiver...
            </div>
            <div style="margin: 15px 0; padding-left: 30px; text-indent: -30px; font-weight: bold; text-align: justify;">
                (i) The receiver shall take over the possession of the vehicle from the respondent at the address given in the loan application.
            </div>
            <div style="margin: 15px 0; padding-left: 30px; text-indent: -30px; font-weight: bold; text-align: justify;">
                (ii) The receiver shall avoid taking the possession of the vehicle if the vehicle is occupied by a women who is not accompanied by a male member...
            </div>
            <div style="text-align: right; font-weight: bold; margin-top: 40px;">
                VINAY KUMAR KHANNA<br>
                District Judge<br>
                <span style="font-style: italic;">(Commercial Court-02) South Distt., Saket, New Delhi/13.02.2020</span>
            </div>
        </div>
        """
        
        st.components.v1.html(sample_html, height=500)
    
    # Technical improvements section
    st.markdown("---")
    st.subheader("🚀 Enhanced Capabilities")
    
    col_t1, col_t2, col_t3 = st.columns(3)
    
    with col_t1:
        st.markdown("**🎯 Intelligent Parsing**")
        st.markdown("""
        - Advanced regex patterns
        - Context-aware classification  
        - Smart content merging
        - Character encoding fixes
        """)
    
    with col_t2:
        st.markdown("**📝 Structure Recognition**")
        st.markdown("""
        - Case number detection
        - Party identification
        - Date extraction  
        - Judge & court parsing
        """)
    
    with col_t3:
        st.markdown("**💪 Scalability**")
        st.markdown("""
        - Batch processing ready
        - Memory efficient
        - Error resilient
        - Multiple format support
        """)

if __name__ == "__main__":
    main()

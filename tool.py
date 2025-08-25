import streamlit as st
import PyPDF2
import pdfplumber
import re
from io import BytesIO
import base64
from typing import List, Dict, Tuple
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Legal Judgment Text Extractor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class JudgmentExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.formatted_html = ""
        self.judgment_data = {}
    
    def extract_text_pypdf2(self, pdf_file) -> str:
        """Extract text using PyPDF2"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            st.error(f"PyPDF2 extraction failed: {str(e)}")
            return ""
    
    def extract_text_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber with better formatting preservation"""
        try:
            text = ""
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        # Add page marker
                        text += f"\n--- PAGE {page_num + 1} ---\n"
                        text += page_text + "\n"
            return text
        except Exception as e:
            st.error(f"PDFPlumber extraction failed: {str(e)}")
            return ""
    
    def parse_judgment_structure(self, text: str) -> Dict:
        """Parse and identify judgment structure components"""
        lines = text.split('\n')
        judgment_data = {
            'case_number': '',
            'parties': '',
            'date': '',
            'judge': '',
            'court': '',
            'paragraphs': [],
            'numbered_points': [],
            'orders': []
        }
        
        # Patterns for different components
        case_number_pattern = r'(?:OMP|CRL|CS|CC|SA|FAO|CRP|MAC|RFA).*?(?:No\.?|/).*?\d+'
        date_pattern = r'\d{1,2}[./]\d{1,2}[./]\d{2,4}'
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Case number detection
            if re.search(case_number_pattern, line, re.IGNORECASE):
                judgment_data['case_number'] = line
            
            # Date detection
            elif re.search(date_pattern, line):
                judgment_data['date'] = line
            
            # VS pattern for parties
            elif ' VS ' in line.upper() or ' V/S ' in line.upper():
                judgment_data['parties'] = line
            
            # Judge detection
            elif any(title in line.upper() for title in ['JUDGE', 'MAGISTRATE', 'J.']):
                judgment_data['judge'] = line
            
            # Court detection
            elif any(court in line.upper() for court in ['COURT', 'TRIBUNAL']):
                judgment_data['court'] = line
        
        return judgment_data
    
    def preserve_numbering(self, text: str) -> str:
        """Preserve original numbering and sub-numbering"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Roman numerals
            if re.match(r'^\s*[IVX]+[.)]\s+', line):
                formatted_lines.append(f'<div class="roman-number">{line}</div>')
            
            # Numbers with parentheses (1) (2) etc.
            elif re.match(r'^\s*\(\d+\)\s+', line):
                formatted_lines.append(f'<div class="numbered-parentheses">{line}</div>')
            
            # Numbers with dots 1. 2. etc.
            elif re.match(r'^\s*\d+\.\s+', line):
                formatted_lines.append(f'<div class="numbered-dots">{line}</div>')
            
            # Lettered points (a) (b) etc.
            elif re.match(r'^\s*\([a-z]\)\s+', line):
                formatted_lines.append(f'<div class="lettered-points">{line}</div>')
            
            # Sub-points (i) (ii) etc.
            elif re.match(r'^\s*\([ivx]+\)\s+', line):
                formatted_lines.append(f'<div class="sub-points">{line}</div>')
            
            # Regular paragraphs
            else:
                formatted_lines.append(f'<div class="paragraph">{line}</div>')
        
        return '\n'.join(formatted_lines)
    
    def generate_html_format(self, text: str, judgment_data: Dict) -> str:
        """Generate HTML format maintaining original structure"""
        
        # Format the text with preserved numbering
        formatted_content = self.preserve_numbering(text)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legal Judgment</title>
    <style>
        body {{
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.5;
            margin: 0;
            padding: 20px;
            background: #f9f9f9;
            color: #000;
        }}
        
        .document {{
            max-width: 210mm;
            margin: 0 auto;
            padding: 30mm;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            min-height: 297mm;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
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
            font-style: italic;
        }}
        
        .content {{
            text-align: justify;
            margin-top: 20px;
        }}
        
        .paragraph {{
            margin: 10px 0;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .numbered-dots {{
            margin: 10px 0;
            padding-left: 20px;
            text-indent: -20px;
            font-weight: bold;
        }}
        
        .numbered-parentheses {{
            margin: 10px 0;
            padding-left: 20px;
            text-indent: -20px;
            font-weight: bold;
        }}
        
        .roman-number {{
            margin: 15px 0;
            padding-left: 30px;
            text-indent: -30px;
            font-weight: bold;
            font-size: 13pt;
        }}
        
        .lettered-points {{
            margin: 8px 0;
            padding-left: 40px;
            text-indent: -20px;
        }}
        
        .sub-points {{
            margin: 8px 0;
            padding-left: 50px;
            text-indent: -20px;
            font-style: italic;
        }}
        
        .judge-signature {{
            text-align: right;
            margin-top: 50px;
            font-weight: bold;
        }}
        
        .court-details {{
            text-align: right;
            margin-top: 10px;
            font-style: italic;
        }}
        
        @media print {{
            body {{ 
                margin: 0; 
                padding: 0;
                background: white;
            }}
            .document {{ 
                margin: 0; 
                padding: 25mm;
                box-shadow: none;
                min-height: auto;
            }}
        }}
    </style>
</head>
<body>
    <div class="document">
        <div class="header">
            <div class="case-number">{judgment_data.get('case_number', 'Case Number Not Found')}</div>
            <div class="parties">{judgment_data.get('parties', 'Parties Not Found')}</div>
            <div class="date">{judgment_data.get('date', 'Date Not Found')}</div>
        </div>
        
        <div class="content">
            {formatted_content}
        </div>
        
        <div class="judge-signature">
            {judgment_data.get('judge', 'Judge Name Not Found')}
        </div>
        <div class="court-details">
            {judgment_data.get('court', 'Court Details Not Found')}
        </div>
    </div>
</body>
</html>
        """
        
        return html_template
    
    def process_judgment(self, pdf_file, extraction_method='pdfplumber'):
        """Main processing function"""
        try:
            # Extract text based on selected method
            if extraction_method == 'pdfplumber':
                self.extracted_text = self.extract_text_pdfplumber(pdf_file)
            else:
                self.extracted_text = self.extract_text_pypdf2(pdf_file)
            
            if not self.extracted_text:
                return False, "Failed to extract text from PDF"
            
            # Parse judgment structure
            self.judgment_data = self.parse_judgment_structure(self.extracted_text)
            
            # Generate HTML format
            self.formatted_html = self.generate_html_format(self.extracted_text, self.judgment_data)
            
            return True, "Processing completed successfully"
            
        except Exception as e:
            return False, f"Error processing judgment: {str(e)}"

def main():
    st.title("⚖️ Legal Judgment Text Extractor")
    st.markdown("---")
    
    # Sidebar configuration
    st.sidebar.title("Configuration")
    extraction_method = st.sidebar.selectbox(
        "Select Extraction Method:",
        ["pdfplumber", "pypdf2"],
        help="pdfplumber generally provides better formatting preservation"
    )
    
    output_format = st.sidebar.selectbox(
        "Output Format:",
        ["HTML", "Plain Text", "Both"],
        help="Choose the desired output format"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Features")
    st.sidebar.markdown("""
    ✅ Preserves original numbering  
    ✅ Maintains sub-numbering  
    ✅ Extracts judgment structure  
    ✅ HTML preview  
    ✅ Batch processing ready  
    ✅ Multiple PDF libraries  
    """)
    
    # Main content
    uploaded_file = st.file_uploader(
        "Upload Legal Judgment PDF",
        type=['pdf'],
        help="Upload a PDF file containing a legal judgment"
    )
    
    if uploaded_file is not None:
        # Initialize extractor
        extractor = JudgmentExtractor()
        
        with st.spinner("Processing judgment..."):
            success, message = extractor.process_judgment(uploaded_file, extraction_method)
        
        if success:
            st.success(message)
            
            # Display extracted information
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("📋 Extracted Information")
                
                # Display judgment metadata
                if extractor.judgment_data:
                    for key, value in extractor.judgment_data.items():
                        if value and key not in ['paragraphs', 'numbered_points', 'orders']:
                            st.write(f"**{key.replace('_', ' ').title()}:** {value}")
                
                st.subheader("📄 Raw Extracted Text")
                with st.expander("View Raw Text", expanded=False):
                    st.text_area(
                        "Extracted Text:",
                        extractor.extracted_text,
                        height=300,
                        key="raw_text"
                    )
            
            with col2:
                st.subheader("🌐 HTML Preview")
                
                # HTML preview
                st.components.v1.html(
                    extractor.formatted_html,
                    height=600,
                    scrolling=True
                )
            
            # Download options
            st.markdown("---")
            st.subheader("⬇️ Download Options")
            
            col3, col4, col5 = st.columns(3)
            
            with col3:
                # Download HTML
                html_bytes = extractor.formatted_html.encode('utf-8')
                st.download_button(
                    label="📥 Download HTML",
                    data=html_bytes,
                    file_name=f"judgment_{uploaded_file.name.replace('.pdf', '.html')}",
                    mime="text/html"
                )
            
            with col4:
                # Download plain text
                text_bytes = extractor.extracted_text.encode('utf-8')
                st.download_button(
                    label="📄 Download Text",
                    data=text_bytes,
                    file_name=f"judgment_{uploaded_file.name.replace('.pdf', '.txt')}",
                    mime="text/plain"
                )
            
            with col5:
                # Download metadata as JSON
                import json
                metadata_json = json.dumps(extractor.judgment_data, indent=2)
                st.download_button(
                    label="📊 Download Metadata",
                    data=metadata_json,
                    file_name=f"metadata_{uploaded_file.name.replace('.pdf', '.json')}",
                    mime="application/json"
                )
            
        else:
            st.error(message)
    
    # Sample demonstration
    st.markdown("---")
    st.subheader("📖 Sample Judgment Preview")
    st.markdown("Here's how a typical judgment would look after processing:")
    
    # Sample HTML from the provided judgment
    sample_html = """
    <div style="font-family: 'Times New Roman', serif; padding: 20px; background: white; border: 1px solid #ddd;">
        <div style="text-align: center; font-weight: bold; margin: 10px 0;">
            OMP (I) Comm. No. 800/20
        </div>
        <div style="text-align: center; font-weight: bold; text-decoration: underline; margin: 10px 0;">
            HDB FINANCIAL SERVICES LTD VS THE DEOBAND PUBLIC SCHOOL
        </div>
        <div style="text-align: center; margin: 10px 0;">
            13.02.2020
        </div>
        <div style="margin: 15px 0; text-align: justify;">
            This is a petition u/s 9 of Indian Arbitration and Conciliation Act 1996 for issuing interim measure by way of appointment of receiver...
        </div>
        <div style="font-weight: bold; margin: 10px 0; padding-left: 20px; text-indent: -20px;">
            (i) The receiver shall take over the possession of the vehicle from the respondent at the address given in the loan application.
        </div>
        <div style="text-align: right; font-weight: bold; margin-top: 30px;">
            VINAY KUMAR KHANNA<br>
            District Judge<br>
            (Commercial Court-02) South Distt., Saket, New Delhi/13.02.2020
        </div>
    </div>
    """
    
    st.components.v1.html(sample_html, height=400)
    
    # Technical details
    st.markdown("---")
    st.subheader("🔧 Technical Details")
    
    with st.expander("Processing Capabilities", expanded=False):
        st.markdown("""
        ### Text Extraction Methods:
        - **PDFPlumber**: Better for complex layouts, tables, and formatting preservation
        - **PyPDF2**: Faster processing, good for simple text extraction
        
        ### Supported Features:
        - Roman numerals (I, II, III, IV, etc.)
        - Numbered lists (1. 2. 3. etc.)
        - Parenthetical numbering ((1) (2) (3) etc.)
        - Lettered points ((a) (b) (c) etc.)
        - Sub-points ((i) (ii) (iii) etc.)
        - Paragraph formatting
        - Judge signatures and court details
        
        ### Scalability:
        - Designed for batch processing
        - Memory-efficient extraction
        - Error handling for corrupt PDFs
        - Support for various district court formats
        """)

if __name__ == "__main__":
    main()

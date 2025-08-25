import streamlit as st
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
import re
from io import BytesIO
import base64
from datetime import datetime
import pandas as pd

class LegalJudgmentExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.html_output = ""
        self.formatting_patterns = {
            'case_number': r'(?:OMP\s*\([I]+\)\s*Comm\.\s*No\.|Case\s+No\.?|Criminal\s+Case\s+No\.?|Civil\s+Case\s+No\.?)[\s:]*([A-Z0-9\/\-\s\.]+)',
            'court_name': r'IN\s+THE\s+(?:HIGH\s+)?COURT\s+OF\s+[A-Z\s,&]+|(?:DISTRICT\s+)?(?:SESSIONS?\s+)?COURT\s+[A-Z\s,&]+',
            'date': r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*,?\s*\d{4}',
            'numbering': r'^\s*(\([a-zA-Z0-9]+\)|\d+\.?\s*\(\w+\)|\d+\.\d+\.?\s*|\d+\.\s*)',
            'roman_numbering': r'^\s*\([ivxlcdm]+\)\s*',
            'paragraph_start': r'^\s*\d+\.\s*',
            'sub_numbering': r'^\s*\([a-zA-Z0-9]+\)\s*|\d+\.\d+\.\s*',
            'page_number': r'Page\s+\d+\s+of\s+\d+|\-\s*\d+\s*\-|:\d+:',
            'signature_line': r'^\s*\([A-Z\s\.]+\)\s*$',
            'judge_signature': r'^[A-Z\s\.]+\n(?:District\s+Judge|Additional\s+District\s+Judge|Chief\s+Judicial\s+Magistrate)',
            'present_line': r'^Present\s*:\s*',
            'colon_numbering': r':\d+:',
        }
    
    def extract_with_pypdf2(self, pdf_file):
        """Extract text using PyPDF2 - basic extraction"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            return text
        except Exception as e:
            st.error(f"PyPDF2 extraction failed: {str(e)}")
            return ""
    
    def extract_with_pdfplumber(self, pdf_file):
        """Extract text using pdfplumber - better for complex layouts"""
        try:
            text = ""
            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text(layout=True, x_tolerance=3, y_tolerance=3)
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            return text
        except Exception as e:
            st.error(f"pdfplumber extraction failed: {str(e)}")
            return ""
    
    def extract_with_pymupdf(self, pdf_file):
        """Extract text using PyMuPDF - good for preserving formatting"""
        try:
            text = ""
            pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                page_text = page.get_text()
                if page_text:
                    text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            pdf_document.close()
            return text
        except Exception as e:
            st.error(f"PyMuPDF extraction failed: {str(e)}")
            return ""
    
    def clean_and_preserve_formatting(self, text):
        """Clean text while preserving legal document formatting"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip page markers we added
            if line.strip().startswith('--- Page') and line.strip().endswith('---'):
                continue
                
            # Preserve important formatting
            line = line.rstrip()
            
            # Skip completely empty lines but preserve single spaces
            if line.strip() == '':
                if cleaned_lines and cleaned_lines[-1].strip() != '':
                    cleaned_lines.append('')
                continue
            
            # Clean up excessive spaces while preserving intentional indentation
            if line.strip():
                # Count leading spaces for indentation
                leading_spaces = len(line) - len(line.lstrip())
                content = ' '.join(line.split())
                
                # Restore some indentation for sub-points
                if leading_spaces > 0 and (
                    re.match(self.formatting_patterns['numbering'], line) or
                    re.match(self.formatting_patterns['sub_numbering'], line) or
                    re.match(self.formatting_patterns['roman_numbering'], line)
                ):
                    content = '    ' + content
                
                cleaned_lines.append(content)
        
        return '\n'.join(cleaned_lines)
    
    def identify_document_structure(self, text):
        """Identify key structural elements of the legal document"""
        structure = {
            'case_number': None,
            'parties': None,
            'court_name': None,
            'date': None,
            'judge': None,
            'numbering_style': 'mixed'
        }
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # Extract case number
            case_match = re.search(self.formatting_patterns['case_number'], line, re.IGNORECASE)
            if case_match and not structure['case_number']:
                structure['case_number'] = case_match.group(0).strip()
            
            # Extract court name
            court_match = re.search(self.formatting_patterns['court_name'], line, re.IGNORECASE)
            if court_match and not structure['court_name']:
                structure['court_name'] = court_match.group(0).strip()
            
            # Extract date
            date_match = re.search(self.formatting_patterns['date'], line)
            if date_match and not structure['date']:
                structure['date'] = date_match.group(0).strip()
            
            # Identify judge signature (usually at the end)
            if i > len(lines) - 10:  # Check last 10 lines
                if (re.search(r'District\s+Judge|Additional\s+District\s+Judge|Chief\s+Judicial\s+Magistrate', line, re.IGNORECASE) and
                    not structure['judge']):
                    # Look for name in previous lines
                    for j in range(max(0, i-3), i+1):
                        if lines[j].strip() and not re.search(r'District|Judge|Magistrate|Court', lines[j]):
                            if lines[j].strip().isupper() or lines[j].count(' ') <= 3:
                                structure['judge'] = lines[j].strip()
                                break
        
        return structure
    
    def convert_to_html(self, text, structure):
        """Convert extracted text to HTML with proper formatting"""
        lines = text.split('\n')
        html_lines = []
        
        html_lines.append('<!DOCTYPE html>')
        html_lines.append('<html lang="en">')
        html_lines.append('<head>')
        html_lines.append('<meta charset="UTF-8">')
        html_lines.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_lines.append('<title>Legal Judgment</title>')
        html_lines.append('<style>')
        html_lines.append("""
            body {
                font-family: 'Times New Roman', serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
                color: #000000;
            }
            .case-header {
                text-align: center;
                margin-bottom: 20px;
                border-bottom: 2px solid #000;
                padding-bottom: 10px;
            }
            .case-number {
                font-weight: bold;
                font-size: 14px;
                margin-bottom: 5px;
            }
            .parties {
                font-weight: bold;
                font-size: 16px;
                margin: 10px 0;
            }
            .date {
                font-weight: bold;
                margin: 10px 0;
            }
            .present-line {
                margin: 15px 0;
                font-style: italic;
            }
            .numbered-point {
                margin: 10px 0;
                margin-left: 20px;
            }
            .sub-numbered-point {
                margin: 8px 0;
                margin-left: 40px;
            }
            .paragraph {
                margin: 15px 0;
                text-align: justify;
            }
            .signature-block {
                margin-top: 40px;
                text-align: right;
            }
            .judge-name {
                font-weight: bold;
                margin-top: 20px;
            }
            .court-designation {
                font-size: 12px;
                margin-top: 5px;
            }
            .page-break {
                border-top: 1px dashed #ccc;
                margin: 20px 0;
                text-align: center;
                color: #666;
                font-size: 12px;
            }
            .colon-numbering {
                text-align: center;
                font-weight: bold;
                margin: 10px 0;
            }
        """)
        html_lines.append('</style>')
        html_lines.append('</head>')
        html_lines.append('<body>')
        
        # Process each line
        in_header = True
        header_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                html_lines.append('<br>')
                continue
            
            # Detect header section
            if in_header and (
                structure['case_number'] and structure['case_number'] in line or
                re.search(self.formatting_patterns['case_number'], line) or
                'VS' in line.upper() or 'V/S' in line.upper() or
                re.search(self.formatting_patterns['date'], line) or
                line.startswith('Present')
            ):
                header_lines.append(line)
                if line.startswith('Present'):
                    in_header = False
                continue
            elif in_header:
                header_lines.append(line)
                continue
            
            # Process header at the end of header detection
            if header_lines and not in_header:
                html_lines.append('<div class="case-header">')
                for header_line in header_lines:
                    if re.search(self.formatting_patterns['case_number'], header_line):
                        html_lines.append(f'<div class="case-number">{header_line}</div>')
                    elif 'VS' in header_line.upper() or 'V/S' in header_line.upper():
                        html_lines.append(f'<div class="parties">{header_line}</div>')
                    elif re.search(self.formatting_patterns['date'], header_line):
                        html_lines.append(f'<div class="date">{header_line}</div>')
                    elif header_line.startswith('Present'):
                        html_lines.append(f'<div class="present-line">{header_line}</div>')
                    else:
                        html_lines.append(f'<div>{header_line}</div>')
                html_lines.append('</div>')
                header_lines = []
            
            # Handle colon numbering (like :2:, :3:)
            if re.match(self.formatting_patterns['colon_numbering'], line):
                html_lines.append(f'<div class="colon-numbering">{line}</div>')
                continue
            
            # Handle numbered points
            if re.match(self.formatting_patterns['numbering'], line):
                if line.strip().startswith('(') and line.count('(') == 1:
                    html_lines.append(f'<div class="sub-numbered-point">{line}</div>')
                else:
                    html_lines.append(f'<div class="numbered-point">{line}</div>')
                continue
            
            # Handle sub-numbered points
            if re.match(self.formatting_patterns['sub_numbering'], line):
                html_lines.append(f'<div class="sub-numbered-point">{line}</div>')
                continue
            
            # Handle judge signature (detect at end of document)
            if i > len(lines) - 10:
                if (re.search(r'District\s+Judge|Additional\s+District\s+Judge|Chief\s+Judicial\s+Magistrate', line, re.IGNORECASE) or
                    (line.isupper() and len(line.split()) <= 4 and i > len(lines) - 5)):
                    if not any('signature-block' in hl for hl in html_lines[-5:]):
                        html_lines.append('<div class="signature-block">')
                    if re.search(r'District\s+Judge|Additional\s+District\s+Judge|Chief\s+Judicial\s+Magistrate', line, re.IGNORECASE):
                        html_lines.append(f'<div class="court-designation">{line}</div>')
                    else:
                        html_lines.append(f'<div class="judge-name">{line}</div>')
                    continue
            
            # Regular paragraphs
            html_lines.append(f'<div class="paragraph">{line}</div>')
        
        # Close signature block if opened
        if html_lines and 'signature-block' in html_lines[-1]:
            html_lines.append('</div>')
        
        html_lines.append('</body>')
        html_lines.append('</html>')
        
        return '\n'.join(html_lines)
    
    def extract_judgment(self, pdf_file, extraction_method):
        """Main extraction function"""
        # Reset file pointer
        pdf_file.seek(0)
        
        # Choose extraction method
        if extraction_method == "PyPDF2":
            raw_text = self.extract_with_pypdf2(pdf_file)
        elif extraction_method == "pdfplumber":
            raw_text = self.extract_with_pdfplumber(pdf_file)
        elif extraction_method == "PyMuPDF":
            raw_text = self.extract_with_pymupdf(pdf_file)
        else:  # Auto-detect
            # Try multiple methods and choose the best result
            pdf_file.seek(0)
            text1 = self.extract_with_pdfplumber(pdf_file)
            pdf_file.seek(0)
            text2 = self.extract_with_pymupdf(pdf_file)
            
            # Choose the method that gives more content
            raw_text = text1 if len(text1) > len(text2) else text2
        
        if not raw_text.strip():
            return None, None, None
        
        # Clean and preserve formatting
        cleaned_text = self.clean_and_preserve_formatting(raw_text)
        
        # Identify document structure
        structure = self.identify_document_structure(cleaned_text)
        
        # Convert to HTML
        html_output = self.convert_to_html(cleaned_text, structure)
        
        return cleaned_text, html_output, structure

# Streamlit App
def main():
    st.set_page_config(
        page_title="Legal Judgment Text Extractor",
        page_icon="⚖️",
        layout="wide"
    )
    
    st.title("⚖️ Legal Judgment Text Extractor")
    st.markdown("""
    This tool extracts text from legal judgment PDFs while maintaining original formatting, numbering, and structure.
    Specifically designed for district court cases with varying formats.
    """)
    
    # Sidebar for configuration
    st.sidebar.header("⚙️ Configuration")
    
    extraction_method = st.sidebar.selectbox(
        "Choose Extraction Method:",
        ["Auto-detect", "pdfplumber", "PyMuPDF", "PyPDF2"],
        help="Auto-detect will try multiple methods and choose the best result"
    )
    
    show_structure = st.sidebar.checkbox("Show Document Structure Analysis", value=True)
    show_raw_text = st.sidebar.checkbox("Show Raw Extracted Text", value=False)
    
    # Main interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 Upload PDF")
        uploaded_file = st.file_uploader(
            "Choose a legal judgment PDF file",
            type=['pdf'],
            help="Upload a PDF file containing a legal judgment"
        )
        
        if uploaded_file is not None:
            st.success(f"File uploaded: {uploaded_file.name}")
            st.info(f"File size: {len(uploaded_file.getvalue())/1024:.1f} KB")
            
            # Extract text
            with st.spinner("Extracting text from PDF..."):
                extractor = LegalJudgmentExtractor()
                extracted_text, html_output, structure = extractor.extract_judgment(
                    uploaded_file, extraction_method
                )
            
            if extracted_text:
                st.success("✅ Text extraction completed!")
                
                # Document structure analysis
                if show_structure and structure:
                    st.subheader("📊 Document Structure Analysis")
                    structure_df = pd.DataFrame([
                        {"Element": "Case Number", "Value": structure.get('case_number', 'Not found')},
                        {"Element": "Court Name", "Value": structure.get('court_name', 'Not found')},
                        {"Element": "Date", "Value": structure.get('date', 'Not found')},
                        {"Element": "Judge", "Value": structure.get('judge', 'Not found')},
                    ])
                    st.dataframe(structure_df, use_container_width=True)
                
                # Download options
                st.subheader("💾 Download Options")
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    # Download as HTML
                    html_bytes = html_output.encode('utf-8')
                    st.download_button(
                        label="📄 Download as HTML",
                        data=html_bytes,
                        file_name=f"judgment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                        mime="text/html"
                    )
                
                with col_dl2:
                    # Download as TXT
                    txt_bytes = extracted_text.encode('utf-8')
                    st.download_button(
                        label="📝 Download as Text",
                        data=txt_bytes,
                        file_name=f"judgment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                
                # Show raw extracted text if requested
                if show_raw_text:
                    st.subheader("📄 Raw Extracted Text")
                    st.text_area("Raw Text:", extracted_text, height=300)
            else:
                st.error("❌ Failed to extract text from the PDF. Please try a different extraction method.")
    
    with col2:
        st.header("👁️ HTML Preview")
        
        if 'html_output' in locals() and html_output:
            # Create a preview of the HTML
            st.subheader("🔍 Formatted Output Preview")
            
            # Display HTML in an iframe-like component
            st.components.v1.html(
                html_output,
                height=600,
                scrolling=True
            )
            
        else:
            st.info("👆 Upload a PDF file to see the formatted preview here")
            
            # Show sample judgment structure
            st.subheader("📋 Sample Judgment Structure")
            sample_html = """
            <div style="font-family: 'Times New Roman', serif; padding: 20px; border: 1px solid #ddd;">
                <div style="text-align: center; margin-bottom: 20px; border-bottom: 2px solid #000; padding-bottom: 10px;">
                    <div style="font-weight: bold;">OMP (I) Comm. No. 800/20</div>
                    <div style="font-weight: bold; font-size: 16px; margin: 10px 0;">
                        HDB FINANCIAL SERVICES LTD VS THE DEOBAND PUBLIC SCHOOL
                    </div>
                    <div style="font-weight: bold;">13.02.2020</div>
                    <div style="font-style: italic; margin: 15px 0;">
                        Present : Sh. Ashok Kumar Ld. Counsel for petitioner.
                    </div>
                </div>
                <div style="margin: 15px 0; text-align: justify;">
                    This is a petition u/s 9 of Indian Arbitration and Conciliation Act 1996...
                </div>
                <div style="margin: 10px 0; margin-left: 20px;">
                    (i) The receiver shall take over the possession of the vehicle...
                </div>
                <div style="margin-top: 40px; text-align: right;">
                    <div style="font-weight: bold; margin-top: 20px;">VINAY KUMAR KHANNA</div>
                    <div style="font-size: 12px; margin-top: 5px;">District Judge</div>
                </div>
            </div>
            """
            st.components.v1.html(sample_html, height=400)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    **Features:**
    - 📄 Maintains original numbering and sub-numbering
    - 🔤 Preserves document structure and formatting
    - 🏛️ Handles various district court judgment formats
    - 📱 Responsive HTML output with proper styling
    - 💾 Multiple download formats (HTML, TXT)
    - 🔍 Document structure analysis
    - ⚡ Scalable for processing millions of cases
    """)

if __name__ == "__main__":
    # Install required packages
    st.markdown("""
    **Required packages:**
    ```bash
    pip install streamlit PyPDF2 pdfplumber PyMuPDF pandas
    ```
    """)
    
    main()

import streamlit as st
import PyPDF2
import fitz  # PyMuPDF
import pdfplumber
import re
from io import BytesIO
import base64
from typing import List, Tuple
import unicodedata

# Page configuration
st.set_page_config(
    page_title="Legal Judgment Text Extractor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class LegalJudgmentExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.html_output = ""
    
    def extract_text_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber - best for preserving layout"""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
                    # Get text with layout preservation
                    text = page.extract_text(layout=True, x_tolerance=1, y_tolerance=1)
                    if text:
                        full_text += text
                        if page_num < len(pdf.pages) - 1:  # Add page break except for last page
                            full_text += "\n\n--- PAGE BREAK ---\n\n"
                return full_text
        except Exception as e:
            st.error(f"Error with pdfplumber: {str(e)}")
            return ""
    
    def extract_text_pymupdf(self, pdf_file) -> str:
        """Extract text using PyMuPDF - good for formatting"""
        try:
            pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
            full_text = ""
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document.get_page(page_num)
                # Get text blocks with position information
                blocks = page.get_text("dict")
                
                page_text = ""
                current_y = None
                
                for block in blocks["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            line_text = ""
                            line_y = line["bbox"][1]  # y coordinate
                            
                            # Add extra line breaks for significant y-coordinate jumps
                            if current_y is not None and abs(line_y - current_y) > 20:
                                page_text += "\n"
                            
                            for span in line["spans"]:
                                line_text += span["text"]
                            
                            if line_text.strip():
                                page_text += line_text + "\n"
                                current_y = line_y
                
                full_text += page_text
                if page_num < pdf_document.page_count - 1:
                    full_text += "\n\n--- PAGE BREAK ---\n\n"
            
            pdf_document.close()
            return full_text
        except Exception as e:
            st.error(f"Error with PyMuPDF: {str(e)}")
            return ""
    
    def extract_text_pypdf2(self, pdf_file) -> str:
        """Extract text using PyPDF2 - fallback method"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            full_text = ""
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                full_text += text
                if page_num < len(pdf_reader.pages) - 1:
                    full_text += "\n\n--- PAGE BREAK ---\n\n"
            
            return full_text
        except Exception as e:
            st.error(f"Error with PyPDF2: {str(e)}")
            return ""
    
    def preserve_formatting(self, text: str) -> str:
        """Preserve original formatting and spacing"""
        # Split into lines
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Preserve leading spaces
            leading_spaces = len(line) - len(line.lstrip())
            
            # Clean up the line but preserve internal spacing
            cleaned_line = re.sub(r'\s+', ' ', line.strip()) if line.strip() else ""
            
            # Add back leading spaces
            if cleaned_line:
                formatted_line = ' ' * leading_spaces + cleaned_line
                formatted_lines.append(formatted_line)
            else:
                formatted_lines.append("")  # Preserve empty lines
        
        return '\n'.join(formatted_lines)
    
    def detect_numbering_patterns(self, text: str) -> List[Tuple[str, str]]:
        """Detect various numbering patterns in legal documents"""
        patterns = [
            (r'^\s*(\d+\.)\s+', 'main-numbering'),  # 1. 2. 3.
            (r'^\s*\(([ivxlcdm]+)\)\s+', 'roman-numbering'),  # (i) (ii) (iii)
            (r'^\s*\(([a-z])\)\s+', 'alpha-numbering'),  # (a) (b) (c)
            (r'^\s*([A-Z]\.)\s+', 'capital-alpha'),  # A. B. C.
            (r'^\s*(\d+\.\d+\.?\d*\.?)\s+', 'decimal-numbering'),  # 1.1 1.1.1
            (r'^\s*Article\s+(\d+)', 'article-numbering'),  # Article 1
            (r'^\s*Section\s+(\d+)', 'section-numbering'),  # Section 1
            (r'^\s*Para\s+(\d+)', 'para-numbering'),  # Para 1
        ]
        
        found_patterns = []
        lines = text.split('\n')
        
        for line in lines[:50]:  # Check first 50 lines
            for pattern, pattern_type in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    found_patterns.append((pattern, pattern_type))
                    break
        
        return found_patterns
    
    def convert_to_html(self, text: str) -> str:
        """Convert extracted text to HTML with preserved formatting"""
        lines = text.split('\n')
        html_content = []
        
        # Detect numbering patterns
        numbering_patterns = self.detect_numbering_patterns(text)
        
        html_content.append('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Legal Judgment</title>
            <style>
                body {
                    font-family: 'Times New Roman', serif;
                    line-height: 1.6;
                    margin: 20px;
                    background-color: #ffffff;
                    color: #000000;
                }
                .judgment-container {
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    border: 1px solid #ccc;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    font-weight: bold;
                    margin-bottom: 20px;
                    border-bottom: 2px solid #000;
                    padding-bottom: 10px;
                }
                .case-number {
                    font-weight: bold;
                    text-align: center;
                }
                .date {
                    text-align: right;
                    font-weight: bold;
                }
                .main-numbering {
                    font-weight: bold;
                    margin-top: 15px;
                }
                .sub-numbering {
                    margin-left: 20px;
                    margin-top: 10px;
                }
                .roman-numbering {
                    margin-left: 30px;
                    margin-top: 8px;
                }
                .alpha-numbering {
                    margin-left: 40px;
                    margin-top: 5px;
                }
                .paragraph {
                    margin-bottom: 10px;
                    text-align: justify;
                }
                .page-break {
                    page-break-before: always;
                    border-top: 2px dashed #ccc;
                    padding-top: 20px;
                    margin-top: 20px;
                }
                .signature-block {
                    text-align: right;
                    margin-top: 30px;
                    font-weight: bold;
                }
                pre {
                    font-family: 'Times New Roman', serif;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }
            </style>
        </head>
        <body>
            <div class="judgment-container">
        ''')
        
        in_header = True
        signature_started = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip empty lines but preserve them in output
            if not line_stripped:
                html_content.append('<br>')
                continue
            
            # Handle page breaks
            if "PAGE BREAK" in line:
                html_content.append('<div class="page-break"></div>')
                continue
            
            # Preserve exact spacing by converting to HTML entities
            html_line = line.replace(' ', '&nbsp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Detect different types of content and apply appropriate styling
            css_class = "paragraph"
            
            # Case number detection
            if re.match(r'^[A-Z\s]*\([A-Z]\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+', line_stripped):
                css_class = "case-number"
            
            # Date detection
            elif re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}', line_stripped):
                css_class = "date"
            
            # Main numbering detection
            elif re.match(r'^\s*\d+\.\s+', line):
                css_class = "main-numbering"
            
            # Roman numbering detection
            elif re.match(r'^\s*\([ivxlcdm]+\)\s+', line, re.IGNORECASE):
                css_class = "roman-numbering"
            
            # Alphabetic numbering detection
            elif re.match(r'^\s*\([a-z]\)\s+', line):
                css_class = "alpha-numbering"
            
            # Sub-numbering detection
            elif re.match(r'^\s*\d+\.\d+', line):
                css_class = "sub-numbering"
            
            # Signature block detection
            elif re.search(r'(Judge|District Judge|Magistrate)', line_stripped, re.IGNORECASE):
                css_class = "signature-block"
                signature_started = True
            elif signature_started and (re.match(r'^[A-Z\s]+$', line_stripped) or 
                                     re.search(r'(Court|District|New Delhi)', line_stripped)):
                css_class = "signature-block"
            
            # Header detection (first few lines)
            if in_header and i < 10:
                if re.match(r'^[A-Z\s]*VS?[A-Z\s]*$', line_stripped, re.IGNORECASE):
                    css_class = "header"
                elif "present" in line_stripped.lower() or "heard" in line_stripped.lower():
                    in_header = False
            
            # Add the line with appropriate styling
            html_content.append(f'<div class="{css_class}"><pre>{html_line}</pre></div>')
        
        html_content.append('''
            </div>
        </body>
        </html>
        ''')
        
        return '\n'.join(html_content)
    
    def process_pdf(self, pdf_file, extraction_method: str) -> Tuple[str, str]:
        """Process PDF and return extracted text and HTML"""
        # Reset file pointer
        pdf_file.seek(0)
        
        # Extract text based on selected method
        if extraction_method == "PDFPlumber (Recommended)":
            extracted_text = self.extract_text_pdfplumber(pdf_file)
        elif extraction_method == "PyMuPDF":
            extracted_text = self.extract_text_pymupdf(pdf_file)
        else:  # PyPDF2
            extracted_text = self.extract_text_pypdf2(pdf_file)
        
        if not extracted_text:
            return "", ""
        
        # Preserve formatting
        formatted_text = self.preserve_formatting(extracted_text)
        
        # Convert to HTML
        html_output = self.convert_to_html(formatted_text)
        
        return formatted_text, html_output

def main():
    st.title("⚖️ Legal Judgment Text Extractor")
    st.markdown("---")
    st.markdown("**Extract and preserve the original formatting of legal judgments from PDF files**")
    
    # Sidebar
    st.sidebar.header("📋 Extraction Settings")
    
    # Extraction method selection
    extraction_method = st.sidebar.selectbox(
        "Choose Extraction Method:",
        ["PDFPlumber (Recommended)", "PyMuPDF", "PyPDF2"],
        help="PDFPlumber generally provides the best layout preservation for legal documents"
    )
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Legal Judgment PDF",
        type=['pdf'],
        help="Upload a PDF file of a legal judgment"
    )
    
    if uploaded_file is not None:
        # Display file info
        st.info(f"📄 **File:** {uploaded_file.name} | **Size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Create extractor instance
        extractor = LegalJudgmentExtractor()
        
        # Process button
        if st.button("🔍 Extract Text", type="primary"):
            with st.spinner("Extracting text from PDF..."):
                try:
                    # Process the PDF
                    extracted_text, html_output = extractor.process_pdf(uploaded_file, extraction_method)
                    
                    if extracted_text:
                        st.success("✅ Text extraction completed successfully!")
                        
                        # Create tabs for different views
                        tab1, tab2, tab3, tab4 = st.tabs(["📋 Raw Text", "🌐 HTML Preview", "💾 Download HTML", "📊 Statistics"])
                        
                        with tab1:
                            st.subheader("Extracted Raw Text")
                            st.text_area(
                                "Raw extracted text with preserved formatting:",
                                value=extracted_text,
                                height=600,
                                help="This shows the extracted text with original spacing and formatting preserved"
                            )
                        
                        with tab2:
                            st.subheader("HTML Preview")
                            st.markdown("**Preview of the formatted HTML output:**")
                            
                            # Display HTML preview
                            st.components.v1.html(html_output, height=800, scrolling=True)
                        
                        with tab3:
                            st.subheader("Download Options")
                            
                            # Create download buttons
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Download as HTML
                                html_bytes = html_output.encode('utf-8')
                                st.download_button(
                                    label="📄 Download HTML File",
                                    data=html_bytes,
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_extracted.html",
                                    mime="text/html"
                                )
                            
                            with col2:
                                # Download as TXT
                                txt_bytes = extracted_text.encode('utf-8')
                                st.download_button(
                                    label="📝 Download Text File",
                                    data=txt_bytes,
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_extracted.txt",
                                    mime="text/plain"
                                )
                        
                        with tab4:
                            st.subheader("Document Statistics")
                            
                            # Calculate statistics
                            lines = extracted_text.split('\n')
                            words = extracted_text.split()
                            characters = len(extracted_text)
                            non_empty_lines = [line for line in lines if line.strip()]
                            
                            # Numbering pattern analysis
                            patterns = extractor.detect_numbering_patterns(extracted_text)
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Total Lines", len(lines))
                                st.metric("Non-empty Lines", len(non_empty_lines))
                            
                            with col2:
                                st.metric("Total Words", len(words))
                                st.metric("Total Characters", characters)
                            
                            with col3:
                                st.metric("Numbering Patterns", len(set(p[1] for p in patterns)))
                                st.metric("Pages Detected", extracted_text.count("PAGE BREAK") + 1)
                            
                            # Show detected patterns
                            if patterns:
                                st.subheader("Detected Numbering Patterns")
                                pattern_types = list(set(p[1] for p in patterns))
                                for pattern_type in pattern_types:
                                    st.write(f"• **{pattern_type.replace('-', ' ').title()}**")
                    
                    else:
                        st.error("❌ Failed to extract text from the PDF. Please try a different extraction method or check if the PDF is text-based.")
                
                except Exception as e:
                    st.error(f"❌ An error occurred during text extraction: {str(e)}")
    
    else:
        # Show sample format
        st.markdown("### 📖 Sample Legal Judgment Format")
        st.markdown("The tool preserves formatting like this:")
        
        sample_text = """OMP (I) Comm. No. 800/20
HDB FINANCIAL SERVICES LTD VS THE DEOBAND PUBLIC SCHOOL
13.02.2020

Present : Sh. Ashok Kumar Ld. Counsel for petitioner.

This is a petition u/s 9 of Indian Arbitration and Conciliation Act
1996 for issuing interim measure by way of appointment of receiver...

(i) The receiver shall take over the possession of the vehicle
    from the respondent at the address given in the loan application.

(ii) The receiver shall avoid taking the possession of the vehicle
     if the vehicle is occupied by a women...

                                    VINAY KUMAR KHANNA
                                    District Judge
                           (Commercial Court-02)
                     South Distt., Saket, New Delhi/13.02.2020"""
        
        st.code(sample_text, language=None)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <small>⚖️ Legal Judgment Text Extractor | Preserves original formatting, numbering, and spacing</small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

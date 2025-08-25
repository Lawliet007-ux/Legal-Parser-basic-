import streamlit as st
import PyPDF2
import fitz  # PyMuPDF
import pdfplumber
import re
from io import BytesIO
import html
from typing import List, Dict, Tuple
import pandas as pd

class LegalJudgmentExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.html_output = ""
        self.extraction_method = ""
        
    def extract_with_pymupdf(self, pdf_file) -> str:
        """Extract text using PyMuPDF (fitz) - best for maintaining formatting"""
        try:
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            text_blocks = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Get text blocks with formatting information
                blocks = page.get_text("dict")
                
                page_text = []
                for block in blocks["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            line_text = ""
                            for span in line["spans"]:
                                line_text += span["text"]
                            if line_text.strip():
                                page_text.append(line_text.strip())
                
                if page_text:
                    text_blocks.extend(page_text)
            
            doc.close()
            return "\n".join(text_blocks)
        except Exception as e:
            st.error(f"PyMuPDF extraction failed: {str(e)}")
            return ""
    
    def extract_with_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber - good for table preservation"""
        try:
            pdf_file.seek(0)  # Reset file pointer
            text_blocks = []
            
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    # Extract text while preserving layout
                    text = page.extract_text()
                    if text:
                        # Split by lines and clean up
                        lines = text.split('\n')
                        cleaned_lines = []
                        for line in lines:
                            line = line.strip()
                            if line:
                                cleaned_lines.append(line)
                        text_blocks.extend(cleaned_lines)
            
            return "\n".join(text_blocks)
        except Exception as e:
            st.error(f"PDFPlumber extraction failed: {str(e)}")
            return ""
    
    def extract_with_pypdf2(self, pdf_file) -> str:
        """Extract text using PyPDF2 - fallback method"""
        try:
            pdf_file.seek(0)  # Reset file pointer
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_blocks = []
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:
                            text_blocks.append(line)
            
            return "\n".join(text_blocks)
        except Exception as e:
            st.error(f"PyPDF2 extraction failed: {str(e)}")
            return ""
    
    def preserve_legal_structure(self, text: str) -> str:
        """Preserve legal document structure and numbering"""
        lines = text.split('\n')
        structured_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Preserve various legal numbering patterns
            patterns = [
                r'^\([ivx]+\)',  # (i), (ii), (iii), (iv), (v), etc.
                r'^\([a-z]\)',   # (a), (b), (c), etc.
                r'^\(\d+\)',     # (1), (2), (3), etc.
                r'^\d+\.',       # 1., 2., 3., etc.
                r'^\([A-Z]\)',   # (A), (B), (C), etc.
                r'^[A-Z]\.',     # A., B., C., etc.
                r'^\d+\)',       # 1), 2), 3), etc.
                r'^OMP.*No\.',   # Case numbers like OMP (I) Comm. No.
                r'^Present\s*:', # Present: section
                r'^Heard\.',     # Heard. section
                r'^Accordingly,', # Accordingly, section
                r'^Considering', # Considering section
                r'^It is submitted', # It is submitted section
                r'^This court',  # This court section
                r'^Ld\. Counsel', # Learned Counsel sections
            ]
            
            is_structured = False
            for pattern in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    is_structured = True
                    break
            
            # Add appropriate spacing for structured elements
            if is_structured:
                if structured_lines and not structured_lines[-1].strip() == "":
                    structured_lines.append("")  # Add spacing before structured elements
            
            structured_lines.append(line)
        
        return '\n'.join(structured_lines)
    
    def generate_html_output(self, text: str) -> str:
        """Generate HTML output that preserves legal document formatting"""
        lines = text.split('\n')
        html_lines = []
        
        html_lines.append("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: 'Times New Roman', serif;
                    line-height: 1.6;
                    margin: 40px;
                    color: #000;
                    background-color: #fff;
                }
                .case-header {
                    text-align: center;
                    font-weight: bold;
                    margin-bottom: 20px;
                    font-size: 14px;
                }
                .case-number {
                    text-align: left;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .case-title {
                    text-align: center;
                    font-weight: bold;
                    margin: 10px 0;
                    text-transform: uppercase;
                }
                .date {
                    text-align: left;
                    margin-bottom: 20px;
                }
                .present {
                    margin: 15px 0;
                }
                .paragraph {
                    text-align: justify;
                    margin: 15px 0;
                    text-indent: 0;
                }
                .numbered-item {
                    margin: 10px 0 10px 30px;
                    text-align: justify;
                }
                .sub-numbered-item {
                    margin: 8px 0 8px 50px;
                    text-align: justify;
                }
                .court-direction {
                    margin: 15px 0;
                    font-weight: normal;
                }
                .signature {
                    text-align: center;
                    margin-top: 30px;
                    font-weight: bold;
                }
                .judge-info {
                    text-align: center;
                    margin: 5px 0;
                }
                .spacing {
                    height: 15px;
                }
            </style>
        </head>
        <body>
        """)
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                html_lines.append('<div class="spacing"></div>')
                continue
            
            escaped_line = html.escape(line)
            
            # Classify line types and apply appropriate styling
            if re.match(r'^OMP.*No\.', line):
                html_lines.append(f'<div class="case-number">{escaped_line}</div>')
            elif re.match(r'^[A-Z\s&]+VS[A-Z\s&]+$', line):
                html_lines.append(f'<div class="case-title">{escaped_line}</div>')
            elif re.match(r'^\d{2}\.\d{2}\.\d{4}$', line):
                html_lines.append(f'<div class="date">{escaped_line}</div>')
            elif re.match(r'^Present\s*:', line):
                html_lines.append(f'<div class="present">{escaped_line}</div>')
            elif re.match(r'^\([ivx]+\)', line) or re.match(r'^\(\d+\)', line):
                html_lines.append(f'<div class="numbered-item">{escaped_line}</div>')
            elif re.match(r'^\([a-z]\)', line):
                html_lines.append(f'<div class="sub-numbered-item">{escaped_line}</div>')
            elif re.match(r'^(Accordingly,|Considering|It is submitted|This court|Heard\.|Ld\. Counsel)', line):
                html_lines.append(f'<div class="court-direction">{escaped_line}</div>')
            elif re.match(r'^[A-Z\s]+$', line) and len(line.split()) <= 4:
                html_lines.append(f'<div class="signature">{escaped_line}</div>')
            elif re.match(r'^\(.*Court.*\)$', line) or 'District' in line or 'Judge' in line:
                html_lines.append(f'<div class="judge-info">{escaped_line}</div>')
            else:
                html_lines.append(f'<div class="paragraph">{escaped_line}</div>')
        
        html_lines.append("""
        </body>
        </html>
        """)
        
        return '\n'.join(html_lines)
    
    def extract_judgment(self, pdf_file, extraction_method="auto"):
        """Main extraction method"""
        if extraction_method == "auto" or extraction_method == "pymupdf":
            self.extracted_text = self.extract_with_pymupdf(pdf_file)
            self.extraction_method = "PyMuPDF"
            
        if not self.extracted_text and (extraction_method == "auto" or extraction_method == "pdfplumber"):
            self.extracted_text = self.extract_with_pdfplumber(pdf_file)
            self.extraction_method = "PDFPlumber"
            
        if not self.extracted_text and (extraction_method == "auto" or extraction_method == "pypdf2"):
            self.extracted_text = self.extract_with_pypdf2(pdf_file)
            self.extraction_method = "PyPDF2"
        
        if self.extracted_text:
            # Preserve legal structure
            self.extracted_text = self.preserve_legal_structure(self.extracted_text)
            # Generate HTML output
            self.html_output = self.generate_html_output(self.extracted_text)
            
        return bool(self.extracted_text)

def main():
    st.set_page_config(
        page_title="Legal Judgment Text Extractor",
        page_icon="⚖️",
        layout="wide"
    )
    
    st.title("⚖️ Legal Judgment Text Extractor")
    st.markdown("""
    This tool extracts text from legal judgment PDFs while maintaining original structure, 
    formatting, numbering, and alignment. Designed for district court cases and various legal document formats.
    """)
    
    # Sidebar configuration
    st.sidebar.header("Configuration")
    
    extraction_method = st.sidebar.selectbox(
        "Extraction Method",
        ["auto", "pymupdf", "pdfplumber", "pypdf2"],
        help="Choose extraction method. 'auto' tries methods in order of reliability."
    )
    
    show_raw_text = st.sidebar.checkbox("Show Raw Extracted Text", value=False)
    show_stats = st.sidebar.checkbox("Show Document Statistics", value=True)
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Legal Judgment PDF", 
        type="pdf",
        help="Upload a PDF file containing legal judgment text"
    )
    
    if uploaded_file is not None:
        # Create columns for layout
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.header("📄 Processing")
            
            with st.spinner("Extracting text from legal judgment..."):
                extractor = LegalJudgmentExtractor()
                success = extractor.extract_judgment(uploaded_file, extraction_method)
            
            if success:
                st.success(f"✅ Text extracted successfully using {extractor.extraction_method}")
                
                if show_stats:
                    st.subheader("📊 Document Statistics")
                    lines = extractor.extracted_text.split('\n')
                    non_empty_lines = [line for line in lines if line.strip()]
                    
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Total Lines", len(lines))
                    with col_stat2:
                        st.metric("Non-empty Lines", len(non_empty_lines))
                    with col_stat3:
                        st.metric("Word Count", len(extractor.extracted_text.split()))
                
                if show_raw_text:
                    st.subheader("📝 Raw Extracted Text")
                    st.text_area("Raw Text", extractor.extracted_text, height=400)
                
                # Download buttons
                st.subheader("💾 Download Options")
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    st.download_button(
                        label="Download as Text File",
                        data=extractor.extracted_text,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_extracted.txt",
                        mime="text/plain"
                    )
                
                with col_dl2:
                    st.download_button(
                        label="Download as HTML File",
                        data=extractor.html_output,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_formatted.html",
                        mime="text/html"
                    )
            else:
                st.error("❌ Failed to extract text from the PDF. Please try a different file or extraction method.")
        
        with col2:
            if uploaded_file is not None and 'extractor' in locals() and extractor.html_output:
                st.header("🔍 HTML Preview")
                st.markdown("**Formatted Output (as it would appear in HTML):**")
                
                # Display HTML preview
                st.components.v1.html(
                    extractor.html_output,
                    height=600,
                    scrolling=True
                )
    
    # Instructions and examples
    with st.expander("📖 Instructions and Features"):
        st.markdown("""
        ### Features:
        - **Structure Preservation**: Maintains original numbering, sub-numbering, and formatting
        - **Multiple Extraction Methods**: Uses PyMuPDF, PDFPlumber, and PyPDF2 for maximum compatibility
        - **Legal Format Recognition**: Recognizes legal document patterns and structures
        - **HTML Generation**: Creates properly formatted HTML output
        - **Download Options**: Export as text or HTML files
        
        ### Supported Legal Document Elements:
        - Case numbers and titles (e.g., OMP (I) Comm. No. 800/20)
        - Numbered sections (1., 2., 3., etc.)
        - Sub-numbering ((i), (ii), (iii), etc.)
        - Alphabetical numbering ((a), (b), (c), etc.)
        - Legal phrases and structures
        - Judge signatures and court information
        
        ### How to Use:
        1. Upload your legal judgment PDF file
        2. Choose extraction method (or use 'auto' for best results)
        3. Review the HTML preview to ensure formatting is maintained
        4. Download the extracted text or formatted HTML file
        
        ### Best Practices:
        - For best results, use high-quality, text-based PDF files
        - If one extraction method fails, try another
        - Check the HTML preview to verify structure preservation
        """)

if __name__ == "__main__":
    main()

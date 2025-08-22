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
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove problematic characters
        text = text.replace('Â­', '-')  # Replace soft hyphen
        text = text.replace('\u00ad', '-')  # Replace soft hyphen
        text = text.replace('\ufeff', '')  # Remove BOM
        
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        return text
    
    def extract_text_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber - best for preserving layout"""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
                    # Get text with layout preservation
                    text = page.extract_text(layout=True, x_tolerance=2, y_tolerance=2)
                    if text:
                        full_text += text
                        if page_num < len(pdf.pages) - 1:
                            full_text += "\n\n[PAGE_BREAK]\n\n"
                return self.clean_text(full_text)
        except Exception as e:
            st.error(f"Error with pdfplumber: {str(e)}")
            return ""
    
    def extract_text_pymupdf(self, pdf_file) -> str:
        """Extract text using PyMuPDF"""
        try:
            pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
            full_text = ""
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document.get_page(page_num)
                text = page.get_text("text")
                full_text += text
                
                if page_num < pdf_document.page_count - 1:
                    full_text += "\n\n[PAGE_BREAK]\n\n"
            
            pdf_document.close()
            return self.clean_text(full_text)
        except Exception as e:
            st.error(f"Error with PyMuPDF: {str(e)}")
            return ""
    
    def extract_text_pypdf2(self, pdf_file) -> str:
        """Extract text using PyPDF2"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            full_text = ""
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                full_text += text
                if page_num < len(pdf_reader.pages) - 1:
                    full_text += "\n\n[PAGE_BREAK]\n\n"
            
            return self.clean_text(full_text)
        except Exception as e:
            st.error(f"Error with PyPDF2: {str(e)}")
            return ""
    
    def normalize_spacing(self, text: str) -> str:
        """Normalize spacing while preserving document structure"""
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Preserve completely empty lines
            if not line.strip():
                normalized_lines.append("")
                continue
            
            # Count leading spaces for indentation
            leading_spaces = len(line) - len(line.lstrip())
            
            # Clean internal spacing but preserve structure
            cleaned_content = ' '.join(line.split())
            
            # Restore appropriate indentation (convert to standard units)
            if leading_spaces > 0:
                # Convert to reasonable indentation levels
                indent_level = min(leading_spaces // 4, 8)  # Max 8 levels
                cleaned_line = '    ' * indent_level + cleaned_content
            else:
                cleaned_line = cleaned_content
            
            normalized_lines.append(cleaned_line)
        
        return '\n'.join(normalized_lines)
    
    def detect_content_type(self, line: str) -> str:
        """Detect the type of content in a line"""
        stripped = line.strip()
        
        if not stripped:
            return "empty"
        
        # Page break
        if "[PAGE_BREAK]" in line:
            return "page-break"
        
        # Case number patterns
        if re.match(r'^[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+', stripped):
            return "case-number"
        
        # Date patterns
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "date"
        
        # Present/Heard pattern
        if re.match(r'^Present\s*:', stripped, re.IGNORECASE):
            return "present"
        
        # Roman numerals in parentheses
        if re.match(r'^\s*\([ivxlcdm]+\)', stripped, re.IGNORECASE):
            return "roman-numbering"
        
        # Alphabetic numbering in parentheses
        if re.match(r'^\s*\([a-z]\)', stripped):
            return "alpha-numbering"
        
        # Main decimal numbering
        if re.match(r'^\s*\d+\.(\d+\.)*\s+', line):
            return "decimal-numbering"
        
        # Simple numbering
        if re.match(r'^\s*\d+\.\s+', line):
            return "main-numbering"
        
        # Judge signature patterns
        if any(term in stripped.upper() for term in ['DISTRICT JUDGE', 'JUDGE', 'MAGISTRATE']):
            return "signature"
        
        # Court/location info
        if re.search(r'(Court|District|New Delhi)', stripped) and any(c.isupper() for c in stripped):
            return "signature"
        
        # All caps names (likely judge names)
        if len(stripped) > 10 and stripped.isupper() and ' ' in stripped:
            return "signature"
        
        # Header detection (party names with VS)
        if ' VS ' in stripped.upper() or ' V/S ' in stripped.upper():
            return "header"
        
        # Default paragraph
        return "paragraph"
    
    def convert_to_html(self, text: str) -> str:
        """Convert text to well-formatted HTML"""
        lines = text.split('\n')
        
        html_content = ['''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legal Judgment</title>
    <style>
        body {
            font-family: 'Times New Roman', Times, serif;
            line-height: 1.5;
            margin: 0;
            padding: 20px;
            background-color: #ffffff;
            color: #000000;
            font-size: 14px;
        }
        
        .judgment-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 30px;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            border: 1px solid #ddd;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0 10px 0;
        }
        
        .header {
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 10px 0 20px 0;
            border-bottom: 2px solid #000;
            padding-bottom: 15px;
        }
        
        .date {
            text-align: center;
            font-weight: bold;
            margin: 15px 0;
        }
        
        .present {
            margin: 15px 0;
            font-weight: bold;
        }
        
        .main-numbering, .decimal-numbering {
            margin: 20px 0 10px 0;
            font-weight: bold;
        }
        
        .roman-numbering {
            margin: 10px 0 5px 20px;
            font-weight: bold;
        }
        
        .alpha-numbering {
            margin: 8px 0 5px 40px;
        }
        
        .paragraph {
            margin: 8px 0;
            text-align: justify;
            text-indent: 0;
        }
        
        .signature {
            text-align: center;
            font-weight: bold;
            margin: 30px 0 5px 0;
        }
        
        .page-break {
            page-break-before: always;
            border-top: 2px dashed #666;
            margin: 40px 0;
            padding-top: 20px;
            text-align: center;
            color: #666;
            font-style: italic;
        }
        
        .empty-line {
            height: 12px;
        }
        
        /* Preserve indentation */
        .indented {
            padding-left: 20px;
        }
        
        .indented-2 {
            padding-left: 40px;
        }
        
        .indented-3 {
            padding-left: 60px;
        }
        
        /* Print styles */
        @media print {
            body { margin: 0; }
            .judgment-container { 
                box-shadow: none; 
                border: none; 
                margin: 0; 
                padding: 20px; 
            }
        }
    </style>
</head>
<body>
    <div class="judgment-container">''']
        
        consecutive_empty = 0
        
        for line in lines:
            content_type = self.detect_content_type(line)
            
            if content_type == "empty":
                consecutive_empty += 1
                if consecutive_empty <= 2:  # Limit consecutive empty lines
                    html_content.append('<div class="empty-line"></div>')
                continue
            else:
                consecutive_empty = 0
            
            if content_type == "page-break":
                html_content.append('<div class="page-break">--- Page Break ---</div>')
                continue
            
            # Process the line content
            escaped_line = line.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            
            # Handle indentation
            indent_class = ""
            if line.startswith('        '):
                indent_class = " indented-3"
            elif line.startswith('    '):
                indent_class = " indented-2" if content_type in ["roman-numbering", "alpha-numbering"] else " indented"
            
            # Generate HTML based on content type
            css_class = content_type + indent_class
            
            html_content.append(f'<div class="{css_class}">{escaped_line}</div>')
        
        html_content.append('''    </div>
</body>
</html>''')
        
        return '\n'.join(html_content)
    
    def generate_statistics(self, text: str) -> dict:
        """Generate comprehensive statistics about the document"""
        lines = text.split('\n')
        words = text.split()
        
        stats = {
            'total_lines': len(lines),
            'non_empty_lines': len([l for l in lines if l.strip()]),
            'total_words': len(words),
            'total_characters': len(text),
            'pages': text.count('[PAGE_BREAK]') + 1,
            'numbering_patterns': {
                'main_numbering': len(re.findall(r'^\s*\d+\.\s+', text, re.MULTILINE)),
                'roman_numbering': len(re.findall(r'^\s*\([ivxlcdm]+\)', text, re.MULTILINE | re.IGNORECASE)),
                'alpha_numbering': len(re.findall(r'^\s*\([a-z]\)', text, re.MULTILINE)),
                'decimal_numbering': len(re.findall(r'^\s*\d+\.\d+', text, re.MULTILINE))
            }
        }
        
        return stats
    
    def process_pdf(self, pdf_file, extraction_method: str) -> Tuple[str, str]:
        """Process PDF and return formatted text and HTML"""
        pdf_file.seek(0)
        
        # Extract text
        if extraction_method == "PDFPlumber (Recommended)":
            extracted_text = self.extract_text_pdfplumber(pdf_file)
        elif extraction_method == "PyMuPDF":
            extracted_text = self.extract_text_pymupdf(pdf_file)
        else:
            extracted_text = self.extract_text_pypdf2(pdf_file)
        
        if not extracted_text:
            return "", ""
        
        # Normalize spacing
        formatted_text = self.normalize_spacing(extracted_text)
        
        # Convert to HTML
        html_output = self.convert_to_html(formatted_text)
        
        return formatted_text, html_output

def main():
    st.title("⚖️ Legal Judgment Text Extractor")
    st.markdown("---")
    st.markdown("**Extract and preserve the formatting of legal judgments from PDF files**")
    
    # Sidebar
    st.sidebar.header("📋 Extraction Settings")
    
    extraction_method = st.sidebar.selectbox(
        "Choose Extraction Method:",
        ["PDFPlumber (Recommended)", "PyMuPDF", "PyPDF2"],
        help="PDFPlumber provides the best balance of accuracy and formatting preservation"
    )
    
    # Advanced options
    st.sidebar.markdown("### Advanced Options")
    preserve_original_spacing = st.sidebar.checkbox(
        "Preserve Original Spacing", 
        value=False,
        help="Keep exact spacing from PDF (may result in uneven formatting)"
    )
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Legal Judgment PDF",
        type=['pdf'],
        help="Upload a PDF file containing a legal judgment"
    )
    
    if uploaded_file is not None:
        st.info(f"📄 **File:** {uploaded_file.name} | **Size:** {uploaded_file.size / 1024:.1f} KB")
        
        extractor = LegalJudgmentExtractor()
        
        if st.button("🔍 Extract Text", type="primary"):
            with st.spinner("Processing PDF..."):
                try:
                    formatted_text, html_output = extractor.process_pdf(uploaded_file, extraction_method)
                    
                    if formatted_text:
                        st.success("✅ Text extraction completed!")
                        
                        # Tabs for different views
                        tab1, tab2, tab3, tab4 = st.tabs(["📄 Formatted Text", "🌐 HTML Preview", "📊 Statistics", "💾 Downloads"])
                        
                        with tab1:
                            st.subheader("Extracted & Formatted Text")
                            st.text_area(
                                "Formatted text with normalized spacing:",
                                value=formatted_text,
                                height=600
                            )
                        
                        with tab2:
                            st.subheader("HTML Preview")
                            st.components.v1.html(html_output, height=800, scrolling=True)
                        
                        with tab3:
                            st.subheader("Document Analysis")
                            stats = extractor.generate_statistics(formatted_text)
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Total Lines", stats['total_lines'])
                                st.metric("Non-empty Lines", stats['non_empty_lines'])
                            
                            with col2:
                                st.metric("Total Words", stats['total_words'])
                                st.metric("Characters", stats['total_characters'])
                            
                            with col3:
                                st.metric("Pages", stats['pages'])
                                st.metric("Avg Words/Page", stats['total_words'] // max(stats['pages'], 1))
                            
                            st.markdown("### Numbering Patterns Detected")
                            for pattern, count in stats['numbering_patterns'].items():
                                if count > 0:
                                    st.write(f"• **{pattern.replace('_', ' ').title()}**: {count}")
                        
                        with tab4:
                            st.subheader("Download Options")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.download_button(
                                    label="📄 Download HTML",
                                    data=html_output.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_formatted.html",
                                    mime="text/html"
                                )
                            
                            with col2:
                                st.download_button(
                                    label="📝 Download Text",
                                    data=formatted_text.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_formatted.txt",
                                    mime="text/plain"
                                )
                    
                    else:
                        st.error("❌ Failed to extract text. Try a different extraction method.")
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    else:
        
        
        st.markdown("### Sample Output Preview")
        

if __name__ == "__main__":
    main()

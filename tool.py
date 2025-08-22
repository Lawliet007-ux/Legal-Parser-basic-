import streamlit as st
import PyPDF2
import fitz  # PyMuPDF
import pdfplumber
import re
from io import BytesIO
import base64
from typing import List, Tuple, Dict
import unicodedata

# Page configuration
st.set_page_config(
    page_title="Legal Judgment Text Extractor - Enhanced",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class EnhancedLegalExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.html_output = ""
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text while preserving structure"""
        # Remove problematic characters
        text = text.replace('Â­', '-')
        text = text.replace('\u00ad', '-')
        text = text.replace('\ufeff', '')
        text = text.replace('\u200b', '')
        
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        return text
    
    def extract_with_layout_preservation(self, pdf_file) -> str:
        """Extract text while preserving original layout using pdfplumber"""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
                    # Extract text with better layout preservation
                    text = page.extract_text(
                        layout=True,
                        x_tolerance=1,
                        y_tolerance=1,
                        keep_blank_chars=True
                    )
                    if text:
                        full_text += text
                        if page_num < len(pdf.pages) - 1:
                            full_text += "\n\n[PAGE_BREAK]\n\n"
                return self.clean_text(full_text)
        except Exception as e:
            st.error(f"Error with pdfplumber: {str(e)}")
            return ""
    
    def extract_text_pymupdf(self, pdf_file) -> str:
        """Extract text using PyMuPDF with layout preservation"""
        try:
            pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
            full_text = ""
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document.get_page(page_num)
                # Use layout preservation mode
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
    
    def smart_line_joining(self, text: str) -> str:
        """Intelligently join lines that are clearly broken mid-sentence"""
        lines = text.split('\n')
        processed_lines = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Skip empty lines and page breaks
            if not current_line or '[PAGE_BREAK]' in current_line:
                processed_lines.append(lines[i])
                i += 1
                continue
            
            # Look ahead to see if next line should be joined
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Join if current line doesn't end with sentence-ending punctuation
                # and next line doesn't start with special patterns
                should_join = (
                    current_line and next_line and
                    not current_line.endswith(('.', ':', '?', '!')) and
                    not next_line[0].isupper() and
                    not re.match(r'^\([ivxlcdm]+\)', next_line.lower()) and
                    not re.match(r'^\d+\.', next_line) and
                    not next_line.startswith('Present:') and
                    not (' VS ' in next_line.upper() or ' V/S ' in next_line.upper()) and
                    not re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}', next_line)
                )
                
                if should_join:
                    # Join with single space
                    processed_lines.append(current_line + ' ' + next_line)
                    i += 2
                else:
                    processed_lines.append(lines[i])
                    i += 1
            else:
                processed_lines.append(lines[i])
                i += 1
        
        return '\n'.join(processed_lines)
    
    def detect_text_patterns(self, line: str) -> str:
        """Detect text patterns for minimal classification"""
        stripped = line.strip()
        
        if not stripped:
            return "empty"
        
        if '[PAGE_BREAK]' in stripped:
            return "page_break"
        
        # Very specific patterns only
        if re.match(r'^[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+', stripped):
            return "case_header"
        
        if (' VS ' in stripped.upper() or ' V/S ' in stripped.upper()) and len(stripped.split()) <= 15:
            return "party_names"
        
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "date"
        
        if re.match(r'^Present\s*:', stripped, re.IGNORECASE):
            return "present"
        
        if re.match(r'^:\d+:$', stripped):
            return "page_number"
        
        # Judge signature at end
        if stripped.upper() in ['DISTRICT JUDGE', 'ADDITIONAL DISTRICT JUDGE', 'CHIEF JUDICIAL MAGISTRATE']:
            return "judge_title"
        
        # Court location with date
        if re.match(r'^.*New Delhi/\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "court_location"
        
        # All caps names (likely signatures) - be very conservative
        if (stripped.isupper() and 
            len(stripped.split()) <= 4 and 
            len(stripped) >= 10 and
            stripped.replace(' ', '').isalpha()):
            return "signature"
        
        return "regular"
    
    def convert_to_clean_html(self, text: str) -> str:
        """Convert to HTML with minimal, clean formatting"""
        lines = text.split('\n')
        
        html_content = ['''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legal Judgment</title>
    <style>
        body {
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.3;
            margin: 0;
            padding: 20px;
            background-color: #ffffff;
            color: #000000;
        }
        
        .judgment-container {
            max-width: 210mm;
            margin: 0 auto;
            padding: 25mm;
            background: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        
        .line {
            margin: 0;
            padding: 0;
            min-height: 1.3em;
        }
        
        .case-header {
            text-align: center;
            font-weight: bold;
        }
        
        .party-names {
            text-align: center;
            font-weight: bold;
        }
        
        .date {
            text-align: center;
        }
        
        .present {
            margin-top: 1em;
        }
        
        .page-number {
            text-align: center;
        }
        
        .judge-title {
            text-align: right;
            font-weight: bold;
        }
        
        .signature {
            text-align: right;
        }
        
        .court-location {
            text-align: right;
        }
        
        .page-break {
            page-break-before: always;
            text-align: center;
            color: #666;
            font-style: italic;
            margin: 2em 0;
        }
        
        .empty {
            height: 1.3em;
        }
        
        @media print {
            body { 
                margin: 0; 
                padding: 0;
                background: white;
            }
            .judgment-container { 
                margin: 0; 
                padding: 20mm;
                box-shadow: none;
            }
            .page-break {
                margin: 0;
                font-size: 0;
                height: 0;
            }
        }
    </style>
</head>
<body>
    <div class="judgment-container">''']
        
        for line in lines:
            content_type = self.detect_text_patterns(line)
            
            if content_type == "empty":
                html_content.append('<div class="line empty"></div>')
            elif content_type == "page_break":
                html_content.append('<div class="page-break">--- Page Break ---</div>')
            else:
                # Escape HTML characters
                escaped_content = (line.replace('&', '&amp;')
                                 .replace('<', '&lt;')
                                 .replace('>', '&gt;')
                                 .replace('"', '&quot;'))
                
                # Apply minimal formatting based on content type
                css_class = {
                    "case_header": "line case-header",
                    "party_names": "line party-names", 
                    "date": "line date",
                    "present": "line present",
                    "page_number": "line page-number",
                    "judge_title": "line judge-title",
                    "signature": "line signature",
                    "court_location": "line court-location",
                    "regular": "line"
                }.get(content_type, "line")
                
                html_content.append(f'<div class="{css_class}">{escaped_content}</div>')
        
        html_content.append('''    </div>
</body>
</html>''')
        
        return '\n'.join(html_content)
    
    def preserve_original_spacing(self, text: str) -> str:
        """Preserve original spacing and indentation"""
        lines = text.split('\n')
        preserved_lines = []
        
        for line in lines:
            # Keep original spacing, only clean obvious artifacts
            if line.strip():
                preserved_lines.append(line.rstrip())  # Remove trailing spaces only
            else:
                preserved_lines.append('')  # Keep empty lines
        
        return '\n'.join(preserved_lines)
    
    def process_pdf_enhanced(self, pdf_file, extraction_method: str) -> Tuple[str, str]:
        """Enhanced PDF processing with better structure preservation"""
        pdf_file.seek(0)
        
        # Extract text based on method
        if extraction_method == "PDFPlumber (Layout Preserved)":
            extracted_text = self.extract_with_layout_preservation(pdf_file)
        elif extraction_method == "PyMuPDF":
            extracted_text = self.extract_text_pymupdf(pdf_file)
        else:
            extracted_text = self.extract_text_pypdf2(pdf_file)
        
        if not extracted_text:
            return "", ""
        
        # Smart line joining (minimal)
        processed_text = self.smart_line_joining(extracted_text)
        
        # Preserve original spacing
        final_text = self.preserve_original_spacing(processed_text)
        
        # Convert to HTML with clean formatting
        html_output = self.convert_to_clean_html(final_text)
        
        return final_text, html_output

def main():
    st.title("Enhanced Legal Judgment Text Extractor")
    st.markdown("---")
    st.markdown("**Preserves exact PDF structure with minimal processing**")
    
    # Sidebar
    with st.sidebar:
        st.header("Extraction Settings")
        
        extraction_method = st.selectbox(
            "Extraction Method:",
            ["PDFPlumber (Layout Preserved)", "PyMuPDF", "PyPDF2"],
            help="Choose the PDF text extraction method"
        )
        
        st.markdown("### New Approach")
        st.markdown("""
        - **Layout Preservation**: Maintains exact spacing
        - **Minimal Processing**: Only essential line joining
        - **Clean HTML**: Simple, readable formatting
        - **No Over-formatting**: Preserves original appearance
        - **Smart Detection**: Minimal pattern recognition
        """)
        
        st.markdown("### Key Improvements")
        st.markdown("""
        - Better spacing preservation
        - Reduced bold text usage
        - Proper indentation handling
        - Cleaner line breaks
        - More accurate structure
        """)
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Legal Judgment PDF",
        type=['pdf'],
        help="Select a PDF file containing a legal judgment"
    )
    
    if uploaded_file is not None:
        file_details = f"**File:** {uploaded_file.name} | **Size:** {uploaded_file.size / 1024:.1f} KB"
        st.info(file_details)
        
        extractor = EnhancedLegalExtractor()
        
        col1, col2 = st.columns([2, 1])
        with col1:
            extract_button = st.button("Extract with Enhanced Processing", type="primary", use_container_width=True)
        with col2:
            if st.button("Clear Results", use_container_width=True):
                st.rerun()
        
        if extract_button:
            with st.spinner("Processing with enhanced layout preservation..."):
                try:
                    formatted_text, html_output = extractor.process_pdf_enhanced(uploaded_file, extraction_method)
                    
                    if formatted_text:
                        st.success("Document processed with enhanced structure preservation!")
                        
                        # Create tabs
                        tab1, tab2, tab3 = st.tabs([
                            "Enhanced Text", 
                            "Clean HTML Preview", 
                            "Downloads"
                        ])
                        
                        with tab1:
                            st.subheader("Enhanced Processed Text")
                            st.text_area(
                                "Text with enhanced processing:",
                                value=formatted_text,
                                height=500,
                                help="Enhanced structure preservation with minimal processing"
                            )
                        
                        with tab2:
                            st.subheader("Clean HTML Preview")
                            st.markdown("*Clean formatting that matches original PDF structure:*")
                            st.components.v1.html(html_output, height=700, scrolling=True)
                        
                        with tab3:
                            st.subheader("Download Options")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.download_button(
                                    label="Download Clean HTML",
                                    data=html_output.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_enhanced.html",
                                    mime="text/html",
                                    help="Download HTML with clean formatting"
                                )
                            
                            with col2:
                                st.download_button(
                                    label="Download Enhanced Text",
                                    data=formatted_text.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_enhanced.txt",
                                    mime="text/plain",
                                    help="Download text with enhanced processing"
                                )
                    
                    else:
                        st.error("Failed to extract text from PDF. Please try a different extraction method.")
                
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")
                    st.info("Try using a different extraction method.")

if __name__ == "__main__":
    main()

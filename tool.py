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
        text = text.replace('Â­', '-')
        text = text.replace('\u00ad', '-')
        text = text.replace('\ufeff', '')
        text = text.replace('\u200b', '')
        
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        return text
    
    def extract_text_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber"""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
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
    
    def minimal_paragraph_reconstruction(self, text: str) -> str:
        """Minimal reconstruction - only fix obvious line breaks within sentences"""
        lines = text.split('\n')
        reconstructed = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Keep empty lines and page breaks as-is
            if not line or '[PAGE_BREAK]' in line:
                reconstructed.append(line)
                i += 1
                continue
            
            # Check if this line should be joined with next lines
            current_block = [line]
            j = i + 1
            
            # Only join lines that are clearly fragmented parts of sentences
            while j < len(lines):
                next_line = lines[j].strip()
                
                # Stop at empty lines or special markers
                if not next_line or '[PAGE_BREAK]' in next_line:
                    break
                
                # Stop at lines that clearly start new sections
                if (re.match(r'^[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+', next_line) or  # Case number
                    ' VS ' in next_line.upper() or ' V/S ' in next_line.upper() or  # Party names
                    re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', next_line) or  # Date
                    re.match(r'^Present\s*:', next_line, re.IGNORECASE) or  # Present
                    re.match(r'^:\d+:$', next_line) or  # Page marker
                    re.match(r'^\([ivxlcdmIVXLCDM]+\)', next_line) or  # Roman numerals
                    re.match(r'^\([a-zA-Z]\)', next_line) or  # Letter items
                    next_line.isupper() and len(next_line.split()) <= 4):  # Short ALL CAPS (likely signatures)
                    break
                
                # Join if the current line doesn't end with sentence-ending punctuation
                # and the next line doesn't start with a capital letter (indicating continuation)
                if (not line.rstrip().endswith(('.', ':', ')', '}')) and 
                    (not next_line[0].isupper() or 
                     next_line.lower().startswith(('and', 'or', 'but', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'the', 'a', 'an')))):
                    current_block.append(next_line)
                    line = next_line  # Update line for next iteration check
                    j += 1
                else:
                    break
            
            # Join the block and add to reconstructed
            reconstructed.append(' '.join(current_block))
            i = j
        
        return '\n'.join(reconstructed)
    
    def identify_content_type(self, line: str) -> str:
        """Identify content type with high precision"""
        stripped = line.strip()
        
        if not stripped:
            return "empty"
        
        if '[PAGE_BREAK]' in stripped:
            return "page_break"
        
        # Case number - very specific pattern
        if re.match(r'^[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+/?\d*$', stripped):
            return "case_number"
        
        # Party names - contains VS pattern
        if (' VS ' in stripped.upper() or ' V/S ' in stripped.upper() or 
            (' V. ' in stripped.upper() and len(stripped.split()) <= 10)):
            return "party_names"
        
        # Date
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "date"
        
        # Present line
        if re.match(r'^Present\s*:', stripped, re.IGNORECASE):
            return "present"
        
        # Page marker
        if re.match(r'^:\d+:$', stripped):
            return "page_marker"
        
        # Numbered items with specific patterns
        if re.match(r'^\([ivxlcdmIVXLCDM]+\)\s+', stripped):
            return "numbered_item"
        if re.match(r'^\([a-zA-Z]\)\s+', stripped):
            return "numbered_item"
        
        # Signature detection - very conservative
        # Only short ALL CAPS names or specific court titles
        if (stripped.isupper() and 
            3 <= len(stripped) <= 30 and 
            stripped.replace(' ', '').isalpha() and
            not any(word in stripped.lower() for word in ['the', 'and', 'or', 'of', 'in', 'on', 'at', 'for', 'with'])):
            return "signature"
        
        # Court designations
        if re.match(r'^District Judge$', stripped, re.IGNORECASE):
            return "signature"
        
        if re.match(r'^\([A-Za-z\s\-]+Court[^)]*\)$', stripped):
            return "signature"
        
        # Location with date pattern
        if re.match(r'^[A-Za-z\s,\.]+/\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "signature"
        
        return "paragraph"
    
    def convert_to_html(self, text: str) -> str:
        """Convert to HTML with minimal formatting"""
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
            line-height: 1.4;
            margin: 0;
            padding: 20px;
            background-color: #ffffff;
            color: #000000;
            font-size: 12pt;
        }
        
        .judgment-container {
            max-width: 8.5in;
            margin: 0 auto;
            padding: 1in;
            background: white;
            min-height: 11in;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            margin: 1em 0;
        }
        
        .party-names {
            text-align: center;
            font-weight: bold;
            margin: 1em 0;
            text-decoration: underline;
        }
        
        .date {
            text-align: center;
            margin: 1em 0;
        }
        
        .present {
            margin: 1em 0;
        }
        
        .paragraph {
            margin: 0.8em 0;
            text-align: justify;
            line-height: 1.5;
        }
        
        .numbered-item {
            margin: 0.8em 0;
            text-align: justify;
            line-height: 1.5;
            padding-left: 2em;
            text-indent: -2em;
        }
        
        .signature {
            text-align: center;
            font-weight: bold;
            margin: 1.5em 0 0.5em 0;
        }
        
        .page-marker {
            text-align: center;
            margin: 1em 0;
        }
        
        .page-break {
            page-break-before: always;
            margin: 2em 0 1em 0;
            text-align: center;
            color: #666;
            font-style: italic;
        }
        
        .empty-line {
            height: 1em;
        }
        
        @media print {
            body { 
                margin: 0; 
                background: white;
                font-size: 11pt;
            }
            .judgment-container { 
                margin: 0; 
                padding: 0.75in;
                min-height: auto;
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
            stripped = line.strip()
            
            if not stripped:
                html_content.append('<div class="empty-line"></div>')
                continue
            
            content_type = self.identify_content_type(stripped)
            
            # Escape HTML
            escaped_content = stripped.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            
            if content_type == "page_break":
                html_content.append('<div class="page-break">--- Page Break ---</div>')
            elif content_type == "case_number":
                html_content.append(f'<div class="case-number">{escaped_content}</div>')
            elif content_type == "party_names":
                html_content.append(f'<div class="party-names">{escaped_content}</div>')
            elif content_type == "date":
                html_content.append(f'<div class="date">{escaped_content}</div>')
            elif content_type == "present":
                html_content.append(f'<div class="present">{escaped_content}</div>')
            elif content_type == "page_marker":
                html_content.append(f'<div class="page-marker">{escaped_content}</div>')
            elif content_type == "numbered_item":
                html_content.append(f'<div class="numbered-item">{escaped_content}</div>')
            elif content_type == "signature":
                html_content.append(f'<div class="signature">{escaped_content}</div>')
            else:  # paragraph
                html_content.append(f'<div class="paragraph">{escaped_content}</div>')
        
        html_content.append('''    </div>
</body>
</html>''')
        
        return '\n'.join(html_content)
    
    def format_text(self, text: str) -> str:
        """Format text with proper indentation for numbered items"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            if not line.strip():
                formatted_lines.append('')
                continue
                
            content_type = self.identify_content_type(line)
            
            if content_type == "numbered_item":
                # Add proper indentation for numbered items
                stripped = line.strip()
                # Extract the numbering part and indent properly
                match = re.match(r'^(\([ivxlcdmIVXLCDM]+\)|\([a-zA-Z]\))\s*(.*)', stripped, re.IGNORECASE)
                if match:
                    number_part = match.group(1)
                    content_part = match.group(2)
                    formatted_lines.append(f"        {number_part} {content_part}")
                else:
                    formatted_lines.append(f"        {stripped}")
            else:
                formatted_lines.append(line.strip())
        
        return '\n'.join(formatted_lines)
    
    def process_pdf(self, pdf_file, extraction_method: str) -> Tuple[str, str]:
        """Process PDF with minimal intervention approach"""
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
        
        # Minimal paragraph reconstruction - only join obvious fragments
        reconstructed_text = self.minimal_paragraph_reconstruction(extracted_text)
        
        # Format text
        formatted_text = self.format_text(reconstructed_text)
        
        # Convert to HTML
        html_output = self.convert_to_html(reconstructed_text)
        
        return formatted_text, html_output

def main():
    st.title("Legal Judgment Text Extractor - Minimal Intervention")
    st.markdown("---")
    st.markdown("**Preserves original PDF structure with minimal processing**")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        extraction_method = st.selectbox(
            "Extraction Method:",
            ["PDFPlumber (Recommended)", "PyMuPDF", "PyPDF2"],
            help="Choose the PDF text extraction method"
        )
        
        st.markdown("### Approach")
        st.markdown("""
        - **Minimal Processing**: Only essential fixes
        - **Structure Preservation**: Maintains original layout
        - **Conservative Classification**: Only obvious patterns
        - **No Over-joining**: Keeps natural breaks
        - **Accurate Formatting**: Matches original appearance
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
        
        extractor = LegalJudgmentExtractor()
        
        col1, col2 = st.columns([2, 1])
        with col1:
            extract_button = st.button("Extract with Minimal Processing", type="primary", use_container_width=True)
        with col2:
            if st.button("Clear Results", use_container_width=True):
                st.rerun()
        
        if extract_button:
            with st.spinner("Processing with minimal intervention..."):
                try:
                    formatted_text, html_output = extractor.process_pdf(uploaded_file, extraction_method)
                    
                    if formatted_text:
                        st.success("Document processed - original structure preserved!")
                        
                        # Create tabs
                        tab1, tab2, tab3 = st.tabs([
                            "Formatted Text", 
                            "HTML Preview", 
                            "Downloads"
                        ])
                        
                        with tab1:
                            st.subheader("Minimally Processed Text")
                            st.text_area(
                                "Text with minimal processing:",
                                value=formatted_text,
                                height=500,
                                help="Original structure preserved with only essential formatting"
                            )
                        
                        with tab2:
                            st.subheader("HTML Preview")
                            st.markdown("*Formatted to closely match original PDF:*")
                            st.components.v1.html(html_output, height=700, scrolling=True)
                        
                        with tab3:
                            st.subheader("Download Options")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.download_button(
                                    label="Download HTML File",
                                    data=html_output.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_minimal.html",
                                    mime="text/html",
                                    help="Download HTML with minimal processing"
                                )
                            
                            with col2:
                                st.download_button(
                                    label="Download Text File",
                                    data=formatted_text.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_minimal.txt",
                                    mime="text/plain",
                                    help="Download text with minimal processing"
                                )
                    
                    else:
                        st.error("Failed to extract text from PDF. Please try a different extraction method.")
                
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")
                    st.info("Try using a different extraction method.")

if __name__ == "__main__":
    main()

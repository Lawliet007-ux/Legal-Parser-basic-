import streamlit as st
import PyPDF2
import fitz  # PyMuPDF
import pdfplumber
import re
from io import BytesIO
from typing import List, Tuple, Dict
import unicodedata

# Page configuration
st.set_page_config(
    page_title="Improved Legal Judgment Extractor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class ImprovedLegalExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.html_output = ""
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove problematic characters
        text = text.replace('Â­', '-')
        text = text.replace('\u00ad', '-')  # soft hyphen
        text = text.replace('\ufeff', '')   # BOM
        text = text.replace('\u200b', '')   # zero-width space
        text = text.replace('\x0c', '\n\n[PAGE_BREAK]\n\n')  # form feed
        
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        return text
    
    def extract_with_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber with better layout handling"""
        try:
            pdf_file.seek(0)
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
                    # Get text blocks to preserve structure better
                    text = page.extract_text(
                        layout=True,
                        x_tolerance=2,
                        y_tolerance=3
                    )
                    
                    if text:
                        full_text += text
                        if page_num < len(pdf.pages) - 1:
                            full_text += "\n\n[PAGE_BREAK]\n\n"
                
                return self.clean_text(full_text)
        except Exception as e:
            st.error(f"PDFPlumber error: {str(e)}")
            return ""
    
    def extract_with_pymupdf(self, pdf_file) -> str:
        """Extract text using PyMuPDF"""
        try:
            pdf_file.seek(0)
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
            st.error(f"PyMuPDF error: {str(e)}")
            return ""
    
    def extract_with_pypdf2(self, pdf_file) -> str:
        """Extract text using PyPDF2"""
        try:
            pdf_file.seek(0)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            full_text = ""
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                full_text += text
                if page_num < len(pdf_reader.pages) - 1:
                    full_text += "\n\n[PAGE_BREAK]\n\n"
            
            return self.clean_text(full_text)
        except Exception as e:
            st.error(f"PyPDF2 error: {str(e)}")
            return ""
    
    def intelligent_line_reconstruction(self, text: str) -> str:
        """Intelligently reconstruct paragraphs and preserve structure"""
        lines = text.split('\n')
        reconstructed = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Handle empty lines and page breaks
            if not current_line:
                # Don't add too many consecutive empty lines
                if not reconstructed or reconstructed[-1].strip():
                    reconstructed.append('')
                i += 1
                continue
            
            if '[PAGE_BREAK]' in current_line:
                reconstructed.append(current_line)
                i += 1
                continue
            
            # Check if this line should be joined with next lines
            paragraph_lines = [current_line]
            i += 1
            
            while i < len(lines):
                next_line = lines[i].strip()
                
                # Stop conditions for paragraph building
                if not next_line:  # Empty line ends paragraph
                    break
                if '[PAGE_BREAK]' in next_line:  # Page break ends paragraph
                    break
                if self.is_structural_element(next_line):  # Structural elements end paragraph
                    break
                if self.starts_new_section(next_line):  # New sections end paragraph
                    break
                
                # Join conditions
                should_join = (
                    not current_line.endswith(('.', ':', '!', '?')) or  # Incomplete sentence
                    (current_line.endswith('.') and not next_line[0].isupper() and 
                     not re.match(r'^\d+\.', next_line))  # Abbreviation or number
                )
                
                if should_join and not self.is_numbered_point(next_line):
                    paragraph_lines.append(next_line)
                    current_line = next_line  # Update for next iteration
                    i += 1
                else:
                    break
            
            # Join the paragraph lines
            if len(paragraph_lines) == 1:
                reconstructed.append(paragraph_lines[0])
            else:
                # Join with single spaces, preserve some structure
                joined = ' '.join(paragraph_lines)
                reconstructed.append(joined)
        
        return '\n'.join(reconstructed)
    
    def is_structural_element(self, line: str) -> bool:
        """Check if line is a structural element (headers, case info, etc.)"""
        line_upper = line.upper()
        
        # Case numbers and court info
        if re.match(r'^[A-Z\s]*\([A-Z]+\).*No\.?\s*\d+', line):
            return True
        
        # Party names (VS, V/S patterns)
        if ' VS ' in line_upper or ' V/S ' in line_upper or ' V. ' in line_upper:
            return True
        
        # Dates
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', line):
            return True
        
        # Present, coram, etc.
        if re.match(r'^(Present|Coram|Before)\s*:', line, re.IGNORECASE):
            return True
        
        # Page numbers
        if re.match(r'^:\d+:$', line) or re.match(r'^\d+$', line.strip()):
            return True
        
        # Judge names and titles
        if line_upper in ['DISTRICT JUDGE', 'ADDITIONAL DISTRICT JUDGE', 'CHIEF JUDICIAL MAGISTRATE']:
            return True
        
        return False
    
    def starts_new_section(self, line: str) -> bool:
        """Check if line starts a new section"""
        # Numbered paragraphs
        if re.match(r'^\d+\.', line.strip()):
            return True
        
        # Roman numerals
        if re.match(r'^\([ivxlcdm]+\)', line.lower().strip()):
            return True
        
        # Lettered points
        if re.match(r'^\([a-z]\)', line.lower().strip()):
            return True
        
        # "Heard." or similar court language
        if line.strip() in ['Heard.', 'Heard:', 'ORDER', 'JUDGMENT', 'REASONING']:
            return True
        
        return False
    
    def is_numbered_point(self, line: str) -> bool:
        """Check if line is a numbered point or sub-point"""
        return (
            re.match(r'^\d+\.', line.strip()) or
            re.match(r'^\([a-z]+\)', line.strip()) or
            re.match(r'^\([ivxlcdm]+\)', line.lower().strip())
        )
    
    def detect_element_type(self, line: str) -> str:
        """Detect the type of content element"""
        if not line.strip():
            return "empty"
        
        if '[PAGE_BREAK]' in line:
            return "page_break"
        
        # Case number
        if re.match(r'^[A-Z\s]*\([A-Z]+\).*No\.?\s*\d+', line):
            return "case_number"
        
        # Party names
        if (' VS ' in line.upper() or ' V/S ' in line.upper() or ' V. ' in line.upper()) and len(line.split()) < 20:
            return "parties"
        
        # Date
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', line.strip()):
            return "date"
        
        # Present/Coram
        if re.match(r'^(Present|Coram|Before)\s*:', line, re.IGNORECASE):
            return "present"
        
        # Page numbers
        if re.match(r'^:\d+:$', line.strip()):
            return "page_number"
        
        # Judge signature area
        if line.strip().upper() in ['DISTRICT JUDGE', 'ADDITIONAL DISTRICT JUDGE', 'CHIEF JUDICIAL MAGISTRATE']:
            return "judge_title"
        
        # Location and date at end
        if re.match(r'.+New Delhi/\d{1,2}\.\d{1,2}\.\d{4}$', line.strip()):
            return "location_date"
        
        # All caps names (signatures) - be more selective
        if (line.strip().isupper() and 
            3 <= len(line.strip().split()) <= 4 and 
            line.strip().replace(' ', '').isalpha() and
            len(line.strip()) > 8):
            return "signature"
        
        # Numbered paragraphs
        if re.match(r'^\d+\.', line.strip()) or re.match(r'^\([a-z]+\)', line.strip()):
            return "numbered"
        
        return "paragraph"
    
    def create_clean_html(self, text: str) -> str:
        """Create clean HTML with proper formatting"""
        lines = text.split('\n')
        
        html_parts = ['''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legal Judgment</title>
    <style>
        body {
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.4;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #000;
        }
        
        .document {
            max-width: 210mm;
            margin: 0 auto;
            padding: 25mm;
            background: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            min-height: 297mm;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            margin: 20px 0;
            font-size: 13pt;
        }
        
        .parties {
            text-align: center;
            font-weight: bold;
            margin: 15px 0;
            text-decoration: underline;
        }
        
        .date {
            text-align: center;
            margin: 15px 0;
        }
        
        .present {
            margin: 15px 0;
            font-weight: bold;
        }
        
        .paragraph {
            margin: 10px 0;
            text-align: justify;
            line-height: 1.5;
        }
        
        .numbered {
            margin: 10px 0;
            text-align: justify;
            line-height: 1.5;
            padding-left: 20px;
            text-indent: -20px;
        }
        
        .page-number {
            text-align: center;
            margin: 10px 0;
            font-weight: bold;
        }
        
        .signature {
            text-align: right;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .judge-title {
            text-align: right;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .location-date {
            text-align: right;
            margin: 5px 0;
        }
        
        .page-break {
            page-break-before: always;
            text-align: center;
            color: #666;
            font-style: italic;
            margin: 20px 0;
            border-top: 1px dashed #ccc;
            padding-top: 10px;
        }
        
        .empty {
            height: 12pt;
        }
        
        @media print {
            body { 
                margin: 0; 
                padding: 0;
                background: white;
            }
            .document { 
                margin: 0; 
                padding: 20mm;
                box-shadow: none;
                min-height: auto;
            }
            .page-break {
                border: none;
                margin: 0;
                padding: 0;
                font-size: 0;
            }
        }
    </style>
</head>
<body>
    <div class="document">''']
        
        consecutive_empty = 0
        
        for line in lines:
            element_type = self.detect_element_type(line)
            
            if element_type == "empty":
                consecutive_empty += 1
                if consecutive_empty <= 2:  # Limit consecutive empty lines
                    html_parts.append('        <div class="empty"></div>')
                continue
            else:
                consecutive_empty = 0
            
            # Escape HTML
            escaped = (line.replace('&', '&amp;')
                          .replace('<', '&lt;')
                          .replace('>', '&gt;')
                          .replace('"', '&quot;'))
            
            if element_type == "page_break":
                html_parts.append('        <div class="page-break">--- Page Break ---</div>')
            else:
                css_class = {
                    "case_number": "case-number",
                    "parties": "parties",
                    "date": "date", 
                    "present": "present",
                    "paragraph": "paragraph",
                    "numbered": "numbered",
                    "page_number": "page-number",
                    "signature": "signature",
                    "judge_title": "judge-title",
                    "location_date": "location-date"
                }.get(element_type, "paragraph")
                
                html_parts.append(f'        <div class="{css_class}">{escaped}</div>')
        
        html_parts.append('''    </div>
</body>
</html>''')
        
        return '\n'.join(html_parts)
    
    def process_pdf(self, pdf_file, method: str) -> Tuple[str, str]:
        """Main processing function"""
        # Extract raw text
        if method == "PDFPlumber":
            raw_text = self.extract_with_pdfplumber(pdf_file)
        elif method == "PyMuPDF": 
            raw_text = self.extract_with_pymupdf(pdf_file)
        else:
            raw_text = self.extract_with_pypdf2(pdf_file)
        
        if not raw_text:
            return "", ""
        
        # Reconstruct text intelligently
        processed_text = self.intelligent_line_reconstruction(raw_text)
        
        # Create HTML
        html_output = self.create_clean_html(processed_text)
        
        return processed_text, html_output

def main():
    st.title("🏛️ Improved Legal Judgment Extractor")
    st.markdown("---")
    st.markdown("**Smart text reconstruction with better paragraph handling**")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Extraction Settings")
        
        method = st.selectbox(
            "PDF Extraction Method:",
            ["PDFPlumber", "PyMuPDF", "PyPDF2"],
            help="Choose extraction method based on your PDF quality"
        )
        
        st.markdown("### 🎯 New Approach")
        st.markdown("""
        - **Smart Line Joining**: Intelligently reconstructs paragraphs
        - **Structure Preservation**: Maintains legal document formatting
        - **Reduced Empty Lines**: Eliminates excessive spacing
        - **Better Pattern Recognition**: Improved content classification
        - **Clean HTML Output**: Professional document appearance
        """)
        
        st.markdown("### 🔧 Key Improvements")
        st.markdown("""
        - Paragraph reconstruction logic
        - Structural element detection
        - Reduced over-formatting
        - Better spacing control
        - Professional HTML styling
        """)
    
    # Main content
    uploaded_file = st.file_uploader(
        "📄 Upload Legal Judgment PDF",
        type=['pdf'],
        help="Select a PDF file containing a legal judgment"
    )
    
    if uploaded_file is not None:
        st.info(f"**File:** {uploaded_file.name} | **Size:** {uploaded_file.size / 1024:.1f} KB")
        
        extractor = ImprovedLegalExtractor()
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("🚀 Extract with Improved Logic", type="primary", use_container_width=True):
                with st.spinner("Processing with improved algorithms..."):
                    try:
                        processed_text, html_output = extractor.process_pdf(uploaded_file, method)
                        
                        if processed_text:
                            st.success("✅ Document processed successfully!")
                            
                            # Results tabs
                            tab1, tab2, tab3 = st.tabs([
                                "📝 Processed Text",
                                "🌐 HTML Preview", 
                                "💾 Downloads"
                            ])
                            
                            with tab1:
                                st.subheader("Processed Text Output")
                                st.text_area(
                                    "Intelligently reconstructed text:",
                                    value=processed_text,
                                    height=600,
                                    help="Text with smart paragraph reconstruction"
                                )
                            
                            with tab2:
                                st.subheader("HTML Preview")
                                st.markdown("*Clean, professional formatting:*")
                                st.components.v1.html(html_output, height=700, scrolling=True)
                            
                            with tab3:
                                st.subheader("Download Files")
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.download_button(
                                        label="📄 Download HTML",
                                        data=html_output.encode('utf-8'),
                                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_improved.html",
                                        mime="text/html",
                                        help="Download professionally formatted HTML"
                                    )
                                
                                with col2:
                                    st.download_button(
                                        label="📝 Download Text",
                                        data=processed_text.encode('utf-8'),
                                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_improved.txt",
                                        mime="text/plain",
                                        help="Download processed text"
                                    )
                        
                        else:
                            st.error("❌ Failed to extract text. Try a different method.")
                    
                    except Exception as e:
                        st.error(f"❌ Processing error: {str(e)}")
                        st.info("Try using a different extraction method.")
        
        with col2:
            if st.button("🗑️ Clear", use_container_width=True):
                st.rerun()

if __name__ == "__main__":
    main()

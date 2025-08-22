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
        text = text.replace('Â­', '-')  # Replace soft hyphen
        text = text.replace('\u00ad', '-')  # Replace soft hyphen
        text = text.replace('\ufeff', '')  # Remove BOM
        text = text.replace('\u200b', '')  # Remove zero-width space
        
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        return text
    
    def extract_text_pdfplumber(self, pdf_file) -> str:
        """Extract text using pdfplumber with better layout preservation"""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
                    # Extract text with layout settings optimized for legal documents
                    text = page.extract_text(
                        layout=True, 
                        x_tolerance=3,
                        y_tolerance=3
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
    
    def get_line_type(self, line: str) -> str:
        """Improved line type detection with better accuracy"""
        stripped = line.strip()
        
        if not stripped:
            return "empty"
        
        # Case number patterns - more specific
        if re.match(r'^[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+/?\d*$', stripped):
            return "case_number"
        
        # Date patterns
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "date"
        
        # Present statement
        if re.match(r'^Present\s*:', stripped, re.IGNORECASE):
            return "present"
        
        # Page markers like :2:, :3:
        if re.match(r'^:\d+:$', stripped):
            return "page_marker"
        
        # Ordered list items with Roman numerals in parentheses
        if re.match(r'^\([ivxlcdm]+\)\s+', stripped, re.IGNORECASE):
            return "numbering"
        
        # Ordered list items with letters in parentheses
        if re.match(r'^\([a-z]\)\s+', stripped):
            return "numbering"
        
        # Numbered list items
        if re.match(r'^\d+\.\s+', stripped):
            return "numbering"
        
        # Sub-numbered items like 1.1, 2.3 etc
        if re.match(r'^\d+\.\d+', stripped):
            return "numbering"
        
        # VS patterns (party names)
        if ' VS ' in stripped.upper() or ' V/S ' in stripped.upper() or ' V. ' in stripped.upper():
            return "header"
        
        # Judge signatures - more restrictive
        judge_patterns = [
            r'^[A-Z\s]+JUDGE$',
            r'^\([A-Za-z\s\-]+Court[^)]*\)$',
            r'^District Judge$',
            r'^Additional District Judge$',
            r'^[A-Z\s]+DISTRICT JUDGE$'
        ]
        
        for pattern in judge_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                return "signature"
        
        # Location and date signature patterns
        if re.match(r'^[A-Za-z\s,]+/\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "signature"
        
        return "paragraph"
    
    def smart_paragraph_reconstruction(self, text: str) -> str:
        """Intelligently reconstruct paragraphs with better logic"""
        lines = text.split('\n')
        processed_lines = []
        current_paragraph = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Handle empty lines
            if not line:
                if current_paragraph:
                    processed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                processed_lines.append('')
                i += 1
                continue
            
            # Handle page breaks
            if '[PAGE_BREAK]' in line:
                if current_paragraph:
                    processed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                processed_lines.append(line)
                i += 1
                continue
            
            line_type = self.get_line_type(line)
            
            # Lines that should stand alone
            if line_type in ['case_number', 'header', 'date', 'present', 'signature', 'page_marker']:
                if current_paragraph:
                    processed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                processed_lines.append(line)
                i += 1
                continue
            
            # Numbered/ordered items
            if line_type == 'numbering':
                if current_paragraph:
                    processed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # Collect the complete numbered item
                numbered_content = [line]
                j = i + 1
                
                # Look ahead for continuation lines
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    
                    next_type = self.get_line_type(next_line)
                    
                    # If next line is also numbering or special type, stop
                    if next_type in ['numbering', 'case_number', 'header', 'date', 'present', 'signature', 'page_marker']:
                        break
                    
                    # If line starts with capital and looks like new sentence, stop
                    if (next_line[0].isupper() and 
                        len(next_line) > 20 and 
                        not next_line.lower().startswith(('and', 'or', 'but', 'however', 'therefore', 'thus', 'hence'))):
                        break
                    
                    numbered_content.append(next_line)
                    j += 1
                
                processed_lines.append(' '.join(numbered_content))
                i = j
                continue
            
            # Regular paragraph text
            if line_type == 'paragraph':
                # Check if this is a continuation or new paragraph
                if current_paragraph:
                    # Heuristics for continuation vs new paragraph
                    last_line = current_paragraph[-1] if current_paragraph else ""
                    
                    # If last line ended with period and current starts with capital, likely new paragraph
                    if (last_line.endswith('.') and 
                        line[0].isupper() and 
                        len(line) > 10):
                        processed_lines.append(' '.join(current_paragraph))
                        current_paragraph = [line]
                    else:
                        current_paragraph.append(line)
                else:
                    current_paragraph = [line]
            
            i += 1
        
        # Handle any remaining paragraph
        if current_paragraph:
            processed_lines.append(' '.join(current_paragraph))
        
        return '\n'.join(processed_lines)
    
    def normalize_spacing(self, text: str) -> str:
        """Improved spacing normalization"""
        # First reconstruct paragraphs
        reconstructed = self.smart_paragraph_reconstruction(text)
        
        lines = reconstructed.split('\n')
        normalized_lines = []
        
        prev_empty = False
        
        for line in lines:
            if not line.strip():
                # Only add one empty line between content
                if not prev_empty and normalized_lines:
                    normalized_lines.append("")
                prev_empty = True
                continue
            
            prev_empty = False
            line_type = self.get_line_type(line.strip())
            
            # Clean up the line
            cleaned = ' '.join(line.split())
            
            # Add appropriate indentation for numbered items
            if line_type == 'numbering':
                # Extract numbering part and content
                match = re.match(r'^(\([ivxlcdm]+\)|\([a-z]\)|\d+\.)\s*(.*)', cleaned, re.IGNORECASE)
                if match:
                    numbering_part = match.group(1)
                    content_part = match.group(2)
                    if content_part:
                        cleaned = f"    {numbering_part} {content_part}"
                    else:
                        cleaned = f"    {numbering_part}"
                else:
                    cleaned = f"    {cleaned}"
            
            normalized_lines.append(cleaned)
        
        return '\n'.join(normalized_lines)
    
    def convert_to_html(self, text: str) -> str:
        """Convert text to well-formatted HTML with better structure"""
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
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #333;
            font-size: 14px;
        }
        
        .judgment-container {
            max-width: 210mm;
            margin: 0 auto;
            padding: 30px;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border: 1px solid #ddd;
            min-height: 297mm;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            color: #2c3e50;
        }
        
        .header {
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0 30px 0;
            border-bottom: 2px solid #34495e;
            padding-bottom: 15px;
            color: #2c3e50;
        }
        
        .date {
            text-align: center;
            font-weight: bold;
            margin: 25px 0;
            color: #2c3e50;
        }
        
        .present {
            margin: 25px 0;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .numbering {
            margin: 15px 0;
            font-weight: 500;
            text-indent: -20px;
            padding-left: 20px;
        }
        
        .paragraph {
            margin: 15px 0;
            text-align: justify;
            line-height: 1.8;
        }
        
        .signature {
            text-align: center;
            font-weight: bold;
            margin: 30px 0 10px 0;
            color: #2c3e50;
        }
        
        .page-marker {
            text-align: center;
            font-weight: bold;
            margin: 25px 0;
            font-size: 16px;
            color: #7f8c8d;
        }
        
        .page-break {
            page-break-before: always;
            border-top: 2px solid #bdc3c7;
            margin: 40px 0 20px 0;
            padding-top: 20px;
            text-align: center;
            color: #7f8c8d;
            font-style: italic;
            font-size: 12px;
        }
        
        .spacing {
            height: 15px;
        }
        
        /* Enhanced print styles */
        @media print {
            body { 
                margin: 0; 
                background: white;
                font-size: 12px;
            }
            .judgment-container { 
                box-shadow: none; 
                border: none; 
                margin: 0; 
                padding: 20px;
                min-height: auto;
            }
            .page-break {
                border-top: none;
                margin: 10px 0;
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
            
            # Handle empty lines
            if not stripped:
                html_content.append('<div class="spacing"></div>')
                continue
            
            # Handle page breaks
            if '[PAGE_BREAK]' in line:
                html_content.append('<div class="page-break">--- Page Break ---</div>')
                continue
            
            # Detect content type
            line_type = self.get_line_type(stripped)
            
            # Escape HTML characters
            escaped_line = stripped.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            
            # Apply appropriate CSS class
            html_content.append(f'<div class="{line_type}">{escaped_line}</div>')
        
        html_content.append('''    </div>
</body>
</html>''')
        
        return '\n'.join(html_content)
    
    def generate_statistics(self, text: str) -> Dict:
        """Generate comprehensive document statistics"""
        lines = text.split('\n')
        words = text.split()
        
        # Count different types of content
        content_counts = {
            'case_number': 0,
            'header': 0,
            'date': 0,
            'present': 0,
            'numbering': 0,
            'paragraph': 0,
            'signature': 0,
            'page_marker': 0
        }
        
        for line in lines:
            if line.strip():
                line_type = self.get_line_type(line.strip())
                if line_type in content_counts:
                    content_counts[line_type] += 1
        
        stats = {
            'total_lines': len(lines),
            'non_empty_lines': len([l for l in lines if l.strip()]),
            'total_words': len(words),
            'total_characters': len(text),
            'pages': text.count('[PAGE_BREAK]') + 1,
            'content_breakdown': content_counts,
            'avg_words_per_line': len(words) / max(len([l for l in lines if l.strip()]), 1),
            'numbering_items': content_counts['numbering']
        }
        
        return stats
    
    def process_pdf(self, pdf_file, extraction_method: str) -> Tuple[str, str]:
        """Process PDF and return formatted text and HTML"""
        pdf_file.seek(0)
        
        # Extract text based on method
        if extraction_method == "PDFPlumber (Recommended)":
            extracted_text = self.extract_text_pdfplumber(pdf_file)
        elif extraction_method == "PyMuPDF":
            extracted_text = self.extract_text_pymupdf(pdf_file)
        else:
            extracted_text = self.extract_text_pypdf2(pdf_file)
        
        if not extracted_text:
            return "", ""
        
        # Normalize spacing and structure
        formatted_text = self.normalize_spacing(extracted_text)
        
        # Convert to HTML
        html_output = self.convert_to_html(formatted_text)
        
        return formatted_text, html_output

def main():
    st.title("⚖️ Legal Judgment Text Extractor (Improved)")
    st.markdown("---")
    st.markdown("**Professional extraction and formatting of legal judgments from PDF files**")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Settings")
        
        extraction_method = st.selectbox(
            "Extraction Method:",
            ["PDFPlumber (Recommended)", "PyMuPDF", "PyPDF2"],
            help="Choose the PDF text extraction method"
        )
        
        st.markdown("### Improvements")
        st.markdown("""
        ✅ **Better paragraph reconstruction**
        ✅ **Improved content classification** 
        ✅ **Smarter spacing normalization**
        ✅ **Enhanced HTML formatting**
        ✅ **Reduced fragmentation**
        ✅ **Better numbered list handling**
        """)
    
    # File upload
    uploaded_file = st.file_uploader(
        "📄 Upload Legal Judgment PDF",
        type=['pdf'],
        help="Select a PDF file containing a legal judgment"
    )
    
    if uploaded_file is not None:
        file_details = f"**File:** {uploaded_file.name} | **Size:** {uploaded_file.size / 1024:.1f} KB"
        st.info(file_details)
        
        extractor = LegalJudgmentExtractor()
        
        col1, col2 = st.columns([2, 1])
        with col1:
            extract_button = st.button("🔍 Extract and Format Text", type="primary", use_container_width=True)
        with col2:
            if st.button("🔄 Clear Results", use_container_width=True):
                st.rerun()
        
        if extract_button:
            with st.spinner("Processing PDF with improved algorithms..."):
                try:
                    formatted_text, html_output = extractor.process_pdf(uploaded_file, extraction_method)
                    
                    if formatted_text:
                        st.success("✅ Document processed successfully with improved formatting!")
                        
                        # Create tabs
                        tab1, tab2, tab3, tab4 = st.tabs([
                            "📄 Formatted Text", 
                            "🌐 HTML Preview", 
                            "📊 Analysis", 
                            "💾 Downloads"
                        ])
                        
                        with tab1:
                            st.subheader("Improved Formatted Text Output")
                            st.text_area(
                                "Clean, formatted text with better paragraph structure:",
                                value=formatted_text,
                                height=500,
                                help="This shows the processed text with improved formatting algorithms"
                            )
                        
                        with tab2:
                            st.subheader("Enhanced HTML Document Preview")
                            st.markdown("*Enhanced formatting with better content recognition:*")
                            st.components.v1.html(html_output, height=700, scrolling=True)
                        
                        with tab3:
                            st.subheader("Document Analysis")
                            stats = extractor.generate_statistics(formatted_text)
                            
                            # Key metrics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Pages", stats['pages'])
                            with col2:
                                st.metric("Total Words", stats['total_words'])
                            with col3:
                                st.metric("Paragraphs", stats['content_breakdown']['paragraph'])
                            with col4:
                                st.metric("Numbered Items", stats['numbering_items'])
                            
                            # Content breakdown
                            st.markdown("#### Content Structure Analysis")
                            breakdown_data = {k: v for k, v in stats['content_breakdown'].items() if v > 0}
                            
                            for content_type, count in breakdown_data.items():
                                st.write(f"**{content_type.replace('_', ' ').title()}**: {count} items")
                            
                            # Additional metrics
                            st.markdown("#### Reading Metrics")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Avg Words per Line", f"{stats['avg_words_per_line']:.1f}")
                            with col2:
                                st.metric("Character Count", stats['total_characters'])
                        
                        with tab4:
                            st.subheader("Download Formatted Document")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.download_button(
                                    label="📄 Download HTML File",
                                    data=html_output.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_improved.html",
                                    mime="text/html",
                                    help="Download as improved HTML document"
                                )
                            
                            with col2:
                                st.download_button(
                                    label="📝 Download Text File",
                                    data=formatted_text.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_improved.txt",
                                    mime="text/plain",
                                    help="Download as improved text file"
                                )
                    
                    else:
                        st.error("❌ Failed to extract text from PDF. Please try a different extraction method.")
                
                except Exception as e:
                    st.error(f"❌ Processing error: {str(e)}")
                    st.info("Try using a different extraction method or ensure the PDF contains readable text.")
    
    else:
        # Show improvements when no file uploaded
        st.markdown("### 🔧 Key Improvements Made")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **❌ Previous Issues:**
            - Lines incorrectly classified as signatures
            - Excessive fragmentation of paragraphs  
            - Too many empty spaces inserted
            - Poor numbered list handling
            - Sentences split inappropriately
            """)
        
        with col2:
            st.markdown("""
            **✅ Improvements:**
            - More accurate line type detection
            - Better paragraph reconstruction logic
            - Smarter spacing normalization
            - Enhanced numbered list recognition
            - Proper sentence continuity
            """)

if __name__ == "__main__":
    main()

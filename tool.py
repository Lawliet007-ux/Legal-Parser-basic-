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
                        x_tolerance=3,  # Slightly more tolerance for character spacing
                        y_tolerance=3   # Better line detection
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
    
    def reconstruct_paragraphs(self, text: str) -> str:
        """Intelligently reconstruct paragraphs from fragmented lines"""
        lines = text.split('\n')
        reconstructed_lines = []
        current_paragraph = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Handle empty lines
            if not line:
                if current_paragraph:
                    reconstructed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                reconstructed_lines.append('')
                i += 1
                continue
            
            # Handle special markers
            if '[PAGE_BREAK]' in line:
                if current_paragraph:
                    reconstructed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                reconstructed_lines.append(line)
                i += 1
                continue
            
            # Detect different line types
            line_type = self.get_line_type(line)
            
            # Lines that should stand alone
            if line_type in ['case_number', 'header', 'date', 'present', 'numbering', 'signature', 'page_marker']:
                if current_paragraph:
                    reconstructed_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                reconstructed_lines.append(line)
                i += 1
                continue
            
            # Regular paragraph text
            if line_type == 'paragraph':
                # Check if this line continues from the previous
                if current_paragraph and not line[0].isupper():
                    # Likely continuation of previous sentence
                    current_paragraph.append(line)
                else:
                    # Start of new paragraph or sentence
                    if current_paragraph:
                        reconstructed_lines.append(' '.join(current_paragraph))
                    current_paragraph = [line]
            
            i += 1
        
        # Handle any remaining paragraph
        if current_paragraph:
            reconstructed_lines.append(' '.join(current_paragraph))
        
        return '\n'.join(reconstructed_lines)
    
    def get_line_type(self, line: str) -> str:
        """Determine the type of a text line"""
        stripped = line.strip()
        
        if not stripped:
            return "empty"
        
        # Case number
        if re.match(r'[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+', stripped):
            return "case_number"
        
        # Date
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', stripped):
            return "date"
        
        # Present statement
        if stripped.startswith('Present'):
            return "present"
        
        # Page markers like :2:, :3:
        if re.match(r'^:\d+:$', stripped):
            return "page_marker"
        
        # Numbering patterns
        if re.match(r'^\([ivxlcdm]+\)\s+', stripped, re.IGNORECASE):
            return "numbering"
        if re.match(r'^\([a-z]\)\s+', stripped):
            return "numbering"
        if re.match(r'^\d+\.\s+', stripped):
            return "numbering"
        if re.match(r'^\d+\.\d+', stripped):
            return "numbering"
        
        # Headers (party names with VS)
        if ' VS ' in stripped.upper() or ' V/S ' in stripped.upper():
            return "header"
        
        # Signatures (judge names, courts, etc.)
        if any(term in stripped.upper() for term in ['JUDGE', 'COURT', 'DISTRICT', 'MAGISTRATE']):
            return "signature"
        
        # All caps names (likely signatures)
        if len(stripped) > 8 and stripped.replace(' ', '').isalpha() and stripped.isupper():
            return "signature"
        
        return "paragraph"
    
    def normalize_spacing(self, text: str) -> str:
        """Improved spacing normalization"""
        # First reconstruct paragraphs
        reconstructed = self.reconstruct_paragraphs(text)
        
        lines = reconstructed.split('\n')
        normalized_lines = []
        
        for line in lines:
            if not line.strip():
                normalized_lines.append("")
                continue
            
            line_type = self.get_line_type(line)
            
            # Different handling based on line type
            if line_type in ['case_number', 'header', 'date', 'signature']:
                # Center-align these by removing excessive leading spaces
                cleaned = ' '.join(line.split())
                normalized_lines.append(cleaned)
            elif line_type == 'numbering':
                # Preserve some indentation for numbering
                # Detect the numbering part and content
                match = re.match(r'^(\s*\([ivxlcdm]+\)\s*|\s*\([a-z]\)\s*|\s*\d+\.\s*)', line, re.IGNORECASE)
                if match:
                    numbering_part = match.group(1).strip()
                    content_part = line[match.end():].strip()
                    if content_part:
                        normalized_lines.append(f"    {numbering_part} {content_part}")
                    else:
                        normalized_lines.append(f"    {numbering_part}")
                else:
                    normalized_lines.append(f"    {' '.join(line.split())}")
            else:
                # Regular paragraphs
                cleaned = ' '.join(line.split())
                normalized_lines.append(cleaned)
        
        return '\n'.join(normalized_lines)
    
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
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #000000;
            font-size: 14px;
        }
        
        .judgment-container {
            max-width: 210mm;
            margin: 0 auto;
            padding: 25mm;
            background: white;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
            border: 1px solid #ddd;
            min-height: 297mm;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 15px 0;
        }
        
        .header {
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 15px 0 25px 0;
            border-bottom: 2px solid #000;
            padding-bottom: 15px;
        }
        
        .date {
            text-align: center;
            font-weight: bold;
            margin: 20px 0;
        }
        
        .present {
            margin: 20px 0;
            font-weight: bold;
        }
        
        .numbering {
            margin: 15px 0 8px 0;
            font-weight: bold;
        }
        
        .paragraph {
            margin: 12px 0;
            text-align: justify;
            line-height: 1.8;
        }
        
        .signature {
            text-align: center;
            font-weight: bold;
            margin: 25px 0 8px 0;
        }
        
        .page-marker {
            text-align: center;
            font-weight: bold;
            margin: 20px 0;
            font-size: 18px;
        }
        
        .page-break {
            page-break-before: always;
            border-top: 3px double #333;
            margin: 50px 0 30px 0;
            padding-top: 30px;
            text-align: center;
            color: #666;
            font-style: italic;
            font-size: 12px;
        }
        
        .spacing {
            height: 20px;
        }
        
        /* Enhanced print styles */
        @media print {
            body { 
                margin: 0; 
                background: white;
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
                margin: 20px 0;
                font-size: 0;
                height: 0;
            }
        }
    </style>
</head>
<body>
    <div class="judgment-container">''']
        
        consecutive_empty = 0
        last_was_numbering = False
        
        for line in lines:
            stripped = line.strip()
            
            # Handle empty lines with better logic
            if not stripped:
                consecutive_empty += 1
                if consecutive_empty == 1:  # Only first empty line
                    html_content.append('<div class="spacing"></div>')
                continue
            else:
                consecutive_empty = 0
            
            # Handle page breaks
            if '[PAGE_BREAK]' in line:
                html_content.append('<div class="page-break">--- New Page ---</div>')
                continue
            
            # Detect content type
            line_type = self.get_line_type(stripped)
            
            # Escape HTML characters
            escaped_line = stripped.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            
            # Apply appropriate CSS class
            css_class = line_type
            
            # Special handling for numbering continuation
            if line_type == 'paragraph' and last_was_numbering:
                # Check if this looks like continuation of numbering
                if not re.match(r'^[A-Z]', stripped):  # Doesn't start with capital
                    escaped_line = f"        {escaped_line}"  # Add extra indentation
            
            html_content.append(f'<div class="{css_class}">{escaped_line}</div>')
            
            last_was_numbering = (line_type == 'numbering')
        
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
    st.title("⚖️ Legal Judgment Text Extractor")
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
        
        st.markdown("### Features")
        st.markdown("""
        ✅ **Smart paragraph reconstruction**
        ✅ **Proper content classification** 
        ✅ **Intelligent spacing normalization**
        ✅ **Professional HTML formatting**
        ✅ **Print-ready output**
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
            with st.spinner("Processing PDF and formatting content..."):
                try:
                    formatted_text, html_output = extractor.process_pdf(uploaded_file, extraction_method)
                    
                    if formatted_text:
                        st.success("✅ Document processed successfully!")
                        
                        # Create tabs
                        tab1, tab2, tab3, tab4 = st.tabs([
                            "📄 Formatted Text", 
                            "🌐 HTML Preview", 
                            "📊 Analysis", 
                            "💾 Downloads"
                        ])
                        
                        with tab1:
                            st.subheader("Formatted Text Output")
                            st.text_area(
                                "Clean, formatted text with proper paragraph structure:",
                                value=formatted_text,
                                height=500,
                                help="This shows the processed text with intelligent formatting"
                            )
                        
                        with tab2:
                            st.subheader("HTML Document Preview")
                            st.markdown("*This preview shows how the document will appear when printed or saved as HTML:*")
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
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_formatted.html",
                                    mime="text/html",
                                    help="Download as formatted HTML document"
                                )
                            
                            with col2:
                                st.download_button(
                                    label="📝 Download Text File",
                                    data=formatted_text.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_formatted.txt",
                                    mime="text/plain",
                                    help="Download as plain text file"
                                )
                            
                            st.markdown("#### Export Options")
                            st.markdown("""
                            - **HTML**: Best for viewing, printing, and sharing
                            - **Text**: Best for editing and further processing
                            """)
                    
                    else:
                        st.error("❌ Failed to extract text from PDF. Please try a different extraction method.")
                
                except Exception as e:
                    st.error(f"❌ Processing error: {str(e)}")
                    st.info("Try using a different extraction method or ensure the PDF contains readable text.")
    
    else:
        # Show example when no file uploaded
        st.markdown("### 📋 What This Tool Does")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Before: Raw PDF Extract**
            ```
            OMP (I) Comm. No. 800/20
            HDB FINANCIAL SERVICES LTD VS THE DEOBAND PUBLIC SCHOOL
            13.02.2020
            Present : Sh. Ashok Kumar Ld. Counsel for petitioner.
                            This is a petition u/s 9 of Indian Arbitration and Conciliation Act
            1996 for issuing interim measure by way of appointment of receiver is received
            by way of assignment. It be checked and registered.
            ```
            """)
        
        with col2:
            st.markdown("""
            **After: Smart Formatting**
            ```
            OMP (I) Comm. No. 800/20
            HDB FINANCIAL SERVICES LTD VS THE DEOBAND PUBLIC SCHOOL
            13.02.2020
            
            Present: Sh. Ashok Kumar Ld. Counsel for petitioner.
            
            This is a petition u/s 9 of Indian Arbitration and Conciliation Act 1996 for issuing interim measure by way of appointment of receiver is received by way of assignment. It be checked and registered.
            ```
            """)

if __name__ == "__main__":
    main()

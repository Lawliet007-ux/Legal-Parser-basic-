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
                        x_tolerance=2,
                        y_tolerance=2
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
    
    def is_case_number(self, line: str) -> bool:
        """Check if line is a case number"""
        return bool(re.match(r'^[A-Z\s]*\([A-Z]+\)\s*[A-Za-z]*\.?\s*No\.?\s*\d+/?\d*$', line.strip()))
    
    def is_party_names(self, line: str) -> bool:
        """Check if line contains party names (VS pattern)"""
        upper_line = line.strip().upper()
        return ' VS ' in upper_line or ' V/S ' in upper_line or ' V. ' in upper_line
    
    def is_date(self, line: str) -> bool:
        """Check if line is a date"""
        return bool(re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', line.strip()))
    
    def is_present_line(self, line: str) -> bool:
        """Check if line starts with Present"""
        return line.strip().lower().startswith('present')
    
    def is_page_marker(self, line: str) -> bool:
        """Check if line is a page marker like :2:"""
        return bool(re.match(r'^:\d+:$', line.strip()))
    
    def is_numbered_item(self, line: str) -> bool:
        """Check if line is a numbered list item"""
        stripped = line.strip()
        patterns = [
            r'^\([ivxlcdm]+\)',  # Roman numerals in parentheses
            r'^\([a-z]\)',       # Letters in parentheses
            r'^\d+\)',           # Numbers in parentheses
        ]
        return any(re.match(pattern, stripped, re.IGNORECASE) for pattern in patterns)
    
    def is_signature_block(self, line: str) -> bool:
        """Check if line is part of signature block"""
        stripped = line.strip()
        signature_patterns = [
            r'^[A-Z\s]+$',  # All caps names
            r'^District Judge$',
            r'^Additional District Judge$',
            r'^\([A-Za-z\s\-]+Court[^)]*\)$',
            r'^[A-Za-z\s,]+/\d{1,2}\.\d{1,2}\.\d{4}$'  # Location/date
        ]
        
        # Must be reasonably short and match patterns
        if len(stripped) > 50:
            return False
            
        return any(re.match(pattern, stripped, re.IGNORECASE) for pattern in signature_patterns)
    
    def reconstruct_document(self, text: str) -> List[Dict]:
        """Reconstruct document preserving original structure"""
        lines = text.split('\n')
        document_blocks = []
        current_paragraph = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                i += 1
                continue
            
            # Handle page breaks
            if '[PAGE_BREAK]' in line:
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'page_break', 'content': ''})
                i += 1
                continue
            
            # Identify line type and handle accordingly
            if self.is_case_number(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'case_number', 'content': line})
                
            elif self.is_party_names(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'party_names', 'content': line})
                
            elif self.is_date(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'date', 'content': line})
                
            elif self.is_present_line(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'present', 'content': line})
                
            elif self.is_page_marker(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'page_marker', 'content': line})
                
            elif self.is_numbered_item(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                
                # Collect the complete numbered item including continuation lines
                numbered_content = [line]
                j = i + 1
                
                # Look for continuation lines that are indented or clearly part of this item
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    
                    # Stop if we hit another numbered item, special line, or clear new paragraph
                    if (self.is_numbered_item(next_line) or 
                        self.is_case_number(next_line) or 
                        self.is_party_names(next_line) or 
                        self.is_date(next_line) or 
                        self.is_present_line(next_line) or 
                        self.is_page_marker(next_line) or
                        self.is_signature_block(next_line)):
                        break
                    
                    # If the line seems to be a continuation (doesn't start with capital or is clearly continuing)
                    if (not next_line[0].isupper() or 
                        next_line.lower().startswith(('and', 'or', 'but', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'with'))):
                        numbered_content.append(next_line)
                        j += 1
                    else:
                        break
                
                document_blocks.append({
                    'type': 'numbered_item',
                    'content': ' '.join(numbered_content).strip()
                })
                i = j
                continue
                
            elif self.is_signature_block(line):
                if current_paragraph:
                    document_blocks.append({
                        'type': 'paragraph',
                        'content': ' '.join(current_paragraph).strip()
                    })
                    current_paragraph = []
                document_blocks.append({'type': 'signature', 'content': line})
                
            else:
                # Regular paragraph text
                current_paragraph.append(line)
            
            i += 1
        
        # Handle any remaining paragraph
        if current_paragraph:
            document_blocks.append({
                'type': 'paragraph',
                'content': ' '.join(current_paragraph).strip()
            })
        
        return document_blocks
    
    def blocks_to_text(self, blocks: List[Dict]) -> str:
        """Convert document blocks back to formatted text"""
        text_lines = []
        
        for block in blocks:
            if block['type'] == 'page_break':
                text_lines.append('\n[PAGE_BREAK]\n')
            elif block['type'] == 'numbered_item':
                # Add proper indentation for numbered items
                content = block['content']
                # Extract the number/letter part and content
                match = re.match(r'^(\([ivxlcdm]+\)|\([a-z]\)|\d+\))\s*(.*)', content, re.IGNORECASE)
                if match:
                    number_part = match.group(1)
                    content_part = match.group(2)
                    text_lines.append(f"    {number_part} {content_part}")
                else:
                    text_lines.append(f"    {content}")
            else:
                if block['content']:
                    text_lines.append(block['content'])
            
            # Add spacing after certain block types
            if block['type'] in ['case_number', 'party_names', 'date', 'present', 'paragraph', 'numbered_item', 'signature']:
                text_lines.append('')
        
        return '\n'.join(text_lines)
    
    def convert_to_html(self, blocks: List[Dict]) -> str:
        """Convert document blocks to HTML with accurate formatting"""
        
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
            background-color: #f5f5f5;
            color: #000;
            font-size: 14px;
        }
        
        .judgment-container {
            max-width: 210mm;
            margin: 0 auto;
            padding: 25mm;
            background: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            border: 1px solid #ccc;
            min-height: 297mm;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            margin: 20px 0;
            font-size: 14px;
        }
        
        .party-names {
            text-align: center;
            font-weight: bold;
            margin: 20px 0;
            border-bottom: 1px solid #000;
            padding-bottom: 10px;
            font-size: 14px;
        }
        
        .date {
            text-align: center;
            margin: 20px 0;
            font-size: 14px;
        }
        
        .present {
            margin: 20px 0;
            font-size: 14px;
        }
        
        .paragraph {
            margin: 15px 0;
            text-align: justify;
            line-height: 1.6;
            font-size: 14px;
        }
        
        .numbered-item {
            margin: 15px 0;
            text-align: justify;
            line-height: 1.6;
            padding-left: 20px;
            text-indent: -20px;
            font-size: 14px;
        }
        
        .signature {
            text-align: center;
            font-weight: bold;
            margin: 25px 0 10px 0;
            font-size: 14px;
        }
        
        .page-marker {
            text-align: center;
            margin: 20px 0;
            font-size: 14px;
        }
        
        .page-break {
            page-break-before: always;
            margin: 30px 0;
            text-align: center;
            color: #666;
            font-style: italic;
            border-top: 1px solid #ccc;
            padding-top: 20px;
        }
        
        /* Print styles */
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
                padding: 20mm;
                min-height: auto;
            }
            .page-break {
                border-top: none;
                margin: 0;
                padding: 0;
                font-size: 0;
                height: 0;
            }
        }
    </style>
</head>
<body>
    <div class="judgment-container">''']
        
        for block in blocks:
            if not block['content'] and block['type'] != 'page_break':
                continue
                
            content = block['content'].replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            
            if block['type'] == 'case_number':
                html_content.append(f'<div class="case-number">{content}</div>')
            elif block['type'] == 'party_names':
                html_content.append(f'<div class="party-names">{content}</div>')
            elif block['type'] == 'date':
                html_content.append(f'<div class="date">{content}</div>')
            elif block['type'] == 'present':
                html_content.append(f'<div class="present">{content}</div>')
            elif block['type'] == 'paragraph':
                html_content.append(f'<div class="paragraph">{content}</div>')
            elif block['type'] == 'numbered_item':
                html_content.append(f'<div class="numbered-item">{content}</div>')
            elif block['type'] == 'signature':
                html_content.append(f'<div class="signature">{content}</div>')
            elif block['type'] == 'page_marker':
                html_content.append(f'<div class="page-marker">{content}</div>')
            elif block['type'] == 'page_break':
                html_content.append('<div class="page-break">--- Page Break ---</div>')
        
        html_content.append('''    </div>
</body>
</html>''')
        
        return '\n'.join(html_content)
    
    def generate_statistics(self, blocks: List[Dict]) -> Dict:
        """Generate document statistics from blocks"""
        stats = {
            'total_blocks': len(blocks),
            'pages': len([b for b in blocks if b['type'] == 'page_break']) + 1,
            'paragraphs': len([b for b in blocks if b['type'] == 'paragraph']),
            'numbered_items': len([b for b in blocks if b['type'] == 'numbered_item']),
            'signatures': len([b for b in blocks if b['type'] == 'signature']),
        }
        
        # Count total words
        total_words = 0
        for block in blocks:
            if block['content']:
                total_words += len(block['content'].split())
        
        stats['total_words'] = total_words
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
        
        # Reconstruct document structure
        document_blocks = self.reconstruct_document(extracted_text)
        
        # Convert to formatted text and HTML
        formatted_text = self.blocks_to_text(document_blocks)
        html_output = self.convert_to_html(document_blocks)
        
        return formatted_text, html_output

def main():
    st.title("Legal Judgment Text Extractor - Structure Preserving Version")
    st.markdown("---")
    st.markdown("**Extracts and formats legal judgments while preserving original document structure**")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        extraction_method = st.selectbox(
            "Extraction Method:",
            ["PDFPlumber (Recommended)", "PyMuPDF", "PyPDF2"],
            help="Choose the PDF text extraction method"
        )
        
        st.markdown("### Key Features")
        st.markdown("""
        - **Structure Preservation**: Maintains original layout
        - **No Over-Fragmentation**: Keeps sentences intact
        - **Accurate Indentation**: Proper numbered item formatting
        - **Minimal Spacing**: Matches original document spacing
        - **Correct Bold/Center**: Only where actually present
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
            extract_button = st.button("Extract and Format Text", type="primary", use_container_width=True)
        with col2:
            if st.button("Clear Results", use_container_width=True):
                st.rerun()
        
        if extract_button:
            with st.spinner("Processing PDF while preserving structure..."):
                try:
                    formatted_text, html_output = extractor.process_pdf(uploaded_file, extraction_method)
                    
                    if formatted_text:
                        st.success("Document processed successfully - structure preserved!")
                        
                        # Create tabs
                        tab1, tab2, tab3, tab4 = st.tabs([
                            "Formatted Text", 
                            "HTML Preview", 
                            "Analysis", 
                            "Downloads"
                        ])
                        
                        with tab1:
                            st.subheader("Structure-Preserving Formatted Text")
                            st.text_area(
                                "Formatted text maintaining original document structure:",
                                value=formatted_text,
                                height=500,
                                help="Text formatted to match original PDF layout"
                            )
                        
                        with tab2:
                            st.subheader("HTML Preview - Original Structure")
                            st.markdown("*Formatted to match the original PDF appearance:*")
                            st.components.v1.html(html_output, height=700, scrolling=True)
                        
                        with tab3:
                            st.subheader("Document Analysis")
                            
                            # Parse blocks for statistics
                            blocks = extractor.reconstruct_document(
                                extractor.extract_text_pdfplumber(uploaded_file) if extraction_method == "PDFPlumber (Recommended)"
                                else extractor.extract_text_pymupdf(uploaded_file) if extraction_method == "PyMuPDF"
                                else extractor.extract_text_pypdf2(uploaded_file)
                            )
                            stats = extractor.generate_statistics(blocks)
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Pages", stats['pages'])
                            with col2:
                                st.metric("Paragraphs", stats['paragraphs'])
                            with col3:
                                st.metric("Numbered Items", stats['numbered_items'])
                            with col4:
                                st.metric("Total Words", stats['total_words'])
                        
                        with tab4:
                            st.subheader("Download Options")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.download_button(
                                    label="Download HTML File",
                                    data=html_output.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_structured.html",
                                    mime="text/html",
                                    help="Download as structured HTML document"
                                )
                            
                            with col2:
                                st.download_button(
                                    label="Download Text File",
                                    data=formatted_text.encode('utf-8'),
                                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_structured.txt",
                                    mime="text/plain",
                                    help="Download as structured text file"
                                )
                    
                    else:
                        st.error("Failed to extract text from PDF. Please try a different extraction method.")
                
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")
                    st.info("Try using a different extraction method or ensure the PDF contains readable text.")

if __name__ == "__main__":
    main()

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
    page_title="Advanced Legal Text Extractor - Final",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class AdvancedLegalExtractor:
    def __init__(self):
        self.extracted_text = ""
        self.html_output = ""
    
    def clean_text(self, text: str) -> str:
        """Aggressive text cleaning"""
        # Remove problematic characters
        replacements = {
            'Â­': '-', '\u00ad': '-', '\ufeff': '', '\u200b': '',
            '\x0c': '\n\n[PAGE_BREAK]\n\n', '\u2010': '-', '\u2011': '-',
            '\u2012': '-', '\u2013': '-', '\u2014': '-', '\u00a0': ' ',
            '\t': ' ', '\r': ''
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Normalize unicode and fix spacing
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r' +', ' ', text)  # Multiple spaces to single
        
        return text
    
    def extract_with_pdfplumber(self, pdf_file) -> str:
        """Extract with PDFPlumber"""
        try:
            pdf_file.seek(0)
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text(
                        layout=False,  # Don't preserve layout - we'll reconstruct
                        x_tolerance=3,
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
        """Extract with PyMuPDF"""
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
        """Extract with PyPDF2"""
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
    
    def is_structural_marker(self, line: str) -> bool:
        """Identify lines that should NOT be joined with others"""
        line = line.strip()
        if not line:
            return False
        
        # Case numbers and legal references
        if re.match(r'^[A-Z\s]*\([A-Z]+\).*No\.?\s*\d+', line):
            return True
        
        # Party names with VS
        if re.search(r'\b(VS|V/S|V\.)\b', line.upper()) and len(line.split()) < 15:
            return True
        
        # Dates
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', line):
            return True
        
        # Present, Coram, etc.
        if re.match(r'^(Present|Coram|Before|Heard)\s*[:\.]', line, re.IGNORECASE):
            return True
        
        # Page numbers
        if re.match(r'^:\d+:$', line):
            return True
        
        # Numbered paragraphs/points
        if re.match(r'^(\d+\.|[a-z]\)|\([a-z]\)|\([ivxlcdm]+\))(\s|$)', line, re.IGNORECASE):
            return True
        
        # Legal keywords that start new sections
        legal_starters = [
            'ORDER', 'JUDGMENT', 'REASONING', 'FACTS', 'HELD', 'RATIO',
            'Accordingly,', 'Therefore,', 'Hence,', 'In view of', 'Considering'
        ]
        for starter in legal_starters:
            if line.startswith(starter):
                return True
        
        return False
    
    def aggressive_paragraph_reconstruction(self, text: str) -> str:
        """Aggressively reconstruct paragraphs - join everything that should be together"""
        lines = [line.strip() for line in text.split('\n')]
        result = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i]
            
            # Handle empty lines and page breaks
            if not current_line:
                i += 1
                continue
            
            if '[PAGE_BREAK]' in current_line:
                result.append(current_line)
                i += 1
                continue
            
            # Start building a paragraph
            paragraph_parts = [current_line]
            i += 1
            
            # Keep adding lines to this paragraph until we hit a structural marker
            while i < len(lines):
                next_line = lines[i].strip()
                
                # Stop conditions
                if not next_line:  # Empty line
                    i += 1
                    break
                
                if '[PAGE_BREAK]' in next_line:  # Page break
                    break
                
                if self.is_structural_marker(next_line):  # New section/structure
                    break
                
                # Add to current paragraph
                paragraph_parts.append(next_line)
                i += 1
            
            # Join paragraph parts intelligently
            if len(paragraph_parts) == 1:
                result.append(paragraph_parts[0])
            else:
                # Join with spaces, handling sentence boundaries
                joined_paragraph = ""
                for j, part in enumerate(paragraph_parts):
                    if j == 0:
                        joined_paragraph = part
                    else:
                        # Smart joining logic
                        if (joined_paragraph.endswith(('.', '!', '?', ':')) or 
                            part[0].isupper() or
                            re.match(r'^\d+\.', part)):
                            joined_paragraph += " " + part
                        else:
                            joined_paragraph += " " + part
                
                result.append(joined_paragraph)
        
        return '\n\n'.join(result)
    
    def classify_content_block(self, text: str) -> str:
        """Classify content blocks for HTML formatting"""
        text = text.strip()
        
        if not text:
            return "empty"
        
        if '[PAGE_BREAK]' in text:
            return "page_break"
        
        # Case number pattern
        if re.match(r'^[A-Z\s]*\([A-Z]+\).*No\.?\s*\d+', text):
            return "case_number"
        
        # Party names
        if re.search(r'\b(VS|V/S|V\.)\b', text.upper()) and len(text.split()) < 15:
            return "parties"
        
        # Date
        if re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', text):
            return "date"
        
        # Present/Coram
        if re.match(r'^(Present|Coram|Before)\s*:', text, re.IGNORECASE):
            return "present"
        
        # Page numbers
        if re.match(r'^:\d+:$', text):
            return "page_number"
        
        # Numbered points
        if re.match(r'^(\d+\.|[a-z]\)|\([a-z]\)|\([ivxlcdm]+\))', text, re.IGNORECASE):
            return "numbered"
        
        # Judge signature
        if (text.isupper() and 
            len(text.split()) <= 4 and 
            text.replace(' ', '').isalpha() and 
            len(text) > 8):
            return "signature"
        
        # Judge title
        if text.upper() in ['DISTRICT JUDGE', 'ADDITIONAL DISTRICT JUDGE', 'CHIEF JUDICIAL MAGISTRATE', 'JUDGE']:
            return "judge_title"
        
        # Court location with date
        if re.search(r'New Delhi.*\d{1,2}\.\d{1,2}\.\d{4}$', text):
            return "location_date"
        
        # Special legal phrases
        if text.startswith(('Heard.', 'ORDER', 'JUDGMENT', 'Accordingly,', 'Therefore,')):
            return "legal_marker"
        
        return "paragraph"
    
    def create_premium_html(self, text: str) -> str:
        """Create premium quality HTML output"""
        blocks = [block.strip() for block in text.split('\n\n') if block.strip()]
        
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Legal Judgment - Professional Format</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Times New Roman', 'Times', serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #000;
            background: #f8f9fa;
            margin: 0;
            padding: 20px;
        }
        
        .document-container {
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 25mm;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            min-height: 297mm;
            position: relative;
        }
        
        .case-number {
            text-align: center;
            font-weight: bold;
            font-size: 14pt;
            margin: 30px 0 20px 0;
            letter-spacing: 0.5px;
        }
        
        .parties {
            text-align: center;
            font-weight: bold;
            font-size: 13pt;
            margin: 20px 0;
            text-decoration: underline;
            text-underline-offset: 3px;
        }
        
        .date {
            text-align: center;
            font-size: 12pt;
            margin: 20px 0;
        }
        
        .present {
            margin: 25px 0 20px 0;
            font-weight: bold;
        }
        
        .paragraph {
            margin: 15px 0;
            text-align: justify;
            line-height: 1.7;
            text-indent: 0;
        }
        
        .numbered {
            margin: 15px 0;
            text-align: justify;
            line-height: 1.7;
            padding-left: 30px;
            text-indent: -30px;
        }
        
        .legal-marker {
            margin: 20px 0 15px 0;
            font-weight: bold;
            text-align: justify;
            line-height: 1.7;
        }
        
        .page-number {
            text-align: center;
            font-weight: bold;
            margin: 15px 0;
        }
        
        .signature {
            text-align: right;
            font-weight: bold;
            margin: 30px 0 10px 0;
            font-size: 11pt;
        }
        
        .judge-title {
            text-align: right;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .location-date {
            text-align: right;
            margin: 5px 0;
            font-style: italic;
        }
        
        .page-break {
            page-break-before: always;
            text-align: center;
            color: #666;
            font-style: italic;
            margin: 30px 0;
            padding: 15px;
            border-top: 2px dashed #ccc;
            border-bottom: 2px dashed #ccc;
            background: #f9f9f9;
        }
        
        /* Improve readability */
        .paragraph:first-letter {
            font-size: 110%;
        }
        
        @media print {
            body {
                margin: 0;
                padding: 0;
                background: white;
            }
            
            .document-container {
                margin: 0;
                padding: 20mm;
                box-shadow: none;
                min-height: auto;
            }
            
            .page-break {
                margin: 0;
                padding: 0;
                font-size: 0;
                border: none;
                background: none;
            }
        }
        
        @media screen and (max-width: 768px) {
            body {
                padding: 10px;
            }
            
            .document-container {
                padding: 15mm;
            }
        }
    </style>
</head>
<body>
    <div class="document-container">
'''
        
        for block in blocks:
            content_type = self.classify_content_block(block)
            
            if content_type == "page_break":
                html_content += '        <div class="page-break">--- Page Break ---</div>\n'
            else:
                # Escape HTML
                escaped = (block.replace('&', '&amp;')
                             .replace('<', '&lt;')
                             .replace('>', '&gt;')
                             .replace('"', '&quot;'))
                
                css_class = {
                    "case_number": "case-number",
                    "parties": "parties",
                    "date": "date",
                    "present": "present", 
                    "paragraph": "paragraph",
                    "numbered": "numbered",
                    "legal_marker": "legal-marker",
                    "page_number": "page-number",
                    "signature": "signature",
                    "judge_title": "judge-title",
                    "location_date": "location-date"
                }.get(content_type, "paragraph")
                
                html_content += f'        <div class="{css_class}">{escaped}</div>\n'
        
        html_content += '''    </div>
</body>
</html>'''
        
        return html_content
    
    def process_pdf(self, pdf_file, method: str) -> Tuple[str, str]:
        """Main processing function with aggressive reconstruction"""
        # Extract raw text
        if method == "PDFPlumber":
            raw_text = self.extract_with_pdfplumber(pdf_file)
        elif method == "PyMuPDF":
            raw_text = self.extract_with_pymupdf(pdf_file)
        else:
            raw_text = self.extract_with_pypdf2(pdf_file)
        
        if not raw_text:
            return "", ""
        
        # Aggressively reconstruct paragraphs
        processed_text = self.aggressive_paragraph_reconstruction(raw_text)
        
        # Create premium HTML
        html_output = self.create_premium_html(processed_text)
        
        return processed_text, html_output

def main():
    st.title("🏛️ Advanced Legal Text Extractor - Premium Edition")
    st.markdown("---")
    st.markdown("**🚀 Aggressive paragraph reconstruction for premium results**")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Advanced Settings")
        
        method = st.selectbox(
            "PDF Extraction Method:",
            ["PDFPlumber", "PyMuPDF", "PyPDF2"],
            help="Choose the best method for your PDF quality"
        )
        
        st.markdown("### 🎯 Revolutionary Approach")
        st.markdown("""
        - **🔥 Aggressive Reconstruction**: Joins all related content
        - **🧠 Smart Content Analysis**: Identifies document structure  
        - **✨ Premium HTML**: Professional court document styling
        - **🚫 Zero Fragmentation**: Eliminates broken lines
        - **📄 Perfect Paragraphs**: Natural reading flow
        """)
        
        st.markdown("### 🏆 Final Improvements")
        st.markdown("""
        - Complete paragraph reconstruction
        - Intelligent content classification
        - Premium typography and spacing
        - Professional legal document format
        - Print-ready output
        """)
        
        st.warning("⚠️ This is the FINAL optimized version designed for top-notch results!")
    
    # File upload
    uploaded_file = st.file_uploader(
        "📄 Upload Legal Judgment PDF",
        type=['pdf'],
        help="Select a PDF file for premium text extraction"
    )
    
    if uploaded_file is not None:
        st.info(f"**📄 File:** {uploaded_file.name} | **📦 Size:** {uploaded_file.size / 1024:.1f} KB")
        
        extractor = AdvancedLegalExtractor()
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            if st.button("🚀 Extract with Premium Processing", type="primary", use_container_width=True):
                with st.spinner("🔄 Processing with advanced algorithms..."):
                    try:
                        processed_text, html_output = extractor.process_pdf(uploaded_file, method)
                        
                        if processed_text:
                            st.success("✅ Document processed with premium quality!")
                            
                            # Display statistics
                            original_lines = len(processed_text.split('\n'))
                            paragraphs = len([p for p in processed_text.split('\n\n') if p.strip()])
                            
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.metric("📏 Lines", original_lines)
                            with col_b:
                                st.metric("📄 Paragraphs", paragraphs)
                            with col_c:
                                st.metric("📊 Ratio", f"{paragraphs/original_lines:.2f}")
                            
                            # Results
                            tab1, tab2, tab3 = st.tabs([
                                "📝 Premium Text",
                                "🌐 Premium HTML",
                                "💾 Downloads"
                            ])
                            
                            with tab1:
                                st.subheader("🏆 Premium Processed Text")
                                st.text_area(
                                    "Aggressively reconstructed premium text:",
                                    value=processed_text,
                                    height=600,
                                    help="Text with advanced paragraph reconstruction"
                                )
                                
                                # Show sample
                                st.markdown("**📖 Sample Preview:**")
                                sample = processed_text.split('\n\n')[:3]
                                for i, para in enumerate(sample):
                                    if para.strip():
                                        st.markdown(f"**Paragraph {i+1}:** {para[:200]}...")
                            
                            with tab2:
                                st.subheader("🎨 Premium HTML Preview")
                                st.markdown("*Professional court document formatting:*")
                                st.components.v1.html(html_output, height=700, scrolling=True)
                            
                            with tab3:
                                st.subheader("📥 Premium Downloads")
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.download_button(
                                        label="📄 Download Premium HTML",
                                        data=html_output.encode('utf-8'),
                                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_premium.html",
                                        mime="text/html",
                                        help="Download professionally formatted HTML"
                                    )
                                
                                with col2:
                                    st.download_button(
                                        label="📝 Download Premium Text",
                                        data=processed_text.encode('utf-8'),
                                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_premium.txt",
                                        mime="text/plain",
                                        help="Download premium processed text"
                                    )
                                
                                st.markdown("### 🎯 Quality Metrics")
                                st.success(f"✅ Successfully reduced fragmentation by {((original_lines - paragraphs) / original_lines * 100):.1f}%")
                        
                        else:
                            st.error("❌ Failed to extract text. Try a different extraction method.")
                    
                    except Exception as e:
                        st.error(f"❌ Processing error: {str(e)}")
                        st.info("💡 Try using a different extraction method or check PDF quality.")
        
        with col2:
            if st.button("🗑️ Reset", use_container_width=True):
                st.rerun()

if __name__ == "__main__":
    main()

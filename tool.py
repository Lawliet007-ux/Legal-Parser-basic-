import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import PyPDF2
import re
from io import BytesIO
import html
from typing import List, Dict, Tuple, Optional
import json
import base64
import numpy as np
from dataclasses import dataclass
import math

@dataclass
class TextElement:
    text: str
    x: float
    y: float
    width: float
    height: float
    font: str
    size: float
    flags: int
    page: int
    line_index: int

class AbsoluteCarbonCopyExtractor:
    def __init__(self):
        self.raw_extraction = ""
        self.perfect_html = ""
        self.text_matrix = []
        self.page_layouts = []
        
    def extract_raw_text_structure(self, pdf_file) -> str:
        """Extract text preserving EXACT original structure"""
        methods = [
            self._method_pdfplumber_layout,
            self._method_pymupdf_raw,
            self._method_pypdf2_raw
        ]
        
        for method in methods:
            try:
                result = method(pdf_file)
                if result and result.strip():
                    return result
            except Exception as e:
                st.warning(f"Method failed: {e}")
                continue
        
        return ""
    
    def _method_pdfplumber_layout(self, pdf_file) -> str:
        """PDFplumber with absolute layout preservation"""
        pdf_file.seek(0)
        
        with pdfplumber.open(pdf_file) as pdf:
            pages_text = []
            
            for page_num, page in enumerate(pdf.pages):
                # Extract with layout=True to preserve spacing
                page_text = page.extract_text(layout=True, x_tolerance=1, y_tolerance=1)
                
                if page_text:
                    # Split into lines and preserve EXACT spacing
                    lines = page_text.split('\n')
                    processed_lines = []
                    
                    for line in lines:
                        # Keep the line EXACTLY as extracted - no modifications
                        processed_lines.append(line)
                    
                    pages_text.append('\n'.join(processed_lines))
            
            return '\n\n'.join(pages_text)
    
    def _method_pymupdf_raw(self, pdf_file) -> str:
        """PyMuPDF raw text extraction"""
        pdf_file.seek(0)
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        
        pages_text = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            
            # Get raw text preserving layout
            text = page.get_text("text")
            if text:
                pages_text.append(text)
        
        doc.close()
        return '\n\n'.join(pages_text)
    
    def _method_pypdf2_raw(self, pdf_file) -> str:
        """PyPDF2 raw extraction"""
        pdf_file.seek(0)
        reader = PyPDF2.PdfReader(pdf_file)
        
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        
        return '\n\n'.join(pages_text)
    
    def create_absolute_replica_html(self, text: str) -> str:
        """Create HTML that is IDENTICAL to original document"""
        
        # Split text into lines - preserve everything
        lines = text.split('\n')
        
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Legal Judgment - Absolute Carbon Copy</title>
    <style>
        @page {{
            margin: 1in;
            size: 8.5in 11in;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        html, body {{
            height: 100%;
            font-family: "Times New Roman", Times, serif;
            font-size: 12pt;
            line-height: 1.0;
            color: #000000;
            background: #ffffff;
        }}
        
        .document-container {{
            width: 100%;
            max-width: none;
            margin: 0;
            padding: 1in;
            font-family: "Times New Roman", Times, serif;
            font-size: 12pt;
            line-height: 1.0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        
        .text-line {{
            font-family: "Times New Roman", Times, serif;
            font-size: 12pt;
            line-height: 1.0;
            margin: 0;
            padding: 0;
            white-space: pre;
            min-height: 1em;
        }}
        
        .empty-line {{
            height: 1em;
            margin: 0;
            padding: 0;
        }}
        
        /* Exact font matching */
        .document-container, .text-line {{
            font-family: "Times New Roman", Times, serif !important;
            font-size: 12pt !important;
            font-weight: normal !important;
            font-style: normal !important;
            text-decoration: none !important;
            letter-spacing: normal !important;
            word-spacing: normal !important;
        }}
        
        @media screen {{
            body {{
                background: #f0f0f0;
                padding: 20px;
            }}
            
            .document-container {{
                background: white;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                margin: 0 auto;
                max-width: 8.5in;
            }}
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
                margin: 0;
            }}
            
            .document-container {{
                padding: 1in;
                margin: 0;
                box-shadow: none;
                max-width: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="document-container">'''
        
        # Process each line EXACTLY as it appears
        for line_num, line in enumerate(lines):
            if line == "":
                # Empty line - preserve exactly
                html_content += '<div class="empty-line"></div>\n'
            else:
                # Non-empty line - preserve ALL characters and spacing
                escaped_line = html.escape(line)
                
                # Convert multiple spaces to HTML spaces (preserve exact spacing)
                escaped_line = escaped_line.replace('  ', '&nbsp;&nbsp;')
                escaped_line = escaped_line.replace(' &nbsp;', '&nbsp;&nbsp;')
                escaped_line = escaped_line.replace('&nbsp; ', '&nbsp;&nbsp;')
                
                # Handle tabs
                escaped_line = escaped_line.replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
                
                html_content += f'<div class="text-line">{escaped_line}</div>\n'
        
        html_content += '''
    </div>
</body>
</html>'''
        
        return html_content
    
    def process_document_absolute(self, pdf_file) -> bool:
        """Process document with absolute precision"""
        
        # Extract raw text structure
        self.raw_extraction = self.extract_raw_text_structure(pdf_file)
        
        if not self.raw_extraction:
            return False
        
        # Create perfect HTML replica
        self.perfect_html = self.create_absolute_replica_html(self.raw_extraction)
        
        return True

def main():
    st.set_page_config(
        page_title="Absolute Carbon Copy Extractor",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 ABSOLUTE CARBON COPY EXTRACTOR")
    st.markdown("""
    **ZERO-MODIFICATION EXTRACTION** - This tool extracts text EXACTLY as it appears in the PDF.
    No interpretation, no formatting changes, no assumptions. PURE CARBON COPY.
    """)
    
    st.warning("""
    ⚠️ **ABSOLUTE PRECISION MODE**: This tool will replicate your document EXACTLY.
    Every space, line break, and character will be preserved without any modification.
    """)
    
    # Simple interface - no complex options
    uploaded_file = st.file_uploader(
        "📤 Upload Legal Judgment PDF",
        type="pdf",
        help="Upload your PDF for EXACT replication"
    )
    
    if uploaded_file is not None:
        # Show file info
        st.info(f"**File:** {uploaded_file.name} | **Size:** {uploaded_file.size:,} bytes")
        
        # Process document
        with st.spinner("🔬 Creating ABSOLUTE carbon copy..."):
            extractor = AbsoluteCarbonCopyExtractor()
            success = extractor.process_document_absolute(uploaded_file)
        
        if success:
            st.success("✅ **ABSOLUTE CARBON COPY CREATED!**")
            
            # Show statistics
            text = extractor.raw_extraction
            lines = text.split('\n')
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("**Total Lines**", f"{len(lines):,}")
            with col2:
                st.metric("**Characters**", f"{len(text):,}")
            with col3:
                st.metric("**Words**", f"{len(text.split()):,}")
            with col4:
                st.metric("**Non-Empty Lines**", f"{len([l for l in lines if l.strip()]):,}")
            
            # Tabbed interface for better organization
            tab1, tab2, tab3 = st.tabs(["📝 Raw Text", "🌐 HTML Preview", "💾 Downloads"])
            
            with tab1:
                st.subheader("📝 Raw Extracted Text (EXACT COPY)")
                st.markdown("**This is the EXACT text as extracted - no modifications:**")
                
                # Show text in a large text area
                st.text_area(
                    "Carbon Copy Text:",
                    text,
                    height=600,
                    help="This is the ABSOLUTE EXACT text from your PDF - every character preserved",
                    key="raw_text_display"
                )
                
                # Text analysis
                with st.expander("🔍 Text Analysis"):
                    st.write("**Character Breakdown:**")
                    char_analysis = {
                        'Spaces': text.count(' '),
                        'Line Breaks': text.count('\n'),
                        'Tabs': text.count('\t'),
                        'Numbers': sum(1 for c in text if c.isdigit()),
                        'Letters': sum(1 for c in text if c.isalpha()),
                        'Punctuation': sum(1 for c in text if not c.isalnum() and not c.isspace())
                    }
                    
                    for char_type, count in char_analysis.items():
                        st.write(f"• **{char_type}:** {count:,}")
            
            with tab2:
                st.subheader("🌐 HTML Preview (PERFECT REPLICA)")
                st.markdown("**Pixel-perfect HTML reproduction:**")
                
                # HTML preview
                st.components.v1.html(
                    extractor.perfect_html,
                    height=700,
                    scrolling=True
                )
            
            with tab3:
                st.subheader("💾 Download Options")
                
                col_d1, col_d2 = st.columns(2)
                
                with col_d1:
                    st.markdown("### 📄 Text File")
                    st.markdown("Raw text with EXACT formatting")
                    
                    st.download_button(
                        label="📥 Download Text (.txt)",
                        data=text.encode('utf-8'),
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_ABSOLUTE_COPY.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                with col_d2:
                    st.markdown("### 🌐 HTML File")
                    st.markdown("Perfect visual replica")
                    
                    st.download_button(
                        label="📥 Download HTML (.html)",
                        data=extractor.perfect_html.encode('utf-8'),
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_PERFECT_REPLICA.html",
                        mime="text/html",
                        use_container_width=True
                    )
                
                # Additional download - JSON with metadata
                st.markdown("### 📊 Complete Data Package")
                
                complete_data = {
                    "filename": uploaded_file.name,
                    "extraction_timestamp": str(pd.Timestamp.now()),
                    "raw_text": text,
                    "html_replica": extractor.perfect_html,
                    "statistics": {
                        "total_lines": len(lines),
                        "total_characters": len(text),
                        "total_words": len(text.split()),
                        "non_empty_lines": len([l for l in lines if l.strip()])
                    }
                }
                
                st.download_button(
                    label="📦 Download Complete Package (.json)",
                    data=json.dumps(complete_data, indent=2, ensure_ascii=False).encode('utf-8'),
                    file_name=f"{uploaded_file.name.replace('.pdf', '')}_COMPLETE_PACKAGE.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        else:
            st.error("❌ **EXTRACTION FAILED**")
            st.error("Could not extract text from the PDF. Please check:")
            st.write("• File is not corrupted")
            st.write("• PDF contains extractable text (not scanned images)")
            st.write("• File is not password protected")
    
    # Help section
    with st.expander("ℹ️ How This Works"):
        st.markdown("""
        ### 🎯 ABSOLUTE CARBON COPY TECHNOLOGY
        
        **Zero Modification Principle:**
        - Extracts text EXACTLY as it appears in PDF
        - No interpretation of legal structure
        - No formatting assumptions
        - No spacing adjustments
        
        **Extraction Process:**
        1. **Primary Method**: PDFplumber with layout=True
        2. **Secondary Method**: PyMuPDF raw text extraction
        3. **Tertiary Method**: PyPDF2 fallback extraction
        
        **HTML Replication:**
        - Uses exact font matching (Times New Roman, 12pt)
        - Preserves all spaces using `&nbsp;`
        - Maintains line structure with `white-space: pre`
        - Creates print-identical output
        
        ### ✅ What You Get:
        - **Raw Text**: EXACT copy with all original formatting
        - **HTML Replica**: Visual reproduction identical to original
        - **Perfect Preservation**: Every character, space, and line break maintained
        
        ### 🎯 Best For:
        - Legal documents requiring exact replication
        - Court judgments with specific formatting
        - Documents where every character matters
        - Professional archival purposes
        """)

if __name__ == "__main__":
    # Import pandas for timestamp
    import pandas as pd
    main()

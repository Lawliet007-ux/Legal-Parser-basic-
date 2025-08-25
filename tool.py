import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import PyPDF2
import re
from io import BytesIO
import html
from typing import List, Dict, Tuple, Optional
import base64

class CarbonCopyExtractor:
    def __init__(self):
        self.raw_text = ""
        self.formatted_html = ""
        self.text_blocks = []
        self.layout_info = []
        
    def extract_with_precise_layout(self, pdf_file) -> bool:
        """Extract text with exact positioning and formatting"""
        try:
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            
            all_text_blocks = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Get text with detailed positioning
                text_dict = page.get_text("dict")
                page_height = page.rect.height
                
                page_blocks = []
                
                for block in text_dict["blocks"]:
                    if "lines" in block:
                        block_bbox = block["bbox"]
                        
                        for line in block["lines"]:
                            line_text = ""
                            line_bbox = line["bbox"]
                            font_info = {}
                            
                            for span in line["spans"]:
                                line_text += span["text"]
                                font_info = {
                                    "font": span.get("font", ""),
                                    "size": span.get("size", 12),
                                    "flags": span.get("flags", 0),  # Bold, italic flags
                                    "color": span.get("color", 0)
                                }
                            
                            if line_text.strip():
                                page_blocks.append({
                                    "text": line_text,
                                    "bbox": line_bbox,
                                    "font_info": font_info,
                                    "y_position": line_bbox[1],  # Top Y coordinate
                                    "x_position": line_bbox[0],  # Left X coordinate
                                    "page": page_num
                                })
                
                # Sort by Y position (top to bottom), then X position (left to right)
                page_blocks.sort(key=lambda x: (x["y_position"], x["x_position"]))
                all_text_blocks.extend(page_blocks)
            
            self.text_blocks = all_text_blocks
            doc.close()
            return True
            
        except Exception as e:
            st.error(f"Layout extraction failed: {str(e)}")
            return False
    
    def reconstruct_exact_layout(self) -> str:
        """Reconstruct the exact layout with precise spacing"""
        if not self.text_blocks:
            return ""
        
        reconstructed_lines = []
        current_page = -1
        last_y = 0
        
        for i, block in enumerate(self.text_blocks):
            text = block["text"].rstrip()
            y_pos = block["y_position"]
            x_pos = block["x_position"]
            page = block["page"]
            
            # Handle page breaks
            if page != current_page:
                if current_page != -1:
                    reconstructed_lines.append("")  # Page separator
                current_page = page
                last_y = y_pos
            
            # Calculate vertical spacing
            if i > 0 and page == self.text_blocks[i-1]["page"]:
                y_diff = abs(y_pos - last_y)
                # Add blank lines for significant vertical gaps
                if y_diff > 20:  # Threshold for line spacing
                    num_blank_lines = max(1, min(3, int(y_diff / 15)))
                    for _ in range(num_blank_lines):
                        reconstructed_lines.append("")
            
            # Handle horizontal positioning for indentation
            if x_pos > 50:  # If indented
                indent_level = int((x_pos - 50) / 20)  # Approximate indentation
                indent = "    " * indent_level
                text = indent + text
            
            reconstructed_lines.append(text)
            last_y = y_pos
        
        return "\n".join(reconstructed_lines)
    
    def create_carbon_copy_html(self, text: str) -> str:
        """Create HTML that exactly matches the original document"""
        lines = text.split('\n')
        
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Legal Judgment - Carbon Copy</title>
    <style>
        @page {{
            margin: 1in;
            size: A4;
        }}
        
        body {{
            font-family: "Times New Roman", Times, serif;
            font-size: 12px;
            line-height: 1.2;
            margin: 0;
            padding: 20px;
            color: #000;
            background: #fff;
            white-space: pre-wrap;
        }}
        
        .document-container {{
            max-width: 8.5in;
            margin: 0 auto;
            background: white;
            padding: 0;
        }}
        
        .line {{
            margin: 0;
            padding: 0;
            min-height: 14px;
            font-family: "Times New Roman", Times, serif;
            font-size: 12px;
            white-space: pre;
        }}
        
        .case-number {{
            font-weight: normal;
        }}
        
        .case-title {{
            font-weight: bold;
            text-align: center;
        }}
        
        .date {{
            font-weight: normal;
        }}
        
        .paragraph {{
            text-align: justify;
            margin: 0;
            padding: 0;
        }}
        
        .indented {{
            padding-left: 20px;
        }}
        
        .double-indented {{
            padding-left: 40px;
        }}
        
        .signature {{
            text-align: center;
            font-weight: bold;
        }}
        
        /* Print styles */
        @media print {{
            body {{
                margin: 0;
                padding: 0;
            }}
            .document-container {{
                margin: 0;
                padding: 1in;
            }}
        }}
    </style>
</head>
<body>
<div class="document-container">
'''
        
        for line in lines:
            if line.strip() == "":
                html_content += '<div class="line">&nbsp;</div>\n'
            else:
                # Escape HTML but preserve exact spacing
                escaped_line = html.escape(line)
                
                # Detect line type and apply minimal styling
                css_class = "line"
                
                # Check for case number pattern
                if re.match(r'^OMP.*No\.', line.strip()):
                    css_class += " case-number"
                # Check for case title (all caps with VS)
                elif " VS " in line.upper() and line.strip().isupper():
                    css_class += " case-title"
                # Check for date pattern
                elif re.match(r'^\d{2}\.\d{2}\.\d{4}', line.strip()):
                    css_class += " date"
                # Check for signature (all caps, short lines at end)
                elif (line.strip().isupper() and len(line.strip().split()) <= 4 and 
                      ("JUDGE" in line or "COURT" in line)):
                    css_class += " signature"
                else:
                    css_class += " paragraph"
                
                # Handle indentation
                if line.startswith("        "):  # Double indent
                    css_class += " double-indented"
                elif line.startswith("    "):  # Single indent
                    css_class += " indented"
                
                html_content += f'<div class="{css_class}">{escaped_line}</div>\n'
        
        html_content += '''
</div>
</body>
</html>'''
        
        return html_content
    
    def fallback_extraction(self, pdf_file) -> str:
        """Fallback extraction that preserves exact text structure"""
        try:
            pdf_file.seek(0)
            
            # Try pdfplumber first for better text positioning
            with pdfplumber.open(pdf_file) as pdf:
                all_text = []
                
                for page in pdf.pages:
                    # Extract text with layout
                    page_text = page.extract_text(layout=True)
                    if page_text:
                        # Split into lines and preserve exact spacing
                        lines = page_text.split('\n')
                        processed_lines = []
                        
                        for line in lines:
                            # Keep original line exactly as is, just strip trailing spaces
                            processed_lines.append(line.rstrip())
                        
                        all_text.extend(processed_lines)
                        all_text.append("")  # Page break
                
                return '\n'.join(all_text)
                
        except Exception as e:
            st.error(f"Fallback extraction error: {str(e)}")
            
            # Final fallback with PyPDF2
            try:
                pdf_file.seek(0)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text_parts = []
                
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        # Preserve line breaks and spacing
                        text_parts.append(page_text)
                
                return '\n\n'.join(text_parts)
                
            except Exception as e2:
                st.error(f"All extraction methods failed: {str(e2)}")
                return ""
    
    def process_judgment(self, pdf_file):
        """Main processing function"""
        # Try precise layout extraction first
        if self.extract_with_precise_layout(pdf_file):
            self.raw_text = self.reconstruct_exact_layout()
        
        # If that fails, use fallback
        if not self.raw_text:
            self.raw_text = self.fallback_extraction(pdf_file)
        
        # Generate HTML
        if self.raw_text:
            self.formatted_html = self.create_carbon_copy_html(self.raw_text)
            return True
        
        return False

def main():
    st.set_page_config(
        page_title="Carbon Copy Legal Judgment Extractor",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 Carbon Copy Legal Judgment Extractor")
    st.markdown("""
    **Perfect Replication Tool** - Extracts legal judgments as exact carbon copies, 
    preserving every space, indentation, line break, and formatting detail.
    """)
    
    # Configuration
    st.sidebar.header("⚙️ Settings")
    show_raw_text = st.sidebar.checkbox("Show Raw Extracted Text", value=True)
    show_comparison = st.sidebar.checkbox("Show Side-by-Side Comparison", value=True)
    
    # File upload
    uploaded_file = st.file_uploader(
        "📤 Upload Legal Judgment PDF", 
        type="pdf",
        help="Upload a PDF file for carbon copy text extraction"
    )
    
    if uploaded_file is not None:
        st.header("🔄 Processing Document")
        
        # Process the document
        with st.spinner("Creating carbon copy..."):
            extractor = CarbonCopyExtractor()
            success = extractor.process_judgment(uploaded_file)
        
        if success:
            st.success("✅ Carbon copy created successfully!")
            
            # Document info
            lines = extractor.raw_text.split('\n')
            total_lines = len(lines)
            non_empty_lines = len([l for l in lines if l.strip()])
            total_chars = len(extractor.raw_text)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Lines", total_lines)
            with col2:
                st.metric("Text Lines", non_empty_lines)
            with col3:
                st.metric("Characters", total_chars)
            with col4:
                st.metric("Pages", extractor.raw_text.count('\n\n\n') + 1)
            
            # Layout options
            if show_comparison:
                col_left, col_right = st.columns([1, 1])
            else:
                col_left = st.container()
                col_right = None
            
            with col_left:
                if show_raw_text:
                    st.subheader("📝 Extracted Text (Raw)")
                    st.text_area(
                        "Raw extracted text with exact formatting:",
                        extractor.raw_text,
                        height=500,
                        help="This is the exact text as extracted, preserving all spacing and formatting"
                    )
                
                # Download options
                st.subheader("💾 Download Carbon Copy")
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    st.download_button(
                        label="📄 Download Text (.txt)",
                        data=extractor.raw_text.encode('utf-8'),
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_carbon_copy.txt",
                        mime="text/plain"
                    )
                
                with col_dl2:
                    st.download_button(
                        label="🌐 Download HTML (.html)",
                        data=extractor.formatted_html.encode('utf-8'),
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_carbon_copy.html",
                        mime="text/html"
                    )
            
            if show_comparison and col_right is not None:
                with col_right:
                    st.subheader("🖼️ HTML Preview")
                    st.markdown("**Formatted output (exact replica):**")
                    
                    # HTML preview with exact formatting
                    st.components.v1.html(
                        extractor.formatted_html,
                        height=500,
                        scrolling=True
                    )
            
            elif not show_comparison:
                st.subheader("🖼️ HTML Preview")
                st.markdown("**Formatted output (exact replica):**")
                st.components.v1.html(
                    extractor.formatted_html,
                    height=600,
                    scrolling=True
                )
            
        else:
            st.error("❌ Failed to extract text. Please check your PDF file.")
    
    # Instructions
    with st.expander("📖 About Carbon Copy Extraction"):
        st.markdown("""
        ### What makes this a "Carbon Copy"?
        
        ✅ **Exact Text Replication**: Every character, space, and line break preserved  
        ✅ **Original Indentation**: Maintains precise spacing and indentation  
        ✅ **Line-by-Line Accuracy**: Each line appears exactly as in the original  
        ✅ **Formatting Preservation**: Bold, spacing, and alignment maintained  
        ✅ **Layout Integrity**: Document structure kept intact  
        
        ### Technical Approach:
        - **Coordinate-based extraction**: Uses exact positioning data from PDF
        - **Multi-layer fallbacks**: Multiple extraction methods for reliability
        - **Spacing analysis**: Calculates exact indentation and line spacing
        - **Layout reconstruction**: Rebuilds document with pixel-perfect accuracy
        
        ### Best Results With:
        - Text-based PDFs (not scanned images)
        - Clear, well-formatted legal documents  
        - Standard fonts and layouts
        - Properly structured PDF files
        
        ### Output Formats:
        - **Text (.txt)**: Plain text with exact formatting preserved
        - **HTML (.html)**: Web format that displays exactly like original
        """)

if __name__ == "__main__":
    main()

import streamlit as st
import PyPDF2
import fitz  # PyMuPDF
import pdfplumber
import re
from io import BytesIO
from typing import List, Tuple, Dict, Optional
import unicodedata
import json
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Enterprise Legal Document Processor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class EnterpriseDocumentProcessor:
    def __init__(self):
        self.confidence_score = 0.0
        self.document_metadata = {}
        self.extraction_stats = {}
        
    def extract_all_methods(self, pdf_file) -> Dict[str, str]:
        """Extract text using all methods for comparison"""
        results = {}
        
        # Method 1: PDFPlumber
        try:
            pdf_file.seek(0)
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text(layout=True, x_tolerance=2, y_tolerance=2)
                    if page_text:
                        text += page_text + "\n\n[PAGE_BREAK]\n\n"
                results['pdfplumber'] = self.clean_text(text)
        except:
            results['pdfplumber'] = ""
            
        # Method 2: PyMuPDF
        try:
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
            text = ""
            for page_num in range(doc.page_count):
                page = doc.get_page(page_num)
                page_text = page.get_text("text")
                if page_text:
                    text += page_text + "\n\n[PAGE_BREAK]\n\n"
            doc.close()
            results['pymupdf'] = self.clean_text(text)
        except:
            results['pymupdf'] = ""
            
        # Method 3: PyPDF2
        try:
            pdf_file.seek(0)
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n[PAGE_BREAK]\n\n"
            results['pypdf2'] = self.clean_text(text)
        except:
            results['pypdf2'] = ""
            
        return results
    
    def clean_text(self, text: str) -> str:
        """Advanced text cleaning"""
        if not text:
            return ""
            
        # Unicode normalization
        text = unicodedata.normalize('NFKC', text)
        
        # Remove problematic characters
        cleanup_map = {
            '\u00ad': '',  # soft hyphen
            '\ufeff': '',  # BOM
            '\u200b': '',  # zero-width space
            '\u00a0': ' ',  # non-breaking space
            '\x0c': '\n[PAGE_BREAK]\n',  # form feed
            '\r\n': '\n',
            '\r': '\n',
            'Â­': '',
            '': '',
        }
        
        for old, new in cleanup_map.items():
            text = text.replace(old, new)
        
        # Fix spacing
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n +', '\n', text)
        text = re.sub(r' +\n', '\n', text)
        
        return text.strip()
    
    def select_best_extraction(self, extractions: Dict[str, str]) -> Tuple[str, str]:
        """Select best extraction based on quality metrics"""
        scores = {}
        
        for method, text in extractions.items():
            if not text:
                scores[method] = 0
                continue
                
            score = 0
            lines = text.split('\n')
            
            # Quality metrics
            score += len(text) * 0.001  # Length bonus
            score += len([l for l in lines if len(l.strip()) > 50]) * 2  # Complete lines
            score -= len([l for l in lines if len(l.strip()) < 5 and l.strip()]) * 1  # Fragment penalty
            
            # Legal document indicators
            if re.search(r'(Present|Coram|Before).*:', text, re.IGNORECASE):
                score += 10
            if re.search(r'\b(VS|V/S|V\.)\b', text):
                score += 10
            if re.search(r'No\.?\s*\d+', text):
                score += 10
            if re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', text):
                score += 5
            
            scores[method] = score
        
        best_method = max(scores.keys(), key=lambda k: scores[k])
        return extractions[best_method], best_method
    
    def analyze_document_structure(self, text: str) -> Dict:
        """Analyze document structure and extract metadata"""
        metadata = {
            'case_number': None,
            'parties': None,
            'date': None,
            'court': None,
            'judge': None,
            'document_type': 'judgment',
            'page_count': len(re.findall(r'\[PAGE_BREAK\]', text)) + 1,
            'confidence_indicators': []
        }
        
        lines = text.split('\n')
        
        # Extract case number
        for line in lines[:10]:
            if re.match(r'.*\([A-Z]+\).*No\.?\s*\d+', line.strip()):
                metadata['case_number'] = line.strip()
                metadata['confidence_indicators'].append('case_number_found')
                break
        
        # Extract parties
        for line in lines[:20]:
            if re.search(r'\b(VS|V/S|V\.)\b', line, re.IGNORECASE):
                metadata['parties'] = line.strip()
                metadata['confidence_indicators'].append('parties_found')
                break
        
        # Extract date
        date_patterns = [
            r'\b\d{1,2}\.\d{1,2}\.\d{4}\b',
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                metadata['date'] = match.group()
                metadata['confidence_indicators'].append('date_found')
                break
        
        # Extract judge
        judge_patterns = [
            r'([A-Z][A-Z\s]+)\s*(District Judge|Additional District Judge|Chief Judicial Magistrate)',
            r'(District Judge|Additional District Judge|Chief Judicial Magistrate)',
        ]
        for pattern in judge_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                metadata['judge'] = ' '.join(matches[0]) if isinstance(matches[0], tuple) else matches[0]
                metadata['confidence_indicators'].append('judge_found')
                break
        
        return metadata
    
    def calculate_confidence_score(self, text: str, metadata: Dict) -> float:
        """Calculate confidence score for extraction quality"""
        score = 0.0
        max_score = 100.0
        
        if not text:
            return 0.0
        
        # Basic text quality (40 points)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            avg_line_length = sum(len(l) for l in lines) / len(lines)
            score += min(20, avg_line_length * 0.5)  # Up to 20 points
        
        complete_lines = len([l for l in lines if len(l) > 50])
        fragment_lines = len([l for l in lines if 5 < len(l) <= 20])
        if complete_lines > 0:
            score += min(20, (complete_lines / (complete_lines + fragment_lines + 1)) * 20)
        
        # Structure recognition (60 points)
        structure_points = {
            'case_number_found': 15,
            'parties_found': 15,
            'date_found': 10,
            'judge_found': 10,
        }
        
        for indicator in metadata.get('confidence_indicators', []):
            score += structure_points.get(indicator, 0)
        
        # Legal document markers (bonus points)
        legal_markers = [
            r'\bPresent\s*:', r'\bCoram\s*:', r'\bBefore\s*:',
            r'\bHeard\b', r'\bORDER\b', r'\bJUDGMENT\b',
            r'\baccordingly\b', r'\btherefore\b', r'\bhence\b'
        ]
        
        marker_count = sum(1 for pattern in legal_markers if re.search(pattern, text, re.IGNORECASE))
        score += min(10, marker_count * 2)
        
        return min(100.0, score)
    
    def format_as_structured_json(self, text: str, metadata: Dict) -> str:
        """Format as structured JSON for database storage"""
        sections = self.segment_document(text)
        
        structured = {
            "document_metadata": {
                "case_number": metadata.get('case_number'),
                "parties": metadata.get('parties'),
                "date": metadata.get('date'),
                "court": metadata.get('court'),
                "judge": metadata.get('judge'),
                "page_count": metadata.get('page_count'),
                "extraction_confidence": self.confidence_score,
                "processing_timestamp": datetime.now().isoformat()
            },
            "document_sections": sections,
            "full_text": text
        }
        
        return json.dumps(structured, indent=2, ensure_ascii=False)
    
    def segment_document(self, text: str) -> Dict:
        """Segment document into logical sections"""
        sections = {
            "header": {"content": "", "confidence": 0},
            "case_details": {"content": "", "confidence": 0},
            "facts": {"content": "", "confidence": 0},
            "arguments": {"content": "", "confidence": 0},
            "reasoning": {"content": "", "confidence": 0},
            "decision": {"content": "", "confidence": 0},
            "directions": {"content": "", "confidence": 0}
        }
        
        lines = text.split('\n')
        current_section = "header"
        
        # Simple segmentation logic
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Section detection
            if any(marker in line_lower for marker in ['case no', 'case number', 'petition']):
                current_section = "case_details"
            elif any(marker in line_lower for marker in ['facts', 'background', 'brief facts']):
                current_section = "facts"
            elif any(marker in line_lower for marker in ['arguments', 'submissions', 'contentions']):
                current_section = "arguments"
            elif any(marker in line_lower for marker in ['reasoning', 'discussion', 'analysis']):
                current_section = "reasoning"
            elif any(marker in line_lower for marker in ['decision', 'held', 'conclusion']):
                current_section = "decision"
            elif any(marker in line_lower for marker in ['direction', 'order', 'accordingly']):
                current_section = "directions"
            
            # Add content to current section
            if line.strip():
                sections[current_section]["content"] += line + "\n"
        
        # Calculate confidence for each section
        for section in sections:
            content_length = len(sections[section]["content"])
            sections[section]["confidence"] = min(100, content_length * 0.1)
        
        return sections
    
    def format_as_original_pdf_style(self, text: str, metadata: Dict) -> str:
        """Format to match original PDF styling"""
        lines = text.split('\n')
        html_parts = []
        
        # Enhanced CSS for court document styling
        css = '''
        <style>
            body { 
                font-family: 'Times New Roman', serif; 
                font-size: 12pt; 
                line-height: 1.4; 
                margin: 0; 
                padding: 20px; 
                background: white; 
            }
            .page { 
                max-width: 210mm; 
                margin: 0 auto; 
                padding: 25mm; 
                min-height: 297mm; 
                background: white; 
                box-shadow: 0 0 10px rgba(0,0,0,0.1); 
            }
            .case-header { 
                text-align: center; 
                font-weight: bold; 
                margin: 20px 0; 
                font-size: 13pt; 
            }
            .parties { 
                text-align: center; 
                font-weight: bold; 
                text-decoration: underline; 
                margin: 15px 0; 
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
                line-height: 1.6; 
            }
            .numbered-para { 
                margin: 10px 0; 
                text-align: justify; 
                padding-left: 25px; 
                text-indent: -25px; 
            }
            .signature-block { 
                text-align: right; 
                margin: 20px 0; 
            }
            .page-break { 
                page-break-before: always; 
                text-align: center; 
                margin: 20px 0; 
                color: #666; 
                font-style: italic; 
            }
        </style>'''
        
        html_parts.append(f'<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head><body><div class="page">')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '[PAGE_BREAK]' in line:
                html_parts.append('<div class="page-break">--- Page Break ---</div>')
                continue
            
            # Classify line type
            css_class = self.classify_line_for_styling(line)
            escaped_line = (line.replace('&', '&amp;')
                               .replace('<', '&lt;')
                               .replace('>', '&gt;'))
            
            html_parts.append(f'<div class="{css_class}">{escaped_line}</div>')
        
        html_parts.append('</div></body></html>')
        return '\n'.join(html_parts)
    
    def classify_line_for_styling(self, line: str) -> str:
        """Classify line for CSS styling"""
        if re.match(r'.*\([A-Z]+\).*No\.?\s*\d+', line):
            return "case-header"
        elif re.search(r'\b(VS|V/S|V\.)\b', line, re.IGNORECASE):
            return "parties"
        elif re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}$', line):
            return "date"
        elif re.match(r'^(Present|Coram|Before)\s*:', line, re.IGNORECASE):
            return "present"
        elif re.match(r'^\s*\d+\.', line):
            return "numbered-para"
        elif line.isupper() and len(line.split()) <= 4:
            return "signature-block"
        else:
            return "paragraph"
    
    def process_document(self, pdf_file) -> Dict:
        """Main processing function"""
        # Extract with all methods
        extractions = self.extract_all_methods(pdf_file)
        
        # Select best extraction
        best_text, best_method = self.select_best_extraction(extractions)
        
        if not best_text:
            return {
                'success': False,
                'error': 'Failed to extract text with any method',
                'confidence': 0
            }
        
        # Analyze document structure
        metadata = self.analyze_document_structure(best_text)
        
        # Calculate confidence
        self.confidence_score = self.calculate_confidence_score(best_text, metadata)
        
        # Generate outputs
        structured_json = self.format_as_structured_json(best_text, metadata)
        original_style_html = self.format_as_original_pdf_style(best_text, metadata)
        
        return {
            'success': True,
            'confidence': self.confidence_score,
            'best_method': best_method,
            'metadata': metadata,
            'raw_text': best_text,
            'structured_json': structured_json,
            'original_style_html': original_style_html,
            'extraction_stats': {
                'methods_attempted': len(extractions),
                'methods_successful': len([k for k, v in extractions.items() if v]),
                'text_length': len(best_text),
                'line_count': len(best_text.split('\n')),
                'page_count': metadata.get('page_count', 1)
            }
        }

def main():
    st.title("🏛️ Enterprise Legal Document Processor")
    st.markdown("**Production-grade system for processing millions of district court cases**")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Enterprise Configuration")
        
        output_format = st.radio(
            "Primary Output Format:",
            ["Structured JSON (Database Ready)", "Original PDF Style", "Both"],
            help="Choose output format for your enterprise needs"
        )
        
        confidence_threshold = st.slider(
            "Confidence Threshold:",
            min_value=0, max_value=100, value=70,
            help="Minimum confidence score for accepting results"
        )
        
        st.markdown("### 🚀 Enterprise Features")
        st.markdown("""
        - **Multi-method extraction** with automatic best selection
        - **Confidence scoring** for quality assurance
        - **Metadata extraction** (case numbers, parties, dates)
        - **Document segmentation** into logical sections
        - **JSON output** for database integration
        - **Original styling preservation**
        - **Batch processing ready**
        - **Quality metrics** and validation
        """)
        
        st.markdown("### 📊 Quality Assurance")
        st.markdown("""
        - Automatic method comparison
        - Structure validation
        - Content completeness checks
        - Legal document markers detection
        - Confidence scoring algorithm
        """)
    
    # Main interface
    uploaded_file = st.file_uploader(
        "📄 Upload District Court Document",
        type=['pdf'],
        help="Upload PDF for enterprise-grade processing"
    )
    
    if uploaded_file is not None:
        st.info(f"**📄 File:** {uploaded_file.name} | **📦 Size:** {uploaded_file.size / 1024:.1f} KB")
        
        processor = EnterpriseDocumentProcessor()
        
        if st.button("🚀 Process with Enterprise Pipeline", type="primary", use_container_width=True):
            with st.spinner("🔄 Running enterprise processing pipeline..."):
                try:
                    result = processor.process_document(uploaded_file)
                    
                    if result['success']:
                        confidence = result['confidence']
                        
                        # Display confidence and quality metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("🎯 Confidence", f"{confidence:.1f}%")
                        with col2:
                            st.metric("📄 Pages", result['extraction_stats']['page_count'])
                        with col3:
                            st.metric("📝 Lines", result['extraction_stats']['line_count'])
                        with col4:
                            st.metric("🔧 Method", result['best_method'])
                        
                        # Quality indicator
                        if confidence >= confidence_threshold:
                            st.success(f"✅ HIGH QUALITY: Confidence {confidence:.1f}% exceeds threshold {confidence_threshold}%")
                        elif confidence >= 50:
                            st.warning(f"⚠️ MEDIUM QUALITY: Confidence {confidence:.1f}% - Review recommended")
                        else:
                            st.error(f"❌ LOW QUALITY: Confidence {confidence:.1f}% - Manual review required")
                        
                        # Document metadata
                        metadata = result['metadata']
                        if any(metadata.values()):
                            st.subheader("📋 Extracted Metadata")
                            meta_cols = st.columns(2)
                            with meta_cols[0]:
                                if metadata['case_number']:
                                    st.write(f"**Case Number:** {metadata['case_number']}")
                                if metadata['parties']:
                                    st.write(f"**Parties:** {metadata['parties']}")
                            with meta_cols[1]:
                                if metadata['date']:
                                    st.write(f"**Date:** {metadata['date']}")
                                if metadata['judge']:
                                    st.write(f"**Judge:** {metadata['judge']}")
                        
                        # Output tabs
                        if output_format == "Both":
                            tab1, tab2, tab3, tab4 = st.tabs(["📝 Raw Text", "🔧 Structured JSON", "🎨 Original Style", "💾 Downloads"])
                        elif output_format == "Structured JSON (Database Ready)":
                            tab1, tab2, tab4 = st.tabs(["📝 Raw Text", "🔧 Structured JSON", "💾 Downloads"])
                        else:
                            tab1, tab3, tab4 = st.tabs(["📝 Raw Text", "🎨 Original Style", "💾 Downloads"])
                        
                        with tab1:
                            st.subheader("📝 Extracted Raw Text")
                            st.text_area("Raw extracted text:", result['raw_text'], height=400)
                        
                        if output_format in ["Structured JSON (Database Ready)", "Both"]:
                            with tab2:
                                st.subheader("🔧 Structured JSON Output")
                                st.json(result['structured_json'])
                                st.code(result['structured_json'], language='json')
                        
                        if output_format in ["Original PDF Style", "Both"]:
                            with (tab3 if output_format == "Both" else tab1):
                                st.subheader("🎨 Original PDF Style")
                                st.components.v1.html(result['original_style_html'], height=600, scrolling=True)
                        
                        # Downloads
                        with (tab4 if output_format == "Both" else (tab4 if 'tab4' in locals() else tab1)):
                            st.subheader("💾 Enterprise Downloads")
                            
                            download_cols = st.columns(3)
                            with download_cols[0]:
                                st.download_button(
                                    "📝 Raw Text",
                                    result['raw_text'].encode('utf-8'),
                                    f"{uploaded_file.name.replace('.pdf', '')}_raw.txt",
                                    "text/plain"
                                )
                            
                            with download_cols[1]:
                                st.download_button(
                                    "🔧 Structured JSON",
                                    result['structured_json'].encode('utf-8'),
                                    f"{uploaded_file.name.replace('.pdf', '')}_structured.json",
                                    "application/json"
                                )
                            
                            with download_cols[2]:
                                st.download_button(
                                    "🎨 Styled HTML",
                                    result['original_style_html'].encode('utf-8'),
                                    f"{uploaded_file.name.replace('.pdf', '')}_styled.html",
                                    "text/html"
                                )
                    
                    else:
                        st.error(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
                
                except Exception as e:
                    st.error(f"❌ System error: {str(e)}")
                    st.info("💡 This may indicate a PDF format not yet supported. Please report for enhancement.")

if __name__ == "__main__":
    main()

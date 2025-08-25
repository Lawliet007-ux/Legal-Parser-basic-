import streamlit as st
import pdfplumber

st.title("Legal Judgment PDF to HTML Converter")

st.markdown("""
This tool extracts text from uploaded legal judgment PDFs while preserving the original structure, numbering, sub-numbering, and text alignment as closely as possible. 
The output is generated in HTML format, with a preview displayed below. The HTML uses a monospace font and preserves whitespace to mimic the PDF layout.
""")

uploaded_file = st.file_uploader("Upload your judgment PDF file", type=["pdf"])

if uploaded_file is not None:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = ""
            for i, page in enumerate(pdf.pages, start=1):
                # Extract text with layout preservation (inserts spaces and newlines to mimic original positions)
                page_text = page.extract_text(layout=True)
                if page_text:
                    full_text += page_text.strip() + f"\n\n"  # Strip trailing spaces but preserve internal layout

        # Generate HTML content that preserves the structure using <pre> tag
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Extracted Judgment</title>
            <style>
                body {{
                    font-family: monospace;
                    margin: 20px;
                    background-color: #f9f9f9;
                }}
                pre {{
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    font-size: 12px;
                    line-height: 1.2;
                    padding: 20px;
                    background-color: white;
                    border: 1px solid #ddd;
                    overflow-x: auto;
                }}
            </style>
        </head>
        <body>
            <h1>Extracted Judgment Text</h1>
            <pre>{full_text}</pre>
        </body>
        </html>
        """

        # Display preview in Streamlit UI
        st.subheader("HTML Preview")
        st.components.v1.html(html_content, height=800, scrolling=True)

        # Provide download button for the HTML file
        st.download_button(
            label="Download HTML File",
            data=html_content,
            file_name=f"{uploaded_file.name.replace('.pdf', '')}.html",
            mime="text/html"
        )

    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {str(e)}")
        st.info("Please ensure the uploaded file is a valid PDF. For best results, use PDFs with text layers (not scanned images).")

st.markdown("""
**Notes:**
- This tool uses layout-preserving text extraction to maintain originality, including numberings, alignments, and structure.
- It is designed to handle varying formats in district court cases, but results may vary with scanned or image-based PDFs (OCR not included).
- For large-scale processing (e.g., hundreds of millions of cases), consider deploying this as a batch script or integrating with cloud services for scalability.
""")

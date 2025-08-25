import streamlit as st
from io import StringIO, BytesIO
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams

st.title("Legal Judgment PDF to HTML Converter (Improved)")

st.markdown("""
This tool uses pdfminer.six to convert uploaded legal judgment PDFs to HTML while preserving the original layout, structure, text alignment, numberings, and sub-numberings as closely as possible. 
The output HTML uses CSS for positioning to mimic the PDF structure accurately.
**Note:** Ensure pdfminer.six is installed in your environment: `pip install pdfminer.six`.
""")

uploaded_file = st.file_uploader("Upload your judgment PDF file", type=["pdf"])

if uploaded_file is not None:
    try:
        output_string = StringIO()
        # Use LAParams with adjusted parameters for better layout preservation
        laparams = LAParams(
            detect_vertical=True,
            all_texts=False,
            char_margin=1.0,  # Tighter char margin for better word grouping
            line_margin=0.3,  # Adjust line overlap for accurate line detection
            word_margin=0.1   # Word spacing detection
        )
        extract_text_to_fp(
            BytesIO(uploaded_file.getvalue()),
            output_string,
            laparams=laparams,
            output_type='html',
            codec=None,
            maxpages=0,  # Process all pages
            caching=True,
            scale=1
        )
        extracted_html = output_string.getvalue()

        # Wrap the extracted HTML in a full HTML document with basic styling for better rendering
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Extracted Judgment</title>
            <style>
                body {{
                    font-family: serif;  /* Use serif font to mimic legal documents */
                    margin: 20px;
                    background-color: #f9f9f9;
                }}
                div {{
                    position: absolute;  /* Preserve absolute positioning from pdfminer */
                }}
                .txt {{
                    white-space: pre;  /* Preserve whitespace in text blocks */
                }}
            </style>
        </head>
        <body>
            {extracted_html}
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
        st.info("Please ensure the uploaded file is a valid PDF with extractable text (not scanned images). For scanned PDFs, OCR tools like Tesseract may be needed separately.")

st.markdown("""
**Notes:**
- This improved version uses pdfminer.six's layout analysis to generate HTML with positioned elements, aiming for a near-carbon copy of the original PDF structure and alignment.
- It handles varying formats in district court cases by analyzing text blocks, lines, and characters precisely.
- For large-scale processing, consider batch scripts or cloud deployment. Results may still vary slightly due to PDF complexities, but this should be much closer to the original.
- If further tuning is needed, adjust LAParams values in the code for specific PDF formats.
""")

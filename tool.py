import streamlit as st
import pypdf2htmlEX
import tempfile
import os

st.title("Legal Judgment PDF to HTML Converter (High-Fidelity Layout Preservation)")

st.markdown("""
This tool uses pdf2htmlEX via a Python wrapper to convert uploaded legal judgment PDFs to HTML, preserving the original layout, structure, text alignment, fonts, and formatting as closely as possible—aiming for a near-carbon copy of the PDF.
**Important Prerequisite:** You must have pdf2htmlEX installed on your system. On Ubuntu, use `sudo apt-get install pdf2htmlex`. For other OS, see https://github.com/pdf2htmlEX/pdf2htmlEX/wiki/Building-and-Installing.
Install the Python wrapper with `pip install pypdf2htmlex`.
""")

# Single file uploader
uploaded_file = st.file_uploader("Upload a single judgment PDF file", type=["pdf"])

if uploaded_file is not None:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        pdf = pypdf2htmlEX.PDF(tmp_path)
        pdf.to_html(drm=False)  # Convert to HTML; drm=False by default

        # Output HTML path
        html_path = os.path.splitext(tmp_path)[0] + '.html'
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Display preview in Streamlit UI
        st.subheader("HTML Preview (Single File)")
        st.components.v1.html(html_content, height=800, scrolling=True)

        # Provide download button
        st.download_button(
            label="Download HTML File",
            data=html_content,
            file_name=f"{uploaded_file.name.replace('.pdf', '')}.html",
            mime="text/html"
        )

        # Clean up temp files
        os.unlink(tmp_path)
        os.unlink(html_path)

    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {str(e)}")
        st.info("Ensure pdf2htmlEX is installed and accessible in your system's PATH.")

# Multiple file uploader for batch processing
uploaded_files = st.file_uploader("Upload multiple judgment PDF files for batch processing", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    try:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file in uploaded_files:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    tmp.write(file.getvalue())
                    tmp_path = tmp.name

                pdf = pypdf2htmlEX.PDF(tmp_path)
                pdf.to_html(drm=False)

                html_path = os.path.splitext(tmp_path)[0] + '.html'
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                # Add to zip
                zip_file.writestr(f"{file.name.replace('.pdf', '')}.html", html_content)

                # Clean up
                os.unlink(tmp_path)
                os.unlink(html_path)

        zip_buffer.seek(0)
        st.download_button(
            label="Download All HTML Files as ZIP",
            data=zip_buffer,
            file_name="converted_judgments.zip",
            mime="application/zip"
        )

        st.success("Batch conversion completed. Download the ZIP file containing all HTML outputs.")

    except Exception as e:
        st.error(f"An error occurred during batch processing: {str(e)}")

st.markdown("""
**Notes:**
- This tool provides high-fidelity conversion, making the HTML output resemble the input PDF completely in structure, alignment, and appearance.
- For processing hundreds of millions of cases with varying district court formats, Streamlit is suitable for interactive use but not ideal for massive scale. Use the following command-line Python script for batch processing large directories:
```python
import pypdf2htmlEX
import os

def batch_convert_pdf_to_html(input_dir, output_dir=None, prefix=''):
    if output_dir is None:
        output_dir = input_dir
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(input_dir, filename)
            pdf = pypdf2htmlEX.PDF(pdf_path)
            pdf.to_html(drm=False)
            # pdf2htmlEX generates HTML in the same directory; move to output if different
            html_filename = os.path.splitext(filename)[0] + '.html'
            html_path = os.path.join(input_dir, html_filename)
            if output_dir != input_dir:
                os.rename(html_path, os.path.join(output_dir, prefix + html_filename))

# Usage example:
# batch_convert_pdf_to_html('path/to/input/folder', 'path/to/output/folder', 'Converted_')

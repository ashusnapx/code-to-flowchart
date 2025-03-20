import streamlit as st
import graphviz
import tempfile
import os
import base64
from reportlab.lib.pagesizes import A4, A3, A2, A1, A0, letter, legal, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Image, PageBreak
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
import io
import subprocess

tabloid = (11 * inch, 17 * inch)

# Set page configuration for a sleek UI
st.set_page_config(page_title="Code to Flowchart", layout="centered", initial_sidebar_state="collapsed")

# Mapping page size options
PAGE_SIZES = {
    "A4": A4, "A3": A3, "A2": A2, "A1": A1, "A0": A0,
    "Letter": letter, "Legal": legal, "Tabloid": tabloid
}

# Mapping DPI settings
DPI_OPTIONS = {
    "Low (72 DPI)": 72, "Medium (150 DPI)": 150,
    "High (300 DPI)": 300, "Very High (600 DPI)": 600
}

st.title("Flowchart Maker By @ashusnapx")

# User input for flowchart code
st.subheader("Enter Flowchart in DOT Format")
flowchart_code = st.text_area("Example:\ndigraph { A -> B; B -> C; }", height=200)

# Advanced options
with st.expander("Advanced Options"):
    col1, col2 = st.columns(2)
    with col1:
        page_size = st.selectbox("Select Page Size", list(PAGE_SIZES.keys()), index=1)  # Default A3
        orientation = st.selectbox("Select Orientation", ["Portrait", "Landscape"], index=1)  # Default Landscape
    with col2:
        dpi = st.selectbox("Image Quality", list(DPI_OPTIONS.keys()), index=2)  # Default High DPI
        scaling_method = st.selectbox("Scaling Method", ["Fit to Page", "Scale to Multiple Pages", "Original Size"], index=1)
    
    margin_mm = st.slider("Page Margin (mm)", 0, 50, 10)  # Default lower margin for better fit

# Render flowchart
if st.button("Generate Flowchart"):
    if flowchart_code.strip():
        try:
            st.graphviz_chart(flowchart_code)
            st.session_state["flowchart_code"] = flowchart_code
            st.session_state["page_size"] = page_size
            st.session_state["orientation"] = orientation
            st.session_state["dpi"] = DPI_OPTIONS[dpi]
            st.session_state["scaling_method"] = scaling_method
            st.session_state["margin_mm"] = margin_mm
        except Exception as e:
            st.error(f"Error in rendering flowchart: {e}")
    else:
        st.warning("Please enter valid flowchart code.")

def check_graphviz_installed():
    """Check if Graphviz is installed and accessible."""
    try:
        subprocess.run(["dot", "-V"], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False

def generate_graphviz_image(dot_code, output_format="png", dpi=300):
    """Generate a graphviz image using the dot command."""
    try:
        dot_file = tempfile.NamedTemporaryFile(delete=False, suffix=".dot")
        dot_file.write(dot_code.encode())
        dot_file.close()
        
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
        output_file.close()
        
        cmd = ["dot", f"-T{output_format}", f"-Gdpi={dpi}", dot_file.name, "-o", output_file.name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Graphviz error: {result.stderr}")
        
        with open(output_file.name, "rb") as f:
            image_data = f.read()
        
        os.unlink(dot_file.name)
        os.unlink(output_file.name)
        
        return image_data
    except Exception as e:
        raise Exception(f"Failed to generate image: {str(e)}")

def generate_pdf(flowchart_code, page_size, orientation, dpi, scaling_method, margin_mm):
    """Generate a PDF with the flowchart, ensuring seamless multi-page continuity."""
    if not check_graphviz_installed():
        st.error("Graphviz is not installed. Please install it to use this feature.")
        return None
    
    try:
        image_data = generate_graphviz_image(flowchart_code, "png", dpi)
        pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_file.close()
        
        page_size_tuple = PAGE_SIZES[page_size]
        if orientation == "Landscape":
            page_size_tuple = landscape(page_size_tuple)
        
        margin = margin_mm * mm

        doc = SimpleDocTemplate(
            pdf_file.name,
            pagesize=page_size_tuple,
            leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=0  # Zero bottom margin for seamless look
        )
        
        img = PILImage.open(io.BytesIO(image_data))
        img_width, img_height = img.size
        
        elements = []
        
        available_width = doc.width
        available_height = doc.height

        if scaling_method == "Fit to Page":
            scale_width = available_width / img_width
            scale_height = available_height / img_height
            scale = min(scale_width, scale_height)
            
            img_obj = Image(io.BytesIO(image_data), width=img_width * scale, height=img_height * scale)
            elements.append(img_obj)

        elif scaling_method == "Scale to Multiple Pages":
            scale = min(1.0, available_width / img_width)
            scaled_width = img_width * scale
            scaled_height = img_height * scale

            if scaled_height <= available_height:
                img_obj = Image(io.BytesIO(image_data), width=scaled_width, height=scaled_height)
                elements.append(img_obj)
            else:
                pages_needed = int((scaled_height / available_height) + 0.999)
                
                for i in range(pages_needed):
                    start_y = int(i * img_height / pages_needed)
                    end_y = int((i + 1) * img_height / pages_needed)
                    
                    section = img.crop((0, start_y, img_width, end_y))
                    
                    section_buffer = io.BytesIO()
                    section.save(section_buffer, format="PNG")
                    section_buffer.seek(0)
                    
                    section_height = (end_y - start_y) * scale
                    section_obj = Image(section_buffer, width=scaled_width, height=section_height)
                    elements.append(section_obj)
                    
                    if i < pages_needed - 1:
                        elements.append(PageBreak())
        
        else:
            img_obj = Image(io.BytesIO(image_data))
            elements.append(img_obj)
        
        doc.build(elements)
        return pdf_file.name
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None

if "flowchart_code" in st.session_state and st.button("Download as PDF"):
    with st.spinner("Generating PDF..."):
        pdf_file = generate_pdf(
            st.session_state["flowchart_code"],
            st.session_state["page_size"],
            st.session_state["orientation"],
            st.session_state["dpi"],
            st.session_state["scaling_method"],
            st.session_state["margin_mm"]
        )
        
        if pdf_file:
            with open(pdf_file, "rb") as f:
                pdf_data = f.read()
            
            st.download_button("Download Flowchart PDF", pdf_data, file_name="flowchart.pdf", mime="application/pdf")
            os.unlink(pdf_file)
        else:
            st.error("Failed to generate PDF.")

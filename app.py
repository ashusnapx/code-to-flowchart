import streamlit as st
import graphviz
import tempfile
import os
import base64
import logging
from reportlab.lib.pagesizes import A4, A3, A2, A1, A0, letter, legal, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Image, PageBreak, Spacer, Paragraph
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image as PILImage
import io
import subprocess
import time
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Standard page sizes
tabloid = (11 * inch, 17 * inch)
PAGE_SIZES = {
    "A4": A4, "A3": A3, "A2": A2, "A1": A1, "A0": A0,
    "Letter": letter, "Legal": legal, "Tabloid": tabloid
}

# Image quality options
DPI_OPTIONS = {
    "Low (72 DPI)": 72, 
    "Medium (150 DPI)": 150,
    "High (300 DPI)": 300, 
    "Very High (600 DPI)": 600
}

# Graphviz engines
ENGINES = {
    "dot": "Hierarchical layouts (default)",
    "neato": "Spring model layouts",
    "fdp": "Force-directed layouts",
    "sfdp": "Scalable force-directed layouts",
    "circo": "Circular layouts",
    "twopi": "Radial layouts",
    "osage": "Array-based layouts"
}

# Set page configuration for a sleek UI
st.set_page_config(
    page_title="Advanced Flowchart Generator", 
    layout="wide", 
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# Advanced Flowchart Generator\nCreated by @ashusnapx\nEnhanced Version"
    }
)

def check_graphviz_installed():
    """Check if Graphviz is installed and accessible, with detailed error reporting."""
    try:
        result = subprocess.run(["dot", "-V"], capture_output=True, text=True)
        logger.info(f"Graphviz detected: {result.stdout}")
        return True, result.stdout
    except FileNotFoundError:
        logger.error("Graphviz not found in system path")
        return False, "Graphviz not found. Please install Graphviz and ensure it's in your system PATH."
    except Exception as e:
        logger.error(f"Error checking Graphviz: {str(e)}")
        return False, f"Error checking Graphviz: {str(e)}"

def validate_dot_syntax(dot_code):
    """Validate DOT syntax before rendering to provide helpful error messages."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dot") as temp_file:
            temp_file.write(dot_code.encode())
            temp_path = temp_file.name
        
        result = subprocess.run(
            ["dot", "-Tpng", temp_path, "-o", os.devnull], 
            capture_output=True, 
            text=True
        )
        os.unlink(temp_path)
        
        if result.returncode != 0:
            # Parse the error message to make it more user-friendly
            error_msg = result.stderr
            # Extract line number if available
            line_match = re.search(r'line (\d+)', error_msg)
            if line_match:
                line_num = int(line_match.group(1))
                lines = dot_code.split('\n')
                error_context = lines[max(0, line_num-2):min(len(lines), line_num+1)]
                context_str = '\n'.join([f"{i+max(0, line_num-2)+1}: {line}" for i, line in enumerate(error_context)])
                return False, f"Syntax error near line {line_num}:\n{context_str}\n\nGraphviz error: {error_msg}"
            return False, f"DOT syntax error: {error_msg}"
        return True, "Syntax valid"
    except Exception as e:
        logger.error(f"Error validating DOT syntax: {str(e)}")
        return False, f"Error validating DOT syntax: {str(e)}"

def generate_graphviz_image(dot_code, output_format="png", dpi=300, engine="dot"):
    """Generate a graphviz image with advanced error handling and performance optimization."""
    start_time = time.time()
    dot_file = None
    output_file = None
    
    try:
        # Create temporary files with meaningful names for debugging
        dot_file = tempfile.NamedTemporaryFile(delete=False, suffix=".dot")
        dot_file.write(dot_code.encode())
        dot_file.close()
        
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
        output_file.close()
        
        # Build the command with all necessary parameters
        cmd = [
            engine, 
            f"-T{output_format}", 
            f"-Gdpi={dpi}",
            # Add optimization parameters
            "-Gnodesep=0.5",  # Node separation
            "-Granksep=0.5",  # Rank separation for hierarchical layouts
            "-Gpad=0.2",      # Padding
            "-Gsplines=ortho", # Orthogonal lines for cleaner appearance
            dot_file.name, 
            "-o", 
            output_file.name
        ]
        
        logger.info(f"Executing command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_message = result.stderr
            # Extract relevant part of the error message
            if "syntax error" in error_message:
                match = re.search(r'Error: .+, line \d+', error_message)
                if match:
                    error_message = match.group(0)
            raise Exception(f"Graphviz error: {error_message}")
        
        # Read the generated image
        with open(output_file.name, "rb") as f:
            image_data = f.read()
        
        logger.info(f"Image generation completed in {time.time() - start_time:.2f} seconds")
        return image_data
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise Exception(f"Failed to generate image: {str(e)}")
    finally:
        # Clean up temporary files
        for file in [dot_file, output_file]:
            if file and os.path.exists(file.name):
                try:
                    os.unlink(file.name)
                except Exception as e:
                    logger.warning(f"Could not delete temporary file {file.name}: {str(e)}")

def generate_pdf(flowchart_code, page_size, orientation, dpi, scaling_method, margin_mm, engine="dot", include_code=False):
    """Generate a PDF with the flowchart, ensuring seamless multi-page continuity with pagination."""
    graphviz_installed, message = check_graphviz_installed()
    if not graphviz_installed:
        return None, message
    
    try:
        # Validate DOT syntax first
        valid, msg = validate_dot_syntax(flowchart_code)
        if not valid:
            return None, msg
        
        # Generate the image
        image_data = generate_graphviz_image(flowchart_code, "png", dpi, engine)
        pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_file.close()
        
        # Set up page parameters
        page_size_tuple = PAGE_SIZES[page_size]
        if orientation == "Landscape":
            page_size_tuple = landscape(page_size_tuple)
        
        margin = margin_mm * mm
        styles = getSampleStyleSheet()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            pdf_file.name,
            pagesize=page_size_tuple,
            leftMargin=margin, 
            rightMargin=margin, 
            topMargin=margin, 
            bottomMargin=margin
        )
        
        # Open and analyze the image
        img = PILImage.open(io.BytesIO(image_data))
        img_width, img_height = img.size
        
        # Calculate available space
        available_width = doc.width
        available_height = doc.height - (10 * mm)  # Reserve space for page numbers
        
        # Prepare PDF elements
        elements = []
        
        # Add DOT code if requested
        if include_code:
            code_title = Paragraph("DOT Source Code:", styles['Heading2'])
            elements.append(code_title)
            code_text = Paragraph(flowchart_code.replace("\n", "<br/>"), styles['Code'])
            elements.append(code_text)
            elements.append(Spacer(1, 10 * mm))
            elements.append(PageBreak())
        
        # Process image based on selected scaling method
        if scaling_method == "Fit to Page":
            # Scale to fit within a single page
            scale_width = available_width / img_width
            scale_height = available_height / img_height
            scale = min(scale_width, scale_height)
            
            img_obj = Image(io.BytesIO(image_data), width=img_width * scale, height=img_height * scale)
            elements.append(img_obj)

        elif scaling_method == "Scale to Multiple Pages":
            # Intelligent multi-page scaling with smooth transitions
            scale = min(1.0, available_width / img_width)
            scaled_width = img_width * scale
            scaled_height = img_height * scale
            
            # Calculate optimal pages needed
            if scaled_height <= available_height:
                # Fits on one page
                img_obj = Image(io.BytesIO(image_data), width=scaled_width, height=scaled_height)
                elements.append(img_obj)
            else:
                # Multi-page with 10% overlap for smooth transitions
                overlap_percentage = 0.10
                effective_page_height = available_height * (1 - overlap_percentage)
                pages_needed = max(1, int((scaled_height / effective_page_height) + 0.999))
                
                # Calculate section height in original image pixels
                section_height_pixels = img_height / pages_needed
                # Add overlap
                overlap_pixels = section_height_pixels * overlap_percentage
                
                for i in range(pages_needed):
                    # Calculate section boundaries with overlap
                    start_y = int(i * section_height_pixels)
                    if i > 0:
                        start_y -= int(overlap_pixels)
                    
                    end_y = int(min((i + 1) * section_height_pixels, img_height))
                    if i < pages_needed - 1:
                        end_y += int(overlap_pixels)
                    
                    # Ensure we don't exceed image boundaries
                    start_y = max(0, start_y)
                    end_y = min(img_height, end_y)
                    
                    # Crop the image section
                    section = img.crop((0, start_y, img_width, end_y))
                    
                    # Save to buffer and create image object
                    section_buffer = io.BytesIO()
                    section.save(section_buffer, format="PNG")
                    section_buffer.seek(0)
                    
                    # Calculate scaled dimensions
                    section_height = (end_y - start_y) * scale
                    section_obj = Image(section_buffer, width=scaled_width, height=section_height)
                    elements.append(section_obj)
                    
                    # Add page number
                    page_number = Paragraph(f"Page {i+1} of {pages_needed}", styles['Normal'])
                    elements.append(page_number)
                    
                    # Add page break if not the last page
                    if i < pages_needed - 1:
                        elements.append(PageBreak())
        
        else:  # Original Size
            img_obj = Image(io.BytesIO(image_data))
            elements.append(img_obj)
        
        # Build the document
        doc.build(elements)
        return pdf_file.name, "PDF generated successfully"
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        return None, f"Error generating PDF: {str(e)}"

def main():
    # Page header with branding
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("Advanced Flowchart Generator")
        st.caption("Transform DOT code into professional flowcharts with multi-page support")
    with col2:
        st.write("")
        graphviz_status, graphviz_message = check_graphviz_installed()
        if graphviz_status:
            st.success("Graphviz Ready")
        else:
            st.error("Graphviz Not Found")
            st.info("Please install Graphviz to use this tool")
    
    # Create tabs for better organization
    tab1, tab2, tab3 = st.tabs(["Create Flowchart", "Examples & Help", "About"])
    
    with tab1:
        # Main input area
        st.subheader("Enter Flowchart in DOT Format")
        
        # Display sample code for easy start
        sample_code = """digraph G {
    rankdir=LR;
    node [shape=box, style=filled, fillcolor=lightblue];
    start [shape=oval, fillcolor=lightgreen, label="Start"];
    process1 [label="Process Data"];
    decision [shape=diamond, fillcolor=lightyellow, label="Check Result?"];
    end [shape=oval, fillcolor=lightcoral, label="End"];
    
    start -> process1;
    process1 -> decision;
    decision -> end [label="Success"];
    decision -> process1 [label="Retry"];
}"""
        
        # Load saved code from session if available
        default_code = st.session_state.get("flowchart_code", sample_code)
        flowchart_code = st.text_area("", default_code, height=300)
        
        # Options in columns for better layout
        col1, col2 = st.columns(2)
        with col1:
            # Render and layout options
            st.subheader("Rendering Options")
            engine = st.selectbox("Layout Engine", list(ENGINES.keys()), 
                                index=0, help="Different engines create different layout styles")
            st.caption(ENGINES[engine])
            
            page_size = st.selectbox("Page Size", list(PAGE_SIZES.keys()), 
                                   index=1, help="Select output page size")
            orientation = st.selectbox("Orientation", ["Portrait", "Landscape"], 
                                     index=1, help="Page orientation")
            
        with col2:
            # Export options
            st.subheader("Export Options")
            dpi = st.selectbox("Image Quality", list(DPI_OPTIONS.keys()), 
                             index=2, help="Higher DPI means better quality but larger file size")
            scaling_method = st.selectbox("Scaling Method", 
                                        ["Fit to Page", "Scale to Multiple Pages", "Original Size"], 
                                        index=1, 
                                        help="How to fit large diagrams to pages")
            margin_mm = st.slider("Page Margin (mm)", 0, 50, 10, 
                                help="Margin around the flowchart")
            include_code = st.checkbox("Include DOT code in PDF", value=False, 
                                     help="Add the source code as the first page of the PDF")
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            preview_btn = st.button("Preview Flowchart", use_container_width=True)
        with col2:
            validate_btn = st.button("Validate DOT Syntax", use_container_width=True)
        with col3:
            generate_btn = st.button("Generate & Download PDF", use_container_width=True, type="primary")
        
        # Validate syntax if requested
        if validate_btn:
            with st.spinner("Validating DOT syntax..."):
                valid, message = validate_dot_syntax(flowchart_code)
                if valid:
                    st.success("DOT syntax is valid!")
                else:
                    st.error(message)
        
        # Preview the flowchart
        if preview_btn or "show_preview" in st.session_state:
            if flowchart_code.strip():
                try:
                    st.session_state["show_preview"] = True
                    st.session_state["flowchart_code"] = flowchart_code
                    st.session_state["page_size"] = page_size
                    st.session_state["orientation"] = orientation
                    st.session_state["dpi"] = DPI_OPTIONS[dpi]
                    st.session_state["scaling_method"] = scaling_method
                    st.session_state["margin_mm"] = margin_mm
                    st.session_state["engine"] = engine
                    st.session_state["include_code"] = include_code
                    
                    # Display preview using Graphviz
                    st.subheader("Flowchart Preview")
                    graph = graphviz.Source(flowchart_code, engine=engine)
                    st.graphviz_chart(flowchart_code, use_container_width=True)
                    
                    # Show image dimensions for reference
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.dot') as f:
                            f.write(flowchart_code.encode())
                            f.flush()
                            result = subprocess.run(
                                [engine, "-Tpng", f.name], 
                                capture_output=True
                            )
                            if result.returncode == 0:
                                img = PILImage.open(io.BytesIO(result.stdout))
                                width, height = img.size
                                st.caption(f"Image dimensions: {width}x{height} pixels")
                    except Exception as e:
                        logger.warning(f"Could not determine image dimensions: {str(e)}")
                except Exception as e:
                    st.error(f"Error rendering preview: {str(e)}")
            else:
                st.warning("Please enter valid flowchart code.")
        
        # Generate and download PDF
        if generate_btn:
            if flowchart_code.strip():
                with st.spinner("Generating PDF - This may take a moment..."):
                    pdf_file, message = generate_pdf(
                        flowchart_code,
                        page_size,
                        orientation,
                        DPI_OPTIONS[dpi],
                        scaling_method,
                        margin_mm,
                        engine,
                        include_code
                    )
                    
                    if pdf_file:
                        with open(pdf_file, "rb") as f:
                            pdf_data = f.read()
                        
                        filename = f"flowchart_{page_size}_{orientation}.pdf"
                        st.success("PDF generated successfully!")
                        st.download_button(
                            "Download Flowchart PDF",
                            pdf_data,
                            file_name=filename,
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                        # Display a thumbnail preview of the PDF
                        st.image("https://cdn-icons-png.flaticon.com/512/337/337946.png", 
                                width=100, 
                                caption="PDF Ready for Download")
                        
                        # Cleanup
                        try:
                            os.unlink(pdf_file)
                        except Exception as e:
                            logger.warning(f"Could not delete temporary PDF: {str(e)}")
                    else:
                        st.error(f"Failed to generate PDF: {message}")
            else:
                st.warning("Please enter valid flowchart code.")
    
    with tab2:
        st.header("Examples & Help")
        
        with st.expander("Basic Flowchart Example"):
            st.code("""digraph G {
    rankdir=TB;  // Top to Bottom layout
    node [shape=box, style=filled, fillcolor=lightblue];
    
    start [shape=oval, fillcolor=lightgreen, label="Start"];
    process [label="Process Data"];
    decision [shape=diamond, fillcolor=lightyellow, label="Is Data Valid?"];
    end [shape=oval, fillcolor=lightcoral, label="End"];
    
    start -> process;
    process -> decision;
    decision -> end [label="Yes"];
    decision -> process [label="No", constraint=false];
}""")
            if st.button("Load this example"):
                st.session_state["flowchart_code"] = """digraph G {
    rankdir=TB;  // Top to Bottom layout
    node [shape=box, style=filled, fillcolor=lightblue];
    
    start [shape=oval, fillcolor=lightgreen, label="Start"];
    process [label="Process Data"];
    decision [shape=diamond, fillcolor=lightyellow, label="Is Data Valid?"];
    end [shape=oval, fillcolor=lightcoral, label="End"];
    
    start -> process;
    process -> decision;
    decision -> end [label="Yes"];
    decision -> process [label="No", constraint=false];
}"""
                st.session_state["show_preview"] = True
                st.experimental_rerun()
        
        with st.expander("Complex Process Flow Example"):
            st.code("""digraph G {
    rankdir=LR;
    node [shape=box, style=filled, fillcolor=lightblue, margin=0.1];
    edge [fontsize=10];
    
    // Define nodes
    start [shape=oval, fillcolor=lightgreen, label="Start"];
    input [label="Receive Input"];
    validate [label="Validate Data"];
    process1 [label="Process Stage 1"];
    process2 [label="Process Stage 2"];
    decision1 [shape=diamond, fillcolor=lightyellow, label="Valid?"];
    decision2 [shape=diamond, fillcolor=lightyellow, label="Complete?"];
    error [shape=box, fillcolor=lightpink, label="Error Handling"];
    output [label="Generate Output"];
    end [shape=oval, fillcolor=lightcoral, label="End"];
    
    // Define edges
    start -> input;
    input -> validate;
    validate -> decision1;
    decision1 -> process1 [label="Yes"];
    decision1 -> error [label="No"];
    process1 -> process2;
    process2 -> decision2;
    decision2 -> output [label="Yes"];
    decision2 -> process1 [label="No", constraint=false];
    error -> input [constraint=false, label="Retry"];
    output -> end;
}""")
            if st.button("Load complex example"):
                st.session_state["flowchart_code"] = """digraph G {
    rankdir=LR;
    node [shape=box, style=filled, fillcolor=lightblue, margin=0.1];
    edge [fontsize=10];
    
    // Define nodes
    start [shape=oval, fillcolor=lightgreen, label="Start"];
    input [label="Receive Input"];
    validate [label="Validate Data"];
    process1 [label="Process Stage 1"];
    process2 [label="Process Stage 2"];
    decision1 [shape=diamond, fillcolor=lightyellow, label="Valid?"];
    decision2 [shape=diamond, fillcolor=lightyellow, label="Complete?"];
    error [shape=box, fillcolor=lightpink, label="Error Handling"];
    output [label="Generate Output"];
    end [shape=oval, fillcolor=lightcoral, label="End"];
    
    // Define edges
    start -> input;
    input -> validate;
    validate -> decision1;
    decision1 -> process1 [label="Yes"];
    decision1 -> error [label="No"];
    process1 -> process2;
    process2 -> decision2;
    decision2 -> output [label="Yes"];
    decision2 -> process1 [label="No", constraint=false];
    error -> input [constraint=false, label="Retry"];
    output -> end;
}"""
                st.session_state["show_preview"] = True
                st.experimental_rerun()
                
        with st.expander("DOT Syntax Quick Reference"):
            st.markdown("""
            ### Basic Syntax
            ```
            digraph G {
                // Nodes
                node1 [label="Node Label", shape=shape_name];
                
                // Edges
                node1 -> node2 [label="Edge Label"];
            }
            ```
            
            ### Common Node Shapes
            - `box` (default)
            - `oval`
            - `circle`
            - `diamond`
            - `plaintext`
            - `polygon`
            - `record`
            
            ### Common Node Attributes
            - `label="Text"` - Node text
            - `shape=shape_name` - Node shape
            - `style=filled` - Fill the node
            - `fillcolor=color` - Background color
            - `color=color` - Border color
            - `fontcolor=color` - Text color
            
            ### Common Edge Attributes
            - `label="Text"` - Edge label
            - `color=color` - Edge color
            - `style=dashed/dotted/solid` - Line style
            - `dir=forward/back/both/none` - Arrow direction
            - `constraint=false` - Allow edge to break rank
            
            ### Graph Attributes
            - `rankdir=TB/LR/BT/RL` - Graph direction
            - `bgcolor=color` - Background color
            - `splines=line/ortho/curved` - Edge style
            
            ### Subgraphs
            ```
            subgraph cluster_name {
                label="Subgraph Label";
                node1; node2;
            }
            ```
            """)
            
    with tab3:
        st.header("About This Tool")
        st.markdown("""
        ### Advanced Flowchart Generator
        
        This tool allows you to create professional flowcharts from DOT language code with advanced features:
        
        - **Multi-page support** for large diagrams with smooth transitions between pages
        - **7 different layout engines** for various flowchart styles
        - **High-quality PDF export** with customizable page sizes and orientations
        - **Syntax validation** to help catch errors before rendering
        - **Intelligent error handling** with helpful suggestions
        
        ### About DOT Language
        
        DOT is a graph description language that allows you to describe directed graphs in a simple text format. It's highly flexible and can be used to create various types of diagrams including flowcharts, network diagrams, and organizational charts.
        
        ### Technologies Used
        
        - **Streamlit**: For the web interface
        - **Graphviz**: For diagram rendering
        - **ReportLab**: For PDF generation
        - **PIL/Pillow**: For image processing
        
        ### Created By
        
        @ashusnapx
        """)

if __name__ == "__main__":
    main()
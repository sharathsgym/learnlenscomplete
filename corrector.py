import streamlit as st
from PIL import Image
import os
import json
from datetime import datetime
import pyodbc

# Base folder where images are stored
BASE_FOLDER = r"C:\Users\Admin\Downloads\ai_assess"

# Azure SQL Database connection settings from environment variables
SERVER = 'jskdsdj458.database.windows.net'
DATABASE = 'zxncbzxcb'
USERNAME = 'sharvas45'
PASSWORD = 'Demo@123'
DRIVER = 'ODBC Driver 18 for SQL Server'  # Ensure installed

def get_connection():
    """Create and return a database connection"""
    if 'db_conn' not in st.session_state:
        try:
            st.session_state.db_conn = pyodbc.connect(
                f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}')
        except Exception as e:
            st.error(f"Failed to connect to database: {e}")
            return None
    return st.session_state.db_conn

def close_connection():
    """Close the database connection if it exists"""
    if 'db_conn' in st.session_state:
        st.session_state.db_conn.close()
        del st.session_state.db_conn

def update_processed(school, program, cycle, question_no, selected_images, all_images):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        print(selected_images)
        f_selected_images = ','.join([f"'{img.replace('.jpg', '')}'" for img in selected_images])
        f_all_images = ','.join([f"'{img.replace('.jpg', '')}'" for img in all_images])

        query1 = f"""update ai_student_responses set is_correct=1
          where question_no='{question_no}' and program='{program}' and cycle='{cycle}' and student_id in ({f_selected_images})"""
        
        query2 = f"""update ai_student_responses set corrected_by_human=1
          where question_no='{question_no}' and program='{program}' and cycle='{cycle}' and student_id in ({f_all_images})"""

        if len(selected_images) > 0:
            cursor.execute(query1)

        if len(all_images) > 0:
            cursor.execute(query2)    
        cursor.commit()
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return 0

def get_images_from_db(school, program, cycle, question_no):
    try:
        conn = get_connection()    
        cursor = conn.cursor()
        query = """
            SELECT a.student_id
            FROM ai_student_responses a
            JOIN ai_student b
            ON a.student_id = b.id 
            where upper(a.question_no)=?
            and b.school= ?
            and a.program= ?
            and a.cycle= ?
            and a.requires_human =1
            and corrected_by_human is null
        """
        cursor.execute(query, (question_no, school, program, cycle))
        result = cursor.fetchall()
        return result
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return 0

# Configuration
st.set_page_config(
    page_title="LearnLens - Human in the Loop",
    page_icon="📚",
    layout="wide"
)

st.title("LearnLens - Human in the Loop")
st.markdown("Which of these student answers were correct?")

# Initialize session state
if "assessments" not in st.session_state:
    st.session_state["assessments"] = {}

# Sidebar filters
st.sidebar.header("🔍 Filter Options")
school = st.sidebar.selectbox("School", ["EP Nyakabanda1", "GS Gatare", "GS RWIMINAZI","GS GICACA","GS KAMASHASHI","Training School"])
program = st.sidebar.selectbox("Program", ["FM", "FR"])
cycle = st.sidebar.selectbox("Cycle", ["End of Cycle 5", "End of Cycle 6","Diagnostics","LearnLens Diagnostics"])
question_no = st.sidebar.selectbox("Question No", ["A", "B", "C", "D", "E","F", "G","H","I","J", "K","L","M","N","O","P","Q1.1","Q1.2","Q1.3","Q2.1","Q2.2","Q2.3","Q3.1","Q3.2","Q3.3","Q4.1","Q4.2","Q4.3","Q5","Q6.1","Q6.2","Q6.3","Q6.4","Q6.5"])

# Generate a unique session key for this image set
session_key = f"{program}_{cycle}_{school}_{question_no}"
image_folder = os.path.join(BASE_FOLDER, program, cycle, school, question_no)

# Add a clear selections button
if st.sidebar.button("🔄 Clear Selections"):
    if f"selected_{session_key}" in st.session_state:
        st.session_state[f"selected_{session_key}"] = []
        st.rerun()

# Button click sets a session flag
if st.sidebar.button("📁 Load Images", type="primary"):
    st.session_state["load_images"] = True
    st.session_state["image_folder"] = image_folder
    if f"selected_{session_key}" not in st.session_state:
        st.session_state[f"selected_{session_key}"] = []

# Only run this part if "Load Images" has been clicked
if st.session_state.get("load_images"):
    # Query database for images
    image_names = get_images_from_db(school, program, cycle, question_no)

    IMAGE_FOLDER = st.session_state["image_folder"]
    
    st.write(f"📂 **Image Directory:** `{IMAGE_FOLDER}`")

    if not os.path.exists(IMAGE_FOLDER):
        st.error(f"❌ The folder '{IMAGE_FOLDER}' does not exist.")
        st.info("💡 Please check if the folder structure matches the expected format.")
    else:
        image_names_set = {f"{name[0].lower()}.jpg" for name in image_names}
        print(image_names_set)
        image_files = sorted([
            f for f in os.listdir(IMAGE_FOLDER)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')) and f.lower() in image_names_set
        ])

        if not image_files:
            st.warning("⚠️ No images found in the selected folder.")
        else:
            # Initialize selected images in session state
            if f"selected_{session_key}" not in st.session_state:
                st.session_state[f"selected_{session_key}"] = []

            # Get current selections from session state
            current_selections = st.session_state[f"selected_{session_key}"]
            
            # Display current selection count
            st.info(f"📊 **Found {len(image_files)} images** | **Selected: {len(current_selections)}**")
            
            st.markdown("### 🖼️ Select the correct answer(s):")
            
            # SOLUTION 2: Use st.form to batch all checkbox updates
            with st.form("image_selection_form"):
                st.markdown("**Select images and click 'Update Selections' to apply changes**")
                
                # Store checkbox states
                checkbox_states = {}
                
                # Create image grid with checkboxes inside the form
                for i in range(0, len(image_files), 4):
                    row_images = image_files[i:i+4]
                    cols = st.columns(4)

                    for col, img_file in zip(cols, row_images):
                        with col:
                            try:
                                img_path = os.path.join(IMAGE_FOLDER, img_file)
                                image = Image.open(img_path)
                                
                                # Display image with border if currently selected
                                if img_file in current_selections:
                                    st.markdown(
                                        '<div style="border: 3px solid #00ff00; border-radius: 10px; padding: 5px; margin-bottom: 10px;">',
                                        unsafe_allow_html=True
                                    )
                                    st.image(image, use_container_width=True, caption=img_file)
                                    st.markdown('</div>', unsafe_allow_html=True)
                                else:
                                    st.image(image, use_container_width=True, caption=img_file)
                                
                                # Checkbox inside form - default to current selection state
                                checkbox_key = f"form_{session_key}_{img_file}"
                                checkbox_states[img_file] = st.checkbox(
                                    f"✅ Select" if img_file in current_selections else "Select",
                                    key=checkbox_key,
                                    value=(img_file in current_selections)
                                )
                                        
                            except Exception as e:
                                st.error(f"❌ Error loading image {img_file}: {str(e)}")

                # Form submit button
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    update_selections = st.form_submit_button("🔄 Update Selections", type="secondary", use_container_width=True)
                
                # Process form submission
                if update_selections:
                    # Update session state based on checkbox states
                    new_selections = [img for img, selected in checkbox_states.items() if selected]
                    st.session_state[f"selected_{session_key}"] = new_selections
                    
                    # Show update message
                    st.success(f"✅ Selections updated! Selected {len(new_selections)} images.")
                    st.rerun()  # Rerun to refresh the display with new selections

            # Display current selections outside the form
            if current_selections:
                st.markdown("### 🎯 Currently Selected Images:")
                selected_cols = st.columns(min(len(current_selections), 4))
                for idx, img_file in enumerate(current_selections):
                    with selected_cols[idx % 4]:
                        try:
                            img_path = os.path.join(IMAGE_FOLDER, img_file)
                            image = Image.open(img_path)
                            st.image(image, use_container_width=True, caption=f"✅ {img_file}")
                        except Exception as e:
                            st.error(f"Error loading {img_file}")

            # Submit Assessment section (outside the selection form)
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col2:
                if st.button("🚀 Submit Assessment", type="primary", use_container_width=True):
                    selected_images = st.session_state[f"selected_{session_key}"]
                    
                    # Store assessment result
                    assessment_data = {
                        "timestamp": datetime.now().isoformat(),
                        "school": school,
                        "program": program,
                        "cycle": cycle,
                        "question_no": question_no,
                        "selected_images": selected_images,
                        "total_images": len(image_files),
                        "all_images": image_files
                    }
                    
                    update_processed(school, program, cycle, question_no, selected_images, image_files)
                    st.session_state["assessments"][session_key] = assessment_data
                    
                    # Success message
                    st.success(f"🎉 Assessment submitted successfully!")
                    st.balloons()
                    
                    # Display results
                    with st.expander("📊 Assessment Results", expanded=True):
                        st.write(f"**📅 Submitted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write(f"**📝 Selected {len(selected_images)} out of {len(image_files)} images**")
                        
                        result_col1, result_col2 = st.columns(2)
                        with result_col1:
                            st.write("**🎯 Selected Images:**")
                            if selected_images:
                                for img in selected_images:
                                    st.write(f"- {img}")
                            else:
                                st.write("- None selected")
                        
                        with result_col2:
                            st.write("**📋 Assessment Details:**")
                            st.write(f"- **School:** {school}")
                            st.write(f"- **Program:** {program}")
                            st.write(f"- **Cycle:** {cycle}")
                            st.write(f"- **Question:** {question_no}")

            # Show assessment history
            if st.session_state["assessments"]:
                with st.expander("📚 Assessment History"):
                    for key, assessment in st.session_state["assessments"].items():
                        st.write(f"**{key}:** {len(assessment['selected_images'])} selected on {assessment['timestamp'][:19]}")
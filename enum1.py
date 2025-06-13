import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import pyodbc
import os


# Azure SQL Database connection settings from environment variables
SERVER = 'jskdsdj458.database.windows.net'
DATABASE = 'zxncbzxcb'
USERNAME = 'sharvas45'
PASSWORD = 'Demo@123'
DRIVER = 'ODBC Driver 18 for SQL Server'  # Ensure installed

# Initialize session state variables if they don't exist
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0
    
if "current_student" not in st.session_state:
    st.session_state.current_student = None
    
if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False
    
# IMPORTANT CHANGE: Initialize selections with a different format
if "selections" not in st.session_state:
    st.session_state.selections = {}
    
if "submit_clicked" not in st.session_state:
    st.session_state.submit_clicked = False

# Add debugging flag
if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = True

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

def load_image(url):
    """Load image from the internet"""
    try:
        response = requests.get(url)
        return Image.open(BytesIO(response.content))
    except Exception as e:
        st.error(f"Failed to load image: {e}")
        return None

def fetch_pending_count(school, program, cycle, s_class, sec):
    """Fetch count of pending evaluations using parameterized query"""
    try:
        conn = get_connection()
        if not conn:
            return 0
            
        cursor = conn.cursor()
        query = """
            SELECT COUNT(student_id) 
            FROM ai_student_levels 
            WHERE school = ? AND program = ? AND cycle = ? AND s_class = ? AND section = ?
            AND student_id NOT IN (
                SELECT student_id 
                FROM ai_evaluator_Responses 
                WHERE school = ? AND program = ? AND cycle = ?
            )
        """
        cursor.execute(query, (school, program, cycle, s_class, sec, school, program, cycle))
        result = cursor.fetchone()[0]
        return int(result)
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return 0

def get_next_student(school, program, cycle, s_class, sec):
    """Get the next student for evaluation using parameterized query"""
    try:
        conn = get_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        query = """
            SELECT TOP (1) student_id, program, cycle, school, s_class, section, image_url 
            FROM ai_student_levels 
            WHERE school = ? AND program = ? AND cycle = ? AND s_class = ? AND section = ?
            AND student_id NOT IN (
                SELECT student_id 
                FROM ai_evaluator_Responses 
                WHERE school = ? AND program = ? AND cycle = ?
            ) 
            ORDER BY NEWID();
        """
        cursor.execute(query, (school, program, cycle, s_class, sec, school, program, cycle))
        result = cursor.fetchone()
        
        if result:
            return {
                "student_id": result[0],
                "program": result[1],
                "cycle": result[2],
                "school": result[3],
                "s_class": result[4],
                "section": result[5],
                "image_url": result[6]
            }
        else:
            return None
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return None

def submit_evaluation(student_data, selections):
    """Submit the evaluation results using parameterized queries"""
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Prepare the query with parameters
        query = """
            INSERT INTO [dbo].[ai_evaluator_Responses]
            (student_id, question_no, evaluator_grading, program, cycle, school)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        
        # Execute for each question - different questions based on program
        if student_data["program"] == "FR":
            questions = [
                "q1.1", "q1.2", "q1.3", 
                "q2.1", "q2.2", "q2.3", 
                "q3.1", "q3.2", "q3.3", 
                "q4.1", "q4.2", "q4.3", 
                "q5", 
                "q6.1", "q6.2", "q6.3", "q6.4", "q6.5"
            ]
        else:  # FM program
            questions = [chr(i) for i in range(ord('A'), ord('P') + 1)]
        
        # Debug the selections dictionary if debug mode is on
        if st.session_state.debug_mode:
            st.write("Debug - Selections being submitted to database:", selections)
        
        # Track how many correct and incorrect answers
        correct_count = 0
        incorrect_count = 0
            
        for q in questions:
            # Check if the checkbox for this question is checked (correct)
            # Get value from the form data using the checkbox key format
            checkbox_key = f"check_{q}_{st.session_state.reset_counter}"
            
            # Get checkbox value directly from the session state
            is_correct = st.session_state.get(checkbox_key, True)
            
            # Set evaluator_grading based on checkbox state
            evaluator_grading = 1 if is_correct else 0
            
            if evaluator_grading == 1:
                correct_count += 1
            else:
                incorrect_count += 1
            
            if st.session_state.debug_mode:
                st.write(f"Debug - Question {q}: checkbox_key={checkbox_key}, is_correct={is_correct}, evaluator_grading={evaluator_grading}")
            
            # Execute the database insert
            cursor.execute(
                query, 
                (student_data["student_id"], q, evaluator_grading, 
                 student_data["program"], student_data["cycle"], student_data["school"])
            )
        
        conn.commit()
        
        # Show summary of what was inserted
        st.success(f"Evaluation submitted: {correct_count} correct answers, {incorrect_count} incorrect answers")
        return True
    except Exception as e:
        st.error(f"Failed to submit evaluation: {e}")
        return False

def load_next_student():
    """Load the next student based on current selections"""
    school = st.session_state.school
    program = st.session_state.program
    cycle = "End of Cycle 6"  # Fixed value
    s_class = st.session_state.s_class
    sec = st.session_state.section
    
    # Get next student
    next_student = get_next_student(school, program, cycle, s_class, sec)
    st.session_state.current_student = next_student
    
    # Reset form state
    st.session_state.form_submitted = False
    st.session_state.submit_clicked = False
    
    # Increment reset counter to force checkbox reinitialization
    st.session_state.reset_counter += 1

def on_form_submit():
    """Set the submit_clicked flag when form is submitted"""
    st.session_state.submit_clicked = True

def on_selectbox_change():
    """Handle changes to school/program/class/section selections"""
    # Reset current student when selections change
    st.session_state.current_student = None
    st.session_state.form_submitted = False
    st.session_state.submit_clicked = False
    st.session_state.reset_counter += 1

# Main app interface
st.title("Student Evaluation App")

# Add debug mode toggle at the top
debug_expander = st.expander("Debug Settings")
with debug_expander:
    st.session_state.debug_mode = st.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)

# Selection dropdowns
col1, col2 = st.columns(2)
with col1:
    st.selectbox(
        "Select School",
        ("EP Nyakabanda1", "GS Gatare", "GS Gicaca", "GS KAMASHASHI", "GS RWIMINAZI"),
        key="school",
        on_change=on_selectbox_change
    )
    
    st.selectbox(
        "Select Class",
        ("Primary 1", "Primary 2", "Primary 3"),
        key="s_class",
        on_change=on_selectbox_change
    )

with col2:
    st.selectbox(
        "Select Program",
        ("FR", "FM"),
        key="program",
        on_change=on_selectbox_change
    )
    
    st.selectbox(
        "Select Section",
        ("A", "B", "C", "D"),
        key="section",
        on_change=on_selectbox_change
    )

cycle = "End of Cycle 6"  # Fixed value

# Display header with current selections
st.header(f"{st.session_state.school}-{st.session_state.s_class}-{st.session_state.section}-{st.session_state.program}-{cycle}", divider="blue")

# Display count of pending evaluations
pending_count = fetch_pending_count(
    st.session_state.school, 
    st.session_state.program, 
    cycle, 
    st.session_state.s_class, 
    st.session_state.section
)

st.metric(label="Total Pending Evaluations", value=pending_count)

# Load initial student if none is loaded
if pending_count > 0 and st.session_state.current_student is None:
    if st.button("Start Evaluations"):
        load_next_student()

# Process form submission from previous render if needed
if st.session_state.submit_clicked and not st.session_state.form_submitted:
    if st.session_state.current_student:
        if submit_evaluation(st.session_state.current_student, st.session_state.selections):
            st.session_state.form_submitted = True
            # Load new student immediately for a better UX
            load_next_student()

# Display student information if available
if st.session_state.current_student:
    student = st.session_state.current_student
    
    left_col, right_col = st.columns([7, 3])
    
    with left_col:
        image = load_image(student["image_url"])
        if image:
            st.image(image, caption=f"Student-{student['student_id']}", width=500)
            st.info("Review the student's work. All answers are marked as correct by default. Uncheck any incorrect answers below.")
    
    with right_col:
        st.markdown("### Expected Answers:")
        
        # Display different answer tables based on program
        if student["program"] == "FR":
            table_md = """
            | Question | Answer    | Question | Answer |
            |----------|-----------|----------|--------|
            | q1.1     | bag       | q1.2     | pet    |
            | q1.3     | run       | q2.1     | rip    |
            | q2.2     | sash      | q2.3     | con    |
            | q3.1     | frog      | q3.2     | pan    |
            | q3.3     | rust      | q4.1     | plane  |
            | q4.2     | nap       | q4.3     | sold   |
            | q5       | The dock was busy with fishermen. | q6.1     | bike |
            | q6.2     | down      | q6.3     | sound |
            | q6.4     | warm      | q6.5     | water |
            """
        else:  # FM program
            table_md = """
            | Q - A       | Q - A    | Q - A | Q - A |
            |-------------|----------|-------|-------|
            | A - 000000  | B - 0000 | C - 8 | D - 2 |
            | E - 17      | F - 19   | G - 4 | H - 3 |
            | I - 18      | J - 19   | K - 12| L - 22|
            | M - option 2| N - 33   | O - 55| P - 79|
            """
        st.markdown(table_md)
    
    st.markdown("""
        :blue[**Instructions:**]
        - :green[✓] **Checked** boxes = CORRECT answers (grading value of 1)
        - :red[✗] **Unchecked** boxes = INCORRECT answers (grading value of 0)
        - All answers start as checked (correct) by default
    """)
    
    # Create a form to batch all the checkbox interactions
    form_key = f"eval_form_{st.session_state.reset_counter}"
    with st.form(key=form_key):
        if student["program"] == "FR":
            questions = [
                "q1.1", "q1.2", "q1.3", 
                "q2.1", "q2.2", "q2.3", 
                "q3.1", "q3.2", "q3.3", 
                "q4.1", "q4.2", "q4.3", 
                "q5", 
                "q6.1", "q6.2", "q6.3", "q6.4", "q6.5"
            ]
            # FR layout - using 3 columns
            cols = st.columns(3)
            for idx, q in enumerate(questions):
                with cols[idx % 3]:
                    subcols = st.columns([1.5, 2])
                    with subcols[0]:
                        st.markdown(f"**{q}**", unsafe_allow_html=True)
                    with subcols[1]:
                        # Use checkbox with unique key
                        checkbox_key = f"check_{q}_{st.session_state.reset_counter}"
                        # Check if key exists in session state, if not set default value to True
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = True
                        
                        st.checkbox("", key=checkbox_key)
        else:
            # FM layout - using 4 columns
            questions = [chr(i) for i in range(ord('A'), ord('P') + 1)]
            cols = st.columns(4)
            for idx, letter in enumerate(questions):
                with cols[idx % 4]:
                    subcols = st.columns([1, 3])
                    with subcols[0]:
                        st.markdown(f"**{letter}**", unsafe_allow_html=True)
                    with subcols[1]:
                        # Use checkbox with unique key
                        checkbox_key = f"check_{letter}_{st.session_state.reset_counter}"
                        # Check if key exists in session state, if not set default value to True
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = True
                            
                        st.checkbox("", key=checkbox_key)
        
        # Show what will be submitted before submission
        st.info("By submitting, you confirm that checked boxes = CORRECT answers (1), unchecked = INCORRECT (0)")
        
        # Submit button inside the form
        st.form_submit_button("Submit Evaluation", on_click=on_form_submit)

elif pending_count == 0:
    st.info("No more evaluations pending for selected criteria.")

# Clean up when the app is done
if st.button("Close Session"):
    close_connection()
    # Use a safer method than clearing all session state
    keys_to_clear = ["current_student", "form_submitted", "selections", 
                     "submit_clicked", "db_conn"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.success("Session closed successfully!")

# Add debug information at the bottom if debug mode is enabled
if st.session_state.debug_mode:
    st.divider()
    st.subheader("Debug Information")
    
    # Show the reset counter value
    st.write(f"Reset Counter: {st.session_state.reset_counter}")
    
    # Show checkbox state if we have a current student
    if st.session_state.current_student:
        st.write("Current Checkbox States:")
        
        if st.session_state.current_student["program"] == "FR":
            questions = [
                "q1.1", "q1.2", "q1.3", 
                "q2.1", "q2.2", "q2.3", 
                "q3.1", "q3.2", "q3.3", 
                "q4.1", "q4.2", "q4.3", 
                "q5", 
                "q6.1", "q6.2", "q6.3", "q6.4", "q6.5"
            ]
        else:
            questions = [chr(i) for i in range(ord('A'), ord('P') + 1)]
        
        # Display current checkbox states for debugging
        debug_data = {}
        for q in questions:
            checkbox_key = f"check_{q}_{st.session_state.reset_counter}"
            debug_data[q] = {
                "key": checkbox_key,
                "value": st.session_state.get(checkbox_key, "Not set"),
                "evaluator_grading": 1 if st.session_state.get(checkbox_key, True) else 0
            }
        
        st.json(debug_data)
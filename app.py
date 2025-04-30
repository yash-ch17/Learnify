import datetime
import os
from matplotlib import pyplot as plt
import streamlit as st
st.set_page_config(page_title="Learnify - AI Learning", layout="wide")
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv
from fpdf import FPDF
import base64
import smtplib
import time
from streamlit_cookies_manager import EncryptedCookieManager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from googleapiclient.discovery import build
import bcrypt
from streamlit_cookies_manager import EncryptedCookieManager
    
# Set page config FIRST before anything else

# Load environment variables
load_dotenv()

# Apply dark mode styling
def apply_custom_styles():
    background_color = "#f5f5dc"  # Beige
    text_color = "#000000"  # Black
    button_color = "#8b4513"  # SaddleBrown
    button_hover = "#a0522d"  # Sienna
    card_bg = "#fffaf0"  # FloralWhite
    box_shadow = "0px 6px 15px rgba(0, 0, 0, 0.15)"
    sidebar_bg = "#d2b48c"  # Tan
    input_border = "#8b4513"
    
    st.markdown(
        f"""
        <style>
        body, .stApp {{
            background-color: {background_color};
            color: {text_color};
        }}
        .stButton>button {{
            width: 100%;
            background: linear-gradient(90deg, {button_color}, {button_hover});
            color: white;
            border-radius: 12px;
            padding: 14px;
            font-size: 18px;
            border: none;
            transition: 0.3s;
            box-shadow: 0px 5px 10px rgba(0, 0, 0, 0.1);
        }}
        .stButton>button:hover {{
            background: linear-gradient(90deg, {button_hover}, {button_color});
        }}
        .stTextInput>div>div>input {{
            border-radius: 8px;
            padding: 12px;
            font-size: 16px;
            border: 1px solid {input_border};
            background: {card_bg};
            color: {text_color};
        }}
        .stMarkdown h1 {{
            text-align: center;
            color: {button_color};
            font-weight: 700;
        }}
        .login-container {{
            width: 420px;
            margin: auto;
            padding: 25px;
            background: {card_bg};
            border-radius: 12px;
            box-shadow: {box_shadow};
        }}
        .stSidebar {{  /* Sidebar background */
            background-color: {sidebar_bg} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

apply_custom_styles()


# Initialize cookies for session persistence
cookies = EncryptedCookieManager(prefix="learnify_", password="your_secure_password")
if not cookies.ready():
    st.stop()



# Fetch API key & email credentials
API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")  # Your Gmail address
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Your Gmail App Password
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
# Twilio credentials
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Ensure API key is available
if not API_KEY:
    st.error("🔴 API key is missing! Please check your .env file.")
    st.stop()

# Configure Gemini API
genai.configure(api_key=API_KEY)

# Use the latest supported model
MODEL_NAME = "gemini-1.5-pro"

# Initialize the database and ensure the users table exists
def initialize_database():
    with sqlite3.connect("learnify.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
            )
        ''')
        conn.commit()

initialize_database()

def initialize_learning_path_table():
    conn = sqlite3.connect("learnify.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            topic TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
initialize_learning_path_table()

def save_learning_path(username, topic, content):
    conn = sqlite3.connect("learnify.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO learning_paths (username, topic, content) VALUES (?, ?, ?)",
                   (username, topic, content))
    conn.commit()
    conn.close()

def init_todo_table():
    conn = sqlite3.connect("learnify.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            task TEXT NOT NULL,
            score INTEGER NOT NULL,
            done INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
init_todo_table()

def save_concept_card(username, concept, content):
    concept = concept.strip() if concept.strip() else "Untitled"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("learnify.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO concept_cards (username, concept, content, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (username, concept, content, timestamp))
    conn.commit()
    conn.close()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Function to verify password
def verify_password(password, hashed_password):
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False  # Handle cases where password is not properly hashed

# Function to authenticate user
def login(username, password):
    with sqlite3.connect("learnify.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

    if user and verify_password(password, user[2]):
        st.session_state["authenticated"] = True
        st.session_state["username"] = username
        cookies["username"] = username  # Store in cookies
        cookies.save()
        st.success("✅ Login successful! Redirecting...")
        time.sleep(1)
        st.rerun()  # This line reloads the app, which displays the main page if the user is authenticated
    else:
        st.error("❌ Incorrect username or password. Try again!")

# Function to register new user
def signup(username, password, mobile):
    with sqlite3.connect("learnify.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username= ?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            st.error("❌ Username already exists! Choose a different one.")
        else:
            hashed_password = hash_password(password)
            cursor.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, hashed_password, email))
            conn.commit()
            st.success("✅ Registration successful! Please login.")

# Ensure login page is shown first, without auto-login from cookies
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    cookies.pop("username", None)  # Clear stored session
    cookies.save()

# Function to logout
def logout():
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    cookies.pop("username", None)
    cookies.save()
    st.success("✅ Logged out successfully!")
    time.sleep(1)
    st.rerun()

import random
# Login/Signup Form
if not st.session_state.get("authenticated", False):
    st.markdown("<h1 class='main-title'>🔐 Learnify Login</h1>", unsafe_allow_html=True)
    choice = st.radio("Select an option", ["Login", "Sign Up"], horizontal=True)
    
    if choice == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            if username and password:
                login(username, password)
            else:
                st.warning("⚠ Please enter both username and password.")
        
        # 🔐 Forgot Password
        with st.expander("🔑 Forgot Password?"):
            email = st.text_input("Enter your registered email", key="forgot_email")
            
            if st.button("Send OTP", key="send_otp_btn"):
                if email:
                    # Generate OTP
                    otp = str(random.randint(100000, 999999))
                    st.session_state["reset_email"] = email
                    st.session_state["reset_otp"] = otp

                    try:
                        msg = MIMEText(f"Your Learnify OTP is: {otp}")
                        msg["Subject"] = "Learnify Password Reset"
                        msg["From"] = EMAIL_SENDER
                        msg["To"] = email

                        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                            server.send_message(msg)

                        st.success("✅ OTP sent to your email.")
                    except Exception as e:
                        st.error(f"❌ Failed to send email: {e}")
                else:
                    st.warning("⚠ Please enter your registered email.")

            if "reset_otp" in st.session_state:
                user_otp = st.text_input("Enter OTP received via email", key="otp_input")
                if st.button("Verify OTP"):
                    if str(user_otp).strip() == str(st.session_state["reset_otp"]).strip():
                        st.session_state["otp_verified"] = True
                        st.success("✅ OTP Verified! You can now reset your password.")
                    else:
                        st.error("❌ Invalid OTP.")

            if st.session_state.get("otp_verified"):
                new_pass = st.text_input("Enter new password", type="password", key="new_pass")
                confirm_pass = st.text_input("Confirm new password", type="password", key="confirm_pass")
                
                if st.button("Reset Password", key="reset_pass_btn"):
                    if new_pass == confirm_pass:
                        try:
                            # ✅ Hash the new password
                            hashed_new_pass = hash_password(new_pass)
                            
                            with sqlite3.connect("learnify.db") as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE users SET password = ? WHERE email = ?", 
                                            (hashed_new_pass, st.session_state["reset_email"]))
                                conn.commit()

                            st.success("✅ Password reset successfully!")

                            # Clear reset-related session state
                            for key in ["reset_email", "reset_otp", "otp_verified"]:
                                st.session_state.pop(key, None)

                        except Exception as e:
                            st.error(f"❌ Error resetting password: {e}")
                else:
                    st.error("❌ Passwords do not match.")

                
    elif choice == "Sign Up":
        new_username = st.text_input("Choose a Username")
        new_password = st.text_input("Choose a Password", type="password")
        email = st.text_input("Email Address")
            
        if st.button("Sign Up"):
            if new_username and new_password and email:
                signup(new_username, new_password, email)
            else:
                st.warning("⚠ Please fill all the fields.")

    st.stop()
    
# Sidebar with logout button
import streamlit as st
# Initialize session state variables for view tracking
if "current_view" not in st.session_state:
    st.session_state["current_view"] = "main"  # Default to main view

# Sidebar navigation and session management
with st.sidebar:
    if st.session_state.get("authenticated", False):
        st.write(f"👤 {st.session_state['username']}")

        col1, col2 = st.columns(2)  # Create two equal-width columns
        with col1:
            if st.button("📊 Dashboard"):
                st.session_state["current_view"] = "dashboard"
                 # Navigate to the dashboard view
        with col2:
            if st.button("🔴 Logout"):
                logout()

def get_user_email(username):
    try:
        with sqlite3.connect("learnify.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            return result[0] if result else "Not found"
    except Exception as e:
        return f"Error: {e}"
    
def send_email_reminder(user_email, subject, message):
    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = user_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        st.success(f"✅ Reminder sent to {user_email}")
    except Exception as e:
        st.error(f"❌ Failed to send email: {e}")

# Check the current view and display content accordingly
if "current_view" not in st.session_state:
    st.session_state["current_view"] = "dashboard"  # Default view
if "active_section" not in st.session_state:
    st.session_state["active_section"] = None
if "active_section" not in st.session_state:
    st.session_state["active_section"] = "dashboard"

# Main application loop
if st.session_state["current_view"] == "dashboard":
    # Sidebar navigation
    if st.sidebar.button("📧 Send Reminder"):
        st.session_state["active_section"] = "send_reminder"

    if st.sidebar.button("Saved Learning Path"):
        st.session_state["active_section"] = "saved_learning_path"
    
    if st.sidebar.button("Create Concept Card"):
        st.session_state["active_section"] = "Concept_Card"
    if st.sidebar.button("Return to Dash"):
        st.session_state["active_section"] = "Dash"
        
    # Dashboard Header and Content
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button("🏠 Main Page"):
            st.session_state["current_view"] = "main"  # Navigate back to main view
            st.rerun()  # Reload the page to go back to home

    username = st.session_state.get("username", "Unknown User")
    email = get_user_email(username)
    
    # Top-left: Username and Email
    with col1:
        st.markdown(f"""
            <div style="position: absolute; top: 0px; left: 15px; text-align: left;">
                <h5 style="margin: 0; font-weight: 600;">👤 {username}</h5>
                <p style="margin: 0; font-size: 14px;">📧 {email}</p>
            </div>
        """, unsafe_allow_html=True)
     
    
    # Display content based on the active section
    if st.session_state["active_section"] == "dashboard":
        st.markdown(
            """
            <div style="display: flex; justify-content: center; align-items: center; height: 40px;">
                <h3>Welcome to your dashboard!</h3>
            </div>
            """, unsafe_allow_html=True)

        # Optional: Include learning stats or quick actions here
        st.success("🧠 Learning stats and reminders go here!")
        
    if st.session_state["active_section"] == "send_reminder":
        username = st.session_state.get("username", "User ")
        user_email = get_user_email(username)

        st.markdown("## 🎯 Set Your Learning Goals")

        goal_type = st.selectbox("Choose Goal Type", ["Daily", "Weekly"])

        if goal_type == "Daily":
            daily_goal = st.number_input("Enter your daily study goal (in hours)", min_value=1, max_value=12)
            progress = st.number_input("Enter today's progress (in hours)", min_value=0, max_value=12)
            if st.button("Save Daily Goal"):
                st.success(f"✅ Daily goal of {daily_goal} hours saved.")
                if progress < daily_goal:
                    send_email_reminder(
                        user_email,
                        "⏰ Daily Study Goal Reminder",
                        f"Hey {username}, you set a goal of {daily_goal} hours today, but have only done {progress}. Keep going!"
                    )

        elif goal_type == "Weekly":
            weekly_goal = st.number_input("Enter your weekly study goal (in hours)", min_value=5, max_value=70)
            progress = st.number_input("Enter this week's progress (in hours)", min_value=0, max_value=70)
            if st.button("Save Weekly Goal"):
                st.success(f"✅ Weekly goal of {weekly_goal} hours saved.")
                if progress < weekly_goal:
                    send_email_reminder(
                        user_email,
                        "📬 Weekly Study Goal Reminder",
                        f"Hey {username}, you set a goal of {weekly_goal} hours this week, but have only done {progress}. Keep pushing!"
                    )
        else:
            st.error("❌ Email not found.")

    
    elif st.session_state["active_section"] == "saved_learning_path":
        st.markdown("## 📚 Saved Learning Paths")
        def load_saved_paths(username):
            conn = sqlite3.connect("learnify.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT id, topic, content, timestamp FROM learning_paths WHERE username = ? ORDER BY timestamp DESC", (username,))
            return cursor.fetchall()
        
        def delete_learning_path(path_id):
            conn = sqlite3.connect("learnify.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM learning_paths WHERE id = ?", (path_id,))
            conn.commit()

        saved_paths = load_saved_paths(st.session_state["username"])
        if saved_paths:
            for idx, (path_id, topic, content, timestamp) in enumerate(saved_paths):
                with st.expander(f"{idx+1}. {topic} — 🕒 {timestamp[:16]}"):
                    st.markdown(content)
                    col1, col2 = st.columns([5, 1])
                    with col2:
                        if st.button("🗑 Delete", key=f"delete_{path_id}"):
                            delete_learning_path(path_id)
                            st.success(f"Deleted learning path: {topic}")
                            st.rerun()
        else:
            st.info("No saved learning paths yet.")

    elif st.session_state["active_section"] == "Concept_Card":

        st.markdown("## 📝 Create Concept Card")
        concept = st.text_input("Enter the concept you want to learn about:")
        if st.button("Generate Concept Card"):
            if concept:
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(f"Create very crisp short revision for {concept}.")
                st.session_state["concept_card"] = response.text
                st.success("✅ Concept card generated!")
            else:
                st.warning("⚠ Please enter a valid concept.")

        # Display the concept card with card styling
        if "concept_card" in st.session_state:
            st.markdown("### 📄 Generated Concept Card:")
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 15px; 
                            box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-left: 6px solid #4CAF50;
                            font-family: 'Segoe UI', sans-serif;">
                    <p style="color: #333; font-size: 15px; line-height: 1.6;">{st.session_state["concept_card"]}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Save Concept Card"):
                save_concept_card(st.session_state["username"], concept, st.session_state["concept_card"])
                st.success("✅ Concept card saved!")

        def load_concept_cards(username):
            conn = sqlite3.connect("learnify.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("""
                    SELECT concept, content, timestamp FROM concept_cards 
                    WHERE username = ? ORDER BY timestamp DESC
                """, (username,))
            cards = cursor.fetchall()
            conn.close()
            return cards
            
        def delete_concept_card(username, concept, timestamp):
            concept = concept.strip() if concept.strip() else "Untitled"
            conn = sqlite3.connect("learnify.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concept_cards WHERE username = ? AND concept = ? AND timestamp = ?", 
                            (username, concept, timestamp))
            conn.commit()
            conn.close()

        cards = load_concept_cards(st.session_state["username"])
        if cards:
            st.markdown("### 📚 Saved Concept Cards")
            for i in range(0, len(cards), 2):
                col1, col2 = st.columns(2)
                for col, card in zip([col1, col2], cards[i:i+2]):
                    concept, content, timestamp = card
                    concept = concept.strip() if concept and concept.strip() else "Untitled"

                    with col:
                        with st.expander(f"📌 {concept}"):
                            st.markdown(
                                    f"""
                                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; 
                                                box-shadow: 0 2px 8px rgba(0,0,0,0.08); 
                                                font-family: 'Segoe UI', sans-serif;">
                                        <p style="color: #333; font-size: 14px; line-height: 1.6;">{content}</p>
                                        <div style="text-align: right; color: #888; font-size: 12px;">🕒 {timestamp}</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                            )
                            if st.button("❌ Delete", key=f"delete_{concept}_{timestamp}"):
                                delete_concept_card(st.session_state["username"], concept, timestamp)
                                st.success(f"'{concept}' deleted!")
                                st.rerun()
        else:
            st.info("No concept cards saved yet. Generate one to get started!")


    elif st.session_state["active_section"] == "Dash":
        st.markdown(
            """
            <div style="display: flex; justify-content: center; align-items: center; height: 40px;">
            <h3>Welcome to your dashboard!</h3>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("## 📝 Todo List")
        conn = sqlite3.connect("learnify.db", check_same_thread=False)
        cursor = conn.cursor()
        task = st.text_input("Enter a task:")
        score = st.number_input("Enter a score for the task:", min_value=1, max_value=5, value=1)

        if st.button("Add Task"):
            if task:
                cursor.execute("INSERT INTO todo (username, task, score) VALUES (?, ?, ?)", (username, task, score))
                conn.commit()
                st.success("✅ Task added!")
                st.rerun()        

        username = st.session_state.get("username", "default_user")
        cursor.execute("SELECT id, task, score, done FROM todo WHERE username = ?", (username,))
        tasks = cursor.fetchall()

        total_score = 0
        completed_score = 0
        completed_tasks = []

        st.subheader("📋 Your Tasks:")

        for task_id, task_text, score_val, done in tasks:
            col1, col2, col3 = st.columns([6, 1, 1])
            with col1:
                checkbox = st.checkbox(task_text, value=bool(done), key=task_id)
            with col2:
                st.write(f"⭐ {score_val}")
            with col3:
                if st.button("🗑", key=f"delete_{task_id}"):
                    cursor.execute("DELETE FROM todo WHERE id=?", (task_id,))
                    conn.commit()
                    st.rerun()

            # Update completion status in DB if changed
            if checkbox != bool(done):
                cursor.execute("UPDATE todo SET done=? WHERE id=?", (int(checkbox), task_id))
                conn.commit()

            total_score += score_val
            if checkbox:
                completed_score += score_val
                completed_tasks.append((task_text, score_val))

        # Display only once
        if total_score > 0:
            st.subheader("📊 Task Completion Overview")
            st.markdown(f"**🎯 Total Score:** {total_score} | ✅ Completed: {completed_score} | ⏳ Pending: {total_score - completed_score}")

            if completed_tasks:
                # Plot completed tasks directly
                task_names = [task for task, _ in completed_tasks]
                task_scores = [score for _, score in completed_tasks]

                fig, ax = plt.subplots(figsize=(8, 5))
                ax.bar(task_names, task_scores, color="#4CAF50")

                ax.set_xlabel("Courses Completed", fontsize=12)
                ax.set_ylabel("Difficulty Level", fontsize=12)
                ax.set_title("📈 Completed Tasks vs Difficulty", fontsize=14)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()

                st.pyplot(fig)
            else:
                st.info("✅ No tasks completed yet. Complete some tasks to visualize them.")
        else:
            st.warning("⚠ No tasks found. Please add some tasks first!")

                
else:
# Main Title
    st.markdown(
        """
        <h1 style='text-align: center; color: #ff6a00;'>🚀 Learnify - AI-Powered Personalized Learning</h1>
        <p style='text-align: center; font-size: 18px;'>
            Find the best courses tailored to your interests and boost your learning journey! 📚✨
        </p>
        """,
        unsafe_allow_html=True
    )


    # Initialize session state variables
    if "courses" not in st.session_state:
        st.session_state["courses"] = []
    if "saved_courses" not in st.session_state:
        st.session_state["saved_courses"] = []
    if "learning_path" not in st.session_state:
        st.session_state["learning_path"] = ""
    if "assignments" not in st.session_state:
        st.session_state["assignments"] = ""

    # Function to get AI course recommendations
    def get_ai_recommendations(interest):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(
                f"List five recommended courses on {interest}. Format each course as follows:\n"
                "Course Title\n"
                "- Short Description (maximum 5 lines, without any links)\n"
                "- Platform (Coursera, Udemy, edX, etc.) with a relevant link"
            )
            return response.text.strip().split("\n\n")
        except Exception as e:
            return [f"Error fetching recommendations: {e}"]
        

    import googleapiclient.discovery
    # Function to fetch YouTube videos
    def get_youtube_video(query):
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        # Search for videos related to the query
        search_response = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=5,
            order="relevance"
        ).execute()

        # Extract video information
        videos = [
            {
                "title": item["snippet"]["title"],
                "video_id": item["id"]["videoId"]
            }
            for item in search_response.get("items", [])
        ]

        return videos


          # Function to send email
    def send_email(user_email, courses):
        try:
            if not EMAIL_SENDER or not EMAIL_PASSWORD:
                st.error("❌ Email sender credentials are missing.")
                return False
            
            msg = MIMEMultipart()
            msg["From"] = EMAIL_SENDER
            msg["To"] = user_email
            msg["Subject"] = "📌 Your Saved Courses from Learnify"
            body = f"Hello,\n\nHere are your saved courses:\n\n" + "\n".join([f"- {course}" for course in courses]) + "\n\nHappy Learning!\nLearnify Team 🚀"
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.send_message(msg)
            
            return True
        except Exception as e:
            st.error(f"❌ Failed to send email: {e}")
            return False

    # Layout Sections
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🔍 Enter Your Learning Interest:")
        interest = st.text_input("Enter your learning interest", placeholder="e.g., Python, AI, Web Development", label_visibility="hidden")

        if st.button("📚 Generate Learning Path"):
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(f"Create a structured learning roadmap for {interest}.")
            st.session_state["learning_path"] = response.text

        if st.session_state.get("learning_path"):
            st.subheader("📖 Your Generated Learning Path:")
            st.write(st.session_state["learning_path"])
            
            seelp = st.checkbox(
                "💰 Click on the Checkbox to save your LEARNING PATH",
                value=False,
                help="Check this box to enable saving your personalized learning path.",
            )
            
            # Topic name input for saving
            if seelp:
                st.text_input("📝 Name this learning path:", key="topic_name", placeholder="e.g., AI Roadmap")
                with col1:
                    if st.button("💾 Save Learning Path"):
                        if "username" not in st.session_state or not st.session_state["username"]:
                            st.warning("⚠ Please log in to save your learning path.")
                        elif not st.session_state.get("topic_name"):
                            st.warning("⚠ Please enter a topic name before saving.")
                        else:
                            save_learning_path(
                                username=st.session_state["username"],
                                topic=st.session_state["topic_name"],
                                content=st.session_state["learning_path"]
                            )
                            st.success(f"✅ Learning path '{st.session_state['topic_name']}' saved!")

           
            see_paid = st.checkbox("💰 Do you want to see paid courses for more reference?", value=False)
            if see_paid:
                if st.button("🎓 Find Courses"):
                    if interest.strip():
                        recommendations = get_ai_recommendations(interest)
                        if recommendations and isinstance(recommendations, list):
                            st.session_state["courses"] = recommendations
                        else:
                            st.session_state["courses"] = []

                    if st.session_state["courses"]:
                        st.subheader(f"📘 Recommended Courses for {interest}:")
                        for course in st.session_state["courses"]:
                            st.write(f"🔹 {course}")
                    else:
                        st.warning("⚠ No courses found. Please try a different interest.")

                    user_email = st.text_input("📩 Enter your email to save courses")
                    if st.button("📌 Save & Email Courses"):
                        if user_email.strip():
                            if send_email(user_email, st.session_state["courses"]):
                                st.success(f"✅ Courses sent to {user_email} successfully!")
                        else:
                            st.warning("⚠ Please enter a valid email address.")
                            
            
    with col2:
        st.subheader("🎥 Video Learning")
        user_prompt = st.text_input("Enter a topic to explore:", placeholder="e.g., How to Write Code")

        # Initialize session state for videos and ratings if not already done
        if 'videos' not in st.session_state:
            st.session_state.videos = []
            st.session_state.ratings = []

        if st.button("Find Video"):
            if user_prompt:
                st.session_state.videos = get_youtube_video(user_prompt)
                st.session_state.ratings = [0] * len(st.session_state.videos)  # Reset ratings for new videos
            else:
                st.warning("⚠ Please enter a valid topic.")

        # Display videos and ratings
        if st.session_state.videos:
            for idx, video in enumerate(st.session_state.videos):
                st.markdown(f"### 📹 {video['title']}")
                st.video(f"https://www.youtube.com/watch?v={video['video_id']}")
                
                # Create a slider for rating, maintaining the current rating in session state
                rating = st.slider(
                    f"Rate this video (1-5):",
                    1, 5,
                    key=f"rating_{idx}",
                    value=st.session_state.ratings[idx]  # Use the stored rating
                )
                st.session_state.ratings[idx] = rating  # Update the rating in session state
                st.write(f"⭐ Your rating: {rating}")
       
    # Sidebar - AI Chatbot
    st.sidebar.header("💬 Ask Learnify AI")
    chat_query = st.sidebar.text_input("Ask about a course...")
    if st.sidebar.button("Ask AI"):
        if chat_query.strip():
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(f"Give guidance on {chat_query} learning paths.")
            st.sidebar.write(f"🤖 AI: {response.text}")

    
    # PDF Generation Function
    def generate_pdf(interest, courses, learning_path, filename):
        """Generate a PDF containing only the learning path with proper formatting."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title Section
        pdf.set_font("Times", "B", 18)
        pdf.cell(200, 10, f"Learning Path for {interest}", ln=True, align="C")
        pdf.ln(10)

        # Learning Path Section
        pdf.set_font("Times", "B", 14)
        pdf.cell(0, 10, "Personalized Learning Path:", ln=True, align="L")
        pdf.ln(5)

        pdf.set_font("Times", "", 12)
        if learning_path:
            pdf.multi_cell(0, 10, learning_path, align="L")
        else:
            pdf.cell(0, 10, "No learning path available.", ln=True)
        pdf.ln(10)

        # Footer
        pdf.set_font("Times", "I", 10)
        pdf.cell(0, 10, "Generated by Learnify AI | 2025", ln=True, align="C")

        # Save PDF
        pdf_path = f"{filename.strip()}.pdf"
        pdf.output(pdf_path, "F")
        return pdf_path

    
    # Function to generate assignments
  
    # Function to generate assignments
    def generate_assignment(topic):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(f"Generate an assignment on {topic} with questions and tasks.")
            return response.text
        except Exception as e:
            st.error(f"❌ Error generating assignment: {e}")
            return ""
        
    def generate_pdf(interest, learning_path, filename):
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title Section
        pdf.set_font("Times", "B", 18)
        pdf.cell(200, 10, f"Learning Path for {interest}", ln=True, align="C")
        pdf.ln(10)

        # Learning Path Section
        pdf.set_font("Times", "B", 14)
        pdf.cell(0, 10, "Personalized Learning Path:", ln=True, align="L")
        pdf.ln(5)

        pdf.set_font("Times", "", 12)
        if learning_path:
            pdf.multi_cell(0, 10, learning_path, align="L")
        else:
            pdf.cell(0, 10, "No learning path available.", ln=True)
        pdf.ln(10)

        # Footer
        pdf.set_font("Times", "I", 10)
        pdf.cell(0, 10, "Generated by Learnify AI | 2025", ln=True, align="C")

        # Save PDF
        pdf_path = f"{filename.strip()}.pdf"
        pdf.output(pdf_path, "F")
        return pdf_path
    
    # Layout Section for Assignment Generation
    st.sidebar.header("📄 Assignment & Quiz Generator")
    topic = st.sidebar.text_input("Enter the topic for the assignment:")
    if st.sidebar.button("Generate Assignment"):
        if topic.strip():
            assignment = generate_assignment(topic)
            if assignment:
                #st.sidebar.subheader("Generated Assignment:")
                #st.sidebar.write(assignment)

                # Generate PDF
                pdf_filename = f"assignment_{topic.replace(' ', '_')}"
                pdf_path = generate_pdf(topic, assignment, pdf_filename)

                # Create a download link for the PDF
                with open(pdf_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="{pdf_filename}.pdf">📥 Download Assignment as PDF</a>'
                st.sidebar.markdown(href, unsafe_allow_html=True)

                # Optionally, you can delete the PDF file after download
                os.remove(pdf_path)
            else:
                st.sidebar.warning("⚠ No assignment generated. Please try again.")
        else:
            st.sidebar.warning("⚠ Please enter a topic for the assignment.")
        

    # Function to generate notes
    def generate_notes(interest):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(f"Generate detailed notes on {interest}.")
            return response.text
        except Exception as e:
            st.error(f"❌ Error generating notes: {e}")
            return ""

    # Notes Generation Section
    st.sidebar.header("📝 Notes Generator")
    notes_interest = st.sidebar.text_input("Enter the topic for notes:")
    if st.sidebar.button("Generate Notes"):
        if notes_interest.strip():
            notes = generate_notes(notes_interest)
            if notes:
                # Generate PDF for Notes
                pdf_filename = f"notes_{notes_interest.replace(' ', '_')}.pdf"
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, f"Notes on {notes_interest}", ln=True, align="C")
                pdf.ln(10)
                pdf.set_font("Arial", "", 12)
                pdf.multi_cell(0, 10, notes.encode('latin1', 'replace').decode('latin1'))
                pdf.output(pdf_filename, "F")

                # Create a download link for the PDF
                with open(pdf_filename, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="{pdf_filename}">📥 Download Notes as PDF</a>'
                st.sidebar.markdown(href, unsafe_allow_html=True)

                # Optionally, delete the PDF file after download
                os.remove(pdf_filename)
            else:
                st.sidebar.warning("⚠ No notes generated. Please try again.")
        else:
            st.sidebar.warning("⚠ Please enter a topic for the notes.")

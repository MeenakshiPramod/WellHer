


import os
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import datetime
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import requests
from io import BytesIO
import hashlib

load_dotenv()

# Load environment variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-pro')

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

st.set_page_config(
    page_title="WellHer - Women's Health Companion",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("style.css")

# Authentication Functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    hashed_pw = hash_password(password)
    try:
        response = supabase.table('users').insert({
            'username': username,
            'password_hash': hashed_pw,
            'created_at': str(datetime.datetime.now())
        }).execute()
        return True if not response.error else False
    except Exception as e:
        st.error(f"Error creating user: {str(e)}")
        return False

def verify_user(username, password):
    hashed_pw = hash_password(password)
    try:
        response = supabase.table('users').select('*').eq('username', username).eq('password_hash', hashed_pw).execute()
        return len(response.data) > 0
    except Exception as e:
        st.error(f"Error verifying user: {str(e)}")
        return False

def save_user_data(table, data):
    data['user_id'] = st.session_state['user_id']
    data['logged_at'] = str(datetime.datetime.now())
    try:
        supabase.table(table).insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

def load_user_data(table):
    try:
        response = supabase.table(table).select('*').eq('user_id', st.session_state['user_id']).execute()
        return response.data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return []

# Initialize Session State
def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_id = None
    
    # Initialize data structures
    if 'health_logs' not in st.session_state:
        st.session_state.health_logs = pd.DataFrame(columns=['Date', 'Blood Pressure', 'Sugar Level', 'Cholesterol'])
    
    if 'calorie_data' not in st.session_state:
        st.session_state.calorie_data = {
            'intake': 0,
            'burned': 0,
            'goal': 1800
        }
    
    if 'pcod_data' not in st.session_state:
        st.session_state.pcod_data = {
            'diagnosed': False,
            'weight': None,
            'height': None,
            'symptoms': [],
            'goals': []
        }
    
    if 'food_logs' not in st.session_state:
        st.session_state.food_logs = []

init_session_state()

# AI Helper Functions (unchanged from your original code)
def analyze_food_image(image):
    """Analyze food image using Gemini and return nutritional info and suggestions."""
    prompt = """
    You are a nutritionist analyzing a food photo. Perform these tasks:
    1. Identify the food items
    2. Estimate total calories
    3. Estimate macronutrients (protein, carbs, fat)
    4. Assess nutritional balance
    5. Suggest healthier substitutes or additions to make it a balanced meal
    
    Return in this JSON format:
    {
        "food_items": [list],
        "calories": number,
        "protein": number,
        "carbs": number,
        "fat": number,
        "balance_rating": "Poor/Average/Good/Excellent",
        "suggestions": [list of suggestions]
    }
    """
    response = model.generate_content([prompt, image])
    try:
        # Extract JSON from the response
        response_text = response.text.replace('```json', '').replace('```', '').strip()
        return eval(response_text)
    except:
        return {
            "food_items": ["Food analysis failed"],
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "balance_rating": "Unknown",
            "suggestions": ["Please try again or enter manually"]
        }

def get_pcod_advice(user_data):
    """Get personalized PCOD advice based on user data."""
    prompt = f"""
    You are a women's health specialist. A user with PCOD has provided this information:
    {user_data}
    
    Provide comprehensive advice for PCOD reversal including:
    - Dietary recommendations tailored to their calorie balance
    - Exercise suggestions
    - Lifestyle changes
    - Supplement ideas (if any)
    - Stress management techniques
    
    Format your response with clear headings and bullet points.
    """
    response = model.generate_content(prompt)
    return response.text

def get_health_insights(health_data):
    """Get health insights based on logged metrics."""
    prompt = f"""
    Analyze this health data and provide personalized recommendations:
    {health_data}
    
    Focus on:
    - Blood pressure analysis
    - Blood sugar analysis
    - Cholesterol analysis
    - Overall health assessment
    - Specific actionable recommendations
    
    Format as bullet points with emojis for readability.
    """
    response = model.generate_content(prompt)
    return response.text

# Authentication UI
def show_auth():
    st.title("🌸 Welcome to WellHer")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.info("Sample Guest Login:\n\n**Username:** guest\n   **Password:** guest1")
        with st.form("login_form"):
            st.subheader("Login to Your Account")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login"):
                if verify_user(username, password):
                    st.session_state.authenticated = True
                    st.session_state.user_id = username
                    # Load user data
                    health_data = load_user_data('health_logs')
                    if health_data:
                        st.session_state.health_logs = pd.DataFrame(health_data)
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("Create New Account")
            new_username = st.text_input("Choose a Username")
            new_password = st.text_input("Choose a Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            if st.form_submit_button("Register"):
                if new_password != confirm_password:
                    st.error("Passwords don't match!")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    if create_user(new_username, new_password):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username already exists")

# Main App Pages (unchanged from your original code)
def render_health_dashboard():
    st.title(f"🌸 Welcome back, {st.session_state.user_id}!")
    st.markdown("""
    <div class="welcome-box">
        <h3>Your Personal Health Dashboard</h3>
        <p>Track your nutrition, manage PCOD symptoms, and achieve your health goals</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick Stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Today's Calories", f"{st.session_state.calorie_data['intake']} kcal")
    col2.metric("Calories Burned", f"{st.session_state.calorie_data['burned']} kcal")
    net_calories = st.session_state.calorie_data['intake'] - st.session_state.calorie_data['burned']
    status = "normal" if net_calories <= st.session_state.calorie_data['goal'] else "inverse"
    col3.metric("Net Calories", f"{net_calories} kcal", delta_color=status)
    
    # Health Summary
    if not st.session_state.health_logs.empty:
        latest_log = st.session_state.health_logs.iloc[-1]
        st.subheader("Latest Health Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Blood Pressure", f"{latest_log['blood_pressure']} mmHg", 
                   "Normal" if latest_log['blood_pressure'] <= 120 else "Elevated")
        col2.metric("Sugar Level", f"{latest_log['sugar_level']} mg/dL", 
                   "Normal" if latest_log['sugar_level'] <= 100 else "High")
        col3.metric("Cholesterol", f"{latest_log['cholesterol']} mg/dL", 
                   "Normal" if latest_log['cholesterol'] <= 200 else "High")
    
    # Health Trend Visualization
    if len(st.session_state.health_logs) > 1:
        st.subheader("Health Trends")
        fig = px.line(st.session_state.health_logs, x='Date', y=['Blood Pressure', 'Sugar Level', 'Cholesterol'],
                     markers=True, title="Your Health Metrics Over Time")
        st.plotly_chart(fig, use_container_width=True)


def render_calorie_dashboard():
    st.title("🍽️ Calorie Log History")

    # Fetch food logs from Supabase for the current user
    food_logs = load_user_data('food_logs')

    if not food_logs or len(food_logs) == 0:
        st.info("No food logs found.")
        return

    # Convert to DataFrame for display
    df = pd.DataFrame(food_logs)

    # Try to parse date/time for sorting if available
    if 'logged_at' in df.columns:
        df['logged_at'] = pd.to_datetime(df['logged_at'])
        df = df.sort_values(by='logged_at', ascending=False)

    st.subheader("Your Food & Calorie History")
    st.dataframe(df, hide_index=True)

    # Show summary statistics if columns exist
    if 'calories' in df.columns:
        total_calories = df['calories'].sum()
        st.metric("Total Calories Logged", f"{total_calories} kcal")

    if 'food_name' in df.columns and 'logged_at' in df.columns:
        st.subheader("Most Recent Meals")
        st.write(df[['logged_at', 'food_name', 'calories']].head(10))
    elif 'food' in df.columns and 'logged_at' in df.columns:
        st.subheader("Most Recent Meals")
        st.write(df[['logged_at', 'food', 'calories']].head(10))

def render_food_analysis():
    st.title("📷 AI Food Analysis")
    st.markdown("Take a photo of your meal and get instant nutritional analysis")
    
    # Food photo input
    uploaded_file = st.file_uploader("Upload Food Photo", type=["jpg", "jpeg", "png"])
    col1, col2 = st.columns(2)
    analysis_result = None
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        col1.image(image, caption="Your Meal", width=300)
        
        if col2.button("Analyze with AI"):
            with st.spinner("AI is analyzing your meal..."):
                analysis_result = analyze_food_image(image)
                
            if analysis_result:
                st.success("Analysis Complete!")
                
                # Display results
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Calories", analysis_result['calories'])
                col2.metric("Protein", f"{analysis_result['protein']}g")
                col3.metric("Carbs", f"{analysis_result['carbs']}g")
                col4.metric("Fat", f"{analysis_result['fat']}g")
                
                st.subheader("Meal Balance")
                rating = analysis_result['balance_rating']
                color = "red" if rating == "Poor" else "orange" if rating == "Average" else "green" if rating == "Good" else "blue"
                st.markdown(f"<div class='rating-badge {color}'>{rating}</div>", unsafe_allow_html=True)
                
                st.subheader("Improvement Suggestions")
                for suggestion in analysis_result['suggestions']:
                    st.markdown(f"- {suggestion}")
                
                # Save to session and database
                st.session_state.calorie_data['intake'] += analysis_result['calories']
                food_entry = {
                    'time': datetime.datetime.now().strftime("%H:%M"),
                    'food': ", ".join(analysis_result['food_items']),
                    'calories': analysis_result['calories']
                }
                st.session_state.food_logs.append(food_entry)
                save_user_data('food_logs', food_entry)
    
    # Manual calorie entry
    with st.expander("Or enter manually"):
        food_name = st.text_input("Food Name")
        calories = st.number_input("Calories", min_value=0, value=300)
        if st.button("Add to Daily Log"):
            st.session_state.calorie_data['intake'] += calories
            food_entry = {
                'time': datetime.datetime.now().strftime("%H:%M"),
                'food': food_name,
                'calories': calories
            }
            st.session_state.food_logs.append(food_entry)
            save_user_data('food_logs', food_entry)
            st.success("Food added to your log!")
    
    # Today's food log
    if st.session_state.food_logs:
        st.subheader("Today's Food Log")
        food_df = pd.DataFrame(st.session_state.food_logs)
        st.dataframe(food_df, hide_index=True)

def render_pcod_assistant():
    st.title("🌸 PCOD Reversal Assistant")
    
    # PCOD Information Form
    with st.expander("Tell us about your PCOD journey", expanded=True):
        with st.form("pcod_form"):
            st.subheader("Your PCOD Profile")
            diagnosed = st.selectbox("Have you been diagnosed with PCOD?", ["Yes", "No", "Not Sure"])
            weight = st.number_input("Current Weight (kg)", min_value=30, max_value=200, value=65)
            height = st.number_input("Height (cm)", min_value=100, max_value=200, value=160)
            symptoms = st.multiselect("Which symptoms do you experience?",
                                    ["Irregular periods", "Weight gain", "Acne", 
                                     "Excess hair growth", "Hair loss", "Mood swings"])
            goals = st.multiselect("Your primary goals",
                                  ["Weight loss", "Regular periods", "Hormone balance", 
                                   "Symptom reduction", "Improved fertility"])
            
            submitted = st.form_submit_button("Save Profile")
            
            if submitted:
                pcod_data = {
                    'diagnosed': diagnosed,
                    'weight': weight,
                    'height': height,
                    'symptoms': symptoms,
                    'goals': goals
                }
                st.session_state.pcod_data = pcod_data
                save_user_data('pcod_profiles', pcod_data)
                st.success("PCOD profile saved!")
    
    # PCOD Dashboard
    if st.session_state.pcod_data['diagnosed']:
        st.subheader("Your PCOD Health Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Weight", f"{st.session_state.pcod_data['weight']} kg")
        col2.metric("Height", f"{st.session_state.pcod_data['height']} cm")
        bmi = st.session_state.pcod_data['weight'] / ((st.session_state.pcod_data['height']/100) ** 2)
        col3.metric("BMI", f"{bmi:.1f}", "Healthy" if 18.5 <= bmi <= 24.9 else "Needs improvement")
        
        # Calorie management
        st.subheader("Calorie Management")
        col1, col2 = st.columns(2)
        with col1:
            intake = st.number_input("Calories Consumed (kcal)", min_value=0, value=st.session_state.calorie_data['intake'])
        with col2:
            burned = st.number_input("Calories Burned (kcal)", min_value=0, value=st.session_state.calorie_data['burned'])
        
        if st.button("Update Calories"):
            st.session_state.calorie_data['intake'] = intake
            st.session_state.calorie_data['burned'] = burned
            save_user_data('calorie_tracking', st.session_state.calorie_data)
        
        # PCOD Advice
        if st.button("Get Personalized PCOD Advice"):
            user_data = {
                "profile": st.session_state.pcod_data,
                "calorie_balance": {
                    "intake": st.session_state.calorie_data['intake'],
                    "burned": st.session_state.calorie_data['burned'],
                    "net": st.session_state.calorie_data['intake'] - st.session_state.calorie_data['burned']
                }
            }
            
            with st.spinner("Generating personalized advice..."):
                advice = get_pcod_advice(user_data)
                st.markdown("### 🧠 Your Personalized PCOD Plan")
                st.markdown(advice)

def render_health_logs():
    st.title("📊 Health Logs")
    
    # Log Health Metrics
    with st.form("health_log_form"):
        st.subheader("Log New Health Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            bp = st.number_input("Blood Pressure (mmHg)", min_value=50, max_value=200, value=120)
        with col2:
            sugar = st.number_input("Sugar Level (mg/dL)", min_value=50, max_value=300, value=100)
        with col3:
            cholesterol = st.number_input("Cholesterol (mg/dL)", min_value=100, max_value=300, value=200)
        
        submitted = st.form_submit_button("Save Log")
        
        if submitted:
            new_log = {
                'Date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                'Blood Pressure': bp,
                'Sugar Level': sugar,
                'Cholesterol': cholesterol
            }
            st.session_state.health_logs = pd.concat(
                [st.session_state.health_logs, pd.DataFrame([new_log])],
                ignore_index=True
            )
            save_user_data('health_logs', {
                'blood_pressure': bp,
                'sugar_level': sugar,
                'cholesterol': cholesterol,
                'date': new_log['Date']
            })
            st.success("Health metrics logged!")
    
    # View History
    if not st.session_state.health_logs.empty:
        st.subheader("Health History")
        st.dataframe(st.session_state.health_logs)
        
        # Get AI Insights
        if st.button("Get Health Insights"):
            with st.spinner("Analyzing your health data..."):
                insights = get_health_insights(st.session_state.health_logs.to_dict())
                st.markdown("### 🩺 AI Health Analysis")
                st.markdown(insights)

# Main App Flow
def main():
    if not st.session_state.authenticated:
        show_auth()
    else:
        # Sidebar Navigation
        st.sidebar.title(f"🌸 {st.session_state.user_id}")
        menu = ["Health Dashboard", "Food Analysis", "PCOD Assistant", "Health Logs"]
        choice = st.sidebar.selectbox("Menu", menu)
        
        # Add logout button
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()
        
        # Page routing
        if choice == "Health Dashboard":
            render_health_dashboard()
            render_calorie_dashboard()
        elif choice == "Food Analysis":
            render_food_analysis()
        elif choice == "PCOD Assistant":
            render_pcod_assistant()
        elif choice == "Health Logs":
            render_health_logs()
        
        # Sidebar additional features
        st.sidebar.markdown("---")
        st.sidebar.subheader("Daily Goals")
        calorie_goal = st.sidebar.slider("Calorie Goal (kcal)", 1200, 3000, st.session_state.calorie_data['goal'])
        st.session_state.calorie_data['goal'] = calorie_goal
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("Calorie Burn Tracker")
        exercise = st.sidebar.selectbox("Activity", ["Walking", "Running", "Cycling", "Yoga", "Swimming"])
        duration = st.sidebar.slider("Duration (minutes)", 0, 120, 30)
        if st.sidebar.button("Add Exercise"):
            calories_burned = duration * 5  # 5 kcal per minute average
            st.session_state.calorie_data['burned'] += calories_burned
            save_user_data('calorie_tracking', st.session_state.calorie_data)
            st.sidebar.success(f"Added {calories_burned} kcal burned!")

if __name__ == "__main__":
    main()
import streamlit as st
import pandas as pd
import uuid
import os
import json
import time
from datetime import datetime
from utils.firecrawl_utils import fetch_regulation_data
from utils.cerebras_utils import process_with_llama_scout
from utils.regulation_utils import extract_relevant_regulations
from utils.logger import log_query, load_log_data, initialize_log_file
from utils.mcp_handler import MCPHandler
from config import (
    FIRECRAWL_API_KEY,
    CEREBRAS_API_KEY,
    REGULATORY_WEBSITES,
    LOG_FILE_PATH,
    LEARNING_CACHE_PATH,
)

# Set page configuration
st.set_page_config(
    page_title="Auto Regulation Advisor",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state variables if they don't exist
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "learning_cache" not in st.session_state:
    if os.path.exists(LEARNING_CACHE_PATH):
        with open(LEARNING_CACHE_PATH, "r") as f:
            st.session_state.learning_cache = json.load(f)
    else:
        st.session_state.learning_cache = {"query_patterns": {}, "website_success_rates": {}}

# Initialize MCP handler
mcp_handler = MCPHandler()

# Initialize log file if it doesn't exist
initialize_log_file(LOG_FILE_PATH)

# Custom CSS for the app
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #E5E7EB;
        border-left: 5px solid #1E3A8A;
    }
    .assistant-message {
        background-color: #F3F4F6;
        border-left: 5px solid #10B981;
    }
    .message-content {
        display: flex;
        flex-direction: row;
    }
    .message-text {
        flex: 1;
    }
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        margin-right: 1rem;
        font-size: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .user-avatar {
        background-color: #1E3A8A;
        color: white;
    }
    .assistant-avatar {
        background-color: #10B981;
        color: white;
    }
    .source-link {
        font-size: 0.8rem;
        color: #6B7280;
        margin-top: 0.5rem;
    }
    .source-title {
        font-weight: bold;
    }
    .stButton>button {
        width: 100%;
        border-radius: 0.5rem;
        height: 3rem;
        font-weight: bold;
        background-color: #1E3A8A;
        color: white;
    }
    .stat-box {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h1 class='main-header'>Automotive Regulations Advisor</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Ask questions about automotive regulations worldwide and get accurate answers from official sources</p>", unsafe_allow_html=True)

# Sidebar with stats
with st.sidebar:
    st.header("About")
    st.write("This tool provides accurate information about automotive regulations by searching and retrieving data from official regulatory websites.")
    
    # Display stats
    st.header("Statistics")
    
    log_data = load_log_data(LOG_FILE_PATH)
    if not log_data.empty:
        # Calculate and display stats
        total_queries = len(log_data)
        avg_response_time = log_data['response_time'].mean()
        top_regulations = log_data['regulation_topic'].value_counts().head(5)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='stat-box'><h3>Total Queries</h3><p>{total_queries}</p></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='stat-box'><h3>Avg Response Time</h3><p>{avg_response_time:.2f}s</p></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='stat-box'><h3>Top Regulation Topics</h3></div>", unsafe_allow_html=True)
        st.bar_chart(top_regulations)
    else:
        st.info("No query data available yet.")

# Main interface
col1, col2 = st.columns([3, 1])

# Display chat history
for message in st.session_state.chat_history:
    if message["role"] == "user":
        st.markdown(f"""
        <div class='chat-message user-message'>
            <div class='message-content'>
                <div class='avatar user-avatar'>👤</div>
                <div class='message-text'>{message["content"]}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class='chat-message assistant-message'>
            <div class='message-content'>
                <div class='avatar assistant-avatar'>🚗</div>
                <div class='message-text'>{message["content"]}</div>
            </div>
            <div class='source-link'>
                {message.get("source_html", "")}
            </div>
        </div>
        """, unsafe_allow_html=True)

# User input
user_query = st.text_input("Ask about automotive regulations:", placeholder="e.g., What are the latest emissions standards for passenger vehicles in the EU?")

# Process button click
if st.button("Get Answer") and user_query:
    # Add user query to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    
    # Create a placeholder for the assistant's response
    response_placeholder = st.empty()
    response_placeholder.markdown("""
    <div class='chat-message assistant-message'>
        <div class='message-content'>
            <div class='avatar assistant-avatar'>🚗</div>
            <div class='message-text'>Searching regulatory databases...</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Process the query
    start_time = time.time()
    
    try:
        # Use learning cache to prioritize websites based on past success
        prioritized_websites = REGULATORY_WEBSITES
        if st.session_state.learning_cache["website_success_rates"]:
            prioritized_websites = sorted(
                REGULATORY_WEBSITES,
                key=lambda x: st.session_state.learning_cache["website_success_rates"].get(x, 0),
                reverse=True
            )
        
        # Search for regulation data using Firecrawl API
        regulation_data, source_urls, source_titles = fetch_regulation_data(
            user_query, 
            prioritized_websites,
            FIRECRAWL_API_KEY
        )
        
        # Extract relevant regulations
        relevant_regulations = extract_relevant_regulations(user_query, regulation_data)
        
        # Process with Llama Scout using Cerebras API
        answer, referenced_sources = process_with_llama_scout(
            user_query,
            relevant_regulations,
            CEREBRAS_API_KEY
        )
        
        # Create the source HTML
        source_html = ""
        for i, source_idx in enumerate(referenced_sources):
            if source_idx < len(source_urls):
                source_html += f"""
                <p><span class='source-title'>Source {i+1}:</span> 
                <a href='{source_urls[source_idx]}' target='_blank'>{source_titles[source_idx]}</a></p>
                """
        
        # Update learning cache
        for source_idx in referenced_sources:
            if source_idx < len(source_urls):
                website_domain = source_urls[source_idx].split('/')[2]
                if website_domain in st.session_state.learning_cache["website_success_rates"]:
                    st.session_state.learning_cache["website_success_rates"][website_domain] += 1
                else:
                    st.session_state.learning_cache["website_success_rates"][website_domain] = 1
        
        # Save learning cache
        with open(LEARNING_CACHE_PATH, "w") as f:
            json.dump(st.session_state.learning_cache, f)
        
        # Add assistant response to chat history
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": answer,
            "source_html": source_html
        })
        
        # Display the assistant's response
        response_placeholder.markdown(f"""
        <div class='chat-message assistant-message'>
            <div class='message-content'>
                <div class='avatar assistant-avatar'>🚗</div>
                <div class='message-text'>{answer}</div>
            </div>
            <div class='source-link'>
                {source_html}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Extract regulation topic from the answer
        regulation_topic = "General"
        topic_keywords = {
            "emissions": "Emissions Standards",
            "safety": "Safety Requirements",
            "fuel": "Fuel Efficiency",
            "electric": "Electric Vehicles",
            "autonomous": "Autonomous Driving",
            "homologation": "Homologation",
            "type approval": "Type Approval",
            "certification": "Certification",
            "recall": "Recalls",
            "import": "Import Regulations"
        }
        
        for keyword, topic in topic_keywords.items():
            if keyword.lower() in user_query.lower() or keyword.lower() in answer.lower():
                regulation_topic = topic
                break
        
        # Log the query
        response_time = time.time() - start_time
        log_query(
            LOG_FILE_PATH,
            st.session_state.session_id,
            user_query,
            answer,
            regulation_topic,
            len(source_urls),
            response_time
        )
        
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        st.session_state.chat_history.append({"role": "assistant", "content": error_message})
        response_placeholder.markdown(f"""
        <div class='chat-message assistant-message'>
            <div class='message-content'>
                <div class='avatar assistant-avatar'>🚗</div>
                <div class='message-text'>{error_message}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Log the error
        response_time = time.time() - start_time
        log_query(
            LOG_FILE_PATH,
            st.session_state.session_id,
            user_query,
            error_message,
            "Error",
            0,
            response_time
        )

# Footer
st.markdown("""
<div style='margin-top: 3rem; text-align: center; color: #6B7280;'>
    <p>This advisor only references official automotive regulation sources. For legal advice, please consult a qualified professional.</p>
</div>
""", unsafe_allow_html=True)

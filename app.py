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
    ERROR_MESSAGES
)

# Set page configuration
st.set_page_config(
    page_title="Auto Regulations AI Agent",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Check API keys on startup
def check_api_keys():
    """Check if required API keys are configured."""
    missing_keys = []
    
    if not FIRECRAWL_API_KEY or FIRECRAWL_API_KEY == "fc-your-firecrawl-api-key-here":
        missing_keys.append("Firecrawl API Key")
    
    if not CEREBRAS_API_KEY or CEREBRAS_API_KEY == "csk-your-cerebras-api-key-here":
        missing_keys.append("Cerebras API Key")
    
    if missing_keys:
        st.error(f"Missing required API keys: {', '.join(missing_keys)}")
        st.error("Please configure your API keys in .streamlit/secrets.toml")
        st.stop()

# Check API keys before proceeding
check_api_keys()

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
    .error-message {
        background-color: #FEE2E2;
        border-left: 5px solid #DC2626;
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
    .error-avatar {
        background-color: #DC2626;
        color: white;
    }
    .source-container {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #E5E7EB;
    }
    .source-link {
        font-size: 0.9rem;
        color: #6B7280;
        margin: 0.25rem 0;
    }
    .source-title {
        font-weight: bold;
        color: #374151;
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
    .warning-box {
        background-color: #FEF3C7;
        border: 1px solid #F59E0B;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h1 class='main-header'>Automotive Regulations Advisor</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Ask questions about automotive regulations worldwide and get accurate answers from official sources</p>", unsafe_allow_html=True)

# Sidebar with stats and information
with st.sidebar:
    st.header("About")
    st.write("This tool provides accurate information about automotive regulations by searching and retrieving data from official regulatory websites and the Interregs.net database.")
    
    # Data sources information
    st.header("Data Sources")
    st.markdown("""
    **Primary Sources:**
    - US NHTSA & EPA
    - EU Commission & UNECE
    - Regional regulatory bodies
    
    **Backup Source:**
    - Interregs.net database
    """)
    
    # Display stats
    st.header("Statistics")
    
    log_data = load_log_data(LOG_FILE_PATH)
    if not log_data.empty:
        # Calculate and display stats
        total_queries = len(log_data)
        successful_queries = log_data['query_successful'].sum() if 'query_successful' in log_data.columns else total_queries
        avg_response_time = log_data['response_time'].mean()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='stat-box'><h3>Total Queries</h3><p>{total_queries}</p></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='stat-box'><h3>Success Rate</h3><p>{successful_queries/total_queries*100:.1f}%</p></div>", unsafe_allow_html=True)
        
        st.markdown(f"<div class='stat-box'><h3>Avg Response Time</h3><p>{avg_response_time:.2f}s</p></div>", unsafe_allow_html=True)
        
        if 'regulation_topic' in log_data.columns:
            top_regulations = log_data['regulation_topic'].value_counts().head(5)
            if not top_regulations.empty:
                st.markdown("<div class='stat-box'><h3>Top Regulation Topics</h3></div>", unsafe_allow_html=True)
                st.bar_chart(top_regulations)
    else:
        st.info("No query data available yet.")
    
    # Important notice
    st.header("Important Notice")
    st.markdown("""
    <div class='warning-box'>
    <strong>⚠️ Legal Disclaimer</strong><br>
    This tool provides information for reference only. 
    Always verify with official regulatory authorities 
    and consult qualified experts for legal compliance.
    </div>
    """, unsafe_allow_html=True)

# Main interface
def display_chat_message(message, message_type="assistant"):
    """Display a chat message with proper styling and source links."""
    if message_type == "user":
        css_class = "user-message"
        avatar_class = "user-avatar"
        avatar_icon = "👤"
    elif message_type == "error":
        css_class = "error-message"
        avatar_class = "error-avatar"
        avatar_icon = "⚠️"
    else:
        css_class = "assistant-message"
        avatar_class = "assistant-avatar"
        avatar_icon = "🚗"
    
    # Extract content and sources
    if isinstance(message, dict):
        content = message.get("content", "")
        source_urls = message.get("source_urls", [])
        source_titles = message.get("source_titles", [])
    else:
        content = str(message)
        source_urls = []
        source_titles = []
    
    # Display the main message
    st.markdown(f"""
    <div class='chat-message {css_class}'>
        <div class='message-content'>
            <div class='avatar {avatar_class}'>{avatar_icon}</div>
            <div class='message-text'>{content}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Display sources separately using Streamlit components
    if source_urls and source_titles and message_type == "assistant":
        st.markdown("**Sources:**")
        for i, (url, title) in enumerate(zip(source_urls, source_titles)):
            st.markdown(f"🔗 [{title}]({url})")

# Display chat history
for message in st.session_state.chat_history:
    display_chat_message(message, message["role"])

# User input
user_query = st.text_input(
    "Ask about automotive regulations:", 
    placeholder="e.g., What are the latest emissions standards for passenger vehicles in the EU?",
    key="user_input"
)

# Process button click
if st.button("Get Answer") and user_query:
    # Add user query to chat history
    user_message = {"role": "user", "content": user_query}
    st.session_state.chat_history.append(user_message)
    display_chat_message(user_message, "user")
    
    # Create a placeholder for the assistant's response
    with st.spinner("🔍 Analyzing your query and searching regulatory databases..."):
        # Process the query
        start_time = time.time()
        query_successful = False
        error_message = None
        answer = ""
        source_urls = []
        source_titles = []
        
        try:
            # Use learning cache to prioritize websites based on past success
            prioritized_websites = list(REGULATORY_WEBSITES.values())
            if st.session_state.learning_cache["website_success_rates"]:
                prioritized_websites = sorted(
                    REGULATORY_WEBSITES.values(),
                    key=lambda x: st.session_state.learning_cache["website_success_rates"].get(x.split('/')[2], 0),
                    reverse=True
                )
            
            # Search for regulation data using Firecrawl API and LLM website selection
            st.info("🌐 LLM selecting most relevant regulatory websites...")
            
            regulation_data, source_urls, source_titles = fetch_regulation_data(
                user_query, 
                prioritized_websites,
                FIRECRAWL_API_KEY
            )
            
            if not regulation_data:
                raise ValueError(ERROR_MESSAGES["no_data_found"])
            
            # Extract relevant regulations
            st.info("📄 Extracting relevant regulatory content...")
            
            relevant_regulations = extract_relevant_regulations(user_query, regulation_data)
            
            # Process with Llama Scout using Cerebras API
            st.info("🤖 Generating precise regulatory answer...")
            
            answer, referenced_sources = process_with_llama_scout(
                user_query,
                relevant_regulations,
                CEREBRAS_API_KEY
            )
            
            # Filter source URLs and titles to only referenced ones
            filtered_source_urls = []
            filtered_source_titles = []
            for source_idx in referenced_sources:
                if source_idx < len(source_urls):
                    filtered_source_urls.append(source_urls[source_idx])
                    filtered_source_titles.append(source_titles[source_idx])
            
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
            
            query_successful = True
            
        except ValueError as e:
            error_message = str(e)
            answer = f"❌ **Data Not Found**: {error_message}\n\nPlease try:\n- Being more specific in your query\n- Checking if the regulation exists\n- Trying different keywords"
            
        except Exception as e:
            error_message = str(e)
            answer = f"❌ **System Error**: {error_message}\n\nPlease try again later or contact support if the problem persists."
    
    # Add assistant response to chat history
    message_data = {
        "role": "error" if not query_successful else "assistant", 
        "content": answer,
        "source_urls": filtered_source_urls if query_successful else [],
        "source_titles": filtered_source_titles if query_successful else []
    }
    st.session_state.chat_history.append(message_data)
    
    # Display the response
    display_chat_message(message_data, "error" if not query_successful else "assistant")
    
    # Extract regulation topic from the answer
    regulation_topic = "Error" if not query_successful else "General"
    if query_successful:
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
        len(filtered_source_urls) if query_successful else 0,
        response_time,
        "Los Angeles, CA, US",  # User location
        query_successful
    )

# Control buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

with col2:
    if st.button("📊 View Query Analytics"):
        if st.session_state.chat_history:
            st.info(f"Total queries this session: {len([m for m in st.session_state.chat_history if m['role'] == 'user'])}")
        else:
            st.info("No queries in this session yet.")

# Footer
st.markdown("""
---
<div style='text-align: center; color: #6B7280; padding: 2rem 0;'>
    <p><strong>⚖️ Legal Notice:</strong> This advisor references official automotive regulation sources but is for informational purposes only. 
    For legal compliance, always consult qualified professionals and verify with official regulatory authorities.</p>
    <p><small>Data sources: Official regulatory websites + Interregs.net database | Powered by Cerebras AI + Firecrawl</small></p>
</div>
""", unsafe_allow_html=True)

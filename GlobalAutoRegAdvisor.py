import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from agent import AutoRegulationsAgent
from logger import Logger

# Load environment variables - ensure we look in the current directory
load_dotenv(override=True)

# Debug information about environment variables
st.sidebar.expander("Debug Info", expanded=False).write(f"""
- Environment variables loaded: {os.path.exists('.env')}
- Current directory: {os.getcwd()}
- GROQ_API_KEY set: {"Yes" if os.getenv("GROQ_API_KEY") else "No"}
""")

# Try to get the API key from multiple sources
groq_api_key = os.getenv("GROQ_API_KEY")

# If not in environment, check for an api_key.txt file
if not groq_api_key and os.path.exists("api_key.txt"):
    with open("api_key.txt", "r") as f:
        groq_api_key = f.read().strip()
    # Set it in the environment for other modules
    os.environ["GROQ_API_KEY"] = groq_api_key

# Allow direct input in the app if still not found
if not groq_api_key:
    st.warning("⚠️ GROQ_API_KEY not found in environment variables or api_key.txt")
    with st.expander("Enter Groq API Key", expanded=True):
        input_key = st.text_input("Enter your Groq API Key:", type="password")
        if input_key:
            groq_api_key = input_key
            # Set it in the environment for other modules
            os.environ["GROQ_API_KEY"] = groq_api_key
            st.success("API Key set! You can now use the app.")
        else:
            st.info("You need to provide a Groq API Key to use this application. Get one from https://console.groq.com/")
            st.write("""
            **Where to put your API key:**
            1. Create a file named `.env` in the application directory with content: `GROQ_API_KEY="your_key_here"`
            2. Or create a file named `api_key.txt` with just your API key
            3. Or enter it directly above
            """)
            st.stop()


# Initialize the agent and logger
@st.cache_resource
def initialize_agent():
    return AutoRegulationsAgent()

@st.cache_resource
def initialize_logger():
    return Logger()

agent = initialize_agent()
logger = initialize_logger()

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = {}

# App title and intro
st.title("Automotive Regulations AI Assistant")
st.markdown("""
This AI assistant helps you find accurate information about automotive regulations worldwide.
Ask questions in simple language, and the assistant will search through official regulation documents to provide answers.
""")

# Sidebar with info and stats
with st.sidebar:
    st.header("About")
    st.markdown("""
    This AI assistant uses RAG (Retrieval Augmented Generation) to provide accurate answers about automotive regulations.
    
    It searches across official regulatory websites including:
    - 🇺🇸 US NHTSA & EPA
    - 🇪🇺 European Union Regulations & ACEA
    - 🇬🇧 UK Department for Transport
    - 🌎 UN ECE Standards
    - 🇨🇳 China MIIT
    - 🇯🇵 Japan MLIT
    - 🇮🇳 India ARAI & CMVR
    - 🇨🇦 Canada Transport
    - 🇦🇺 Australia Vehicle Standards
    - 🇧🇷 Brazil INMETRO
    - 🇰🇷 South Korea MOLIT
    - 🇷🇺 Russia Rosavtodor
    - 🇲🇽 Mexico SCT
    - 🇿🇦 South Africa NRCS
    - 🇦🇷 Argentina ANSV
    - 🌐 ISO & IEC Standards
    
    All answers are based only on official regulatory documents.
    """)
    
    st.header("Performance Stats")
    performance_stats = agent.get_performance_stats()
    
    st.metric("Total Queries", performance_stats.get("total_queries", 0))
    st.metric("Success Rate", f"{performance_stats.get('success_rate', 0) * 100:.1f}%")
    st.metric("Avg Processing Time", f"{performance_stats.get('avg_processing_time', 0):.2f}s")
    
    # Show stats visualization if enough data
    if performance_stats.get("total_queries", 0) > 5:
        st.subheader("Processing Time Trend")
        
        # Get performance data
        perf_data = logger.performance_df.copy()
        if len(perf_data) > 0:
            perf_data['timestamp'] = pd.to_datetime(perf_data['timestamp'])
            perf_data = perf_data.sort_values('timestamp')
            
            # Create a rolling average
            perf_data['rolling_avg'] = perf_data['processing_time'].rolling(window=5, min_periods=1).mean()
            
            # Plot
            fig = px.line(perf_data, x='timestamp', y='rolling_avg', 
                        title='Processing Time (5-query rolling avg)',
                        labels={'rolling_avg': 'Processing Time (s)', 'timestamp': 'Time'})
            st.plotly_chart(fig, use_container_width=True)

# Main chat interface
st.header("Ask about Automotive Regulations")

# Query input
query = st.chat_input("What would you like to know about automotive regulations?")

# Process the query
if query:
    # Display user query
    with st.chat_message("user"):
        st.write(query)
    
    # Add to chat history
    st.session_state.chat_history.append({"role": "user", "content": query})
    
    # Process with the agent
    with st.chat_message("assistant"):
        with st.spinner("Searching regulatory documents..."):
            start_time = datetime.now()
            
            try:
                response, sources = agent.process_query(query)
                
                # Calculate processing time
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # Display the response
                st.write(response)
                
                # Display sources if available
                if sources:
                    with st.expander("View Sources", expanded=False):
                        for i, source in enumerate(sources):
                            st.markdown(f"{i+1}. [{source['title']}]({source['url']}) - {source['source']}")
                
                # Add to chat history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response,
                    "sources": sources,
                    "processing_time": processing_time
                })
                
                # Add feedback buttons
                col1, col2, col3 = st.columns(3)
                
                feedback_key = f"feedback_{len(st.session_state.chat_history) - 1}"
                
                if col1.button("👍 Helpful", key=f"helpful_{feedback_key}"):
                    agent.record_feedback(query, response, 1.0)
                    st.session_state.feedback_given[feedback_key] = True
                    st.success("Thank you for your feedback!")
                
                if col2.button("👎 Not Helpful", key=f"not_helpful_{feedback_key}"):
                    agent.record_feedback(query, response, 0.0)
                    st.session_state.feedback_given[feedback_key] = True
                    st.error("Sorry about that. We'll try to improve.")
                
                if col3.button("⚠️ Report Issue", key=f"issue_{feedback_key}"):
                    agent.record_feedback(query, response, 0.2)
                    st.session_state.feedback_given[feedback_key] = True
                    st.warning("Thank you for reporting this issue.")
                
            except Exception as e:
                st.error(f"Error processing your query: {str(e)}")
                logger.log_error(f"Query processing error: {str(e)}")

# Display chat history
if len(st.session_state.chat_history) > 0:
    st.header("Conversation History")
    
    # Reverse to have newest at the bottom
    for i, message in enumerate(st.session_state.chat_history):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
            # Display metadata for assistant messages
            if message["role"] == "assistant" and "processing_time" in message:
                st.caption(f"Processing time: {message['processing_time']:.2f}s")
                
                # Show feedback buttons if not already given
                feedback_key = f"feedback_{i}"
                if feedback_key not in st.session_state.feedback_given:
                    col1, col2, col3 = st.columns(3)
                    
                    if col1.button("👍 Helpful", key=f"hist_helpful_{feedback_key}"):
                        agent.record_feedback(st.session_state.chat_history[i-1]["content"], message["content"], 1.0)
                        st.session_state.feedback_given[feedback_key] = True
                        st.success("Thank you for your feedback!")
                        st.experimental_rerun()
                    
                    if col2.button("👎 Not Helpful", key=f"hist_not_helpful_{feedback_key}"):
                        agent.record_feedback(st.session_state.chat_history[i-1]["content"], message["content"], 0.0)
                        st.session_state.feedback_given[feedback_key] = True
                        st.error("Sorry about that. We'll try to improve.")
                        st.experimental_rerun()
                    
                    if col3.button("⚠️ Report Issue", key=f"hist_issue_{feedback_key}"):
                        agent.record_feedback(st.session_state.chat_history[i-1]["content"], message["content"], 0.2)
                        st.session_state.feedback_given[feedback_key] = True
                        st.warning("Thank you for reporting this issue.")
                        st.experimental_rerun()

# Admin panel with expander
with st.expander("Admin Panel", expanded=False):
    st.header("Admin Controls")
    
    # Export data
    if st.button("Export Log Data"):
        export_data = logger.export_data()
        st.download_button(
            label="Download JSON",
            data=json.dumps(export_data, indent=2),
            file_name=f"auto_regs_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # Trigger improvement cycle
    if st.button("Run Improvement Cycle"):
        with st.spinner("Running improvement cycle..."):
            agent.improve()
        st.success("Improvement cycle completed!")
    
    # Clear conversation
    if st.button("Clear Conversation"):
        st.session_state.chat_history = []
        st.session_state.feedback_given = {}
        st.success("Conversation cleared!")
        st.experimental_rerun()

# Footer
st.markdown("---")
st.caption("Automotive Regulations AI Assistant • Built with Groq + Llama model")

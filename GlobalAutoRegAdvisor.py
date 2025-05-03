import streamlit as st
import requests
import os
import re
import json
import time
import uuid
import datetime
import sqlite3
import pandas as pd
import socket
import hashlib
import logging
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.schema import Document
import streamlit.components.v1 as components
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import matplotlib
matplotlib.use('Agg')
from io import BytesIO
import base64
import traceback
from urllib.parse import urlparse
import random
import asyncio
import aiohttp
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Import our custom modules
import config
from enhanced_web_crawler import RegulatoryWebCrawler
from database_manager import get_database_manager

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AutoRegulationsApp")

# Set page configuration
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout=config.APP_LAYOUT,
    initial_sidebar_state="expanded"
)

def clean_response(response):
    """Clean LLM response to ensure only content is returned"""
    if isinstance(response, str):
        # Clean the string of any metadata patterns
        response = re.sub(r'content="(.*?)"', r'\1', response)
        response = re.sub(r'additional_kwargs=\{\}.*', '', response, flags=re.DOTALL)
        response = re.sub(r'response_metadata=\{.*?\}', '', response, flags=re.DOTALL)
        response = re.sub(r'usage_metadata=\{.*?\}', '', response, flags=re.DOTALL)
        response = re.sub(r'id=\'run--.*?\'', '', response)
        return response.strip()
        
    if hasattr(response, 'content'):
        return response.content
        
    if hasattr(response, 'choices') and len(response.choices) > 0:
        return response.choices[0].message.content
    
    # Deep inspection for nested content
    if isinstance(response, dict):
        if 'content' in response:
            return response['content']
        if 'choices' in response and len(response['choices']) > 0:
            choice = response['choices'][0]
            if isinstance(choice, dict) and 'message' in choice:
                return choice['message'].get('content', '')
    
    # Last resort
    return str(response)
    
# Learning settings
ENABLE_LEARNING = True
ENABLE_CACHING = True
USE_MODEL_CONTEXT_PROTOCOL = True

# Get database manager
db_manager = get_database_manager()

# Generate or retrieve user ID for tracking
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
    # Register user with the database manager
    db_manager.set_user_id(st.session_state.user_id)

# Streaming output buffer for better UX
if 'output_buffer' not in st.session_state:
    st.session_state.output_buffer = []

# Initialize session state
if 'history' not in st.session_state:
    st.session_state.history = []
if 'documents' not in st.session_state:
    st.session_state.documents = []
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
if 'crawler' not in st.session_state:
    st.session_state.crawler = RegulatoryWebCrawler(db_manager)
if 'last_query' not in st.session_state:
    st.session_state.last_query = None

# Create logger for telemetry
@st.cache_resource
def get_logger():
    return logger

app_logger = get_logger()

# Enhanced document processor with learning capabilities
class EnhancedDocumentProcessor:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Use a smaller, faster model for better performance
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        
        # Document cache
        self.document_cache = {}
    
    def process_documents(self, documents):
        """Process documents for RAG with caching and learning"""
        if not documents:
            return None
        
        # Flatten the list of documents
        flat_docs = []
        for doc_list in documents:
            if doc_list:
                flat_docs.extend(doc_list)
        
        # Check if we already processed these documents
        doc_hash = self._hash_documents(flat_docs)
        if ENABLE_CACHING and doc_hash in self.document_cache:
            logger.info(f"Using cached vectorstore for {len(flat_docs)} documents")
            return self.document_cache[doc_hash]
        
        # Split documents
        splits = self.text_splitter.split_documents(flat_docs)
        
        if not splits:
            logger.warning("No document splits were generated")
            return None
        
        # Create vectorstore
        try:
            vectorstore = FAISS.from_documents(documents=splits, embedding=self.embeddings)
            
            # Cache the vectorstore
            if ENABLE_CACHING:
                self.document_cache[doc_hash] = vectorstore
                
            logger.info(f"Created vectorstore with {len(splits)} splits")
            return vectorstore
        except Exception as e:
            logger.error(f"Error creating vectorstore: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def get_relevant_context(self, vectorstore, query, k=config.MAX_RETRIEVAL_CHUNKS):
        """Get relevant context for a query"""
        if not vectorstore:
            return []
        
        try:
            # Create retriever with advanced options
            retriever = vectorstore.as_retriever(
                search_kwargs={
                    "k": k,
                    "fetch_k": k * 3,  # Fetch more documents than needed for better candidate selection
                    "lambda_mult": 0.5,  # Add diversity to results
                }
            )
            
            # Get relevant documents
            relevant_docs = retriever.get_relevant_documents(query)
            
            logger.info(f"Retrieved {len(relevant_docs)} relevant documents")
            return relevant_docs
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            logger.error(traceback.format_exc())
            return []
    
    def _hash_documents(self, documents):
        """Create a hash of the documents to use as a cache key"""
        doc_texts = [doc.page_content for doc in documents]
        return hashlib.md5(''.join(doc_texts).encode()).hexdigest()

# Modern Model Context Protocol implementation
class ModelContextProtocol:
    """
    Implementation of Model Context Protocol for adaptive response generation
    with built-in verification and chain of thought reasoning.
    """
    
    def __init__(self, llm, db_manager=None):
        self.llm = llm
        self.db_manager = db_manager
        
        # Templates for different stages
        self.templates = {
            "understanding": """
            You are an automotive regulations expert analyzing a user's question.
            
            USER QUERY: {query}
            
            Please analyze this query to understand:
            1. What specific regulations, standards, or compliance areas is the user asking about?
            2. What countries or regulatory bodies might have relevant information?
            3. What technical terms or concepts are central to answering this query?
            4. What type of information would constitute a complete answer?
            
            Provide a detailed analysis that will guide the information retrieval process.
            """,
            
            "extraction": """
            You are an automotive regulations expert conducting a meticulous evidence gathering process.
            
            USER QUERY: {query}
            
            QUERY ANALYSIS: {understanding}
            
            I have retrieved the following regulatory documents. Extract ONLY the information that directly addresses the query:
            
            {context}
            
            For each relevant piece of information, include:
            1. The specific regulation or section number
            2. The regulatory body or authority
            3. The exact text that addresses the query
            
            Focus on extracting ONLY facts and official regulatory information, not interpretations or opinions.
            If the documents don't contain information needed to answer the query, explicitly state what is missing.
            """,
            
            "verification": """
            You are an automotive regulations expert validating information for accuracy.
            
            USER QUERY: {query}
            
            EXTRACTED INFORMATION: {extraction}
            
            Your task is to verify the extracted information:
            1. Check for any inconsistencies or contradictions in the information
            2. Identify any information that seems questionable or needs additional verification
            3. Flag any potential misinterpretations of regulatory text
            4. Note any important missing information that would be needed for a complete answer
            
            If you can't verify certain information with the given context, clearly state this.
            Only mark information as verified if it's directly supported by official regulatory documentation.
            """,
            
            "response": """
            You are an automotive regulations expert providing accurate, friendly assistance.
            
            USER QUERY: {query}
            
            VERIFIED INFORMATION: {verification}
            
            Based ONLY on the verified regulatory information, provide a clear, conversational answer to the user's query.
            
            Guidelines:
            1. Be precise and factual, citing specific regulations where appropriate
            2. Use a natural, friendly tone that's easy to understand
            3. If precise information isn't available, clearly explain what's known and what's not
            4. Organize information logically with proper formatting for readability
            5. Include relevant regulation numbers and their sources
            
            Remember, you are helping someone understand complex regulatory information. Be helpful, accurate, and respectful.
            Your conversation should feel natural while still conveying expert knowledge.
            
            If the verified information doesn't allow for a complete answer, be honest about these limitations.
            """
        }
        
    async def generate_response(self, query, relevant_docs):
        """Generate a response using Model Context Protocol"""
        try:
            # Logging and performance tracking
            if self.db_manager:
                self.db_manager.start_query(query)
            
            # Step 1: Query understanding - what does the user really want to know?
            understanding_prompt = PromptTemplate.from_template(self.templates["understanding"])
            understanding = await self._invoke_async(understanding_prompt, {"query": query})
            
            logger.info("Completed query understanding phase")
            
            # Step 2: Information extraction - get relevant facts from documents
            if relevant_docs:
                extraction_prompt = PromptTemplate.from_template(self.templates["extraction"])
                extraction = await self._invoke_async(extraction_prompt, {
                    "query": query,
                    "understanding": understanding,
                    "context": self._format_documents(relevant_docs)
                })
            else:
                extraction = "No relevant regulatory documents found."
            
            logger.info("Completed information extraction phase")
            
            # Step 3: Verification - is the information accurate and complete?
            verification_prompt = PromptTemplate.from_template(self.templates["verification"])
            verification = await self._invoke_async(verification_prompt, {
                "query": query, 
                "extraction": extraction
            })
            
            logger.info("Completed verification phase")
            
            # Step 4: Generate final response
            response_prompt = PromptTemplate.from_template(self.templates["response"])
            final_response = await self._invoke_async(response_prompt, {
                "query": query,
                "verification": verification
            })
            
            logger.info("Completed response generation phase")
            
            return final_response
        except Exception as e:
            logger.error(f"Error in MCP response generation: {e}")
            logger.error(traceback.format_exc())
            return f"I'm sorry, I encountered an error while processing your query: {str(e)}"
    
    async def _invoke_async(self, prompt, inputs):
        """Invoke the LLM asynchronously"""
        formatted_prompt = prompt.format(**inputs)
        response = self.llm.invoke(formatted_prompt)
        return response
    
    def _format_documents(self, docs):
        """Format documents for inclusion in prompts"""
        formatted_docs = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get('source', 'Unknown source')
            authority = doc.metadata.get('authority', 'Unknown authority')
            title = doc.metadata.get('title', 'Untitled document')
            
            formatted_docs.append(
                f"DOCUMENT {i+1}:\n"
                f"Title: {title}\n"
                f"Authority: {authority}\n"
                f"Source: {source}\n\n"
                f"Content:\n{doc.page_content}\n"
                f"{'-' * 80}\n"
            )
        
        return "\n".join(formatted_docs)

# LLM Chain with enhanced capabilities
class EnhancedRegulatoryLLMChain:
    def __init__(self, api_key=config.GROQ_API_KEY, model_name=config.DEFAULT_MODEL, db_manager=None):
        self.api_key = api_key
        self.model_name = model_name
        
        try:
            self.llm = ChatGroq(
                api_key=api_key,
                model_name=model_name,
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=4000,
                top_p=0.9
            )
            
            # Initialize MCP if enabled
            if USE_MODEL_CONTEXT_PROTOCOL:
                self.mcp = ModelContextProtocol(self.llm, db_manager)
            
        except Exception as e:
            logger.error(f"Error initializing LLM: {e}")
            logger.error(traceback.format_exc())
            raise
        
        self.db_manager = db_manager
    
    async def generate_response(self, query, relevant_docs):
        """Generate a response using advanced prompting techniques"""
        # If MCP is enabled, use it
        if USE_MODEL_CONTEXT_PROTOCOL:
            return await self.mcp.generate_response(query, relevant_docs)
        
        # Otherwise, use traditional chain-based approach
        try:
            if self.db_manager:
                self.db_manager.start_query(query)
            
            # Step 1: Understand the user query
            understanding_prompt = ChatPromptTemplate.from_template(
                """You are an automotive regulations expert. 
                Analyze this user query about automotive regulations:
                
                User Query: {query}
                
                What specific regulations or standards is the user asking about?
                What countries or regulatory bodies might have relevant information?
                What key terms should I focus on when searching regulatory documents?
                
                Provide a concise analysis."""
            )
            
            understanding_chain = understanding_prompt | self.llm | StrOutputParser()
            
            understanding = understanding_chain.invoke({"query": query})
            
            # Step 2: Extract and analyze relevant information from documents
            if relevant_docs:
                extraction_prompt = ChatPromptTemplate.from_template(
                    """You are an automotive regulations expert tasked with extracting precise information.
                    
                    User Query: {query}
                    Query Analysis: {understanding}
                    
                    I have retrieved the following regulatory documents. Extract only the information that directly addresses the query:
                    
                    {context}
                    
                    Provide the extracted information with citations to specific regulations, sections, and document sources."""
                )
                
                extraction_chain = create_stuff_documents_chain(extraction_prompt, self.llm)
                
                extraction = extraction_chain.invoke({
                    "query": query,
                    "understanding": understanding,
                    "context": relevant_docs
                })
            else:
                extraction = "No relevant regulatory documents found."
            
            # Step 3: Formulate the final response
            response_prompt = ChatPromptTemplate.from_template(
                """You are an automotive regulations expert providing accurate information.
                
                User Query: {query}
                Query Analysis: {understanding}
                
                Relevant Regulatory Information:
                {extraction}
                
                Based ONLY on the extracted regulatory information, provide a clear, accurate answer to the user's query.
                
                If the extracted information does not contain a direct answer to the query, explain what information is missing and why a definitive answer cannot be provided.
                
                Format your answer professionally with proper citations to specific regulations and clauses.
                DO NOT fabricate or hallucinate information that is not explicitly found in the extracted regulatory data.
                
                Use a friendly, conversational tone while maintaining accuracy and professionalism.
                
                Focus only on facts from automotive regulatory documents."""
            )
            
            response_chain = response_prompt | self.llm | StrOutputParser()
            
            final_response = response_chain.invoke({
                "query": query,
                "understanding": understanding,
                "extraction": extraction
            })
            
            if isinstance(final_response, str):
                return final_response
            
            # If it's a langchain response object
            if hasattr(final_response, 'content'):
                return final_response.content
                
            # If it's a Groq API response object
            if hasattr(final_response, 'choices') and len(final_response.choices) > 0:
                return final_response.choices[0].message.content
                
            # If it's a dictionary or has other structure
            if isinstance(final_response, dict) and 'content' in final_response:
                return final_response['content']
                
            # Last resort - convert to string and clean up
            response_str = str(final_response)
            # Remove metadata patterns
            response_str = re.sub(r'token_usage.*?}', '', response_str, flags=re.DOTALL)
            response_str = re.sub(r'additional_kwargs=\{\}', '', response_str)
            response_str = re.sub(r'response_metadata=\{.*?\}', '', response_str, flags=re.DOTALL)
            response_str = re.sub(r'id=\'run--.*?\'', '', response_str)
            response_str = re.sub(r'usage_metadata=\{.*?\}', '', response_str, flags=re.DOTALL)
            
            return response_str.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            logger.error(traceback.format_exc())
            return f"I'm sorry, I encountered an error while processing your query: {str(e)}"

# Enhanced Process Map Generator
def generate_process_map():
    """Generate a modern, polished visual process map of the agent's workflow"""
    # Use a cleaner style for matplotlib
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Create a directed graph
    G = nx.DiGraph()
    
    # Define nodes with positions for better layout control
    nodes = [
        ("User Query", "Input query", (0, 2)),
        ("Query Analysis", "Understand intent", (2, 2)),
        ("Interregs Access", "Fetch regulations", (4, 2)),
        ("Document Retrieval", "Find documents", (6, 2)),
        ("Document Processing", "Extract content", (8, 2)),
        ("Vector Database", "Create embeddings", (7, 0)),
        ("Context Retrieval", "Get relevant text", (5, 0)),
        ("LLM Processing", "Generate response", (3, 0)),
        ("Response", "Display answer", (1, 0))
    ]
    
    # Add nodes with positions and descriptions
    for node, desc, pos in nodes:
        G.add_node(node, description=desc, pos=pos)
    
    # Add edges
    edges = [
        ("User Query", "Query Analysis"),
        ("Query Analysis", "Interregs Access"),
        ("Interregs Access", "Document Retrieval"),
        ("Document Retrieval", "Document Processing"),
        ("Document Processing", "Vector Database"),
        ("Vector Database", "Context Retrieval"),
        ("Context Retrieval", "LLM Processing"),
        ("LLM Processing", "Response"),
        ("Response", "User Query")  # Complete the cycle
    ]
    
    for edge in edges:
        G.add_edge(edge[0], edge[1])
    
    # Create a high-quality figure
    plt.figure(figsize=(12, 6), dpi=100, facecolor='white')
    
    # Get positions from node attributes
    pos = nx.get_node_attributes(G, 'pos')
    
    # Define colors with opacity
    node_color = '#4A89DC'  # Modern blue
    edge_color = '#9BB7D4'  # Lighter blue for edges
    highlight_color = '#5D9CEC'  # Highlighted nodes (brighter blue)
    
    # Draw nodes with increased size and alpha for modern look
    nx.draw_networkx_nodes(
        G, 
        pos, 
        node_size=2500, 
        node_color=[highlight_color if node in ["Interregs Access", "Query Analysis", "Response"] 
                    else node_color for node in G.nodes()],
        alpha=0.85,
        edgecolors='white',
        linewidths=2,
        node_shape='o'
    )
    
    # Draw curved edges with improved appearance
    edge_curve = 0.2  # degree of curve
    for edge in G.edges():
        # For the cycle-closing edge, use a different style
        if edge == ("Response", "User Query"):
            # Draw the returning edge differently
            # Calculate control points for a more pronounced curve
            source_pos = pos[edge[0]]
            target_pos = pos[edge[1]]
            
            # Create a curved edge path using bent_edges
            nx.draw_networkx_edges(
                G, 
                pos, 
                edgelist=[edge],
                edge_color=edge_color, 
                width=2,
                alpha=0.6,
                arrows=True, 
                arrowsize=20,
                connectionstyle=f'arc3,rad=-0.4'  # More pronounced curve for this edge
            )
        else:
            # Normal edges with slight curve
            nx.draw_networkx_edges(
                G, 
                pos, 
                edgelist=[edge],
                edge_color=edge_color, 
                width=2,
                alpha=0.7,
                arrows=True, 
                arrowsize=20,
                connectionstyle=f'arc3,rad={edge_curve}'  # Curved edges
            )
    
    # Draw primary labels with clear offset to avoid overlapping with nodes
    nx.draw_networkx_labels(
        G, 
        pos, 
        font_size=12,
        font_family='sans-serif',
        font_weight='bold',
        font_color='white'
    )
    
    # Draw description labels with greater offset to avoid overlapping
    desc_pos = {}
    for node, coords in pos.items():
        desc_pos[node] = (coords[0], coords[1] - 0.35)  # Greater offset
    
    # Get node descriptions
    node_attrs = nx.get_node_attributes(G, 'description')
    
    # Draw description labels with light background for better readability
    # First draw label backgrounds
    for node, desc in node_attrs.items():
        x, y = desc_pos[node]
        plt.text(
            x, y, desc,
            horizontalalignment='center',
            fontsize=10,
            fontfamily='sans-serif',
            color='#444444',
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                alpha=0.8,
                edgecolor="none"
            )
        )
    
    # Add title with subtle background
    plt.text(
        4, 3.2, 'Automotive Regulation AI Process Flow',
        horizontalalignment='center',
        fontsize=16,
        fontweight='bold',
        fontfamily='sans-serif',
        color='#333333',
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="white",
            alpha=0.9,
            edgecolor="#DDDDDD"
        )
    )
    
    # Add a subtle grid
    plt.grid(True, linestyle='--', alpha=0.2)
    
    # Remove axis
    plt.axis('off')
    
    # Set tight layout for better space usage
    plt.tight_layout()
    
    # Add an elegant background with gradient (white to very light blue)
    ax = plt.gca()
    ax.set_facecolor('#F8FBFF')  # Very light blue
    
    # Convert plot to base64 string
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='#F8FBFF', edgecolor='none')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    return img_str

# Main application logic
async def process_query_async(user_query):
    """Process a user query asynchronously"""
    try:
        # Start logging
        db_manager.start_query(user_query)
        
        with st.spinner("Processing your query..."):
            # Step 1: Find relevant regulatory documents
            crawler = st.session_state.crawler
            st.info("Searching for relevant regulatory documents...")
            doc_infos = crawler.find_regulatory_documents(user_query)
            
            if not doc_infos:
                error_message = "Could not find relevant regulatory documents. Please try a different query."
                st.error(error_message)
                # Log error
                db_manager.log_query(
                    query=user_query,
                    response_status="error",
                    error_message=error_message,
                    model_used=config.DEFAULT_MODEL
                )
                return
            
            # Display found documents
            with st.expander("📚 Found Regulatory Documents"):
                for doc in doc_infos:
                    st.markdown(f"**{doc['title']}**  \n{doc['authority']} - [Link]({doc['url']})")
            
            # Step 2: Download and process documents
            st.info("Downloading and processing documents...")
            documents = []
            for doc_info in doc_infos:
                doc = crawler.download_document(doc_info)
                if doc:
                    documents.append(doc)
            
            # Step 3: Process documents for RAG
            processor = EnhancedDocumentProcessor()
            vectorstore = processor.process_documents(documents)
            
            if not vectorstore:
                error_message = "Could not process documents. Please try again."
                st.error(error_message)
                # Log error
                db_manager.log_query(
                    query=user_query,
                    response_status="error",
                    error_message=error_message,
                    model_used=config.DEFAULT_MODEL
                )
                return
            
            # Save to session state
            st.session_state.vectorstore = vectorstore
            
            # Step 4: Get relevant context for the query
            relevant_docs = processor.get_relevant_context(vectorstore, user_query)
            
            # Step 5: Generate response using LLM
            llm_chain = EnhancedRegulatoryLLMChain(db_manager=db_manager)
            response = await llm_chain.generate_response(user_query, relevant_docs)
            
            # Add to history
            st.session_state.history.append({
                "query": user_query,
                "response": response
            })
            
            # Log successful query
            db_manager.log_query(
                query=user_query,
                response_status="success",
                documents_retrieved=len(documents),
                model_used=config.DEFAULT_MODEL
            )
            
            # Save last query for feedback
            st.session_state.last_query = user_query
            
            return clean_response(response)
            
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        st.error(error_message)
        # Log exception
        db_manager.log_query(
            query=user_query,
            response_status="error",
            error_message=error_message,
            model_used=config.DEFAULT_MODEL
        )
        logger.error(f"Error processing query: {e}")
        logger.error(traceback.format_exc())
        return f"I'm sorry, I encountered an error while processing your query: {str(e)}"

def main():
    # Display title and introduction
    st.title("🚗 Automotive Regulations AI Assistant")
    st.markdown("""
    Ask questions about automotive regulations worldwide, and get answers based on official documents.
    """)
    
    # Create two columns in the sidebar
    col1, col2 = st.sidebar.columns([3, 1])
    
    # Performance metrics in the sidebar
    with col1:
        st.sidebar.header("Information")
        
        # Display performance metrics if available
        metrics = db_manager.get_performance_metrics()
        if metrics and metrics['query_count'] > 0:
            with st.sidebar.expander("System Performance"):
                st.metric("Success Rate", f"{metrics['success_rate']:.1f}%")
                st.metric("Avg. Response Time", f"{metrics['avg_execution_time']:.1f}s")
                st.metric("Queries Processed", metrics['query_count'])
    
    # Display process map in expander
    with st.expander("🔄 View Process Flow Diagram"):
        img_str = generate_process_map()
        st.image(f"data:image/png;base64,{img_str}", use_column_width=True)
    
    # Initialize a user ID if not present
    if 'user_id' not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    
    # User input
    user_query = st.text_input("🔍 Ask about automotive regulations:", placeholder="Example: What are the EU requirements for Advanced Emergency Braking Systems in trucks?")
    
    if st.button("Submit", type="primary") and user_query:
        # Run the async query processing in a non-blocking way
        response = asyncio.run(process_query_async(user_query))
        if response:
            st.session_state.output_buffer.append(response)
    
    # Admin panel (hidden by default)
    if st.sidebar.checkbox("Admin Access", False):
        st.sidebar.subheader("Admin Login")
        admin_username = st.sidebar.text_input("Username")
        admin_password = st.sidebar.text_input("Password", type="password")
        
        if st.sidebar.button("Access Logs"):
            if admin_username and admin_password:
                logs_df = db_manager.get_logs_dataframe(admin_username, admin_password)
                if logs_df is not None:
                    st.sidebar.success("Login successful!")
                    st.sidebar.download_button(
                        label="Download Logs CSV",
                        data=logs_df.to_csv(index=False),
                        file_name=f"regulatory_agent_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    st.sidebar.subheader("Usage Statistics")
                    st.sidebar.metric("Total Queries", len(logs_df))
                    st.sidebar.metric("Successful Queries", len(logs_df[logs_df['response_status'] == 'success']))
                    st.sidebar.metric("Error Rate", f"{(len(logs_df[logs_df['response_status'] == 'error']) / len(logs_df) * 100):.1f}%")
                else:
                    st.sidebar.error("Invalid credentials")
    
    # Display response from buffer
    if st.session_state.output_buffer:
        st.markdown("### Response:")
        
        # Get the latest response
        latest_response = st.session_state.output_buffer[-1]
        
        # Display the response
        st.markdown(latest_response)
        
        # Add feedback buttons
        col1, col2, col3 = st.columns([1, 1, 5])
        with col1:
            if st.button("👍 Helpful"):
                if st.session_state.last_query:
                    db_manager.record_feedback(st.session_state.last_query, 1)
                    st.success("Thank you for your feedback!")
        with col2:
            if st.button("👎 Not Helpful"):
                if st.session_state.last_query:
                    db_manager.record_feedback(st.session_state.last_query, 0)
                    st.error("Sorry the response wasn't helpful. We'll work on improving.")
    
    # Display conversation history
    if st.session_state.history and len(st.session_state.history) > 1:  # Skip showing history if only the latest response
        with st.expander("Conversation History", expanded=False):
            for i, exchange in enumerate(st.session_state.history[:-1]):  # Skip the latest response which is already shown
                st.markdown(f"#### Q: {exchange['query']}")
                st.markdown(f"{exchange['response']}")
                st.markdown("---")

# Run the main application
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled exception in main application: {e}")
        logger.error(traceback.format_exc())
        st.error(f"The application encountered an unexpected error: {str(e)}")
    finally:
        # Clean up when the app closes
        if 'crawler' in st.session_state and st.session_state.crawler:
            st.session_state.crawler.close()
        
        # End user session
        if db_manager:
            db_manager.end_session()

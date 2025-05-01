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
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.schema import Document
import streamlit.components.v1 as components
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from io import BytesIO
import base64

# Import configuration
import config

# Set page configuration
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout=config.APP_LAYOUT,
    initial_sidebar_state="expanded"
)

# Usage Logger Class
class UsageLogger:
    """
    Handles the logging of user queries, errors, and system usage.
    Stores logs in a SQLite database with admin-only access.
    """
    def __init__(self, db_path=config.LOG_DB_PATH):
        """Initialize the logger with the path to the SQLite database"""
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.datetime.now()
        
        # Initialize database if it doesn't exist
        self._initialize_db()
    
    def _initialize_db(self):
        """Create the database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create main logs table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp TEXT,
            user_id TEXT,
            ip_address TEXT,
            user_agent TEXT,
            query TEXT,
            response_status TEXT,
            error_message TEXT,
            execution_time REAL,
            documents_retrieved INTEGER,
            model_used TEXT
        )
        ''')
        
        # Create admin users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            created_at TEXT
        )
        ''')
        
        # Add default admin if none exists
        cursor.execute("SELECT COUNT(*) FROM admin_users")
        if cursor.fetchone()[0] == 0:
            # Create default admin with password from config
            default_pass = hashlib.sha256(config.DEFAULT_ADMIN_PASSWORD.encode()).hexdigest()
            cursor.execute(
                "INSERT INTO admin_users VALUES (?, ?, ?)",
                (config.DEFAULT_ADMIN_USERNAME, default_pass, datetime.datetime.now().isoformat())
            )
        
        conn.commit()
        conn.close()
    
    def _get_anonymized_user_info(self):
        """Get anonymized user information based on available data"""
        try:
            # Get client IP if available
            client_ip = hashlib.md5(socket.gethostbyname(socket.gethostname()).encode()).hexdigest()
        except:
            client_ip = "unknown"
            
        try:
            # Get user agent if available
            user_agent = st.session_state.get('_user_agent', 'unknown')
        except:
            user_agent = "unknown"
            
        return {
            "user_id": st.session_state.get('user_id', 'anonymous'),
            "ip_address": client_ip,
            "user_agent": user_agent
        }
    
    def log_query(self, query, response_status="success", error_message="", documents_retrieved=0, model_used=""):
        """Log a user query with results"""
        user_info = self._get_anonymized_user_info()
        execution_time = (datetime.datetime.now() - self.start_time).total_seconds()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO usage_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),  # unique log id
                self.session_id,
                datetime.datetime.now().isoformat(),
                user_info["user_id"],
                user_info["ip_address"],
                user_info["user_agent"],
                query,
                response_status,
                error_message,
                execution_time,
                documents_retrieved,
                model_used
            )
        )
        
        conn.commit()
        conn.close()
    
    def get_logs_dataframe(self, admin_username, admin_password):
        """Get all logs as a pandas DataFrame - admin access only"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verify admin credentials
        cursor.execute(
            "SELECT password_hash FROM admin_users WHERE username = ?", 
            (admin_username,)
        )
        result = cursor.fetchone()
        
        if not result or result[0] != hashlib.sha256(admin_password.encode()).hexdigest():
            conn.close()
            return None
        
        # If credentials valid, return logs
        logs_df = pd.read_sql_query("SELECT * FROM usage_logs", conn)
        conn.close()
        
        return logs_df

# Initialize logger (hidden from regular users)
@st.cache_resource
def get_logger():
    """Get or create the logger as a cached resource"""
    return UsageLogger()

logger = get_logger()

# Streamlit UI setup
st.title("🚗 Automotive Regulations AI Assistant")
st.markdown("""
This assistant provides accurate information about automotive regulations worldwide.
It only references official regulatory documents and will not hallucinate information.
""")

# Sidebar for configuration and information
with st.sidebar:
    st.header("Information")
    st.markdown("""
    This assistant provides accurate information about automotive regulations worldwide.
    It searches official regulatory sources and provides verifiable answers.
    """)
    
    # Admin panel (hidden by default)
    if st.sidebar.checkbox("Admin Access", False):
        st.sidebar.subheader("Admin Login")
        admin_username = st.sidebar.text_input("Username")
        admin_password = st.sidebar.text_input("Password", type="password")
        
        if st.sidebar.button("Access Logs"):
            if admin_username and admin_password:
                logs_df = logger.get_logs_dataframe(admin_username, admin_password)
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

# Initialize session state
if 'history' not in st.session_state:
    st.session_state.history = []
if 'documents' not in st.session_state:
    st.session_state.documents = []
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None

# Define regulatory websites from config
REGULATORY_WEBSITES = config.REGULATORY_WEBSITES

# Class for handling web requests with retry logic and anti-blocking techniques
class RegulatoryWebCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Login to Interregs upon initialization
        self._login_to_interregs()
        
    def _login_to_interregs(self):
        """Login to Interregs.net with credentials from config"""
        try:
            # First get the login page to capture any tokens/cookies
            login_response = self.session.get(config.INTERREGS_LOGIN_URL, timeout=15)
            
            if login_response.status_code == 200:
                # Parse the login form to get any CSRF token if needed
                soup = BeautifulSoup(login_response.text, 'html.parser')
                
                # Prepare login data
                login_data = {
                    'email': config.INTERREGS_EMAIL,
                    'password': config.INTERREGS_PASSWORD,
                    'remember': '1',  # Optional: stay logged in
                }
                
                # Extract CSRF token if it exists
                csrf_token = soup.find('input', {'name': 'csrf_token'})
                if csrf_token:
                    login_data['csrf_token'] = csrf_token.get('value', '')
                
                # Submit login form
                post_response = self.session.post(
                    config.INTERREGS_LOGIN_URL,
                    data=login_data,
                    allow_redirects=True,
                    timeout=15
                )
                
                # Check if login was successful
                if post_response.status_code == 200:
                    # Verify login success by checking for specific elements
                    if 'Welcome' in post_response.text or 'Dashboard' in post_response.text or 'Logout' in post_response.text:
                        return True
            
            st.warning("Failed to login to Interregs.net. Will try to continue anyway.")
            return False
            
        except Exception as e:
            st.warning(f"Error logging into Interregs.net: {e}")
            return False
        
    def get_with_retry(self, url, max_retries=3, delay=2):
        """Get a URL with retry logic and randomized delays to avoid blocking"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15)  # Increased timeout
                if response.status_code == 200:
                    return response
                else:
                    st.warning(f"Received status code {response.status_code} for {url}")
            except Exception as e:
                st.warning(f"Error retrieving {url}: {e}")
            
            # Wait with exponential backoff
            time.sleep(delay * (2 ** attempt))
        
        return None
    
    def find_interregs_documents(self, query):
        """Find regulatory documents from Interregs.net"""
        documents = []
        
        try:
            # Create search URL for Interregs
            search_terms = '+'.join(query.split())
            search_url = f"{config.INTERREGS_URL}&search={search_terms}"
            
            # Get the search results page
            response = self.get_with_retry(search_url)
            if not response:
                return []
            
            # Parse the search results to find document links
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for regulation links - adjust these selectors based on the actual site structure
            result_links = soup.select('a.regulation-link, a.document-link, div.search-result a, table.results a')
            
            # If no specific classes found, try a more general approach
            if not result_links:
                # Look for any link that might be a document based on text content or href
                all_links = soup.find_all('a', href=True)
                result_links = [link for link in all_links if 
                               ('regulation' in link.get('href', '').lower() or
                                'document' in link.get('href', '').lower() or
                                'pdf' in link.get('href', '').lower() or
                                (link.text and any(term.lower() in link.text.lower() for term in query.split())))]
            
            # Process found links
            for link in result_links:
                href = link['href']
                
                # Ensure we have absolute URLs
                if not href.startswith('http'):
                    if href.startswith('/'):
                        doc_url = f"https://www.interregs.net{href}"
                    else:
                        doc_url = f"https://www.interregs.net/{href}"
                else:
                    doc_url = href
                
                # Get document title
                doc_title = link.text.strip() if link.text.strip() else doc_url.split('/')[-1]
                
                # Add document info
                doc_info = {
                    'title': doc_title,
                    'url': doc_url,
                    'authority': 'Interregs'
                }
                
                if doc_info not in documents:
                    documents.append(doc_info)
            
            return documents
            
        except Exception as e:
            st.warning(f"Error searching Interregs.net: {e}")
            return []
    
    def find_regulatory_documents(self, query, max_docs=config.MAX_DOCUMENTS):
        """Find regulatory documents related to the query"""
        # First try Interregs
        documents = self.find_interregs_documents(query)
        
        # If we got enough documents from Interregs, return them
        if len(documents) >= max_docs:
            return documents[:max_docs]
        
        # Otherwise, try the backup sources
        for authority, site_info in REGULATORY_WEBSITES.items():
            # Skip if we already have enough documents
            if len(documents) >= max_docs:
                break
                
            # Create search URL or path based on the authority
            if authority == 'UNECE':
                search_url = f"{site_info['base_url']}{site_info['regulations_path']}"
            elif authority == 'EU':
                # For EU, we might want to search more specifically
                search_query = '+'.join(query.split())
                search_url = f"{site_info['base_url']}/search.html?qid=1596132631839&text={search_query}"
            elif authority == 'NHTSA':
                search_query = '+'.join(query.split())
                search_url = f"{site_info['base_url']}/search?keywords={search_query}"
            else:
                search_query = '+'.join(query.split())
                search_url = f"{site_info['base_url']}/search/site/{search_query}"
            
            # Get the search results page
            response = self.get_with_retry(search_url)
            if not response:
                continue
            
            # Parse the search results to find document links
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', href=True)
            
            # Filter links that match document patterns
            for link in links:
                href = link['href']
                # Check if the link matches our patterns for document URLs
                if any(pattern in href for pattern in site_info['doc_patterns']):
                    # Ensure we have absolute URLs
                    if href.startswith('http'):
                        doc_url = href
                    else:
                        doc_url = f"{site_info['base_url']}{href}"
                    
                    # Get document title if available
                    doc_title = link.text.strip() if link.text.strip() else doc_url.split('/')[-1]
                    
                    # Add document info
                    doc_info = {
                        'title': doc_title,
                        'url': doc_url,
                        'authority': authority
                    }
                    
                    if doc_info not in documents:
                        documents.append(doc_info)
                        
                    # Limit the number of documents
                    if len(documents) >= max_docs:
                        return documents
        
        return documents
        
    def download_document(self, doc_info):
        """Download and extract text from a document URL"""
        url = doc_info['url']
        authority = doc_info['authority']
        title = doc_info['title']
        
        try:
            # Handle PDF documents
            if url.endswith('.pdf'):
                # Stream the PDF to a file
                response = self.get_with_retry(url)
                if not response:
                    return None
                
                # Save temporary file
                temp_file = f"temp_doc_{hash(url)}.pdf"
                with open(temp_file, 'wb') as f:
                    f.write(response.content)
                
                # Use langchain's PyPDFLoader
                loader = PyPDFLoader(temp_file)
                docs = loader.load()
                
                # Clean up
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                # Add metadata
                for doc in docs:
                    doc.metadata.update({
                        'source': url,
                        'authority': authority,
                        'title': title
                    })
                
                return docs
            
            # Handle web documents
            else:
                response = self.get_with_retry(url)
                if not response:
                    return None
                
                # Create a temporary HTML file if it's an Interregs page
                if authority == 'Interregs':
                    temp_file = f"temp_doc_{hash(url)}.html"
                    with open(temp_file, 'wb') as f:
                        f.write(response.content)
                    
                    # Use WebBaseLoader with local file
                    loader = WebBaseLoader(temp_file)
                    docs = loader.load()
                    
                    # Clean up
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                else:
                    # Use WebBaseLoader with URL
                    loader = WebBaseLoader(url)
                    docs = loader.load()
                
                # Add metadata
                for doc in docs:
                    doc.metadata.update({
                        'source': url,
                        'authority': authority,
                        'title': title
                    })
                
                return docs
                
        except Exception as e:
            st.warning(f"Error downloading document {url}: {e}")
            return None

# Document processor for RAG
class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
    
    def process_documents(self, documents):
        """Process documents for RAG"""
        if not documents:
            return None
        
        # Flatten the list of documents
        flat_docs = []
        for doc_list in documents:
            if doc_list:
                flat_docs.extend(doc_list)
        
        # Split documents
        splits = self.text_splitter.split_documents(flat_docs)
        
        # Create vectorstore
        vectorstore = FAISS.from_documents(documents=splits, embedding=self.embeddings)
        
        return vectorstore
    
    def get_relevant_context(self, vectorstore, query, k=config.MAX_RETRIEVAL_CHUNKS):
        """Get relevant context for a query"""
        if not vectorstore:
            return []
        
        # Create retriever
        retriever = vectorstore.as_retriever(search_kwargs={"k": k})
        
        # Get relevant documents
        relevant_docs = retriever.get_relevant_documents(query)
        
        return relevant_docs

# LLM Chain with MCP (Multi-Chain Prompting) for accurate answers
class RegulatoryLLMChain:
    def __init__(self, api_key=config.GROQ_API_KEY, model_name=config.DEFAULT_MODEL):
        self.api_key = api_key
        self.model_name = model_name
        self.llm = ChatGroq(
            api_key=api_key,
            model_name=model_name
        )
    
    def generate_response(self, query, relevant_docs):
        """Generate a response using Multi-Chain Prompting (MCP)"""
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
            
            Focus only on facts from automotive regulatory documents."""
        )
        
        response_chain = response_prompt | self.llm | StrOutputParser()
        
        final_response = response_chain.invoke({
            "query": query,
            "understanding": understanding,
            "extraction": extraction
        })
        
        return final_response

# Process Map Generator
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
    plt.figure(figsize=(12, 6), dpi=100)
    
    # Get positions from node attributes
    pos = nx.get_node_attributes(G, 'pos')
    
    # Define colors and styles
    node_color = '#4A89DC'  # Modern blue
    edge_color = '#9BB7D4'  # Lighter blue for edges
    font_color = '#333333'  # Dark gray for text
    edge_font_color = '#555555'  # Medium gray for edge text
    font_size = 11
    
    # Draw nodes with increased size and alpha for modern look
    nx.draw_networkx_nodes(
        G, 
        pos, 
        node_size=2500, 
        node_color=node_color, 
        alpha=0.8,
        edgecolors='white',
        linewidths=2,
        node_shape='o'
    )
    
    # Draw edges with curved lines for better visual flow
    nx.draw_networkx_edges(
        G, 
        pos, 
        edge_color=edge_color, 
        width=2,
        alpha=0.7,
        arrows=True, 
        arrowsize=20,
        connectionstyle='arc3,rad=0.1'  # Curved edges
    )
    
    # Draw primary labels with clear offset to avoid overlapping with nodes
    nx.draw_networkx_labels(
        G, 
        pos, 
        font_size=font_size,
        font_family='sans-serif',
        font_weight='bold',
        font_color=font_color
    )
    
    # Draw description labels with greater offset to avoid overlapping
    desc_pos = {}
    for node, coords in pos.items():
        desc_pos[node] = (coords[0], coords[1] - 0.35)  # Greater offset
    
    # Get node descriptions
    node_attrs = nx.get_node_attributes(G, 'description')
    
    # Draw description labels
    nx.draw_networkx_labels(
        G, 
        desc_pos, 
        labels=node_attrs, 
        font_size=font_size-2,  # Smaller font for descriptions
        font_family='sans-serif',
        font_color=edge_font_color,
        alpha=0.8
    )
    
    # Set a light background with a subtle gradient
    ax = plt.gca()
    
    # Remove axis
    plt.axis('off')
    
    # Set tight layout for better space usage
    plt.tight_layout()
    
    # Give the figure a title
    plt.title('Automotive Regulations AI Process Flow', fontsize=14, fontweight='bold', pad=20)
    
    # Convert plot to base64 string
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    return img_str
# Main application logic
def main():
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
        try:
            with st.spinner("Processing your query..."):
                # Log the start of the query process
                # Step 1: Find relevant regulatory documents
                crawler = RegulatoryWebCrawler()
                st.info("Searching for relevant regulatory documents...")
                doc_infos = crawler.find_regulatory_documents(user_query)
                
                if not doc_infos:
                    error_message = "Could not find relevant regulatory documents. Please try a different query."
                    st.error(error_message)
                    # Log error
                    logger.log_query(
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
                processor = DocumentProcessor()
                vectorstore = processor.process_documents(documents)
                
                if not vectorstore:
                    error_message = "Could not process documents. Please try again."
                    st.error(error_message)
                    # Log error
                    logger.log_query(
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
                llm_chain = RegulatoryLLMChain()
                response = llm_chain.generate_response(user_query, relevant_docs)
                
                # Add to history
                st.session_state.history.append({
                    "query": user_query,
                    "response": response
                })
                
                # Log successful query
                logger.log_query(
                    query=user_query,
                    response_status="success",
                    documents_retrieved=len(documents),
                    model_used=config.DEFAULT_MODEL
                )
                
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            st.error(error_message)
            # Log exception
            logger.log_query(
                query=user_query,
                response_status="error",
                error_message=error_message,
                model_used=config.DEFAULT_MODEL
            )
    
    # Display conversation history
    if st.session_state.history:
        st.markdown("### Conversation History")
        for i, exchange in enumerate(st.session_state.history):
            st.markdown(f"#### Q: {exchange['query']}")
            st.markdown(f"{exchange['response']}")
            st.markdown("---")

# Admin utility functions (separate from the main application)
def admin_view_logs(db_path=config.LOG_DB_PATH):
    """Standalone utility for admins to view logs (can be run separately)"""
    if not os.path.exists(db_path):
        print(f"Log database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    try:
        logs_df = pd.read_sql_query("SELECT * FROM usage_logs", conn)
        print(f"Total logs: {len(logs_df)}")
        print(logs_df.head())
        
        # Save to CSV if needed
        csv_path = f"logs/export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        logs_df.to_csv(csv_path, index=False)
        print(f"Logs exported to {csv_path}")
        
    except Exception as e:
        print(f"Error accessing logs: {e}")
    finally:
        conn.close()

# Function to securely modify admin credentials
def change_admin_password(username, new_password, db_path=config.LOG_DB_PATH):
    """Utility to change admin password (can be run separately)"""
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute("SELECT username FROM admin_users WHERE username = ?", (username,))
        if not cursor.fetchone():
            print(f"Admin user '{username}' not found")
            return False
        
        # Update password
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        cursor.execute(
            "UPDATE admin_users SET password_hash = ? WHERE username = ?",
            (password_hash, username)
        )
        conn.commit()
        print(f"Password updated for admin user '{username}'")
        return True
        
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    main()
    
    # Uncomment these lines to run admin utilities (when running script directly)
    # admin_view_logs()
    # change_admin_password(config.DEFAULT_ADMIN_USERNAME, 'new_secure_password')

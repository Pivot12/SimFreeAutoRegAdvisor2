# Calculate base score
base_score = min(0.95, 0.3 + (term_density / 10) + phrase_boost)
        
# Check for regulation numbers
reg_patterns = [
        r'[RU]N?[ -]?R?[ -]?(\d+)',  # UN R## patterns
        r'FMVSS[ -]?(\d+)',  # FMVSS ## patterns
        r'[EU][UC][ -]?(\d+/\d+)',  # EU regulations
        r'GB[ -]?(\d+)',  # China GB standards
        r'CMVSS[ -]?(\d+)'  # Canadian standards
]
        
for pattern in reg_patterns:
    reg_numbers = re.findall(pattern, query)
    if reg_numbers:
        for num in reg_numbers:
            # Check if the regulation number is in the content
            reg_pattern = re.compile(f"[RU]N?[ -]?R?[ -]?{num}|FMVSS[ -]?{num}|[EU][UC][ -]?{num}|GB[ -]?{num}|CMVSS[ -]?{num}", re.IGNORECASE)
            if reg_pattern.search(content):
                base_score = min(0.95, base_score + 0.3)  # Significant boost for regulation match
                break

return base_score

def _extract_text_from_pdf_url(self, url: str) -> str:
"""
Extract text from a PDF URL.

Args:
    url: The URL
    
Returns:
    Extracted text
"""
try:
    # Download the PDF
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Extract text from PDF
    pdf_content = BytesIO(response.content)
    
    # Use PyPDF2 to extract text
    text = ""
    pdf_reader = PyPDF2.PdfReader(pdf_content)
    
    # Get total number of pages
    num_pages = len(pdf_reader.pages)
    
    # Only process up to 20 pages to avoid huge documents
    for page_num in range(min(num_pages, 20)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() + "\n\n"
    
    # Clean up the text
    text = text.replace("\n\n", "\n").strip()
    
    return text
except Exception as e:
    logger.error(f"Error extracting text from PDF URL {url}: {e}")
    return ""

def _extract_text_from_html_url(self, url: str) -> str:
"""
Extract text from an HTML URL.

Args:
    url: The URL
    
Returns:
    Extracted text
"""
try:
    # Download the HTML
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.extract()
    
    # Get text
    text = soup.get_text()
    
    # Break into lines and remove leading and trailing space
    lines = (line.strip() for line in text.splitlines())
    
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    
    # Drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text
except Exception as e:
    logger.error(f"Error extracting text from HTML URL {url}: {e}")
    return ""

def _update_document_relevance(self, doc: Dict[str, Any], query: str, relevance_score: float = None):
"""
Update document relevance in the learning database.

Args:
    doc: Document information
    query: The query
    relevance_score: Optional relevance score override
"""
if not doc.get("url"):
    return
    
url = doc["url"]
source_id = doc.get("source_id", "unknown")
document_id = doc.get("document_id", "unknown")

# Extract topics from the query
topics = self.extract_key_phrases(query)

# Initialize document entry if needed
if url not in self.document_relevance:
    self.document_relevance[url] = {
        "source_id": source_id,
        "document_id": document_id,
        "topics": {},
        "access_count": 1
    }
else:
    # Increment access count
    self.document_relevance[url]["access_count"] = self.document_relevance[url].get("access_count", 0) + 1

# Get or use provided relevance score
if relevance_score is None:
    relevance_score = doc.get("relevance_score", 0.5)

# Update topics
for topic in topics:
    if topic not in self.document_relevance[url].get("topics", {}):
        self.document_relevance[url].setdefault("topics", {})[topic] = relevance_score
    else:
        # Update with weighted average
        current_score = self.document_relevance[url]["topics"][topic]
        count = self.document_relevance[url].get("access_count", 1)
        new_score = (current_score * (count - 1) + relevance_score) / count
        self.document_relevance[url]["topics"][topic] = new_score

class AutoRegulationAdvisor:
"""
An intelligent AI agent that provides accurate answers about automotive regulations
by dynamically retrieving information from regulatory websites based on user queries.
"""

def __init__(self, groq_api_key: str):
"""
Initialize the AutoRegulationAdvisor agent.

Args:
    groq_api_key: API key for Groq
"""
self.groq_api_key = groq_api_key

# Initialize the Groq client
self.groq_client = GroqClient(api_key=groq_api_key)

# Initialize the regulation search engine
self.search_engine = RegulationSearchEngine(groq_client=self.groq_client)

# Configuration
self.max_documents = 5  # Maximum number of documents to retrieve per query
self.max_context_length = 12000  # Maximum context length for LLM (in characters)

def query(self, question: str) -> Dict[str, Any]:
"""
Query the advisor with a question about automotive regulations.
This method dynamically retrieves information from regulatory websites
based on the question.

Args:
    question: The question to ask
    
Returns:
    A dictionary containing the answer, sources, and confidence score
"""
start_time = time.time()

try:
    # Search for relevant documents
    st.markdown("### Searching for relevant regulatory information...")
    documents = self.search_engine.search_for_documents(question, top_n=3)
    
    if not documents:
        return {
            "answer": "I'm sorry, but I couldn't find any relevant automotive regulatory information for your question. Could you try rephrasing your question with more specific terms, regulation numbers, or regional requirements?",
            "sources": [],
            "confidence": 0.0,
            "clean_response": "No relevant regulatory information found."
        }
    
    # Extract relevant sections from documents
    st.markdown("### Analyzing regulatory documents...")
    relevant_sections = self._extract_relevant_sections(question, documents)
    
    # Generate a prompt for the LLM
    prompt = self._generate_prompt(question, relevant_sections, documents)
    
    # Query the LLM
    st.markdown("### Generating response...")
    system_prompt = """You are an expert in global automotive regulations with 30 years of experience. 
    Your task is to provide accurate, detailed answers based solely on the provided regulatory information.
    Include specific regulatory references and section numbers in your answer.
    If the provided information doesn't fully answer the question, clearly state what is known and what is missing.
    Always provide the most up-to-date information available."""
    
    answer = self.groq_client.generate_sync(prompt, system_prompt=system_prompt)
    
    # Clean the response
    clean_response = self._clean_response(answer)
    
    # Calculate confidence based on document scores and answer quality
    confidence = self._calculate_confidence(documents, answer, question)
    
    # Prepare the sources for the response
    sources = []
    for doc in documents:
        if "url" in doc and "source_id" in doc and "document_id" in doc:
            source_info = {
                "url": doc["url"],
                "source_id": doc["source_id"],
                "document_id": doc["document_id"],
                "relevance_score": doc.get("relevance_score", 0.5)
            }
            sources.append(source_info)
    
    # Calculate response time
    processing_time = time.time() - start_time
    
    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "clean_response": clean_response,
        "processing_time": processing_time
    }
    
except Exception as e:
    logger.error(f"Error processing query: {e}")
    
    return {
        "answer": f"I'm sorry, but I encountered an error while processing your question: {str(e)}",
        "sources": [],
        "confidence": 0.0,
        "clean_response": f"Error: {str(e)}",
        "processing_time": time.time() - start_time
    }

def _extract_relevant_sections(self, question: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
"""
Extract relevant sections from documents based on the question.

Args:
    question: The question
    documents: List of documents
    
Returns:
    List of relevant sections with their source information
"""
relevant_sections = []

# Extract key terms from the question
key_terms = self.search_engine.extract_key_phrases(question)

for doc in documents:
    # Skip if no content
    if "content" not in doc or not doc["content"]:
        continue
    
    content = doc["content"]
    
    # Split content into paragraphs
    paragraphs = re.split(r'\n\s*\n|\r\n\s*\r\n', content)
    
    # For each paragraph, check relevance to the question
    for para_idx, paragraph in enumerate(paragraphs):
        # Skip short paragraphs
        if len(paragraph.strip()) < 50:
            continue
        
        # Check if paragraph contains any key terms
        if not any(term.lower() in paragraph.lower() for term in key_terms):
            continue
        
        # Calculate relevance score
        relevance = self.search_engine._calculate_relevance_score(paragraph, question)
        
        if relevance > 0.4:  # Threshold for relevance
            # Find the section number or title if available
            section_title = ""
            
            # Look for section patterns like "Section 4.1" or "CHAPTER II"
            section_match = re.search(r'(?:Section|Chapter|Paragraph|Article|Annex)\s+[\d\w\.]+', paragraph, re.IGNORECASE)
            if section_match:
                section_title = section_match.group(0)
            
            # Add to relevant sections
            relevant_sections.append({
                "source_id": doc["source_id"],
                "document_id": doc.get("document_id", ""),
                "document_url": doc.get("url", ""),
                "paragraph_index": para_idx,
                "section_title": section_title,
                "excerpt": paragraph.strip(),
                "relevance": relevance
            })

# Sort by relevance
relevant_sections.sort(key=lambda x: x["relevance"], reverse=True)

# Limit to avoid context length issues
total_length = 0
filtered_sections = []

for section in relevant_sections:
    section_length = len(section["excerpt"])
    if total_length + section_length <= self.max_context_length:
        filtered_sections.append(section)
        total_length += section_length
    else:
        # If we can't fit any more full sections, break
        break

return filtered_sections

def _generate_prompt(self, question: str, relevant_sections: List[Dict[str, Any]], 
                documents: List[Dict[str, Any]]) -> str:
"""
Generate a prompt for the LLM based on the question and relevant sections.

Args:
    question: The question to ask
    relevant_sections: List of relevant sections
    documents: Original documents information
    
Returns:
    The generated prompt
"""
prompt = f"Question about automotive regulations: {question}\n\n"
prompt += "Here are the relevant sections from regulatory documents:\n\n"

# Add relevant sections with source information
for i, section in enumerate(relevant_sections):
    source_id = section["source_id"]
    reg_body_name = next((body_info["name"] for body_id, body_info in 
                        self.search_engine.regulatory_bodies.items() 
                        if body_id == source_id), source_id)
    
    prompt += f"Section {i+1} - Source: {reg_body_name}"
    
    if section["section_title"]:
        prompt += f", {section['section_title']}"
    
    if section["document_url"]:
        prompt += f"\nURL: {section['document_url']}"
    
    prompt += f"\n{section['excerpt']}\n\n"

# Add instructions for the response
prompt += """
Based only on the regulatory information provided above, please answer the question comprehensively.

Please include:
1. The specific regulatory references (regulation numbers, sections, etc.)
2. Direct quotes of key requirements or provisions (if available)
3. Any relevant test methods or compliance criteria
4. Regional differences in requirements (if mentioned)
5. Any implementation dates or phase-in periods

If the provided information doesn't fully address the question, clearly state what aspects are covered and what information is missing.

Format your answer in a clean, structured manner with appropriate headings and bullet points as needed.
"""
        
        return prompt
    
    def _clean_response(self, response: str) -> str:
        """
        Clean the LLM response to make it more presentable.
        
        Args:
            response: The raw LLM response
            
        Returns:
            The cleaned response
        """
        # Check if the response already has good formatting
        if "##" in response or "**" in response:
            return response
        
        # Split into sections based on common patterns
        sections = []
        current_section = []
        current_title = None
        
        for line in response.splitlines():
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if this is a section header
            if re.match(r'^[\d\.]+\s+\w+', line) or line.isupper() or (
                    len(line) < 70 and line.endswith(':')):
                # If we have a current section, add it
                if current_section:
                    sections.append((current_title, '\n'.join(current_section)))
                
                # Start a new section
                current_title = line
                current_section = []
            else:
                # Add to current section
                current_section.append(line)
        
        # Add the last section
        if current_section:
            sections.append((current_title, '\n'.join(current_section)))
        
        # Format the response
        clean_response = ""
        
        for title, content in sections:
            if title:
                clean_response += f"## {title}\n\n"
            clean_response += f"{content}\n\n"
        
        # If no sections were found, just return the original response
        if not clean_response:
            return response
        
        return clean_response.strip()
    
    def _calculate_confidence(self, documents: List[Dict[str, Any]], answer: str, question: str) -> float:
        """
        Calculate confidence score based on document relevance and answer quality.
        
        Args:
            documents: List of documents
            answer: The generated answer
            question: The original question
            
        Returns:
            Confidence score (0-1)
        """
        # Calculate base confidence from document relevance
        if not documents:
            return 0.3  # Low confidence if no documents
        
        avg_doc_score = sum(doc.get("relevance_score", 0.3) for doc in documents) / len(documents)
        
        # Adjust confidence based on answer characteristics
        
        # Check for specific regulation references
        reg_patterns = [
            r'[RU]N?\s?R?\s?(\d+)',  # UN R## patterns
            r'FMVSS\s?(\d+)',  # FMVSS ## patterns
            r'[EU][UC]\s?(\d+/\d+)',  # EU regulations
            r'GB\s?(\d+)',  # China GB standards
            r'CMVSS\s?(\d+)'  # Canadian standards
        ]
        
        has_reg_refs = any(re.search(pattern, answer) for pattern in reg_patterns)
        
        # Check for specific requirements language
        req_keywords = [
            r'shall', r'must', r'required', r'minimum', r'maximum',
            r'at least', r'no more than', r'requirements'
        ]
        
        has_req_terms = any(re.search(keyword, answer, re.IGNORECASE) for keyword in req_keywords)
        
        # Check if there are specific measurements or values
        has_measurements = bool(re.search(r'(\d+(\.\d+)?)\s?(mm|cm|m|lux|cd|°|degrees)', answer))
        
        # Check if the answer addresses limitations
        has_limitations = (
            'not specified in' in answer.lower() or
            'information is not provided' in answer.lower() or
            'not covered in' in answer.lower()
        )
        
        # Calculate confidence adjustments
        confidence_adjustments = 0.0
        if has_reg_refs:
            confidence_adjustments += 0.15
        if has_req_terms:
            confidence_adjustments += 0.10
        if has_measurements:
            confidence_adjustments += 0.10
        if has_limitations:
            confidence_adjustments -= 0.05  # Slight reduction if limitations are noted
            
        # Overall confidence calculation
        confidence = avg_doc_score * 0.7 + confidence_adjustments
        
        # Clip to valid range
        return max(0.1, min(0.95, confidence))

# Initialize the Streamlit application
def main():
    st.title("🚗 Automotive Regulation Intelligent Agent")
    st.subheader("Ask questions about global automotive regulations")
    
    # Sidebar
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1642/1642069.png", width=100)
    st.sidebar.title("SimFreeAutoRegAdvisor2")
    st.sidebar.markdown("This intelligent agent provides answers about automotive regulations by dynamically searching regulatory websites.")

    # Groq API key input
    groq_api_key = st.sidebar.text_input("Groq API Key", type="password")
    
    # Initialize session state for query history
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    
    # Example queries
    st.sidebar.markdown("### Example Queries")
    examples = [
        "What are the requirements for headlights in UNECE R48?",
        "Are backup cameras mandatory in the US according to FMVSS 111?",
        "What is the minimum braking performance required by EU regulations?",
        "What are the sound requirements for electric vehicles in UN R138?"
    ]
    
    for example in examples:
        if st.sidebar.button(example):
            st.session_state.question = example
    
    # Query history
    st.sidebar.markdown("### Recent Queries")
    if not st.session_state.query_history:
        st.sidebar.markdown("No recent queries")
    else:
        for i, query in enumerate(st.session_state.query_history[-5:]):
            st.sidebar.markdown(f"**{i+1}.** {query['question'][:40]}...")
    
    # Main content
    if "question" not in st.session_state:
        st.session_state.question = ""
    
    question = st.text_area("Enter your question about automotive regulations:", 
                          st.session_state.question, 
                          height=100,
                          help="Ask about specific regulations, requirements, or standards")
    
    col1, col2 = st.columns([1, 5])
    submit = col1.button("Submit")
    
    if submit and question and groq_api_key:
        with st.spinner("Processing your query..."):
            try:
                # Initialize the advisor
                advisor = AutoRegulationAdvisor(groq_api_key=groq_api_key)
                
                # Process the query
                result = advisor.query(question)
                
                # Store in query history
                st.session_state.query_history.append({
                    "question": question,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "result": result
                })
                
                # Reset the query input
                st.session_state.question = ""
                
                # Display result
                st.markdown("## Answer")
                
                # Display confidence and processing time
                col1, col2 = st.columns(2)
                col1.metric("Confidence", f"{int(result['confidence'] * 100)}%")
                col2.metric("Processing Time", f"{result['processing_time']:.2f}s")
                
                # Display the answer
                st.markdown(result['clean_response'])
                
                # Display sources
                st.markdown("## Sources")
                for i, source in enumerate(result['sources']):
                    with st.expander(f"{source['source_id']} - {source['document_id']} (Relevance: {int(source['relevance_score'] * 100)}%)"):
                        st.markdown(f"**URL:** [{source['url']}]({source['url']})")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    elif submit and not groq_api_key:
        st.error("Please enter your Groq API key in the sidebar to proceed.")
    elif submit and not question:
        st.error("Please enter a question.")

if __name__ == "__main__":
    main()import streamlit as st
import requests
import re
import json
import logging
import time
import hashlib
import os
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
from urllib.parse import urljoin, urlparse
from io import BytesIO
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
import PyPDF2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Automotive Regulation Advisor",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

class GroqClient:
    """Client for interacting with the Groq API."""
    
    def __init__(self, api_key: str, model: str = "llama3-70b-8192"):
        """
        Initialize the Groq client.
        
        Args:
            api_key: Groq API key
            model: Model to use (default: llama3-70b-8192)
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0) -> str:
        """
        Generate a response from the Groq API.
        
        Args:
            prompt: The prompt to send to the model
            system_prompt: Optional system prompt
            temperature: Temperature for generation (0-1)
            
        Returns:
            The generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            raise

    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0) -> str:
        """
        Generate a response from the Groq API (synchronous version).
        
        Args:
            prompt: The prompt to send to the model
            system_prompt: Optional system prompt
            temperature: Temperature for generation (0-1)
            
        Returns:
            The generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            raise

class RegulationSearchEngine:
    """
    Search engine for finding relevant regulatory information based on query classification.
    """
    
    def __init__(self, groq_client):
        """
        Initialize the regulation search engine.
        
        Args:
            groq_client: GroqClient instance for LLM capabilities
        """
        self.groq_client = groq_client
        
        # Define regulatory bodies and their search patterns
        self.regulatory_bodies = self._initialize_regulatory_bodies()
        
        # Initialize in-memory document cache for the current session
        self.document_cache = {}
        
        # Initialize in-memory learning for the session
        self.query_patterns = {}
        self.document_relevance = {}
    
    def _initialize_regulatory_bodies(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize the regulatory bodies with their search patterns and metadata.
        
        Returns:
            Dictionary of regulatory bodies
        """
        return {
            "UNECE": {
                "name": "United Nations Economic Commission for Europe",
                "base_url": "https://unece.org/transport/vehicle-regulations",
                "search_url": "https://unece.org/transport/vehicle-regulations-wp29/standards/addenda-1958-agreement-regulations-161-180",
                "patterns": [
                    r"R\d+",  # UN Regulation numbers
                    r"GTR\s*No\.\s*\d+",  # Global Technical Regulations
                    r"light",
                    r"brake",
                    r"emission",
                    r"safety",
                    r"electric",
                    r"autonomous"
                ],
                "document_url_patterns": [
                    r"https://unece.org/.*?pdf"
                ],
                "relevance": {
                    "lighting": 0.9,
                    "braking": 0.9,
                    "emissions": 0.9,
                    "safety": 0.9,
                    "autonomous": 0.9,
                    "vehicle type approval": 0.9,
                    "global harmonization": 0.9
                }
            },
            "NHTSA": {
                "name": "National Highway Traffic Safety Administration",
                "base_url": "https://www.nhtsa.gov/laws-regulations/fmvss",
                "search_url": "https://www.nhtsa.gov/laws-regulations",
                "patterns": [
                    r"FMVSS\s*No\.\s*\d+",  # Federal Motor Vehicle Safety Standards
                    r"Federal Motor Vehicle Safety Standard",
                    r"NCAP",  # New Car Assessment Program
                    r"recall",
                    r"compliance",
                    r"crash test"
                ],
                "document_url_patterns": [
                    r"https://www.nhtsa.gov/.*?pdf"
                ],
                "relevance": {
                    "crash safety": 0.95,
                    "US regulations": 0.95,
                    "FMVSS": 0.95,
                    "recalls": 0.9,
                    "NCAP": 0.9,
                    "compliance": 0.9,
                    "CAFE": 0.8  # Corporate Average Fuel Economy
                }
            },
            "EU": {
                "name": "European Union Regulations",
                "base_url": "https://eur-lex.europa.eu/homepage.html",
                "search_url": "https://eur-lex.europa.eu/search.html?scope=EURLEX&type=quick&qid=1566991056761&CC_1_CODED=07",
                "patterns": [
                    r"EU\s*\d+/\d+",  # EU Regulation numbers
                    r"EC\s*\d+/\d+",  # EC Regulation numbers
                    r"Euro\s*\d+",  # Euro emissions standards
                    r"WLTP",  # Worldwide Harmonized Light Vehicles Test Procedure
                    r"RDE",  # Real Driving Emissions
                    r"type approval"
                ],
                "document_url_patterns": [
                    r"https://eur-lex.europa.eu/.*?\.pdf"
                ],
                "relevance": {
                    "European regulations": 0.95,
                    "Euro emissions": 0.9,
                    "type approval": 0.9,
                    "WLTP": 0.9,
                    "RDE": 0.9,
                    "European market": 0.9
                }
            },
            "CMVSS": {
                "name": "Canadian Motor Vehicle Safety Standards",
                "base_url": "https://tc.canada.ca/en/road-transportation/motor-vehicle-safety/motor-vehicle-safety-regulations-schedule-iii-standard-100-600",
                "search_url": "https://tc.canada.ca/en/road-transportation/motor-vehicle-safety",
                "patterns": [
                    r"CMVSS\s*\d+",  # Canadian Motor Vehicle Safety Standards numbers
                    r"Transport Canada",
                    r"Canadian certification"
                ],
                "document_url_patterns": [
                    r"https://tc.canada.ca/.*?\.pdf"
                ],
                "relevance": {
                    "Canadian regulations": 0.95,
                    "CMVSS": 0.9,
                    "Canadian market": 0.9
                }
            },
            "China": {
                "name": "China GB Standards",
                "base_url": "http://www.gb688.cn/bzgk/gb/index",
                "search_url": "http://www.gb688.cn/bzgk/gb/std_list?p.p1=0&p.p90=circulation_date&p.p91=desc",
                "patterns": [
                    r"GB\s*\d+",  # GB Standard numbers
                    r"China certification",
                    r"CCC",  # China Compulsory Certification
                    r"Chinese market"
                ],
                "document_url_patterns": [
                    r"http://www.gb688.cn/.*?\.pdf"
                ],
                "relevance": {
                    "Chinese regulations": 0.95,
                    "GB standards": 0.9,
                    "CCC": 0.9,
                    "Chinese market": 0.9
                }
            },
            "Japan": {
                "name": "Japan Automotive Standards",
                "base_url": "https://www.mlit.go.jp/jidosha/jidosha_fr10_000006.html",
                "search_url": "https://www.mlit.go.jp/jidosha/jidosha_fr10_000006.html",
                "patterns": [
                    r"J-NCAP",  # Japan New Car Assessment Program
                    r"Japan certification",
                    r"Japanese market",
                    r"TRIAS"  # Japanese Test Requirements and Instructions for Automobile Standards
                ],
                "document_url_patterns": [
                    r"https://www.mlit.go.jp/.*?\.pdf"
                ],
                "relevance": {
                    "Japanese regulations": 0.95,
                    "J-NCAP": 0.9,
                    "Japanese market": 0.9,
                    "TRIAS": 0.9
                }
            }
        }
    
    def extract_key_phrases(self, text: str) -> List[str]:
        """
        Extract key phrases from text using pattern matching.
        
        Args:
            text: The text to extract key phrases from
            
        Returns:
            List of key phrases
        """
        # First, try to detect specific regulation references, which are high-value
        reg_refs = []
        
        # UN/ECE regulations
        un_regs = re.findall(r'UN[ -]?R[ -]?(\d+)', text, re.IGNORECASE)
        if un_regs:
            reg_refs.extend([f"UN R{num}" for num in un_regs])
        
        # FMVSS regulations
        fmvss = re.findall(r'FMVSS[ -]?(\d+)', text, re.IGNORECASE)
        if fmvss:
            reg_refs.extend([f"FMVSS {num}" for num in fmvss])
        
        # EU regulations
        eu_regs = re.findall(r'(EU|EC)[ -]?(\d+/\d+)', text, re.IGNORECASE)
        if eu_regs:
            reg_refs.extend([f"{prefix} {num}" for prefix, num in eu_regs])
        
        # If we found specific regulation references, prioritize them
        if reg_refs:
            return reg_refs
        
        # Extract common automotive regulatory terms
        auto_terms = []
        common_terms = [
            "headlight", "brake", "emission", "safety", "airbag", "seatbelt",
            "crashworthiness", "pedestrian", "type approval", "homologation",
            "certification", "compliance", "recall", "ADAS", "electric", "hybrid",
            "autonomous", "self-driving", "fuel efficiency", "noise", "tire"
        ]
        
        for term in common_terms:
            if term.lower() in text.lower():
                auto_terms.append(term)
        
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if len(w) > 3 and w not in [
            'what', 'when', 'where', 'which', 'who', 'why', 'how',
            'does', 'are', 'about', 'with', 'from', 'have', 'that', 'this'
        ]]
        
        # Combine automotive terms with keywords
        return auto_terms + keywords
    
    def classify_query(self, query: str) -> Dict[str, float]:
        """
        Classify a query to determine which regulatory bodies are most relevant.
        
        Args:
            query: The query to classify
            
        Returns:
            Dictionary mapping regulatory body IDs to relevance scores (0-1)
        """
        relevance_scores = {}
        
        # First, check the learning database for similar patterns
        key_phrases = self.extract_key_phrases(query)
        
        # Check for learned patterns
        learned_relevance = {}
        
        for phrase in key_phrases:
            for pattern, pattern_data in self.query_patterns.items():
                if phrase.lower() in pattern.lower():
                    bodies = pattern_data.get("regulatory_bodies", [])
                    relevance = pattern_data.get("relevance", 0.5)
                    
                    for body in bodies:
                        if body in learned_relevance:
                            learned_relevance[body] = max(learned_relevance[body], float(relevance))
                        else:
                            learned_relevance[body] = float(relevance)
        
        # If we have learned relevance, use it with a weight
        if learned_relevance:
            for body, score in learned_relevance.items():
                relevance_scores[body] = score * 0.7  # 70% weight to learned patterns
        
        # Second, use pattern matching on the query
        query_lower = query.lower()
        
        for body_id, body_info in self.regulatory_bodies.items():
            # Start with default score of 0.1
            if body_id not in relevance_scores:
                relevance_scores[body_id] = 0.1
            
            # Check for explicit mentions of the body
            if body_id.lower() in query_lower or body_info["name"].lower() in query_lower:
                relevance_scores[body_id] = max(relevance_scores[body_id], 0.9)
                continue
            
            # Check patterns
            for pattern in body_info["patterns"]:
                if re.search(pattern, query, re.IGNORECASE):
                    relevance_scores[body_id] = max(relevance_scores[body_id], 0.8)
                    break
            
            # Check relevance dictionary
            for topic, score in body_info.get("relevance", {}).items():
                if topic.lower() in query_lower:
                    relevance_scores[body_id] = max(relevance_scores[body_id], score * 0.3)  # 30% weight to predefined patterns
        
        # If no strong matches, use LLM for classification
        if not any(score > 0.5 for score in relevance_scores.values()):
            try:
                prompt = f"""
                Analyze this automotive regulatory query and determine which regulatory bodies/standards are most relevant:
                
                "{query}"
                
                Return ONLY a JSON object mapping regulatory body IDs to relevance scores (0-1), with no explanation.
                Consider: UNECE, NHTSA, EU, CMVSS, China, Japan
                Example: {{"UNECE": 0.9, "EU": 0.7, "NHTSA": 0.3, "CMVSS": 0.1, "China": 0.1, "Japan": 0.1}}
                """
                
                result = self.groq_client.generate_sync(prompt)
                # Extract JSON object from response
                result = result.strip()
                if result.startswith("```json"):
                    result = result[7:]
                if result.endswith("```"):
                    result = result[:-3]
                
                result = result.strip()
                llm_scores = json.loads(result)
                
                # Merge with existing scores, with higher weight to LLM
                for body_id, score in llm_scores.items():
                    if body_id in relevance_scores:
                        relevance_scores[body_id] = relevance_scores[body_id] * 0.3 + float(score) * 0.7
                    else:
                        relevance_scores[body_id] = float(score) * 0.7
            
            except Exception as e:
                logger.error(f"Error classifying query with LLM: {e}")
        
        # Normalize scores to sum to 1
        total = sum(relevance_scores.values())
        if total > 0:
            return {k: v / total for k, v in relevance_scores.items()}
        return {k: 1.0 / len(relevance_scores) for k in relevance_scores}
    
    def search_for_documents(self, query: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant documents based on the query.
        
        Args:
            query: The query
            top_n: Number of top regulatory bodies to search
            
        Returns:
            List of document information dictionaries
        """
        # Use a progress bar to show search progress
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Classify the query to determine which regulatory bodies are most relevant
        status_text.text("Classifying query...")
        relevance_scores = self.classify_query(query)
        progress_bar.progress(10)
        
        # Sort regulatory bodies by relevance
        sorted_bodies = sorted(
            relevance_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Select top N regulatory bodies
        selected_bodies = [body_id for body_id, _ in sorted_bodies[:top_n]]
        progress_bar.progress(20)
        
        # Check if we have any learned document relevance for this query
        relevant_documents = self._get_relevant_documents_from_learning(query, selected_bodies)
        progress_bar.progress(30)
        
        # If we have enough relevant documents from learning, use them
        if len(relevant_documents) >= 3:
            progress_bar.progress(100)
            status_text.empty()
            return relevant_documents[:5]  # Limit to 5 documents
        
        # Otherwise, search regulatory websites
        documents = []
        
        for i, body_id in enumerate(selected_bodies):
            progress_percent = 30 + (i / len(selected_bodies)) * 60
            progress_bar.progress(int(progress_percent))
            status_text.text(f"Searching {body_id} regulatory documents...")
            
            body_info = self.regulatory_bodies[body_id]
            
            # Search the regulatory website
            body_documents = self._search_regulatory_website(body_id, body_info, query)
            documents.extend(body_documents)
        
        # Sort documents by relevance
        documents.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Update learning database
        for doc in documents:
            self._update_document_relevance(doc, query)
        
        # Limit to 5 documents
        progress_bar.progress(100)
        status_text.empty()
        return documents[:5]
    
    def _get_relevant_documents_from_learning(self, query: str, selected_bodies: List[str]) -> List[Dict[str, Any]]:
        """
        Get relevant documents from learning database.
        
        Args:
            query: The query
            selected_bodies: List of selected regulatory body IDs
            
        Returns:
            List of document information dictionaries
        """
        # Extract key phrases from the query
        key_phrases = self.extract_key_phrases(query)
        
        relevant_documents = {}
        
        for phrase in key_phrases:
            for doc_url, doc_data in self.document_relevance.items():
                # Check if document is from a selected body and relevant to the phrase
                if doc_data["source_id"] in selected_bodies:
                    for topic, relevance in doc_data.get("topics", {}).items():
                        if phrase.lower() in topic.lower() and relevance > 0.5:
                            if doc_url not in relevant_documents:
                                relevant_documents[doc_url] = {
                                    "url": doc_url,
                                    "source_id": doc_data["source_id"],
                                    "document_id": doc_data["document_id"],
                                    "content": doc_data.get("content", ""),
                                    "relevance_score": relevance,
                                    "access_count": doc_data.get("access_count", 1)
                                }
                            else:
                                # Update relevance if higher
                                if relevance > relevant_documents[doc_url]["relevance_score"]:
                                    relevant_documents[doc_url]["relevance_score"] = relevance
        
        # Convert dictionary to list and sort by relevance
        documents = list(relevant_documents.values())
        documents.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return documents
    
    def _search_regulatory_website(self, body_id: str, body_info: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        """
        Search a regulatory website for relevant documents.
        
        Args:
            body_id: ID of the regulatory body
            body_info: Information about the regulatory body
            query: The query
            
        Returns:
            List of document information dictionaries
        """
        documents = []
        
        try:
            # Construct search terms
            search_terms = query
            
            # Try to extract specific regulation numbers or keywords
            reg_numbers = re.findall(r'[RU]N?[ -]?R?[ -]?(\d+)', query)  # Match UN R## patterns
            fmvss_numbers = re.findall(r'FMVSS[ -]?(\d+)', query)  # Match FMVSS ## patterns
            eu_regs = re.findall(r'[EU][UC][ -]?(\d+/\d+)', query)  # Match EU regulations
            
            if reg_numbers:
                search_terms = f"{body_id} regulation {reg_numbers[0]}"
            elif fmvss_numbers:
                search_terms = f"FMVSS {fmvss_numbers[0]}"
            elif eu_regs:
                search_terms = f"EU regulation {eu_regs[0]}"
            else:
                # Extract key terms for more effective search
                key_phrases = self.extract_key_phrases(query)
                if key_phrases:
                    search_terms = f"{body_id} {' '.join(key_phrases[:2])}"
            
            # Use the search URL for the regulatory body
            search_url = body_info.get("search_url", body_info["base_url"])
            
            # For some regulatory bodies, we might need to construct a search URL
            if "eur-lex.europa.eu" in search_url:
                search_url = f"{search_url}&text={search_terms.replace(' ', '%20')}"
            
            # Fetch the search page
            logger.info(f"Searching {body_id} with search terms: {search_terms}")
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find links that might be relevant documents
            found_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                
                # Check if the link matches our document patterns
                for pattern in body_info.get("document_url_patterns", []):
                    if re.search(pattern, href, re.IGNORECASE):
                        # Make sure it's an absolute URL
                        if not href.startswith("http"):
                            href = urljoin(search_url, href)
                        
                        # Check if this link might be relevant to our query
                        link_text = a.text.strip().lower()
                        if any(term.lower() in link_text for term in search_terms.split()):
                            found_links.append(href)
                            break
            
            # If we didn't find any links with the patterns, look for PDF links
            if not found_links:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.endswith(".pdf"):
                        # Make sure it's an absolute URL
                        if not href.startswith("http"):
                            href = urljoin(search_url, href)
                        
                        # Check if this link might be relevant to our query
                        link_text = a.text.strip().lower()
                        if any(term.lower() in link_text for term in search_terms.split()):
                            found_links.append(href)
            
            # Process up to 3 links
            for link in found_links[:3]:
                # Generate a document ID from the URL
                doc_id = self._generate_document_id(link)
                
                # Check if the document is already in our cache
                if link in self.document_cache:
                    doc_cache = self.document_cache[link]
                    
                    # Add to documents list
                    documents.append({
                        "url": link,
                        "source_id": body_id,
                        "document_id": doc_id,
                        "content": doc_cache["content"],
                        "relevance_score": 0.7  # Default score for cached documents
                    })
                    continue
                
                # Download and process the document
                if link.endswith(".pdf"):
                    # PDF document
                    content = self._extract_text_from_pdf_url(link)
                else:
                    # HTML document
                    content = self._extract_text_from_html_url(link)
                
                if content:
                    # Calculate relevance score based on query terms
                    relevance_score = self._calculate_relevance_score(content, query)
                    
                    # Cache the document
                    self.document_cache[link] = {
                        "url": link,
                        "source_id": body_id,
                        "document_id": doc_id,
                        "content": content,
                        "timestamp": time.time(),
                        "last_accessed": time.time(),
                        "access_count": 1
                    }
                    
                    # Add to documents list
                    documents.append({
                        "url": link,
                        "source_id": body_id,
                        "document_id": doc_id,
                        "content": content,
                        "relevance_score": relevance_score
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error searching regulatory website {body_id}: {e}")
            return []
    
    def _generate_document_id(self, url: str) -> str:
        """
        Generate a document ID from a URL.
        
        Args:
            url: The URL
            
        Returns:
            Document ID
        """
        # Extract filename from URL
        parsed_url = urlparse(url)
        path = parsed_url.path
        filename = os.path.basename(path)
        
        # Remove extension
        filename = os.path.splitext(filename)[0]
        
        # Clean up the filename
        filename = re.sub(r'[^\w\-]', '_', filename)
        
        # If filename is too long, truncate it and add a hash
        if len(filename) > 20:
            hash_suffix = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{filename[:12]}_{hash_suffix}"
        
        return filename
    
    def _calculate_relevance_score(self, content: str, query: str) -> float:
        """
        Calculate relevance score for a document based on the query.
        
        Args:
            content: Document content
            query: The query
            
        Returns:
            Relevance score (0-1)
        """
        # Convert to lowercase for comparison
        content_lower = content.lower()
        query_lower = query.lower()
        
        # Split query into terms
        query_terms = re.findall(r'\b\w+\b', query_lower)
        query_terms = [term for term in query_terms if len(term) > 3]
        
        if not query_terms:
            return 0.5  # Default score
        
        # Count occurrences of query terms
        term_count = sum(content_lower.count(term) for term in query_terms)
        
        # Check for exact phrases
        phrases = re.findall(r'"([^"]+)"', query)
        phrase_matches = sum(content_lower.count(phrase.lower()) for phrase in phrases)
        
        # Calculate score based on term density and phrase matches
        term_density = term_count / (len(content) / 100)  # Terms per 100 characters
        
        # Boost score if phrases match
        phrase_boost = 0.2 * phrase_matches
        
        # Calculate base score
        base_score = min(0.95, 0.3 + (term_density / 10) + phrase_boost)
        
        # Check for regulation numbers
        reg_patterns = [
            r'[RU]N?[ -]?R?[ -]?(\d+)',  # UN R## patterns
            r'FMVSS[ -]?(\d+)',  # FMVSS ## patterns
            r'[EU][UC][ -]?(\

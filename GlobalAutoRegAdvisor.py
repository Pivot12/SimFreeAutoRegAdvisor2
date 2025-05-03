"""
SimFreeAutoRegAdvisor2: An AI agent for automotive regulations
This implementation fixes document access and response cleaning issues
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# For web scraping and document processing
import requests
from bs4 import BeautifulSoup
import PyPDF2
from io import BytesIO

# Vector database
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

# LLM integration
import json
import httpx
from langchain.chains import RetrievalQA
from langchain.llms.base import LLM
from typing import Any, List, Mapping, Optional
from langchain.callbacks.manager import CallbackManagerForLLMRun

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GroqLLM(LLM):
    """
    Custom LLM wrapper for Groq API with Llama model.
    """
    
    groq_api_key: str
    model_name: str = "llama3-70b-8192"
    temperature: float = 0
    
    @property
    def _llm_type(self) -> str:
        return "groq_llm"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature
        }
        
        if stop:
            payload["stop"] = stop
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            raise

class AutoRegulationAdvisor:
    """
    An AI agent that provides accurate answers about automotive regulations
    by retrieving and using actual regulatory documents.
    """
    
    def __init__(self, groq_api_key: str, data_dir: str = "regulatory_data"):
        """
        Initialize the AutoRegulationAdvisor agent.
        
        Args:
            groq_api_key: API key for Groq
            data_dir: Directory to store the regulatory documents and vector database
        """
        self.groq_api_key = groq_api_key
        
        # Set up directories
        self.data_dir = Path(data_dir)
        self.docs_dir = self.data_dir / "documents"
        self.db_dir = self.data_dir / "vectordb"
        
        # Create directories if they don't exist
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize regulatory sources
        self.regulatory_sources = self._initialize_regulatory_sources()
        
        # Set up text splitter for document processing
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # Set up embeddings using sentence-transformers (free alternative to OpenAI embeddings)
        from langchain_community.embeddings import HuggingFaceEmbeddings
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Initialize the vector store if it exists, otherwise it will be created when documents are added
        self._initialize_vector_store()
        
        # Set up the LLM using Groq
        self.llm = GroqLLM(
            groq_api_key=groq_api_key,
            model_name="llama3-70b-8192",
            temperature=0
        )
    
    def _initialize_regulatory_sources(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize the regulatory sources with their respective metadata.
        
        Returns:
            A dictionary of regulatory sources with metadata.
        """
        return {
            "UNECE": {
                "name": "United Nations Economic Commission for Europe",
                "base_url": "https://unece.org/transport/vehicle-regulations",
                "document_patterns": [
                    r"https://unece.org/.*?/(?:ECE-TRANS-WP29|wp29).*?\.pdf"
                ],
                "scrape_method": "unece_scraper"
            },
            "NHTSA": {
                "name": "National Highway Traffic Safety Administration",
                "base_url": "https://www.nhtsa.gov/laws-regulations/fmvss",
                "document_patterns": [
                    r"https://www.nhtsa.gov/.*?/pdf"
                ],
                "scrape_method": "nhtsa_scraper"
            },
            "EU": {
                "name": "European Union Regulations",
                "base_url": "https://eur-lex.europa.eu/homepage.html",
                "document_patterns": [
                    r"https://eur-lex.europa.eu/.*?\.pdf"
                ],
                "search_url": "https://eur-lex.europa.eu/search.html?qid=1566991056761&text=vehicle%20regulation&scope=EURLEX&type=quick&lang=en",
                "scrape_method": "eu_scraper"
            },
            "CMVSS": {
                "name": "Canadian Motor Vehicle Safety Standards",
                "base_url": "https://tc.canada.ca/en/road-transportation/motor-vehicle-safety/motor-vehicle-safety-regulations-schedule-iii-standard-100-600",
                "document_patterns": [
                    r"https://tc.canada.ca/.*?/pdf"
                ],
                "scrape_method": "cmvss_scraper"
            },
            "China": {
                "name": "China GB Standards",
                "base_url": "http://www.gb688.cn/bzgk/gb/index",
                "document_patterns": [
                    r"http://www.gb688.cn/.*?\.pdf"
                ],
                "scrape_method": "china_scraper"
            },
            "Japan": {
                "name": "Japan Automotive Standards",
                "base_url": "https://www.mlit.go.jp/jidosha/jidosha_fr10_000006.html",
                "document_patterns": [
                    r"https://www.mlit.go.jp/.*?\.pdf"
                ],
                "scrape_method": "japan_scraper"
            }
        }
    
    def _initialize_vector_store(self):
        """
        Initialize the vector store if it exists, otherwise it will be created when documents are added.
        """
        if os.path.exists(self.db_dir):
            try:
                self.vector_store = Chroma(
                    persist_directory=str(self.db_dir),
                    embedding_function=self.embeddings
                )
                logger.info(f"Vector store loaded with {self.vector_store._collection.count()} documents")
            except Exception as e:
                logger.error(f"Error loading vector store: {e}")
                logger.info("Will create a new vector store when documents are added")
                self.vector_store = None
        else:
            self.vector_store = None
    
    async def update_regulatory_documents(self, force_update: bool = False):
        """
        Update the regulatory documents by scraping the regulatory sources.
        
        Args:
            force_update: Whether to force update even if documents exist
        """
        logger.info("Updating regulatory documents...")
        
        documents_updated = False
        
        for source_id, source_info in self.regulatory_sources.items():
            logger.info(f"Processing source: {source_info['name']}")
            
            # Get the scraper method
            scraper_method_name = source_info.get("scrape_method")
            if not scraper_method_name or not hasattr(self, scraper_method_name):
                logger.warning(f"No scraper method found for {source_id}")
                continue
            
            scraper_method = getattr(self, scraper_method_name)
            
            # Scrape documents
            try:
                documents = scraper_method(source_info, force_update)
                if documents:
                    documents_updated = True
            except Exception as e:
                logger.error(f"Error scraping {source_id}: {e}")
        
        # If documents were updated, update the vector store
        if documents_updated:
            self._update_vector_store()
    
    def _update_vector_store(self):
        """
        Update the vector store with the latest documents.
        """
        logger.info("Updating vector store...")
        
        # Get all document files
        document_files = list(self.docs_dir.glob("**/*.txt"))
        if not document_files:
            logger.warning("No document files found")
            return
        
        # Process all documents
        all_chunks = []
        all_metadatas = []
        
        for doc_file in document_files:
            try:
                with open(doc_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Extract metadata from filename
                # Filename format: source_id_document_id.txt
                filename = doc_file.stem
                parts = filename.split("_", 1)
                
                if len(parts) >= 2:
                    source_id, document_id = parts
                else:
                    source_id = parts[0]
                    document_id = "unknown"
                
                # Split the document into chunks
                chunks = self.text_splitter.split_text(content)
                
                # Create metadata for each chunk
                metadatas = [
                    {
                        "source": source_id,
                        "document_id": document_id,
                        "chunk_id": i,
                        "file_path": str(doc_file)
                    }
                    for i in range(len(chunks))
                ]
                
                all_chunks.extend(chunks)
                all_metadatas.extend(metadatas)
                
                logger.info(f"Processed document: {doc_file.name} - {len(chunks)} chunks")
            
            except Exception as e:
                logger.error(f"Error processing document {doc_file}: {e}")
        
        # Create or update the vector store
        if all_chunks:
            if self.vector_store is None:
                logger.info(f"Creating new vector store with {len(all_chunks)} chunks")
                self.vector_store = Chroma.from_texts(
                    texts=all_chunks,
                    embedding=self.embeddings,
                    metadatas=all_metadatas,
                    persist_directory=str(self.db_dir)
                )
                self.vector_store.persist()
            else:
                logger.info(f"Adding {len(all_chunks)} chunks to existing vector store")
                self.vector_store.add_texts(
                    texts=all_chunks,
                    metadatas=all_metadatas
                )
                self.vector_store.persist()
                
            logger.info(f"Vector store updated with {self.vector_store._collection.count()} total chunks")
        else:
            logger.warning("No chunks to add to vector store")
    
    # Scraper methods for different regulatory sources
    
    def unece_scraper(self, source_info: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Scrape UNECE regulations.
        
        Args:
            source_info: Information about the regulatory source
            force_update: Whether to force update even if documents exist
            
        Returns:
            Whether new documents were added
        """
        logger.info("Scraping UNECE regulations...")
        
        base_url = source_info["base_url"]
        
        # Create source directory if it doesn't exist
        source_dir = self.docs_dir / "UNECE"
        source_dir.mkdir(exist_ok=True)
        
        # Check if we need to update
        if not force_update and list(source_dir.glob("*.txt")):
            logger.info("UNECE documents already exist, skipping update")
            return False
        
        # Get the regulations page
        try:
            response = requests.get(base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find regulation links
            regulation_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(re.match(pattern, href) for pattern in source_info["document_patterns"]):
                    regulation_links.append(href)
            
            if not regulation_links:
                logger.warning("No UNECE regulation links found")
                return False
            
            # Download and process regulations
            documents_added = False
            
            for link in regulation_links[:5]:  # Limit to 5 for testing
                try:
                    # Extract regulation ID from link
                    reg_id = re.search(r"(?:ECE-TRANS-WP29|wp29)-(\d+-\w+)", link)
                    if reg_id:
                        reg_id = reg_id.group(1)
                    else:
                        reg_id = link.split("/")[-1].replace(".pdf", "")
                    
                    # Check if the regulation already exists
                    reg_file = source_dir / f"UNECE_{reg_id}.txt"
                    if not force_update and reg_file.exists():
                        logger.info(f"Regulation {reg_id} already exists, skipping")
                        continue
                    
                    # Download the PDF
                    pdf_response = requests.get(link)
                    pdf_response.raise_for_status()
                    
                    # Extract text from PDF
                    pdf_content = BytesIO(pdf_response.content)
                    text = self._extract_text_from_pdf(pdf_content)
                    
                    # Save the text
                    with open(reg_file, "w", encoding="utf-8") as f:
                        f.write(text)
                    
                    logger.info(f"Added regulation: {reg_id}")
                    documents_added = True
                
                except Exception as e:
                    logger.error(f"Error processing regulation {link}: {e}")
            
            return documents_added
        
        except Exception as e:
            logger.error(f"Error scraping UNECE regulations: {e}")
            return False
    
    def nhtsa_scraper(self, source_info: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Scrape NHTSA FMVSS regulations.
        
        Args:
            source_info: Information about the regulatory source
            force_update: Whether to force update even if documents exist
            
        Returns:
            Whether new documents were added
        """
        logger.info("Scraping NHTSA regulations...")
        
        base_url = source_info["base_url"]
        
        # Create source directory if it doesn't exist
        source_dir = self.docs_dir / "NHTSA"
        source_dir.mkdir(exist_ok=True)
        
        # Check if we need to update
        if not force_update and list(source_dir.glob("*.txt")):
            logger.info("NHTSA documents already exist, skipping update")
            return False
        
        # Get the regulations page
        try:
            response = requests.get(base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find regulation links
            regulation_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.endswith(".pdf") and "fmvss" in href.lower():
                    # Make sure it's an absolute URL
                    if not href.startswith("http"):
                        if href.startswith("/"):
                            href = f"https://www.nhtsa.gov{href}"
                        else:
                            href = f"https://www.nhtsa.gov/{href}"
                    regulation_links.append(href)
            
            if not regulation_links:
                # Try another approach - look for links to regulation pages
                for a in soup.find_all("a", href=True):
                    if "standard" in a.text.lower() and "no." in a.text.lower():
                        href = a["href"]
                        if not href.startswith("http"):
                            if href.startswith("/"):
                                href = f"https://www.nhtsa.gov{href}"
                            else:
                                href = f"https://www.nhtsa.gov/{href}"
                        
                        # Get the regulation page
                        try:
                            reg_response = requests.get(href)
                            reg_response.raise_for_status()
                            
                            reg_soup = BeautifulSoup(reg_response.text, "html.parser")
                            
                            # Find PDF links
                            for reg_a in reg_soup.find_all("a", href=True):
                                reg_href = reg_a["href"]
                                if reg_href.endswith(".pdf"):
                                    if not reg_href.startswith("http"):
                                        if reg_href.startswith("/"):
                                            reg_href = f"https://www.nhtsa.gov{reg_href}"
                                        else:
                                            reg_href = f"https://www.nhtsa.gov/{reg_href}"
                                    regulation_links.append(reg_href)
                        
                        except Exception as e:
                            logger.error(f"Error fetching regulation page {href}: {e}")
            
            if not regulation_links:
                logger.warning("No NHTSA regulation links found")
                return False
            
            # Download and process regulations
            documents_added = False
            
            for link in regulation_links[:5]:  # Limit to 5 for testing
                try:
                    # Extract regulation ID from link
                    reg_id = link.split("/")[-1].replace(".pdf", "")
                    
                    # Check if the regulation already exists
                    reg_file = source_dir / f"NHTSA_{reg_id}.txt"
                    if not force_update and reg_file.exists():
                        logger.info(f"Regulation {reg_id} already exists, skipping")
                        continue
                    
                    # Download the PDF
                    pdf_response = requests.get(link)
                    pdf_response.raise_for_status()
                    
                    # Extract text from PDF
                    pdf_content = BytesIO(pdf_response.content)
                    text = self._extract_text_from_pdf(pdf_content)
                    
                    # Save the text
                    with open(reg_file, "w", encoding="utf-8") as f:
                        f.write(text)
                    
                    logger.info(f"Added regulation: {reg_id}")
                    documents_added = True
                
                except Exception as e:
                    logger.error(f"Error processing regulation {link}: {e}")
            
            return documents_added
        
        except Exception as e:
            logger.error(f"Error scraping NHTSA regulations: {e}")
            return False
    
    def eu_scraper(self, source_info: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Scrape EU regulations.
        
        Args:
            source_info: Information about the regulatory source
            force_update: Whether to force update even if documents exist
            
        Returns:
            Whether new documents were added
        """
        # Implementation similar to the UNECE and NHTSA scrapers
        # For brevity, only showing placeholder
        logger.info("Scraping EU regulations...")
        return False  # Implement similar to UNECE
    
    def cmvss_scraper(self, source_info: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Scrape CMVSS regulations.
        
        Args:
            source_info: Information about the regulatory source
            force_update: Whether to force update even if documents exist
            
        Returns:
            Whether new documents were added
        """
        # Implementation similar to the UNECE and NHTSA scrapers
        logger.info("Scraping CMVSS regulations...")
        return False  # Implement similar to UNECE
    
    def china_scraper(self, source_info: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Scrape China GB Standards regulations.
        
        Args:
            source_info: Information about the regulatory source
            force_update: Whether to force update even if documents exist
            
        Returns:
            Whether new documents were added
        """
        # Implementation similar to the UNECE and NHTSA scrapers
        logger.info("Scraping China GB Standards...")
        return False  # Implement similar to UNECE
    
    def japan_scraper(self, source_info: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Scrape Japan Automotive Standards regulations.
        
        Args:
            source_info: Information about the regulatory source
            force_update: Whether to force update even if documents exist
            
        Returns:
            Whether new documents were added
        """
        # Implementation similar to the UNECE and NHTSA scrapers
        logger.info("Scraping Japan Automotive Standards...")
        return False  # Implement similar to UNECE
    
    def _extract_text_from_pdf(self, pdf_content: BytesIO) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_content: PDF content as BytesIO
            
        Returns:
            Extracted text
        """
        text = ""
        
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_content)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n\n"
            
            # Clean up the text
            text = text.replace("\n\n", "\n").strip()
            
            return text
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return text
    
    async def query(self, question: str, k: int = 5) -> Dict[str, Any]:
        """
        Query the advisor with a question about automotive regulations.
        
        Args:
            question: The question to ask
            k: Number of relevant documents to retrieve
            
        Returns:
            A dictionary containing the answer, sources, and confidence score
        """
        logger.info(f"Processing query: {question}")
        
        # Check if vector store exists
        if self.vector_store is None:
            logger.error("Vector store not initialized")
            return {
                "answer": "I'm sorry, but I don't have any regulatory documents loaded. Please update the regulatory documents first.",
                "sources": [],
                "confidence": 0.0,
                "clean_response": "Error: No regulatory documents available."
            }
        
        # Retrieve relevant documents
        retrieved_docs = self.vector_store.similarity_search_with_score(
            question,
            k=k
        )
        
        if not retrieved_docs:
            logger.warning("No relevant documents found")
            return {
                "answer": "I'm sorry, but I couldn't find any relevant regulatory information for your question.",
                "sources": [],
                "confidence": 0.0,
                "clean_response": "No relevant regulatory information found."
            }
        
        # Prepare the documents and their scores
        docs = []
        for doc, score in retrieved_docs:
            source_id = doc.metadata.get("source", "unknown")
            document_id = doc.metadata.get("document_id", "unknown")
            
            source_info = self.regulatory_sources.get(source_id, {"name": source_id})
            source_name = source_info.get("name", source_id)
            
            docs.append({
                "content": doc.page_content,
                "source_id": source_id,
                "document_id": document_id,
                "source_name": source_name,
                "relevance_score": float(score)
            })
        
        # Generate a prompt for the LLM
        prompt = self._generate_prompt(question, docs)
        
        # Query the LLM
        try:
            # Use the initialized Groq LLM directly
            answer = self.llm(prompt)
            
            # Clean the response
            clean_response = self._clean_response(answer)
            
            # Calculate confidence based on document scores
            avg_score = sum(doc["relevance_score"] for doc in docs) / len(docs)
            confidence = 1.0 - avg_score  # Convert distance to confidence
            
            # Prepare the sources for the response
            sources = []
            for doc in docs:
                sources.append({
                    "source_id": doc["source_id"],
                    "document_id": doc["document_id"],
                    "source_name": doc["source_name"],
                    "relevance_score": doc["relevance_score"]
                })
            
            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "clean_response": clean_response
            }
        
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            return {
                "answer": f"I'm sorry, but I encountered an error while processing your question: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "clean_response": f"Error: {str(e)}"
            }
    
    def _generate_prompt(self, question: str, docs: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for the LLM based on the question and retrieved documents.
        
        Args:
            question: The question to ask
            docs: List of retrieved documents
            
        Returns:
            The generated prompt
        """
        prompt = f"Question: {question}\n\n"
        prompt += "Here are the relevant regulatory documents:\n\n"
        
        for i, doc in enumerate(docs):
            prompt += f"Document {i+1} - {doc['source_name']} ({doc['document_id']}):\n"
            prompt += f"{doc['content']}\n\n"
        
        prompt += "Based only on the information in these documents, please answer the question. "
        prompt += "Include specific regulatory references and section numbers. "
        prompt += "If the documents don't provide a clear answer, say so and explain what information is missing. "
        prompt += "Do not make up information or cite regulations that are not in the provided documents.\n\n"
        prompt += "Please provide your response in the following format:\n"
        prompt += "Answer: [Your detailed answer here]\n"
        prompt += "Citations: [List of specific regulatory references you used]\n"
        prompt += "Limitations: [Any limitations in your answer due to incomplete information]\n"
        
        return prompt
    
    def _clean_response(self, response: str) -> str:
        """
        Clean the LLM response to make it more presentable.
        
        Args:
            response: The raw LLM response
            
        Returns:
            The cleaned response
        """
        # Split into sections
        sections = {}
        
        # Extract sections using regex
        answer_match = re.search(r"Answer:(.*?)(?:Citations:|Limitations:|$)", response, re.DOTALL)
        if answer_match:
            sections["answer"] = answer_match.group(1).strip()
        
        citations_match = re.search(r"Citations:(.*?)(?:Limitations:|$)", response, re.DOTALL)
        if citations_match:
            sections["citations"] = citations_match.group(1).strip()
        
        limitations_match = re.search(r"Limitations:(.*?)$", response, re.DOTALL)
        if limitations_match:
            sections["limitations"] = limitations_match.group(1).strip()
        
        # If regex failed, try simple splits
        if not sections:
            parts = response.split("\n\n")
            if len(parts) >= 1:
                sections["answer"] = parts[0]
            if len(parts) >= 2:
                sections["citations"] = parts[1]
            if len(parts) >= 3:
                sections["limitations"] = parts[2]
        
        # Format the clean response
        clean_response = ""
        
        if "answer" in sections:
            clean_response += sections["answer"] + "\n\n"
        
        if "citations" in sections:
            clean_response += "**References:**\n" + sections["citations"] + "\n\n"
        
        if "limitations" in sections and sections["limitations"]:
            clean_response += "**Note:**\n" + sections["limitations"]
        
        return clean_response.strip()

class ApiServer:
    """
    API server for the AutoRegulationAdvisor.
    """
    
    def __init__(self, advisor: AutoRegulationAdvisor):
        """
        Initialize the API server.
        
        Args:
            advisor: The AutoRegulationAdvisor instance
        """
        self.advisor = advisor
    
    async def update_documents_endpoint(self, force_update: bool = False):
        """
        API endpoint to update regulatory documents.
        
        Args:
            force_update: Whether to force update even if documents exist
            
        Returns:
            API response
        """
        try:
            await self.advisor.update_regulatory_documents(force_update)
            return {"status": "success", "message": "Regulatory documents updated successfully"}
        except Exception as e:
            logger.error(f"Error updating documents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def query_endpoint(self, question: str, k: int = 5):
        """
        API endpoint to query the advisor.
        
        Args:
            question: The question to ask
            k: Number of relevant documents to retrieve
            
        Returns:
            API response
        """
        try:
            result = await self.advisor.query(question, k)
            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            logger.error(f"Error querying advisor: {e}")
            return {"status": "error", "message": str(e)}

# Example usage
async def main():
    # Set up the advisor
    advisor = AutoRegulationAdvisor(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        data_dir="regulatory_data"
    )
    
    # Update regulatory documents
    await advisor.update_regulatory_documents()
    
    # Query the advisor
    result = await advisor.query("What are the requirements for headlights in UNECE regulations?")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

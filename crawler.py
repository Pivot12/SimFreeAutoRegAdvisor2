import os
import time
import random
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import PyPDF2
from io import BytesIO
import chardet
from tika import parser
from playwright.sync_api import sync_playwright
from logger import Logger

class AutoRegulationCrawler:
    """
    Specialized crawler for automotive regulation websites that can navigate
    complex document structures and extract information.
    """
    
    def __init__(self):
        self.logger = Logger()
        
        # User agent rotation to avoid being blocked
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
        ]
        
        # Rate limiting settings
        self.min_delay = 2.0  # Minimum seconds between requests to same domain
        self.last_requests = {}  # Last request time per domain
        
        # Document parsing settings
        self.chunk_size = 1000  # Characters per chunk
        self.chunk_overlap = 200  # Character overlap between chunks
        
        # Access tracking to respect robots.txt
        self.robots_cache = {}  # Cache of robots.txt rules
        
        # Initialize document parsers
        try:
            from tika import initVM
            initVM()
        except:
            self.logger.log_error("Tika initialization failed, will fall back to other parsers")
            
    def _get_random_user_agent(self) -> str:
        """Get a random user agent to avoid detection."""
        return random.choice(self.user_agents)
    
    def _respect_rate_limits(self, domain: str):
        """Enforce rate limiting for each domain."""
        current_time = time.time()
        if domain in self.last_requests:
            elapsed = current_time - self.last_requests[domain]
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
        
        self.last_requests[domain] = time.time()
    
    def _check_robots_txt(self, url: str) -> bool:
        """Check if crawling is allowed by robots.txt."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if domain in self.robots_cache:
            rules = self.robots_cache[domain]
        else:
            # Fetch robots.txt
            robots_url = f"{parsed_url.scheme}://{domain}/robots.txt"
            try:
                response = requests.get(
                    robots_url, 
                    headers={"User-Agent": self._get_random_user_agent()},
                    timeout=10
                )
                
                if response.status_code == 200:
                    # Very basic robots.txt parsing
                    content = response.text
                    # Check for specific disallow rules
                    disallowed_paths = re.findall(r'Disallow: (.*)', content)
                    self.robots_cache[domain] = disallowed_paths
                    rules = disallowed_paths
                else:
                    # No robots.txt or couldn't access
                    self.robots_cache[domain] = []
                    rules = []
            except Exception as e:
                self.logger.log_error(f"Error fetching robots.txt for {domain}: {str(e)}")
                self.robots_cache[domain] = []
                rules = []
        
        # Check if URL path is allowed
        path = parsed_url.path
        for rule in rules:
            if rule.strip() == "/" or path.startswith(rule.strip()):
                return False
        
        return True
    
    def fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch the content of a URL with proper headers and rate limiting.
        Returns the HTML content or None if unsuccessful.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check robots.txt
        if not self._check_robots_txt(url):
            self.logger.log_event("robots_disallowed", {"url": url})
            return None
        
        # Respect rate limits
        self._respect_rate_limits(domain)
        
        # Set up headers
        headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # Detect encoding if not specified
                if not response.encoding or response.encoding == 'ISO-8859-1':
                    detected = chardet.detect(response.content)
                    response.encoding = detected['encoding']
                
                return response.text
            else:
                self.logger.log_error(f"HTTP error {response.status_code} for URL: {url}")
                return None
                
        except Exception as e:
            self.logger.log_error(f"Error fetching URL {url}: {str(e)}")
            return None
    
    def fetch_with_browser(self, url: str) -> Optional[str]:
        """
        Fetch URL using headless browser for JavaScript-heavy sites.
        Returns the HTML content or None if unsuccessful.
        """
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self._get_random_user_agent(),
                    viewport={"width": 1920, "height": 1080}
                )
                
                page = context.new_page()
                
                # Add additional headers
                page.set_extra_http_headers({
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Fetch-Dest": "document"
                })
                
                # Check robots.txt
                parsed_url = urlparse(url)
                domain = parsed_url.netloc
                if not self._check_robots_txt(url):
                    self.logger.log_event("robots_disallowed", {"url": url})
                    browser.close()
                    return None
                
                # Respect rate limits
                self._respect_rate_limits(domain)
                
                # Navigate to the page
                response = page.goto(url, wait_until="networkidle", timeout=30000)
                
                if response is None or not response.ok:
                    self.logger.log_error(f"Failed to load URL with browser: {url}")
                    browser.close()
                    return None
                
                # Wait for content to load
                page.wait_for_load_state("networkidle")
                
                # Get the content
                content = page.content()
                browser.close()
                
                return content
                
        except Exception as e:
            self.logger.log_error(f"Browser fetch error for {url}: {str(e)}")
            return None
    
    def fetch_pdf(self, url: str) -> Optional[str]:
        """
        Fetch and extract text from a PDF document.
        Returns the text content or None if unsuccessful.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check robots.txt
        if not self._check_robots_txt(url):
            self.logger.log_event("robots_disallowed", {"url": url})
            return None
        
        # Respect rate limits
        self._respect_rate_limits(domain)
        
        try:
            # Set up headers
            headers = {
                "User-Agent": self._get_random_user_agent(),
                "Accept": "application/pdf",
                "Connection": "keep-alive"
            }
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            
            if response.status_code != 200:
                self.logger.log_error(f"HTTP error {response.status_code} for PDF URL: {url}")
                return None
            
            # Try Apache Tika first (better for scanned PDFs with OCR)
            try:
                parsed_pdf = parser.from_buffer(response.content)
                if parsed_pdf["content"] and len(parsed_pdf["content"].strip()) > 100:
                    return parsed_pdf["content"]
            except Exception as tika_error:
                self.logger.log_error(f"Tika PDF parsing error: {str(tika_error)}")
            
            # Fall back to PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(BytesIO(response.content))
                text = ""
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n\n"
                
                if text.strip():
                    return text
                else:
                    self.logger.log_error(f"Empty text extracted from PDF: {url}")
                    return None
            except Exception as pypdf_error:
                self.logger.log_error(f"PyPDF2 parsing error: {str(pypdf_error)}")
                return None
                
        except Exception as e:
            self.logger.log_error(f"Error fetching PDF {url}: {str(e)}")
            return None
    
    def find_document_links(self, html_content: str, base_url: str, patterns: List[str]) -> List[Dict]:
        """
        Extract links to regulation documents from HTML content.
        Returns list of dictionaries with title and URL.
        """
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            
            # Check if URL matches any of the patterns
            if any(pattern in absolute_url for pattern in patterns):
                title = link.get_text().strip()
                if not title:
                    # Try to get title from parent element
                    parent = link.parent
                    if parent:
                        title = parent.get_text().strip()
                
                # If still no title, use the URL
                if not title:
                    title = os.path.basename(absolute_url)
                
                # Check for PDF or document links
                is_document = False
                if absolute_url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
                    is_document = True
                
                links.append({
                    "title": title,
                    "url": absolute_url,
                    "is_document": is_document
                })
        
        return links
    
    def _extract_document_title(self, html_content: str) -> str:
        """Extract the title of a document from its HTML content."""
        if not html_content:
            return "Unknown Document"
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # First try the title tag
        title_tag = soup.find('title')
        if title_tag and title_tag.string and len(title_tag.string.strip()) > 0:
            return title_tag.string.strip()
        
        # Try h1 tags
        h1_tag = soup.find('h1')
        if h1_tag and h1_tag.get_text().strip():
            return h1_tag.get_text().strip()
        
        # Try looking for typical document title patterns
        for tag in soup.find_all(['h2', 'h3', 'strong', 'b']):
            text = tag.get_text().strip()
            if re.search(r'(regulation|directive|standard|act|law|code|rule)\s+no\.?\s+\d+', text, re.I):
                return text
        
        return "Unknown Document"
    
    def retrieve_documents(self, base_url: str, doc_patterns: List[str], query_analysis: Dict) -> List[Dict]:
        """
        Retrieve relevant documents from a regulatory source.
        Returns list of dictionaries with title, URL and content.
        """
        documents = []
        
        # Step 1: Fetch the base URL to find document links
        html_content = self.fetch_url(base_url)
        if not html_content:
            # Try with headless browser if regular fetch fails
            html_content = self.fetch_with_browser(base_url)
        
        if not html_content:
            self.logger.log_error(f"Failed to fetch base URL: {base_url}")
            return documents
        
        # Step 2: Find links to regulation documents
        doc_links = self.find_document_links(html_content, base_url, doc_patterns)
        
        # Step 3: Filter links based on query analysis
        filtered_links = self._filter_links_by_relevance(doc_links, query_analysis)
        
        # Step 4: Retrieve document content
        for link in filtered_links[:5]:  # Limit to top 5 most relevant docs
            content = None
            
            if link["is_document"] and link["url"].lower().endswith('.pdf'):
                content = self.fetch_pdf(link["url"])
            else:
                content = self.fetch_url(link["url"])
                if not content:
                    content = self.fetch_with_browser(link["url"])
            
            if content:
                # Get or extract title
                title = link["title"]
                if title == os.path.basename(link["url"]) and not link["is_document"]:
                    title = self._extract_document_title(content)
                
                documents.append({
                    "title": title,
                    "url": link["url"],
                    "content": content,
                    "source": base_url
                })
        
        return documents
    
    def _filter_links_by_relevance(self, links: List[Dict], query_analysis: Dict) -> List[Dict]:
        """Filter document links by relevance to the query."""
        # Calculate relevance score for each link
        scored_links = []
        
        for link in links:
            score = 0
            title_lower = link["title"].lower()
            url_lower = link["url"].lower()
            
            # Check for region/country relevance
            for region in query_analysis["regions"]:
                if region.lower() in title_lower or region.lower() in url_lower:
                    score += 3
            
            # Check for regulation type relevance
            for reg_type in query_analysis["regulation_types"]:
                if reg_type.lower() in title_lower or reg_type.lower() in url_lower:
                    score += 2
            
            # Check for vehicle category relevance
            for category in query_analysis["vehicle_categories"]:
                if category.lower() in title_lower or category.lower() in url_lower:
                    score += 2
            
            # Check for technical parameters
            for param in query_analysis["technical_parameters"]:
                if param.lower() in title_lower or param.lower() in url_lower:
                    score += 1
            
            # Bonus for document links (PDF, DOC, etc.)
            if link["is_document"]:
                score += 1
            
            scored_links.append((link, score))
        
        # Sort by relevance score (descending)
        scored_links.sort(key=lambda x: x[1], reverse=True)
        
        # Return the links only, without scores
        return [link for link, score in scored_links]
    
    def chunk_document(self, content: str) -> List[Dict]:
        """
        Split document content into manageable chunks for processing.
        Returns list of dictionaries with text chunks and metadata.
        """
        if not content:
            return []
        
        chunks = []
        
        # Normalize line breaks
        content = re.sub(r'\r\n', '\n', content)
        
        # Clean up excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        # Split content into chunks
        paragraphs = re.split(r'\n{2,}', content)
        current_chunk = ""
        
        for paragraph in paragraphs:
            # Skip empty paragraphs
            if not paragraph.strip():
                continue
                
            # If adding this paragraph exceeds chunk size, save current chunk and start new one
            if len(current_chunk) + len(paragraph) > self.chunk_size:
                if current_chunk:
                    chunks.append({"text": current_chunk.strip(), "source": "document"})
                
                # Start new chunk with overlap from previous chunk if possible
                if len(current_chunk) > self.chunk_overlap:
                    # Find a paragraph or sentence break for the overlap
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    # Try to find a sentence break
                    sentence_break = re.search(r'[.!?]\s+[A-Z]', overlap_text)
                    if sentence_break:
                        overlap_index = sentence_break.start() + 2  # Include the punctuation
                        current_chunk = overlap_text[overlap_index:]
                    else:
                        # If no sentence break, find a space
                        space_index = overlap_text.find(' ')
                        if space_index > 0:
                            current_chunk = overlap_text[space_index+1:]
                        else:
                            current_chunk = ""
                else:
                    current_chunk = ""
            
            # Add paragraph to current chunk
            if current_chunk and not current_chunk.endswith(" "):
                current_chunk += " "
            current_chunk += paragraph
        
        # Add the last chunk if not empty
        if current_chunk.strip():
            chunks.append({"text": current_chunk.strip(), "source": "document"})
        
        return chunks
    
    def search_in_regulations(self, query: str, documents: List[Dict]) -> List[Dict]:
        """
        Search for query terms in regulatory documents.
        Returns list of relevant text chunks with metadata.
        """
        if not documents:
            return []
        
        # Extract search terms from query
        search_terms = re.findall(r'\b\w{3,}\b', query.lower())
        search_terms = [term for term in search_terms if term not in ['and', 'the', 'for', 'with', 'this', 'that', 'what', 'how', 'when', 'where', 'why', 'who']]
        
        # Create chunks from all documents
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc["content"])
            for chunk in chunks:
                chunk["document_title"] = doc["title"]
                chunk["document_url"] = doc["url"]
                all_chunks.append(chunk)
        
        # Score chunks by relevance to search terms
        scored_chunks = []
        for chunk in all_chunks:
            score = 0
            text_lower = chunk["text"].lower()
            
            for term in search_terms:
                # Count occurrences of the term
                count = text_lower.count(term)
                score += count
                
                # Bonus for terms in the same sentence
                sentences = re.split(r'[.!?]+', text_lower)
                for sentence in sentences:
                    term_count_in_sentence = sum(1 for term in search_terms if term in sentence)
                    if term_count_in_sentence > 1:
                        score += term_count_in_sentence
            
            if score > 0:
                scored_chunks.append((chunk, score))
        
        # Sort by relevance score (descending)
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Return top chunks (maximum 10)
        return [chunk for chunk, score in scored_chunks[:10]]

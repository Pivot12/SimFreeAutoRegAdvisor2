import requests
import time
import os
import re
import json
import logging
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RegulatoryWebCrawler")

class RegulatoryWebCrawler:
    """
    Enhanced web crawler for regulatory websites with robust authentication,
    adaptive navigation, and learning capabilities.
    """
    
    def __init__(self, db_manager=None):
        """Initialize the crawler with advanced capabilities"""
        # User agent rotation for avoiding detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
        
        # Store knowledge of successful paths
        self.successful_paths = {}
        self.db_manager = db_manager
        
        # Load successful paths from database if available
        if self.db_manager:
            self.load_successful_paths()
        
        # Initialize session with random user agent
        self.session = self._create_new_session()
        
        # Initialize headless browser for complex sites
        self.browser = None
        
        # Site-specific authentication status
        self.auth_status = {
            'interregs': False
        }
        
        # URLs verification cache
        self.url_verification_cache = {}
        
        # Current regulatory site being accessed
        self.current_site = None
        
        # Adaptive paths for each authority
        self.adaptive_paths = self._load_adaptive_paths()
        
    def _create_new_session(self):
        """Create a new session with random user agent and headers"""
        session = requests.Session()
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'DNT': '1'  # Do Not Track request header
        }
        session.headers.update(headers)
        return session
    
    def _load_adaptive_paths(self):
        """Load alternative paths for navigation"""
        # These are fallback paths for each authority
        return {
            'UNECE WP.29': [
                '/transport/vehicle-regulations',
                '/transport/standards/transport/vehicle-regulations-wp29',
                '/transport/standards/transport',
                '/areas-of-work/transport/vehicle-regulations'
            ],
            'NHTSA': [
                '/laws-regulations',
                '/laws-regulations/fmvss',
                '/vehicle-manufacturers/regulations-standards',
                '/vehicle-safety'
            ],
            # Add fallback paths for other authorities
            'EU European Commission': [
                '/index_en',
                '/transport',
                '/mobility',
                '/road-safety'
            ],
            # Add more fallbacks for other sites
            'interregs': [
                '/db/index.php?id=ATO-01',
                '/login',
                '/search',
                '/regulations'
            ]
        }
        
    def load_successful_paths(self):
        """Load successful navigation paths from database"""
        if self.db_manager:
            try:
                paths_data = self.db_manager.get_successful_paths()
                if paths_data:
                    self.successful_paths = paths_data
                    logger.info(f"Loaded {len(self.successful_paths)} successful paths from database")
            except Exception as e:
                logger.error(f"Error loading successful paths: {e}")
    
    def save_successful_path(self, authority, search_term, path, success=True):
        """Save a successful navigation path to the database"""
        if self.db_manager:
            try:
                self.db_manager.save_path(authority, search_term, path, success)
                # Update local cache
                if authority not in self.successful_paths:
                    self.successful_paths[authority] = {}
                if search_term not in self.successful_paths[authority]:
                    self.successful_paths[authority][search_term] = []
                self.successful_paths[authority][search_term].append((path, success))
                
                logger.info(f"Saved path for {authority}: {path} (success: {success})")
            except Exception as e:
                logger.error(f"Error saving successful path: {e}")
    
    def _get_browser(self):
        """Initialize headless browser with cloud-compatible settings"""
        if self.browser is None:
            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                
                # For Streamlit Cloud compatibility
                chrome_options.binary_location = "/usr/bin/chromium-browser"
                
                self.browser = webdriver.Chrome(options=chrome_options)
                logger.info("Headless browser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize headless browser: {e}")
                return None
        return self.browser
    
    def verify_url(self, url):
        """Verify if a URL exists and is accessible"""
        if url in self.url_verification_cache:
            return self.url_verification_cache[url]
        
        try:
            # Use a HEAD request to check URL validity without downloading content
            response = self.session.head(url, timeout=10, allow_redirects=True)
            result = 200 <= response.status_code < 300
            self.url_verification_cache[url] = result
            return result
        except Exception as e:
            logger.warning(f"URL verification failed for {url}: {e}")
            self.url_verification_cache[url] = False
            return False
    
    def login_to_interregs(self):
        """Enhanced login to Interregs.net with multiple approaches"""
        if self.auth_status.get('interregs', False):
            logger.info("Already logged in to Interregs")
            return True
        
        logger.info("Attempting to login to Interregs.net")
        
        # First attempt: Standard session-based login
        try:
            login_url = "https://www.interregs.net/login"
            # Get the login page to capture CSRF token if any
            login_response = self.session.get(login_url, timeout=20)
            
            if login_response.status_code == 200:
                # Parse form and extract any hidden fields like CSRF tokens
                soup = BeautifulSoup(login_response.text, 'html.parser')
                login_form = soup.find('form')
                
                if login_form:
                    # Extract all hidden fields
                    hidden_fields = {}
                    for field in login_form.find_all('input', {'type': 'hidden'}):
                        name = field.get('name')
                        value = field.get('value', '')
                        if name:
                            hidden_fields[name] = value
                    
                    # Prepare login data with credentials and hidden fields
                    login_data = {
                        'email': st.secrets.get("INTERREGS_EMAIL", "neelshah@lucidmotors.com"),
                        'password': st.secrets.get("INTERREGS_PASSWORD", "eyzzp3iw"),
                        'remember': '1'
                    }
                    login_data.update(hidden_fields)
                    
                    # Submit login form
                    post_response = self.session.post(
                        login_url,
                        data=login_data,
                        allow_redirects=True,
                        timeout=20
                    )
                    
                    # Check if login was successful
                    if post_response.status_code == 200:
                        # Verify login success by looking for specific elements
                        content = post_response.text.lower()
                        success_indicators = ['logout', 'account', 'profile', 'welcome', 'dashboard']
                        
                        if any(indicator in content for indicator in success_indicators):
                            logger.info("Successfully logged in to Interregs via session")
                            self.auth_status['interregs'] = True
                            return True
                        else:
                            logger.warning("Login request succeeded but couldn't verify login status")
        except Exception as e:
            logger.error(f"Session-based login to Interregs failed: {e}")
        
        # Second attempt: Selenium-based login for complex authentication
        try:
            browser = self._get_browser()
            if browser:
                browser.get("https://www.interregs.net/login")
                
                # Wait for the login form to load
                WebDriverWait(browser, 10).until(
                    EC.presence_of_element_located((By.NAME, "email"))
                )
                
                # Fill in login details
                email_field = browser.find_element(By.NAME, "email")
                password_field = browser.find_element(By.NAME, "password")
                
                email_field.send_keys(st.secrets.get("INTERREGS_EMAIL", "neelshah@lucidmotors.com"))
                password_field.send_keys(st.secrets.get("INTERREGS_PASSWORD", "eyzzp3iw"))
                
                # Find and click login button
                login_button = browser.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                
                # Wait for login to complete
                try:
                    WebDriverWait(browser, 15).until(
                        lambda driver: any(
                            indicator in driver.page_source.lower() 
                            for indicator in ['logout', 'account', 'profile']
                        )
                    )
                    
                    # Extract cookies from browser and add to session
                    for cookie in browser.get_cookies():
                        self.session.cookies.set(cookie['name'], cookie['value'])
                    
                    logger.info("Successfully logged in to Interregs via browser")
                    self.auth_status['interregs'] = True
                    return True
                except TimeoutException:
                    logger.warning("Timed out waiting for login confirmation")
        except Exception as e:
            logger.error(f"Browser-based login to Interregs failed: {e}")
        
        logger.error("All login attempts to Interregs failed")
        return False
    
    def get_with_retry(self, url, max_retries=5, delay=2, timeout=30, verify_ssl=True):
        """
        Enhanced get request with retry logic, JavaScript handling, and adaptability
        """
        full_url = url
        if not (url.startswith('http://') or url.startswith('https://')):
            parsed_url = urlparse(self.session.get_adapter('https://').get_connection('').url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            full_url = urljoin(base_url, url)
        
        logger.info(f"Fetching URL: {full_url}")
        
        # Try session-based request first with exponential backoff
        for attempt in range(max_retries):
            try:
                # Rotate user agent on each retry
                if attempt > 0:
                    self.session.headers.update({
                        'User-Agent': random.choice(self.user_agents)
                    })
                
                # Delay with jitter to avoid detection
                if attempt > 0:
                    jitter = random.uniform(0.5, 1.5)
                    time.sleep(delay * (2 ** (attempt - 1)) * jitter)
                
                response = self.session.get(
                    full_url, 
                    timeout=timeout,
                    verify=verify_ssl,
                    allow_redirects=True
                )
                
                if 200 <= response.status_code < 300:
                    logger.info(f"Successfully fetched URL (attempt {attempt+1}): {full_url}")
                    return response
                elif response.status_code == 403:
                    logger.warning(f"Access forbidden (403) for {full_url}")
                    
                    # If this is Interregs and we're not authenticated, try logging in
                    if 'interregs' in full_url.lower() and not self.auth_status.get('interregs', False):
                        logger.info("Attempting to login to Interregs")
                        if self.login_to_interregs():
                            continue  # Retry after login
                    
                    # If access is still forbidden, try browser-based approach
                    browser = self._get_browser()
                    if browser:
                        try:
                            browser.get(full_url)
                            WebDriverWait(browser, 10).until(
                                lambda driver: driver.page_source != ""
                            )
                            
                            # Extract cookies and copy to session
                            for cookie in browser.get_cookies():
                                self.session.cookies.set(cookie['name'], cookie['value'])
                            
                            # Extract content
                            html_content = browser.page_source
                            
                            # Create a mock response object
                            class MockResponse:
                                def __init__(self, content, status_code):
                                    self.content = content.encode('utf-8')
                                    self.status_code = status_code
                                    self.text = content
                            
                            return MockResponse(html_content, 200)
                        except Exception as e:
                            logger.error(f"Browser fetch failed: {e}")
                elif response.status_code == 404:
                    logger.warning(f"Page not found (404) for {full_url}")
                    
                    # Try alternative URLs if this is a known authority
                    if self.current_site and self.current_site in self.adaptive_paths:
                        for alt_path in self.adaptive_paths.get(self.current_site, []):
                            parsed = urlparse(full_url)
                            base = f"{parsed.scheme}://{parsed.netloc}"
                            alt_url = urljoin(base, alt_path)
                            
                            logger.info(f"Trying alternative URL: {alt_url}")
                            alt_response = self.session.get(
                                alt_url,
                                timeout=timeout,
                                verify=verify_ssl,
                                allow_redirects=True
                            )
                            
                            if 200 <= alt_response.status_code < 300:
                                logger.info(f"Successfully found alternative URL: {alt_url}")
                                # Save this successful path for future use
                                if self.current_site:
                                    self.save_successful_path(
                                        self.current_site, 
                                        "alternative_path", 
                                        alt_path, 
                                        True
                                    )
                                return alt_response
                else:
                    logger.warning(f"Received status code {response.status_code} for {full_url}")
                
            except requests.RequestException as e:
                logger.error(f"Request error (attempt {attempt+1}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt+1}): {e}")
        
        # As a last resort, try using the browser
        if not browser:
            browser = self._get_browser()
        
        if browser:
            try:
                browser.get(full_url)
                time.sleep(5)  # Give JS time to execute
                
                # Extract content from browser
                html_content = browser.page_source
                
                # Create a mock response object
                class MockResponse:
                    def __init__(self, content, status_code):
                        self.content = content.encode('utf-8')
                        self.status_code = status_code
                        self.text = content
                
                logger.info(f"Successfully fetched URL via browser: {full_url}")
                return MockResponse(html_content, 200)
            except Exception as e:
                logger.error(f"Browser fetch failed as last resort: {e}")
        
        logger.error(f"All attempts to fetch URL failed: {full_url}")
        return None
    
    def find_interregs_documents(self, query):
        """Find regulatory documents from Interregs.net with enhanced navigation"""
        documents = []
        self.current_site = "interregs"
        
        # Ensure we're logged in
        if not self.auth_status.get('interregs', False):
            self.login_to_interregs()
        
        # Try to find documents by leveraging learning from previous queries
        if "interregs" in self.successful_paths:
            for term, paths in self.successful_paths["interregs"].items():
                # See if any previous successful query terms overlap with current query
                if any(word in query.lower() for word in term.lower().split()):
                    for path, success in paths:
                        if success:
                            logger.info(f"Using previously successful path: {path}")
                            search_url = f"https://www.interregs.net{path}"
                            if "?" in path:
                                search_url = f"{search_url}&search={'+'.join(query.split())}"
                            else:
                                search_url = f"{search_url}?search={'+'.join(query.split())}"
                            
                            response = self.get_with_retry(search_url)
                            if response and response.status_code == 200:
                                # Extract document links
                                new_docs = self._extract_document_links(response, "Interregs")
                                if new_docs:
                                    documents.extend(new_docs)
        
        # If no documents found through learned paths, try standard approach
        if not documents:
            try:
                # Create multiple search patterns and try them
                search_patterns = [
                    f"/db/index.php?id=ATO-01&search={'+'.join(query.split())}",
                    f"/search?q={'+'.join(query.split())}",
                    f"/db/index.php?id=ATO-01&keyword={'+'.join(query.split())}"
                ]
                
                for pattern in search_patterns:
                    search_url = f"https://www.interregs.net{pattern}"
                    logger.info(f"Searching Interregs with URL: {search_url}")
                    
                    response = self.get_with_retry(search_url)
                    if response and response.status_code == 200:
                        new_docs = self._extract_document_links(response, "Interregs")
                        if new_docs:
                            # Save this successful path
                            self.save_successful_path(
                                "interregs", 
                                query, 
                                pattern, 
                                True
                            )
                            documents.extend(new_docs)
                            break
            except Exception as e:
                logger.error(f"Error searching Interregs: {e}")
        
        # As a last resort, try browser-based search if no documents found
        if not documents:
            browser = self._get_browser()
            if browser:
                try:
                    browser.get(f"https://www.interregs.net/db/index.php?id=ATO-01")
                    
                    # Wait for page to load
                    WebDriverWait(browser, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # Try to find search box
                    try:
                        search_input = browser.find_element(By.XPATH, "//input[@type='search']")
                        if not search_input:
                            search_input = browser.find_element(By.XPATH, "//input[@name='search']")
                        if not search_input:
                            search_input = browser.find_element(By.XPATH, "//input[@placeholder='Search']")
                            
                        search_input.send_keys(query)
                        search_input.submit()
                        
                        # Wait for results
                        time.sleep(5)
                        
                        # Extract document links
                        html_content = browser.page_source
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        # Look for regulation links
                        links = soup.find_all('a', href=True)
                        for link in links:
                            href = link['href']
                            # Filter for likely document links
                            if any(x in href.lower() for x in ['.pdf', 'regulation', 'document', 'standard']):
                                # Get document title
                                doc_title = link.text.strip() if link.text.strip() else href.split('/')[-1]
                                
                                # Add document info
                                doc_info = {
                                    'title': doc_title,
                                    'url': href if href.startswith('http') else f"https://www.interregs.net{href}",
                                    'authority': "Interregs"
                                }
                                
                                if doc_info not in documents:
                                    documents.append(doc_info)
                    except Exception as e:
                        logger.error(f"Browser search failed: {e}")
                except Exception as e:
                    logger.error(f"Browser navigation failed: {e}")
        
        return documents
    
    def _extract_document_links(self, response, authority):
        """Extract document links from response"""
        documents = []
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different approaches to find document links
            # First look for table structures
            tables = soup.find_all('table')
            for table in tables:
                links = table.find_all('a', href=True)
                for link in links:
                    doc_info = self._process_link(link, authority)
                    if doc_info and doc_info not in documents:
                        documents.append(doc_info)
            
            # Then check for common document containers
            containers = soup.find_all(['div', 'section', 'article'], class_=lambda c: c and any(x in c.lower() for x in ['result', 'document', 'regulation', 'standard']))
            for container in containers:
                links = container.find_all('a', href=True)
                for link in links:
                    doc_info = self._process_link(link, authority)
                    if doc_info and doc_info not in documents:
                        documents.append(doc_info)
            
            # Last resort: scan all links and apply heuristics
            if not documents:
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link['href']
                    if any(pattern in href.lower() for pattern in ['.pdf', 'regulation', 'standard', 'document', 'text']):
                        doc_info = self._process_link(link, authority)
                        if doc_info and doc_info not in documents:
                            documents.append(doc_info)
        except Exception as e:
            logger.error(f"Error extracting document links: {e}")
        
        return documents
    
    def _process_link(self, link, authority):
        """Process a link element to extract document information"""
        href = link['href']
        
        # Skip navigation links, javascript links, etc.
        skip_patterns = ['javascript:', '#', 'login', 'register', 'about', 'contact']
        if any(pattern in href.lower() for pattern in skip_patterns):
            return None
        
        # Get document title
        doc_title = link.text.strip()
        if not doc_title:
            # Try to find title in parent elements
            parent = link.parent
            for _ in range(3):  # Check up to 3 levels up
                if parent and parent.text.strip():
                    doc_title = parent.text.strip()
                    break
                if parent:
                    parent = parent.parent
        
        # If still no title, use the URL
        if not doc_title:
            doc_title = href.split('/')[-1]
        
        # Ensure we have absolute URL
        base_url = None
        if hasattr(self, 'current_site') and self.current_site:
            from config import REGULATORY_WEBSITES
            if self.current_site in REGULATORY_WEBSITES:
                base_url = REGULATORY_WEBSITES[self.current_site]['base_url']
        
        if not href.startswith(('http://', 'https://')):
            if base_url:
                doc_url = urljoin(base_url, href)
            else:
                # Try to extract base URL from current URL
                parsed_url = urlparse(link.get('href', ''))
                if parsed_url.netloc:
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    doc_url = urljoin(base_url, href)
                else:
                    # Default to interregs base URL if all else fails
                    doc_url = f"https://www.interregs.net{href}" if href.startswith('/') else f"https://www.interregs.net/{href}"
        else:
            doc_url = href
        
        return {
            'title': doc_title[:200],  # Limit title length
            'url': doc_url,
            'authority': authority
        }
    
    def find_regulatory_documents(self, query, max_docs=5):
        """
        Enhanced method to find regulatory documents related to the query,
        with adaptive learning and improved navigation
        """
        all_documents = []
        
        # First, check if we have any learned successful paths for this query
        query_terms = set(query.lower().split())
        learned_documents = self._get_documents_from_learned_paths(query_terms)
        all_documents.extend(learned_documents)
        
        # If we found enough documents from learned paths, return them
        if len(all_documents) >= max_docs:
            return all_documents[:max_docs]
        
        # Otherwise try Interregs first (our primary source)
        logger.info("Searching Interregs for documents")
        interregs_docs = self.find_interregs_documents(query)
        
        # Add unique documents from Interregs
        for doc in interregs_docs:
            if doc not in all_documents:
                all_documents.append(doc)
                
        # If we found enough documents now, return them
        if len(all_documents) >= max_docs:
            return all_documents[:max_docs]
        
        # If we still need more documents, try other sources
        from config import REGULATORY_WEBSITES
        
        # Choose regulatory websites to try based on query content
        prioritized_sites = self._prioritize_websites(query, REGULATORY_WEBSITES)
        
        for authority, site_info in prioritized_sites:
            # Skip if we already have enough documents
            if len(all_documents) >= max_docs:
                break
                
            self.current_site = authority
            logger.info(f"Searching {authority} for documents")
            
            # Try each alternative path
            paths_to_try = self.adaptive_paths.get(authority, [site_info['regulations_path']])
            if site_info['regulations_path'] not in paths_to_try:
                paths_to_try.insert(0, site_info['regulations_path'])
            
            for path in paths_to_try:
                # Construct search URL
                search_url = self._construct_search_url(site_info['base_url'], path, query, authority)
                
                if not search_url:
                    continue
                
                # Verify URL before attempting to fetch
                if not self.verify_url(search_url):
                    logger.warning(f"URL verification failed for {search_url}")
                    continue
                
                # Get search results page
                response = self.get_with_retry(search_url)
                if not response:
                    continue
                
                # Parse results to find document links
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)
                
                # Filter links that match document patterns
                for link in links:
                    href = link['href']
                    
                    # Skip if not a likely document link
                    if not any(pattern in href.lower() for pattern in site_info['doc_patterns']):
                        continue
                    
                    # Process the link
                    doc_info = self._process_link(link, authority)
                    if doc_info and doc_info not in all_documents:
                        all_documents.append(doc_info)
                        
                        # Save this successful path
                        self.save_successful_path(authority, query, path, True)
                        
                    # Limit the number of documents
                    if len(all_documents) >= max_docs:
                        break
                
                # If we found documents from this path, no need to try other paths
                if any(doc['authority'] == authority for doc in all_documents):
                    break
        
        return all_documents[:max_docs]
    
    def _get_documents_from_learned_paths(self, query_terms):
        """Get documents using previously successful paths"""
        documents = []
        
        if not self.successful_paths:
            return documents
        
        # For each authority, check if we have any learned paths
        for authority, term_paths in self.successful_paths.items():
            for term, paths in term_paths.items():
                # Check if any terms in the learned path match our query
                term_set = set(term.lower().split())
                if query_terms.intersection(term_set):
                    for path, success in paths:
                        if success:
                            try:
                                from config import REGULATORY_WEBSITES
                                
                                if authority in REGULATORY_WEBSITES:
                                    base_url = REGULATORY_WEBSITES[authority]['base_url']
                                    
                                    # Construct URL with the learned path
                                    search_url = self._construct_search_url(
                                        base_url, 
                                        path, 
                                        " ".join(query_terms), 
                                        authority
                                    )
                                    
                                    if search_url and self.verify_url(search_url):
                                        response = self.get_with_retry(search_url)
                                        if response and response.status_code == 200:
                                            soup = BeautifulSoup(response.text, 'html.parser')
                                            links = soup.find_all('a', href=True)
                                            
                                            for link in links:
                                                href = link['href']
                                                if authority in REGULATORY_WEBSITES and any(
                                                    pattern in href.lower() 
                                                    for pattern in REGULATORY_WEBSITES[authority]['doc_patterns']
                                                ):
                                                    doc_info = self._process_link(link, authority)
                                                    if doc_info and doc_info not in documents:
                                                        documents.append(doc_info)
                            except Exception as e:
                                logger.error(f"Error using learned path: {e}")
        
        return documents
    
    def _prioritize_websites(self, query, websites):
        """Prioritize which regulatory websites to check based on query content"""
        # Convert query to lowercase for comparison
        query_lower = query.lower()
        
        # Define keywords that might indicate relevance to specific authorities
        keywords = {
            'UNECE WP.29': ['unece', 'un', 'global', 'international', 'wp29', 'world', 'harmonization'],
            'EU European Commission': ['eu', 'europe', 'european', 'commission', 'ec'],
            'NHTSA': ['nhtsa', 'us', 'usa', 'united states', 'america', 'fmvss'],
            'US EPA': ['epa', 'environment', 'emissions', 'pollution'],
            'Japan MLIT': ['japan', 'japanese', 'jaso', 'mlit'],
            'China MIIT': ['china', 'chinese', 'miit'],
            'India ARAI': ['india', 'indian', 'arai', 'cmvr'],
            'Transport Canada': ['canada', 'canadian', 'cmvss'],
            'UK Department for Transport': ['uk', 'british', 'england', 'britain']
        }
        
        # Score each website based on keyword relevance
        scored_websites = []
        for authority, site_info in websites.items():
            score = 0
            
            # Check for authority name in query
            if authority.lower() in query_lower:
                score += 5
            
            # Check for keywords associated with this authority
            if authority in keywords:
                for keyword in keywords[authority]:
                    if keyword in query_lower:
                        score += 3
            
            # Check if we have successful paths for this authority
            if authority in self.successful_paths:
                score += 2
            
            scored_websites.append((score, authority, site_info))
        
        # Sort by score (descending)
        scored_websites.sort(reverse=True)
        
        # Return as (authority, site_info) tuples
        return [(authority, site_info) for _, authority, site_info in scored_websites]
    
    def _construct_search_url(self, base_url, path, query, authority):
        """Construct search URL based on authority and path"""
        search_url = urljoin(base_url, path)
        search_terms = '+'.join(query.split())
        
        # Construct URL differently based on authority
        if authority == 'UNECE WP.29':
            # For UNECE, check different URL patterns
            if '/regulations' in path:
                return f"{search_url}?keyword={search_terms}"
            else:
                return f"{search_url}/regulations?keyword={search_terms}"
        elif authority == 'NHTSA':
            return f"{search_url}?keywords={search_terms}"
        elif authority == 'EU European Commission':
            return f"{search_url}?query={search_terms}"
        elif authority == 'US EPA':
            return f"{search_url}?search={search_terms}"
        elif 'interregs' in authority.lower():
            if '?' in path:
                return f"{search_url}&search={search_terms}"
            else:
                return f"{search_url}?search={search_terms}"
        else:
            # Default approach for other authorities
            if '?' in path:
                return f"{search_url}&q={search_terms}"
            else:
                return f"{search_url}?q={search_terms}"
    
    def download_document(self, doc_info):
        """
        Enhanced document downloading with diverse format handling,
        error recovery, and partial content extraction
        """
        url = doc_info['url']
        authority = doc_info['authority']
        title = doc_info['title']
        
        logger.info(f"Downloading document: {title} from {authority} ({url})")
        
        try:
            # Handle PDF documents
            if url.lower().endswith('.pdf'):
                # Try to download using session first
                response = self.get_with_retry(url)
                if not response:
                    return None
                
                # Save temporary file
                temp_file = f"temp_doc_{hash(url)}.pdf"
                with open(temp_file, 'wb') as f:
                    f.write(response.content)
                
                try:
                    # Use langchain's PyPDFLoader
                    loader = PyPDFLoader(temp_file)
                    docs = loader.load()
                    
                    # Add metadata
                    for doc in docs:
                        doc.metadata.update({
                            'source': url,
                            'authority': authority,
                            'title': title
                        })
                    
                    logger.info(f"Successfully loaded PDF with {len(docs)} pages")
                    
                    # Clean up
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    return docs
                except Exception as e:
                    logger.error(f"Error processing PDF: {e}")
                    
                    # Clean up
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    # Try browser-based approach as fallback
                    return self._download_with_browser(url, authority, title)
            
            # Handle web documents
            else:
                # Handle Interregs specifically
                if authority == 'Interregs':
                    # Make sure we're logged in
                    if not self.auth_status.get('interregs', False):
                        self.login_to_interregs()
                
                # Try to fetch content
                response = self.get_with_retry(url)
                if not response:
                    return self._download_with_browser(url, authority, title)
                
                # Create a temporary HTML file
                temp_file = f"temp_doc_{hash(url)}.html"
                with open(temp_file, 'wb') as f:
                    f.write(response.content)
                
                try:
                    # Use WebBaseLoader with local file
                    loader = WebBaseLoader(temp_file)
                    docs = loader.load()
                    
                    # Add metadata
                    for doc in docs:
                        doc.metadata.update({
                            'source': url,
                            'authority': authority,
                            'title': title
                        })
                    
                    logger.info(f"Successfully loaded web document with {len(docs)} sections")
                    
                    # Clean up
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    return docs
                except Exception as e:
                    logger.error(f"Error processing web document: {e}")
                    
                    # Clean up
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    # Try browser-based approach as fallback
                    return self._download_with_browser(url, authority, title)
        
        except Exception as e:
            logger.error(f"Error downloading document {url}: {e}")
            return self._download_with_browser(url, authority, title)
    
    def _download_with_browser(self, url, authority, title):
        """Download document using browser as a fallback"""
        logger.info(f"Attempting to download with browser: {url}")
        
        browser = self._get_browser()
        if not browser:
            return None
        
        try:
            browser.get(url)
            
            # Wait for page to load
            WebDriverWait(browser, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extract content
            html_content = browser.page_source
            
            # Create a temporary HTML file
            temp_file = f"temp_doc_{hash(url)}.html"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Use document splitter to create documents
            try:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=2000,
                    chunk_overlap=200
                )
                
                docs = []
                with open(temp_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    splits = text_splitter.split_text(content)
                    
                    # Create documents from splits
                    from langchain.schema import Document
                    for i, split in enumerate(splits):
                        docs.append(Document(
                            page_content=split,
                            metadata={
                                'source': url,
                                'authority': authority,
                                'title': title,
                                'chunk': i
                            }
                        ))
                
                # Clean up
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                logger.info(f"Successfully created {len(docs)} document chunks from browser content")
                return docs
            except Exception as e:
                logger.error(f"Error processing browser content: {e}")
                
                # Clean up
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                # Last attempt: create a single document from browser content
                try:
                    from langchain.schema import Document
                    docs = [Document(
                        page_content=BeautifulSoup(html_content, 'html.parser').get_text(),
                        metadata={
                            'source': url,
                            'authority': authority,
                            'title': title
                        }
                    )]
                    return docs
                except Exception as e:
                    logger.error(f"Final attempt failed: {e}")
                    return None
        except Exception as e:
            logger.error(f"Browser download failed: {e}")
            return None
    
    def close(self):
        """Close browser if it's open"""
        if self.browser:
            try:
                self.browser.quit()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            self.browser = None

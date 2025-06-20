import requests
import logging
from typing import List, Tuple, Dict, Any
from bs4 import BeautifulSoup
import re
from config import INTERREGS_EMAIL, INTERREGS_PASSWORD, INTERREGS_BASE_URL, ERROR_MESSAGES

logger = logging.getLogger(__name__)

class InterregsClient:
    """Client for accessing Interregs.net regulatory database."""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = INTERREGS_BASE_URL
        self.logged_in = False
    
    def login(self) -> bool:
        """
        Login to Interregs.net using provided credentials.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            # First try to access the main page to check if it's accessible
            main_page = self.session.get(f"{self.base_url}/db/index.php", timeout=15)
            
            if main_page.status_code != 200:
                logger.error(f"Cannot access Interregs.net main page: {main_page.status_code}")
                return False
            
            # Check if we're already logged in or if login is required
            if 'welcome' in main_page.text.lower() or 'dashboard' in main_page.text.lower():
                self.logged_in = True
                logger.info("Already logged into Interregs.net or no login required")
                return True
            
            # Look for login form
            soup = BeautifulSoup(main_page.content, 'html.parser')
            
            # Try multiple login form selectors
            login_form = (soup.find('form', {'id': 'login'}) or 
                         soup.find('form', class_=re.compile(r'login', re.I)) or
                         soup.find('form') or
                         soup.find('input', {'type': 'email'}))
            
            if not login_form:
                logger.warning("No login form found on Interregs.net - attempting direct access")
                # Try to access database directly
                db_page = self.session.get(f"{self.base_url}/db/search.php", timeout=15)
                if db_page.status_code == 200:
                    self.logged_in = True
                    return True
                else:
                    return False
            
            # Prepare login data with multiple possible field names
            login_data = {
                'email': INTERREGS_EMAIL,
                'password': INTERREGS_PASSWORD,
                'username': INTERREGS_EMAIL,  # Alternative field name
                'login_email': INTERREGS_EMAIL,  # Alternative field name
                'login_password': INTERREGS_PASSWORD  # Alternative field name
            }
            
            # Add any hidden form fields (CSRF tokens, etc.)
            if isinstance(login_form, dict):
                # If we found an input, look for its parent form
                login_form = login_form.find_parent('form') if hasattr(login_form, 'find_parent') else None
            
            if login_form:
                for hidden_input in login_form.find_all('input', type='hidden'):
                    if hidden_input.get('name'):
                        login_data[hidden_input.get('name')] = hidden_input.get('value', '')
            
            # Try multiple login endpoints
            login_endpoints = [
                f"{self.base_url}/login.php",
                f"{self.base_url}/db/login.php", 
                f"{self.base_url}/auth/login.php",
                f"{self.base_url}/user/login.php"
            ]
            
            for endpoint in login_endpoints:
                try:
                    login_response = self.session.post(
                        endpoint,
                        data=login_data,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Referer': f"{self.base_url}/db/index.php"
                        },
                        timeout=15
                    )
                    
                    if login_response.status_code == 200:
                        # Check for success indicators
                        response_text = login_response.text.lower()
                        if any(indicator in response_text for indicator in ['welcome', 'dashboard', 'logout', 'profile']):
                            self.logged_in = True
                            logger.info(f"Successfully logged into Interregs.net via {endpoint}")
                            return True
                        elif 'error' not in response_text and 'invalid' not in response_text:
                            # If no explicit error, assume success
                            self.logged_in = True
                            logger.info(f"Logged into Interregs.net via {endpoint} (assumed success)")
                            return True
                    
                except Exception as e:
                    logger.debug(f"Login attempt failed for {endpoint}: {str(e)}")
                    continue
            
            logger.error("All login attempts failed for Interregs.net")
            return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Interregs.net login: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Interregs.net login: {str(e)}")
            return False
    
    def search_regulations(self, query: str, region: str = "", category: str = "") -> Tuple[List[str], List[str], List[str]]:
        """
        Search for regulations in Interregs.net database.
        
        Args:
            query: Search query
            region: Optional region filter
            category: Optional category filter
        
        Returns:
            Tuple of (regulation_texts, source_urls, source_titles)
        """
        if not self.logged_in and not self.login():
            raise Exception(ERROR_MESSAGES["interregs_api_error"])
        
        try:
            # Prepare search parameters
            search_params = {
                'search': query,
                'region': region,
                'category': category,
                'action': 'search'
            }
            
            # Perform search
            search_response = self.session.get(
                f"{self.base_url}/db/search.php",
                params=search_params
            )
            search_response.raise_for_status()
            
            # Parse search results
            soup = BeautifulSoup(search_response.content, 'html.parser')
            
            regulation_texts = []
            source_urls = []
            source_titles = []
            
            # Find regulation entries in search results
            regulation_entries = soup.find_all('div', class_=['regulation-entry', 'search-result'])
            
            if not regulation_entries:
                # Try alternative selectors
                regulation_entries = soup.find_all(['tr', 'li'], class_=re.compile(r'regulation|result'))
            
            for entry in regulation_entries[:5]:  # Limit to top 5 results
                # Extract regulation title
                title_elem = entry.find(['h3', 'h4', 'a', 'strong'])
                title = title_elem.get_text(strip=True) if title_elem else "Regulation Document"
                
                # Extract regulation link
                link_elem = entry.find('a', href=True)
                if link_elem:
                    reg_url = link_elem['href']
                    if not reg_url.startswith('http'):
                        reg_url = f"{self.base_url}{reg_url}" if reg_url.startswith('/') else f"{self.base_url}/db/{reg_url}"
                    
                    # Get full regulation content
                    reg_content = self._get_regulation_content(reg_url)
                    if reg_content:
                        regulation_texts.append(reg_content)
                        source_urls.append(reg_url)
                        source_titles.append(title)
                
                # Also extract any summary text directly from search results
                summary_elem = entry.find(['p', 'div'], class_=re.compile(r'summary|description|content'))
                if summary_elem:
                    summary = summary_elem.get_text(strip=True)
                    if len(summary) > 100:  # Only include substantial summaries
                        regulation_texts.append(f"Summary: {summary}")
                        source_urls.append(search_response.url)
                        source_titles.append(f"{title} - Summary")
            
            logger.info(f"Found {len(regulation_texts)} regulations from Interregs.net for query: {query}")
            return regulation_texts, source_urls, source_titles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Interregs.net search: {str(e)}")
            raise Exception(ERROR_MESSAGES["interregs_api_error"])
        except Exception as e:
            logger.error(f"Error searching Interregs.net: {str(e)}")
            raise Exception(ERROR_MESSAGES["interregs_api_error"])
    
    def _get_regulation_content(self, url: str) -> str:
        """
        Get full content of a regulation document.
        
        Args:
            url: URL of the regulation document
        
        Returns:
            str: Full text content of the regulation
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove navigation, ads, and other non-content elements
            for element in soup(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                element.decompose()
            
            # Find main content area
            content_selectors = [
                'div.regulation-content',
                'div.content',
                'main',
                'article',
                'div.document',
                'div.text-content'
            ]
            
            content = None
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    break
            
            if not content:
                # Fallback to body content
                content = soup.find('body')
            
            if content:
                # Extract clean text
                text = content.get_text(separator='\n', strip=True)
                
                # Clean up excessive whitespace
                text = re.sub(r'\n\s*\n', '\n\n', text)
                text = re.sub(r' +', ' ', text)
                
                return text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error fetching regulation content from {url}: {str(e)}")
            return ""
    
    def get_regulation_by_id(self, regulation_id: str) -> Tuple[str, str, str]:
        """
        Get specific regulation by ID.
        
        Args:
            regulation_id: ID of the regulation (e.g., ATO-01)
        
        Returns:
            Tuple of (regulation_text, source_url, source_title)
        """
        if not self.logged_in and not self.login():
            raise Exception(ERROR_MESSAGES["interregs_api_error"])
        
        try:
            # Construct URL for specific regulation
            reg_url = f"{self.base_url}/db/index.php?id={regulation_id}"
            
            response = self.session.get(reg_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_elem = soup.find(['h1', 'h2', 'title'])
            title = title_elem.get_text(strip=True) if title_elem else f"Regulation {regulation_id}"
            
            # Extract content
            content = self._get_regulation_content(reg_url)
            
            return content, reg_url, title
            
        except Exception as e:
            logger.error(f"Error fetching regulation {regulation_id} from Interregs.net: {str(e)}")
            raise Exception(ERROR_MESSAGES["interregs_api_error"])


def search_interregs_regulations(query: str, region: str = "", category: str = "") -> Tuple[List[str], List[str], List[str]]:
    """
    Search Interregs.net for automotive regulations.
    
    Args:
        query: Search query
        region: Optional region filter
        category: Optional category filter
    
    Returns:
        Tuple of (regulation_texts, source_urls, source_titles)
    """
    client = InterregsClient()
    return client.search_regulations(query, region, category)


def get_interregs_regulation(regulation_id: str) -> Tuple[str, str, str]:
    """
    Get specific regulation from Interregs.net by ID.
    
    Args:
        regulation_id: Regulation ID
    
    Returns:
        Tuple of (regulation_text, source_url, source_title)
    """
    client = InterregsClient()
    return client.get_regulation_by_id(regulation_id)

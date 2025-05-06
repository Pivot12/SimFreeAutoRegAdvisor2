import os
import json
import time
import requests
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

class InterregsClient:
    """Client for accessing the interregs.net regulatory database."""
    
    def __init__(self, email: str, password: str, logger=None):
        """Initialize with login credentials."""
        self.email = email
        self.password = password
        self.base_url = "https://www.interregs.net"
        self.session = requests.Session()
        self.logged_in = False
        self.last_request_time = 0
        self.request_delay = 1.0  # Delay between requests in seconds
        
        # Setup logging
        self.logger = logger if logger else logging.getLogger(__name__)
    
    def login(self) -> bool:
        """Login to interregs.net."""
        if self.logged_in:
            return True
            
        try:
            # Respect rate limits
            self._respect_rate_limit()
            
            # Get the login page first to obtain any CSRF tokens
            login_url = f"{self.base_url}/login"
            response = self.session.get(login_url)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to get login page: {response.status_code}")
                return False
            
            # Extract CSRF token if present
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_token = None
            token_field = soup.find('input', {'name': '_token'})
            if token_field:
                csrf_token = token_field.get('value')
            
            # Prepare login data
            login_data = {
                'email': self.email,
                'password': self.password
            }
            
            if csrf_token:
                login_data['_token'] = csrf_token
            
            # Perform login
            self._respect_rate_limit()
            response = self.session.post(
                login_url, 
                data=login_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': login_url
                }
            )
            
            # Check if login was successful
            if response.status_code == 200 and 'Dashboard' in response.text:
                self.logged_in = True
                self.logger.info("Successfully logged in to interregs.net")
                return True
            else:
                self.logger.error(f"Login failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during login: {str(e)}")
            return False
    
    def search_regulations(self, query: str, region: Optional[str] = None) -> List[Dict]:
        """
        Search for regulations matching the query.
        
        Args:
            query: Search terms
            region: Optional region filter (e.g., "EU", "US", "UN")
            
        Returns:
            List of regulation dictionaries with title, url, and description
        """
        if not self.logged_in and not self.login():
            self.logger.error("Not logged in, cannot search")
            return []
        
        try:
            # Respect rate limits
            self._respect_rate_limit()
            
            # Build search URL
            search_url = f"{self.base_url}/search"
            search_params = {'q': query}
            
            if region:
                search_params['region'] = region
            
            # Perform search
            response = self.session.get(search_url, params=search_params)
            
            if response.status_code != 200:
                self.logger.error(f"Search failed: {response.status_code}")
                return []
            
            # Parse results
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find search result elements - this needs to be adjusted based on actual HTML structure
            result_elements = soup.find_all('div', class_='search-result-item')
            
            if not result_elements:
                # Try alternative selectors if the expected class isn't found
                result_elements = soup.find_all('div', class_='result-item')
            
            if not result_elements:
                # Try a more generic approach if specific classes not found
                # Look for links within the main content area
                main_content = soup.find('main') or soup.find('div', id='content') or soup.find('div', class_='container')
                if main_content:
                    result_elements = main_content.find_all('a', href=True)
            
            for result in result_elements:
                try:
                    # Extract title and URL
                    title_element = result.find('h3') or result.find('h4') or result.find('h2') or result
                    title = title_element.get_text().strip()
                    
                    # Get URL if it's a link or contains a link
                    url = None
                    if result.name == 'a' and result.has_attr('href'):
                        url = result['href']
                    else:
                        link = result.find('a', href=True)
                        if link:
                            url = link['href']
                    
                    if url and not url.startswith(('http://', 'https://')):
                        url = urljoin(self.base_url, url)
                    
                    # Extract description if available
                    description_element = result.find('p') or result.find('div', class_='description')
                    description = description_element.get_text().strip() if description_element else ""
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'url': url,
                            'description': description
                        })
                except Exception as e:
                    self.logger.error(f"Error parsing result: {str(e)}")
                    continue
            
            self.logger.info(f"Found {len(results)} search results for query: {query}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error during search: {str(e)}")
            return []
    
    def get_regulation_content(self, url: str) -> Optional[str]:
        """
        Get the full content of a regulation.
        
        Args:
            url: URL of the regulation page
            
        Returns:
            Content of the regulation as text, or None if unsuccessful
        """
        if not self.logged_in and not self.login():
            self.logger.error("Not logged in, cannot get regulation content")
            return None
        
        try:
            # Respect rate limits
            self._respect_rate_limit()
            
            # Fetch the regulation page
            response = self.session.get(url)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to get regulation: {response.status_code}")
                return None
            
            # Parse the content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the main content container - this needs to be adjusted based on actual HTML structure
            content_element = soup.find('div', class_='regulation-content')
            
            if not content_element:
                # Try alternative selectors if the expected class isn't found
                content_element = soup.find('article') or soup.find('div', class_='content')
            
            if not content_element:
                # Fallback to the main element or body if specific containers not found
                content_element = soup.find('main') or soup.body
            
            if content_element:
                # Extract text content
                content = content_element.get_text(separator='\n\n')
                
                # Additional cleaning
                content = content.replace('\n\n\n\n', '\n\n')
                
                return content
            else:
                self.logger.error("Couldn't find content container in regulation page")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting regulation content: {str(e)}")
            return None
    
    def get_regions(self) -> List[Dict]:
        """Get available regulatory regions."""
        if not self.logged_in and not self.login():
            self.logger.error("Not logged in, cannot get regions")
            return []
        
        try:
            # Respect rate limits
            self._respect_rate_limit()
            
            # Get the regions page or API endpoint
            response = self.session.get(f"{self.base_url}/regions")
            
            if response.status_code != 200:
                self.logger.error(f"Failed to get regions: {response.status_code}")
                return []
            
            # Parse the regions
            soup = BeautifulSoup(response.text, 'html.parser')
            regions = []
            
            # Find region elements - this needs to be adjusted based on actual HTML structure
            region_elements = soup.find_all('div', class_='region-item')
            
            if not region_elements:
                # Try alternative approach - look for links to regions
                links = soup.find_all('a', href=True)
                region_links = [link for link in links if '/region/' in link['href']]
                
                for link in region_links:
                    region_id = link['href'].split('/region/')[1]
                    region_name = link.get_text().strip()
                    regions.append({
                        'id': region_id,
                        'name': region_name
                    })
            else:
                for region in region_elements:
                    region_name = region.get_text().strip()
                    region_id = region.get('data-id', '')
                    regions.append({
                        'id': region_id,
                        'name': region_name
                    })
            
            return regions
            
        except Exception as e:
            self.logger.error(f"Error getting regions: {str(e)}")
            return []
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        
        self.last_request_time = time.time()

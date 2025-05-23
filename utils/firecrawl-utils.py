import requests
import logging
import time
from typing import List, Tuple, Dict, Any
from config import FIRECRAWL_BASE_URL, MAX_SITES_PER_QUERY, MAX_RESULTS_PER_SITE, CRAWL_DEPTH, ERROR_MESSAGES

logger = logging.getLogger(__name__)

def fetch_regulation_data(
    query: str, 
    websites: List[str], 
    api_key: str
) -> Tuple[List[str], List[str], List[str]]:
    """
    Fetch regulation data from multiple regulatory websites using Firecrawl API.
    
    Args:
        query: User query about automotive regulations
        websites: List of regulatory websites to search
        api_key: Firecrawl API key
    
    Returns:
        Tuple containing:
            - List of extracted regulatory texts
            - List of source URLs
            - List of source titles
    """
    logger.info(f"Fetching regulation data for query: {query}")
    
    # Prepare search terms based on query
    search_terms = prepare_search_terms(query)
    
    # Prepare websites for search (limit to MAX_SITES_PER_QUERY)
    target_websites = websites[:MAX_SITES_PER_QUERY]
    
    all_regulation_data = []
    all_source_urls = []
    all_source_titles = []
    
    for website in target_websites:
        try:
            logger.debug(f"Searching website: {website}")
            
            # First, scrape the website to get content
            scrape_data = scrape_website(website, api_key)
            
            # Check if we got useful content from scraping
            if not scrape_data or "markdown" not in scrape_data:
                logger.warning(f"No useful content found from scraping {website}")
                continue
            
            # Get title of the website
            website_title = scrape_data.get("metadata", {}).get("title", website)
            
            # Extract regulation content that's relevant to the query
            relevant_content = extract_relevant_content(scrape_data["markdown"], search_terms)
            
            if relevant_content:
                all_regulation_data.append(relevant_content)
                all_source_urls.append(website)
                all_source_titles.append(website_title)
                logger.debug(f"Found relevant content from {website}")
            
            # Optionally, if we need more content, crawl the website
            if CRAWL_DEPTH > 0:
                crawl_data, urls, titles = crawl_website(website, search_terms, api_key, max_results=MAX_RESULTS_PER_SITE)
                
                # Add results from crawling to our lists
                all_regulation_data.extend(crawl_data)
                all_source_urls.extend(urls)
                all_source_titles.extend(titles)
            
        except Exception as e:
            logger.error(f"Error fetching data from {website}: {str(e)}")
            continue
    
    if not all_regulation_data:
        logger.warning("No regulation data found from any website")
        raise ValueError(ERROR_MESSAGES["no_data_found"])
    
    logger.info(f"Successfully fetched regulation data from {len(all_source_urls)} sources")
    return all_regulation_data, all_source_urls, all_source_titles

def prepare_search_terms(query: str) -> List[str]:
    """
    Prepare search terms based on user query.
    Extract key phrases and keywords for regulation search.
    
    Args:
        query: The user's query about automotive regulations
    
    Returns:
        List of search terms
    """
    # Remove common words and split query into terms
    common_words = ["what", "is", "are", "the", "for", "a", "an", "in", "on", "about", "how", "can", "do", "does"]
    terms = query.lower().split()
    terms = [term for term in terms if term not in common_words]
    
    # Add specific regulation terminology
    regulation_terms = ["regulation", "standard", "directive", "requirement", "law", "homologation", "type approval"]
    region_terms = ["eu", "european", "us", "united states", "uk", "japan", "china", "global", "international"]
    
    # Find any specific regulation codes mentioned (e.g., ECE-R100)
    import re
    reg_codes = re.findall(r'[A-Z]{1,5}[-]\d{1,4}', query)
    
    # Combine all search terms
    search_terms = terms + regulation_terms + region_terms + reg_codes
    
    # Remove duplicates
    search_terms = list(set(search_terms))
    
    return search_terms

def scrape_website(url: str, api_key: str) -> Dict[str, Any]:
    """
    Scrape a website using Firecrawl API.
    
    Args:
        url: Website URL to scrape
        api_key: Firecrawl API key
    
    Returns:
        Dictionary containing the scraped content
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "url": url,
        "formats": ["markdown", "html"],
        "withMetadata": True
    }
    
    try:
        response = requests.post(
            f"{FIRECRAWL_BASE_URL}/scrape",
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            logger.error(f"Error scraping {url}: {response.text}")
            return {}
        
        return response.json()
    
    except Exception as e:
        logger.error(f"Error in scrape_website for {url}: {str(e)}")
        raise Exception(ERROR_MESSAGES["firecrawl_api_error"])

def crawl_website(
    url: str, 
    search_terms: List[str], 
    api_key: str, 
    max_results: int = 3
) -> Tuple[List[str], List[str], List[str]]:
    """
    Crawl a website to find relevant regulation content using Firecrawl API.
    
    Args:
        url: Website URL to crawl
        search_terms: List of search terms to find relevant content
        api_key: Firecrawl API key
        max_results: Maximum number of results to return
    
    Returns:
        Tuple containing:
            - List of regulation contents
            - List of source URLs
            - List of source titles
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Since crawling can take time, we'll use the async crawl method
    crawl_data = {
        "url": url,
        "limit": 10,  # Only crawl up to 10 pages
        "scrapeOptions": {
            "formats": ["markdown"],
            "withMetadata": True
        }
    }
    
    try:
        # Start the crawl job
        crawl_response = requests.post(
            f"{FIRECRAWL_BASE_URL}/crawl",
            headers=headers,
            json=crawl_data
        )
        
        if crawl_response.status_code != 200:
            logger.error(f"Error starting crawl for {url}: {crawl_response.text}")
            return [], [], []
        
        crawl_job = crawl_response.json()
        job_id = crawl_job.get("id")
        
        if not job_id:
            logger.error(f"No job ID returned for crawl of {url}")
            return [], [], []
        
        # Wait for the crawl job to complete (with timeout)
        max_attempts = 5
        attempts = 0
        crawl_results = None
        
        while attempts < max_attempts:
            attempts += 1
            
            # Check job status
            status_response = requests.get(
                f"{FIRECRAWL_BASE_URL}/crawl/{job_id}",
                headers=headers
            )
            
            if status_response.status_code != 200:
                logger.error(f"Error checking crawl status: {status_response.text}")
                time.sleep(2)
                continue
            
            status_data = status_response.json()
            
            if status_data.get("status") == "completed":
                crawl_results = status_data.get("data", [])
                break
            elif status_data.get("status") == "failed":
                logger.error(f"Crawl job failed for {url}")
                return [], [], []
            
            # Wait before checking again
            time.sleep(2)
        
        if not crawl_results:
            logger.warning(f"Crawl job timed out or returned no results for {url}")
            return [], [], []
        
        # Process the crawl results
        regulation_contents = []
        source_urls = []
        source_titles = []
        
        for result in crawl_results:
            if "markdown" not in result:
                continue
            
            # Check if the content is relevant to our search terms
            content = result["markdown"]
            relevant_content = extract_relevant_content(content, search_terms)
            
            if relevant_content:
                # Get the source URL and title
                source_url = result.get("metadata", {}).get("sourceURL", url)
                source_title = result.get("metadata", {}).get("title", source_url)
                
                regulation_contents.append(relevant_content)
                source_urls.append(source_url)
                source_titles.append(source_title)
                
                # Limit the number of results
                if len(regulation_contents) >= max_results:
                    break
        
        return regulation_contents, source_urls, source_titles
    
    except Exception as e:
        logger.error(f"Error in crawl_website for {url}: {str(e)}")
        raise Exception(ERROR_MESSAGES["firecrawl_api_error"])

def extract_relevant_content(content: str, search_terms: List[str]) -> str:
    """
    Extract relevant parts of the content based on search terms.
    
    Args:
        content: The full content from a webpage
        search_terms: List of search terms to find relevant content
    
    Returns:
        Extracted relevant content as a string
    """
    # Split content into paragraphs
    paragraphs = content.split('\n\n')
    relevant_paragraphs = []
    
    for paragraph in paragraphs:
        # Check if this paragraph contains any search terms
        if any(term.lower() in paragraph.lower() for term in search_terms):
            relevant_paragraphs.append(paragraph)
    
    # If we have too few paragraphs, widen the search
    if len(relevant_paragraphs) < 2:
        # Try looking for sentences containing our terms
        sentences = content.replace('\n', ' ').split('. ')
        for sentence in sentences:
            if any(term.lower() in sentence.lower() for term in search_terms) and sentence not in ' '.join(relevant_paragraphs):
                relevant_paragraphs.append(sentence + '.')
    
    # Join the relevant paragraphs into a single string
    if relevant_paragraphs:
        return '\n\n'.join(relevant_paragraphs)
    
    # If we couldn't find anything relevant, return an empty string
    return ""

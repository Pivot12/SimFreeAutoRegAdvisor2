import requests
import logging
import time
import re
from typing import List, Tuple, Dict, Any
from config import (
    FIRECRAWL_BASE_URL, 
    MAX_SITES_PER_QUERY, 
    MAX_RESULTS_PER_SITE, 
    CRAWL_DEPTH, 
    ERROR_MESSAGES,
    REGULATORY_WEBSITES,
    WEBSITE_SELECTION_CRITERIA,
    REGION_WEBSITES,
    CEREBRAS_API_KEY
)
from utils.interregs_utils import search_interregs_regulations

logger = logging.getLogger(__name__)

def select_websites_with_llm(query: str, api_key: str) -> List[str]:
    """
    Use LLM to determine the most appropriate regulatory websites for the query.
    
    Args:
        query: User query about automotive regulations
        api_key: Cerebras API key
    
    Returns:
        List of selected website URLs
    """
    try:
        from cerebras.cloud.sdk import Cerebras
        
        client = Cerebras(api_key=api_key)
        
        # Create prompt for website selection
        websites_info = "\n".join([f"- {key}: {url}" for key, url in REGULATORY_WEBSITES.items()])
        
        prompt = f"""You are an automotive regulatory expert. Given the user query, select the 3 most appropriate regulatory websites to search from this list:

{websites_info}

Query: "{query}"

Consider:
- Geographic regions mentioned (US, EU, Japan, etc.)
- Regulation categories (emissions, safety, homologation, etc.)
- Specific agencies or standards mentioned

Respond with ONLY the website keys (e.g., US_NHTSA, EU_COMMISSION, UNECE) separated by commas, in order of relevance."""

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-4-scout-17b-16e-instruct",
            temperature=0.1,
            max_tokens=100
        )
        
        # Parse LLM response
        selected_keys = [key.strip() for key in response.choices[0].message.content.split(',')]
        selected_websites = [REGULATORY_WEBSITES[key] for key in selected_keys if key in REGULATORY_WEBSITES]
        
        if selected_websites:
            logger.info(f"LLM selected websites: {selected_keys}")
            return selected_websites[:MAX_SITES_PER_QUERY]
        else:
            logger.warning("LLM didn't select valid websites, falling back to heuristic selection")
            return select_websites_heuristic(query)
            
    except Exception as e:
        logger.error(f"Error using LLM for website selection: {str(e)}")
        return select_websites_heuristic(query)

def select_websites_heuristic(query: str) -> List[str]:
    """
    Fallback heuristic method for website selection when LLM fails.
    
    Args:
        query: User query about automotive regulations
    
    Returns:
        List of selected website URLs
    """
    query_lower = query.lower()
    selected_websites = set()
    
    # Region-based selection
    for region, websites in REGION_WEBSITES.items():
        if region in query_lower:
            for website_key in websites:
                if website_key in REGULATORY_WEBSITES:
                    selected_websites.add(REGULATORY_WEBSITES[website_key])
    
    # Category-based selection
    for category, websites in WEBSITE_SELECTION_CRITERIA.items():
        if category in query_lower or category.replace('_', ' ') in query_lower:
            for website_key in websites:
                if website_key in REGULATORY_WEBSITES:
                    selected_websites.add(REGULATORY_WEBSITES[website_key])
    
    # If no specific matches, use global sources
    if not selected_websites:
        global_keys = ["UNECE", "EU_COMMISSION", "US_EPA"]
        selected_websites = {REGULATORY_WEBSITES[key] for key in global_keys if key in REGULATORY_WEBSITES}
    
    return list(selected_websites)[:MAX_SITES_PER_QUERY]

def fetch_regulation_data(
    query: str, 
    websites: List[str], 
    api_key: str
) -> Tuple[List[str], List[str], List[str]]:
    """
    Fetch regulation data from multiple regulatory websites using Firecrawl API.
    Falls back to Interregs.net if primary sources fail.
    
    Args:
        query: User query about automotive regulations
        websites: List of regulatory websites to search (ignored - LLM will select)
        api_key: Firecrawl API key
    
    Returns:
        Tuple containing:
            - List of extracted regulatory texts
            - List of source URLs
            - List of source titles
    """
    logger.info(f"Fetching regulation data for query: {query}")
    
    # Check if API key is configured
    if not api_key or api_key == "YOUR_FIRECRAWL_API_KEY":
        logger.error("Firecrawl API key not configured")
        raise ValueError(ERROR_MESSAGES["api_key_missing"])
    
    # Use LLM to select most appropriate websites
    target_websites = select_websites_with_llm(query, CEREBRAS_API_KEY)
    
    # Prepare search terms based on query
    search_terms = prepare_search_terms(query)
    
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
            
            # Extract regulation content that's relevant to the query - ENHANCED VERSION
            relevant_content = extract_detailed_regulatory_content(scrape_data["markdown"], search_terms, query)
            
            if relevant_content and len(relevant_content.strip()) > 100:  # Ensure substantial content
                all_regulation_data.append(relevant_content)
                all_source_urls.append(website)
                all_source_titles.append(website_title)
                logger.debug(f"Found relevant content from {website}")
            
        except Exception as e:
            logger.error(f"Error fetching data from {website}: {str(e)}")
            continue
    
    # If we didn't find sufficient data from primary sources, try Interregs.net as backup
    if len(all_regulation_data) < 2:
        logger.info("Insufficient data from primary sources, trying Interregs.net backup")
        try:
            # Extract region and category for Interregs search
            region = extract_region_from_query(query)
            category = extract_category_from_query(query)
            
            interregs_data, interregs_urls, interregs_titles = search_interregs_regulations(
                query, region, category
            )
            
            all_regulation_data.extend(interregs_data)
            all_source_urls.extend(interregs_urls)
            all_source_titles.extend(interregs_titles)
            
            logger.info(f"Added {len(interregs_data)} results from Interregs.net backup")
            
        except Exception as e:
            logger.error(f"Error fetching data from Interregs.net backup: {str(e)}")
    
    # If still no data found, raise an error
    if not all_regulation_data:
        logger.error("No regulation data found from any source")
        raise ValueError(ERROR_MESSAGES["no_data_found"])
    
    logger.info(f"Successfully fetched regulation data from {len(all_source_urls)} sources")
    return all_regulation_data, all_source_urls, all_source_titles

def extract_detailed_regulatory_content(content: str, search_terms: List[str], query: str) -> str:
    """
    Enhanced content extraction that focuses on specific regulatory information.
    
    Args:
        content: The full content from a webpage
        search_terms: List of search terms to find relevant content
        query: Original user query for context
    
    Returns:
        Extracted relevant regulatory content as a string
    """
    if not content:
        return ""
    
    # Split content into sections and paragraphs
    sections = re.split(r'\n#{1,6}\s+', content)  # Split by markdown headers
    relevant_sections = []
    
    # First pass: Find sections with high relevance
    for section in sections:
        if not section.strip():
            continue
            
        section_score = 0
        section_lower = section.lower()
        
        # Score based on search terms
        for term in search_terms:
            if term.lower() in section_lower:
                section_score += 1
        
        # Bonus points for regulatory indicators
        regulatory_indicators = [
            'regulation', 'directive', 'standard', 'requirement', 'shall', 'must',
            'compliance', 'certification', 'approval', 'limit', 'maximum', 'minimum',
            'article', 'section', 'paragraph', 'amendment', 'annex'
        ]
        
        for indicator in regulatory_indicators:
            if indicator in section_lower:
                section_score += 0.5
        
        # Bonus for specific regulation numbers
        if re.search(r'(regulation|directive|standard)\s+(no\.?\s*)?(\d+|[A-Z]+[-/]\d+)', section_lower):
            section_score += 2
        
        # Include if score is high enough
        if section_score >= 2:
            relevant_sections.append((section_score, section))
    
    # Sort by relevance score and take top sections
    relevant_sections.sort(key=lambda x: x[0], reverse=True)
    
    # Extract the most relevant content
    extracted_content = []
    total_length = 0
    max_content_length = 3000  # Limit to prevent token overflow
    
    for score, section in relevant_sections:
        if total_length >= max_content_length:
            break
            
        # Clean and format the section
        cleaned_section = clean_regulatory_text(section)
        
        if len(cleaned_section) > 50:  # Only include substantial sections
            extracted_content.append(cleaned_section)
            total_length += len(cleaned_section)
    
    # If we don't have enough content, do a second pass with lower threshold
    if not extracted_content:
        paragraphs = content.split('\n\n')
        for paragraph in paragraphs[:10]:  # Check first 10 paragraphs
            if any(term.lower() in paragraph.lower() for term in search_terms):
                cleaned_para = clean_regulatory_text(paragraph)
                if len(cleaned_para) > 30:
                    extracted_content.append(cleaned_para)
    
    return '\n\n'.join(extracted_content) if extracted_content else ""

def clean_regulatory_text(text: str) -> str:
    """
    Clean and format regulatory text for better processing.
    
    Args:
        text: Raw regulatory text
    
    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Remove common navigation/footer elements
    text = re.sub(r'(Cookie|Privacy|Terms|Contact|Navigation|Menu|Search|Login).*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove URLs that are not regulation references
    text = re.sub(r'https?://[^\s]+(?<!\.pdf)(?<!regulations?)(?<!directive)', '', text)
    
    # Clean up markdown artifacts
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Remove markdown links but keep text
    text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)  # Remove markdown emphasis
    
    # Remove excessive punctuation
    text = re.sub(r'[.]{3,}', '...', text)
    text = re.sub(r'[-]{3,}', '---', text)
    
    return text.strip()

def extract_region_from_query(query: str) -> str:
    """Extract region information from query for Interregs search."""
    query_lower = query.lower()
    
    if any(term in query_lower for term in ['us', 'usa', 'united states', 'america']):
        return 'US'
    elif any(term in query_lower for term in ['eu', 'europe', 'european']):
        return 'EU'
    elif 'japan' in query_lower:
        return 'Japan'
    elif 'china' in query_lower:
        return 'China'
    elif any(term in query_lower for term in ['uk', 'britain', 'british']):
        return 'UK'
    elif 'india' in query_lower:
        return 'India'
    elif 'australia' in query_lower:
        return 'Australia'
    else:
        return 'Global'

def extract_category_from_query(query: str) -> str:
    """Extract category information from query for Interregs search."""
    query_lower = query.lower()
    
    if any(term in query_lower for term in ['emission', 'exhaust', 'co2', 'pollution']):
        return 'Emissions'
    elif any(term in query_lower for term in ['safety', 'crash', 'protection']):
        return 'Safety'
    elif any(term in query_lower for term in ['homologation', 'type approval', 'certification']):
        return 'Homologation'
    elif any(term in query_lower for term in ['electric', 'ev', 'battery']):
        return 'Electric Vehicles'
    elif any(term in query_lower for term in ['fuel', 'gasoline', 'diesel']):
        return 'Fuel'
    elif any(term in query_lower for term in ['noise', 'sound']):
        return 'Noise'
    elif any(term in query_lower for term in ['light', 'lamp', 'illumination']):
        return 'Lighting'
    else:
        return 'General'

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
    terms = [term for term in terms if term not in common_words and len(term) > 2]
    
    # Add specific regulation terminology
    regulation_terms = ["regulation", "standard", "directive", "requirement", "law", "homologation", "type approval"]
    region_terms = ["eu", "european", "us", "united states", "uk", "japan", "china", "global", "international"]
    
    # Find any specific regulation codes mentioned (e.g., ECE-R100)
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
        "formats": ["markdown"],
        "timeout": 30000,  # Timeout in milliseconds (30 seconds)
        "extractorOptions": {
            "mode": "llm-extraction",
            "extractionPrompt": "Extract all regulatory content, standards, requirements, and official guidelines related to automotive regulations. Include regulation numbers, compliance requirements, and official standards."
        }
    }
    
    try:
        response = requests.post(
            f"{FIRECRAWL_BASE_URL}/scrape",
            headers=headers,
            json=data,
            timeout=30  # Request timeout
        )
        
        if response.status_code != 200:
            logger.error(f"Error scraping {url}: {response.status_code} - {response.text}")
            raise Exception(f"Firecrawl API error: {response.status_code}")
        
        result = response.json()
        
        # Check if the response contains data
        if "data" in result:
            return result["data"]
        else:
            return result
    
    except requests.exceptions.Timeout:
        logger.error(f"Timeout scraping {url}")
        raise Exception(f"Timeout scraping {url}")
    except Exception as e:
        logger.error(f"Error in scrape_website for {url}: {str(e)}")
        raise

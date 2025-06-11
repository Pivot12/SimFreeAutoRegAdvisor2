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
    
    # Check if API key is configured
    if not api_key or api_key == "YOUR_FIRECRAWL_API_KEY":
        logger.error("Firecrawl API key not configured")
        # Return mock data for demonstration
        return create_mock_regulation_data(query)
    
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
            
            # For cloud deployment, skip crawling to avoid timeouts
            # if CRAWL_DEPTH > 0 and len(all_regulation_data) < 3:
            #     crawl_data, urls, titles = crawl_website(website, search_terms, api_key, max_results=MAX_RESULTS_PER_SITE)
            #     all_regulation_data.extend(crawl_data)
            #     all_source_urls.extend(urls)
            #     all_source_titles.extend(titles)
            
        except Exception as e:
            logger.error(f"Error fetching data from {website}: {str(e)}")
            continue
    
    # If we didn't find any data, provide mock data for demonstration
    if not all_regulation_data:
        logger.warning("No regulation data found from any website, providing mock data")
        return create_mock_regulation_data(query)
    
    logger.info(f"Successfully fetched regulation data from {len(all_source_urls)} sources")
    return all_regulation_data, all_source_urls, all_source_titles

def create_mock_regulation_data(query: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Create mock regulation data for demonstration purposes when API is not available.
    
    Args:
        query: User query about automotive regulations
    
    Returns:
        Tuple containing mock regulation data, URLs, and titles
    """
    logger.info("Creating mock regulation data for demonstration")
    
    # Analyze query to provide relevant mock data
    query_lower = query.lower()
    
    mock_data = []
    mock_urls = []
    mock_titles = []
    
    if "emissions" in query_lower:
        mock_data.append("""
# Emissions Standards Overview

## European Union
The European Union has implemented the Euro 6 emissions standards for passenger vehicles, which came into effect in September 2014. These standards set strict limits on nitrogen oxides (NOx), particulate matter (PM), carbon monoxide (CO), and hydrocarbons (HC).

Key requirements:
- NOx limit: 80 mg/km for diesel vehicles
- PM limit: 5 mg/km for diesel vehicles
- Real-world driving emissions (RDE) testing introduced

## United States
The U.S. Environmental Protection Agency (EPA) has established Tier 3 emissions standards, which are being phased in from 2017 through 2025. These standards reduce both tailpipe and evaporative emissions.

## China
China has implemented China 6 emissions standards, which are among the most stringent globally and comparable to Euro 6 standards.
        """)
        mock_urls.append("https://www.epa.gov/regulations-emissions-vehicles-and-engines")
        mock_titles.append("EPA Vehicle Emissions Standards")
        
        mock_data.append("""
# Global Emissions Regulations Comparison

The automotive industry faces increasingly stringent emissions regulations worldwide. Major markets have implemented comprehensive standards:

- **Euro 7**: Expected implementation by 2025 with further reduced limits
- **California CARB**: Advanced Clean Cars II program
- **Japan**: Post New Long-term regulations
- **India**: BS VI standards equivalent to Euro 6

These regulations drive technological innovation in catalytic converters, particulate filters, and hybrid/electric powertrains.
        """)
        mock_urls.append("https://unece.org/transport/vehicle-regulations")
        mock_titles.append("UNECE Vehicle Regulations")
        
    elif "safety" in query_lower:
        mock_data.append("""
# Vehicle Safety Requirements

## Global Safety Standards
The United Nations Economic Commission for Europe (UNECE) has established various safety regulations under the 1958 Agreement covering:

- Braking systems (Regulation No. 13)
- Lighting and light-signalling devices (Regulations No. 48, 7, 87, etc.)
- Passive safety (crash performance) (Regulations No. 94, 95, 16, etc.)
- Active safety systems (Regulations No. 131, 152, etc.)

## Advanced Safety Features
Modern vehicles must be equipped with:
- Emergency braking systems
- Lane-keeping assistance
- Driver drowsiness detection
- Blind spot monitoring
        """)
        mock_urls.append("https://www.nhtsa.gov/laws-regulations")
        mock_titles.append("NHTSA Safety Standards")
        
    elif "homologation" in query_lower or "type approval" in query_lower:
        mock_data.append("""
# Vehicle Homologation Process

## What is Homologation?
Homologation is the process of certifying that a vehicle meets the regulatory requirements of a specific market. It involves comprehensive testing and documentation.

## EU Type Approval Process
In the European Union, vehicle type approval is governed by Regulation (EU) 2018/858:

1. **Whole Vehicle Type Approval (WVTA)**: Covers the complete vehicle
2. **Step-by-step approval**: Individual systems approved separately
3. **Mixed procedure**: Combination of both approaches

## Key Documentation
- Certificate of Conformity (CoC)
- Technical documentation package
- Test reports from accredited laboratories
- Declaration of conformity

## Global Recognition
Under the UNECE 1958 Agreement, type approvals can be mutually recognized between contracting parties.
        """)
        mock_urls.append("https://ec.europa.eu/growth/sectors/automotive-industry_en")
        mock_titles.append("EU Type Approval System")
        
    else:
        # General automotive regulations information
        mock_data.append("""
# Automotive Regulatory Framework

The automotive industry is subject to extensive regulations covering:

## Safety Regulations
- Crash safety standards
- Electronic stability control
- Advanced driver assistance systems (ADAS)
- Lighting and visibility requirements

## Environmental Standards
- Emissions limits for pollutants
- Fuel economy standards
- End-of-life vehicle recycling
- Noise regulations

## Market Access Requirements
- Type approval and homologation
- Conformity of production
- Market surveillance
- Recall procedures
        """)
        mock_urls.append("https://www.acea.auto/publication/automotive-regulatory-guide-2023/")
        mock_titles.append("ACEA Automotive Regulatory Guide")
        
        mock_data.append("""
# Regional Regulatory Differences

## Harmonization Efforts
While global harmonization through UNECE regulations has made progress, significant regional differences remain:

- **Testing procedures**: Different test cycles and conditions
- **Implementation timelines**: Varying phase-in schedules
- **Enforcement mechanisms**: Different approaches to compliance
- **Market-specific requirements**: Unique regional needs

## Future Trends
- Increased focus on cybersecurity
- Autonomous vehicle regulations
- Electric vehicle infrastructure
- Connected vehicle standards
        """)
        mock_urls.append("https://unece.org/transport/vehicle-regulations")
        mock_titles.append("UNECE Global Vehicle Regulations")
    
    return mock_data, mock_urls, mock_titles

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
        "formats": ["markdown"],
        "withMetadata": True,
        "timeout": 30  # Add timeout to prevent hanging
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
            return {}
        
        result = response.json()
        
        # Check if the response contains data
        if "data" in result:
            return result["data"]
        else:
            return result
    
    except requests.exceptions.Timeout:
        logger.error(f"Timeout scraping {url}")
        return {}
    except Exception as e:
        logger.error(f"Error in scrape_website for {url}: {str(e)}")
        return {}

def crawl_website(
    url: str, 
    search_terms: List[str], 
    api_key: str, 
    max_results: int = 3
) -> Tuple[List[str], List[str], List[str]]:
    """
    Crawl a website to find relevant regulation content using Firecrawl API.
    This function is currently disabled for cloud deployment to avoid timeouts.
    
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
    # Disable crawling for now to avoid timeouts in cloud deployment
    logger.info(f"Crawling disabled for cloud deployment: {url}")
    return [], [], []

def extract_relevant_content(content: str, search_terms: List[str]) -> str:
    """
    Extract relevant parts of the content based on search terms.
    
    Args:
        content: The full content from a webpage
        search_terms: List of search terms to find relevant content
    
    Returns:
        Extracted relevant content as a string
    """
    if not content:
        return ""
    
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
    
    # If still no relevant content found, return first few paragraphs as fallback
    if not relevant_paragraphs and paragraphs:
        relevant_paragraphs = paragraphs[:3]  # Return first 3 paragraphs
    
    # Join the relevant paragraphs into a single string
    if relevant_paragraphs:
        return '\n\n'.join(relevant_paragraphs)
    
    # If we couldn't find anything relevant, return an empty string
    return ""

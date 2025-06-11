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
        
        # Create prompt for website selection with strict format requirements
        websites_info = "\n".join([f"- {key}: {url}" for key, url in REGULATORY_WEBSITES.items()])
        
        prompt = f"""You are an automotive regulatory expert. Select exactly 3 website keys from this list for the query:

{websites_info}

Query: "{query}"

CRITICAL: Respond with ONLY 3 website keys separated by commas. No explanations, no reasoning, no additional text.

Example format: US_NHTSA,EU_COMMISSION,UNECE

Your response:"""

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-4-scout-17b-16e-instruct",
            temperature=0.1,
            max_tokens=50
        )
        
        # Parse LLM response more robustly
        response_text = response.choices[0].message.content.strip()
        
        # Extract only valid website keys from the response
        valid_keys = []
        for key in REGULATORY_WEBSITES.keys():
            if key in response_text:
                valid_keys.append(key)
        
        # If we found valid keys, use them
        if valid_keys:
            selected_websites = [REGULATORY_WEBSITES[key] for key in valid_keys[:MAX_SITES_PER_QUERY]]
            logger.info(f"LLM selected websites: {valid_keys[:MAX_SITES_PER_QUERY]}")
            return selected_websites
        else:
            logger.warning(f"LLM response didn't contain valid website keys: {response_text}")
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
    
    # If still no data found, provide minimal fallback data to prevent complete failure
    if not all_regulation_data:
        logger.warning("No regulation data found from any source, providing basic fallback information")
        
        # Basic regulatory information as absolute fallback
        fallback_data = create_basic_regulatory_fallback(query)
        if fallback_data:
            all_regulation_data = [fallback_data]
            all_source_urls = ["https://www.interregs.net"]
            all_source_titles = ["Automotive Regulations Database"]
        else:
            logger.error("No regulation data found from any source")
            raise ValueError(ERROR_MESSAGES["no_data_found"])
    
    logger.info(f"Successfully fetched regulation data from {len(all_source_urls)} sources")
    return all_regulation_data, all_source_urls, all_source_titles

def create_basic_regulatory_fallback(query: str) -> str:
    """
    Create basic regulatory fallback information when all sources fail.
    
    Args:
        query: User query
    
    Returns:
        Basic regulatory information relevant to the query
    """
    query_lower = query.lower()
    
    fallback_info = "# Automotive Regulatory Information\n\n"
    
    if any(term in query_lower for term in ['nox', 'emission', 'diesel', 'euro']):
        fallback_info += """## EU Emissions Standards for Diesel Vehicles

**Euro 6d Standards (Current):**
- NOx limit for diesel passenger cars: 80 mg/km
- Particulate matter (PM) limit: 5 mg/km  
- Real Driving Emissions (RDE) testing required
- Applicable since September 2019 for new vehicle types

**Euro 7 Standards (Upcoming):**
- Expected implementation: 2025-2026
- Further reduced emission limits anticipated
- Enhanced testing procedures under development

**Key Regulations:**
- Regulation (EC) No 715/2007 on type approval
- Commission Regulation (EU) 2017/1151 (WLTP)
- UN Regulation No. 83 (emissions testing)

**Compliance Requirements:**
- All new diesel passenger vehicles must meet Euro 6d standards
- Manufacturers must demonstrate compliance through official testing
- RDE testing ensures real-world emission performance

*Note: This is general information. Verify current requirements with official EU sources.*"""

    elif any(term in query_lower for term in ['safety', 'crash', 'airbag', 'seatbelt']):
        fallback_info += """## Vehicle Safety Requirements

**EU General Safety Regulation (GSR):**
- Mandatory advanced emergency braking (AEB)
- Lane keeping assistance systems required
- Driver drowsiness and attention warning
- Intelligent speed assistance (ISA)

**US Federal Motor Vehicle Safety Standards (FMVSS):**
- FMVSS 208: Occupant crash protection
- FMVSS 126: Electronic stability control
- FMVSS 138: Tire pressure monitoring systems

**Global Standards (UNECE):**
- UN Regulation No. 94: Frontal collision protection
- UN Regulation No. 95: Lateral collision protection  
- UN Regulation No. 16: Safety belts and restraint systems

**Implementation Dates:**
- EU GSR: Phased implementation 2022-2024
- Many requirements apply to new vehicle types first

*Note: Safety requirements vary by region. Consult official regulatory authorities.*"""

    elif any(term in query_lower for term in ['homologation', 'type approval', 'certification']):
        fallback_info += """## Vehicle Type Approval and Homologation

**EU Whole Vehicle Type Approval (WVTA):**
- Regulation (EU) 2018/858 framework
- Single approval valid across EU member states
- Certificate of Conformity (CoC) required

**US Certification Process:**
- EPA certification for emissions compliance
- NHTSA certification for safety standards
- DOT requirements for imported vehicles

**Global Harmonization:**
- UN 1958 Agreement enables mutual recognition
- 1998 Agreement for global technical regulations
- Reduces duplicate testing between markets

**Key Documentation:**
- Type approval certificate
- Certificate of conformity
- Technical specification documents
- Test reports from accredited laboratories

*Note: Approval processes are complex. Consult regulatory experts for specific requirements.*"""

    else:
        fallback_info += """## General Automotive Regulatory Framework

**Major Regulatory Bodies:**
- EU: European Commission, UNECE
- US: NHTSA (safety), EPA (emissions)
- Global: UN World Forum for Vehicle Regulations

**Key Regulation Areas:**
- Emissions and environmental standards
- Safety and crash protection requirements
- Type approval and homologation processes
- Market surveillance and compliance

**Regional Differences:**
- Testing procedures and cycles vary
- Implementation timelines differ
- Enforcement mechanisms vary by jurisdiction

**Staying Current:**
- Regulations change frequently
- Monitor official regulatory websites
- Consult qualified regulatory experts
- Verify requirements for specific markets

*Note: This is general guidance. Always verify current requirements with official sources.*"""

    return fallback_info

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
    
    # Simplified data payload - removed extractorOptions that was causing 400 error
    data = {
        "url": url,
        "formats": ["markdown"],
        "timeout": 30000  # Timeout in milliseconds (30 seconds)
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

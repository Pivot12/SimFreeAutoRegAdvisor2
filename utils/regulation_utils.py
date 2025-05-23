import logging
import re
from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

def extract_relevant_regulations(query: str, regulation_data: List[str]) -> List[str]:
    """
    Extract and rank relevant regulations from the collected regulation data.
    
    Args:
        query: The user's query about automotive regulations
        regulation_data: List of extracted regulation content from various sources
    
    Returns:
        List of most relevant regulation data snippets
    """
    logger.info("Extracting relevant regulations from collected data")
    
    if not regulation_data:
        logger.warning("No regulation data provided for extraction")
        return []
    
    try:
        # Create a TF-IDF vectorizer
        vectorizer = TfidfVectorizer(stop_words='english', max_df=0.85, min_df=1)
        
        # Combine query and regulation data for vectorization
        all_texts = [query] + regulation_data
        
        # Fit and transform the texts
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # Calculate cosine similarity between query and each regulation snippet
        cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        
        # Rank regulation snippets by relevance
        ranked_indices = np.argsort(cosine_similarities)[::-1]
        
        # Select the most relevant regulations
        relevant_regulations = [regulation_data[i] for i in ranked_indices]
        
        logger.info(f"Successfully extracted {len(relevant_regulations)} relevant regulations")
        return relevant_regulations
    
    except Exception as e:
        logger.error(f"Error in extract_relevant_regulations: {str(e)}")
        # Return original data if extraction fails
        return regulation_data

def extract_regulation_metadata(text: str) -> Dict[str, Any]:
    """
    Extract metadata from regulation text such as dates, regulation numbers, etc.
    
    Args:
        text: Regulation text content
    
    Returns:
        Dictionary containing extracted metadata
    """
    metadata = {
        "regulation_numbers": [],
        "dates": [],
        "regions": [],
        "categories": []
    }
    
    # Extract regulation numbers (e.g., ECE-R100, 2018/858)
    reg_numbers = re.findall(r'[A-Z]{1,5}[-/]?[A-Z]?\d{1,4}|Regulation\s+(?:No\.\s+)?(\d+)', text)
    metadata["regulation_numbers"] = [num for num in reg_numbers if num]
    
    # Extract dates (basic implementation, can be enhanced)
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY, MM/DD/YYYY
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',    # YYYY/MM/DD
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}'  # Month DD, YYYY
    ]
    
    for pattern in date_patterns:
        dates = re.findall(pattern, text)
        metadata["dates"].extend(dates)
    
    # Extract regions
    region_patterns = {
        "European Union": [r'EU', r'European Union', r'Europe', r'UNECE', r'ECE'],
        "United States": [r'US', r'USA', r'United States', r'FMVSS', r'NHTSA', r'EPA'],
        "China": [r'China', r'Chinese'],
        "Japan": [r'Japan', r'Japanese', r'TRIAS'],
        "Global": [r'Global', r'International', r'Worldwide', r'UN'],
        "United Kingdom": [r'UK', r'United Kingdom', r'Britain', r'British'],
        "India": [r'India', r'Indian', r'ARAI'],
        "Brazil": [r'Brazil', r'Brazilian'],
        "Russia": [r'Russia', r'Russian'],
        "Australia": [r'Australia', r'Australian']
    }
    
    for region, patterns in region_patterns.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', text, re.IGNORECASE):
                if region not in metadata["regions"]:
                    metadata["regions"].append(region)
    
    # Extract categories
    category_patterns = {
        "Emissions": [r'emission', r'exhaust', r'CO2', r'carbon dioxide', r'pollutant'],
        "Safety": [r'safety', r'crash', r'collision', r'protection', r'restraint'],
        "Homologation": [r'homologation', r'type approval', r'certification'],
        "Electric Vehicles": [r'electric', r'EV', r'battery', r'charging'],
        "Autonomous": [r'autonomous', r'self-driving', r'automated', r'driver assistance'],
        "Noise": [r'noise', r'sound', r'acoustic'],
        "Lighting": [r'light', r'lamp', r'illumination'],
        "Fuel Efficiency": [r'fuel', r'consumption', r'efficiency', r'economy'],
        "Tires": [r'tyre', r'tire', r'wheel']
    }
    
    for category, patterns in category_patterns.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'[a-z]*\b', text, re.IGNORECASE):
                if category not in metadata["categories"]:
                    metadata["categories"].append(category)
    
    return metadata

def format_regulation_response(query: str, relevant_regulations: List[str], source_urls: List[str]) -> str:
    """
    Format the regulation data into a structured response.
    
    Args:
        query: The user's query about automotive regulations
        relevant_regulations: List of relevant regulation content
        source_urls: List of source URLs
    
    Returns:
        Formatted response string
    """
    # Extract key regions and categories from the query and regulations
    query_metadata = extract_regulation_metadata(query)
    regulation_metadata = [extract_regulation_metadata(reg) for reg in relevant_regulations]
    
    # Combine metadata from all regulations
    combined_metadata = {
        "regulation_numbers": [],
        "dates": [],
        "regions": [],
        "categories": []
    }
    
    for metadata in regulation_metadata:
        for key, values in metadata.items():
            combined_metadata[key].extend(values)
    
    # Remove duplicates
    for key in combined_metadata:
        combined_metadata[key] = list(set(combined_metadata[key]))
    
    # Prioritize regions and categories mentioned in the query
    priority_regions = [r for r in combined_metadata["regions"] if any(r.lower() in qr.lower() for qr in query_metadata["regions"])] if query_metadata["regions"] else combined_metadata["regions"]
    priority_categories = [c for c in combined_metadata["categories"] if any(c.lower() in qc.lower() for qc in query_metadata["categories"])] if query_metadata["categories"] else combined_metadata["categories"]
    
    # Build the response
    response = f"# Automotive Regulation Information\n\n"
    
    # Add region information if available
    if priority_regions:
        response += "## Applicable Regions\n"
        for region in priority_regions:
            response += f"- {region}\n"
        response += "\n"
    
    # Add category information if available
    if priority_categories:
        response += "## Regulation Categories\n"
        for category in priority_categories:
            response += f"- {category}\n"
        response += "\n"
    
    # Add regulation numbers if available
    if combined_metadata["regulation_numbers"]:
        response += "## Relevant Regulation Numbers\n"
        for number in combined_metadata["regulation_numbers"]:
            response += f"- {number}\n"
        response += "\n"
    
    # Add main content from relevant regulations
    response += "## Detailed Information\n\n"
    for i, regulation in enumerate(relevant_regulations[:3]):  # Limit to top 3 most relevant
        response += f"### Source {i+1}\n"
        response += f"{regulation}\n\n"
    
    # Add source information
    response += "## Sources\n"
    for i, url in enumerate(source_urls[:3]):  # Limit to top 3 sources
        response += f"- [Source {i+1}]({url})\n"
    
    return response

def identify_regulation_gaps(query: str, regulation_data: List[str]) -> List[str]:
    """
    Identify gaps in regulation data that might require additional searches.
    
    Args:
        query: The user's query about automotive regulations
        regulation_data: List of extracted regulation content
    
    Returns:
        List of suggested search terms to fill gaps
    """
    # Extract key regions, categories, and regulation numbers from the query
    query_metadata = extract_regulation_metadata(query)
    
    # Extract metadata from all available regulation data
    regulation_metadata = [extract_regulation_metadata(reg) for reg in regulation_data]
    
    # Combine metadata from all regulations
    combined_metadata = {
        "regulation_numbers": [],
        "regions": [],
        "categories": []
    }
    
    for metadata in regulation_metadata:
        for key in combined_metadata:
            combined_metadata[key].extend(metadata[key])
    
    # Remove duplicates
    for key in combined_metadata:
        combined_metadata[key] = list(set(combined_metadata[key]))
    
    # Identify missing regions
    missing_regions = [r for r in query_metadata["regions"] if r not in combined_metadata["regions"]]
    
    # Identify missing categories
    missing_categories = [c for c in query_metadata["categories"] if c not in combined_metadata["categories"]]
    
    # Identify missing regulation numbers
    missing_regulations = [r for r in query_metadata["regulation_numbers"] if r not in combined_metadata["regulation_numbers"]]
    
    # Generate suggested search terms
    suggested_searches = []
    
    for region in missing_regions:
        for category in query_metadata["categories"]:
            suggested_searches.append(f"{region} {category} regulations")
    
    for category in missing_categories:
        suggested_searches.append(f"{category} regulations {' '.join(query_metadata['regions'])}")
    
    for reg in missing_regulations:
        suggested_searches.append(f"Regulation {reg} automotive")
    
    return suggested_searches

def extract_regulation_requirements(text: str) -> List[Dict[str, Any]]:
    """
    Extract specific requirements from regulation text.
    
    Args:
        text: Regulation text content
    
    Returns:
        List of dictionaries containing requirement information
    """
    requirements = []
    
    # Find paragraphs that likely contain requirements
    requirement_indicators = [
        r'shall',
        r'must',
        r'required',
        r'mandatory',
        r'minimum',
        r'maximum',
        r'limit',
        r'not exceed',
        r'comply with',
        r'requirement'
    ]
    
    # Split text into paragraphs
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        # Check if paragraph contains requirement indicators
        if any(re.search(r'\b' + indicator + r'\b', paragraph, re.IGNORECASE) for indicator in requirement_indicators):
            # Extract metadata from the requirement
            metadata = extract_regulation_metadata(paragraph)
            
            # Determine requirement type
            req_type = "General"
            for category in metadata["categories"]:
                req_type = category
                break
            
            # Create requirement entry
            requirement = {
                "text": paragraph,
                "type": req_type,
                "regions": metadata["regions"],
                "regulation_numbers": metadata["regulation_numbers"]
            }
            
            requirements.append(requirement)
    
    return requirements

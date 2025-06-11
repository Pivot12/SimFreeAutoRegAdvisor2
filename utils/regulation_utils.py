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
    Enhanced version with better content scoring and filtering.
    
    Args:
        query: The user's query about automotive regulations
        regulation_data: List of extracted regulation content from various sources
    
    Returns:
        List of most relevant regulation data snippets, ranked by relevance
    """
    logger.info("Extracting relevant regulations from collected data")
    
    if not regulation_data:
        logger.warning("No regulation data provided for extraction")
        return []
    
    try:
        # Enhanced content scoring and ranking
        scored_regulations = []
        
        for i, regulation_text in enumerate(regulation_data):
            if not regulation_text or len(regulation_text.strip()) < 50:
                continue
                
            # Calculate relevance score using multiple factors
            relevance_score = calculate_comprehensive_relevance_score(query, regulation_text)
            
            # Only include regulations with decent relevance scores
            if relevance_score > 0.1:
                scored_regulations.append((relevance_score, regulation_text, i))
        
        # Sort by relevance score (highest first)
        scored_regulations.sort(key=lambda x: x[0], reverse=True)
        
        # Extract the regulation texts, keeping original order information
        relevant_regulations = [reg_text for score, reg_text, idx in scored_regulations]
        
        # Limit to top 5 most relevant regulations to prevent token overflow
        relevant_regulations = relevant_regulations[:5]
        
        logger.info(f"Successfully extracted {len(relevant_regulations)} relevant regulations")
        return relevant_regulations
    
    except Exception as e:
        logger.error(f"Error in extract_relevant_regulations: {str(e)}")
        # Return original data if extraction fails
        return regulation_data[:3]  # Limit to prevent token overflow

def calculate_comprehensive_relevance_score(query: str, regulation_text: str) -> float:
    """
    Calculate a comprehensive relevance score using multiple factors.
    
    Args:
        query: User query
        regulation_text: Regulation content to score
    
    Returns:
        Relevance score (0.0 to 1.0+)
    """
    try:
        # Initialize score
        total_score = 0.0
        
        # 1. TF-IDF Cosine Similarity (base score)
        vectorizer = TfidfVectorizer(stop_words='english', max_df=0.85, min_df=1, lowercase=True)
        try:
            tfidf_matrix = vectorizer.fit_transform([query, regulation_text])
            cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            total_score += cosine_sim * 1.0  # Weight: 1.0
        except:
            cosine_sim = 0.0
        
        # 2. Keyword overlap score
        query_words = set(query.lower().split())
        reg_words = set(regulation_text.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
        query_words -= stop_words
        reg_words -= stop_words
        
        if query_words:
            keyword_overlap = len(query_words.intersection(reg_words)) / len(query_words)
            total_score += keyword_overlap * 0.5  # Weight: 0.5
        
        # 3. Regulatory specificity score
        regulatory_indicators = [
            'regulation', 'directive', 'standard', 'requirement', 'shall', 'must',
            'compliance', 'certification', 'approval', 'limit', 'maximum', 'minimum',
            'article', 'section', 'paragraph', 'amendment', 'annex', 'schedule'
        ]
        
        reg_indicator_count = sum(1 for indicator in regulatory_indicators if indicator in regulation_text.lower())
        regulatory_score = min(reg_indicator_count / 10.0, 0.3)  # Cap at 0.3
        total_score += regulatory_score
        
        # 4. Specific regulation number bonus
        regulation_patterns = [
            r'regulation\s+(?:no\.?\s*)?(\d+)',
            r'directive\s+(\d+/\d+)',
            r'ece[-\s]r(\d+)',
            r'fmvss\s+(\d+)',
            r'iso\s+(\d+)',
            r'sae\s+j(\d+)'
        ]
        
        for pattern in regulation_patterns:
            if re.search(pattern, regulation_text.lower()):
                total_score += 0.2
                break
        
        # 5. Numerical data bonus (limits, dates, specific values)
        numerical_patterns = [
            r'\d+(?:\.\d+)?\s*(?:mg/km|g/test|dB|%|ppm|bar|kPa|mph|km/h)',  # Technical limits
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # Dates
            r'[€$£¥]\s*\d+',  # Monetary amounts
            r'\d+\s*(?:years?|months?|days?)'  # Time periods
        ]
        
        numerical_matches = sum(1 for pattern in numerical_patterns if re.search(pattern, regulation_text))
        if numerical_matches > 0:
            total_score += min(numerical_matches * 0.1, 0.2)  # Cap at 0.2
        
        # 6. Query-specific terms bonus
        query_lower = query.lower()
        specific_terms = {
            'emissions': ['emission', 'exhaust', 'co2', 'nox', 'pollutant'],
            'safety': ['safety', 'crash', 'protection', 'airbag', 'seatbelt'],
            'fuel': ['fuel', 'gasoline', 'diesel', 'consumption', 'efficiency'],
            'electric': ['electric', 'battery', 'charging', 'ev', 'hybrid'],
            'autonomous': ['autonomous', 'automated', 'driver assistance', 'adas']
        }
        
        for category, terms in specific_terms.items():
            if category in query_lower:
                category_score = sum(0.05 for term in terms if term in regulation_text.lower())
                total_score += min(category_score, 0.15)  # Cap at 0.15 per category
        
        # 7. Content length penalty (avoid very short snippets)
        if len(regulation_text.strip()) < 200:
            total_score *= 0.7  # Penalty for short content
        elif len(regulation_text.strip()) < 100:
            total_score *= 0.4  # Heavier penalty for very short content
        
        return min(total_score, 2.0)  # Cap maximum score at 2.0
        
    except Exception as e:
        logger.error(f"Error calculating relevance score: {str(e)}")
        return 0.1  # Default low score

def extract_regulation_metadata(text: str) -> Dict[str, Any]:
    """
    Extract metadata from regulation text such as dates, regulation numbers, etc.
    Enhanced version with better pattern matching.
    
    Args:
        text: Regulation text content
    
    Returns:
        Dictionary containing extracted metadata
    """
    metadata = {
        "regulation_numbers": [],
        "dates": [],
        "regions": [],
        "categories": [],
        "limits": [],
        "compliance_dates": []
    }
    
    # Enhanced regulation number extraction
    reg_patterns = [
        r'(?:regulation|directive|standard)\s+(?:no\.?\s*)?(\d+(?:/\d+)?(?:[A-Z]+)?)',
        r'(?:ECE[-\s]R|FMVSS|ISO|SAE[-\s]J|ASTM)\s*(\d+)',
        r'(?:EU|EC)\s*(\d+/\d+)',
        r'(?:UNECE|UN)\s*(?:regulation\s*)?(\d+)',
        r'(?:BS|DIN|JIS)\s*(\d+)',
        r'(?:CFR)\s*(\d+\.\d+)'
    ]
    
    for pattern in reg_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        metadata["regulation_numbers"].extend(matches)
    
    # Enhanced date extraction
    date_patterns = [
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
        r'(?:from|by|before|after|until)\s+(\d{4})',
        r'(?:effective|applicable|mandatory)\s+(?:from\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
    ]
    
    for pattern in date_patterns:
        dates = re.findall(pattern, text, re.IGNORECASE)
        metadata["dates"].extend(dates)
    
    # Enhanced region extraction
    region_patterns = {
        "European Union": [r'\bEU\b', r'European\s+Union', r'Europe(?:an)?', r'UNECE', r'ECE', r'Brussels'],
        "United States": [r'\bUS\b', r'\bUSA\b', r'United\s+States', r'America(?:n)?', r'FMVSS', r'NHTSA', r'EPA', r'CFR'],
        "China": [r'China', r'Chinese', r'GB\s+\d+', r'CCC'],
        "Japan": [r'Japan(?:ese)?', r'JIS', r'TRIAS', r'MLIT'],
        "United Kingdom": [r'\bUK\b', r'United\s+Kingdom', r'Britain', r'British', r'BS\s+\d+'],
        "India": [r'India(?:n)?', r'BIS', r'ARAI', r'CMVR'],
        "Australia": [r'Australia(?:n)?', r'ADR\s+\d+'],
        "Brazil": [r'Brazil(?:ian)?', r'CONTRAN', r'INMETRO'],
        "Canada": [r'Canada(?:ian)?', r'CMVSS', r'Transport\s+Canada'],
        "Global": [r'Global', r'International', r'Worldwide', r'UN(?:\s|$)', r'ISO']
    }
    
    for region, patterns in region_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if region not in metadata["regions"]:
                    metadata["regions"].append(region)
    
    # Enhanced category extraction
    category_patterns = {
        "Emissions": [r'emission(?:s)?', r'exhaust', r'CO2?', r'carbon\s+(?:dioxide|monoxide)', r'pollutant', r'NOx?', r'particulate'],
        "Safety": [r'safety', r'crash', r'collision', r'protection', r'restraint', r'airbag', r'seatbelt', r'brake'],
        "Homologation": [r'homologation', r'type\s+approval', r'certification', r'conformity', r'approval'],
        "Electric Vehicles": [r'electric(?:\s+vehicle)?', r'\bEV\b', r'battery', r'charging', r'hybrid', r'plug-?in'],
        "Autonomous": [r'autonomous', r'self-driving', r'automated', r'driver\s+assistance', r'ADAS'],
        "Noise": [r'noise', r'sound', r'acoustic', r'decibel', r'\bdB\b'],
        "Lighting": [r'light(?:ing)?', r'lamp', r'illumination', r'headlight', r'LED'],
        "Fuel Efficiency": [r'fuel\s+(?:efficiency|economy|consumption)', r'mpg', r'l/100km', r'efficiency'],
        "Tires": [r'tyre', r'tire', r'wheel', r'tread'],
        "Construction": [r'construction', r'design', r'structure', r'material'],
        "Testing": [r'test(?:ing)?', r'procedure', r'method', r'protocol', r'measurement']
    }
    
    for category, patterns in category_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if category not in metadata["categories"]:
                    metadata["categories"].append(category)
    
    # Extract technical limits and values
    limit_patterns = [
        r'\d+(?:\.\d+)?\s*(?:mg/km|g/test|dB|%|ppm|bar|kPa|mph|km/h|mm|cm|kg|tonnes?)',
        r'(?:maximum|minimum|limit(?:ed)?|not\s+exceed(?:ing)?|less\s+than|greater\s+than)\s+\d+(?:\.\d+)?',
        r'\d+(?:\.\d+)?\s*(?:degrees?|°[CF]?)',
        r'[€$£¥]\s*\d+(?:,\d{3})*(?:\.\d{2})?'
    ]
    
    for pattern in limit_patterns:
        limits = re.findall(pattern, text, re.IGNORECASE)
        metadata["limits"].extend(limits)
    
    # Extract compliance dates
    compliance_patterns = [
        r'(?:effective|applicable|mandatory|enforced?)\s+(?:from|by|on|after)\s+([^,\n.]{10,30})',
        r'(?:deadline|due\s+date|compliance\s+date)(?:\s*:)?\s*([^,\n.]{10,30})',
        r'(?:phase[-\s]in|implementation)\s+(?:period|date|schedule)(?:\s*:)?\s*([^,\n.]{10,50})'
    ]
    
    for pattern in compliance_patterns:
        comp_dates = re.findall(pattern, text, re.IGNORECASE)
        metadata["compliance_dates"].extend(comp_dates)
    
    # Remove duplicates and clean up
    for key in metadata:
        if isinstance(metadata[key], list):
            metadata[key] = list(set(metadata[key]))  # Remove duplicates
            metadata[key] = [item.strip() for item in metadata[key] if item.strip()]  # Remove empty strings
    
    return metadata

def format_regulation_response(query: str, relevant_regulations: List[str], source_urls: List[str]) -> str:
    """
    Format the regulation data into a structured response.
    Enhanced version with better organization.
    
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
        "categories": [],
        "limits": [],
        "compliance_dates": []
    }
    
    for metadata in regulation_metadata:
        for key, values in metadata.items():
            combined_metadata[key].extend(values)
    
    # Remove duplicates
    for key in combined_metadata:
        combined_metadata[key] = list(set(combined_metadata[key]))
    
    # Prioritize regions and categories mentioned in the query
    priority_regions = [r for r in combined_metadata["regions"] if any(r.lower() in qr.lower() for qr in query_metadata["regions"])] if query_metadata["regions"] else combined_metadata["regions"][:3]
    priority_categories = [c for c in combined_metadata["categories"] if any(c.lower() in qc.lower() for qc in query_metadata["categories"])] if query_metadata["categories"] else combined_metadata["categories"][:3]
    
    # Build the response
    response = f"# Automotive Regulation Information\n\n"
    
    # Add quick summary if we have good metadata
    if priority_regions or priority_categories or combined_metadata["regulation_numbers"]:
        response += "## Quick Summary\n"
        
        if priority_regions:
            response += f"**Applicable Regions:** {', '.join(priority_regions)}\n"
        
        if priority_categories:
            response += f"**Categories:** {', '.join(priority_categories)}\n"
        
        if combined_metadata["regulation_numbers"]:
            response += f"**Key Regulations:** {', '.join(combined_metadata['regulation_numbers'][:5])}\n"
        
        response += "\n"
    
    # Add main content from relevant regulations
    response += "## Detailed Information\n\n"
    for i, regulation in enumerate(relevant_regulations[:3]):  # Limit to top 3 most relevant
        response += f"### Source {i+1}\n"
        response += f"{regulation}\n\n"
    
    # Add technical limits if available
    if combined_metadata["limits"]:
        response += "## Key Technical Limits\n"
        for limit in combined_metadata["limits"][:5]:  # Top 5 limits
            response += f"- {limit}\n"
        response += "\n"
    
    # Add compliance information if available
    if combined_metadata["compliance_dates"]:
        response += "## Compliance Information\n"
        for comp_date in combined_metadata["compliance_dates"][:3]:  # Top 3 compliance dates
            response += f"- {comp_date}\n"
        response += "\n"
    
    # Add source information
    response += "## Sources\n"
    for i, url in enumerate(source_urls[:3]):  # Limit to top 3 sources
        response += f"- [Source {i+1}]({url})\n"
    
    return response

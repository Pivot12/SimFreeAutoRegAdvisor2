"""
Regulatory knowledge database containing mappings between automotive regulatory topics
and the specific regulations and regulatory bodies that cover them.
"""

class RegulatoryKnowledge:
    """
    Knowledge base for automotive regulations that helps map queries to specific
    regulatory documents and direct URLs.
    """
    
    def __init__(self):
        # Map of common regulatory topics to specific regulations
        self.topic_regulation_map = {
            "lighting": {
                "us": ["FMVSS 108"],
                "eu": ["ECE R48", "ECE R7", "ECE R87"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 48"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 4785"],
                "india": ["AIS-008"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20048"]
            },
            "stop lamp": {
                "us": ["FMVSS 108", "SAE J586"],
                "eu": ["ECE R7", "ECE R48"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 7"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 4785"],
                "india": ["AIS-008"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20007"]
            },
            "brake light": {
                "us": ["FMVSS 108", "SAE J586"],
                "eu": ["ECE R7", "ECE R48"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 7"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 4785"],
                "india": ["AIS-008"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20007"]
            },
            "centre high mounted stop lamp": {
                "us": ["FMVSS 108", "SAE J186"],
                "eu": ["ECE R48"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 48"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 4785"],
                "india": ["AIS-008"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20048"]
            },
            "chmsl": {  # Acronym for Centre High Mounted Stop Lamp
                "us": ["FMVSS 108", "SAE J186"],
                "eu": ["ECE R48"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 48"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 4785"],
                "india": ["AIS-008"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20048"]
            },
            "headlamp": {
                "us": ["FMVSS 108", "SAE J1383"],
                "eu": ["ECE R48", "ECE R112", "ECE R113"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 48", "UNECE Regulation 112"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 4599"],
                "india": ["AIS-008", "AIS-010"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20112"]
            },
            "turn signal": {
                "us": ["FMVSS 108", "SAE J588"],
                "eu": ["ECE R48", "ECE R6"],
                "global": ["GTR No. 6"],
                "uk": ["UNECE Regulation 48", "UNECE Regulation 6"],
                "australia": ["ADR 13"],
                "japan": ["Article 32 of the Safety Regulations"],
                "china": ["GB 17509"],
                "india": ["AIS-008", "AIS-012"],
                "canada": ["CMVSS 108"],
                "south africa": ["SANS 20006"]
            },
            "safety belt": {
                "us": ["FMVSS 209", "FMVSS 210"],
                "eu": ["ECE R16"],
                "global": ["GTR No. 7"],
                "uk": ["UNECE Regulation 16"],
                "australia": ["ADR 4", "ADR 5"],
                "japan": ["Article 22 of the Safety Regulations"],
                "china": ["GB 14166"],
                "india": ["AIS-015", "AIS-072"],
                "canada": ["CMVSS 209", "CMVSS 210"],
                "south africa": ["SANS 1080"]
            },
            "tire": {
                "us": ["FMVSS 109", "FMVSS 139"],
                "eu": ["ECE R30", "ECE R54", "ECE R117"],
                "global": ["GTR No. 16"],
                "uk": ["UNECE Regulation 30"],
                "australia": ["ADR 23"],
                "japan": ["Article 9 of the Safety Regulations"],
                "china": ["GB 9743", "GB 9744"],
                "india": ["AIS-044"],
                "canada": ["CMVSS 109", "CMVSS 119"],
                "south africa": ["SANS 20030"]
            },
            "brake system": {
                "us": ["FMVSS 105", "FMVSS 126", "FMVSS 135"],
                "eu": ["ECE R13", "ECE R13H", "ECE R90"],
                "global": ["GTR No. 8"],
                "uk": ["UNECE Regulation 13", "UNECE Regulation 13H"],
                "australia": ["ADR 31", "ADR 35"],
                "japan": ["Article 12 of the Safety Regulations"],
                "china": ["GB 12676", "GB 21670"],
                "india": ["AIS-014"],
                "canada": ["CMVSS 105", "CMVSS 135"],
                "south africa": ["SANS 20013"]
            },
            "emissions": {
                "us": ["EPA Tier 3", "CARB LEV III"],
                "eu": ["Euro 6", "Euro 7"],
                "global": ["GTR No. 15"],
                "uk": ["Euro 6", "Euro 7"],
                "australia": ["ADR 79"],
                "japan": ["WLTP", "JC08"],
                "china": ["China 6", "China 6b"],
                "india": ["BS VI"],
                "canada": ["TIER 3"],
                "south africa": ["Euro 5"]
            },
            "fuel economy": {
                "us": ["CAFE Standards", "EPA 40 CFR Part 600"],
                "eu": ["EU 2019/631"],
                "global": ["GTR No. 15"],
                "uk": ["EU 2019/631"],
                "australia": ["ADR 81"],
                "japan": ["WLTP", "JC08"],
                "china": ["CAFC"],
                "india": ["CAFE"],
                "canada": ["CAFC"],
                "south africa": ["SANS 20101"]
            }
        }
        
        # Map of regulation names to specific document URLs
        self.regulation_url_map = {
            "FMVSS 108": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-571/subpart-B/section-571.108",
            "ECE R48": "https://unece.org/transport/vehicle-regulations-wp29/standards/addenda-1958-agreement-regulations-41-60",
            "ECE R7": "https://unece.org/transport/vehicle-regulations-wp29/standards/addenda-1958-agreement-regulations-1-20",
            "GTR No. 6": "https://unece.org/transport/vehicle-regulations-wp29/standards/addenda-1998-agreement-gtrs-global-technical-regulations",
            "SAE J586": "https://www.sae.org/standards/content/j586_201903/",
            "ADR 13": "https://www.legislation.gov.au/Series/F2005L03990",
            "GB 4785": "http://www.gbstandards.org/GB_standard_english.asp?code=GB%204785",
            "AIS-008": "https://hmr.araiindia.com/Control/AIS"
        }
        
        # Map of regulatory bodies to their websites
        self.regulatory_body_url_map = {
            "NHTSA": "https://www.nhtsa.gov/laws-regulations",
            "FMVSS": "https://www.nhtsa.gov/laws-regulations/fmvss",
            "UNECE": "https://unece.org/transport/vehicle-regulations-wp29",
            "ECE": "https://unece.org/transport/vehicle-regulations-wp29",
            "EU": "https://ec.europa.eu/growth/sectors/automotive-industry/legislation_en",
            "EPA": "https://www.epa.gov/vehicle-and-engine-certification",
            "CARB": "https://ww2.arb.ca.gov/our-work/programs/advanced-clean-cars-program",
            "Transport Canada": "https://tc.canada.ca/en/road-transportation/motor-vehicle-safety",
            "CMVSS": "https://tc.canada.ca/en/road-transportation/motor-vehicle-safety/canadian-motor-vehicle-safety-standards",
            "Japan MLIT": "https://www.mlit.go.jp/en/road/",
            "China MIIT": "http://www.miit.gov.cn/",
            "India ARAI": "https://www.araiindia.com/",
            "Australia": "https://www.infrastructure.gov.au/infrastructure-transport-vehicles/vehicles/vehicle-design-regulation"
        }
        
        # Map of specific regulatory search terms to use with interregs.net
        self.interregs_search_terms = {
            "centre high mounted stop lamp": ["CHMSL", "centre high mounted stop lamp", "center high-mount stop lamp", "third brake light", "installation height stop lamp"],
            "stop lamp": ["stop lamp", "brake light", "stop light", "S3 lamp", "S4 lamp"],
            "headlamp": ["headlamp", "headlight", "low beam", "high beam"],
            "turn signal": ["turn signal", "direction indicator", "turn lamp"],
            "safety belt": ["safety belt", "seat belt", "restraint system"],
            "tire": ["tire", "tyre", "wheel"],
            "brake system": ["brake system", "braking", "ABS"],
            "emissions": ["emissions", "exhaust", "pollutant", "CO2"],
            "fuel economy": ["fuel economy", "fuel efficiency", "CO2 emissions"]
        }
    
    def get_relevant_regulations(self, query_terms, regions=None):
        """
        Get relevant regulations based on query terms and regions.
        
        Args:
            query_terms: List of terms extracted from the query
            regions: List of regions to consider, or None for all regions
            
        Returns:
            List of relevant regulation names
        """
        relevant_regulations = set()
        
        # Check each query term against our topic map
        for term in query_terms:
            term_lower = term.lower()
            
            # Check if term directly matches a topic
            for topic, region_regs in self.topic_regulation_map.items():
                if term_lower in topic or topic in term_lower:
                    # If regions specified, only include those regions
                    if regions:
                        for region in regions:
                            region_lower = region.lower()
                            if region_lower in region_regs:
                                relevant_regulations.update(region_regs[region_lower])
                    else:
                        # If no regions specified, include all regions
                        for region_regulations in region_regs.values():
                            relevant_regulations.update(region_regulations)
        
        return list(relevant_regulations)
    
    def get_regulation_urls(self, regulation_names):
        """
        Get URLs for specific regulations.
        
        Args:
            regulation_names: List of regulation names
            
        Returns:
            List of URLs for those regulations
        """
        urls = []
        
        for name in regulation_names:
            if name in self.regulation_url_map:
                urls.append(self.regulation_url_map[name])
        
        return urls
    
    def get_regulatory_body_urls(self, body_names):
        """
        Get URLs for regulatory bodies.
        
        Args:
            body_names: List of regulatory body names
            
        Returns:
            List of URLs for those bodies
        """
        urls = []
        
        for name in body_names:
            for body, url in self.regulatory_body_url_map.items():
                if name.upper() in body or body in name.upper():
                    urls.append(url)
        
        return urls
    
    def get_interregs_search_terms(self, query_terms):
        """
        Get specialized search terms for interregs.net based on query.
        
        Args:
            query_terms: List of terms from the query
            
        Returns:
            List of search terms to use with interregs.net
        """
        search_terms = []
        
        # Check if any query terms match our predefined categories
        for term in query_terms:
            term_lower = term.lower()
            
            for category, terms in self.interregs_search_terms.items():
                if term_lower in category or category in term_lower:
                    search_terms.extend(terms)
        
        # If no specific terms found, use the original query terms
        if not search_terms:
            search_terms = query_terms
            
        return search_terms

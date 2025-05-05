import os
import time
import json
import hashlib
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests
from dotenv import load_dotenv
import numpy as np
from crawler import AutoRegulationCrawler
from vector_store import VectorStore
from logger import Logger

# Load environment variables
load_dotenv()

# Model Context Protocol to ensure compatibility across versions
MCP_VERSION = "1.0"

class AutoRegulationsAgent:
    """
    AI agent for answering automotive regulation queries using RAG with direct access
    to regulatory websites and documents.
    """
    
    def __init__(self):
        # Initialize API client
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("LLAMA_MODEL", "llama3-70b-8192")
        
        # We'll implement direct API calls instead of using the Groq client
        # to avoid compatibility issues
        self.groq_client = None
        
        # Initialize components
        self.crawler = AutoRegulationCrawler()
        self.vector_store = VectorStore()
        self.logger = Logger()
        
        # Learning database
        self.feedback_threshold = 0.7  # Threshold for positive feedback to learn
        self.query_cache = {}  # Cache for frequently asked queries
        
        # Load regulatory sources
        self.reg_sources = self._load_regulatory_sources()
        
        # Track agent performance
        self.query_count = 0
        self.successful_queries = 0
        
        # Set up Model Context Protocol
        self.mcp_config = {
            "version": MCP_VERSION,
            "prompt_templates": self._load_prompt_templates(),
            "embeddings_config": {
                "dimensions": 1536,
                "normalize": True
            }
        }
    
    def _load_regulatory_sources(self) -> Dict:
        """Load the list of regulatory sources and their access patterns."""
        # This could be loaded from a file or database
        return {
            "us_nhtsa": {
                "name": "US National Highway Traffic Safety Administration",
                "base_url": "https://www.nhtsa.gov",
                "doc_patterns": ["/laws-regulations", "/fmvss", "/regulations"],
                "country": "USA"
            },
            "us_epa": {
                "name": "US Environmental Protection Agency - Vehicle Regulations",
                "base_url": "https://www.epa.gov/vehicle-and-engine-certification",
                "doc_patterns": ["/regulations-standards", "/compliance-information"],
                "country": "USA"
            },
            "eu_regulations": {
                "name": "European Union Vehicle Regulations",
                "base_url": "https://ec.europa.eu/transport/home_en",
                "doc_patterns": ["/legal-content/EN/TXT/", "/legal-content/EN/ALL/", "/transport/road-safety/"],
                "country": "EU"
            },
            "efta": {
                "name": "European Free Trade Association - Vehicle Regulations",
                "base_url": "https://www.efta.int/eea/eea-legal-order/transport",
                "doc_patterns": ["/eea-legal-order", "/publications"],
                "country": "EU"
            },
            "uk_dft": {
                "name": "UK Department for Transport",
                "base_url": "https://www.gov.uk/government/organisations/department-for-transport",
                "doc_patterns": ["/guidance/", "/government/publications/", "/vehicle-approval"],
                "country": "UK"
            },
            "un_ece": {
                "name": "UN Economic Commission for Europe",
                "base_url": "https://unece.org/transport/vehicle-regulations",
                "doc_patterns": ["/wp29/", "/standards/", "/transport/main/wp29/wp29regs"],
                "country": "International"
            },
            "iso_vehicles": {
                "name": "International Organization for Standardization - Road Vehicles",
                "base_url": "https://www.iso.org/committee/45306.html",
                "doc_patterns": ["/standards-catalogue/", "/committee/", "/standards/"],
                "country": "International"
            },
            "iec_vehicles": {
                "name": "International Electrotechnical Commission - Road Vehicles",
                "base_url": "https://www.iec.ch/standardsdev/publications/standards.htm",
                "doc_patterns": ["/standardsdev/", "/publications/", "/iec61851/"],
                "country": "International"
            },
            "acea": {
                "name": "European Automobile Manufacturers' Association",
                "base_url": "https://www.acea.auto/publications/",
                "doc_patterns": ["/publications/", "/regulatory-guide/", "/facts/"],
                "country": "EU"
            },
            "china_miit": {
                "name": "China Ministry of Industry and Information Technology",
                "base_url": "http://www.miit.gov.cn",
                "doc_patterns": ["/n1146295/", "/policy/", "/gongzuo/"],
                "country": "China"
            },
            "japan_mlit": {
                "name": "Japan Ministry of Land, Infrastructure, Transport and Tourism",
                "base_url": "https://www.mlit.go.jp/en/road/index.html",
                "doc_patterns": ["/jidosha/", "/technical/", "/road/"],
                "country": "Japan"
            },
            "india_arai": {
                "name": "Automotive Research Association of India",
                "base_url": "https://www.araiindia.com",
                "doc_patterns": ["/standards/", "/certification/", "/regulations/"],
                "country": "India"
            },
            "india_cmvr": {
                "name": "Central Motor Vehicle Rules (India)",
                "base_url": "https://www.morth.nic.in",
                "doc_patterns": ["/cmvr/", "/motor-vehicles-act/", "/regulatory/"],
                "country": "India"
            },
            "canada_tc": {
                "name": "Transport Canada - Motor Vehicle Safety",
                "base_url": "https://tc.canada.ca/en/road-transportation/motor-vehicle-safety",
                "doc_patterns": ["/road-transportation/", "/motor-vehicle-safety-regulations", "/standards/"],
                "country": "Canada"
            },
            "australia_vs": {
                "name": "Australia Vehicle Standards",
                "base_url": "https://www.infrastructure.gov.au/vehicles/vehicle-standards",
                "doc_patterns": ["/vehicles/", "/standards/", "/adrs/"],
                "country": "Australia"
            },
            "brazil_inmetro": {
                "name": "Brazil National Institute of Metrology, Quality and Technology",
                "base_url": "https://www.gov.br/inmetro/pt-br",
                "doc_patterns": ["/pt-br/", "/regulamentos/", "/normas/"],
                "country": "Brazil"
            },
            "korea_molit": {
                "name": "South Korea Ministry of Land, Infrastructure and Transport",
                "base_url": "https://www.molit.go.kr/english/",
                "doc_patterns": ["/english/", "/USR/", "/auto/"],
                "country": "South Korea"
            },
            "russia_rosavtodor": {
                "name": "Russia Federal Road Agency (Rosavtodor)",
                "base_url": "https://www.rosavtodor.ru/en/",
                "doc_patterns": ["/en/", "/activities/", "/docs/"],
                "country": "Russia"
            },
            "mexico_sct": {
                "name": "Mexico Secretariat of Communications and Transportation",
                "base_url": "https://www.gob.mx/sct",
                "doc_patterns": ["/sct/", "/documentos/", "/normas/"],
                "country": "Mexico"
            },
            "southafrica_nrcs": {
                "name": "South Africa National Regulator for Compulsory Specifications",
                "base_url": "https://www.nrcs.org.za/",
                "doc_patterns": ["/sabs/", "/automotive/", "/standards/"],
                "country": "South Africa"
            },
            "argentina_ansv": {
                "name": "Argentina National Road Safety Agency",
                "base_url": "https://www.ansv.gob.ar/",
                "doc_patterns": ["/normativa/", "/reglamentos/", "/seguridad-vial/"],
                "country": "Argentina"
            }
        }
    
    def _load_prompt_templates(self) -> Dict:
        """Load prompt templates with version compatibility."""
        return {
            "query_analysis": "As an automotive regulation expert, analyze this query: {query}\n\nIdentify:\n1. Relevant countries/regions: {}\n2. Specific regulation types: {}\n3. Vehicle categories: {}\n4. Timeframe: {}\n5. Key technical parameters: {}",
            
            "response_generation": """As an automotive regulations expert with 30 years of experience, answer the following query based ONLY on the regulatory documents provided below. Do not include any information not present in these sources.

USER QUERY: {query}

REGULATORY DOCUMENTS:
{context}

INSTRUCTIONS:
1. Provide a clear, concise answer citing specific regulations
2. Include regulation names, numbers, and sections
3. Note any differences between jurisdictions if relevant
4. Highlight effective dates and compliance deadlines
5. Only state facts found in the provided documents
6. If information is missing, clearly state what cannot be determined

ANSWER:""",
            
            "source_selection": "Given this automotive regulatory query: {query}\nIdentify the most relevant regulatory bodies and document types to search for from this list:\n{sources}\n\nOutput a JSON list of recommended sources to check."
        }
    
    def _get_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for the given text using Groq API."""
        try:
            # Try using the client's embedding method if available
            try:
                # Modern Groq client approach
                response = self.groq_client.embeddings.create(
                    model="llama3-embedding-v1",
                    input=text
                )
                embedding = response.data[0].embedding
            except (AttributeError, TypeError):
                # Fallback to direct API call if client method not available
                endpoint = "https://api.groq.com/openai/v1/embeddings"
                headers = {
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json={
                        "model": "llama3-embedding-v1",
                        "input": text
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"API error: {response.status_code} - {response.text}")
                    
                embedding = response.json()["data"][0]["embedding"]
            
            # Normalize the embedding if needed
            if self.mcp_config["embeddings_config"]["normalize"]:
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = [x / norm for x in embedding]
            return embedding
        except Exception as e:
            self.logger.log_error(f"Embedding generation error: {str(e)}")
            return [0.0] * self.mcp_config["embeddings_config"]["dimensions"]
    
    def _analyze_query(self, query: str) -> Dict:
        """Analyze the user query to determine what regulations to search for."""
        try:
            # Use direct API call to Groq to analyze the query
            prompt = self.mcp_config["prompt_templates"]["query_analysis"].format(query=query)
            
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an automotive regulations expert who helps analyze queries to determine what specific regulations should be searched for."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code} - {response.text}")
                
            analysis = response.json()["choices"][0]["message"]["content"]
            
            # Extract structured information using another call
            extraction_prompt = f"Extract the following information from this analysis into a JSON format:\n\n{analysis}\n\nOutput a JSON object with keys: regions, regulation_types, vehicle_categories, timeframe, technical_parameters"
            
            extraction_response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that extracts structured information into clean JSON."},
                        {"role": "user", "content": extraction_prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            
            if extraction_response.status_code != 200:
                raise Exception(f"API error: {extraction_response.status_code} - {extraction_response.text}")
                
            # Parse the JSON output
            structured_analysis = json.loads(extraction_response.json()["choices"][0]["message"]["content"])
            return structured_analysis
            
        except Exception as e:
            self.logger.log_error(f"Query analysis error: {str(e)}")
            # Return default analysis
            return {
                "regions": ["global"],
                "regulation_types": ["general"],
                "vehicle_categories": ["all"],
                "timeframe": "current",
                "technical_parameters": []
            }
    
    def _select_sources(self, query_analysis: Dict) -> List[str]:
        """Select the most relevant regulatory sources based on query analysis."""
        relevant_sources = []
        
        # Check each source for relevance
        for source_id, source_info in self.reg_sources.items():
            relevance_score = 0
            
            # Check country relevance
            if source_info["country"] in query_analysis["regions"] or "global" in query_analysis["regions"] or "all" in query_analysis["regions"]:
                relevance_score += 3
            
            # Add source if it meets minimum relevance
            if relevance_score > 0:
                relevant_sources.append(source_id)
        
        # If no specific sources found, include all major ones
        if not relevant_sources:
            relevant_sources = list(self.reg_sources.keys())[:3]  # Top 3 sources
        
        return relevant_sources
    
    def _get_cached_response(self, query: str) -> Optional[str]:
        """Check if we have a cached response for this or a very similar query."""
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        
        # Check exact match
        if query_hash in self.query_cache:
            cache_entry = self.query_cache[query_hash]
            # Check if cache is still valid (less than 1 week old)
            if (datetime.now() - cache_entry["timestamp"]).days < 7:
                self.logger.log_event("cache_hit", {"query": query})
                return cache_entry["response"]
        
        # No valid cache entry found
        return None
    
    def _update_cache(self, query: str, response: str, sources: List[Dict]):
        """Update the cache with a new query-response pair."""
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        
        self.query_cache[query_hash] = {
            "query": query,
            "response": response,
            "sources": sources,
            "timestamp": datetime.now(),
            "access_count": 1
        }
        
        # Save cache periodically
        if len(self.query_cache) % 10 == 0:
            self._save_cache()
    
    def _save_cache(self):
        """Save the query cache to disk."""
        try:
            cache_data = {}
            for k, v in self.query_cache.items():
                cache_entry = v.copy()
                cache_entry["timestamp"] = cache_entry["timestamp"].isoformat()
                cache_data[k] = cache_entry
                
            with open("data/query_cache.json", "w") as f:
                json.dump(cache_data, f)
                
        except Exception as e:
            self.logger.log_error(f"Cache save error: {str(e)}")
    
    def _load_cache(self):
        """Load the query cache from disk."""
        try:
            if os.path.exists("data/query_cache.json"):
                with open("data/query_cache.json", "r") as f:
                    cache_data = json.load(f)
                
                for k, v in cache_data.items():
                    v["timestamp"] = datetime.fromisoformat(v["timestamp"])
                    self.query_cache[k] = v
                    
        except Exception as e:
            self.logger.log_error(f"Cache load error: {str(e)}")
    
    def process_query(self, query: str) -> Tuple[str, List[Dict]]:
        """
        Process a user query and return a response based on regulatory documents.
        
        Args:
            query: The user's question about automotive regulations
            
        Returns:
            Tuple containing:
            - response: The generated answer
            - sources: List of source documents used
        """
        start_time = time.time()
        self.query_count += 1
        self.logger.log_query(query)
        
        # Check cache first
        cached_response = self._get_cached_response(query)
        if cached_response:
            processing_time = time.time() - start_time
            self.logger.log_performance(query, processing_time, True)
            return cached_response, []  # No sources needed for cached response
        
        # Step 1: Analyze the query
        query_analysis = self._analyze_query(query)
        self.logger.log_event("query_analysis", query_analysis)
        
        # Step 2: Select relevant sources
        relevant_source_ids = self._select_sources(query_analysis)
        self.logger.log_event("selected_sources", {"sources": relevant_source_ids})
        
        # Step 3: Retrieve documents from sources
        all_chunks = []
        source_documents = []
        
        for source_id in relevant_source_ids:
            source_info = self.reg_sources[source_id]
            documents = self.crawler.retrieve_documents(
                source_info["base_url"],
                source_info["doc_patterns"],
                query_analysis
            )
            
            # Process and chunk documents
            for doc in documents:
                chunks = self.crawler.chunk_document(doc["content"])
                all_chunks.extend(chunks)
                source_documents.append({
                    "title": doc["title"],
                    "url": doc["url"],
                    "source": source_info["name"]
                })
        
        # Step 4: Generate embeddings and find relevant chunks
        if not all_chunks:
            response = "I couldn't find specific regulatory information to answer your query accurately. Please try rephrasing your question or specifying particular regulations you're interested in."
            self.logger.log_performance(query, time.time() - start_time, False)
            return response, []
        
        query_embedding = self._get_embeddings(query)
        relevant_chunks = self.vector_store.find_relevant_chunks(query_embedding, all_chunks)
        
        # Step 5: Generate response using Groq API directly
        context = "\n\n".join([f"Document: {chunk['text']}\nSource: {chunk['source']}" for chunk in relevant_chunks])
        prompt = self.mcp_config["prompt_templates"]["response_generation"].format(
            query=query,
            context=context
        )
        
        try:
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an automotive regulations expert with 30 years of experience. Provide accurate, detailed answers about automotive regulations based ONLY on the sources provided."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 2000
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code} - {response.text}")
                
            generated_response = response.json()["choices"][0]["message"]["content"]
            
            # Add citation references
            formatted_response = self._add_citations(generated_response, source_documents)
            
            # Update cache
            self._update_cache(query, formatted_response, source_documents)
            
            # Log performance
            processing_time = time.time() - start_time
            self.logger.log_performance(query, processing_time, True)
            
            self.successful_queries += 1
            return formatted_response, source_documents
            
        except Exception as e:
            error_message = f"I encountered an error while processing your query: {str(e)}"
            self.logger.log_error(f"Response generation error: {str(e)}")
            self.logger.log_performance(query, time.time() - start_time, False)
            return error_message, []
    
    def _add_citations(self, response: str, sources: List[Dict]) -> str:
        """Add citation references to the response."""
        # Create a citation index
        citations = {}
        for i, source in enumerate(sources):
            citation_key = f"[{i+1}]"
            citations[citation_key] = f"{source['title']} - {source['source']} ({source['url']})"
        
        # Check if we need to add citations
        if not re.search(r'\[\d+\]', response):
            # No citation format detected, add a sources section
            response += "\n\nSources:\n"
            for i, (_, citation) in enumerate(citations.items()):
                response += f"[{i+1}] {citation}\n"
        else:
            # Replace existing citations
            for key, citation in citations.items():
                if key in response:
                    # Citation already used
                    continue
            
            # Add missing citations at the end
            response += "\n\nSources:\n"
            for key, citation in citations.items():
                response += f"{key} {citation}\n"
        
        return response
    
    def record_feedback(self, query: str, response: str, feedback_score: float):
        """Record user feedback to improve the agent over time."""
        self.logger.log_feedback(query, feedback_score)
        
        # Update query cache with feedback if it exists
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        if query_hash in self.query_cache:
            if "feedback" not in self.query_cache[query_hash]:
                self.query_cache[query_hash]["feedback"] = []
            
            self.query_cache[query_hash]["feedback"].append({
                "score": feedback_score,
                "timestamp": datetime.now()
            })
            
            # Calculate average feedback
            feedback_scores = [f["score"] for f in self.query_cache[query_hash]["feedback"]]
            self.query_cache[query_hash]["avg_feedback"] = sum(feedback_scores) / len(feedback_scores)
            
            # Learn from highly rated responses
            if feedback_score >= self.feedback_threshold:
                # Update vector store with this successful query-response pair
                self.vector_store.add_to_learning_set(query, response, feedback_score)
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics for the agent."""
        return {
            "total_queries": self.query_count,
            "successful_queries": self.successful_queries,
            "success_rate": self.successful_queries / max(1, self.query_count),
            "cache_size": len(self.query_cache),
            "avg_processing_time": self.logger.get_avg_processing_time()
        }
    
    def improve(self):
        """Periodically improve the agent based on feedback and performance."""
        # This would be called on a schedule
        
        # 1. Update prompt templates based on successful responses
        high_rated_queries = {k: v for k, v in self.query_cache.items() 
                             if v.get("avg_feedback", 0) >= self.feedback_threshold}
        
        if high_rated_queries:
            # Use successful queries to potentially refine prompt templates
            sample_successful_prompts = list(high_rated_queries.values())[:5]
            
            # Generate improved prompt template (this would use the LLM)
            # For now we'll just log that we're improving
            self.logger.log_event("improving_prompts", {
                "num_samples": len(sample_successful_prompts)
            })
        
        # 2. Update crawler patterns based on success rates
        source_success_rates = self.logger.get_source_success_rates()
        
        # Log the improvement cycle
        self.logger.log_event("improvement_cycle", {
            "high_rated_queries": len(high_rated_queries),
            "source_success_rates": source_success_rates
        })

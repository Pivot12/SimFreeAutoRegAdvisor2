import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pickle
import hnswlib
from logger import Logger

class VectorStore:
    """
    Vector database for storing and retrieving document chunks based on semantic similarity.
    Uses HNSW (Hierarchical Navigable Small World) algorithm for efficient similarity search.
    """
    
    def __init__(self):
        self.logger = Logger()
        
        # Vector store settings
        self.dimensions = 1536  # Default dimension for embeddings
        self.max_elements = 100000  # Maximum number of elements in the index
        self.ef_construction = 200  # Controls index quality
        self.M = 16  # Controls index size/speed tradeoff
        self.ef_search = 100  # Controls search accuracy
        
        # Initialize index
        self.initialized = False
        self._initialize_index()
        
        # Metadata storage
        self.metadata = {}  # Maps index id to metadata
        self.id_counter = 0  # For assigning sequential IDs
        
        # Learning database
        self.learning_set = []  # Store successful query-response pairs
        self.learning_embeddings = []  # Embeddings of learning queries
        
        # Load existing data if available
        self._load_data()
    
    def _initialize_index(self):
        """Initialize the HNSW index."""
        try:
            self.index = hnswlib.Index(space='cosine', dim=self.dimensions)
            self.index.init_index(
                max_elements=self.max_elements,
                ef_construction=self.ef_construction,
                M=self.M
            )
            self.index.set_ef(self.ef_search)
            self.initialized = True
            
        except Exception as e:
            self.logger.log_error(f"HNSW index initialization error: {str(e)}")
            self.initialized = False
    
    def _load_data(self):
        """Load existing vector store data if available."""
        try:
            # Check if data files exist
            if os.path.exists("data/vector_index.bin") and os.path.exists("data/vector_metadata.pkl"):
                # Load the index
                self.index.load_index("data/vector_index.bin")
                
                # Load metadata
                with open("data/vector_metadata.pkl", "rb") as f:
                    loaded_data = pickle.load(f)
                    self.metadata = loaded_data["metadata"]
                    self.id_counter = loaded_data["id_counter"]
                
                # Update the current element count
                self.index.set_num_threads(4)  # Use multiple threads
                
                self.logger.log_event("vector_store_loaded", {
                    "elements": len(self.metadata),
                    "dimensions": self.dimensions
                })
            
            # Load learning set if available
            if os.path.exists("data/learning_set.pkl"):
                with open("data/learning_set.pkl", "rb") as f:
                    loaded_learning = pickle.load(f)
                    self.learning_set = loaded_learning["entries"]
                    self.learning_embeddings = loaded_learning["embeddings"]
                    
                self.logger.log_event("learning_set_loaded", {
                    "entries": len(self.learning_set)
                })
                
        except Exception as e:
            self.logger.log_error(f"Error loading vector store data: {str(e)}")
            # Reset and reinitialize the index if loading fails
            self._initialize_index()
            self.metadata = {}
            self.id_counter = 0
    
    def _save_data(self):
        """Save vector store data to disk."""
        try:
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)
            
            # Save the index
            self.index.save_index("data/vector_index.bin")
            
            # Save metadata
            with open("data/vector_metadata.pkl", "wb") as f:
                pickle.dump({
                    "metadata": self.metadata,
                    "id_counter": self.id_counter
                }, f)
                
            # Save learning set
            with open("data/learning_set.pkl", "wb") as f:
                pickle.dump({
                    "entries": self.learning_set,
                    "embeddings": self.learning_embeddings
                }, f)
                
            self.logger.log_event("vector_store_saved", {
                "elements": len(self.metadata)
            })
            
        except Exception as e:
            self.logger.log_error(f"Error saving vector store data: {str(e)}")
    
    def add_vectors(self, vectors: List[List[float]], metadata_list: List[Dict]):
        """
        Add vectors and their metadata to the store.
        
        Args:
            vectors: List of embedding vectors (each a list of floats)
            metadata_list: List of metadata dictionaries for each vector
        """
        if not self.initialized:
            self.logger.log_error("Vector store not initialized")
            return
        
        if len(vectors) != len(metadata_list):
            self.logger.log_error(f"Vector and metadata list lengths don't match: {len(vectors)} vs {len(metadata_list)}")
            return
        
        try:
            # Convert to numpy array
            vectors_np = np.array(vectors).astype('float32')
            
            # Create IDs for the new vectors
            ids = np.arange(self.id_counter, self.id_counter + len(vectors))
            
            # Add to the index
            self.index.add_items(vectors_np, ids)
            
            # Store metadata
            for i, idx in enumerate(ids):
                self.metadata[int(idx)] = metadata_list[i]
            
            # Update counter
            self.id_counter += len(vectors)
            
            # Save periodically
            if self.id_counter % 100 == 0:
                self._save_data()
                
        except Exception as e:
            self.logger.log_error(f"Error adding vectors: {str(e)}")
    
    def search(self, query_vector: List[float], k: int = 5) -> List[Tuple[int, float, Dict]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: The embedding vector to search for
            k: Number of results to return
            
        Returns:
            List of tuples containing (id, distance, metadata)
        """
        if not self.initialized or len(self.metadata) == 0:
            return []
        
        try:
            # Convert to numpy array
            query_np = np.array(query_vector).astype('float32').reshape(1, -1)
            
            # Perform the search
            indices, distances = self.index.knn_query(query_np, k=min(k, len(self.metadata)))
            
            # Format results
            results = []
            for i in range(len(indices[0])):
                idx = int(indices[0][i])
                distance = float(distances[0][i])
                
                if idx in self.metadata:
                    results.append((idx, distance, self.metadata[idx]))
            
            return results
            
        except Exception as e:
            self.logger.log_error(f"Search error: {str(e)}")
            return []
    
    def find_relevant_chunks(self, query_embedding: List[float], chunks: List[Dict], k: int = 5) -> List[Dict]:
        """
        Find the most relevant chunks for a query.
        
        Args:
            query_embedding: Embedding vector of the query
            chunks: List of document chunks with text and metadata
            k: Number of chunks to return
            
        Returns:
            List of the most relevant chunks
        """
        # First search for similar queries in the learning set
        learning_results = self._search_learning_set(query_embedding, 3)
        
        # Add chunks to the vector store (temporarily)
        chunk_embeddings = []
        chunk_metadata = []
        
        for i, chunk in enumerate(chunks):
            # For now, we'll assume chunk embeddings are computed elsewhere
            # In a real implementation, we would compute embeddings for each chunk
            # But for simplicity, we'll use a mock embedding here
            mock_embedding = [0.0] * self.dimensions
            chunk_id = self.id_counter + i
            
            chunk_embeddings.append(mock_embedding)
            chunk_metadata.append(chunk)
        
        # Add chunks to vector store (without saving)
        try:
            self.add_vectors(chunk_embeddings, chunk_metadata)
            
            # Search for similar chunks
            results = self.search(query_embedding, k=k)
            
            # Get the chunks
            relevant_chunks = [metadata for _, _, metadata in results]
            
            # Restore the ID counter (undo the additions)
            self.id_counter -= len(chunks)
            
            # Combine with learning results if available
            if learning_results:
                # Get the chunks from learning results
                for entry in learning_results:
                    # Extract any document references from successful responses
                    doc_refs = self._extract_doc_refs(entry["response"])
                    if doc_refs:
                        relevant_chunks.extend(doc_refs)
            
            return relevant_chunks[:k]  # Return the top k chunks
            
        except Exception as e:
            self.logger.log_error(f"Error finding relevant chunks: {str(e)}")
            return chunks[:k]  # Fallback to first k chunks
    
    def _extract_doc_refs(self, response: str) -> List[Dict]:
        """Extract document references from a response text."""
        # This is a simplified implementation
        # In a real system, we would parse the response to extract actual references
        refs = []
        
        # Look for citation patterns like [1], [2], etc.
        import re
        citation_matches = re.findall(r'\[(\d+)\]', response)
        
        for match in citation_matches:
            # Create a mock chunk for each citation
            refs.append({
                "text": f"Reference from previous successful query [citation {match}]",
                "source": "learning_database"
            })
        
        return refs
    
    def _search_learning_set(self, query_embedding: List[float], k: int = 3) -> List[Dict]:
        """Search for similar queries in the learning set."""
        if not self.learning_embeddings:
            return []
        
        try:
            # Convert to numpy array
            query_np = np.array(query_embedding).astype('float32')
            learning_np = np.array(self.learning_embeddings).astype('float32')
            
            # Compute similarities
            similarities = np.dot(learning_np, query_np) / (
                np.linalg.norm(learning_np, axis=1) * np.linalg.norm(query_np)
            )
            
            # Get the top k indices
            top_indices = np.argsort(similarities)[-k:][::-1]
            
            # Return the entries
            return [self.learning_set[i] for i in top_indices if similarities[i] > 0.7]
            
        except Exception as e:
            self.logger.log_error(f"Learning set search error: {str(e)}")
            return []
    
    def add_to_learning_set(self, query: str, response: str, feedback_score: float):
        """Add a successful query-response pair to the learning set."""
        try:
            # Generate embedding for the query (mocked for simplicity)
            # In a real implementation, this would use the actual embedding function
            mock_embedding = [0.0] * self.dimensions
            
            # Add to learning set
            entry = {
                "query": query,
                "response": response,
                "feedback_score": feedback_score,
                "timestamp": datetime.now().isoformat()
            }
            
            self.learning_set.append(entry)
            self.learning_embeddings.append(mock_embedding)
            
            # Save periodically
            if len(self.learning_set) % 10 == 0:
                self._save_data()
                
            self.logger.log_event("added_to_learning_set", {
                "query": query,
                "feedback_score": feedback_score
            })
            
        except Exception as e:
            self.logger.log_error(f"Error adding to learning set: {str(e)}")
    
    def clear(self):
        """Clear the vector store and reinitialize."""
        try:
            self._initialize_index()
            self.metadata = {}
            self.id_counter = 0
            self._save_data()
            
            self.logger.log_event("vector_store_cleared", {})
            
        except Exception as e:
            self.logger.log_error(f"Error clearing vector store: {str(e)}")

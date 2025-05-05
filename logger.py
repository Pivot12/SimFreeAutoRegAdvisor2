import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import hashlib
from pathlib import Path

class Logger:
    """
    Logger for the auto regulations agent that captures diagnostics and
    user interaction data for performance tracking and improvement.
    """
    
    def __init__(self):
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler("auto_regs_agent.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("auto_regs_agent")
        
        # Create data directory
        os.makedirs("data", exist_ok=True)
        
        # Initialize dataframes
        self.queries_df = self._load_or_create_df("queries.csv", [
            "query_id", "timestamp", "query_text", "user_id", "processing_time", "success"
        ])
        
        self.errors_df = self._load_or_create_df("errors.csv", [
            "error_id", "timestamp", "error_type", "error_message", "query_id"
        ])
        
        self.feedback_df = self._load_or_create_df("feedback.csv", [
            "feedback_id", "timestamp", "query_id", "user_id", "score", "comments"
        ])
        
        self.performance_df = self._load_or_create_df("performance.csv", [
            "timestamp", "processing_time", "query_id", "success", "num_sources", "num_chunks"
        ])
        
        self.events_df = self._load_or_create_df("events.csv", [
            "event_id", "timestamp", "event_type", "event_data", "query_id"
        ])
        
        # Track current query ID
        self.current_query_id = None
        
        # Save counts for efficient saving
        self.save_threshold = 10
        self.entry_count = 0
    
    def _load_or_create_df(self, filename: str, columns: List[str]) -> pd.DataFrame:
        """Load a dataframe from file or create a new one if it doesn't exist."""
        filepath = Path(f"data/{filename}")
        
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                # Ensure all expected columns exist
                for col in columns:
                    if col not in df.columns:
                        df[col] = None
                return df
            except Exception as e:
                self.logger.error(f"Error loading {filename}: {str(e)}")
                # If loading fails, create a new dataframe
                return pd.DataFrame(columns=columns)
        else:
            return pd.DataFrame(columns=columns)
    
    def _save_dataframes(self):
        """Save all dataframes to CSV files."""
        try:
            self.queries_df.to_csv("data/queries.csv", index=False)
            self.errors_df.to_csv("data/errors.csv", index=False)
            self.feedback_df.to_csv("data/feedback.csv", index=False)
            self.performance_df.to_csv("data/performance.csv", index=False)
            self.events_df.to_csv("data/events.csv", index=False)
        except Exception as e:
            self.logger.error(f"Error saving dataframes: {str(e)}")
    
    def _get_user_id(self) -> str:
        """Get an anonymous user ID based on environment or session."""
        # This would normally use a session ID or authenticated user ID
        # For simplicity, we'll use a placeholder
        user_hash = hashlib.md5(os.environ.get("USER", "anonymous").encode()).hexdigest()
        return user_hash[:8]
    
    def log_query(self, query_text: str):
        """Log a new user query."""
        query_id = hashlib.md5(f"{datetime.now().isoformat()}-{query_text}".encode()).hexdigest()[:12]
        self.current_query_id = query_id
        
        timestamp = datetime.now().isoformat()
        user_id = self._get_user_id()
        
        # Create a new row as a DataFrame and concat instead of using append
        new_row = pd.DataFrame([{
            "query_id": query_id,
            "timestamp": timestamp,
            "query_text": query_text,
            "user_id": user_id,
            "processing_time": None,  # Will be updated later
            "success": None  # Will be updated later
        }])
        
        self.queries_df = pd.concat([self.queries_df, new_row], ignore_index=True)
        
        self.entry_count += 1
        if self.entry_count >= self.save_threshold:
            self._save_dataframes()
            self.entry_count = 0
        
        self.logger.info(f"Query logged: {query_id}")
    
    def log_error(self, error_message: str, error_type: str = "general"):
        """Log an error encountered during processing."""
        error_id = hashlib.md5(f"{datetime.now().isoformat()}-{error_message}".encode()).hexdigest()[:12]
        timestamp = datetime.now().isoformat()
        
        # Create a new row as a DataFrame and concat instead of using append
        new_row = pd.DataFrame([{
            "error_id": error_id,
            "timestamp": timestamp,
            "error_type": error_type,
            "error_message": error_message,
            "query_id": self.current_query_id
        }])
        
        self.errors_df = pd.concat([self.errors_df, new_row], ignore_index=True)
        
        self.logger.error(f"Error: {error_message}")
        
        self.entry_count += 1
        if self.entry_count >= self.save_threshold:
            self._save_dataframes()
            self.entry_count = 0
    
    def log_feedback(self, query: str, score: float, comments: str = ""):
        """Log user feedback on a response."""
        # Find the query ID if it exists
        query_mask = self.queries_df["query_text"] == query
        query_id = None
        
        if query_mask.any():
            query_id = self.queries_df.loc[query_mask, "query_id"].iloc[0]
        else:
            query_id = self.current_query_id
        
        timestamp = datetime.now().isoformat()
        user_id = self._get_user_id()
        feedback_id = hashlib.md5(f"{timestamp}-{query_id}-{score}".encode()).hexdigest()[:12]
        
        # Create a new row as a DataFrame and concat instead of using append
        new_row = pd.DataFrame([{
            "feedback_id": feedback_id,
            "timestamp": timestamp,
            "query_id": query_id,
            "user_id": user_id,
            "score": score,
            "comments": comments
        }])
        
        self.feedback_df = pd.concat([self.feedback_df, new_row], ignore_index=True)
        
        self.logger.info(f"Feedback logged: {score} for query {query_id}")
        
        self.entry_count += 1
        if self.entry_count >= self.save_threshold:
            self._save_dataframes()
            self.entry_count = 0
    
    def log_performance(self, query: str, processing_time: float, success: bool, 
                        num_sources: int = 0, num_chunks: int = 0):
        """Log performance metrics for a query."""
        timestamp = datetime.now().isoformat()
        
        # Update the query entry with processing time and success
        if self.current_query_id:
            query_mask = self.queries_df["query_id"] == self.current_query_id
            if query_mask.any():
                self.queries_df.loc[query_mask, "processing_time"] = processing_time
                self.queries_df.loc[query_mask, "success"] = success
        
        # Also add to performance dataframe for time series analysis
        # Create a new row as a DataFrame and concat instead of using append
        new_row = pd.DataFrame([{
            "timestamp": timestamp,
            "processing_time": processing_time,
            "query_id": self.current_query_id,
            "success": success,
            "num_sources": num_sources,
            "num_chunks": num_chunks
        }])
        
        self.performance_df = pd.concat([self.performance_df, new_row], ignore_index=True)
        
        self.logger.info(f"Performance logged: {processing_time:.2f}s, success={success}")
        
        self.entry_count += 1
        if self.entry_count >= self.save_threshold:
            self._save_dataframes()
            self.entry_count = 0
    
    def log_event(self, event_type: str, event_data: Dict):
        """Log a general event with associated data."""
        event_id = hashlib.md5(f"{datetime.now().isoformat()}-{event_type}".encode()).hexdigest()[:12]
        timestamp = datetime.now().isoformat()
        
        # Convert dict to JSON string
        event_data_json = json.dumps(event_data)
        
        # Create a new row as a DataFrame and concat instead of using append
        new_row = pd.DataFrame([{
            "event_id": event_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "event_data": event_data_json,
            "query_id": self.current_query_id
        }])
        
        self.events_df = pd.concat([self.events_df, new_row], ignore_index=True)
        
        self.logger.info(f"Event logged: {event_type}")
        
        self.entry_count += 1
        if self.entry_count >= self.save_threshold:
            self._save_dataframes()
            self.entry_count = 0
    
    def get_avg_processing_time(self) -> float:
        """Get the average processing time for successful queries."""
        success_mask = self.queries_df["success"] == True
        if success_mask.any():
            return self.queries_df.loc[success_mask, "processing_time"].mean()
        return 0.0
    
    def get_success_rate(self) -> float:
        """Get the success rate of queries."""
        if len(self.queries_df) == 0:
            return 0.0
        
        success_mask = self.queries_df["success"] == True
        return success_mask.sum() / len(self.queries_df)
    
    def get_source_success_rates(self) -> Dict[str, float]:
        """Get success rates by source."""
        # Parse source information from events
        source_events = self.events_df[self.events_df["event_type"] == "selected_sources"]
        
        if len(source_events) == 0:
            return {}
        
        # Extract source data and join with queries for success info
        source_data = []
        for _, row in source_events.iterrows():
            try:
                query_id = row["query_id"]
                event_data = json.loads(row["event_data"])
                sources = event_data.get("sources", [])
                
                # Get success status for this query
                query_mask = self.queries_df["query_id"] == query_id
                if query_mask.any():
                    success = self.queries_df.loc[query_mask, "success"].iloc[0]
                    
                    for source in sources:
                        source_data.append({
                            "source": source,
                            "success": success
                        })
            except:
                continue
        
        if not source_data:
            return {}
        
        # Convert to dataframe
        source_df = pd.DataFrame(source_data)
        
        # Calculate success rate per source
        success_rates = {}
        for source in source_df["source"].unique():
            source_mask = source_df["source"] == source
            success_mask = source_df.loc[source_mask, "success"] == True
            
            if source_mask.any():
                success_rates[source] = success_mask.sum() / source_mask.sum()
        
        return success_rates
    
    def export_data(self):
        """Export all data as a dictionary."""
        self._save_dataframes()
        
        return {
            "queries": self.queries_df.to_dict(orient="records"),
            "errors": self.errors_df.to_dict(orient="records"),
            "feedback": self.feedback_df.to_dict(orient="records"),
            "performance": self.performance_df.to_dict(orient="records"),
            "events": self.events_df.to_dict(orient="records")
        }

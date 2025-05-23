import os
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_log_file(log_file_path: str) -> None:
    """
    Initialize the log file with column headers if it doesn't exist.
    
    Args:
        log_file_path: Path to the log file
    """
    if not os.path.exists(log_file_path):
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        # Create empty dataframe with headers
        log_df = pd.DataFrame(columns=[
            'session_id',
            'timestamp',
            'query',
            'response',
            'regulation_topic',
            'num_sources',
            'response_time',
            'user_location',
            'query_successful'
        ])
        
        # Save to CSV
        log_df.to_csv(log_file_path, index=False)
        logger.info(f"Initialized log file at {log_file_path}")
    else:
        logger.info(f"Log file already exists at {log_file_path}")

def log_query(
    log_file_path: str,
    session_id: str,
    query: str,
    response: str,
    regulation_topic: str,
    num_sources: int,
    response_time: float,
    user_location: str = "Unknown",
    query_successful: bool = True
) -> bool:
    """
    Log a query and its response to the log file.
    
    Args:
        log_file_path: Path to the log file
        session_id: Unique session identifier
        query: User's query
        response: System's response
        regulation_topic: Topic of the regulation
        num_sources: Number of sources used
        response_time: Time taken to respond (in seconds)
        user_location: User's location (if available)
        query_successful: Whether the query was successful
    
    Returns:
        Boolean indicating if logging was successful
    """
    try:
        # Create log entry
        log_entry = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'response': response,
            'regulation_topic': regulation_topic,
            'num_sources': num_sources,
            'response_time': response_time,
            'user_location': user_location,
            'query_successful': query_successful
        }
        
        # Convert to DataFrame
        log_df = pd.DataFrame([log_entry])
        
        # Append to log file
        log_df.to_csv(log_file_path, mode='a', header=False, index=False)
        
        logger.info(f"Logged query with session ID {session_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error logging query: {str(e)}")
        return False

def load_log_data(log_file_path: str) -> pd.DataFrame:
    """
    Load log data from the log file.
    
    Args:
        log_file_path: Path to the log file
    
    Returns:
        DataFrame containing log data
    """
    if not os.path.exists(log_file_path):
        logger.warning(f"Log file not found at {log_file_path}")
        return pd.DataFrame()
    
    try:
        log_df = pd.read_csv(log_file_path)
        return log_df
    
    except Exception as e:
        logger.error(f"Error loading log data: {str(e)}")
        return pd.DataFrame()

def get_query_statistics(log_file_path: str) -> Dict[str, Any]:
    """
    Generate statistics from the log data.
    
    Args:
        log_file_path: Path to the log file
    
    Returns:
        Dictionary containing statistics
    """
    log_df = load_log_data(log_file_path)
    
    if log_df.empty:
        return {
            'total_queries': 0,
            'successful_queries': 0,
            'average_response_time': 0,
            'top_regulation_topics': {},
            'queries_per_day': {}
        }
    
    try:
        # Calculate statistics
        total_queries = len(log_df)
        successful_queries = log_df['query_successful'].sum()
        average_response_time = log_df['response_time'].mean()
        
        # Get top regulation topics
        top_regulation_topics = log_df['regulation_topic'].value_counts().to_dict()
        
        # Convert timestamp to datetime and get queries per day
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'])
        log_df['date'] = log_df['timestamp'].dt.date
        queries_per_day = log_df.groupby('date').size().to_dict()
        
        # Convert date objects to strings
        queries_per_day = {str(date): count for date, count in queries_per_day.items()}
        
        return {
            'total_queries': total_queries,
            'successful_queries': successful_queries,
            'average_response_time': average_response_time,
            'top_regulation_topics': top_regulation_topics,
            'queries_per_day': queries_per_day
        }
    
    except Exception as e:
        logger.error(f"Error generating query statistics: {str(e)}")
        return {
            'total_queries': 0,
            'successful_queries': 0,
            'average_response_time': 0,
            'top_regulation_topics': {},
            'queries_per_day': {}
        }

def get_user_queries(log_file_path: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get user queries from the log data.
    
    Args:
        log_file_path: Path to the log file
        session_id: Optional session ID to filter queries
    
    Returns:
        List of query dictionaries
    """
    log_df = load_log_data(log_file_path)
    
    if log_df.empty:
        return []
    
    try:
        # Filter by session ID if provided
        if session_id:
            log_df = log_df[log_df['session_id'] == session_id]
        
        # Convert DataFrame to list of dictionaries
        queries = log_df[['session_id', 'timestamp', 'query', 'response', 'regulation_topic', 'response_time']].to_dict('records')
        
        return queries
    
    except Exception as e:
        logger.error(f"Error getting user queries: {str(e)}")
        return []

def anonymize_log_data(log_file_path: str, output_path: str) -> bool:
    """
    Create an anonymized version of the log data for sharing.
    
    Args:
        log_file_path: Path to the original log file
        output_path: Path to save the anonymized log file
    
    Returns:
        Boolean indicating if anonymization was successful
    """
    log_df = load_log_data(log_file_path)
    
    if log_df.empty:
        logger.warning(f"No log data to anonymize")
        return False
    
    try:
        # Create a copy of the log DataFrame
        anon_df = log_df.copy()
        
        # Replace session IDs with random IDs
        import uuid
        session_ids = anon_df['session_id'].unique()
        session_id_map = {sid: str(uuid.uuid4()) for sid in session_ids}
        anon_df['session_id'] = anon_df['session_id'].map(session_id_map)
        
        # Remove potentially sensitive information
        anon_df['user_location'] = "Anonymized"
        
        # Save anonymized data
        anon_df.to_csv(output_path, index=False)
        
        logger.info(f"Anonymized log data saved to {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error anonymizing log data: {str(e)}")
        return False

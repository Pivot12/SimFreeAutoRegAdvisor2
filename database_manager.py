import os
import sqlite3
import json
import uuid
import datetime
import time
import logging
import hashlib
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/db_manager.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DatabaseManager")

class DatabaseManager:
    """
    Enhanced database manager that handles logging, learning, and performance tracking
    """
    
    def __init__(self, db_path="logs/auto_regulations.db"):
        """Initialize the database manager"""
        # Make sure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.session_id = str(uuid.uuid4())
        self.user_id = None
        
        # Initialize the database
        self._initialize_db()
        
        # Performance tracking
        self.query_start_time = None
        
        logger.info(f"Database manager initialized with session ID: {self.session_id}")
    
    def _initialize_db(self):
        """Initialize the database with all necessary tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create usage logs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                timestamp TEXT,
                user_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                query TEXT,
                response_status TEXT,
                error_message TEXT,
                execution_time REAL,
                documents_retrieved INTEGER,
                model_used TEXT,
                feedback_score INTEGER
            )
            ''')
            
            # Create admin users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                created_at TEXT
            )
            ''')
            
            # Create successful paths table for learning
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS successful_paths (
                id TEXT PRIMARY KEY,
                authority TEXT,
                search_term TEXT,
                path TEXT,
                success INTEGER,
                timestamp TEXT,
                usage_count INTEGER
            )
            ''')
            
            # Create query performance table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_performance (
                id TEXT PRIMARY KEY,
                query TEXT,
                execution_time REAL,
                documents_retrieved INTEGER,
                successful INTEGER,
                timestamp TEXT
            )
            ''')
            
            # Create document cache table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_cache (
                id TEXT PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                authority TEXT,
                content BLOB,
                metadata TEXT,
                timestamp TEXT,
                last_accessed TEXT,
                access_count INTEGER
            )
            ''')
            
            # Create user sessions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                start_time TEXT,
                end_time TEXT,
                query_count INTEGER,
                success_rate REAL
            )
            ''')
            
            # Add default admin if none exists
            cursor.execute("SELECT COUNT(*) FROM admin_users")
            if cursor.fetchone()[0] == 0:
                # Create default admin with password 'admin123' (should be changed)
                default_pass = hashlib.sha256('admin123'.encode()).hexdigest()
                cursor.execute(
                    "INSERT INTO admin_users VALUES (?, ?, ?)",
                    ('admin', default_pass, datetime.datetime.now().isoformat())
                )
                logger.info("Created default admin user")
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    def set_user_id(self, user_id, ip_address=None, user_agent=None):
        """Set the user ID for this session"""
        self.user_id = user_id
        
        # Log the session start
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO user_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session_id,
                    user_id,
                    ip_address or "unknown",
                    user_agent or "unknown",
                    datetime.datetime.now().isoformat(),
                    None,  # end_time will be updated when session ends
                    0,     # query_count starts at 0
                    0.0    # success_rate starts at 0
                )
            )
            
            conn.commit()
            conn.close()
            logger.info(f"User session started: {user_id}")
        except Exception as e:
            logger.error(f"Error logging session start: {e}")
    
    def start_query(self, query):
        """Start timing a query execution"""
        self.query_start_time = time.time()
        logger.info(f"Starting query: {query}")
    
    def log_query(self, query, response_status="success", error_message="", 
                  documents_retrieved=0, model_used=""):
        """Log a user query with results"""
        # Calculate execution time if available
        execution_time = None
        if self.query_start_time:
            execution_time = time.time() - self.query_start_time
            self.query_start_time = None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Generate a unique ID for this log
            log_id = str(uuid.uuid4())
            
            # Insert the log
            cursor.execute(
                "INSERT INTO usage_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    log_id,
                    self.session_id,
                    datetime.datetime.now().isoformat(),
                    self.user_id or "anonymous",
                    "unknown",  # IP address - not collecting
                    "unknown",  # User agent - not collecting
                    query,
                    response_status,
                    error_message,
                    execution_time,
                    documents_retrieved,
                    model_used,
                    None  # feedback_score - will be updated if user provides feedback
                )
            )
            
            # Also log to query performance
            cursor.execute(
                "INSERT INTO query_performance VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    query,
                    execution_time,
                    documents_retrieved,
                    1 if response_status == "success" else 0,
                    datetime.datetime.now().isoformat()
                )
            )
            
            # Update session stats
            cursor.execute(
                "UPDATE user_sessions SET query_count = query_count + 1 WHERE id = ?",
                (self.session_id,)
            )
            
            # Update success rate
            cursor.execute(
                """
                UPDATE user_sessions 
                SET success_rate = (
                    SELECT CAST(SUM(CASE WHEN response_status = 'success' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) 
                    FROM usage_logs 
                    WHERE session_id = ?
                )
                WHERE id = ?
                """,
                (self.session_id, self.session_id)
            )
            
            conn.commit()
            conn.close()
            logger.info(f"Query logged: {query}")
        except Exception as e:
            logger.error(f"Error logging query: {e}")
    
    def save_path(self, authority, search_term, path, success=True):
        """Save a successful navigation path"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if this path already exists
            cursor.execute(
                "SELECT id, usage_count FROM successful_paths WHERE authority = ? AND search_term = ? AND path = ?",
                (authority, search_term, path)
            )
            result = cursor.fetchone()
            
            if result:
                # Update existing path
                path_id, usage_count = result
                cursor.execute(
                    "UPDATE successful_paths SET success = ?, timestamp = ?, usage_count = ? WHERE id = ?",
                    (
                        1 if success else 0,
                        datetime.datetime.now().isoformat(),
                        usage_count + 1,
                        path_id
                    )
                )
            else:
                # Insert new path
                cursor.execute(
                    "INSERT INTO successful_paths VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        authority,
                        search_term,
                        path,
                        1 if success else 0,
                        datetime.datetime.now().isoformat(),
                        1  # Initial usage count
                    )
                )
            
            conn.commit()
            conn.close()
            logger.info(f"Path saved for {authority}: {path} (success: {success})")
            return True
        except Exception as e:
            logger.error(f"Error saving path: {e}")
            return False
    
    def get_successful_paths(self):
        """Get all successful navigation paths"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT authority, search_term, path, success FROM successful_paths WHERE success = 1"
            )
            
            results = cursor.fetchall()
            conn.close()
            
            # Convert to dictionary format
            paths = {}
            for authority, search_term, path, success in results:
                if authority not in paths:
                    paths[authority] = {}
                if search_term not in paths[authority]:
                    paths[authority][search_term] = []
                paths[authority][search_term].append((path, bool(success)))
            
            return paths
        except Exception as e:
            logger.error(f"Error retrieving successful paths: {e}")
            return {}
    
    def cache_document(self, url, title, authority, content, metadata):
        """Cache a document for faster retrieval"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert metadata to JSON
            metadata_json = json.dumps(metadata)
            
            # Check if document already exists
            cursor.execute("SELECT id, access_count FROM document_cache WHERE url = ?", (url,))
            result = cursor.fetchone()
            
            if result:
                # Update existing document
                doc_id, access_count = result
                cursor.execute(
                    "UPDATE document_cache SET title = ?, authority = ?, content = ?, metadata = ?, last_accessed = ?, access_count = ? WHERE id = ?",
                    (
                        title,
                        authority,
                        content,
                        metadata_json,
                        datetime.datetime.now().isoformat(),
                        access_count + 1,
                        doc_id
                    )
                )
            else:
                # Insert new document
                cursor.execute(
                    "INSERT INTO document_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        url,
                        title,
                        authority,
                        content,
                        metadata_json,
                        datetime.datetime.now().isoformat(),
                        datetime.datetime.now().isoformat(),
                        1  # Initial access count
                    )
                )
            
            conn.commit()
            conn.close()
            logger.info(f"Document cached: {title} ({url})")
            return True
        except Exception as e:
            logger.error(f"Error caching document: {e}")
            return False
    
    def get_cached_document(self, url):
        """Get a cached document"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT title, authority, content, metadata, access_count FROM document_cache WHERE url = ?",
                (url,)
            )
            
            result = cursor.fetchone()
            
            if result:
                title, authority, content, metadata_json, access_count = result
                
                # Update access count and timestamp
                cursor.execute(
                    "UPDATE document_cache SET last_accessed = ?, access_count = ? WHERE url = ?",
                    (
                        datetime.datetime.now().isoformat(),
                        access_count + 1,
                        url
                    )
                )
                
                conn.commit()
                conn.close()
                
                # Parse metadata from JSON
                metadata = json.loads(metadata_json)
                
                return {
                    'title': title,
                    'authority': authority,
                    'content': content,
                    'metadata': metadata
                }
            else:
                conn.close()
                return None
        except Exception as e:
            logger.error(f"Error retrieving cached document: {e}")
            return None
    
    def record_feedback(self, query, score):
        """Record user feedback for a query"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find the most recent log for this query
            cursor.execute(
                "SELECT id FROM usage_logs WHERE query = ? AND session_id = ? ORDER BY timestamp DESC LIMIT 1",
                (query, self.session_id)
            )
            
            result = cursor.fetchone()
            
            if result:
                log_id = result[0]
                
                # Update feedback score
                cursor.execute(
                    "UPDATE usage_logs SET feedback_score = ? WHERE id = ?",
                    (score, log_id)
                )
                
                conn.commit()
                conn.close()
                logger.info(f"Feedback recorded for query: {query} (score: {score})")
                return True
            else:
                conn.close()
                logger.warning(f"No log found for query: {query}")
                return False
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")
            return False
    
    def get_logs_dataframe(self, admin_username, admin_password):
        """Get all logs as a pandas DataFrame"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verify admin credentials
        cursor.execute(
            "SELECT password_hash FROM admin_users WHERE username = ?", 
            (admin_username,)
        )
        result = cursor.fetchone()
        
        if not result or result[0] != hashlib.sha256(admin_password.encode()).hexdigest():
            conn.close()
            logger.warning(f"Invalid admin credentials: {admin_username}")
            return None
        
        # If credentials valid, return logs
        try:
            logs_df = pd.read_sql_query("SELECT * FROM usage_logs", conn)
            
            # Get performance metrics
            performance_df = pd.read_sql_query("SELECT * FROM query_performance", conn)
            
            # Get session stats
            sessions_df = pd.read_sql_query("SELECT * FROM user_sessions", conn)
            
            # Combine into a single DataFrame with additional stats
            result_df = logs_df.copy()
            
            # Add global statistics
            if not result_df.empty:
                result_df['avg_execution_time'] = performance_df['execution_time'].mean()
                result_df['avg_documents'] = performance_df['documents_retrieved'].mean()
                result_df['overall_success_rate'] = (performance_df['successful'].sum() / len(performance_df)) * 100
            
            conn.close()
            logger.info(f"Logs retrieved by admin: {admin_username}")
            return result_df
        except Exception as e:
            conn.close()
            logger.error(f"Error retrieving logs: {e}")
            return None
    
    def get_performance_metrics(self):
        """Get performance metrics for the system"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Query counts
            query_count = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM usage_logs", 
                conn
            ).iloc[0]['count']
            
            # Success rate
            success_rate = pd.read_sql_query(
                "SELECT (SUM(CASE WHEN response_status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as rate FROM usage_logs", 
                conn
            ).iloc[0]['rate']
            
            # Average execution time
            avg_time = pd.read_sql_query(
                "SELECT AVG(execution_time) as avg_time FROM query_performance", 
                conn
            ).iloc[0]['avg_time']
            
            # Average documents retrieved
            avg_docs = pd.read_sql_query(
                "SELECT AVG(documents_retrieved) as avg_docs FROM query_performance", 
                conn
            ).iloc[0]['avg_docs']
            
            # Most common errors
            error_types = pd.read_sql_query(
                "SELECT error_message, COUNT(*) as count FROM usage_logs WHERE response_status = 'error' GROUP BY error_message ORDER BY count DESC LIMIT 5", 
                conn
            )
            
            conn.close()
            
            return {
                'query_count': int(query_count) if not pd.isna(query_count) else 0,
                'success_rate': float(success_rate) if not pd.isna(success_rate) else 0.0,
                'avg_execution_time': float(avg_time) if not pd.isna(avg_time) else 0.0,
                'avg_documents': float(avg_docs) if not pd.isna(avg_docs) else 0.0,
                'error_types': error_types.to_dict('records') if not error_types.empty else []
            }
        except Exception as e:
            logger.error(f"Error retrieving performance metrics: {e}")
            return {
                'query_count': 0,
                'success_rate': 0.0,
                'avg_execution_time': 0.0,
                'avg_documents': 0.0,
                'error_types': []
            }
    
    def end_session(self):
        """End the current session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update session end time
            cursor.execute(
                "UPDATE user_sessions SET end_time = ? WHERE id = ?",
                (
                    datetime.datetime.now().isoformat(),
                    self.session_id
                )
            )
            
            conn.commit()
            conn.close()
            logger.info(f"Session ended: {self.session_id}")
        except Exception as e:
            logger.error(f"Error ending session: {e}")

# Utility function to create a database manager instance
def get_database_manager():
    """Create or retrieve a database manager instance"""
    db_path = "logs/auto_regulations.db"
    return DatabaseManager(db_path)

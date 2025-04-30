# config.py
# Configuration file for Automotive Regulations AI Agent

# Groq API Configuration
GROQ_API_KEY = "your-groq-api-key-here"  # Replace with your actual API key

# Model Configuration
DEFAULT_MODEL = "llama3-70b-8192"  # Default model to use
AVAILABLE_MODELS = [
    "llama3-70b-8192",  # Most capable model
    "llama3-8b-8192",    # Faster, smaller model
    "mixtral-8x7b-32768"  # Alternative option
]

# Regulatory Websites Configuration
REGULATORY_WEBSITES = {
    'UNECE': {
        'base_url': 'https://unece.org',
        'regulations_path': '/transport/vehicle-regulations/regulations',
        'doc_patterns': ['.pdf', '/regulation/']
    },
    'EU': {
        'base_url': 'https://eur-lex.europa.eu',
        'regulations_path': '/EN/legal-content/EN/TXT/?uri=',
        'doc_patterns': ['.pdf', 'CELEX:']
    },
    'NHTSA': {
        'base_url': 'https://www.nhtsa.gov',
        'regulations_path': '/laws-regulations/fmvss',
        'doc_patterns': ['.pdf', '/fmvss/']
    },
    'Transport Canada': {
        'base_url': 'https://tc.canada.ca',
        'regulations_path': '/en/transport-canada/corporate/acts-regulations/regulations/sor-95-147.html',
        'doc_patterns': ['.pdf', '/regulations/']
    },
}

# Logging Configuration
LOG_DB_PATH = "logs/usage_logs.db"

# Default Admin Credentials (for first-time setup only)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"  # Should be changed immediately after first login

# Document Retrieval Settings
MAX_DOCUMENTS = 5
MAX_RETRIEVAL_CHUNKS = 5

# Application Settings
APP_TITLE = "Automotive Regulations AI Assistant"
APP_ICON = "🚗"
APP_LAYOUT = "wide"

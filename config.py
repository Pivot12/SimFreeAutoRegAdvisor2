import os
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env file if it exists
load_dotenv()

# API Keys (load from environment variables or Streamlit secrets)
def get_api_key(key_name, secret_name):
    # Try to get from environment variables first
    api_key = os.getenv(key_name)
    
    # If not found, try to get from Streamlit secrets
    if not api_key and hasattr(st, "secrets") and secret_name in st.secrets:
        api_key = st.secrets[secret_name]
    
    return api_key

FIRECRAWL_API_KEY = get_api_key("FIRECRAWL_API_KEY", "firecrawl_api_key")
CEREBRAS_API_KEY = get_api_key("CEREBRAS_API_KEY", "cerebras_api_key")

# Check if API keys are available, using placeholders for development
if not FIRECRAWL_API_KEY:
    FIRECRAWL_API_KEY = "YOUR_FIRECRAWL_API_KEY"  # Replace with your key for local development
if not CEREBRAS_API_KEY:
    CEREBRAS_API_KEY = "YOUR_CEREBRAS_API_KEY"  # Replace with your key for local development

# Cerebras Llama Scout model configuration
LLAMA_SCOUT_MODEL = "llama-4-scout-17b-16e-instruct"
TEMPERATURE = 0.1
MAX_TOKENS = 2048

# Firecrawl API configuration
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"
MAX_SITES_PER_QUERY = 3  # Reduced from 5 to avoid timeouts
MAX_RESULTS_PER_SITE = 2  # Reduced from 3 to avoid timeouts
CRAWL_DEPTH = 1  # Reduced from 2 to avoid timeouts

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_FILE_PATH = os.path.join(DATA_DIR, "log_data.csv")
LEARNING_CACHE_PATH = os.path.join(DATA_DIR, "learning_cache.json")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Model Context Protocol configuration
# Disable MCP server for cloud deployment to avoid port conflicts
IS_CLOUD_DEPLOYMENT = os.getenv("STREAMLIT_CLOUD") or "STREAMLIT" in os.environ
MCP_ENABLED = False if IS_CLOUD_DEPLOYMENT else True
MCP_PORT = 3000
MCP_HOST = "localhost"

# List of regulatory websites to search (simplified for better reliability)
REGULATORY_WEBSITES = [
    # Focus on more reliable sources first
    "https://www.nhtsa.gov/laws-regulations",
    "https://www.epa.gov/regulations-emissions-vehicles-and-engines",
    "https://ec.europa.eu/growth/sectors/automotive-industry_en",
    "https://unece.org/transport/vehicle-regulations",
    "https://www.acea.auto/publication/automotive-regulatory-guide-2023/",
    
    # Additional sources (will be used if the above don't provide enough data)
    "https://www.vehicle-certification-agency.gov.uk/",
    "https://www.gov.uk/government/organisations/department-for-transport",
    "https://www.mlit.go.jp/en/",
    "https://morth.nic.in/",
    "https://www.infrastructure.gov.au/infrastructure-transport-vehicles/vehicles/vehicle-design-regulation",
]

# Error messages
ERROR_MESSAGES = {
    "firecrawl_api_error": "Error connecting to the Firecrawl API. Please check your API key and try again.",
    "cerebras_api_error": "Error connecting to the Cerebras API. Please check your API key and try again.",
    "no_data_found": "No relevant regulation data found for this query. Please try a different query or be more specific.",
    "general_error": "An unexpected error occurred. Please try again later.",
    "api_key_missing": "API keys are not configured. Please check your configuration.",
}

# Logging configuration
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
LOG_LEVEL = LOG_LEVELS.get(os.getenv("LOG_LEVEL", "INFO"), 20)

# Debug information
print(f"Firecrawl API Key configured: {'Yes' if FIRECRAWL_API_KEY and FIRECRAWL_API_KEY != 'YOUR_FIRECRAWL_API_KEY' else 'No'}")
print(f"Cerebras API Key configured: {'Yes' if CEREBRAS_API_KEY and CEREBRAS_API_KEY != 'YOUR_CEREBRAS_API_KEY' else 'No'}")
print(f"MCP Enabled: {MCP_ENABLED}")
print(f"Cloud Deployment: {IS_CLOUD_DEPLOYMENT}")

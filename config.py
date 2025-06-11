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

# API key loading
FIRECRAWL_API_KEY = get_api_key("FIRECRAWL_API_KEY", "firecrawl_api_key")
CEREBRAS_API_KEY = get_api_key("CEREBRAS_API_KEY", "cerebras_api_key")

# Interregs.net credentials
INTERREGS_EMAIL = get_api_key("INTERREGS_EMAIL", "interregs_email")
INTERREGS_PASSWORD = get_api_key("INTERREGS_PASSWORD", "interregs_password")
INTERREGS_BASE_URL = "https://www.interregs.net"

# Validate required API keys
if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY is required but not configured")
if not CEREBRAS_API_KEY:
    raise ValueError("CEREBRAS_API_KEY is required but not configured")
if not INTERREGS_EMAIL or not INTERREGS_PASSWORD:
    raise ValueError("Interregs.net credentials are required but not configured")

# Cerebras Llama Scout model configuration
LLAMA_SCOUT_MODEL = "llama-4-scout-17b-16e-instruct"
TEMPERATURE = 0.1
MAX_TOKENS = 2048

# Firecrawl API configuration
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"
MAX_SITES_PER_QUERY = 3
MAX_RESULTS_PER_SITE = 2
CRAWL_DEPTH = 1

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_FILE_PATH = os.path.join(DATA_DIR, "log_data.csv")
LEARNING_CACHE_PATH = os.path.join(DATA_DIR, "learning_cache.json")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Model Context Protocol configuration
IS_CLOUD_DEPLOYMENT = os.getenv("STREAMLIT_CLOUD") or "STREAMLIT" in os.environ
MCP_ENABLED = False if IS_CLOUD_DEPLOYMENT else True
MCP_PORT = 3000
MCP_HOST = "localhost"

# Primary regulatory websites - LLM will select most appropriate
REGULATORY_WEBSITES = {
    "US_NHTSA": "https://www.nhtsa.gov/laws-regulations",
    "US_EPA": "https://www.epa.gov/regulations-emissions-vehicles-and-engines", 
    "EU_COMMISSION": "https://ec.europa.eu/growth/sectors/automotive-industry_en",
    "UNECE": "https://unece.org/transport/vehicle-regulations",
    "ACEA": "https://www.acea.auto/publication/automotive-regulatory-guide-2023/",
    "UK_VCA": "https://www.vehicle-certification-agency.gov.uk/",
    "JAPAN_MLIT": "https://www.mlit.go.jp/en/",
    "INDIA_MORTH": "https://morth.nic.in/",
    "AUSTRALIA_INFRASTRUCTURE": "https://www.infrastructure.gov.au/infrastructure-transport-vehicles/vehicles/vehicle-design-regulation"
}

# Website selection criteria for LLM
WEBSITE_SELECTION_CRITERIA = {
    "emissions": ["US_EPA", "EU_COMMISSION", "UNECE"],
    "safety": ["US_NHTSA", "UNECE", "EU_COMMISSION"],
    "homologation": ["EU_COMMISSION", "UNECE", "UK_VCA"],
    "type_approval": ["EU_COMMISSION", "UNECE"],
    "electric_vehicles": ["US_EPA", "EU_COMMISSION", "UNECE"],
    "fuel": ["US_EPA", "EU_COMMISSION"],
    "lighting": ["UNECE", "EU_COMMISSION"],
    "noise": ["UNECE", "EU_COMMISSION"]
}

# Regional mapping
REGION_WEBSITES = {
    "us": ["US_NHTSA", "US_EPA"],
    "usa": ["US_NHTSA", "US_EPA"],
    "united_states": ["US_NHTSA", "US_EPA"],
    "eu": ["EU_COMMISSION", "UNECE"],
    "europe": ["EU_COMMISSION", "UNECE"],
    "european": ["EU_COMMISSION", "UNECE"],
    "uk": ["UK_VCA", "UNECE"],
    "japan": ["JAPAN_MLIT", "UNECE"],
    "india": ["INDIA_MORTH"],
    "australia": ["AUSTRALIA_INFRASTRUCTURE"],
    "global": ["UNECE", "ACEA"]
}

# Error messages
ERROR_MESSAGES = {
    "firecrawl_api_error": "Error connecting to the Firecrawl API. Please check your API key and network connection.",
    "cerebras_api_error": "Error connecting to the Cerebras API. Please check your API key and network connection.", 
    "interregs_api_error": "Error connecting to the Interregs.net database. Please check credentials and network connection.",
    "no_data_found": "No relevant regulation data found for this query. Please try a more specific query or check if the regulation exists.",
    "general_error": "An unexpected error occurred. Please try again later.",
    "api_key_missing": "Required API keys are not configured. Please check your configuration."
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

print(f"Configuration loaded successfully:")
print(f"- Firecrawl API Key: {'Configured' if FIRECRAWL_API_KEY else 'Missing'}")
print(f"- Cerebras API Key: {'Configured' if CEREBRAS_API_KEY else 'Missing'}")
print(f"- Interregs Credentials: {'Configured' if INTERREGS_EMAIL and INTERREGS_PASSWORD else 'Missing'}")
print(f"- Cloud Deployment: {IS_CLOUD_DEPLOYMENT}")

# config.py
# Configuration file for Automotive Regulations AI Agent

# Groq API Configuration
GROQ_API_KEY = "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"

# Model Configuration
DEFAULT_MODEL = "llama3-70b-8192"  # Default model to use
AVAILABLE_MODELS = [
    "llama3-70b-8192",  # Most capable model
    "llama3-8b-8192",    # Faster, smaller model
    "mixtral-8x7b-32768"  # Alternative option
]

# Interregs Authentication
INTERREGS_URL = "https://www.interregs.net/db/index.php?id=ATO-01"
INTERREGS_LOGIN_URL = "https://www.interregs.net/login"
INTERREGS_EMAIL = "neelshah@lucidmotors.com"
INTERREGS_PASSWORD = "eyzzp3iw"

# Regulatory Websites Configuration (backup sources)
REGULATORY_WEBSITES = {
    'UNECE WP.29': {
        'base_url': 'https://unece.org',
        'regulations_path': '/transport/vehicle-regulations',
        'doc_patterns': ['.pdf', '/regulation/', 'wp29', 'WP.29']
    },
    'EU European Commission': {
        'base_url': 'https://transport.ec.europa.eu',
        'regulations_path': '/index_en',
        'doc_patterns': ['.pdf', 'regulation', 'directive', 'mobility']
    },
    'ACEA': {
        'base_url': 'https://www.acea.auto',
        'regulations_path': '/publications-events',
        'doc_patterns': ['.pdf', 'regulatory', 'regulation', 'guide']
    },
    'ISO Road Vehicles': {
        'base_url': 'https://www.iso.org',
        'regulations_path': '/committee/46706.html',
        'doc_patterns': ['.pdf', 'ISO', 'standard', 'TC 22']
    },
    'IEC Road Vehicles': {
        'base_url': 'https://www.iec.ch',
        'regulations_path': '/transportation/electric-vehicles',
        'doc_patterns': ['.pdf', 'IEC', 'standard', 'electric vehicle']
    },
    'NHTSA': {
        'base_url': 'https://www.nhtsa.gov',
        'regulations_path': '/laws-regulations',
        'doc_patterns': ['.pdf', 'FMVSS', 'regulation', 'standard']
    },
    'US EPA': {
        'base_url': 'https://www.epa.gov',
        'regulations_path': '/vehicle-and-engine-certification',
        'doc_patterns': ['.pdf', 'regulation', 'emissions', 'certification']
    },
    'EFTA': {
        'base_url': 'https://www.efta.int',
        'regulations_path': '/eea/eea-legal-order/transport',
        'doc_patterns': ['.pdf', 'regulation', 'vehicles', 'transport']
    },
    'Japan MLIT': {
        'base_url': 'https://www.mlit.go.jp',
        'regulations_path': '/en/road/index.html',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    },
    'China MIIT': {
        'base_url': 'https://www.miit.gov.cn',
        'regulations_path': '/',
        'doc_patterns': ['.pdf', 'standard', 'regulation', 'vehicle']
    },
    'India ARAI': {
        'base_url': 'https://www.araiindia.com',
        'regulations_path': '/regulations-standards',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'AIS']
    },
    'India CMVR': {
        'base_url': 'https://morth.nic.in',
        'regulations_path': '/transport',
        'doc_patterns': ['.pdf', 'CMVR', 'regulation', 'motor vehicle']
    },
    'Transport Canada': {
        'base_url': 'https://tc.canada.ca',
        'regulations_path': '/en/road-transportation/motor-vehicle-safety',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'CMVSS']
    },
    'Australia Vehicle Standards': {
        'base_url': 'https://www.infrastructure.gov.au',
        'regulations_path': '/vehicles/vehicle-standards',
        'doc_patterns': ['.pdf', 'ADR', 'standard', 'regulation']
    },
    'Brazil INMETRO': {
        'base_url': 'https://www.gov.br',
        'regulations_path': '/inmetro/pt-br',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    },
    'South Korea MOLIT': {
        'base_url': 'https://www.molit.go.kr',
        'regulations_path': '/english',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    },
    'Russia Rosavtodor': {
        'base_url': 'https://www.rosavtodor.ru',
        'regulations_path': '/en',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    },
    'Mexico SCT': {
        'base_url': 'https://www.gob.mx',
        'regulations_path': '/sct',
        'doc_patterns': ['.pdf', 'regulation', 'NOM', 'vehicle']
    },
    'South Africa NRCS': {
        'base_url': 'https://www.nrcs.org.za',
        'regulations_path': '/',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    },
    'Argentina ANSV': {
        'base_url': 'https://www.ansv.gob.ar',
        'regulations_path': '/',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    },
    'UK Department for Transport': {
        'base_url': 'https://www.gov.uk',
        'regulations_path': '/government/organisations/department-for-transport',
        'doc_patterns': ['.pdf', 'regulation', 'standard', 'vehicle']
    }
}

# Logging Configuration
LOG_DB_PATH = "logs/usage_logs.db"

# Default Admin Credentials (for first-time setup only)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin0147"  # Should be changed immediately after first login

# Document Retrieval Settings
MAX_DOCUMENTS = 5
MAX_RETRIEVAL_CHUNKS = 5

# Application Settings
APP_TITLE = "Automotive Regulations AI Assistant"
APP_ICON = "🚗"
APP_LAYOUT = "wide"

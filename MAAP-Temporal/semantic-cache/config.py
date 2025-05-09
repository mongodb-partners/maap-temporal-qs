import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Application settings
APP_NAME = "MAAP-Semantic-Cache"
APP_VERSION = "1.0"
APP_DESCRIPTION = "A semantic cache service for storing and retrieving query responses based on semantic similarity"
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Service configuration
SERVICE_HOST = os.getenv("SERVICE_HOST", "0.0.0.0")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8183"))
LOGGER_SERVICE_URL = os.getenv("LOGGER_SERVICE_URL", "http://event-logger:8181")

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "semantic_cache")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "cache")
VECTOR_SEARCH_INDEX_NAME = os.getenv("VECTOR_SEARCH_INDEX_NAME", "cache_vector_index")

# Cache configuration
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.95"))

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "1536"))
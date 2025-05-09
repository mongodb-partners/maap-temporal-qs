import os
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

# Configuration from environment variables with sensible defaults
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "event_logs")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "logs")
LOG_DIR = os.getenv("LOG_DIR", "logs")
FLUSH_INTERVAL = int(os.getenv("FLUSH_INTERVAL", 60))  # seconds
DELETE_LOGS_OLDER_THAN = int(os.getenv("DELETE_LOGS_OLDER_THAN", 30))  # days
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 60))  # TTL for MongoDB docs
LOG_BUFFER_SIZE = int(os.getenv("LOG_BUFFER_SIZE", 1000))  # Force flush at this size
MAX_COLLECTION_SIZE = int(os.getenv("MAX_COLLECTION_SIZE", 1073741824))  # 1GB
MAX_DOCUMENTS = int(os.getenv("MAX_DOCUMENTS", 100000))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8181))
WORKER_COUNT = int(os.getenv("WORKER_COUNT", 0))  # 0 means use default

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

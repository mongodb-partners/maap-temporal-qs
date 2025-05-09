import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError
from typing import Any, Dict, List, Optional
import config
from utils.logger import logger

class MongoDBManager:
    """Manager for MongoDB operations."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(MongoDBManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize MongoDB connection and collections."""
        if self._initialized:
            return
            
        try:
            # Connect to MongoDB
            self.client = MongoClient(
                config.MONGODB_URI,
                w="majority",
                connectTimeoutMS=5000,
                serverSelectionTimeoutMS=5000
            )
            
            # Test connection
            self.client.admin.command('ismaster')
            logger.info("Successfully connected to MongoDB")
            
            # Initialize database and collection
            self.db = self.client[config.MONGODB_DATABASE]
            self.cache_collection = self.db[config.MONGODB_COLLECTION]
            
            # Setup collection and indexes
            self._setup_collection()
            
            self._initialized = True
        except PyMongoError as e:
            logger.error(f"Failed to initialize MongoDB: {e}")
            raise
    
    def _setup_collection(self):
        """Setup collection and create necessary indexes."""
        try:
            # Create collection if it doesn't exist
            if self.cache_collection.name not in self.db.list_collection_names():
                self.db.create_collection(self.cache_collection.name)
                logger.info(f"Created collection: {self.cache_collection.name}")
            
            # Setup vector search index
            self._setup_vector_index()
            
            # Setup TTL index
            self._setup_ttl_index()
        except PyMongoError as e:
            logger.error(f"Failed to setup collection: {e}")
            raise
    
    def _setup_vector_index(self):
        """Setup vector search index."""
        try:
            # Define the vector search index
            index_definition = {
                "name": config.VECTOR_SEARCH_INDEX_NAME,
                "type": "vectorSearch",
                "definition": {
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": config.VECTOR_DIMENSION,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "user_id"},
                    ]
                },
            }
            
            # Create the index if it doesn't exist
            existing_indexes = [idx["name"] for idx in self.cache_collection.list_search_indexes()]
            if config.VECTOR_SEARCH_INDEX_NAME not in existing_indexes:
                self.cache_collection.create_search_index(model=index_definition)
                logger.info(f"Created vector search index: {config.VECTOR_SEARCH_INDEX_NAME}")
            else:
                logger.info(f"Vector search index already exists: {config.VECTOR_SEARCH_INDEX_NAME}")
        except PyMongoError as e:
            logger.error(f"Failed to setup vector index: {e}")
            # Continue even if index creation fails - it might be created via Atlas UI
    
    def _setup_ttl_index(self):
        """Setup TTL index for automatic cache expiration."""
        try:
            index_info = self.cache_collection.index_information()
            if "timestamp_ttl_idx" not in index_info:
                self.cache_collection.create_index(
                    [("timestamp", pymongo.ASCENDING)],
                    expireAfterSeconds=config.CACHE_TTL_SECONDS,
                    name="timestamp_ttl_idx"
                )
                logger.info(f"Created TTL index with expiry: {config.CACHE_TTL_SECONDS} seconds")
        except PyMongoError as e:
            logger.error(f"Failed to setup TTL index: {e}")
    
    def insert_cache_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Insert a cache entry into the database.
        
        Args:
            entry: Cache entry as dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.cache_collection.insert_one(entry)
            return bool(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to insert cache entry: {e}")
            return False
    
    def find_similar_query(
        self,
        user_id: str,
        embedding: List[float],
        threshold: float = config.SIMILARITY_THRESHOLD
    ) -> Optional[Dict[str, Any]]:
        """
        Find a similar query in the cache using vector search.
        
        Args:
            user_id: User identifier
            embedding: Query embedding vector
            threshold: Similarity threshold (0-1)
            
        Returns:
            Dict or None: The cached entry if found with sufficient similarity
        """
        try:
            results = self.cache_collection.aggregate([
                {
                    "$vectorSearch": {
                        "index": config.VECTOR_SEARCH_INDEX_NAME,
                        "path": "embedding",
                        "queryVector": embedding,
                        "numCandidates": 200,
                        "limit": 1,
                        "filter": {"user_id": user_id},
                    }
                },
                {
                    "$project": {
                        "score": {"$meta": "vectorSearchScore"},
                        "query": 1,
                        "response": 1,
                        "_id": 0,
                    }
                },
            ])
            
            result = next(results, None)
            
            if result and result.get("score", 0) > threshold:
                logger.info(f"Found cache entry with similarity: {result.get('score')}")
                return result
                
            return None
        except PyMongoError as e:
            logger.error(f"Vector search failed: {e}")
            return None
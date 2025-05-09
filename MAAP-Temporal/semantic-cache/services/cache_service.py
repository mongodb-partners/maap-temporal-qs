from typing import Dict, List, Optional, Any
from database.mongodb import MongoDBManager
from services.bedrock_service import get_bedrock_service
from models.pydantic_models import CacheEntry, QueryRequest
import config
from utils.logger import logger

class CacheService:
    """Service for semantic cache operations."""
    
    def __init__(self):
        """Initialize cache service with MongoDB and Bedrock services."""
        self.mongodb = MongoDBManager()
        self.bedrock_service = get_bedrock_service()
        self.similarity_threshold = config.SIMILARITY_THRESHOLD
    
    async def save_to_cache(self, entry: CacheEntry) -> Dict[str, Any]:
        """
        Save an entry to the semantic cache.
        
        Args:
            entry: Cache entry to save
            
        Returns:
            Dict: Status response
        """
        try:
            # Generate embedding if not provided
            if not entry.embedding:
                entry.embedding = await self.bedrock_service.generate_embedding(entry.query)
            
            # Skip if embedding generation failed
            if not entry.embedding:
                return {
                    "message": "Failed to save to cache",
                    "error": "Could not generate embedding"
                }
            
            # Convert to dictionary and save to MongoDB
            entry_dict = entry.to_dict()
            success = self.mongodb.insert_cache_entry(entry_dict)
            
            if success:
                logger.info(f"Saved query-response to cache for user {entry.user_id}")
                return {"message": "Successfully saved to cache"}
            else:
                return {
                    "message": "Failed to save to cache",
                    "error": "Database insert failed"
                }
                
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")
            return {
                "message": "Failed to save to cache",
                "error": str(e)
            }
    
    async def lookup_cache(self, request: QueryRequest) -> Dict[str, Any]:
        """
        Look up a query in the semantic cache.
        
        Args:
            request: Query request
            
        Returns:
            Dict: Response with cached content or empty string if not found
        """
        try:
            # Generate embedding for the query
            embedding = await self.bedrock_service.generate_embedding(request.query)
            
            if not embedding:
                logger.error("Failed to generate embedding for cache lookup")
                return {"response": "", "error": "Failed to generate embedding"}
            
            # Look up in cache
            result = self.mongodb.find_similar_query(
                request.user_id,
                embedding,
                self.similarity_threshold
            )
            
            if result:
                logger.info(f"Cache hit for user {request.user_id}")
                return {"response": result["response"]}
            
            logger.info(f"Cache miss for user {request.user_id}")
            return {"response": "cache_miss"}
            
        except Exception as e:
            logger.error(f"Error processing cache lookup: {e}")
            return {"response": "", "error": str(e)}
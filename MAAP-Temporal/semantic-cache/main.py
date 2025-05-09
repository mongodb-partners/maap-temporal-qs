from fastapi import FastAPI, Depends, HTTPException,status
import uvicorn

# Import from local modules
import config
from utils.logger import logger
from models.pydantic_models import QueryRequest, CacheEntry, CacheResponse, CacheSaveResponse
from services.cache_service import CacheService

# Initialize FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description=config.APP_DESCRIPTION
)

# Dependencies
def get_cache_service() -> CacheService:
    """Dependency to get cache service instance."""
    try:
        return CacheService()
    except Exception as e:
        logger.error(f"Failed to initialize cache service: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Service initialization failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/save_to_cache", response_model=CacheSaveResponse)
async def save_to_cache(
    entry: CacheEntry,
    cache_service: CacheService = Depends(get_cache_service)
):
    """
    Save a query-response entry to the semantic cache.
    
    This endpoint stores a query and its response in the cache, generating
    an embedding vector for semantic similarity matching.
    
    Args:
        entry: The cache entry containing query, response, and user information
        
    Returns:
        Status message indicating success or failure
    """
    return await cache_service.save_to_cache(entry)

@app.post("/read_cache", response_model=CacheResponse)
async def read_cache(
    request: QueryRequest,
    cache_service: CacheService = Depends(get_cache_service)
):
    """
    Check if a semantically similar query exists in the cache.
    
    This endpoint looks up a query in the semantic cache by generating
    an embedding and finding the most similar cached queries.
    
    Args:
        request: The request containing user ID and query
        
    Returns:
        The cached response if found, otherwise an empty string
    """
    return await cache_service.lookup_cache(request)

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=config.SERVICE_HOST, 
        port=config.SERVICE_PORT,
        reload=config.DEBUG
    )
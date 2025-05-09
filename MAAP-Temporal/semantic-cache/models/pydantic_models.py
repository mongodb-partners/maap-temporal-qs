from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

class QueryRequest(BaseModel):
    """Model for cache lookup requests."""
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="The query text to look up")

class CacheEntry(BaseModel):
    """Model for cache entries."""
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="The query text")
    response: str = Field(..., description="The cached response")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of the cache entry")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding of the query")


    def parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """Parse timestamp string to datetime object."""
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert model to dictionary for MongoDB storage."""
        result = self.dict(exclude_none=True)
        
        # Ensure timestamp is a datetime object
        if isinstance(self.timestamp, str):
            result["timestamp"] = self.parse_timestamp(self.timestamp)
        elif self.timestamp is None:
            result["timestamp"] = datetime.now(timezone.utc)
            
        return result

class CacheResponse(BaseModel):
    """Model for cache lookup responses."""
    response: str = Field(..., description="The cached response or empty string if not found")
    error: Optional[str] = Field(None, description="Error message if applicable")

class CacheSaveResponse(BaseModel):
    """Model for cache save responses."""
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if applicable")
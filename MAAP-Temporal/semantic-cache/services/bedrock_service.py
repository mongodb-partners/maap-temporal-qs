import json
import boto3
from typing import List, Optional
from functools import lru_cache
import config
from utils.logger import logger

class BedrockService:
    """Service for AWS Bedrock operations."""
    
    def __init__(self, region_name: str = config.AWS_REGION):
        """
        Initialize the Bedrock service.
        
        Args:
            region_name: AWS region name
        """
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.embedding_model_id = config.EMBEDDING_MODEL_ID
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding vector for the given text using Bedrock.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List[float]: Embedding vector or empty list on failure
        """
        try:
            payload = {"inputText": text}
            response = self.client.invoke_model(
                modelId=self.embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload)
            )
            
            result = json.loads(response["body"].read())
            embedding = result.get("embedding", [])
            
            if not embedding:
                logger.error(f"Empty embedding returned for text: {text[:50]}...")
                return []
                
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []

@lru_cache()
def get_bedrock_service() -> BedrockService:
    """
    Get a cached Bedrock service instance.
    
    Returns:
        BedrockService: Bedrock service instance
    """
    return BedrockService()
from typing import Dict, List, Any, Optional
import httpx

from mcp.server.fastmcp import FastMCP
from datetime import datetime

import mcp_config as mcp_config
from bedrock_service import get_bedrock_service
from mongodb_service import get_mongodb_service
from tavily import TavilyClient
from logger import logger

# Initialize FastMCP server
mcp_server = FastMCP(
    title=mcp_config.APP_NAME,
    version=mcp_config.APP_VERSION,
    description=mcp_config.APP_DESCRIPTION,
    instructions="This server provides tools for MongoDB vector search and document processing.",
    dependencies=["pymongo"],
)

# Initialize services
bedrock_service = get_bedrock_service()
mongodb_service = get_mongodb_service()


# region ai-memory
@mcp_server.tool(description="Store a message in AI memory")
async def store_memory(
    conversation_id: str,
    text: str,
    message_type: str,
    user_id,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a message to conversation history.

    Args:
        conversation_id: ID of the conversation
        text: Content of the message
        message_type: Type of message ("human" or "ai")
        user_id: ID of the user
        timestamp: Optional UTC timestamp

    Returns:
        API response as a dictionary
    """
    if user_id is None:
        if user_id is None:
            raise ValueError(
                "user_id must be provided either in the method call or when creating the client"
            )

    if message_type not in ["human", "ai"]:
        raise ValueError("message_type must be either 'human' or 'ai'")

    payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "type": message_type,
        "text": text,
    }

    if timestamp:
        payload["timestamp"] = timestamp

    client = httpx.AsyncClient(timeout=300.0)
    try:
        response = await client.post(
            f"{mcp_config.AI_MEMORY_SERVICE_URL}/conversation/", json=payload
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(
            f"Error adding message to memory: {e.response.status_code} - {e.response.text}"
        )
        return {"error": str(e)}


@mcp_server.tool(description="Get relevant AI memory with context and summary")
async def retrieve_memory(user_id: str, text: str) -> Dict[str, Any]:
    """
    Comprehensive memory retrieval: finds relevant memories, context, and generates a summary.

    Args:
        user_id: ID of the user
        text: Query text to find relevant memories


    Returns:
        Dictionary containing:
        - memory_items: Directly relevant conversation messages
        - context: Surrounding context of the conversation
        - conversation_summary: Summary of the conversation
        - similar_memories: Similar memory nodes from the memory tree
    """

    try:
        if user_id is None:
            if user_id is None:
                raise ValueError(
                    "user_id must be provided either in the method call or when creating the client"
                )

        params = {"user_id": user_id, "text": text}

        client = httpx.AsyncClient(timeout=1000.0)
        response = await client.get(
            f"{mcp_config.AI_MEMORY_SERVICE_URL}/retrieve_memory/", params=params
        )
        response.raise_for_status()
        return {
            "related_conversation": response.json().get("related_conversation", ""),
            "conversation_summary": response.json().get("conversation_summary", ""),
            "similar_memories": response.json().get("similar_memories", ""),
        }

    except httpx.HTTPError as e:
        logger.error(
            f"Error retrieving memory: {e.response.status_code} - {e.response.text}"
        )
        return {
            "related_conversation": f"Error retrieving memory: {e.response.status_code} - {e.response.text}",
            "conversation_summary": "",
            "similar_memories": "",
        }


# endregion ai-memory

# region semantic-cache


# Register semantic_cache tools
@mcp_server.tool(description="Cache AI response for similar queries")
async def semantic_cache_response(
    user_id: str, query: str, response: str, timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cache an AI response for future similar queries.
    Args:
        query: Original query text
        response: AI-generated response to cache
        user_id: User ID for this cache entry
    Returns:
        Dictionary with status and cache entry ID
    """
    if user_id is None:
        if user_id is None:
            raise ValueError(
                "user_id must be provided either in the method call or when creating the client"
            )

    payload = {
        "user_id": user_id,
        "query": query,
        "response": response,
    }

    if timestamp:
        payload["timestamp"] = timestamp

    client = httpx.AsyncClient(timeout=300.0)
    try:
        response = await client.post(
            f"{mcp_config.SEMANTIC_CACHE_SERVICE_URL}/save_to_cache", json=payload
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error: {e.response.status_code} - {e.response.text}")
        return {"error": str(e)}


@mcp_server.tool(description="Get cached response for similar query")
async def check_semantic_cache(user_id: str, query: str) -> Dict[str, Any]:
    """
    Retrieve a cached response for a semantically similar query.
    Args:
        query: Query text to find similar cached responses
        user_id: User ID to filter cache entries
    Returns:
        Dictionary with cached response if found
    """
    if user_id is None:
        if user_id is None:
            raise ValueError(
                "user_id must be provided either in the method call or when creating the client"
            )

    payload = {
        "user_id": user_id,
        "query": query,
    }

    client = httpx.AsyncClient(timeout=300.0)
    try:
        response = await client.post(
            f"{mcp_config.SEMANTIC_CACHE_SERVICE_URL}/read_cache", json=payload
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error: {e.response.status_code} - {e.response.text}")
        return {"error": str(e)}


# endregion semantic-cache


# region mongodb search
@mcp_server.tool(
    description="""This tool provides all the necessary information required for the user's queries. 
                 This tool can Search MongoDB collections using advanced hybrid search algorithms that combine vector similarity and keyword matching.
    
    This tool executes a hybrid search on the user's MongoDB collections to find the most relevant documents based on both 
    semantic similarity (vector search) and keyword matching (full-text search). The results are weighted and combined to 
    provide comprehensive, contextually relevant information.
    
    Parameters:
    - query (str): The search query text. Can be a question, phrase, or keywords related to the information you're seeking.
    - user_id (str): The unique identifier for the user whose data collections should be searched.
    - weight (float, default=0.5): Balance between vector and text search. Values closer to 0 favor keyword matching, 
      values closer to 1 favor semantic similarity. Range: 0.0 - 1.0.
    - limit (int, default=10): Maximum number of results to return. Higher values provide more comprehensive results 
      but may include less relevant documents.
    
    Returns:
    - Dict[str, List[Dict[str, Any]]]: A dictionary containing search results organized by collection name. Each result 
      includes the document content, metadata, relevance score, and match highlights.
    
    Usage Notes:
    - More specific queries generally yield better results
    - Use natural language questions for best semantic matching
    - The tool automatically searches across all collections accessible to the user
    - Results are returned in descending order of relevance
    - Document snippets may be truncated for large documents
    """
)
async def hybrid_search(
    query: str, user_id: str, weight=0.5, limit=10
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Perform a hybrid search operation on MongoDB by combining full-text and vector (semantic) search results.
    """
    limit=int(limit)
    weight=float(weight)
    embedding = bedrock_service.generate_embeddings([query])[0]
    collecton = mongodb_service.get_collection(mcp_config.COLLECTION_NAME)

    pipeline = [
        {
            "$search": {
                "index": mcp_config.FULLTEXT_SEARCH_FIELD,
                "text": {"query": query, "path": mcp_config.FULLTEXT_SEARCH_FIELD},
            }
        },
        {"$match": {"metadata.user_id": user_id}},
        {"$addFields": {"fts_score": {"$meta": "searchScore"}}},
        {"$setWindowFields": {"output": {"maxScore": {"$max": "$fts_score"}}}},
        {
            "$addFields": {
                "normalized_fts_score": {"$divide": ["$fts_score", "$maxScore"]}
            }
        },
        {
            "$project": {
                "text": 1,
                "normalized_fts_score": 1,
            }
        },
        {
            "$unionWith": {
                "coll": mcp_config.COLLECTION_NAME,
                "pipeline": [
                    {
                        "$vectorSearch": {
                            "index": mcp_config.VECTOR_SEARCH_INDEX_NAME,
                            "queryVector": embedding,
                            "path": mcp_config.VECTOR_SEARCH_FIELD,
                            "numCandidates": limit * 10,
                            "limit": limit,
                            "filter": {"metadata.user_id": user_id},
                        }
                    },
                    {"$addFields": {"vs_score": {"$meta": "vectorSearchScore"}}},
                    {
                        "$setWindowFields": {
                            "output": {"maxScore": {"$max": "$vs_score"}}
                        }
                    },
                    {
                        "$addFields": {
                            "normalized_vs_score": {
                                "$divide": ["$vs_score", "$maxScore"]
                            }
                        }
                    },
                    {
                        "$project": {
                            "text": 1,
                            "normalized_vs_score": 1,
                        }
                    },
                ],
            }
        },
        {
            "$group": {
                "_id": "$_id",  # Group by document ID
                "fts_score": {"$max": "$normalized_fts_score"},
                "vs_score": {"$max": "$normalized_vs_score"},
                "text_field": {"$first": "$text"},
            }
        },
        {
            "$addFields": {
                "hybrid_score": {
                    "$add": [
                        {"$multiply": [weight, {"$ifNull": ["$vs_score", 0]}]},
                        {"$multiply": [1 - weight, {"$ifNull": ["$fts_score", 0]}]},
                    ]
                }
            }
        },
        {"$sort": {"hybrid_score": -1}},  # Sort by combined hybrid score descending
        {"$limit": limit},  # Limit final output
        {
            "$project": {
                "_id": 1,
                "fts_score": 1,
                "vs_score": 1,
                "score": "$hybrid_score",
                "text": "$text_field",
            }
        },
    ]
    # Execute the aggregation pipeline and return the results
    try:
        results = list(collecton.aggregate(pipeline))
        return results
    except Exception as e:
        logger.error(f"Error in hybrid_search: {e}")
        raise


# endregion mongodb search


@mcp_server.tool(description="Search Web using Tavily API")
async def search_web(query: str) -> List[str]:
    """
    Performs a web search using Tavily API.

    Args:
        query (str): The search query string.

    Returns:
        List[str]: Retrieved document contents from the web.
    """
    tavily_client = (
        TavilyClient(api_key=mcp_config.TAVILY_API_KEY) if mcp_config.TAVILY_API_KEY else None
    )

    documents = tavily_client.search(query)
    return [doc["content"] for doc in documents.get("results", [])]


@mcp_server.prompt("conversation_prompt")
def conversation_prompt(
    user_id: str, conversation_summary: str | List, similar_memories: str | List
) -> List[Dict[str, Any]]:
    """Generate a prompt for conversation with memory context."""
    # Add memory context to messages with proper content format
    memory_text = f"My user_id is:{user_id}\n\n Here is a memory knowledge about me collected over various conversations: {similar_memories}\n\n  Here is some relevant context from your previous conversations with me: {conversation_summary}\n\nPlease keep this in mind when responding to my query, but don't explicitly reference this context unless necessary."
    return [{"role": "user", "content": memory_text}]


@mcp_server.resource("health://status")
def health_check() -> Dict[str, str]:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": mcp_config.APP_NAME,
        "timestamp": datetime.now().isoformat(),
    }


@mcp_server.resource("maap://config")
def mongodb_config() -> Dict[str, Any]:
    """Get MongoDB configuration information."""
    return mcp_config.get_config()


if __name__ == "__main__":
    mcp_server.run()

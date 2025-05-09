# models.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ImageProcessingParams:
    """Parameters for the ImageProcessingWorkflow."""

    image_path: str


@dataclass
class SemanticCacheParams:
    """Parameters for the SemanticCacheCheckWorkflow."""

    user_id: str
    query: str


@dataclass
class MemoryRetrievalParams:
    """Parameters for the MemoryRetrievalWorkflow."""

    user_id: str
    query: str


@dataclass
class PromptRetrievalParams:
    """Parameters for the PromptRetrievalWorkflow."""

    user_id: str
    conversation_summary: str
    similar_memories: str


@dataclass
class AIGenerationParams:
    """Parameters for the AIGenerationWorkflow."""

    messages: List[Dict[str, Any]]


@dataclass
class MemoryStorageParams:
    """Parameters for the MemoryStorageWorkflow."""

    conversation_id: str
    user_id: str
    user_query: str
    ai_response: str


@dataclass
class CacheStorageParams:
    """Parameters for the CacheStorageWorkflow."""

    user_id: str
    query: str
    response: str


@dataclass
class ProcessQueryParams:
    """Parameters for the QueryProcessingWorkflow."""

    user_id: str
    query: str
    conversation_id: str
    previous_messages: Optional[List[Dict[str, Any]]] = None
    image_path: Optional[str] = None


@dataclass
class ToolExecutionParams:
    """Parameters for executing a tool via MCP."""

    server_name: str
    tool_name: str
    arguments: Dict[str, Any]


@dataclass
class AIProcessingParams:
    """Parameters for the AIProcessingWorkflow."""

    user_id: str
    query: str
    conversation_id: str
    tools: Optional[List[Dict[str, Any]]] = None
    files: Optional[List[Dict[str, Any]]] = None


@dataclass
class ResourceReadParams:
    """Parameters for reading a resource via MCP."""

    server_name: str
    resource_id: str


@dataclass
class PromptGetParams:
    """Parameters for retrieving a prompt from MCP."""

    server_name: str
    prompt_name: str
    arguments: Dict[str, Any]


@dataclass
class ImageProcessingResult:
    """Result of image processing."""

    image_bytes: bytes
    image_format: str


@dataclass
class DataIngestionParams:
    """Parameters for the data ingestion activity."""

    user_id: str
    mongodb_uri: str
    urls: Optional[List[str]] = None
    files: Optional[List[str]] = None
    mongodb_database: str = "maap_data_loader"
    mongodb_collection: str = "document"
    mongodb_index_name: str = "document_vector_index"
    mongodb_text_field: str = "text"
    mongodb_embedding_field: str = "embedding"

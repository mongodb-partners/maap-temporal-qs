# workflows.py
from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
import json

with workflow.unsafe.imports_passed_through():
    from activities import (
        mcp_call_tool,
        mcp_read_resource,
        mcp_get_prompt,
        invoke_bedrock,
        ingest_data_activity,
        process_image,
        # Import the parameter dataclasses
        PromptGetParams,
        ToolExecutionParams,
        ImageProcessingResult,
        ImageProcessingParams,
        SemanticCacheParams,
        MemoryRetrievalParams,
        PromptRetrievalParams,
        AIGenerationParams,
        MemoryStorageParams,
        CacheStorageParams,
        DataIngestionParams

    )

logger = workflow.logger

@workflow.defn
class ImageProcessingWorkflow:
    def __init__(self):
        self._current_stage = "image_processing"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: ImageProcessingParams) -> ImageProcessingResult:
        """Process an image and return the result."""
        self._progress = {"status": "processing_image"}
        try:
            image_result = await workflow.execute_activity(
                process_image,
                params.image_path,
                start_to_close_timeout=timedelta(minutes=2),
            )
            self._progress = {"status": "completed"}
            return image_result
        except Exception as e:
            logger.error(f"Error in ImageProcessingWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class SemanticCacheCheckWorkflow:
    def __init__(self):
        self._current_stage = "cache_check"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: SemanticCacheParams) -> Dict[str, Any]:
        """Check semantic cache for similar queries."""
        self._progress = {"status": "checking_cache"}
        try:
            cache_result = await workflow.execute_activity(
                mcp_call_tool,
                ToolExecutionParams(
                    server_name="maap",
                    tool_name="check_semantic_cache",
                    arguments={
                        "user_id": params.user_id,
                        "query": params.query,
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            processed_result = {"cache_hit": False, "response": None}
            
            if cache_result and cache_result.get("isError") is False:
                cache_data = cache_result.get("result")
                if cache_data:
                    try:
                        cache_data_json = json.loads(cache_data)
                        if "response" in cache_data_json:
                            cached_response = cache_data_json["response"]
                            if cached_response != "cache_miss":
                                processed_result = {
                                    "cache_hit": True,
                                    "response": cached_response
                                }
                    except (json.JSONDecodeError, IndexError, AttributeError) as e:
                        logger.warning(f"Failed to parse cache response: {str(e)}")
            
            self._progress = {"status": "completed"}
            return processed_result
        except Exception as e:
            logger.error(f"Error in SemanticCacheCheckWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class MemoryRetrievalWorkflow:
    def __init__(self):
        self._current_stage = "memory_retrieval"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: MemoryRetrievalParams) -> Dict[str, Any]:
        """Retrieve relevant memories for the given user and query."""
        self._progress = {"status": "retrieving_memories"}
        try:
            memory_result = await workflow.execute_activity(
                mcp_call_tool,
                ToolExecutionParams(
                    server_name="maap",
                    tool_name="retrieve_memory",
                    arguments={
                        "user_id": params.user_id,
                        "text": params.query,
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            memories = {
        
                "conversation_summary": "",
                "similar_memories": ""
            }
            
            if memory_result and memory_result.get("isError") is False:
                memory_response = memory_result.get("result")
                if memory_response:
                    try:
                        memory_data = json.loads(memory_response)
                        #memories["related_conversation"] = memory_data.get("related_conversation", "")
                        memories["conversation_summary"] = memory_data.get("conversation_summary", "")
                        memories["similar_memories"] = memory_data.get("similar_memories", "")
                        logger.info("Memory retrieved successfully.")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse memory response: {str(e)}")
                else:
                    logger.info("No memory found for this user.")
            else:
                logger.error("Failed to retrieve memory.")
            
            self._progress = {"status": "completed"}
            return memories
        except Exception as e:
            logger.error(f"Error in MemoryRetrievalWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class PromptRetrievalWorkflow:
    def __init__(self):
        self._current_stage = "prompt_retrieval"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: PromptRetrievalParams) -> Dict[str, Any]:
        """Retrieve prompt for conversation."""
        self._progress = {"status": "retrieving_prompt"}
        try:
            prompt_result = await workflow.execute_activity(
                mcp_get_prompt,
                PromptGetParams(
                    server_name="maap",
                    prompt_name="conversation_prompt",
                    arguments={
                        "user_id": params.user_id,
                        "conversation_summary": str(params.conversation_summary),
                        "similar_memories": str(params.similar_memories),
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            prompt_text = ""
            if prompt_result and prompt_result.get("isError") is False:
                prompt_response = prompt_result.get("result")
                if prompt_response:
                    prompt_text = prompt_response
                    logger.info("Prompt retrieved successfully.")
                else:
                    logger.info("No prompt found for this user.")
                    # Create fallback prompt
                    memory_text = f"My user_id is:{params.user_id}\n\n Here is a memory knowledge about me collected over various conversations: {params.similar_memories}\n\n Here is some relevant context from your previous conversations with me: {params.conversation_summary}\n\nPlease keep this in mind when responding to my query, but don't explicitly reference this context unless necessary."
                    prompt_text = {
                        "role": "user",
                        "content": [{"text": memory_text}],
                    }
            else:
                logger.error("Failed to retrieve prompt.")
                # fallback to default prompt
                memory_text = f"My user_id is:{params.user_id}\n\n Here is a memory knowledge about me collected over various conversations: {params.similar_memories}\n\n  Here is some relevant context from your previous conversations with me: {params.conversation_summary}\n\nPlease keep this in mind when responding to my query, but don't explicitly reference this context unless necessary."
                prompt_text = {
                    "role": "user",
                    "content": [{"text": memory_text}],
                }
            
            self._progress = {"status": "completed"}
            return prompt_text
        except Exception as e:
            logger.error(f"Error in PromptRetrievalWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class AIGenerationWorkflow:
    def __init__(self):
        self._current_stage = "ai_generation"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: AIGenerationParams) -> Any:
        """Generate AI response using Bedrock."""
        self._progress = {"status": "generating_response"}
        try:
            response_text = await workflow.execute_activity(
                invoke_bedrock,
                params.messages,
                start_to_close_timeout=timedelta(minutes=10),
            )
            
            self._progress = {"status": "completed"}
            return response_text
        except Exception as e:
            logger.error(f"Error in AIGenerationWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class MemoryStorageWorkflow:
    def __init__(self):
        self._current_stage = "memory_storage"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: MemoryStorageParams) -> bool:
        """Store conversation in memory."""
        self._progress = {"status": "storing_memory"}
        try:
            # Store user message
            user_result = await workflow.execute_activity(
                mcp_call_tool,
                ToolExecutionParams(
                    server_name="maap",
                    tool_name="store_memory",
                    arguments={
                        "conversation_id": params.conversation_id,
                        "text": params.user_query,
                        "message_type": "human",
                        "user_id": params.user_id
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            # Store AI response
            ai_result = await workflow.execute_activity(
                mcp_call_tool,
                ToolExecutionParams(
                    server_name="maap",
                    tool_name="store_memory",
                    arguments={
                        "conversation_id": params.conversation_id,
                        "text": params.ai_response,
                        "message_type": "ai",
                        "user_id": params.user_id,
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            self._progress = {"status": "completed"}
            return True
        except Exception as e:
            logger.error(f"Error in MemoryStorageWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class CacheStorageWorkflow:
    def __init__(self):
        self._current_stage = "cache_storage"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: CacheStorageParams) -> bool:
        """Cache response for future similar queries."""
        self._progress = {"status": "caching_response"}
        try:
            cache_result = await workflow.execute_activity(
                mcp_call_tool,
                ToolExecutionParams(
                    server_name="maap",
                    tool_name="semantic_cache_response",
                    arguments={
                        "user_id": params.user_id,
                        "query": params.query,
                        "response": params.response,
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            self._progress = {"status": "completed"}
            return True
        except Exception as e:
            logger.error(f"Error in CacheStorageWorkflow: {str(e)}")
            self._progress = {"status": "failed", "error": str(e)}
            raise


@workflow.defn
class DataIngestionWorkflow:
    def __init__(self):
        self._current_stage = "data_ingestion"
        self._progress = {}
        self._activity_details = {}
        self._detailed_progress = []

    @workflow.signal
    async def record_activity_heartbeat(
        self, activity_name: str, message: str, timestamp: Optional[str] = None
    ):
        """Signal handler to record activity heartbeats."""
        if activity_name not in self._activity_details:
            self._activity_details[activity_name] = []
        self._activity_details[activity_name].append(
            {"message": message, "timestamp": timestamp or workflow.now().isoformat()}
        )
        # Add to detailed progress log
        self._detailed_progress.append(
            {
                "activity": activity_name,
                "message": message,
                "timestamp": timestamp or workflow.now().isoformat(),
            }
        )
        # Notify external systems
        await workflow.update_handler()

    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """Query handler to retrieve current progress."""
        return {
            "current_stage": self._current_stage,
            "progress": self._progress,
            "activity_details": self._activity_details,
            "detailed_progress": self._detailed_progress,
        }

    @workflow.run
    async def run(self, params: DataIngestionParams) -> Dict[str, Any]:
        """
        Run the data ingestion workflow that processes files and URLs.
        
        Args:
            params: DataIngestionParams containing user_id, urls, files, and MongoDB config
            
        Returns:
            Dict with ingestion results
        """
        self._progress = {"status": "starting", "message": "Starting data ingestion workflow"}
        
        try:
            # Step 1: Validate input parameters
            self._progress = {"status": "validating", "message": "Validating input parameters"}
            
            if not params.user_id:
                raise ValueError("User ID is required")
                
            if not params.mongodb_uri:
                raise ValueError("MongoDB URI is required")
                
            if not (params.urls or params.files):
                raise ValueError("Either URLs or files must be provided")
                
            # Step 2: Execute the data ingestion activity
            self._progress = {"status": "ingesting", "message": "Ingesting data"}
            
            result = await workflow.execute_activity(
                ingest_data_activity,
                params,
                start_to_close_timeout=timedelta(minutes=15)
            )
            
            # Step 3: Process the result
            if result["success"]:
                self._progress = {
                    "status": "completed", 
                    "message": "Data ingestion completed successfully"
                }
            else:
                self._progress = {
                    "status": "failed", 
                    "message": f"Data ingestion failed: {result.get('message')}"
                }
                
            return {
                "success": result["success"],
                "message": result["message"],
                "details": result.get("details", ""),
                "user_id": params.user_id,
                "file_count": len(params.files) if params.files else 0,
                "url_count": len(params.urls) if params.urls else 0
            }
            
        except Exception as e:
            self._progress = {"status": "error", "message": f"Error in workflow: {str(e)}"}
            workflow.logger.error(f"Error in DataIngestionWorkflow: {str(e)}")
            return {
                "success": False,
                "message": f"Workflow error: {str(e)}",
                "details": "",
                "user_id": params.user_id,
                "file_count": len(params.files) if params.files else 0,
                "url_count": len(params.urls) if params.urls else 0
            }
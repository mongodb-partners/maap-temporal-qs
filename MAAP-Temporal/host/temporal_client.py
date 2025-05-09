# temporal_client.py
import asyncio
from temporalio.client import Client
from typing import Optional, Any, Dict
from maap_mcp.mcp_config import TEMPORAL_HOST, TEMPORAL_PORT
class TemporalClientManager:
    """
    A singleton manager for the Temporal client connections.
    """
    _instance: Optional["TemporalClientManager"] = None
    _client: Optional[Client] = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls) -> "TemporalClientManager":
        """Get or create the client manager instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = TemporalClientManager()
                await cls._instance.initialize()
            return cls._instance
    
    async def initialize(self) -> None:
        """Initialize the Temporal client connection."""
        if self._client is None:
            # Connect to Temporal server
            self._client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
    
    async def execute_workflow(self, workflow_name: str, args: Any, **kwargs) -> Any:
        """
        Execute a Temporal workflow.
        
        Args:
            workflow_name: The name of the workflow to execute
            args: The arguments to pass to the workflow
            **kwargs: Additional arguments to pass to the workflow start method
            
        Returns:
            The result of the workflow execution
        """
        if not self._client:
            raise RuntimeError("Temporal client not initialized")
        
        # Import the workflow dynamically
        workflow_class = self._get_workflow_class(workflow_name)
        
        # Execute the workflow
        result = await self._client.execute_workflow(
            workflow_class.run,
            args,
            **kwargs
        )
        
        return result
    
    def _get_workflow_class(self, workflow_name: str) -> Any:
        """Get the workflow class based on the workflow name."""
        from workflows import (
            ImageProcessingWorkflow,
            SemanticCacheCheckWorkflow,
            MemoryRetrievalWorkflow,
            PromptRetrievalWorkflow,
            AIGenerationWorkflow,
            MemoryStorageWorkflow,
            CacheStorageWorkflow,
            DataIngestionWorkflow
        )
        
        workflow_map = {
            "ImageProcessingWorkflow": ImageProcessingWorkflow,
            "SemanticCacheCheckWorkflow": SemanticCacheCheckWorkflow,
            "MemoryRetrievalWorkflow": MemoryRetrievalWorkflow,
            "PromptRetrievalWorkflow": PromptRetrievalWorkflow,
            "AIGenerationWorkflow": AIGenerationWorkflow,
            "MemoryStorageWorkflow": MemoryStorageWorkflow,
            "CacheStorageWorkflow": CacheStorageWorkflow,
            "DataIngestionWorkflow": DataIngestionWorkflow,
        }
        
        if workflow_name not in workflow_map:
            raise ValueError(f"Unknown workflow: {workflow_name}")
            
        return workflow_map[workflow_name]
    
    async def get_workflow_status(self, workflow_id: str, run_id: Optional[str] = None) -> Dict:
        """
        Get the status and progress of a running workflow.
        
        Args:
            workflow_id: The ID of the workflow
            run_id: Optional run ID of the workflow
            
        Returns:
            The workflow status information
        """
        if not self._client:
            raise RuntimeError("Temporal client not initialized")
            
        handle = self._client.get_workflow_handle(workflow_id, run_id)
        
        try:
            progress = await handle.query("get_progress")
            return {
                "status": "running",
                "progress": progress
            }
        except Exception as e:
            # The workflow might have completed or failed
            return {
                "status": "unknown",
                "error": str(e)
            }
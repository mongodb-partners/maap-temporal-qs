# temporal_worker.py
import asyncio
import concurrent.futures
import traceback
from activities import (
    mcp_call_tool,
    mcp_read_resource,
    mcp_get_prompt,
    mcp_manager,
    invoke_bedrock,
    process_image,
    ingest_data_activity
)
from maap_mcp.mcp_config import TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_PORT
from temporalio.client import Client
from temporalio.worker import Worker
from maap_mcp.logger import logger
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
import random
from typing import Optional

async def main():
    """Main entry point for the temporal worker."""
    max_retries = 100
    retry_count = 0
    last_exception: Optional[Exception] = None
    
    while retry_count < max_retries:
        try:
            # Connect to Temporal server
            logger.info(f"Connecting to Temporal server at {TEMPORAL_HOST}:{TEMPORAL_PORT} (Attempt {retry_count + 1}/{max_retries})")
            client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
            
            # Register workflows and activities
            logger.info(f"Starting worker on task queue {TASK_QUEUE}")
            
            # Create a worker that hosts all workflow implementations and activity implementations
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=100
            ) as activity_executor:
                worker = Worker(
                    client,
                    task_queue=TASK_QUEUE,
                    workflows=[
                        ImageProcessingWorkflow,
                        SemanticCacheCheckWorkflow,
                        MemoryRetrievalWorkflow,
                        PromptRetrievalWorkflow,
                        AIGenerationWorkflow,
                        MemoryStorageWorkflow,
                        CacheStorageWorkflow,
                        DataIngestionWorkflow
                    ],
                    activities=[
                        mcp_call_tool,
                        mcp_read_resource,
                        mcp_get_prompt,
                        invoke_bedrock,
                        process_image,
                        ingest_data_activity
                    ],
                    activity_executor=activity_executor,
                )
                # Start listening to task queue
                await logger.ainfo("Temporal worker starting...")
                await worker.run()
                # If we reach here without exceptions, break out of the retry loop
                break
                
        except Exception as e:
            retry_count += 1
            last_exception = e
            error_details = traceback.format_exc()
            
            if retry_count >= max_retries:
                logger.error(f"Failed after {retry_count} attempts. Final error: {str(e)}\n{error_details}")
            else:
                # Calculate backoff time with exponential backoff and jitter
                backoff_seconds = min(2 ** retry_count + random.uniform(0, 1), 60)
                logger.warning(f"Attempt {retry_count}/{max_retries} failed: {str(e)}. Retrying in {backoff_seconds:.2f} seconds...")
                await asyncio.sleep(backoff_seconds)
                
        finally:
            # Only shut down MCP server connections if we're not retrying
            if retry_count >= max_retries or last_exception is None:
                await mcp_manager.shutdown()
    
    # If we exhausted all retries and still failed, raise the last exception
    if retry_count >= max_retries and last_exception is not None:
        logger.error(f"Worker failed to start after {max_retries} attempts")
        raise last_exception
    

if __name__ == "__main__":
    asyncio.run(main())
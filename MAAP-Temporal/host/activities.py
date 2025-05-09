# activities.py
import io
import json
import os
import mimetypes
import requests
from typing import Any, Dict, List

import filetype
from PIL import Image
from temporalio import activity
from maap_mcp.logger import logger
from maap_mcp.mcp_clients_manager import MCPClientsManager
from models import (
    AIProcessingParams,
    ImageProcessingResult,
    ProcessQueryParams,
    PromptGetParams,
    ResourceReadParams,
    ToolExecutionParams,
    ImageProcessingParams,
    SemanticCacheParams,
    MemoryRetrievalParams,
    PromptRetrievalParams,
    AIGenerationParams,
    MemoryStorageParams,
    CacheStorageParams,
    DataIngestionParams
)
import maap_mcp.mcp_config as mcp_config

@activity.defn
async def process_image(image_path: str) -> ImageProcessingResult:
    """Process and prepare an image for the AI model."""
    activity.logger.info(f"Starting image processing: {image_path}")
    activity.heartbeat("Starting image processing")

    try:
        activity.logger.info(f"Reading image file: {image_path}")
        activity.heartbeat("Reading image file")
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

            activity.logger.info("Determining image format")
            activity.heartbeat("Determining image format")
            kind = filetype.guess(image_path)
            image_format = kind.extension if kind else "jpeg"

            activity.logger.info(f"Processing image format: {image_format}")
            activity.heartbeat(f"Processing image format: {image_format}")

            # Convert jpg/jpeg to png and resize
            activity.logger.info("Opening image for processing")
            activity.heartbeat("Opening image for processing")
            image = Image.open(io.BytesIO(image_bytes))

            if image_format in ["jpg", "jpeg"]:
                activity.logger.info("Converting JPEG to PNG")
                activity.heartbeat("Converting JPEG to PNG")
                image_format = "png"
                image = image.convert("RGB")

            activity.logger.info("Resizing image")
            activity.heartbeat("Resizing image")
            image.thumbnail((512, 512))

            activity.logger.info("Saving processed image")
            activity.heartbeat("Saving processed image")
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format="PNG")
            image_bytes = img_byte_arr.getvalue()

        activity.logger.info("Image processing completed successfully")
        activity.heartbeat("Image processing completed")
        return ImageProcessingResult(image_bytes=image_bytes, image_format=image_format)

    except Exception as e:
        error_msg = f"Error in process_image: {str(e)}"
        activity.logger.error(error_msg)
        activity.heartbeat(f"Error: {error_msg}")
        raise


# Create a global instance of the MCP clients manager
mcp_manager = MCPClientsManager()
# Load MCP server configuration
mcp_manager.load_config()


# Add MCP-specific activities
@activity.defn
async def mcp_call_tool(params: ToolExecutionParams) -> Dict:
    """Activity to call an MCP tool."""
    activity.logger.info(
        f"Starting mcp_call_tool: {params.tool_name} on {params.server_name}"
    )
    activity.heartbeat(f"Starting tool call: {params.tool_name}")

    try:
        activity.logger.info("Initializing MCP servers")
        activity.heartbeat("Initializing MCP servers")
        # Initialize MCP servers
        await mcp_manager.initialize_servers()

        activity.logger.info(
            f"Calling tool: {params.tool_name} with arguments: {params.arguments}"
        )
        activity.heartbeat(f"Calling {params.tool_name}")
        result = await mcp_manager.call_tool(
            params.server_name, params.tool_name, params.arguments
        )

        activity.logger.info("Processing tool call results")
        activity.heartbeat("Processing tool results")
        # Process result to ensure it's serializable
        response_data = {}
        for content in result.content:
            if hasattr(content, "text"):
                response_data = content.text
                break

        activity.logger.info(f"Tool call completed: {params.tool_name}")
        activity.heartbeat(f"Completed tool call: {params.tool_name}")
        return {"result": response_data, "isError": result.isError}

    except Exception as e:
        error_msg = f"Error in mcp_call_tool activity: {str(e)}"
        logger.error(error_msg)
        activity.logger.error(error_msg)
        activity.heartbeat(f"Error: {error_msg}")
        return {"result": None, "isError": True, "error": str(e)}


@activity.defn
async def mcp_read_resource(params: ResourceReadParams) -> Dict:
    """Activity to read an MCP resource."""
    activity.logger.info(
        f"Starting mcp_read_resource: {params.resource_uri} from {params.server_name}"
    )
    activity.heartbeat(f"Starting resource read: {params.resource_uri}")

    try:
        activity.logger.info("Initializing MCP servers")
        activity.heartbeat("Initializing MCP servers")
        # Initialize MCP servers
        await mcp_manager.initialize_servers()

        activity.logger.info(f"Reading resource: {params.resource_uri}")
        activity.heartbeat(f"Reading resource: {params.resource_uri}")
        result = await mcp_manager.read_resource(
            params.server_name, params.resource_uri
        )

        activity.logger.info("Processing resource data")
        activity.heartbeat("Processing resource data")
        # Process result to ensure it's serializable
        response_data = []
        for content in result.contents:
            if hasattr(content, "text"):
                response_data.append(
                    {
                        "type": "text",
                        "text": content.text,
                        "mimeType": (
                            content.mimeType
                            if hasattr(content, "mimeType")
                            else "text/plain"
                        ),
                    }
                )

        activity.logger.info(f"Resource read completed: {params.resource_uri}")
        activity.heartbeat(f"Completed resource read: {params.resource_uri}")
        return {"contents": response_data, "isError": False}

    except Exception as e:
        error_msg = f"Error in mcp_read_resource activity: {str(e)}"
        logger.error(error_msg)
        activity.logger.error(error_msg)
        activity.heartbeat(f"Error: {error_msg}")
        return {"contents": [], "isError": True, "error": str(e)}


@activity.defn
async def mcp_get_prompt(params: PromptGetParams) -> Dict:
    """Activity to get an MCP prompt."""
    activity.logger.info(
        f"Starting mcp_get_prompt: {params.prompt_name} from {params.server_name}"
    )
    activity.heartbeat(f"Starting prompt retrieval: {params.prompt_name}")

    try:
        activity.logger.info("Initializing MCP servers")
        activity.heartbeat("Initializing MCP servers")
        # Initialize MCP servers
        await mcp_manager.initialize_servers()

        activity.logger.info(
            f"Getting prompt: {params.prompt_name} with arguments: {params.arguments}"
        )
        activity.heartbeat(f"Retrieving prompt: {params.prompt_name}")
        result = await mcp_manager.get_prompt(
            params.server_name, params.prompt_name, params.arguments
        )

        activity.logger.info("Processing prompt data")
        activity.heartbeat("Processing prompt data")

        # Process result to ensure it's serializable
        if hasattr(result, "messages"):
            messages = result.messages
            # Iterate through messages to find user role message
            for message in messages:
                if hasattr(message, "role") and message.role == "user":
                    # Check if content has text attribute
                    if hasattr(message.content, "text"):
                        memory_text = message.content.text

                        # Format the output as requested
                        formatted_output = {
                            "role": "user",
                            "content": [{"text": memory_text}],
                        }

                        activity.logger.info(
                            f"Prompt retrieved successfully: {params.prompt_name}"
                        )
                        activity.heartbeat(f"Prompt retrieved: {params.prompt_name}")
                        return {"result": formatted_output, "isError": False}

        # If we reach here, we couldn't find the expected structure
        activity.logger.info("Prompt structure not as expected, returning empty result")
        activity.heartbeat("Prompt structure not recognized")
        return {"result": {}, "isError": False}

    except Exception as e:
        error_msg = f"Error in mcp_get_prompt activity: {str(e)}"
        logger.error(error_msg)
        activity.logger.error(error_msg)
        activity.heartbeat(f"Error: {error_msg}")
        return {"contents": [], "isError": True, "error": str(e)}


@activity.defn
async def invoke_bedrock(messages: List[Dict[Any, Any]]) -> Dict:
    """
    Send messages to Amazon Bedrock and return the response.
    """
    activity.logger.info("Starting Bedrock invocation")
    activity.heartbeat("Starting Bedrock invocation")

    try:
        activity.logger.info("Initializing MCP servers")
        activity.heartbeat("Initializing MCP servers")
        # Initialize MCP servers
        await mcp_manager.initialize_servers()

        activity.logger.info("Sending messages to Bedrock")
        activity.heartbeat("Sending messages to Bedrock")
        result = await mcp_manager.invoke_bedrock("maap", messages)

        activity.logger.info("Processing Bedrock response")
        activity.heartbeat("Processing Bedrock response")
        # The data tuple consists of the most recent response and a conversation history
        most_recent_response = result[0]
        conversation_history = result[1]

        activity.logger.info("Parsing conversation history")
        activity.heartbeat("Parsing conversation history")
        # Parse the conversation history
        parsed_conversation = []
        for message in conversation_history:
            role = message["role"]

            # Extract text content from the message
            content_text = []
            if "content" in message:
                for content_item in message["content"]:
                    if "text" in content_item:
                        content_text.append(content_item["text"])

            parsed_message = {"role": role, "content": content_text}
            parsed_conversation.append(parsed_message)

        result = {
            "most_recent_response": most_recent_response,
            "conversation_history": parsed_conversation,
        }

        activity.logger.info("Bedrock response received successfully")
        activity.heartbeat("Bedrock response received")
        logger.info(f"Bedrock response: {most_recent_response}")
        return {"result": most_recent_response, "isError": False}

    except Exception as e:
        error_msg = f"Error in invoke_bedrock activity: {str(e)}"
        logger.error(error_msg)
        activity.logger.error(error_msg)
        activity.heartbeat(f"Error: {error_msg}")
        return {"result": None, "isError": True, "error": str(e)}




@activity.defn
async def ingest_data_activity(params: DataIngestionParams) -> Dict[str, Any]:
    """
    Activity that ingests data from files and URLs into the MongoDB database.
    
    Args:
        params: DataIngestionParams containing user_id, urls, files, and MongoDB config
        
    Returns:
        Dict with success status and message
    """
    # Set up logging for activity heartbeats
    activity.heartbeat("Starting data ingestion...")
    
    url = f"{mcp_config.DATA_LOADER_SERVICE_URL}/upload"
    
    # Prepare MongoDB config
    mongodb_config = {
        "uri": params.mongodb_uri,
        "database": params.mongodb_database,
        "collection": params.mongodb_collection,
        "index_name": params.mongodb_index_name,
        "text_field": params.mongodb_text_field,
        "embedding_field": params.mongodb_embedding_field
    }
    
    # Prepare request params
    request_params = {
        "user_id": params.user_id,
        "mongodb_config": mongodb_config,
        "web_pages": params.urls or []
    }
    
    # Prepare payload
    payload = {"json_input_params": json.dumps(request_params)}
    
    # Prepare files
    files = []
    file_types = [
        ".bmp", ".csv", ".doc", ".docx", ".eml", ".epub", ".heic", ".html",
        ".jpeg", ".jpg", ".png", ".md", ".msg", ".odt", ".org", ".p7s", ".pdf",
        ".png", ".ppt", ".pptx", ".rst", ".rtf", ".tiff", ".txt", ".tsv",
        ".xls", ".xlsx", ".xml",
        ".vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".vnd.openxmlformats-officedocument.presentationml.presentation",
    ]
    
    # Send activity heartbeat for file preparation
    if params.files and len(params.files) > 0:
        activity.heartbeat(f"Preparing {len(params.files)} files for ingestion...")
        
    for file_path in params.files or []:
        file_name, file_ext = os.path.splitext(file_path)
        file_name = os.path.basename(file_path)
        mime_type, encoding = mimetypes.guess_type(file_path)
        
        if file_ext.lower() in file_types:
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                    files.append(("files", (file_name, file_content, mime_type)))
                    activity.heartbeat(f"Added file: {file_name}")
            except Exception as e:
                activity.heartbeat(f"Error reading file {file_name}: {str(e)}")
                logger.error(f"Error reading file {file_name}: {str(e)}")
    
    # Send API request
    activity.heartbeat("Sending request to ingestion service...")
    
    try:
        headers = {}
        response = requests.request(
            "POST", 
            url, 
            headers=headers, 
            data=payload, 
            files=files
        )
        
        response_text = response.text
        activity.heartbeat(f"Received response: {response_text[:100]}...")
        
        # Check if the upload was successful
        if "Upload processed successfully" in response_text:
            return {
                "success": True,
                "message": "Successfully ingested data",
                "details": response_text
            }
        else:
            return {
                "success": False,
                "message": "Failed to ingest data",
                "details": response_text
            }
    except Exception as e:
        error_message = f"Error during data ingestion: {str(e)}"
        activity.heartbeat(error_message)
        logger.error(error_message)
        return {
            "success": False,
            "message": error_message,
            "details": None
        }



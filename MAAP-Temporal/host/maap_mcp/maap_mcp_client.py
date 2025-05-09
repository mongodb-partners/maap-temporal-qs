import io
import json
import traceback
import os
import re
import time
from contextlib import AsyncExitStack
from typing import Any, Dict, List
import boto3
import maap_mcp.mcp_config as mcp_config
import filetype
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import AnyUrl
from PIL import Image
from maap_mcp.converse_tool_manager import ConverseToolManager
from maap_mcp.logger import logger


class MaapMCPClient:
    def __init__(self):
        """Initialize the MAAP MCP client."""
        self.system_prompt =mcp_config.DEFAULT_SYSTEM_PROMPT or "You are a helpful assistant that can use tools to help answer questions and perform tasks."
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.user_id = mcp_config.DEFAULT_USER_ID
        self.conversation_id = f"conv_{os.getpid()}_{int(time.time())}"
        self.model_id = mcp_config.LLM_MODEL_ID
        self.region = mcp_config.AWS_REGION
        self.client = boto3.client("bedrock-runtime", region_name=self.region)
        self.system_prompt = "You are a helpful assistant that can use tools to help answer questions and perform tasks."
        self.messages = []
        self.tools = ConverseToolManager()
        self._streams_context = None
        self._session_context = None
        self.stdio = None
        self.writer = None

    async def call_tool(self, tool_name: str, arguments: dict = None) -> Any:
        """Call a tool with given arguments"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        logger.print(f"Calling tool: {tool_name} with arguments: {arguments}")
        result = await self.session.call_tool(tool_name, arguments=arguments)
        return result

    async def get_available_tools(self) -> List[Any]:
        """List available tools"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        response = await self.session.list_tools()
        return response.tools

    async def read_resource(self, resource_uri: str):
        """Read a resource from the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        return await self.session.read_resource(AnyUrl(resource_uri))

    async def get_prompt(self, prompt_name: str, arguments: Dict[str, Any] = None):
        """Get a prompt from the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        return await self.session.get_prompt(prompt_name, arguments=arguments)

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an SSE MCP server."""
        logger.info(f"Connecting to SSE MCP server at {server_url}")
        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()
        self._session_context = ClientSession(*streams)
        self.session = await self._session_context.__aenter__()
        # Initialize
        await self.session.initialize()
        # List available tools
        tools = await self.get_available_tools()
        logger.info(
            f"Connected to SSE MCP Server at {server_url}. Available tools: {[tool.name for tool in tools]}"
        )

    async def connect_to_stdio_server(self, server_script_path: str, env: dict = None):
        """Connect to a stdio MCP server."""
        is_python = False
        is_javascript = False
        command = None
        args = [server_script_path]
        # Determine if the server is a file path or npm package
        if server_script_path.startswith("@") or "/" not in server_script_path:
            # Assume it's an npm package
            is_javascript = True
            command = "npx"
        else:
            # It's a file path
            is_python = server_script_path.endswith(".py")
            is_javascript = server_script_path.endswith(".js")
            if not (is_python or is_javascript):
                raise ValueError(
                    "Server script must be a .py, .js file or npm package."
                )
            command = "python" if is_python else "node"
        server_params = StdioServerParameters(command=command, args=args, env=env)
        logger.info(
            f"Connecting to stdio MCP server with command: {command} and args: {args}"
        )
        # Start the server
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.writer = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.writer)
        )
        await self.session.initialize()
        # List available tools
        tools = await self.get_available_tools()
        logger.info(
            f"Connected to stdio MCP Server. Available tools: {[tool.name for tool in tools]}"
        )

    async def connect_to_server(self, server_path_or_url: str, env: dict = None):
        """Connect to an MCP server (either stdio or SSE)."""
        # Check if the input is a URL (for SSE server)
        url_pattern = re.compile(r"^https?://")
        if url_pattern.match(server_path_or_url):
            # It's a URL, connect to SSE server
            await self.connect_to_sse_server(server_path_or_url)
        else:
            # It's a script path, connect to stdio server
            await self.connect_to_stdio_server(server_path_or_url, env)
        # After connection, register tools
        tools = await self.get_available_tools()
        for tool in tools:
            self.tools.register_tool(
                name=tool.name,
                func=self.call_tool,
                description=tool.description,
                input_schema={"json": tool.inputSchema} if tool.inputSchema else {},
            )

    async def _get_converse_response(self, image_paths=None):
        """Get response from Bedrock Converse API"""
        # Create properly formatted messages for Converse API
        formatted_messages = []
        for message in self.messages:
            msg_content = []
            # Format the content correctly - convert string content to list with text object
            if "content" in message:
                if isinstance(message["content"], str):
                    # String content needs to be converted to a content object
                    msg_content = [{"text": message["content"]}]
                elif isinstance(message["content"], list):
                    # If it's already a list, keep it as is
                    msg_content = message["content"]
            # Handle images if present for user messages
            if message["role"] == "user" and image_paths:
                msg_idx = len(formatted_messages)
                if msg_idx in image_paths:
                    # Add image as base64 content
                    with open(image_paths[msg_idx], "rb") as img_file:
                        import base64

                        img_data = base64.b64encode(img_file.read()).decode("utf-8")
                        msg_content.append({"image": img_data})
            formatted_messages.append({"role": message["role"], "content": msg_content})
        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=formatted_messages,
                system=[{"text": self.system_prompt}],
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.7,
                },
                toolConfig=self.tools.get_tools(),
            )
            # Log response structure for debugging
            logger.debug(f"Response structure: {json.dumps(response, default=str)}")
            return response
        except Exception as e:
            logger.error(f"Error in converse API call: {str(e)}")
            raise

    async def invoke(self, response_content=None):
        """Process a response or continue conversation with tool results"""
        try:
            if response_content:
                # This is a follow-up with tool results
                # Make sure tool results are correctly formatted
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            response_content
                            if isinstance(response_content, list)
                            else [{"text": str(response_content)}]
                        ),
                    }
                )
            response = await self._get_converse_response()
            # Check if the response contains the expected structure
            if "output" not in response:
                logger.error(f"Unexpected response format: {response}")
                return "Error: Unexpected response format from Bedrock"
            # Add the response to conversation history
            self.messages.append(response["output"]["message"])
            # Get the stop reason
            stop_reason = response.get("stopReason", "")
            if "output" in response and "stopReason" in response["output"]:
                stop_reason = response["output"]["stopReason"]
            # Check for tool use
            if stop_reason == "tool_use":
                # Extract tool use details from response
                tool_response = []
                for content_item in response["output"]["message"]["content"]:
                    if "toolUse" in content_item:
                        tool_request = {
                            "toolUseId": content_item["toolUse"]["toolUseId"],
                            "name": content_item["toolUse"]["name"],
                            "input": content_item["toolUse"]["input"],
                        }
                        logger.info(
                            f"Calling tool {tool_request['name']} with input: {tool_request['input']}"
                        )
                        tool_result = await self.tools.execute_tool(tool_request)
                        tool_response.append({"toolResult": tool_result})
                # Recursive call to continue conversation with tool results
                return await self.invoke(tool_response)
            # Extract final text from response
            final_text = ""
            for content_item in response["output"]["message"]["content"]:
                if "text" in content_item:
                    final_text += content_item["text"]
            return final_text
        except Exception as e:
            logger.error(f"Error in invoke method: {str(e)}")
            return f"Error processing your request: {str(e)}"

    async def process_query(
        self, query: str, previous_messages: list = None, image_path: str = None
    ) -> tuple[str, list]:
        """
        Process a query using the MCP server and Converse API.
        Args:
            query: User query text
            previous_messages: Previous conversation messages
            image_path: Optional path to an image file to include with the query
        Returns:
            tuple of response text and updated message history
        """
        if not self.session:
            raise RuntimeError("Client session is not initialized.")
        # Reset messages or use previous
        if previous_messages:
            self.messages = previous_messages
        # Add user message with proper content format for Converse API
        if image_path:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
                kind = filetype.guess(image_path)
                image_format = kind.extension if kind else "jpeg"
                # Convert jpg/jpeg to png and resize
                image = Image.open(io.BytesIO(image_bytes))
                if image_format in ["jpg", "jpeg"]:
                    image_format = "png"
                    image = image.convert("RGB")
                image.thumbnail((512, 512))
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format="PNG")
                image_bytes = img_byte_arr.getvalue()
            self.messages.append(
                {
                    "role": "user",
                    "content": [
                        {"text": query},
                        {
                            "image": {
                                "format": image_format,
                                "source": {"bytes": image_bytes},
                            }
                        },
                    ],
                }
            )
        else:
            self.messages.append(
                {
                    "role": "user",
                    "content": [
                        {"text": query}
                    ],  # Correctly formatted as a list with text object
                }
            )
        # Store user message with image info if available
        user_message_for_memory = query
        if image_path:
            user_message_for_memory += (
                f" [Included image: {os.path.basename(image_path)}]"
            )
        # Check semantic cache first to see if we have a similar query
        try:
            logger.info(f"Checking semantic cache for query: {query[:50]}...")
            cache_response = await self.session.call_tool(
                "check_semantic_cache",
                {"user_id": self.user_id, "query": user_message_for_memory},
            )
            # More robust handling of cache response
            if cache_response.content:
                try:
                    if isinstance(cache_response.content[0].text, str):
                        cache_data = json.loads(cache_response.content[0].text)
                        if "response" in cache_data:
                            cached_response = cache_data["response"]
                            if cached_response != "cache_miss":
                                # Cache hit found
                                logger.info(
                                    "Cache hit! Found similar query in semantic cache."
                                )
                                self.messages.append(
                                    {
                                        "role": "assistant",
                                        "content": [
                                            {"text": cached_response}
                                        ],  # Correctly formatted content
                                    }
                                )
                                return cached_response, self.messages
                except (json.JSONDecodeError, IndexError, AttributeError) as e:
                    logger.warning(f"Failed to parse cache response: {str(e)}")
            logger.info(
                "No cache hit found or failed to parse. Proceeding with LLM call."
            )
        except Exception as e:
            logger.error(f"Error checking semantic cache: {str(e)}")
        # Try to retrieve relevant memories
        memories = {}
        try:
            memory_response = await self.session.call_tool(
                "retrieve_memory",
                {"user_id": self.user_id, "text": user_message_for_memory},
            )
            if isinstance(memory_response.content[0].text, str):
                memories = json.loads(memory_response.content[0].text)
                related_conversation = memories.get("related_conversation", "")
                conversation_summary = memories.get("conversation_summary", "")
                similar_memories = memories.get("similar_memories", "")
                # Add memory context to messages with proper content format
                memory_text = f"My user_id is:{self.user_id}\n\n Here is a memory knowledge about me collected over various conversations: {similar_memories}\n\n  Here is some relevant context from your previous conversations with me: {conversation_summary}\n\nPlease keep this in mind when responding to my query, but don't explicitly reference this context unless necessary."
                self.messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"text": memory_text}
                        ],  # Correctly formatted as a list with text object
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to retrieve memories: {str(e)}")
        # Setup image paths dictionary
        image_paths = {}
        if image_path:
            # The last message is the user query
            image_paths[len(self.messages) - 1] = image_path
        # Send to Bedrock using invoke method that handles recursive tool calls
        logger.info(f"Sending query to Bedrock with {len(self.messages)} messages")
        response_text = await self.invoke()
        # Store the AI response in memory
        try:
            await self.session.call_tool(
                "store_memory",
                {
                    "conversation_id": self.conversation_id,
                    "text": query,
                    "message_type": "human",
                    "user_id": self.user_id,
                },
            )
            await self.session.call_tool(
                "store_memory",
                {
                    "conversation_id": self.conversation_id,
                    "text": response_text,
                    "message_type": "ai",
                    "user_id": self.user_id,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to store AI response in memory: {str(e)}")
        # Cache the response for similar future queries
        try:
            await self.session.call_tool(
                "semantic_cache_response",
                {
                    "user_id": self.user_id,
                    "query": user_message_for_memory,
                    "response": response_text,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to cache response: {str(e)}")
        return response_text, self.messages



    
    # region temporal
    def convert_bytes_in_messages(self, messages):
        for message in messages:
            if "content" in message and isinstance(message["content"], list):
                for content_item in message["content"]:
                    if isinstance(content_item, dict) and "image" in content_item:
                        if "source" in content_item["image"]:
                            source = content_item["image"]["source"]
                            if "bytes" in source and isinstance(source["bytes"], list):
                                # Convert list to bytes object
                                source["bytes"] = bytes(source["bytes"])
    
        return messages
    async def _get_converse_response_bedrock(self, messages, image_paths=None):
        """Get response from Bedrock Converse API with messages passed as parameter"""
        #Create properly formatted messages for Converse API
        formatted_messages = []
        for idx, message in enumerate(messages):
            msg_content = []
            # Format the content correctly - convert string content to list with text object
            if "content" in message:
                if isinstance(message["content"], str):
                    # String content needs to be converted to a content object
                    msg_content = [{"text": message["content"]}]
                elif isinstance(message["content"], list):
                    # If it's already a list, keep it as is
                    msg_content = message["content"]
            # Handle images if present for user messages
            if message["role"] == "user" and image_paths:
                if idx in image_paths:
                    # Add image as base64 content
                    with open(image_paths[idx], "rb") as img_file:
                        import base64

                        img_data = base64.b64encode(img_file.read()).decode("utf-8")
                        msg_content.append({"image": img_data})
            formatted_messages.append({"role": message["role"], "content": msg_content})
        try:
            formatted_messages = self.convert_bytes_in_messages(formatted_messages)
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": self.system_prompt}],
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.7,
                },
                toolConfig=self.tools.get_tools(),
            )
            # Log response structure for debugging
            logger.debug(f"Response structure: {json.dumps(response, default=str)}")
            return response
        except Exception as e:
            logger.error(f"Error in converse API call: {str(e)}")
            raise

    async def invoke_bedrock(self, messages, response_content=None):
        """Process a response or continue conversation with tool results"""
        logger.info("Starting invoke_bedrock method")
        try:
            # Create a copy of the messages to avoid modifying the original
            current_messages = messages.copy()
            logger.info(f"Working with messages copy, count: {len(current_messages)}")
            
            if response_content:
                # This is a follow-up with tool results
                logger.info(f"Follow-up call with tool results: {response_content}")
                # Make sure tool results are correctly formatted
                current_messages.append(
                    {
                        "role": "user",
                        "content": (
                            response_content
                            if isinstance(response_content, list)
                            else [{"text": str(response_content)}]
                        ),
                    }
                )
                logger.info(f"Added tool results to messages, new count: {len(current_messages)}")
            
            logger.info("Calling Bedrock API...")
            response = await self._get_converse_response_bedrock(
                messages=current_messages
            )
            logger.info(f"Received response from Bedrock API: {json.dumps(response, indent=2)[:500]}...")
            
            # Check if the response contains the expected structure
            if "output" not in response:
                logger.error(f"Unexpected response format: {response}")
                return (
                    "Error: Unexpected response format from Bedrock",
                    current_messages,
                )
            
            # Add the response to conversation history
            current_messages.append(response["output"]["message"])
            logger.info(f"Added model response to conversation history, message count: {len(current_messages)}")
            
            # Get the stop reason
            stop_reason = response.get("stopReason", "")
            if "output" in response and "stopReason" in response["output"]:
                stop_reason = response["output"]["stopReason"]
            logger.info(f"Response stop reason: {stop_reason}")
            
            # Check for tool use
            if stop_reason == "tool_use":
                logger.info("Model requested tool use")
                # Extract tool use details from response
                tool_response = []
                for content_item in response["output"]["message"]["content"]:
                    if "toolUse" in content_item:
                        tool_request = {
                            "toolUseId": content_item["toolUse"]["toolUseId"],
                            "name": content_item["toolUse"]["name"],
                            "input": content_item["toolUse"]["input"],
                        }
                        logger.info(
                            f"Extracting tool request - ID: {tool_request['toolUseId']}, Name: {tool_request['name']}, Input: {tool_request['input']}"
                        )
                        logger.info(f"Calling tool {tool_request['name']} with input: {tool_request['input']}")
                        tool_result = await self.tools.execute_tool(tool_request)
                        logger.info(f"Tool execution result: {tool_result}")
                        tool_response.append({"toolResult": tool_result})
                
                logger.info(f"All tool responses collected: {tool_response}")
                # Recursive call to continue conversation with tool results
                logger.info("Making recursive call with tool results")
                return await self.invoke_bedrock(
                    messages=current_messages,
                    response_content=tool_response,
                )
            
            # Extract final text from response
            final_text = ""
            for content_item in response["output"]["message"]["content"]:
                if "text" in content_item:
                    final_text += content_item["text"]
                    logger.debug(f"Added text from content item: {content_item['text'][:100]}...")
            
            logger.info(f"Final response extracted, length: {len(final_text)} characters")
            return final_text, current_messages
        except Exception as e:
            logger.error(f"Error in invoke method: {str(e)}")
            logger.error(traceback.format_exc())
            return f"Error processing your request: {str(e)}", messages

    # endregion

    async def chat_loop(self):
        """Run an interactive chat loop with the server."""
        previous_messages = []
        print("Type your queries or commands:")
        print("  - 'quit': Exit the chat")
        print("  - 'refresh': Start a new conversation")
        print(
            "  - 'image:/path/to/image.jpg Your query': Include an image with your query"
        )
        debug_mode = False
        while True:
            try:
                user_input = input("\nQuery: ").strip()
                if user_input.lower() == "quit":
                    break
                # Check for conversation refresh
                if user_input.lower() == "refresh":
                    previous_messages = []
                    self.messages = []
                    self.conversation_id = f"conv_{os.getpid()}_{int(time.time())}"
                    print("Started a new conversation.")
                    continue
                # Check if user wants to include an image
                image_path = None
                if user_input.startswith("image:"):
                    # Extract image path and actual query
                    parts = user_input.split(" ", 1)
                    if len(parts) < 2:
                        print("Error: Please provide both an image path and a query.")
                        print("Format: image:/path/to/image.jpg Your query text")
                        continue
                    image_path = parts[0].replace("image:", "").replace('"', "")
                    query = parts[1]
                    # Validate image path
                    if not os.path.exists(image_path):
                        print(f"Error: Image file not found at {image_path}")
                        continue
                else:
                    query = user_input
                # Process the query with clear error handling
                try:
                    response, previous_messages = await self.process_query(
                        query=query,
                        previous_messages=previous_messages,
                        image_path=image_path,
                    )
                    print("\nResponse:", response)
                except Exception as e:
                    print(f"\nError processing query: {str(e)}")
                    if debug_mode:
                        import traceback

                        print(traceback.format_exc())
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
                logger.error(f"Error in chat loop: {str(e)}", exc_info=True)

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()
        if hasattr(self, "_session_context") and self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if hasattr(self, "_streams_context") and self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

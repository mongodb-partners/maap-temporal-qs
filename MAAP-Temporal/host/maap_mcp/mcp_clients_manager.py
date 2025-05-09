import json
import os
import sys
from typing import Dict, Any, List  
from maap_mcp.logger import logger
import maap_mcp.mcp_config as mcp_config

# Import the MaapMCPClient class
from maap_mcp.maap_mcp_client import MaapMCPClient

class MCPClientsManager:
    """Manages connections to MCP servers."""
    def __init__(self):
        self.servers = {}
        self.sessions = {}
        self.server_capabilities = {}

    def load_config(self):
        """Load MCP server configuration from file or environment variables."""
        config_data = {}
        # Try to load from environment variable first
        if hasattr(mcp_config, 'MCP_CONFIG_ENV') and mcp_config.MCP_CONFIG_ENV:
            try:
                config_data = json.loads(mcp_config.MCP_CONFIG_ENV)
                logger.info("Loaded MCP server configuration from environment")
            except json.JSONDecodeError:
                logger.error("Failed to parse MCP_SERVERS environment variable as JSON")
        # If not found or invalid, try loading from file
        if not config_data and hasattr(mcp_config, 'MCP_CONFIG_PATH') and os.path.exists(mcp_config.MCP_CONFIG_PATH):
            try:
                with open(mcp_config.MCP_CONFIG_PATH, "r") as f:
                    config_data = json.load(f)
                logger.info(f"Loaded MCP server configuration from {mcp_config.MCP_CONFIG_PATH}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(
                    f"Failed to load MCP server configuration from {mcp_config.MCP_CONFIG_PATH}: {e}"
                )
        if not config_data:
            logger.warning(
                "No MCP server configuration found, using default configuration"
            )
            # Default configuration for common MCP servers
            config_data = {
                "maap": {"server_path": "mcp_server/maap_mcp_server.py", "env": {}}
            }
        self.servers = config_data
        return config_data

    async def initialize_servers(self):
        """Initialize connections to all configured MCP servers."""
        for server_name, server_config in self.servers.items():
            # Check if a client already exists
            existing_client = self.sessions.get(server_name)
            if existing_client:
                try:
                    # Check if the client is healthy by calling the health check endpoint
                    health_response = await existing_client.read_resource("health://status")
                    status=json.loads(health_response.contents[0].text).get("status")
                    
                    if status == "healthy":
                        logger.info(f"Using existing healthy MCP client for {server_name}")
                        continue
                    else:
                        logger.warning(f"Existing MCP client for {server_name} reports unhealthy status. Recreating...")
                except Exception as e:
                    # Client exists but has errored when trying to check health
                    logger.warning(f"Existing MCP client for {server_name} appears to be in error state: {str(e)}. Recreating...")
                    
            # Create a new client if needed
            try:
                logger.info(f"Initializing MCP client: {server_name}")
                # Prepare server environment
                server_env = {**os.environ}
                if "env" in server_config:
                    server_env.update(server_config["env"])
                
                client = MaapMCPClient()
                await client.connect_to_server(
                    server_config["server_path"],
                    server_env,
                )
                self.sessions[server_name] = client
                logger.info(f"Successfully connected to {server_name} MCP server")
            except Exception as e:
                logger.error(f"Failed to initialize {server_name} MCP client: {str(e)}")

    async def shutdown(self):
        """Close all MCP server connections."""
        for server_name, client in self.sessions.items():
            try:
                logger.info(f"Shutting down connection to {server_name} MCP server")
                if client:
                    await client.cleanup()
                    logger.info(f"MCP Client for {server_name} closed")
                else:
                    logger.warning(
                        f"No active session found for {server_name} MCP server"
                    )
            except Exception as e:
                logger.error(
                    f"Error shutting down connection to {server_name} MCP server: {str(e)}"
                )
        self.sessions.clear()

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any] = None
    ):
        """Call a tool on a specific MCP server."""
        if server_name not in self.sessions:
            error_msg = f"MCP server {server_name} not initialized"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            client = self.sessions[server_name]
            logger.info(f"Calling tool {tool_name} on server {server_name}")
            result = await client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(
                f"Error calling tool {tool_name} on server {server_name}: {str(e)}"
            )
            raise

    async def read_resource(self, server_name: str, resource_uri: str):
        """Read a resource from a specific MCP server."""
        if server_name not in self.sessions:
            error_msg = f"MCP server {server_name} not initialized"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            client = self.sessions[server_name]
            logger.info(f"Reading resource {resource_uri} from server {server_name}")
            result = await client.read_resource(resource_uri)
            return result
        except Exception as e:
            logger.error(
                f"Error reading resource {resource_uri} from server {server_name}: {str(e)}"
            )
            raise

    async def get_prompt(
        self, server_name: str, prompt_name: str, arguments: Dict[str, Any] = None
    ):
        """Get a prompt from a specific MCP server."""
        if server_name not in self.sessions:
            error_msg = f"MCP server {server_name} not initialized"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            client = self.sessions[server_name]
            logger.info(f"Reading prompt {prompt_name} from server {server_name}")
            result = await client.get_prompt(prompt_name, arguments=arguments)
            return result
        except Exception as e:
            logger.error(
                f"Error reading prompt {prompt_name} from server {server_name}: {str(e)}"
            )
            raise

    async def invoke_bedrock(
        self, server_name: str, messages: List[Dict[str, Any]]
    ):
        """Get a prompt from a specific MCP server."""
        if server_name not in self.sessions:
            error_msg = f"MCP server {server_name} not initialized"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            client = self.sessions[server_name]
            logger.info(f"Invoking Bedrock from server {server_name}")
            result = await client.invoke_bedrock(messages)
            return result
        except Exception as e:
            logger.error(
                f"Error invoking Bedrock from server {server_name}: {str(e)}"
            )
            raise
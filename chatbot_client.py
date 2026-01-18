import os
import asyncio
import json
import logging
import sys
from typing import Optional, List, Dict, Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Global MCP Client Management (Singleton Pattern)
# -----------------------------
_mcp_clients = {
    "ads": None,
    "analytics": None
}
_mcp_agents = {
    "ads": None,
    "analytics": None
}

async def get_or_create_agent(agent_type: str):
    """
    Get or create a persistent MCP client and agent for the specific type.
    """
    global _mcp_clients, _mcp_agents
    
    if _mcp_agents.get(agent_type) is None:
        try:
            logger.info(f"🔌 Initializing MCP client for {agent_type}...")
            
            # Use the current system python executable (works locally and on Render)
            python_path = sys.executable
            
            server_config = {}
            if agent_type == "ads":
                server_config = {
                    "googleads": {
                        "command": python_path,
                        "args": [os.path.abspath("mcp-server/googleads_server.py")],
                        "transport": "stdio",
                    }
                }
            else:
                server_config = {
                    "googleanalytics": {
                        "command": python_path,
                        "args": [os.path.abspath("mcp-server/googleanalytics_server.py")],
                        "transport": "stdio",
                    }
                }

            client = MultiServerMCPClient(server_config)
            tools = await client.get_tools()
            
            # Initialize Groq model
            model = ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=0,
                api_key=os.environ.get("GROQ_API_KEY"),
            )

            # Create ReAct agent with tools
            agent = create_react_agent(model=model, tools=tools)
            
            _mcp_clients[agent_type] = client
            _mcp_agents[agent_type] = agent
            
            logger.info(f"✅ {agent_type} agent created with {len(tools)} tools")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize {agent_type} agent: {e}")
            raise
    
    return _mcp_agents[agent_type]

async def get_chatbot_response(message: str, agent_type: str = "ads", chat_history: List[Any] = None) -> str:
    """
    Main entry point for getting a response from the chatbot.
    """
    agent = await get_or_create_agent(agent_type)
    
    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append(HumanMessage(content=message))
    
    try:
        response = await agent.ainvoke({"messages": messages})
        if response and "messages" in response:
            return response["messages"][-1].content
        return "I'm sorry, I couldn't generate a response."
    except Exception as e:
        logger.error(f"Error getting response from {agent_type} agent: {e}")
        return f"Error: {str(e)}"

async def cleanup():
    """Clean up MCP client connections on exit."""
    global _mcp_clients
    for agent_type, client in _mcp_clients.items():
        if client is not None:
            try:
                logger.info(f"🧹 Cleaning up {agent_type} MCP client...")
                if hasattr(client, 'close'):
                    await client.close()
                elif hasattr(client, '__aexit__'):
                    await client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"⚠️ Error during cleanup of {agent_type}: {e}")
            finally:
                _mcp_clients[agent_type] = None

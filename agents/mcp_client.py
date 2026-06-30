"""
mcp_client.py

Synchronous HTTP client for communicating with MCP (Model Context Protocol) servers
deployed as Kubernetes sidecars. Each MCP server exposes REST endpoints
for tool discovery and execution.

Architecture:
    Python Agent  --HTTP-->  MCP Server (TypeScript/Express)  --Azure SDK-->  Azure APIs
    (this client)            (sidecar on same pod, localhost)
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List


class MCPClient:
    """
    Generic HTTP client for calling MCP server tools over REST.
    Used by Python agents to communicate with TypeScript MCP servers
    running as Kubernetes sidecars on the same pod.
    """

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls a tool on the MCP server via HTTP POST.

        Args:
            tool_name: Name of the MCP tool to invoke
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            Dictionary containing the tool response with 'content' array,
            or an error dict with 'error': True
        """
        url = f"{self.base_url}/api/tools/call"
        payload = {"name": tool_name, "arguments": arguments}

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": True,
                    "status": response.status_code,
                    "message": response.text,
                }
        except requests.ConnectionError:
            return {
                "error": True,
                "message": f"Cannot connect to MCP server at {self.base_url}. Is the sidecar running?",
            }
        except requests.Timeout:
            return {
                "error": True,
                "message": f"MCP server at {self.base_url} timed out after {self.timeout}s",
            }
        except Exception as e:
            return {"error": True, "message": f"MCP client error: {str(e)}"}

    def list_tools(self) -> List[Dict[str, Any]]:
        """Lists all available tools on the MCP server."""
        url = f"{self.base_url}/api/tools"
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return data.get("tools", [])
            return []
        except Exception:
            return []

    def health_check(self) -> bool:
        """Checks if the MCP server is healthy and reachable."""
        url = f"{self.base_url}/health"
        try:
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False


class MCPClients:
    """
    Factory for pre-configured MCP server clients.
    Uses Kubernetes service discovery via environment variables.

    In the sidecar pattern, all MCP servers run as containers in the same
    pod, sharing localhost. Each server binds to a unique port:
        - Cost Management:  3000
        - Policy & RBAC:    3001
        - Governance:       3002
        - Security:         3003
        - Azure Tools:      3004
    """

    _instances: Dict[str, MCPClient] = {}

    @classmethod
    def _get_or_create(cls, key: str, env_var: str, default_url: str) -> MCPClient:
        if key not in cls._instances:
            url = os.environ.get(env_var, default_url)
            cls._instances[key] = MCPClient(url)
        return cls._instances[key]

    @classmethod
    def cost_mgmt(cls) -> MCPClient:
        """Client for the Cost Management MCP Server (port 3000)."""
        return cls._get_or_create("cost_mgmt", "COST_MCP_URL", "http://localhost:3000")

    @classmethod
    def policy(cls) -> MCPClient:
        """Client for the Policy & RBAC MCP Server (port 3001)."""
        return cls._get_or_create("policy", "POLICY_MCP_URL", "http://localhost:3001")

    @classmethod
    def governance(cls) -> MCPClient:
        """Client for the Governance MCP Server (port 3002)."""
        return cls._get_or_create(
            "governance", "GOVERNANCE_MCP_URL", "http://localhost:3002"
        )

    @classmethod
    def security(cls) -> MCPClient:
        """Client for the Security MCP Server (port 3003)."""
        return cls._get_or_create(
            "security", "SECURITY_MCP_URL", "http://localhost:3003"
        )

    @classmethod
    def azure_tools(cls) -> MCPClient:
        """Client for the Azure Tools MCP Server (port 3004)."""
        return cls._get_or_create(
            "azure_tools", "AZURE_TOOLS_MCP_URL", "http://localhost:3004"
        )

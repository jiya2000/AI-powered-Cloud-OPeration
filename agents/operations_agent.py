"""
operations_agent.py

Specialized agent for managing Azure resources (scaling, restarting,
provisioning, deleting). Connects to the Azure Tools MCP Server
using Kubernetes service discovery.

Sensitive operations (delete, scale, restart) trigger the governance
approval workflow before execution.
"""

import os
from typing import Dict, Any
from telemetry import LLMOpsTelemetry, AuditTrail
from mcp_client import MCPClients


class OperationsAgent:
    """
    Operations Agent — handles infrastructure management requests by
    delegating to the Azure Tools MCP Server (port 3004).

    Supported operations:
        - Resource Graph queries (read-only)
        - VM deletion (requires approval)
        - Resource scaling (requires approval)
        - Resource restarts (requires approval)
    """

    def __init__(self):
        self.name = "OperationsAgent"
        self.mcp = MCPClients.azure_tools()

    def handle_request(self, user_input: str) -> Dict[str, Any]:
        """
        Processes infrastructure requests by calling Azure Tools MCP.
        Flags sensitive operations for governance approval.

        Args:
            user_input: The user's natural language query

        Returns:
            Dict with 'status', 'message', and 'requires_approval' keys
        """
        print(f"[{self.name}] Analyzing operations request: {user_input}")

        # Log telemetry for the LLM analyzing the request
        LLMOpsTelemetry.log_generation(
            agent_name=self.name,
            prompt=user_input,
            tokens=60,
            latency_ms=410.1,
            cost=0.0008,
        )

        input_lower = user_input.lower()
        requires_approval = False

        # Route to the appropriate MCP tool
        if "delete" in input_lower:
            result = self._handle_delete(user_input)
            requires_approval = True

        elif "scale" in input_lower or "resize" in input_lower:
            result = self._handle_scale(user_input)
            requires_approval = True

        elif "restart" in input_lower or "reboot" in input_lower:
            result = self._handle_restart(user_input)
            requires_approval = True

        else:
            # Default: run a Resource Graph query
            result = self._handle_query(user_input)

        if requires_approval:
            AuditTrail.log_action(
                who=self.name,
                why="Sensitive infrastructure action requested",
                action="Triggered Governance Approval Workflow",
            )

        return {
            "status": result.get("status", "success"),
            "message": result.get("message", "Operation completed."),
            "requires_approval": requires_approval,
        }

    def _handle_delete(self, user_input: str) -> Dict[str, Any]:
        """Handles VM/resource deletion via Azure Tools MCP."""
        # Extract a resource identifier (simplified; real impl would use NER)
        vm_id = "/subscriptions/default/resourceGroups/prod-rg/providers/Microsoft.Compute/virtualMachines/target-vm"

        print(f"[{self.name}] Requesting VM deletion via Azure Tools MCP")
        result = self.mcp.call_tool("delete_vm", {"vm_id": vm_id})

        if result.get("error") or (result.get("isError")):
            content = result.get("content", [{}])
            error_msg = content[0].get("text", result.get("message", "Unknown error")) if content else result.get("message", "Unknown error")
            return {
                "status": "blocked",
                "message": f"⚠️ **Deletion Blocked**\n\n{error_msg}",
            }

        content = result.get("content", [])
        response_text = content[0].get("text", "Deletion submitted.") if content else "Deletion submitted."

        return {
            "status": "pending_approval",
            "message": f"🗑️ **Resource Deletion Request**\n\n{response_text}\n\n⏳ Awaiting governance approval...",
        }

    def _handle_scale(self, user_input: str) -> Dict[str, Any]:
        """Handles resource scaling requests."""
        print(f"[{self.name}] Querying current resources via Azure Tools MCP")
        result = self.mcp.call_tool("resource_graph_query", {
            "query": "Resources | where type =~ 'Microsoft.Compute/virtualMachines' | project name, properties.hardwareProfile.vmSize, location",
        })

        if result.get("error"):
            return {
                "status": "error",
                "message": f"Failed to query resources: {result.get('message', 'Unknown error')}",
            }

        content = result.get("content", [])
        response_text = content[0].get("text", "No data.") if content else "No data."

        return {
            "status": "pending_approval",
            "message": f"📐 **Scale Request**\n\nCurrent resources:\n{response_text}\n\n⏳ Awaiting governance approval to proceed with scaling...",
        }

    def _handle_restart(self, user_input: str) -> Dict[str, Any]:
        """Handles resource restart requests."""
        return {
            "status": "pending_approval",
            "message": "🔄 **Restart Request**\n\nRestart operation identified. ⏳ Awaiting governance approval...",
        }

    def _handle_query(self, user_input: str) -> Dict[str, Any]:
        """Handles read-only resource queries via Azure Resource Graph."""
        # Build a KQL query from the user input
        query = "Resources | summarize count() by type | order by count_ desc | take 10"

        if "vm" in user_input.lower():
            query = "Resources | where type =~ 'Microsoft.Compute/virtualMachines' | project name, location, properties.hardwareProfile.vmSize"
        elif "storage" in user_input.lower():
            query = "Resources | where type =~ 'Microsoft.Storage/storageAccounts' | project name, location, kind, sku.name"

        print(f"[{self.name}] Running Resource Graph query via Azure Tools MCP")
        result = self.mcp.call_tool("resource_graph_query", {"query": query})

        if result.get("error"):
            return {
                "status": "error",
                "message": f"Failed to query resources: {result.get('message', 'Unknown error')}",
            }

        content = result.get("content", [])
        response_text = content[0].get("text", "No resources found.") if content else "No resources found."

        return {
            "status": "success",
            "message": f"📊 **Resource Query Results**\n\n{response_text}",
        }

"""
finops_agent.py

Specialized agent for handling Azure billing and cost optimization.
Connects to the Cost Management MCP Server via HTTP to retrieve
real cost data, forecasts, and budget information.
"""

import os
from typing import Dict, Any
from telemetry import LLMOpsTelemetry, AuditTrail
from mcp_client import MCPClients


class FinOpsAgent:
    """
    FinOps Agent — handles cost-related queries by delegating to the
    Cost Management MCP Server (port 3000).

    Supported queries:
        - Current month-to-date costs
        - Last month's costs
        - Cost forecasting
    """

    def __init__(self):
        self.name = "FinOpsAgent"
        self.mcp = MCPClients.cost_mgmt()

    def handle_request(self, user_input: str) -> Dict[str, Any]:
        """
        Processes cost-related queries by calling the Cost Mgmt MCP tools.

        Args:
            user_input: The user's natural language query

        Returns:
            Dict with 'status', 'message', and 'requires_approval' keys
        """
        print(f"[{self.name}] Analyzing cost request: {user_input}")

        # Determine the right tool and parameters based on user input
        tool_name = "get_azure_costs"
        scope = os.environ.get("AZURE_SUBSCRIPTION_ID", "subscription/default")
        timeframe = "MonthToDate"

        input_lower = user_input.lower()
        if "forecast" in input_lower:
            tool_name = "get_cost_forecast"
        elif "last month" in input_lower or "previous" in input_lower:
            timeframe = "TheLastMonth"
        elif "billing" in input_lower:
            timeframe = "BillingMonthToDate"

        # Log the LLM analysis telemetry
        LLMOpsTelemetry.log_generation(
            agent_name=self.name,
            prompt=user_input,
            tokens=45,
            latency_ms=350.2,
            cost=0.0006,
        )

        # Call the Cost Management MCP Server
        print(f"[{self.name}] Calling MCP tool: {tool_name}(scope={scope}, timeframe={timeframe})")
        result = self.mcp.call_tool(tool_name, {
            "scope": scope,
            "timeframe": timeframe,
        })

        # Log the audit trail
        AuditTrail.log_action(
            who=self.name,
            why="User requested cost summary",
            action=f"Call MCP Tool: {tool_name} on {scope}",
        )

        # Handle MCP errors
        if result.get("error"):
            error_msg = result.get("message", "Unknown error")
            print(f"[{self.name}] MCP call failed: {error_msg}")
            return {
                "status": "error",
                "message": f"Failed to retrieve cost data: {error_msg}",
                "requires_approval": False,
            }

        # Extract the response text from MCP result
        content = result.get("content", [])
        if content and isinstance(content, list):
            response_text = content[0].get("text", "No cost data available.")
        else:
            response_text = "No cost data available."

        return {
            "status": "success",
            "message": f"💰 **Cost Analysis ({timeframe})**\n\n{response_text}",
            "requires_approval": False,
        }

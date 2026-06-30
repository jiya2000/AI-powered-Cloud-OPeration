"""
security_agent.py

Specialized agent for auditing RBAC, Azure Policy compliance, and
Microsoft Defender for Cloud alerts.

Connects to two MCP servers:
    - Policy MCP (port 3001) — for compliance and policy queries
    - Security MCP (port 3003) — for RBAC and Defender alert queries
"""

import os
from typing import Dict, Any
from telemetry import LLMOpsTelemetry, AuditTrail
from mcp_client import MCPClients


class SecurityAgent:
    """
    Security Agent — handles compliance and security queries by delegating
    to the Policy MCP and Security MCP servers.

    Supported queries:
        - Azure Policy compliance checks
        - RBAC role assignment audits
        - Microsoft Defender for Cloud alerts
        - Permission auditing
    """

    def __init__(self):
        self.name = "SecurityAgent"
        self.policy_mcp = MCPClients.policy()
        self.security_mcp = MCPClients.security()

    def handle_request(self, user_input: str) -> Dict[str, Any]:
        """
        Processes compliance and security requests by routing to the
        appropriate MCP server.

        Args:
            user_input: The user's natural language query

        Returns:
            Dict with 'status', 'message', and 'requires_approval' keys
        """
        print(f"[{self.name}] Analyzing security request: {user_input}")

        # Log telemetry
        LLMOpsTelemetry.log_generation(
            agent_name=self.name,
            prompt=user_input,
            tokens=80,
            latency_ms=500.5,
            cost=0.0010,
        )

        input_lower = user_input.lower()
        requires_approval = False

        # Route to the right MCP server and tool based on query content
        if "policy" in input_lower or "compliance" in input_lower:
            result = self._check_compliance(user_input)
            mcp_tool = "check_compliance"

        elif "defender" in input_lower or "alert" in input_lower:
            result = self._check_defender_alerts(user_input)
            mcp_tool = "check_defender_alerts"

        elif "rbac" in input_lower or "role" in input_lower or "permission" in input_lower:
            result = self._audit_rbac(user_input)
            mcp_tool = "read_rbac_assignments"

            # Modifying RBAC requires approval
            if any(kw in input_lower for kw in ["change", "modify", "update", "delete", "remove"]):
                requires_approval = True

        else:
            # Default to a compliance check
            result = self._check_compliance(user_input)
            mcp_tool = "check_compliance"

        # Log audit trail
        AuditTrail.log_action(
            who=self.name,
            why="Security audit requested",
            action=f"Call MCP Tool: {mcp_tool}",
        )

        return {
            "status": result.get("status", "success"),
            "message": result.get("message", "Security check completed."),
            "requires_approval": requires_approval,
        }

    def _check_compliance(self, user_input: str) -> Dict[str, Any]:
        """Calls the Policy MCP to check compliance status."""
        scope = os.environ.get("AZURE_SUBSCRIPTION_ID", "subscription/default")

        print(f"[{self.name}] Checking compliance via Policy MCP")
        result = self.policy_mcp.call_tool("check_compliance", {
            "scope": scope,
        })

        if result.get("error"):
            return {
                "status": "error",
                "message": f"Failed to check compliance: {result.get('message', 'Unknown error')}",
            }

        content = result.get("content", [])
        response_text = content[0].get("text", "No compliance data.") if content else "No compliance data."

        return {
            "status": "success",
            "message": f"🛡️ **Compliance Report**\n\n{response_text}",
        }

    def _check_defender_alerts(self, user_input: str) -> Dict[str, Any]:
        """Calls the Security MCP to get Defender for Cloud alerts."""
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "subscription/default")

        # Check if user specified a severity filter
        severity = None
        input_lower = user_input.lower()
        if "high" in input_lower:
            severity = "High"
        elif "medium" in input_lower:
            severity = "Medium"
        elif "low" in input_lower:
            severity = "Low"

        print(f"[{self.name}] Checking Defender alerts via Security MCP")
        args: Dict[str, Any] = {"subscription_id": subscription_id}
        if severity:
            args["severity"] = severity

        result = self.security_mcp.call_tool("check_defender_alerts", args)

        if result.get("error"):
            return {
                "status": "error",
                "message": f"Failed to fetch alerts: {result.get('message', 'Unknown error')}",
            }

        content = result.get("content", [])
        response_text = content[0].get("text", "No alerts.") if content else "No alerts."

        return {
            "status": "success",
            "message": f"🚨 **Security Alerts**\n\n{response_text}",
        }

    def _audit_rbac(self, user_input: str) -> Dict[str, Any]:
        """Calls the Security MCP to audit RBAC role assignments."""
        scope = os.environ.get("AZURE_SUBSCRIPTION_ID", "subscription/default")

        print(f"[{self.name}] Auditing RBAC via Security MCP")
        result = self.security_mcp.call_tool("read_rbac_assignments", {
            "scope": scope,
        })

        if result.get("error"):
            return {
                "status": "error",
                "message": f"Failed to audit RBAC: {result.get('message', 'Unknown error')}",
            }

        content = result.get("content", [])
        response_text = content[0].get("text", "No RBAC data.") if content else "No RBAC data."

        return {
            "status": "success",
            "message": f"🔐 **RBAC Audit**\n\n{response_text}",
        }

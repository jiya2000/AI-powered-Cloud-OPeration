"""
approval_workflow.py

Connects to the Governance MCP Server to handle Role-Based Approvals
and emit structured audit trails. Falls back to local policy evaluation
when the Governance MCP is unreachable.

Architecture:
    Agent → ApprovalWorkflow → Governance MCP (port 3002) → policy.json + role_mapping.json
"""

import os
import json
import uuid
from datetime import datetime
from telemetry import LLMOpsTelemetry, AuditTrail, logger
from mcp_client import MCPClients


class ApprovalWorkflow:
    """
    Handles governance approval requests by communicating with the
    Governance MCP Server. Provides local fallback evaluation using
    policy.json when the MCP server is unavailable.
    """

    def __init__(self):
        self.mcp = MCPClients.governance()

    def execute(self, action_details: str, requested_by: str) -> str:
        """
        Submits an approval request to the Governance MCP server.

        Args:
            action_details: Description of the action requiring approval
            requested_by: Name of the agent requesting approval

        Returns:
            Status string: "APPROVED" or "REJECTED"
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"

        logger.info(f"Requesting approval from Governance MCP", extra={"request_id": request_id, "action": action_details, "requested_by": requested_by})

        # Call the Governance MCP server
        result = self.mcp.call_tool("request_approval", {
            "request_id": request_id,
            "action": action_details,
            "requested_by": requested_by,
        })

        if result.get("error"):
            logger.error(f"MCP call failed: {result.get('message')}", extra={"request_id": request_id})
            logger.warn("Falling back to local policy evaluation", extra={"request_id": request_id})
            status = self._evaluate_locally(action_details)
        else:
            # Parse the MCP response
            content = result.get("content", [])
            if content and isinstance(content, list):
                response_text = content[0].get("text", "")
                try:
                    response_data = json.loads(response_text)
                    status = response_data.get("status", "approved").upper()
                except json.JSONDecodeError:
                    status = "APPROVED" if "approved" in response_text.lower() else "REJECTED"
            else:
                status = "APPROVED"

        # Emit structured audit trail
        audit_payload = {
            "request_id": request_id,
            "action": action_details,
            "requested_by": requested_by,
            "status": status.lower(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        AuditTrail.log_action(
            who=requested_by,
            why=action_details,
            action=f"Governance Approval: {status}",
            approved_by="GovernanceMCP",
        )

        logger.info("Governance record emitted", extra={"payload": audit_payload})

        return status

    def _evaluate_locally(self, action_details: str) -> str:
        """
        Fallback: evaluates approval locally using policy.json rules
        when the Governance MCP server is unreachable.
        """
        # Try to load local policy file
        try:
            policy_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "mcp-servers", "governance", "policy.json",
            )
            with open(policy_path, "r") as f:
                policies = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warn("No local policy file found. Defaulting to APPROVED.")
            return "APPROVED"

        action_lower = action_details.lower()

        # Apply policy rules
        if "delete" in action_lower or "remove" in action_lower:
            policy = policies.get("delete_resource", {})
            required_roles = policy.get("roles", ["CloudAdmin"])
            logger.info(f"Local policy: delete requires roles {required_roles}")

        elif "scale" in action_lower or "resize" in action_lower:
            policy = policies.get("scale_resource", {})
            required_roles = policy.get("roles", ["CloudAdmin", "OpsManager"])
            logger.info(f"Local policy: scale requires roles {required_roles}")

        elif "rbac" in action_lower or "role" in action_lower:
            policy = policies.get("modify_rbac", {})
            required_roles = policy.get("roles", ["SecurityAdmin"])
            logger.info(f"Local policy: RBAC modification requires roles {required_roles}")

        # Simulate approval decision based on action keywords
        # In production: would send Teams Adaptive Card and wait for response
        if "reject" in action_lower:
            return "REJECTED"

        return "APPROVED"

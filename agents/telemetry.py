"""
telemetry.py

Handles LLMOps Observability and Structured Audit Trails via Azure Application Insights.
"""

import os
import time
import json
from datetime import datetime
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Initialize Azure Monitor if Connection String is provided
_APPINSIGHTS_CONN_STR = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _APPINSIGHTS_CONN_STR:
    configure_azure_monitor(connection_string=_APPINSIGHTS_CONN_STR)

tracer = trace.get_tracer(__name__)

class LLMOpsTelemetry:
    """
    Handles logging of LLM interactions and Agent execution metrics.
    """
    @staticmethod
    def log_generation(agent_name: str, prompt: str, tokens: int, latency_ms: float, cost: float):
        """
        Logs a custom event to Application Insights for LLMOps tracking.
        """
        with tracer.start_as_current_span(f"LLM_Generation_{agent_name}") as span:
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("llm.prompt", prompt)
            span.set_attribute("llm.tokens", tokens)
            span.set_attribute("llm.latency_ms", latency_ms)
            span.set_attribute("llm.cost_usd", cost)
            print(f"[TELEMETRY] Logged generation for {agent_name}: {tokens} tokens, {latency_ms}ms")

class AuditTrail:
    """
    Handles the Structured Audit Trail for enterprise compliance.
    """
    @staticmethod
    def log_action(who: str, why: str, action: str, approved_by: str = "auto"):
        """
        Emits a structured JSON audit log.
        """
        audit_payload = {
            "who": who,
            "why": why,
            "action": action,
            "time": datetime.utcnow().isoformat() + "Z",
            "approved_by": approved_by
        }
        
        with tracer.start_as_current_span(f"Audit_Action_{action}") as span:
            span.set_attribute("audit.payload", json.dumps(audit_payload))
            span.set_attribute("audit.action", action)
            span.set_status(Status(StatusCode.OK))
            print(f"[AUDIT] {json.dumps(audit_payload)}")

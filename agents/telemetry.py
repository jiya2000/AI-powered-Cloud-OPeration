"""
telemetry.py

Handles structured logging, OpenTelemetry integration (Application Insights),
and structured audit trails for enterprise compliance.
"""

import os
import json
import logging
import sys
from datetime import datetime
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# ─── Structured JSON Logger Setup ─────────────────────────────────────
def setup_logging():
    logger = logging.getLogger("azure_mcp_agent")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = setup_logging()


# ─── Application Insights Setup ───────────────────────────────────────
app_insights_conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

if app_insights_conn_str:
    try:
        configure_azure_monitor(connection_string=app_insights_conn_str)
        logger.info("Azure Application Insights configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure Application Insights: {e}")
else:
    logger.warn("APPLICATIONINSIGHTS_CONNECTION_STRING not set. Metrics will not be sent to Azure.")

tracer = trace.get_tracer(__name__)


# ─── Telemetry Helpers ────────────────────────────────────────────────
class LLMOpsTelemetry:
    """Tracks token usage, latency, and costs for LLM operations."""
    
    @staticmethod
    def log_generation(agent_name: str, prompt: str, tokens: int, latency_ms: float, cost: float):
        payload = {
            "type": "llm_generation",
            "agent": agent_name,
            "tokens": tokens,
            "latency_ms": latency_ms,
            "cost_usd": cost,
            "prompt_length": len(prompt)
        }
        # Log to structured JSON log
        logger.info(json.dumps(payload))
        
        # Log to App Insights span
        with tracer.start_as_current_span(f"LLM_Generation_{agent_name}") as span:
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("llm.prompt", prompt)
            span.set_attribute("llm.tokens", tokens)
            span.set_attribute("llm.latency_ms", latency_ms)
            span.set_attribute("llm.cost_usd", cost)


class AuditTrail:
    """Provides a structured audit trail for sensitive actions."""
    
    @staticmethod
    def log_action(who: str, why: str, action: str, approved_by: str = "auto"):
        payload = {
            "type": "audit_trail",
            "user": who,
            "reason": why,
            "action": action,
            "approved_by": approved_by,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        # Log to structured JSON log
        logger.info(json.dumps(payload))
        
        # Log to App Insights span
        with tracer.start_as_current_span(f"Audit_Action_{action}") as span:
            span.set_attribute("audit.payload", json.dumps(payload))
            span.set_attribute("audit.action", action)
            span.set_status(Status(StatusCode.OK))

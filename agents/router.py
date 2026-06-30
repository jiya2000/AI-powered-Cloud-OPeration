"""
router.py

The main LangGraph entry point. Routes incoming user requests to specialized agents
using intent classification, delegates to the appropriate agent, and handles
governance approval workflows for sensitive operations.

Architecture:
    User → Bot Framework → app.py → router.py (LangGraph) → Agent → MCP Server
"""

import time
from typing import Dict, TypedDict, Any
from langgraph.graph import StateGraph, END
from telemetry import LLMOpsTelemetry, logger
from approval_workflow import ApprovalWorkflow
from finops_agent import FinOpsAgent
from security_agent import SecurityAgent
from operations_agent import OperationsAgent
from memory import AgentMemoryStore
from llm_provider import get_llm, classify_intent


# ─── Initialize Agent Instances ───────────────────────────────────────
finops = FinOpsAgent()
security = SecurityAgent()
operations = OperationsAgent()
memory_store = AgentMemoryStore()
approval = ApprovalWorkflow()

# Initialize LLM (auto-detects Groq/Gemini/Azure OpenAI, or None)
llm = get_llm()


# ─── State Schema ─────────────────────────────────────────────────────
class AgentState(TypedDict):
    user_input: str
    session_id: str
    intent: str
    agent_response: str
    requires_approval: bool
    approval_status: str


# ─── Graph Nodes ──────────────────────────────────────────────────────

def analyze_intent(state: AgentState) -> Dict[str, Any]:
    """
    Classifies the user's request into an intent category.

    Uses an LLM (Groq/Gemini/Azure OpenAI) when available for nuanced
    intent understanding. Falls back to keyword matching if no LLM is
    configured. The LLM provider is auto-detected from environment variables.
    """
    start_time = time.time()

    # Classify using LLM if available, else keywords
    intent = classify_intent(state["user_input"], llm)
    using_llm = llm is not None

    elapsed_ms = (time.time() - start_time) * 1000

    # Log telemetry with real metrics when using LLM
    LLMOpsTelemetry.log_generation(
        agent_name="RouterAgent",
        prompt=state["user_input"],
        tokens=25 if using_llm else 0,
        latency_ms=round(elapsed_ms, 1),
        cost=0.0001 if using_llm else 0.0,
    )

    logger.info(f"Intent classified", extra={"intent": intent, "source": "LLM" if using_llm else "keywords", "elapsed_ms": round(elapsed_ms, 1)})

    # Persist intent to session memory
    session_id = state.get("session_id", "default")
    memory_store.save_state(
        session_id,
        {"last_intent": intent, "last_input": state["user_input"]},
    )

    return {"intent": intent}


def route_request(state: AgentState) -> str:
    """Conditional edge: routes to the appropriate agent node based on classified intent."""
    intent = state["intent"]
    routing_map = {
        "finops": "finops_agent",
        "security": "security_agent",
        "operations": "operations_agent",
    }
    return routing_map.get(intent, "fallback")


def finops_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the FinOps agent which calls the Cost Management MCP."""
    result = finops.handle_request(state["user_input"])
    return {
        "agent_response": result["message"],
        "requires_approval": result.get("requires_approval", False),
    }


def security_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the Security agent which calls the Policy & Security MCPs."""
    result = security.handle_request(state["user_input"])
    return {
        "agent_response": result["message"],
        "requires_approval": result.get("requires_approval", False),
    }


def operations_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the Operations agent which calls the Azure Tools MCP."""
    result = operations.handle_request(state["user_input"])
    return {
        "agent_response": result["message"],
        "requires_approval": result.get("requires_approval", False),
    }


def fallback_node(state: AgentState) -> Dict[str, Any]:
    """Handles unknown intents with a helpful message."""
    return {
        "agent_response": (
            "I can help with:\n"
            "• **Cost Management** — billing, spend analysis, forecasting\n"
            "• **Security & Compliance** — RBAC audit, policy checks, Defender alerts\n"
            "• **Infrastructure Operations** — scaling, restarting, provisioning resources\n\n"
            "Could you rephrase your request?"
        ),
        "requires_approval": False,
    }


def approval_node(state: AgentState) -> Dict[str, Any]:
    """Triggers the Governance MCP approval workflow for sensitive actions."""
    status = approval.execute(
        action_details=state["user_input"],
        requested_by="RouterAgent",
    )

    if status == "REJECTED":
        return {
            "agent_response": (
                f"⛔ **Request Denied** — Your action was rejected by the governance workflow.\n\n"
                f"Original analysis: {state.get('agent_response', 'N/A')}"
            ),
            "approval_status": "REJECTED",
        }

    return {
        "approval_status": status,
        "agent_response": (
            f"✅ **Request Approved & Executed**\n\n"
            f"{state.get('agent_response', '')}"
        ),
    }


def check_approval(state: AgentState) -> str:
    """Conditional edge: routes to approval node if the action requires it."""
    if state.get("requires_approval"):
        return "approval"
    return END


# ─── Build the LangGraph Workflow ─────────────────────────────────────

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("analyze", analyze_intent)
workflow.add_node("finops_agent", finops_node)
workflow.add_node("security_agent", security_node)
workflow.add_node("operations_agent", operations_node)
workflow.add_node("fallback", fallback_node)
workflow.add_node("approval", approval_node)

# Set entry point
workflow.set_entry_point("analyze")

# Router: intent → agent
workflow.add_conditional_edges(
    "analyze",
    route_request,
    {
        "finops_agent": "finops_agent",
        "security_agent": "security_agent",
        "operations_agent": "operations_agent",
        "fallback": "fallback",
    },
)

# Approval check for sensitive operations
workflow.add_conditional_edges(
    "operations_agent", check_approval, {"approval": "approval", END: END}
)
workflow.add_conditional_edges(
    "security_agent", check_approval, {"approval": "approval", END: END}
)

# Terminal edges
workflow.add_edge("finops_agent", END)
workflow.add_edge("fallback", END)
workflow.add_edge("approval", END)

# Compile the graph — exported for app.py
graph = workflow.compile()

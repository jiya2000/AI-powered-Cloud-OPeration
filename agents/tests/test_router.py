import pytest
from router import route_intent

def test_route_intent():
    # Test cost intent routing
    state_cost = {"user_input": "cost", "intent": "cost"}
    assert route_intent(state_cost) == "finops_agent"

    # Test security intent routing
    state_sec = {"user_input": "security", "intent": "security"}
    assert route_intent(state_sec) == "security_agent"

    # Test operations intent routing
    state_ops = {"user_input": "operations", "intent": "operations"}
    assert route_intent(state_ops) == "operations_agent"

    # Test fallback
    state_unknown = {"user_input": "hello", "intent": "unknown"}
    assert route_intent(state_unknown) == "__end__"

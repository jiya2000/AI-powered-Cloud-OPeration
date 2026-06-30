import pytest
from llm_provider import _keyword_classify

def test_keyword_classify_cost():
    intent = _keyword_classify("how much did we spend on azure yesterday?")
    assert intent == "cost"

def test_keyword_classify_security():
    intent = _keyword_classify("check my rbac roles")
    assert intent == "security"

def test_keyword_classify_operations():
    intent = _keyword_classify("delete vm prod-db")
    assert intent == "operations"

def test_keyword_classify_unknown():
    intent = _keyword_classify("tell me a joke")
    assert intent == "unknown"

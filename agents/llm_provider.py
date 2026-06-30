"""
llm_provider.py

Configurable LLM provider factory. Automatically selects the best available
LLM based on environment variables. Supports Azure OpenAI, Groq (free),
Google Gemini (free), and falls back to keyword-based classification.

Usage:
    from llm_provider import get_llm, classify_intent

    # Get a LangChain LLM instance
    llm = get_llm()

    # Or directly classify intent
    intent = classify_intent("What's my Azure spend this month?")
    # Returns: "finops"
"""

import os
from typing import Optional


def get_llm() -> Optional[object]:
    """
    Returns the best available LangChain LLM based on configured API keys.

    Priority order:
        1. Azure OpenAI (enterprise)  — AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY
        2. Groq (free tier)           — GROQ_API_KEY
        3. Google Gemini (free tier)  — GOOGLE_API_KEY
        4. None (falls back to keyword matching)

    Returns:
        A LangChain ChatModel instance, or None if no LLM is configured.
    """

    # Option 1: Azure OpenAI (production / enterprise)
    if os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_API_KEY"):
        try:
            from langchain_openai import AzureChatOpenAI

            llm = AzureChatOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
                temperature=0,
                max_tokens=100,
            )
            print("[LLM] Using Azure OpenAI")
            return llm
        except ImportError:
            print("[LLM] langchain-openai not installed. Trying next provider...")
        except Exception as e:
            print(f"[LLM] Azure OpenAI init failed: {e}. Trying next provider...")

    # Option 2: Groq (free tier — Llama 3.3 70B, very fast)
    if os.environ.get("GROQ_API_KEY"):
        try:
            from langchain_groq import ChatGroq

            llm = ChatGroq(
                api_key=os.environ["GROQ_API_KEY"],
                model_name=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                temperature=0,
                max_tokens=100,
            )
            print("[LLM] Using Groq (free tier — Llama 3.3 70B)")
            return llm
        except ImportError:
            print("[LLM] langchain-groq not installed. Trying next provider...")
        except Exception as e:
            print(f"[LLM] Groq init failed: {e}. Trying next provider...")

    # Option 3: Google Gemini (free tier — 15 RPM)
    if os.environ.get("GOOGLE_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(
                model=os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash"),
                google_api_key=os.environ["GOOGLE_API_KEY"],
                temperature=0,
                max_output_tokens=100,
            )
            print("[LLM] Using Google Gemini (free tier)")
            return llm
        except ImportError:
            print("[LLM] langchain-google-genai not installed. Trying next provider...")
        except Exception as e:
            print(f"[LLM] Google Gemini init failed: {e}. Trying next provider...")

    # Fallback: No LLM available
    print("[LLM] No LLM provider configured. Using keyword-based intent classification.")
    print("[LLM] Set GROQ_API_KEY (free) or GOOGLE_API_KEY (free) to enable LLM routing.")
    return None


def classify_intent(user_input: str, llm: Optional[object] = None) -> str:
    """
    Classifies the user's request into an intent category.

    If an LLM is available, uses it for nuanced understanding.
    Otherwise, falls back to keyword matching.

    Args:
        user_input: The user's natural language query
        llm: Optional LangChain ChatModel instance

    Returns:
        One of: "finops", "security", "operations", or "unknown"
    """

    # If no LLM, use keyword matching
    if llm is None:
        return _keyword_classify(user_input)

    # Use LLM for intent classification
    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        system_prompt = """You are an intent classifier for an Azure cloud operations bot.
Classify the user's message into EXACTLY ONE of these categories:

- finops: Cost management, billing, spend analysis, budgets, forecasting, invoices, pricing
- security: RBAC, policy compliance, role assignments, Defender alerts, permissions, auditing
- operations: Resource management, scaling, restarting, deleting, provisioning, deploying, VMs, infrastructure
- unknown: Anything that doesn't fit the above categories

Respond with ONLY the category name (one word). Nothing else."""

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ])

        intent = response.content.strip().lower()

        # Validate the response is one of our known intents
        valid_intents = {"finops", "security", "operations", "unknown"}
        if intent in valid_intents:
            return intent

        # If LLM returned something unexpected, try to map it
        if any(kw in intent for kw in ["cost", "billing", "finops", "budget"]):
            return "finops"
        if any(kw in intent for kw in ["security", "compliance", "rbac", "policy"]):
            return "security"
        if any(kw in intent for kw in ["operations", "infrastructure", "resource", "deploy"]):
            return "operations"

        return "unknown"

    except Exception as e:
        print(f"[LLM] Classification failed: {e}. Falling back to keywords.")
        return _keyword_classify(user_input)


def _keyword_classify(user_input: str) -> str:
    """
    Fallback keyword-based intent classification.
    Used when no LLM provider is configured.
    """
    input_lower = user_input.lower()

    cost_keywords = ["cost", "billing", "spend", "budget", "forecast", "invoice", "price"]
    security_keywords = ["policy", "rbac", "compliance", "role", "permission", "defender", "alert", "audit"]
    ops_keywords = ["delete", "restart", "scale", "provision", "deploy", "vm", "resource", "infrastructure"]

    if any(kw in input_lower for kw in cost_keywords):
        return "finops"
    elif any(kw in input_lower for kw in security_keywords):
        return "security"
    elif any(kw in input_lower for kw in ops_keywords):
        return "operations"

    return "unknown"

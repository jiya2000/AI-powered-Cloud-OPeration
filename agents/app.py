"""
app.py

Main entry point for the Azure MCP Agent bot server.
Receives messages from Microsoft Teams via Bot Framework, passes them
through the LangGraph router, and sends responses back to the user.

Endpoints:
    POST /api/messages  — Bot Framework message handler
    GET  /health        — Kubernetes health probe
"""

import sys
import os
import traceback
import logging
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.schema import Activity, ActivityTypes

# Import the compiled LangGraph
from router import graph

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── Bot Adapter Setup ────────────────────────────────────────────────
APP_ID = os.environ.get("MicrosoftAppId", "")
APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")

SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)


async def on_error(context: TurnContext, error: Exception):
    """Global error handler for the Bot Framework adapter."""
    logger.error(f"[on_turn_error] unhandled error: {error}")
    traceback.print_exc()
    await context.send_activity(
        "⚠️ The bot encountered an error. Please try again or contact support."
    )


ADAPTER.on_turn_error = on_error


# ─── Message Handler ──────────────────────────────────────────────────
async def messages(req: web.Request) -> web.Response:
    """
    Main bot message handler.
    Receives incoming Bot Framework activities, processes message activities
    through the LangGraph router, and returns the AI response.
    """
    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def process_message(turn_context: TurnContext):
        # Only process text messages from users
        if turn_context.activity.type != ActivityTypes.message:
            return

        user_input = turn_context.activity.text
        if not user_input:
            return

        # Send typing indicator while processing
        typing_activity = Activity(type=ActivityTypes.typing)
        await turn_context.send_activity(typing_activity)

        # Build the initial state for the LangGraph
        session_id = "default"
        if turn_context.activity.conversation:
            session_id = turn_context.activity.conversation.id

        initial_state = {
            "user_input": user_input,
            "session_id": session_id,
            "intent": "",
            "agent_response": "",
            "requires_approval": False,
            "approval_status": "",
        }

        try:
            # Run the LangGraph pipeline
            result = graph.invoke(initial_state)
            ai_response = result.get(
                "agent_response", "I couldn't process that request."
            )
            await turn_context.send_activity(ai_response)
        except Exception as e:
            logger.error(f"[LangGraph Error] {e}")
            traceback.print_exc()
            await turn_context.send_activity(
                "Sorry, I encountered an error processing your request. Please try again."
            )

    try:
        await ADAPTER.process_activity(activity, auth_header, process_message)
        return web.Response(status=201)
    except Exception as e:
        raise e


# ─── Health Check ─────────────────────────────────────────────────────
async def health(req: web.Request) -> web.Response:
    """Kubernetes liveness/readiness probe endpoint."""
    return web.json_response({"status": "healthy", "service": "azure-mcp-agent"})


# ─── Application Setup ───────────────────────────────────────────────
app = web.Application()
app.router.add_post("/api/messages", messages)
app.router.add_get("/health", health)


if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", "8080"))
        logger.info(f"Starting Azure MCP Bot Server on port {port}...")
        web.run_app(app, host="0.0.0.0", port=port)
    except Exception as error:
        raise error

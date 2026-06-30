"""
memory.py

Handles Agent Session Memory using Azure Cosmos DB.
"""

import os
import json
from azure.cosmos import CosmosClient, PartitionKey, exceptions

class AgentMemoryStore:
    """
    Connects to Azure Cosmos DB to persist LangGraph agent state.
    """
    def __init__(self):
        self.endpoint = os.getenv("COSMOS_ENDPOINT")
        self.key = os.getenv("COSMOS_KEY")
        
        if not self.endpoint or not self.key:
            print("[MEMORY] Warning: Cosmos DB credentials missing. Falling back to in-memory.")
            self.client = None
            self.memory_cache = {}
            return

        self.client = CosmosClient(self.endpoint, self.key)
        self.database = self.client.get_database_client("agent-memory")
        
        # We partition by session_id to group agent interactions per user/thread
        self.container = self.database.get_container_client("sessions")

    def save_state(self, session_id: str, state_data: dict):
        """Upserts the current agent state into Cosmos DB."""
        if not self.client:
            self.memory_cache[session_id] = state_data
            return

        document = {
            "id": session_id,
            "partitionKey": session_id,
            "state": state_data
        }
        try:
            self.container.upsert_item(body=document)
            print(f"[MEMORY] Saved state for session {session_id}")
        except exceptions.CosmosHttpResponseError as e:
            print(f"[MEMORY] Error saving state: {e}")

    def load_state(self, session_id: str) -> dict:
        """Retrieves the current agent state from Cosmos DB."""
        if not self.client:
            return self.memory_cache.get(session_id, {})

        try:
            response = self.container.read_item(item=session_id, partition_key=session_id)
            print(f"[MEMORY] Loaded state for session {session_id}")
            return response.get("state", {})
        except exceptions.CosmosResourceNotFoundError:
            return {}
        except exceptions.CosmosHttpResponseError as e:
            print(f"[MEMORY] Error loading state: {e}")
            return {}

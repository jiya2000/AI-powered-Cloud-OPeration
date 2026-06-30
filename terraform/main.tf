terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# ─── Azure Container Registry (ACR) ──────────────────────────────────
# Stores Docker images for the Python agent and MCP server containers.
resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic" # Cost-effective for student credits
  admin_enabled       = true
}

# ─── Log Analytics Workspace ─────────────────────────────────────────
# Central log aggregation for all agent and MCP server telemetry.
resource "azurerm_log_analytics_workspace" "law" {
  name                = "adds-mcp-agent-law"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ─── Application Insights ────────────────────────────────────────────
# LLMOps observability: tracks agent telemetry, token usage, and audit trails.
resource "azurerm_application_insights" "appinsights" {
  name                = "adds-mcp-agent-appinsights"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"
}

# ─── Cosmos DB (Agent Memory) ────────────────────────────────────────
# Stores LangGraph agent session state for conversation continuity.
resource "azurerm_cosmosdb_account" "db" {
  name                = "adds-mcp-agent-memory-db"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # Important for student credits: force free tier
  free_tier_enabled = true

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
  }
}

resource "azurerm_cosmosdb_sql_database" "sqldb" {
  name                = "adds-agent-memory"
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.db.name
}

resource "azurerm_cosmosdb_sql_container" "sessions" {
  name                = "sessions"
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.db.name
  database_name       = azurerm_cosmosdb_sql_database.sqldb.name
  partition_key_path  = "/partitionKey"

  # Auto-expire session data after 7 days
  default_ttl = 604800
}

# ─── Key Vault ────────────────────────────────────────────────────────
# Securely stores Bot Framework credentials, Cosmos DB keys, and API keys.
data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_key_vault" "kv" {
  name                        = "adds-mcagentkv${random_string.suffix.result}"
  location                    = azurerm_resource_group.rg.location
  resource_group_name         = azurerm_resource_group.rg.name
  enabled_for_disk_encryption = true
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false

  sku_name = "standard"
}

# ─── AKS Cluster ─────────────────────────────────────────────────────
# Hosts the agent pod with Python agent + 5 MCP server sidecars.
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "adds-mcp-agent-aks"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "adds-mcpagent"

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_B2s" # Cost-effective instance for the credit balance
  }

  identity {
    type = "SystemAssigned"
  }
}

# ─── ACR Pull Permission for AKS ─────────────────────────────────────
# Allows AKS to pull container images from ACR without manual docker login.
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

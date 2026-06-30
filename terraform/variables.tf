variable "resource_group_name" {
  type        = string
  description = "Name of the resource group."
  default     = "adds-azure-mcp-agent-rg"
}

variable "location" {
  type        = string
  description = "Azure region for all resources."
  default     = "southeastasia"
}

variable "acr_name" {
  type        = string
  description = "Name of the Azure Container Registry (must be globally unique, alphanumeric only)."
  default     = "addsmcpagentacr2026"
}

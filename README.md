# Azure MCP Agent Platform

An enterprise-grade, AI-powered cloud operations platform that uses the **Model Context Protocol (MCP)** architecture to autonomously manage Azure infrastructure. Built with a multi-agent framework, it provides intelligent cost management, security compliance auditing, and infrastructure operations through natural language interactions in Microsoft Teams.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Microsoft Teams                                   │
│                     (User sends message)                                 │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ Bot Framework
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Kubernetes Pod (AKS)                                   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              Python Agent (LangGraph Router)                      │   │
│  │                                                                    │   │
│  │   ┌──────────┐  ┌──────────────┐  ┌────────────────┐            │   │
│  │   │  FinOps   │  │  Security     │  │  Operations    │            │   │
│  │   │  Agent    │  │  Agent        │  │  Agent         │            │   │
│  │   └─────┬────┘  └──────┬───────┘  └───────┬────────┘            │   │
│  │         │               │                   │                      │   │
│  │   ┌─────┴──────────────┴──────────────────┴────────────┐        │   │
│  │   │            MCP Client (HTTP)                         │        │   │
│  │   └─────┬──────────┬───────────┬──────────┬────────────┘        │   │
│  └─────────┼──────────┼───────────┼──────────┼──────────────────────┘   │
│            │          │           │          │                            │
│  ┌─────────▼──┐ ┌────▼─────┐ ┌──▼────────┐ ┌▼──────────┐ ┌──────────┐│
│  │ Cost Mgmt  │ │ Policy   │ │Governance │ │ Security  │ │Azure     ││
│  │ MCP :3000  │ │ MCP :3001│ │MCP :3002  │ │ MCP :3003 │ │Tools :3004│
│  └─────┬──────┘ └────┬─────┘ └──┬────────┘ └┬──────────┘ └──┬───────┘│
│        │             │          │            │               │         │
└────────┼─────────────┼──────────┼────────────┼───────────────┼─────────┘
         │             │          │            │               │
         ▼             ▼          ▼            ▼               ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                     Azure APIs                                │
   │  Cost Management │ Policy │ Defender │ RBAC │ Resource Graph  │
   └──────────────────────────────────────────────────────────────┘
```

## Components

### Python Agents (`agents/`)

| File | Description |
|------|-------------|
| `app.py` | Bot Framework entry point — receives Teams messages, runs LangGraph |
| `router.py` | LangGraph workflow — intent classification & agent routing |
| `finops_agent.py` | Cost analysis agent → calls Cost Management MCP |
| `security_agent.py` | Security audit agent → calls Policy & Security MCPs |
| `operations_agent.py` | Infrastructure ops agent → calls Azure Tools MCP |
| `approval_workflow.py` | Governance approval handler → calls Governance MCP |
| `mcp_client.py` | HTTP client for agent ↔ MCP server communication |
| `memory.py` | Session persistence via Azure Cosmos DB |
| `telemetry.py` | LLMOps observability via Azure Application Insights |

### MCP Servers (`mcp-servers/`)

| Server | Port | Tools |
|--------|------|-------|
| Cost Management | 3000 | `get_azure_costs`, `get_cost_forecast` |
| Policy & Compliance | 3001 | `check_compliance`, `list_policy_assignments`, `evaluate_resource` |
| Governance | 3002 | `request_approval`, `check_approval_status`, `list_pending_approvals` |
| Security | 3003 | `read_rbac_assignments`, `check_defender_alerts`, `audit_permissions` |
| Azure Tools | 3004 | `resource_graph_query`, `delete_vm`, `list_resources` |

### Infrastructure

| Directory | Purpose |
|-----------|---------|
| `terraform/` | IaC for AKS, ACR, Cosmos DB, App Insights, Key Vault |
| `k8s/` | Kubernetes manifests (Deployment, Service, ConfigMap) |
| `.github/workflows/` | CI/CD pipeline (build → push to ACR → deploy to AKS) |

## Prerequisites

- **Azure Subscription** with sufficient credits
- **Azure CLI** (`az`) installed and authenticated
- **Docker** for building container images
- **kubectl** for Kubernetes management
- **Terraform** for infrastructure provisioning
- **Node.js 20+** and **Python 3.11+** for local development

## Quick Start

### 1. Provision Azure Infrastructure

```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### 2. Configure Secrets

```bash
# Copy and fill in your environment variables
cp .env.example .env

# Create Kubernetes secrets from terraform outputs
kubectl create secret generic mcp-secrets \
  --from-literal=COSMOS_ENDPOINT=$(terraform output -raw cosmos_endpoint) \
  --from-literal=COSMOS_KEY=$(terraform output -raw cosmos_primary_key) \
  --from-literal=APPLICATIONINSIGHTS_CONNECTION_STRING=$(terraform output -raw appinsights_connection_string) \
  --from-literal=MicrosoftAppId=<your-bot-app-id> \
  --from-literal=MicrosoftAppPassword=<your-bot-app-password>
```

### 3. Build & Deploy

```bash
# Login to ACR
az acr login --name addsmcpagentacr2026

# Build and push images
docker build -t addsmcpagentacr2026.azurecr.io/python-agent:latest ./agents
docker build -t addsmcpagentacr2026.azurecr.io/mcp-server:latest ./mcp-servers
docker push addsmcpagentacr2026.azurecr.io/python-agent:latest
docker push addsmcpagentacr2026.azurecr.io/mcp-server:latest

# Deploy to AKS
az aks get-credentials --resource-group adds-azure-mcp-agent-rg --name adds-mcp-agent-aks
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 4. Local Development

```bash
# Start MCP servers (in separate terminals)
cd mcp-servers
npm install
npm run dev:cost-mgmt    # Port 3000
npm run dev:policy       # Port 3001
npm run dev:governance   # Port 3002
npm run dev:security     # Port 3003
npm run dev:azure-tools  # Port 3004

# Start the Python agent
cd agents
pip install -r requirements.txt
python app.py            # Port 8080
```

## Governance & Approval Flow

Sensitive operations (delete, scale, restart) follow a strict governance path:

```
User Request → Router → Operations Agent → Approval Check
                                              ↓
                                    Governance MCP (port 3002)
                                              ↓
                                    policy.json evaluation
                                              ↓
                                    role_mapping.json lookup
                                              ↓
                                  ┌─────────────────────────┐
                                  │ APPROVED → Execute action │
                                  │ REJECTED → Deny & audit   │
                                  └─────────────────────────┘
                                              ↓
                                    Structured Audit Trail
                                    (Application Insights)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Framework | LangGraph (multi-agent orchestration) |
| Bot Interface | Microsoft Bot Framework + Teams |
| MCP Servers | TypeScript + Express + MCP SDK |
| Infrastructure | Azure Kubernetes Service (AKS) |
| Memory | Azure Cosmos DB |
| Observability | Azure Application Insights + OpenTelemetry |
| Secrets | Azure Key Vault |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Container Registry | Azure Container Registry (ACR) |

## Project Structure

```
azure-mcp-agent/
├── agents/                     # Python agent layer
│   ├── app.py                  # Bot Framework entry point
│   ├── router.py               # LangGraph workflow
│   ├── finops_agent.py         # Cost management agent
│   ├── security_agent.py       # Security audit agent
│   ├── operations_agent.py     # Infrastructure ops agent
│   ├── approval_workflow.py    # Governance approval handler
│   ├── mcp_client.py           # HTTP client for MCP servers
│   ├── memory.py               # Cosmos DB session store
│   ├── telemetry.py            # Application Insights telemetry
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile
├── mcp-servers/                # TypeScript MCP server layer
│   ├── cost-mgmt/server.ts     # Port 3000
│   ├── policy/server.ts        # Port 3001
│   ├── governance/             # Port 3002
│   │   ├── server.ts
│   │   ├── policy.json         # Governance policy rules
│   │   └── role_mapping.json   # Role-to-approver mapping
│   ├── security/server.ts      # Port 3003
│   ├── azure-tools/server.ts   # Port 3004
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
├── k8s/                        # Kubernetes manifests
│   ├── deployment.yaml         # Pod with agent + 5 MCP sidecars
│   ├── service.yaml            # LoadBalancer service
│   └── configmap.yaml          # MCP server URLs
├── terraform/                  # Infrastructure as Code
│   ├── main.tf                 # AKS, ACR, Cosmos DB, etc.
│   ├── variables.tf
│   └── outputs.tf
├── .github/workflows/ci.yml   # CI/CD pipeline
├── .env.example                # Environment variable template
├── .gitignore
└── README.md
```

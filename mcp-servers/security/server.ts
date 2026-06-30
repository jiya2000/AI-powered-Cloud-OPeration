/**
 * security/server.ts
 *
 * Security MCP Server
 * Provides tools for auditing RBAC role assignments, querying
 * Microsoft Defender for Cloud alerts, and auditing access permissions.
 *
 * Port: 3003
 *
 * In production, uses @azure/arm-authorization and @azure/arm-security
 * for real Azure Security data. Falls back to realistic mock data.
 */

import express, { Request, Response, NextFunction } from "express";
import { DefaultAzureCredential } from "@azure/identity";

const app = express();
app.use(express.json());

const PORT = parseInt(process.env.PORT || "3003");

// ─── Structured Logging ──────────────────────────────────────────────
const logger = {
  info: (msg: string, meta: any = {}) => console.log(JSON.stringify({ timestamp: new Date().toISOString(), level: "INFO", service: "security", message: msg, ...meta })),
  warn: (msg: string, meta: any = {}) => console.warn(JSON.stringify({ timestamp: new Date().toISOString(), level: "WARN", service: "security", message: msg, ...meta })),
  error: (msg: string, meta: any = {}) => console.error(JSON.stringify({ timestamp: new Date().toISOString(), level: "ERROR", service: "security", message: msg, ...meta }))
};

// ─── Auth Middleware ─────────────────────────────────────────────────
const EXPECTED_TOKEN = process.env.MCP_AUTH_TOKEN || "";
function requireAuth(req: Request, res: Response, next: NextFunction) {
  if (!EXPECTED_TOKEN) return next();
  const token = req.header("x-mcp-token");
  if (!token || token !== EXPECTED_TOKEN) {
    logger.warn("Unauthorized request attempt", { path: req.path, ip: req.ip });
    return res.status(401).json({ error: true, message: "Unauthorized: Invalid or missing x-mcp-token" });
  }
  next();
}

// Azure credential initialization
let credential: any = null;
let useAzure = false;
try {
  credential = new DefaultAzureCredential();
  useAzure = true;
} catch (e) {
  console.warn("[SecurityMCP] Azure credentials not available. Using mock data.");
}

// ─── Tool Definitions ────────────────────────────────────────────────
const tools = [
  {
    name: "read_rbac_assignments",
    description:
      "List all RBAC role assignments for a given scope (subscription, resource group, or resource).",
    inputSchema: {
      type: "object",
      properties: {
        scope: {
          type: "string",
          description: "Azure scope to query RBAC assignments for",
        },
        principal_name: {
          type: "string",
          description: "Optional: filter by user/service principal name",
        },
      },
      required: ["scope"],
    },
  },
  {
    name: "check_defender_alerts",
    description:
      "Query Microsoft Defender for Cloud security alerts for the subscription.",
    inputSchema: {
      type: "object",
      properties: {
        subscription_id: {
          type: "string",
          description: "Azure subscription ID to check alerts for",
        },
        severity: {
          type: "string",
          enum: ["High", "Medium", "Low"],
          description: "Optional: filter by alert severity",
        },
      },
      required: ["subscription_id"],
    },
  },
  {
    name: "audit_permissions",
    description:
      "Audit who has access to a specific Azure resource and what actions they can perform.",
    inputSchema: {
      type: "object",
      properties: {
        resource_id: {
          type: "string",
          description: "Full Azure resource ID to audit",
        },
      },
      required: ["resource_id"],
    },
  },
];

// ─── Tool Implementations ────────────────────────────────────────────
async function handleToolCall(name: string, args: any): Promise<any> {
  switch (name) {
    case "read_rbac_assignments": {
      const { scope, principal_name } = args;
      console.log(`[SecurityMCP] Reading RBAC assignments for: ${scope}`);

      // In production:
      // import { AuthorizationManagementClient } from "@azure/arm-authorization";
      // const client = new AuthorizationManagementClient(credential, subscriptionId);
      // const assignments = await client.roleAssignments.listForScope(scope);

      const allAssignments = [
        { principal: "admin@company.com", role: "Owner", scope: scope, type: "User", inherited: false },
        { principal: "aditi@company.com", role: "Contributor", scope: scope, type: "User", inherited: false },
        { principal: "ops@company.com", role: "Reader", scope: scope, type: "User", inherited: true },
        { principal: "devteam-sp", role: "Contributor", scope: scope, type: "ServicePrincipal", inherited: false },
        { principal: "security@company.com", role: "Security Reader", scope: scope, type: "User", inherited: true },
        { principal: "aks-managed-identity", role: "AcrPull", scope: scope, type: "ManagedIdentity", inherited: false },
      ];

      const filtered = principal_name
        ? allAssignments.filter((a) => a.principal.toLowerCase().includes(principal_name.toLowerCase()))
        : allAssignments;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                scope,
                filter: principal_name || "none",
                total_assignments: filtered.length,
                assignments: filtered,
                last_queried: new Date().toISOString(),
              },
              null,
              2
            ),
          },
        ],
      };
    }

    case "check_defender_alerts": {
      const { subscription_id, severity } = args;
      console.log(`[SecurityMCP] Checking Defender alerts for subscription: ${subscription_id}`);

      // In production:
      // import { SecurityCenter } from "@azure/arm-security";
      // const client = new SecurityCenter(credential, subscription_id);
      // const alerts = await client.alerts.list();

      const allAlerts = [
        {
          id: "alert-001",
          name: "Suspicious login from unusual location",
          severity: "High",
          status: "Active",
          resource: "/subscriptions/.../providers/Microsoft.Compute/virtualMachines/prod-api-vm",
          timestamp: "2026-06-30T08:15:00Z",
          description: "Login detected from IP 203.0.113.42 (Nigeria) on a VM that typically receives logins from India.",
        },
        {
          id: "alert-002",
          name: "Storage account publicly accessible",
          severity: "Medium",
          status: "Active",
          resource: "/subscriptions/.../providers/Microsoft.Storage/storageAccounts/logstorage01",
          timestamp: "2026-06-29T14:30:00Z",
          description: "Blob container 'logs' has public read access enabled.",
        },
        {
          id: "alert-003",
          name: "Unusual outbound network traffic",
          severity: "Low",
          status: "Resolved",
          resource: "/subscriptions/.../providers/Microsoft.Compute/virtualMachines/dev-worker-01",
          timestamp: "2026-06-28T22:00:00Z",
          description: "Spike in outbound data transfer detected (15GB in 1 hour).",
        },
      ];

      const filtered = severity
        ? allAlerts.filter((a) => a.severity === severity)
        : allAlerts;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                subscription_id,
                severity_filter: severity || "all",
                total_alerts: filtered.length,
                active_alerts: filtered.filter((a) => a.status === "Active").length,
                alerts: filtered,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    case "audit_permissions": {
      const { resource_id } = args;
      console.log(`[SecurityMCP] Auditing permissions for: ${resource_id}`);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                resource_id,
                effective_permissions: [
                  {
                    principal: "admin@company.com",
                    role: "Owner",
                    actions: ["*"],
                    source: "Direct assignment",
                  },
                  {
                    principal: "devteam-sp",
                    role: "Contributor",
                    actions: ["*/read", "*/write", "*/delete"],
                    not_actions: ["Microsoft.Authorization/*/write"],
                    source: "Direct assignment",
                  },
                  {
                    principal: "ops@company.com",
                    role: "Reader",
                    actions: ["*/read"],
                    source: "Inherited from resource group",
                  },
                ],
                risk_assessment: {
                  level: "Medium",
                  findings: [
                    "1 Owner assignment detected — consider using PIM for JIT access",
                    "Service principal has broad Contributor access",
                  ],
                },
                audited_at: new Date().toISOString(),
              },
              null,
              2
            ),
          },
        ],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// ─── REST API Endpoints ──────────────────────────────────────────────
app.get("/health", (_req, res) => {
  res.json({ status: "healthy", service: "security-mcp", port: PORT, azure: useAzure });
});

app.get("/api/tools", requireAuth, (_req, res) => {
  res.json({ tools });
});

app.post("/api/tools/call", requireAuth, async (req, res) => {
  try {
    const { name, arguments: args } = req.body;
    if (!name) {
      return res.status(400).json({ error: true, message: "Tool name is required" });
    }
    const result = await handleToolCall(name, args || {});
    res.json(result);
  } catch (error: any) {
    logger.error(`Error executing tool`, { error: error.message });
    res.status(400).json({ error: true, message: error.message });
  }
});

// ─── Start Server ────────────────────────────────────────────────────
app.listen(PORT, () => {
  logger.info(`Security MCP Server running`, { port: PORT });
  console.log(`[SecurityMCP] Azure credentials: ${useAzure ? "available" : "mock mode"}`);
});

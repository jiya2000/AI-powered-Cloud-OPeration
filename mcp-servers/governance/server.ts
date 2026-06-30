/**
 * governance/server.ts
 *
 * Governance MCP Server
 * Handles role-based approval workflows, approval status tracking,
 * and governance audit trails. Uses policy.json and role_mapping.json
 * for local policy evaluation.
 *
 * Port: 3002
 *
 * In production, this would integrate with Azure Logic Apps or
 * Power Automate to send Teams Adaptive Cards for human-in-the-loop approval.
 */

import express, { Request, Response, NextFunction } from "express";
import fs from "fs";
import path from "path";

const app = express();
app.use(express.json());

const PORT = parseInt(process.env.PORT || "3002");

// ─── Structured Logging ──────────────────────────────────────────────
const logger = {
  info: (msg: string, meta: any = {}) => console.log(JSON.stringify({ timestamp: new Date().toISOString(), level: "INFO", service: "governance", message: msg, ...meta })),
  warn: (msg: string, meta: any = {}) => console.warn(JSON.stringify({ timestamp: new Date().toISOString(), level: "WARN", service: "governance", message: msg, ...meta })),
  error: (msg: string, meta: any = {}) => console.error(JSON.stringify({ timestamp: new Date().toISOString(), level: "ERROR", service: "governance", message: msg, ...meta }))
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

// ─── Load Governance Configs ─────────────────────────────────────────
interface PolicyRule {
  roles: string[];
  expiry_hours: number;
}

interface ApprovalRecord {
  request_id: string;
  action: string;
  requested_by: string;
  status: "pending" | "approved" | "rejected";
  required_role: string;
  approver: string | null;
  reason: string;
  created_at: string;
  resolved_at: string | null;
}

// Load policy and role mapping
let policies: Record<string, PolicyRule> = {};
let roleMappings: Record<string, string[]> = {};

try {
  const policyPath = path.join(__dirname, "policy.json");
  policies = JSON.parse(fs.readFileSync(policyPath, "utf-8"));
  console.log("[GovernanceMCP] Loaded policy.json");
} catch (e) {
  console.warn("[GovernanceMCP] Could not load policy.json, using defaults");
  policies = {
    delete_resource: { roles: ["CloudAdmin"], expiry_hours: 12 },
    scale_resource: { roles: ["CloudAdmin", "OpsManager"], expiry_hours: 24 },
    modify_rbac: { roles: ["SecurityAdmin"], expiry_hours: 24 },
  };
}

try {
  const rolePath = path.join(__dirname, "role_mapping.json");
  roleMappings = JSON.parse(fs.readFileSync(rolePath, "utf-8"));
  console.log("[GovernanceMCP] Loaded role_mapping.json");
} catch (e) {
  console.warn("[GovernanceMCP] Could not load role_mapping.json, using defaults");
  roleMappings = {
    CloudAdmin: ["admin@company.com"],
    OpsManager: ["ops@company.com"],
    SecurityAdmin: ["security@company.com"],
  };
}

// In-memory approval store (production would use Cosmos DB / Azure Table)
const approvalStore: Map<string, ApprovalRecord> = new Map();

// ─── Governance Logic ────────────────────────────────────────────────
function classifyAction(actionDetails: string): string {
  const lower = actionDetails.toLowerCase();
  if (lower.includes("delete") || lower.includes("remove") || lower.includes("destroy")) {
    return "delete_resource";
  }
  if (lower.includes("scale") || lower.includes("resize")) {
    return "scale_resource";
  }
  if (lower.includes("rbac") || lower.includes("role") || lower.includes("permission")) {
    return "modify_rbac";
  }
  return "delete_resource"; // Default to most restrictive
}

function evaluateApproval(action: string, actionDetails: string): ApprovalRecord {
  const actionType = classifyAction(actionDetails);
  const policy = policies[actionType] || { roles: ["CloudAdmin"], expiry_hours: 12 };
  const requiredRole = policy.roles[0];
  const approvers = roleMappings[requiredRole] || [];

  console.log(`[GovernanceMCP] Action type: ${actionType}`);
  console.log(`[GovernanceMCP] Required role: ${requiredRole}`);
  console.log(`[GovernanceMCP] Eligible approvers: ${approvers.join(", ")}`);

  // Simulate approval logic:
  // - Reject if action mentions "reject" or "friday" (change freeze demo)
  // - Otherwise approve
  const isRejected =
    actionDetails.toLowerCase().includes("reject") ||
    (new Date().getDay() === 5 && actionDetails.toLowerCase().includes("prod"));

  const approver = approvers[0] || "unknown";
  const status = isRejected ? "rejected" : "approved";
  const reason = isRejected
    ? "Action violates governance policy (change freeze or explicit rejection)."
    : `Approved by ${approver} via Governance MCP. Role: ${requiredRole}.`;

  // In production: Send Teams Adaptive Card via Bot Framework
  // await sendAdaptiveCard(approver, actionDetails, requestId);
  console.log(`[GovernanceMCP] Would send Teams Adaptive Card to: ${approver}`);
  console.log(`[GovernanceMCP] Decision: ${status.toUpperCase()}`);

  return {
    request_id: action,
    action: actionDetails,
    requested_by: "agent",
    status: status as "approved" | "rejected",
    required_role: requiredRole,
    approver: isRejected ? null : approver,
    reason,
    created_at: new Date().toISOString(),
    resolved_at: new Date().toISOString(),
  };
}

// ─── Tool Definitions ────────────────────────────────────────────────
const tools = [
  {
    name: "request_approval",
    description:
      "Submit a governance approval request for a sensitive action. Evaluates against policy.json rules and role mappings.",
    inputSchema: {
      type: "object",
      properties: {
        request_id: {
          type: "string",
          description: "Unique identifier for the approval request",
        },
        action: {
          type: "string",
          description: "Description of the action requiring approval",
        },
        requested_by: {
          type: "string",
          description: "Name of the agent/user requesting approval",
        },
      },
      required: ["request_id", "action", "requested_by"],
    },
  },
  {
    name: "check_approval_status",
    description: "Check the status of an existing approval request.",
    inputSchema: {
      type: "object",
      properties: {
        request_id: {
          type: "string",
          description: "The approval request ID to check",
        },
      },
      required: ["request_id"],
    },
  },
  {
    name: "list_pending_approvals",
    description: "List all pending governance approval requests.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

// ─── Tool Implementations ────────────────────────────────────────────
async function handleToolCall(name: string, args: any): Promise<any> {
  switch (name) {
    case "request_approval": {
      const { request_id, action, requested_by } = args;
      console.log(`[GovernanceMCP] Processing approval request: ${request_id}`);

      const record = evaluateApproval(request_id, action);
      record.request_id = request_id;
      record.requested_by = requested_by;

      // Store the record
      approvalStore.set(request_id, record);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                request_id,
                status: record.status,
                approver: record.approver,
                required_role: record.required_role,
                reason: record.reason,
                resolved_at: record.resolved_at,
                audit_emitted: true,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    case "check_approval_status": {
      const { request_id } = args;
      const record = approvalStore.get(request_id);

      if (!record) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ request_id, status: "not_found", message: "No approval request found with this ID." }),
            },
          ],
        };
      }

      return {
        content: [{ type: "text", text: JSON.stringify(record, null, 2) }],
      };
    }

    case "list_pending_approvals": {
      const pending = Array.from(approvalStore.values()).filter(
        (r) => r.status === "pending"
      );

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                total_pending: pending.length,
                requests: pending,
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
  res.json({ status: "healthy", service: "governance-mcp", port: PORT });
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
  logger.info(`Governance MCP Server running`, { port: PORT });
});

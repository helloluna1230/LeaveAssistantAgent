export type Role = "employee" | "manager";

export interface DemoUser {
  employee_id: string;
  name: string;
  role: Role;
}

export interface ToolCallTrace {
  name: string;
  status: "running" | "ok" | "error" | "awaiting_confirmation";
  error_type?: string | null;
}

export interface Citation {
  source: string;
  section: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  toolCalls?: ToolCallTrace[];
  citations?: Citation[];
  traceId?: string | null;
  agentVersion?: string | null;
  streaming?: boolean;
}

export interface ResponseResult {
  id: string;
  conversation?: string | null;
  output_text: string;
  tool_calls?: ToolCallTrace[];
  citations?: Citation[];
  agent_version?: string | null;
  trace_id?: string | null;
  simulated?: boolean;
}

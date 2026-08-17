import type { ResponseResult } from "./types";

export interface SendOptions {
  input: string;
  previousResponseId?: string | null;
  token?: string;
  onDelta?: (text: string) => void;
}

// Single-user demo: the browser talks to the BFF (/responses), which injects the
// Foundry auth token. A demo identity token rides on x-user-token (kept so this
// upgrades cleanly to real per-user auth); the BFF forwards it to the agent.
export async function sendMessage(opts: SendOptions): Promise<ResponseResult> {
  const res = await fetch("/responses", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(opts.token ? { "x-user-token": opts.token } : {}),
    },
    body: JSON.stringify({
      input: opts.input,
      previous_response_id: opts.previousResponseId ?? null,
      store: true,
      stream: true,
    }),
  });
  if (!res.ok) throw new Error(`agent request failed: ${res.status}`);

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("text/event-stream") && res.body) {
    return await readSse(res.body, opts.onDelta);
  }
  const json = await res.json();
  return {
    id: json.id ?? "",
    conversation: json.conversation ?? null,
    output_text: extractOutputText(json),
    tool_calls: json.tool_calls ?? [],
    citations: json.citations ?? [],
    agent_version: json.agent_version ?? null,
    trace_id: json.trace_id ?? null,
  };
}

/** Extract assistant text from an OpenAI Responses payload. */
function extractOutputText(json: any): string {
  if (typeof json?.output_text === "string" && json.output_text) return json.output_text;
  const parts: string[] = [];
  for (const item of json?.output ?? []) {
    if (item?.type === "message") {
      for (const c of item?.content ?? []) {
        if (c?.type === "output_text" && typeof c.text === "string") parts.push(c.text);
      }
    }
  }
  return parts.join("");
}

export interface SessionPointer {
  previous_response_id?: string | null;
  conversation?: string | null;
}

async function readSse(
  body: ReadableStream<Uint8Array>,
  onDelta?: (text: string) => void
): Promise<ResponseResult> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const acc: ResponseResult = { id: "", output_text: "", tool_calls: [], citations: [] };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      const line = evt.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") continue;
      try {
        const obj = JSON.parse(payload);
        const type: string = obj.type ?? "";
        // Only accumulate the assistant's OUTPUT text deltas (ignore reasoning-
        // summary deltas, which also carry a `delta` field).
        if (type === "response.output_text.delta" && typeof obj.delta === "string") {
          acc.output_text += obj.delta;
          onDelta?.(obj.delta);
        }
        if (type === "response.output_text.done" && typeof obj.text === "string") {
          acc.output_text = obj.text;
        }
        if (type === "response.created" || type === "response.completed") {
          if (obj.response?.id) acc.id = obj.response.id;
          const finalText = extractOutputText(obj.response ?? {});
          if (finalText) acc.output_text = finalText;
        }
        if (typeof obj.output_text === "string" && obj.output_text) acc.output_text = obj.output_text;
        if (obj.id && !acc.id) acc.id = obj.id;
        if (obj.conversation) acc.conversation = obj.conversation;
        if (obj.tool_calls) acc.tool_calls = obj.tool_calls;
        if (obj.citations) acc.citations = obj.citations;
        if (obj.agent_version) acc.agent_version = obj.agent_version;
        if (obj.trace_id) acc.trace_id = obj.trace_id;
      } catch {
        // Non-JSON keepalive; ignore.
      }
    }
  }
  return acc;
}

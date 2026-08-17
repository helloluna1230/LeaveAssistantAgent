import { useEffect, useMemo, useRef, useState } from "react";
import { sendMessage } from "./api";
import { Chart, extractCharts } from "./Chart";
import type { ChatMessage } from "./types";

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

// Single fixed demo user. The demo identity token is forwarded to the BFF on
// x-user-token (kept so this upgrades cleanly to real per-user auth later).
const DEMO_USER = { name: "Alice", employee_id: "E1001", role: "员工" };
const IDENTITY_TOKEN = DEMO_USER.employee_id;

const EXAMPLE_QUESTIONS = [
  "我还有多少年假？",
  "我有没有即将过期的假期？",
  "帮我规划一下 12 月休 3 天年假",
  "公司的病假政策是什么？",
  "记住我偏好在 5 月和 10 月休假，且尽量最大化连续休假",
  "查看我保存的休假偏好",
  "分析我今年各类假期的使用情况并画一张曲线图",
];

// Session persistence: the conversation (transcript + server-side chain pointer)
// survives reloads. previousResponseId chains turns via the Foundry Responses store.
const STORAGE_KEY = "leave-assistant-session-v1";
type Session = { messages: ChatMessage[]; previousResponseId: string | null };

function loadSession(): Session {
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return {
      messages: (s.messages || []).map((m: ChatMessage) => ({ ...m, streaming: false })),
      previousResponseId: s.previousResponseId ?? null,
    };
  } catch {
    return { messages: [], previousResponseId: null };
  }
}

function saveSession(s: Session) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // Ignore storage quota / privacy-mode errors; history is best-effort.
  }
}

export default function App() {
  const initial = useMemo(loadSession, []);
  const [messages, setMessages] = useState<ChatMessage[]>(initial.messages);
  const [previousResponseId, setPreviousResponseId] = useState<string | null>(
    initial.previousResponseId
  );
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [agentVersion, setAgentVersion] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Persist the session on every change so a reload restores the conversation.
  useEffect(() => {
    saveSession({ messages, previousResponseId });
  }, [messages, previousResponseId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    setBusy(true);

    const assistantId = uid();
    setMessages((m) => [
      ...m,
      { id: uid(), role: "user", text: content },
      { id: assistantId, role: "assistant", text: "", streaming: true },
    ]);
    setInput("");

    try {
      const result = await sendMessage({
        input: content,
        previousResponseId,
        token: IDENTITY_TOKEN,
        onDelta: (delta) =>
          setMessages((m) =>
            m.map((msg) =>
              msg.id === assistantId ? { ...msg, text: msg.text + delta } : msg
            )
          ),
      });
      setPreviousResponseId(result.id || null);
      if (result.agent_version) setAgentVersion(result.agent_version);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                text: result.output_text || msg.text,
                toolCalls: result.tool_calls,
                citations: result.citations,
                agentVersion: result.agent_version,
                streaming: false,
              }
            : msg
        )
      );
    } catch (err) {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === assistantId
            ? { ...msg, text: `⚠️ 请求失败：${String(err)}`, streaming: false }
            : msg
        )
      );
    } finally {
      setBusy(false);
    }
  }

  function clearSession() {
    setMessages([]);
    setPreviousResponseId(null);
  }

  return (
    <div className="app">
      <div className="sim-banner">
        当前数据来自模拟 HR MCP 服务，仅用于功能演示。 · SIMULATED HR data — demo only.
      </div>

      <div className="layout">
        <aside className="sidebar">
          <h1>休假助手 Leave Assistant</h1>

          <div className="meta">
            <div>
              <b>演示用户</b>
              <span>
                {DEMO_USER.name} · {DEMO_USER.employee_id}（{DEMO_USER.role}）
              </span>
            </div>
            <div>
              <b>Identity token</b>
              <span className="mono">{IDENTITY_TOKEN}</span>
            </div>
            <div>
              <b>Agent Version</b>
              <span className="mono">{agentVersion ?? "—"}</span>
            </div>
          </div>

          <div className="actions">
            <button onClick={() => submit("查看我保存的休假偏好")}>查看偏好</button>
            <button onClick={() => submit("删除我保存的休假偏好")}>删除偏好</button>
            <button onClick={clearSession}>新会话 / 清除</button>
          </div>

          <div className="hint">
            单用户演示：请求以固定演示身份（{DEMO_USER.employee_id}）调用托管 Agent；
            会话本地保存，刷新不丢。
          </div>
        </aside>

        <main className="chat">
          <div className="messages">
            {messages.length === 0 && (
              <div className="empty">开始对话，或点击下方常用问题直接发送。</div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>
                <div className="bubble">
                  {(() => {
                    if (m.role !== "assistant") return m.text || (m.streaming ? "…" : "");
                    const { clean, charts } = extractCharts(m.text);
                    return (
                      <>
                        {clean || (m.streaming ? "…" : "")}
                        {charts.map((spec, i) => (
                          <Chart key={i} spec={spec} />
                        ))}
                      </>
                    );
                  })()}
                  {m.citations && m.citations.length > 0 && (
                    <div className="citations">
                      来源：
                      {m.citations.map((c, i) => (
                        <span key={i} className="chip">
                          {c.source} · {c.section}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                {m.toolCalls && m.toolCalls.length > 0 && (
                  <div className="toolcalls">
                    {m.toolCalls.map((t, i) => (
                      <span key={i} className={`toolchip ${t.status}`}>
                        {t.name} · {t.status}
                        {t.error_type ? ` (${t.error_type})` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Always-visible quick questions — persist even after a message is sent. */}
          <div className="quickbar">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                className="example"
                disabled={busy}
                onClick={() => submit(q)}
              >
                {q}
              </button>
            ))}
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              submit(input);
            }}
          >
            <input
              value={input}
              placeholder="输入你的问题…"
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button type="submit" disabled={busy || !input.trim()}>
              {busy ? "…" : "发送"}
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}

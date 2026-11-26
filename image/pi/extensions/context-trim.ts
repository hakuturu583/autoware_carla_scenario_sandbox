// pi checks for auto-compaction only after an agent run ends (agent_end). In
// `pi -p "<task>"` the whole task is ONE run, so with Inkling's 32k window a
// long task (skill text + framework sources) overflows mid-run; the overflow
// compaction then starts after the run and print mode exits before it ends.
//
// This hook runs before every LLM call and shortens old tool results to their
// head and tail. It changes only what is sent, not the session.
//
// Prefix-cache friendly: every rewrite of an early message makes the server
// re-read (prefill) the whole prompt. So the trimmed region only grows in
// large steps: when the estimate exceeds PI_TRIM_BUDGET (default 20000
// tokens), every tool result except the newest PI_TRIM_KEEP (default 2) is
// trimmed and that boundary is remembered. Until the budget is exceeded again
// the same messages are sent byte-for-byte, and the server's cache hits.
export default function (pi: any) {
  const budget = Number(process.env.PI_TRIM_BUDGET ?? "20000");
  const keep = Number(process.env.PI_TRIM_KEEP ?? "2");
  const HEAD = 600;
  const TAIL = 400;
  let boundary = 0; // number of tool results (counted from the start) that are trimmed

  const textOf = (m: any): string => {
    if (typeof m.content === "string") return m.content;
    if (!Array.isArray(m.content)) return "";
    return m.content.map((c: any) => (c.type === "text" ? c.text : c.type === "toolCall" ? JSON.stringify(c.arguments ?? {}) : "")).join("");
  };
  // chars/3 overestimates for code; Japanese text is roughly 1 token per char.
  const tokens = (t: string) => {
    const cjk = (t.match(/[　-鿿＀-￯]/g) ?? []).length;
    return Math.ceil((t.length - cjk) / 3) + cjk;
  };
  const trimmed = (t: string) =>
    t.length <= HEAD + TAIL + 200
      ? t
      : `${t.slice(0, HEAD)}\n[... ${t.length - HEAD - TAIL} chars of this old output trimmed to fit the context; re-run the command if you need them ...]\n${t.slice(-TAIL)}`;

  const apply = (msgs: any[], upto: number) => {
    let n = 0;
    for (const m of msgs) {
      if (m.role !== "toolResult") continue;
      if (n++ >= upto) break;
      m.content = [{ type: "text", text: trimmed(textOf(m)) }];
    }
  };
  const estimate = (msgs: any[]) => msgs.reduce((s, m) => s + tokens(textOf(m)), 3000); // + system prompt/tools

  pi.on("context", (event: any) => {
    const msgs = event.messages;
    const results = msgs.filter((m: any) => m.role === "toolResult").length;
    apply(msgs, boundary);
    if (estimate(msgs) > budget) {
      boundary = Math.max(boundary, results - keep);
      apply(msgs, boundary);
    }
    return { messages: msgs };
  });
}

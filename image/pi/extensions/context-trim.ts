// pi checks for auto-compaction only after an agent run ends (agent_end). In
// `pi -p "<task>"` the whole task is ONE run, so with Inkling's 32k window a
// long task (skill text + framework sources) overflows mid-run; the overflow
// compaction then starts after the run and print mode exits before it ends.
//
// This hook runs before every LLM call. When the estimated context exceeds
// PI_TRIM_BUDGET tokens (default 18000), it shortens old tool results (all but
// the newest PI_TRIM_KEEP, default 4) to their head and tail. It changes only
// what is sent, not the session. Trimming breaks the server's prefix cache, so
// it trims all old results at once to make the next trim rare.
export default function (pi: any) {
  const budget = Number(process.env.PI_TRIM_BUDGET ?? "18000");
  const keep = Number(process.env.PI_TRIM_KEEP ?? "4");
  const HEAD = 600;
  const TAIL = 400;

  const textOf = (m: any): string => {
    if (typeof m.content === "string") return m.content;
    if (!Array.isArray(m.content)) return "";
    return m.content.map((c: any) => (c.type === "text" ? c.text : c.type === "toolCall" ? JSON.stringify(c.arguments ?? {}) : "")).join("");
  };
  // chars/3 overestimates for code; Japanese text is roughly 1 token per char.
  const estimate = (msgs: any[]) =>
    msgs.reduce((n, m) => {
      const t = textOf(m);
      const cjk = (t.match(/[　-鿿＀-￯]/g) ?? []).length;
      return n + Math.ceil((t.length - cjk) / 3) + cjk;
    }, 0);

  pi.on("context", (event: any) => {
    const msgs = event.messages;
    if (estimate(msgs) + 3000 <= budget) return; // 3000 ~ system prompt + tools
    const results: number[] = [];
    msgs.forEach((m: any, i: number) => {
      if (m.role === "toolResult") results.push(i);
    });
    const old = results.slice(0, Math.max(0, results.length - keep));
    for (const i of old) {
      const m = msgs[i];
      const t = textOf(m);
      if (t.length <= HEAD + TAIL + 200) continue;
      const cut = t.length - HEAD - TAIL;
      m.content = [{
        type: "text",
        text: `${t.slice(0, HEAD)}\n[... ${cut} chars of this old output trimmed to fit the context; re-run the command if you need them ...]\n${t.slice(-TAIL)}`,
      }];
    }
    return { messages: msgs };
  });
}

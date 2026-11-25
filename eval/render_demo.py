"""Render a recorded pi run (record_demo.py's events.jsonl) as a terminal-style MP4.

  python3 eval/render_demo.py out_dir/events.jsonl out_dir/demo.mp4 --title "..." [--speed 1.0]

Nothing is invented: every character on screen comes from the recorded event
stream (the model's streamed thinking/text, the exact tool commands it ran and
their outputs), shown at the time it arrived (host-side timestamps), divided by
--speed. Long tool outputs/commands are truncated with a visible marker.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SIZE = 15
LINE_H = 20
PAD = 18
HEADER_H = 64
COLS = (W - 2 * PAD) // 9  # DejaVu Sans Mono 15px is 9px wide
ROWS = (H - HEADER_H - PAD) // LINE_H
COLORS = {
    "bg": (18, 20, 24), "header": (32, 36, 44), "title": (235, 238, 242), "sub": (150, 160, 175),
    "prompt": (120, 180, 255), "think": (125, 132, 145), "say": (235, 238, 242),
    "cmd": (110, 220, 140), "out": (175, 182, 192), "err": (255, 120, 110),
    "pass": (110, 220, 140), "fail": (255, 120, 110), "dim": (95, 100, 110),
}
MAX_CMD_LINES, MAX_OUT_LINES = 10, 8


class Transcript:
    def __init__(self) -> None:
        self.blocks: list[list] = []  # [kind, text]

    def add(self, kind: str, text: str) -> None:
        self.blocks.append([kind, text])

    def append(self, kind: str, delta: str) -> None:
        if self.blocks and self.blocks[-1][0] == kind:
            self.blocks[-1][1] += delta
        else:
            self.add(kind, delta)

    def lines(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for kind, text in self.blocks:
            text = text.strip("\n")
            if not text:
                continue
            raw = text.splitlines()
            if kind == "cmd" and len(raw) > MAX_CMD_LINES:
                raw = raw[:MAX_CMD_LINES] + [f"… ({len(raw) - MAX_CMD_LINES} more lines of this command)"]
            if kind in ("out", "err") and len(raw) > MAX_OUT_LINES:
                # head + tail: a validator's verdict is at the end
                raw = raw[:3] + [f"… ({len(raw) - MAX_OUT_LINES} output lines omitted)"] + raw[-(MAX_OUT_LINES - 3):]
            prefix = {"cmd": "$ ", "think": "· ", "prompt": "> "}.get(kind, "")
            for i, r in enumerate(raw):
                body = (prefix if i == 0 else " " * len(prefix)) + r
                for w in textwrap.wrap(body, COLS, replace_whitespace=False, drop_whitespace=False) or [""]:
                    k = kind
                    if kind == "validate":
                        k = "pass" if ("PASS" in r and "FAIL" not in r) or "[ok]" in r else ("fail" if "FAIL" in r else "out")
                    out.append((k, w))
            out.append(("dim", ""))
        return out


def render(lines, title, sub, clock, fonts, path) -> None:
    img = Image.new("RGB", (W, H), COLORS["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, HEADER_H], fill=COLORS["header"])
    d.text((PAD, 12), title, font=fonts["b"], fill=COLORS["title"])
    d.text((PAD, 36), sub, font=fonts["r"], fill=COLORS["sub"])
    d.text((W - PAD - 9 * 9, 12), clock, font=fonts["b"], fill=COLORS["title"])
    y = HEADER_H + 10
    for kind, text in lines[-ROWS:]:
        d.text((PAD, y), text, font=fonts["r"], fill=COLORS.get(kind, COLORS["say"]))
        y += LINE_H
    img.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("out")
    ap.add_argument("--title", default="pi + Inkling 2 Mini (Strata, local) in an OpenShell sandbox")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--fps", type=float, default=12.0)
    args = ap.parse_args()

    fonts = {"r": ImageFont.truetype(FONT, SIZE), "b": ImageFont.truetype(FONT_B, SIZE + 1)}
    tr = Transcript()
    snaps: list[tuple[float, list]] = []
    sub = ""
    tool_errors = 0
    for line in pathlib.Path(args.events).read_text().splitlines():
        rec = json.loads(line)
        t, ev = rec["t"] / args.speed, rec["ev"]
        typ = ev.get("type")
        if typ == "demo_prompt":
            sub = f"sandbox {ev['sandbox']} · no WAN · only egress: Strata on the host · validator: validate-scenario"
            tr.add("prompt", ev["text"])
        elif typ == "message_update":
            a = ev.get("assistantMessageEvent") or {}
            if a.get("type") == "thinking_delta":
                tr.append("think", a.get("delta", ""))
            elif a.get("type") == "text_delta":
                tr.append("say", a.get("delta", ""))
            else:
                continue
        elif typ == "tool_execution_start":
            args_ = ev.get("args") or {}
            cmd = args_.get("command") or json.dumps(args_)
            tr.add("cmd", cmd if ev.get("toolName") == "bash" else f"[{ev.get('toolName')}] {cmd}")
        elif typ == "tool_execution_end":
            res = ev.get("result") or {}
            txt = "".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
            tool_errors += bool(ev.get("isError"))
            tr.add("err" if ev.get("isError") else "out", txt or "(no output)")
        elif typ == "demo_validate":
            tr.add("say", "[host-side re-check after the agent finished]")
            tr.add("validate", ev["text"])
        else:
            continue
        snap = tr.lines()
        if snaps and t - snaps[-1][0] < 1.0 / args.fps:
            snaps[-1] = (snaps[-1][0], snap)
        else:
            snaps.append((t, snap))
    if not snaps:
        raise SystemExit("no events")
    snaps.append((snaps[-1][0] + 4.0, snaps[-1][1]))  # hold the final screen

    with tempfile.TemporaryDirectory() as tmp:
        concat = pathlib.Path(tmp, "list.txt")
        entries = []
        for i, (t, snap) in enumerate(snaps[:-1]):
            p = pathlib.Path(tmp, f"f{i:05d}.png")
            m, s = divmod(int(t * args.speed), 60)
            render(snap, args.title, sub, f"{m:02d}:{s:02d}", fonts, p)
            dur = max(snaps[i + 1][0] - t, 1.0 / args.fps)
            entries.append(f"file '{p}'\nduration {dur:.3f}")
        entries.append(f"file '{pathlib.Path(tmp, f'f{len(snaps) - 2:05d}.png')}'")
        concat.write_text("\n".join(entries) + "\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                        "-vf", f"fps={int(args.fps)},format=yuv420p", "-c:v", "libx264", "-crf", "23",
                        "-movflags", "+faststart", args.out], check=True)
    print(f"wrote {args.out} ({len(snaps)} screens, {snaps[-1][0]:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

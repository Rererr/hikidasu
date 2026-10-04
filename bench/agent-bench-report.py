#!/usr/bin/env python3
"""agent-bench/*.jsonl を集計。正解到達 = 正解ノートを Read した（none 問は回答に「該当なし」系の文言）。
出力: 指示×モデルの表（到達率・平均入力tok・平均費用・平均秒・平均ターン・検索回数）と、問ごとの到達マトリクス。"""
import glob, json, os, re, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.environ.get("GOLDEN", os.path.join(HERE, "golden.jsonl"))
gold = {g["id"]: g for g in (json.loads(l) for l in open(GOLDEN) if l.strip())}
NONE_RE = re.compile(r"該当なし|該当(する)?(ノート|もの)?(は|が)?(無|ない|ありません|見つかりません)|ノートは(無|ない|ありません)|見つかりませんでした")
def says_none(ans): return bool(NONE_RE.search(ans[:80]))  # 先頭 80 文字で判定（末尾の保険文「〜なら該当なし」を拾わない）
rows = []
BDIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "agent-bench")
for f in sorted(glob.glob(os.path.join(BDIR, "*.jsonl"))):
    name = os.path.basename(f)[:-6]; parts = name.split("-")
    v = parts[0]; qid = parts[-1]; m = "-".join(parts[1:-1])
    ev = [json.loads(l) for l in open(f) if l.strip()]
    res = next((e for e in ev if e.get("type") == "result"), None)
    if not res: rows.append(dict(v=v, m=m, qid=qid, err=True)); continue
    tools = [c for e in ev if e.get("type") == "assistant" for c in e["message"]["content"] if c.get("type") == "tool_use"]
    reads = {c["input"].get("file_path", "") for c in tools if c["name"] == "Read"}
    n_ruri = sum(1 for c in tools if c["name"] == "Bash" and "hikidasu" in c["input"].get("command", ""))
    n_grep = sum(1 for c in tools if c["name"] in ("Grep", "Glob"))
    g = gold[qid]; ans = res.get("result") or ""
    denied = sum(1 for e in ev if e.get("type") == "user" for c in e["message"]["content"] if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"))
    if g["relevant"]:
        hit = sum(1 for r in g["relevant"] if any(p.endswith("/" + r) for p in reads)) / len(g["relevant"])
    else:
        hit = 1.0 if says_none(ans) else 0.0
    false_none = bool(g["relevant"]) and says_none(ans)
    u = res["usage"]; tok_in = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    rows.append(dict(v=v, m=m, qid=qid, tag=g["tag"], hit=hit, tok_in=tok_in, tok_out=u.get("output_tokens", 0), cost=res.get("total_cost_usd", 0),
                     sec=res["duration_ms"] / 1000, turns=res["num_turns"], n_ruri=n_ruri, n_grep=n_grep, denied=denied, false_none=false_none, n_reads=len(reads), readme="README.md" in " ".join(reads), err=False))
ok0 = [r for r in rows if not r["err"]]
MODELS = [m for m in ["haiku", "sonnet", "opus", "claude-fable-5-1"] if any(r["m"] == m for r in ok0)] + sorted({r["m"] for r in ok0} - {"haiku", "sonnet", "opus", "claude-fable-5-1"})
VARS = [v for v in ["ruri", "grep", "hybrid"] if any(r["v"] == v for r in ok0)] + sorted({r["v"] for r in ok0} - {"ruri", "grep", "hybrid"})
short = {"claude-fable-5-1": "fable"}
ok = [r for r in rows if not r["err"]]
print(f"# エージェント込みベンチ  {len(ok)} 本（エラー {len(rows)-len(ok)}）  質問 {sorted({r['qid'] for r in ok})}\n")
print("## 指示 × モデル（平均）\n\n| 指示 | モデル | n | 到達率 | 入力tok | 出力tok | 費用$ | 秒 | ターン | ruri回 | grep回 | Read数 | README読 | 権限拒否 | 誤該当なし |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for v in VARS:
    for m in MODELS:
        rs = [r for r in ok if r["v"] == v and r["m"] == m]
        if not rs: continue
        n = len(rs); avg = lambda k: sum(r[k] for r in rs) / n
        print(f"| {v} | {short.get(m,m)} | {n} | {avg('hit'):.2f} | {avg('tok_in'):,.0f} | {avg('tok_out'):,.0f} | {avg('cost'):.3f} | {avg('sec'):.0f} | {avg('turns'):.1f} | {avg('n_ruri'):.1f} | {avg('n_grep'):.1f} | {avg('n_reads'):.1f} | {sum(r['readme'] for r in rs)}/{n} | {sum(r['denied'] for r in rs)} | {sum(r['false_none'] for r in rs)} |")
print("\n## 問ごとの到達（指示/モデル）\n")
qids = sorted({r["qid"] for r in ok}); cols = [(v, m) for v in VARS for m in MODELS if any(r["v"] == v and r["m"] == m for r in ok)]
print("| 問 | tag | " + " | ".join(f"{v}/{short.get(m,m)}" for v, m in cols) + " |\n|---|---|" + "---|" * len(cols))
idx = {(r["v"], r["m"], r["qid"]): r for r in ok}
for q in qids:
    cells = []
    for v, m in cols:
        r = idx.get((v, m, q)); cells.append("-" if not r else ("○" if r["hit"] == 1 else ("△" if r["hit"] > 0 else "×")))
    print(f"| {q} | {gold[q]['tag']} | " + " | ".join(cells) + " |")
print("\n判定: 到達 = 正解ノートを Read した割合（回答文の正誤は見ていない）。none 問は回答の先頭 80 文字に該当なし系の文言。Read数 = 読んだノート数（多く読むほど到達に有利）\n\n## タグ別到達率（指示ごと、モデル平均）\n\n| 指示 | " + " | ".join(["lex", "syn", "xlang", "multi", "none"]) + " |\n|---|---|---|---|---|---|")
for v in VARS:
    cells = []
    for t in ["lex", "syn", "xlang", "multi", "none"]:
        rs = [r for r in ok if r["v"] == v and r["tag"] == t]; cells.append(f"{sum(r['hit'] for r in rs)/len(rs):.2f}" if rs else "-")
    print(f"| {v} | " + " | ".join(cells) + " |")
errs = [r for r in rows if r["err"]]
if errs: print("\n## 結果なし: " + ", ".join(f"{r['v']}/{r['m']}/{r['qid']}" for r in errs))

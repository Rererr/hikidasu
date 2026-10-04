#!/usr/bin/env python
"""埋め込み検索の Recall@5。ノート全文を文書、golden の query（または keywords）をクエリとしてコサイン上位5件で判定。
使い方: .venv/bin/python measure-embed.py [--model cl-nagoya/ruri-v3-310m] [--mode sent|kw] [--kb ~/notes] [--golden golden.jsonl]
ruri は「検索クエリ: 」「検索文書: 」の接頭辞を要求する（モデルカード）。他モデルでは --no-prefix。"""
import argparse, json, os, sys, glob
from collections import defaultdict
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="cl-nagoya/ruri-v3-310m"); ap.add_argument("--mode", default="sent", choices=["sent", "kw"])
ap.add_argument("--kb", default=os.path.expanduser(os.environ.get("HIKIDASU_KB", "~/notes"))); ap.add_argument("--golden", default=os.path.join(os.path.dirname(__file__), "golden.jsonl"))
ap.add_argument("--no-prefix", action="store_true"); ap.add_argument("--field", default="body", choices=["body", "description"])
a = ap.parse_args()
from sentence_transformers import SentenceTransformer
import torch
K = 5
paths = sorted(p for d in ("patterns", "decisions", "runbooks") for p in glob.glob(os.path.join(a.kb, d, "*.md")))
rel_paths = [os.path.relpath(p, a.kb) for p in paths]
def text_of(p):
    s = open(p, encoding="utf-8").read()
    if a.field == "description":
        for line in s.splitlines():
            if line.startswith("description:"): return line[len("description:"):].strip()
    return s
docs = [text_of(p) for p in paths]
qp, dp = ("", "") if a.no_prefix else ("検索クエリ: ", "検索文書: ")
m = SentenceTransformer(a.model, device="mps" if torch.backends.mps.is_available() else "cpu")
m.max_seq_length = min(m.max_seq_length or 8192, 8192)
D = m.encode([dp + d for d in docs], normalize_embeddings=True, batch_size=8, show_progress_bar=False)
gold = [json.loads(l) for l in open(a.golden, encoding="utf-8") if l.strip()]
queries = [(g["query"] if a.mode == "sent" else " ".join(g["keywords"])) for g in gold]
Q = m.encode([qp + q for q in queries], normalize_embeddings=True, show_progress_bar=False)
S = Q @ D.T
print(f"# embed {a.model} mode={a.mode} field={a.field}  Recall@{K}")
print(f"- docs: {len(docs)} ({a.kb})  prefix: {'なし' if a.no_prefix else 'ruri 形式'}  max_seq_length: {m.max_seq_length}")
print(f"\n| id | tag | 正解数 | 上位{K}内の正解 | Recall | 上位{K}（cos） |\n|---|---|---|---|---|---|")
tag_sum, tag_n = defaultdict(float), defaultdict(int); tot, n, missed, none_rows = 0.0, 0, [], []
for g, s in zip(gold, S):
    top = sorted(range(len(docs)), key=lambda i: -s[i])[:K]
    shown = " ".join(f"{os.path.basename(rel_paths[i])}({s[i]:.2f})" for i in top)
    if not g["relevant"]:
        print(f"| {g['id']} | {g['tag']} | 0 | - | (対象外) 1位cos {s[top[0]]:.2f} | {shown} |"); continue
    found = sum(1 for r in g["relevant"] if r in {rel_paths[i] for i in top}); rc = found / len(g["relevant"])
    tag_sum[g["tag"]] += rc; tag_n[g["tag"]] += 1; tot += rc; n += 1
    if found < len(g["relevant"]): missed.append(f"- {g['id']}({g['tag']}): 正解 " + " ".join(os.path.basename(r) for r in g["relevant"]))
    print(f"| {g['id']} | {g['tag']} | {len(g['relevant'])} | {found} | {rc:.2f} | {shown} |")
print(f"\n## 全体 Recall@{K} (答えなし {len(gold)-n}問を除く {n} 問): {tot/n:.3f}\n\n## タグ別")
for t in ("lex", "syn", "xlang", "multi"):
    if tag_n[t]: print(f"- {t}: {tag_sum[t]/tag_n[t]:.3f} (n={tag_n[t]})")
print(f"\n## 取りこぼし（正解の一部でも上位{K}外）: {len(missed)} 問"); print("\n".join(missed))

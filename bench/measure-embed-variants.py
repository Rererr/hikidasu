#!/usr/bin/env python
"""残る問題の改善案を ruri で実測する。
変種: base(全文) / strip(定型句除去) / ens(raw+strip の max) / chunk(節ごとに埋め込み max) / chunk+ens
各変種で Recall@5/@8/@10、multi の内訳、該当なし信号（top1 cos・top1-top2 差・z スコア）を出す。
さらに top1 の関連リンク展開で multi の残りが拾えるかを数える。"""
import glob, json, os, re, sys
import numpy as np
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TOKENIZERS_PARALLELISM", "false"); os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1"); os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
HERE = os.path.dirname(os.path.abspath(__file__)); KB = os.path.expanduser(os.environ.get("HIKIDASU_KB", "~/notes"))
from sentence_transformers import SentenceTransformer
import torch
m = SentenceTransformer("cl-nagoya/ruri-v3-310m", device="mps" if torch.backends.mps.is_available() else "cpu"); m.max_seq_length = 8192
paths = sorted(os.path.relpath(p, KB) for d in ("patterns", "decisions", "runbooks") for p in glob.glob(os.path.join(KB, d, "*.md")))
texts = {p: open(os.path.join(KB, p), encoding="utf-8").read() for p in paths}
gold = [json.loads(l) for l in open(os.path.join(HERE, "golden.jsonl")) if l.strip()]
enc = lambda xs, pre: m.encode([pre + x for x in xs], normalize_embeddings=True, batch_size=8, show_progress_bar=False)
# 文書: 全文 / 節
D_full = enc([texts[p] for p in paths], "検索文書: ")
def sections(t):
    fm = t.split("---", 2); body = fm[2] if len(fm) > 2 else t
    desc = next((l[len("description:"):].strip() for l in t.splitlines() if l.startswith("description:")), "")
    parts = [s.strip() for s in re.split(r"\n(?=#{1,3} )", body) if len(s.strip()) > 40]
    return [desc] + parts if desc else parts
chunks, owner = [], []
for i, p in enumerate(paths):
    for s in sections(texts[p]): chunks.append(s); owner.append(i)
D_chunk = enc(chunks, "検索文書: "); owner = np.array(owner)
print(f"docs={len(paths)} chunks={len(chunks)}")
# 質問: raw / strip
STRIP = re.compile(r"[。．]?\s*(何を疑う|どこを疑う|どこがまずい|なぜ|どうする|どう決めるべき|対処は|原因の候補は|注意点をまとめて|指針は|ノートの立場は|CSS の何を見る|書き方は|取り方は|どっち向き|どう確認する|価値はある|設定は|手順|は)?[？?]*\s*$")
strip = lambda q: STRIP.sub("", q).strip("。 ") or q
Q_raw = enc([g["query"] for g in gold], "検索クエリ: "); Q_strip = enc([strip(g["query"]) for g in gold], "検索クエリ: ")
def scores(variant):
    out = []
    for i, g in enumerate(gold):
        qs = {"base": [Q_raw[i]], "strip": [Q_strip[i]], "ens": [Q_raw[i], Q_strip[i]], "chunk": [Q_raw[i]], "chunk+ens": [Q_raw[i], Q_strip[i]]}[variant]
        if variant.startswith("chunk"):
            s = np.full(len(paths), -1.0)
            for q in qs:
                cs = D_chunk @ q
                for ci, v in enumerate(cs): s[owner[ci]] = max(s[owner[ci]], v)
        else:
            s = np.max(np.stack([D_full @ q for q in qs]), axis=0)
        out.append(s)
    return out
links = {p: set(re.findall(r"\(([a-z0-9\-]+\.md)\)", texts[p])) | set(re.findall(r"\[\[([a-z0-9\-]+)\]\]", texts[p])) for p in paths}
base = {os.path.basename(p): p for p in paths}
def expand(top_path):
    return {base.get(l if l.endswith(".md") else l + ".md") for l in links[top_path]} - {None}
print("\n| 変種 | R@5 | R@8 | R@10 | lex | syn | xlang | multi@5 | multi@10 | Q11 順位 | Q17 上位5の正解数 | multi: top1 リンク展開で拾える残り |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
for variant in ["base", "strip", "ens", "chunk", "chunk+ens"]:
    S = scores(variant); r = {5: [], 8: [], 10: []}; tag = {}; q11 = q17 = ""; link_gain = []
    for g, s in zip(gold, S):
        if not g["relevant"]: continue
        order = [paths[i] for i in np.argsort(-s)]
        for k in r: r[k].append(sum(1 for x in g["relevant"] if x in order[:k]) / len(g["relevant"]))
        tag.setdefault(g["tag"], {5: [], 10: []});
        for k in (5, 10): tag[g["tag"]][k].append(sum(1 for x in g["relevant"] if x in order[:k]) / len(g["relevant"]))
        if g["id"] == "Q11": q11 = order.index(g["relevant"][0]) + 1
        if g["id"] == "Q17": q17 = sum(1 for x in g["relevant"] if x in order[:5])
        if g["tag"] == "multi":
            missing = [x for x in g["relevant"] if x not in order[:5]]
            if missing: link_gain.append(f"{g['id']}:{sum(1 for x in missing if x in expand(order[0]))}/{len(missing)}")
    avg = lambda xs: f"{sum(xs)/len(xs):.3f}"
    print(f"| {variant} | {avg(r[5])} | {avg(r[8])} | {avg(r[10])} | {avg(tag['lex'][5])} | {avg(tag['syn'][5])} | {avg(tag['xlang'][5])} | {avg(tag['multi'][5])} | {avg(tag['multi'][10])} | {q11} | {q17}/3 | {' '.join(link_gain) or '-'} |")
# 該当なし信号（base）
print("\n## 該当なし信号（base）: 問 | tag | top1 | top1-top2 | top1-top5 | z(top1) | 正解の順位\n|---|---|---|---|---|---|---|")
for g, s in zip(gold, scores("base")):
    o = np.argsort(-s); z = (s[o[0]] - s.mean()) / s.std()
    rank = "-" if not g["relevant"] else ",".join(str([paths[i] for i in o].index(x) + 1) for x in g["relevant"])
    print(f"| {g['id']} | {g['tag']} | {s[o[0]]:.3f} | {s[o[0]]-s[o[1]]:.3f} | {s[o[0]]-s[o[4]]:.3f} | {z:.2f} | {rank} |")

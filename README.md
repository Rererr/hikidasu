# hikidasu

Semantic search over a directory of markdown notes, in Japanese, with a resident embedding server.
Built to answer one question with measurements instead of opinions: *when does grep miss, and is adding embeddings worth it for a personal knowledge base read by a coding agent?*

- `hikidasu "質問文"` returns the top notes (path, cosine, frontmatter description) in ~50 ms once the server is warm
- `hikidasu-serve.py` keeps [cl-nagoya/ruri-v3-310m](https://huggingface.co/cl-nagoya/ruri-v3-310m) loaded behind a Unix socket (mode 0600), re-embeds only notes whose sha256 changed, and exits after an idle hour
- `bench/` holds the measurement scripts used in the write-up: grep baseline, qmd (BM25 / vector / hybrid), direct embedding Recall@5, and an agent-in-the-loop benchmark driven by `claude -p`

## Install

```sh
uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r requirements.txt
export HIKIDASU_KB=~/notes            # directory with patterns/ decisions/ runbooks/ (override with HIKIDASU_DIRS=a,b,c)
./hikidasu "リトライの上限回数はどう決めるべき？"
```

The first call downloads the model (~1.2 GB in safetensors) and starts the server; later calls take tens of milliseconds. `./hikidasu --status` / `--stop`. Set `HIKIDASU_OFFLINE=1` to forbid network access once the model is cached.

The server reads `HIKIDASU_KB` at start and refuses clients that ask for a different directory; stop it before switching.

## What the tool does not do

- It never says "no match". Cosine scores of unanswerable questions (0.82–0.86 on our corpus) overlap with those of correct paraphrase hits, so the caller has to read the returned descriptions and decide. In the agent benchmark that judgment was made correctly by the agent in every unanswerable case.
- It returns 8 results by default because, on our corpus, questions whose answer spans three notes needed rank 6–8 once the question was rephrased.
- Queries ending in a short question clause after a full stop (「…出続ける。なぜ？」) are also embedded without that clause; the per-document max of the two is used. The rule only fires after 「。」.

## Measurements (104 Japanese notes, 2026-10-04)

Two question sets of 20 (lex 5 / synonym 6 / JA↔EN 3 / multi-note 3 / no-answer 3). Set B was written by a separate agent that had not seen set A or the tool. Recall@5 excludes the no-answer questions.

| Searcher (input) | Set A | Set B (held-out) |
|---|---|---|
| grep, per-term OR, ranked by hit lines (keywords) | 0.666 | 0.471 |
| qmd `search`, BM25 (keywords) | 0.402 | 0.382 |
| qmd `search`, BM25 (full sentence) | 0.000 | 0.000 |
| ruri-v3-310m, plain (sentence) | 0.941 | 1.000 |
| hikidasu as shipped (sentence) | 1.000 | 1.000 |

Agent-in-the-loop (Claude Code headless, 20 held-out questions, sequential): with sonnet all three instructions (grep / hikidasu / hybrid) reached the correct note in 100% of cases; input tokens were 44.8k / 22.6k / 26.4k and cost $0.077 / $0.026 / $0.028 per question, wall clock 9–10 s each. The agent expands synonyms on its own and reads the human-written index, which is why grep instructions do not lose; the embedding route mainly halves cost.

qmd's BM25 lost to grep on Japanese because it indexes CJK runs as per-character exact phrases and ANDs every term; `third_party/qmd-patch/` is an experimental word-segmentation patch that helps keyword queries a little and sentence queries not at all.

## License

MIT for the code in this repository (see LICENSE, Copyright (c) 2026 Rererr). Third-party models and the qmd patch are covered in NOTICE.md; the patch keeps upstream qmd's MIT notice.

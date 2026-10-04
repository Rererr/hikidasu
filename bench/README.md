# bench

Measurement scripts. All read-only against the note directory. Golden files are `{"id","query","relevant":[paths],"tag","keywords":[...]}` per line; see `../golden.example.jsonl`.

- `measure-grep.sh [KB]` grep baseline (per-term `grep -ric`, summed per file, ranked by hit lines; ties by path)
- `measure-qmd.sh search-kw|search-sent|vsearch|query [collection]` qmd Recall@5 (needs qmd, jq, coreutils `timeout`)
- `measure-embed.py --mode sent|kw [--model ...] [--field body|description]` direct embedding Recall@5 (needs the venv)
- `measure-hikidasu-cli.sh` Recall@5/@8 through the shipped `hikidasu`
- `measure-embed-variants.py` query-stripping / ensemble / chunking variants and no-answer score statistics
- `agent-bench.sh [parallelism]` runs `claude -p` with grep / ruri / hybrid instructions over a golden file (`GOLDEN=`, `MODELS=`, `VARIANTS=`, `BENCH_DIR=`), `agent-bench-report.py [dir]` aggregates. Reach = the correct note was Read; no-answer = the reply opens with a no-match phrase. Reply correctness is not scored
- `translate.sh` translates notes to English with ollama (`MODEL=qwen3:8b`) into `knowledge-en/` as a regenerable search-index projection, not for reading

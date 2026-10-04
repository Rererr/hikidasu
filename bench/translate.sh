#!/usr/bin/env bash
# knowledge の日本語ノートを ollama(qwen3:8b, think off, temperature 0) で英訳し、knowledge-en/ に同じパスで保存する。
# 検索索引用の派生物。読む対象ではない。原本ハッシュを .src-hash に残し、変更があれば再生成する。
# 使い方: ./translate.sh [KNOWLEDGE_DIR]   順序: golden の正解ノート → 残り
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; KB="${1:-$HOME/notes}"; OUT="$HERE/knowledge-en"
MODEL="${MODEL:-qwen3:8b}"; LOG="$HERE/translate.log"
cd "$KB"
first=$(jq -r '.relevant[]' "$HERE/golden.jsonl" | sort -u)
rest=$(find patterns decisions runbooks -name '*.md' | sort | grep -vxF -f <(printf '%s\n' "$first"))
PROMPT='Translate the following Japanese Markdown note into English for use as a full-text search index.
Rules:
- Keep the YAML frontmatter. Keep the "name" and "tags" values unchanged; translate "description".
- Translate all prose. Use standard, widely used technical English terms. Be consistent.
- Keep code blocks, commands, file paths, identifiers, URLs, and Markdown structure unchanged.
- Do not add commentary, notes, or explanations. Output only the translated document, no code fence around it.

'
for f in $first $rest; do
  dst="$OUT/$f"; mkdir -p "$(dirname "$dst")"
  h=$(shasum -a 256 "$f" | cut -c1-16)
  if [ -f "$dst" ] && [ "$(cat "$dst.src-hash" 2>/dev/null)" = "$h" ]; then continue; fi
  t0=$(date +%s)
  body=$(jq -Rs --arg p "$PROMPT" --arg m "$MODEL" '{model:$m, prompt:($p + .), stream:false, think:false, options:{temperature:0, num_ctx:16384, num_predict:6000}}' "$f")
  resp=$(curl -s --max-time 900 http://localhost:11434/api/generate -d "$body")
  out=$(jq -r '.response // empty' <<<"$resp")
  if [ -z "$out" ]; then echo "$(date +%T) FAIL $f: $(jq -c '{error}' <<<"$resp" 2>/dev/null)" | tee -a "$LOG"; continue; fi
  # 先頭/末尾の ``` フェンスを剥がす
  printf '%s\n' "$out" | sed -e '1{/^```/d;}' -e '${/^```$/d;}' > "$dst"; echo "$h" > "$dst.src-hash"
  echo "$(date +%T) ok $f $(( $(date +%s) - t0 ))s in=$(wc -c <"$f") out=$(wc -c <"$dst") eval_tok=$(jq -r .eval_count <<<"$resp")" | tee -a "$LOG"
done
find "$OUT" -name "*.md" | while read -r e; do src="${e#$OUT/}"; [ -f "$KB/$src" ] || { rm -f "$e" "$e.src-hash"; echo "$(date +%T) 原本なしで削除 $src" | tee -a "$LOG"; }; done
echo "$(date +%T) DONE" | tee -a "$LOG"

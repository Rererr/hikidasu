#!/usr/bin/env bash
# 検索指示（ruri / grep / hybrid）× モデル × 質問 を claude -p で回し、1 本 1 jsonl を agent-bench/ に残す。
# 使い方: ./agent-bench.sh [並列数=3]   質問は QIDS、モデルは MODELS、指示は VARIANTS の環境変数で上書き可
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; P="${1:-3}"; BDIR="${BENCH_DIR:-$HERE/agent-bench}"; mkdir -p "$BDIR"; export BDIR
KB="${KB:-$HOME/notes}"; RS="${HIKIDASU_BIN:-hikidasu}"  # PATH 上の hikidasu（uv tool install 等）。別の実体は HIKIDASU_BIN で
GOLDEN="${GOLDEN:-$HERE/golden.jsonl}"
QIDS="${QIDS:-$(jq -r .id "$GOLDEN" | paste -sd" " -)}"  # 既定は golden 全問
MODELS="${MODELS:-haiku sonnet opus claude-fable-5-1}"
VARIANTS="${VARIANTS:-ruri grep hybrid}"
export HERE KB RS GOLDEN
one() { # $1=variant $2=model $3=qid
  local V="$1" M="$2" QID="$3"; local Q; Q=$(jq -r --arg id "$QID" 'select(.id==$id) | .query' "$GOLDEN")
  local OUT="$BDIR/$V-$M-$QID.jsonl"; [ -s "$OUT" ] && jq -e 'select(.type=="result")' "$OUT" >/dev/null 2>&1 && return 0
  local COMMON="あなたは Ren の開発アシスタント。Bash を使うときはコマンドを絶対パスでそのまま 1 つだけ実行し、cd や && を付けない。横断ナレッジは $KB にある（patterns/ decisions/ runbooks/、README.md が索引）。質問に答えるときは、まずナレッジに該当ノートがあるか探し、あれば Read で本文を開いて要点を答える。無ければ「knowledge に該当なし」と明言し、一般論は 2 行以内。回答は日本語で簡潔に。"
  local SYS TOOLS
  case "$V" in
    ruri)   SYS="$COMMON ナレッジの検索は Bash で \`$RS \"質問文\"\` を実行する（日本語の自然文でよい）。cos の絶対値では該当なしを判定できないので、返った description を読んで該当するかを判断する。grep は使わない。"; TOOLS="Bash($RS:*),Bash(cd $HERE && ./hikidasu:*),Read" ;;
    grep)   SYS="$COMMON ナレッジの検索は Grep / Glob / Read で行う（README.md の索引と本文の全文検索）。"; TOOLS="Read,Grep,Glob" ;;
    hybrid) SYS="$COMMON ナレッジの検索はまず Bash で \`$RS \"質問文\"\` を実行する（日本語の自然文でよい）。返った description に該当が無ければ、症状や対象を表す語だけに言い換えて 1 回だけ再実行し、それでも無ければ Grep で日英の類語を OR で全文検索する。cos の絶対値では該当なしを判定できない。"; TOOLS="Bash($RS:*),Bash(cd $HERE && ./hikidasu:*),Read,Grep,Glob" ;;
  esac
  local t0=$(date +%s.%N)
  ( cd "$BDIR" && env $(env | grep -o '^CLAUDE[A-Z_]*' | sed 's/^/-u /' | tr '\n' ' ') \
    claude -p --model "$M" --setting-sources "" --strict-mcp-config --max-turns 12 \
    --add-dir "$KB" --append-system-prompt "$SYS" --allowedTools "$TOOLS" --tools "Bash,Read,Grep,Glob" \
    --output-format stream-json --verbose <<<"$Q" > "$OUT" 2>"$OUT.err" ) || true
  echo "$(date +%T) $V $M $QID wall=$(printf '%.0f' "$(echo "$(date +%s.%N) - $t0" | bc)")s $(jq -r 'select(.type=="result") | "turns=\(.num_turns) cost=\(.total_cost_usd)"' "$OUT" 2>/dev/null || echo "NO RESULT: $(head -c 120 "$OUT.err")")"
}
export -f one
for V in $VARIANTS; do for M in $MODELS; do for Q in $QIDS; do echo "$V $M $Q"; done; done; done \
  | xargs -P "$P" -L 1 bash -c 'one "$0" "$1" "$2"' | tee -a "$BDIR/run.log"
echo "$(date +%T) BENCH DONE" | tee -a "$BDIR/run.log"

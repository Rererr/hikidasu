#!/usr/bin/env bash
# 第2段: vsearch / query を 日本語コーパス(knowledge) と 英訳コーパス(knowledge-en) で sent/kw 両モードで計測
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
jq -c '.query = (.keywords | join(" "))' golden.jsonl > golden-kwq.jsonl
jq -c '.query = (.keywords | join(" "))' golden-en.jsonl > golden-en-kwq.jsonl
run() { # $1=prefix $2=mode $3=collection $4=golden $5=label
  local t0=$(date +%s); GOLDEN="$HERE/$4" ./measure-qmd.sh "$2" "$3" > "result-$1-qmd-$2-$5.md"; echo "$(date +%T) $1 $2 $5 $(( $(date +%s)-t0 ))s: $(grep '^## 全体' "result-$1-qmd-$2-$5.md")"; }
for mode in vsearch query; do run jp $mode knowledge golden.jsonl sent; run jp $mode knowledge golden-kwq.jsonl kw; done
export XDG_CACHE_HOME=$HERE/qmd-cache-en QMD_CONFIG_DIR=$HERE/qmd-config-en
for mode in vsearch query; do run en $mode knowledge-en golden-en.jsonl sent; run en $mode knowledge-en golden-en-kwq.jsonl kw; done
echo "$(date +%T) STAGE2 DONE"

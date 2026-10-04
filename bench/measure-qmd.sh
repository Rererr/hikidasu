#!/usr/bin/env bash
# qmd 計測: golden.jsonl の各問を qmd に投げ、ノート（patterns/decisions/runbooks）に絞った上位5件で Recall@5 を出す。
# 使い方: ./measure-qmd.sh [MODE] [COLLECTION]
#   MODE: search-kw   = `qmd search` (BM25) に keywords を空白区切りで渡す（FTS5 は全語 AND）  ※既定
#         search-sent = `qmd search` に質問文 (query) をそのまま渡す
#         vsearch     = `qmd vsearch` に質問文（要 qmd embed）
#         query       = `qmd query`   に質問文（要 embed・リランク・クエリ拡張モデル）
#   COLLECTION 既定: knowledge
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
GOLDEN="${GOLDEN:-$HERE/golden.jsonl}"
MODE="${1:-search-kw}"; COL="${2:-knowledge}"; K=5
command -v qmd >/dev/null || { echo "qmd が無い" >&2; exit 1; }
command -v jq  >/dev/null || { echo "jq が無い" >&2; exit 1; }
command -v timeout >/dev/null || { echo "timeout が無い（macOS は brew install coreutils）" >&2; exit 1; }

case "$MODE" in
  search-kw|search-sent) CMD=search ;;
  vsearch) CMD=vsearch ;;
  query) CMD=query ;;
  *) echo "不明な MODE: $MODE" >&2; exit 1 ;;
esac

echo "# qmd $MODE  Recall@$K"
echo "- qmd: $(qmd --version 2>&1 | head -1)  collection: $COL  $(qmd status 2>/dev/null | grep -E 'Total|Vectors' | tr -s ' ' | paste -sd';' -)"
echo "- 入力: $([ "$MODE" = search-kw ] && echo 'keywords を空白区切り' || echo '質問文そのまま')。上位10件を取り README/AGENTS を除いた先頭${K}件で判定"
echo
printf '| id | tag | 正解数 | 上位%d内の正解 | Recall | 上位%d（スコア） |\n' $K $K
echo '|---|---|---|---|---|---|'

sum_lex=0; n_lex=0; sum_syn=0; n_syn=0; sum_xlang=0; n_xlang=0; sum_multi=0; n_multi=0; n_none=0
total_sum=0; total_n=0; missed=""; zero=0; errs=0; total_q=0

while IFS= read -r line; do
  id=$(jq -r .id <<<"$line"); tag=$(jq -r .tag <<<"$line")
  rel=(); while IFS= read -r x; do [ -n "$x" ] && rel+=("$x"); done < <(jq -r '.relevant[]' <<<"$line")
  if [ "$MODE" = search-kw ]; then q=$(jq -r '.keywords | join(" ")' <<<"$line"); else q=$(jq -r .query <<<"$line"); fi

  total_q=$((total_q+1))
  if ! raw=$(timeout 120 qmd "$CMD" "$q" -c "$COL" --json -n 10 2>/tmp/measure-qmd.err); then errs=$((errs+1)); echo "  qmd エラー ($id): $(head -c 160 /tmp/measure-qmd.err)" >&2; raw='[]'; fi
  top=$(jq -r '.[] | "\(.file)\t\(.score)"' <<<"$raw" | sed "s#^qmd://$COL/##" \
        | grep -E '^(patterns|decisions|runbooks)/' | head -n $K || true)
  paths=$(cut -f1 <<<"$top")
  shown=$(awk -F'\t' '{sub(".*/","",$1); printf "%s(%s) ", $1, $2}' <<<"$top")
  nhit=$(grep -c . <<<"$paths" || true)
  [ "$nhit" -eq 0 ] && zero=$((zero+1))

  if [ ${#rel[@]} -eq 0 ]; then
    n_none=$((n_none+1))
    printf '| %s | %s | 0 | - | (対象外) ヒット%d件 | %s |\n' "$id" "$tag" "$nhit" "$shown"
    continue
  fi
  found=0
  for r in "${rel[@]}"; do grep -qxF -- "$r" <<<"$paths" && found=$((found+1)); done
  recall=$(awk -v f=$found -v n=${#rel[@]} 'BEGIN{printf "%.6f", f/n}')
  eval "sum_$tag=\$(awk -v a=\$sum_$tag -v b=$recall 'BEGIN{print a+b}'); n_$tag=\$((n_$tag+1))"
  total_sum=$(awk -v a=$total_sum -v b=$recall 'BEGIN{print a+b}'); total_n=$((total_n+1))
  [ "$found" -lt "${#rel[@]}" ] && missed="$missed- $id($tag): 正解 $(printf '%s ' "${rel[@]}" | sed 's#[a-z]*/##g')"$'\n'
  printf '| %s | %s | %d | %d | %.2f | %s |\n' "$id" "$tag" "${#rel[@]}" "$found" "$recall" "$shown"
done < "$GOLDEN"

echo
echo "## 全体 Recall@$K (答えなし ${n_none}問を除く $total_n 問): $(awk -v a=$total_sum -v n=$total_n 'BEGIN{printf "%.3f", a/n}')"
echo "- 0 件で返った問: $zero / $total_q  qmd エラー: $errs"
echo
echo "## タグ別"
for t in lex syn xlang multi; do
  eval "a=\$sum_$t; n=\$n_$t"
  [ "$n" -gt 0 ] && echo "- $t: $(awk -v a=$a -v n=$n 'BEGIN{printf "%.3f", a/n}') (n=$n)"
done
echo
echo "## 取りこぼし（正解の一部でも上位${K}外）: $(printf '%s' "$missed" | grep -c . || true) 問"
printf '%s' "$missed"

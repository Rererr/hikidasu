#!/usr/bin/env bash
# grep ベースライン: golden.jsonl の keywords で grep -ril し、ヒット行数降順の上位5件に正解が含まれるかで Recall@5 を出す。
# 使い方: ./measure-grep.sh [KNOWLEDGE_DIR]   (既定: ~/notes)
#   環境変数 GREP で grep 実体を差し替え可（既定: PATH 上の grep。版数は先頭に印字する）
set -euo pipefail
export LC_ALL=en_US.UTF-8 2>/dev/null; locale -a 2>/dev/null | grep -qi "en_US.UTF-8" || export LC_ALL=C.UTF-8

HERE="$(cd "$(dirname "$0")" && pwd)"
GOLDEN="${GOLDEN:-$HERE/golden.jsonl}"
KB="${1:-$HOME/notes}"
GREP="${GREP:-grep}"
K=5

command -v jq >/dev/null || { echo "jq が必要です" >&2; exit 1; }
[ -d "$KB" ] || { echo "ナレッジディレクトリが無い: $KB" >&2; exit 1; }
cd "$KB"

echo "# grep baseline  Recall@$K"
echo "- knowledge: $KB @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')  ノート数: $(find patterns decisions runbooks -name '*.md' | wc -l | tr -d ' ')"
echo "- grep: $($GREP --version | head -1)"
echo "- 順位: 各キーワードを個別に grep -ric（大小文字無視・行数）し、ファイルごとに合算。合算降順、同数はパス昇順"
echo

printf '| id | tag | 正解数 | 上位%d内の正解 | Recall | 上位%d |\n' $K $K
echo '|---|---|---|---|---|---|'

# bash 3.2 (macOS 既定) 互換のため連想配列は使わない
sum_lex=0; n_lex=0; sum_syn=0; n_syn=0; sum_xlang=0; n_xlang=0; sum_multi=0; n_multi=0; n_none=0
total_sum=0; total_n=0; missed=""

while IFS= read -r line; do
  id=$(jq -r .id <<<"$line"); tag=$(jq -r .tag <<<"$line")
  rel=(); while IFS= read -r x; do [ -n "$x" ] && rel+=("$x"); done < <(jq -r '.relevant[]' <<<"$line")
  kws=(); while IFS= read -r x; do [ -n "$x" ] && kws+=("$x"); done < <(jq -r '.keywords[]' <<<"$line")

  # ファイルごとのヒット行数合算 → 上位K
  top=$(for kw in "${kws[@]}"; do
          $GREP -ric -- "$kw" patterns decisions runbooks 2>/dev/null | awk -F: '$NF>0' || true
        done | awk -F: '{c[$1]+=$NF} END{for(f in c) print c[f]"\t"f}' \
        | sort -t$'\t' -k1,1nr -k2,2 | head -n $K | cut -f2)
  nhit=$(printf '%s\n' "$top" | grep -c . || true)

  if [ ${#rel[@]} -eq 0 ]; then
    n_none=$((n_none+1))
    # 答えなし: Recall の分母に入れない。返った件数（ノイズ）だけ示す
    printf '| %s | %s | 0 | - | (対象外) ヒット%d件 | %s |\n' "$id" "$tag" "$nhit" "$(printf '%s\n' "$top" | sed 's#.*/##' | paste -sd' ' -)"
    continue
  fi

  found=0
  for r in "${rel[@]}"; do grep -qxF -- "$r" <<<"$top" && found=$((found+1)); done
  recall=$(awk -v f=$found -v n=${#rel[@]} 'BEGIN{printf "%.6f", f/n}')  # 合算は丸めない。表示時だけ 2 桁
  eval "sum_$tag=\$(awk -v a=\$sum_$tag -v b=$recall 'BEGIN{print a+b}'); n_$tag=\$((n_$tag+1))"
  total_sum=$(awk -v a=$total_sum -v b=$recall 'BEGIN{print a+b}'); total_n=$((total_n+1))
  [ "$found" -lt "${#rel[@]}" ] && missed="$missed- $id($tag): 正解 $(printf '%s ' "${rel[@]}" | sed 's#[a-z]*/##g')"$'\n' 
  printf '| %s | %s | %d | %d | %.2f | %s |\n' "$id" "$tag" "${#rel[@]}" "$found" "$recall" "$(printf '%s\n' "$top" | sed 's#.*/##' | paste -sd' ' -)"
done < "$GOLDEN"

echo
echo "## 全体 Recall@$K (答えなし ${n_none}問を除く $total_n 問): $(awk -v a=$total_sum -v n=$total_n 'BEGIN{printf "%.3f", a/n}')"
echo
echo "## タグ別"
for t in lex syn xlang multi; do
  eval "a=\$sum_$t; n=\$n_$t"
  [ "$n" -gt 0 ] && echo "- $t: $(awk -v a=$a -v n=$n 'BEGIN{printf "%.3f", a/n}') (n=$n)"
done
echo
echo "## 取りこぼし（正解の一部でも上位${K}外）: $(printf '%s' "$missed" | grep -c . || true) 問"
printf '%s' "$missed"

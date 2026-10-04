#!/usr/bin/env bash
# 常駐 hikidasu（実ツール）に golden の質問文を投げ、Recall@5 と @8 を出す
set -euo pipefail; HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
GOLDEN="${GOLDEN:-$HERE/golden.jsonl}"; expected=$(grep -c . "$GOLDEN"); export expected
jq -c '.' "$GOLDEN" | while read -r g; do
  id=$(jq -r .id <<<"$g"); q=$(jq -r .query <<<"$g"); rel=$(jq -c .relevant <<<"$g"); tag=$(jq -r .tag <<<"$g")
  "${HIKIDASU_BIN:-hikidasu}" "$q" -n 8 --json 2>>/tmp/measure-ruri-cli.err | jq -c --arg id "$id" --arg tag "$tag" --argjson rel "$rel" '{id:$id, tag:$tag, n:($rel|length), r5:([.[0:5][].path] as $t | [$rel[] | select(. as $r | $t | index($r))] | length), r8:([.[0:8][].path] as $t | [$rel[] | select(. as $r | $t | index($r))] | length)}'
done | jq -s -r --arg expected "$expected" 'if length != ($expected|tonumber) then error("問数が合わない: \(length) / \($expected)") else . end | (map(select(.n>0)) | "R@5=\((map(.r5/.n)|add/length)|.*1000|round/1000) R@8=\((map(.r8/.n)|add/length)|.*1000|round/1000) (n=\(length))"), (group_by(.tag) | map(select(.[0].n>0)) | map("\(.[0].tag): R@5=\((map(.r5/.n)|add/length)|.*100|round/100) R@8=\((map(.r8/.n)|add/length)|.*100|round/100)") | join("  "))'

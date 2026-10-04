# bench

[English](README.en.md)

計測スクリプト置き場です。
どれもノートのディレクトリを読むだけで、書き換えません。

golden ファイルは 1 行 1 問の JSONL で、`{"id","query","relevant":[paths],"tag","keywords":[...]}` の形です。
例は `../golden.example.jsonl` にあります。
`relevant` が空の行は「答えがない問い」として扱い、Recall の分母から外します。

- `measure-grep.sh [KB]`：grep のベースライン。語ごとに `grep -ric` し、ファイル単位で合算してヒット行数順に並べる（同数はパス昇順）
- `measure-qmd.sh search-kw|search-sent|vsearch|query [collection]`：qmd の Recall@5。qmd、jq、coreutils の `timeout` が要る
- `measure-embed.py --mode sent|kw [--model ...] [--field body|description]`：埋め込みを直接使った Recall@5。venv が要る
- `measure-hikidasu-cli.sh`：出荷版の `hikidasu` を通した Recall@5 と Recall@8
- `measure-embed-variants.py`：問いの定型句除去、原文とのアンサンブル、節ごとの埋め込みの比較と、答えなし問いのスコア分布
- `agent-bench.sh [並列数]`：`claude -p` に grep、hikidasu、併用の 3 通りの指示を与えて golden を解かせる（`GOLDEN=`、`MODELS=`、`VARIANTS=`、`BENCH_DIR=` で変更）。`agent-bench-report.py [dir]` で集計する。到達は「正解ノートを Read したか」、答えなしは「回答の冒頭に該当なしの文言があるか」で判定し、回答文の正しさは見ていない
- `translate.sh`：ollama（`MODEL=qwen3:8b`）でノートを英訳し `knowledge-en/` に置く。読むためではなく検索索引の派生物として扱い、原本のハッシュが変わった分だけ作り直す

## 読むときの注意

- 検索器単体の数値（grep、qmd、埋め込み）はキーワード入力と質問文入力を分けて見る。grep と BM25 はキーワード、埋め込みは質問文が本来の入力で、表に入力列を付けている
- `agent-bench.sh` の壁時計は、同じ計算機で他の負荷が無いときに逐次（並列 1）で測った値だけを比較に使う
- 評価セットを作った人が正解を知っている偏りは消えない。別の人（別のエージェント）に held-out セットを作らせて再計測するのが、この bench での検証のしかた

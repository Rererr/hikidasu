# qmd の Intl.Segmenter パッチ

[English](README.en.md)

[tobi/qmd](https://github.com/tobi/qmd)（MIT、Copyright (c) 2024-2026 Tobi Lutke。同じディレクトリの LICENSE を参照）に当てる実験用のパッチです。
`dist/store.js` にある CJK の 1 文字ずつの正規化を、Node 組み込みの `Intl.Segmenter("ja")` による語分割に置き換え、分割した語を 1 つの完全一致フレーズではなく独立した FTS5 の AND 項にします。

日本語ノート 104 本での計測では、`qmd search` の Recall@5 がキーワード入力で 0.402 から 0.461 に、質問文入力で 0.000 から 0.088 に動きました。
残る差は全語 AND の意味論によるもので、このパッチはそこを変えていません。

インストール済みのコピーに当てます（グローバルのインストールを直接書き換えず、先にコピーします）。

```sh
cp -R "$(npm root -g)/@tobilu/qmd" ./qmd-patched && ln -sfn "$(npm root -g)/@tobilu/qmd/node_modules" ./qmd-patched/node_modules
patch -d ./qmd-patched -p1 < qmd-intl-segmenter.patch
XDG_CACHE_HOME=./qmd-cache QMD_CONFIG_DIR=./qmd-config ./qmd-patched/bin/qmd collection add <dir> --name <name>
```

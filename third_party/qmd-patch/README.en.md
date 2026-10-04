# qmd Intl.Segmenter patch

[日本語版](README.md)

Experimental patch against [tobi/qmd](https://github.com/tobi/qmd) (MIT, Copyright (c) 2024-2026 Tobi Lutke; see LICENSE in this directory).
It replaces the per-character CJK normalization in `dist/store.js` with word segmentation via Node's built-in `Intl.Segmenter("ja")`, and turns each segmented word into an independent FTS5 AND term instead of one exact phrase.

Measured on a 104-note Japanese corpus: `qmd search` Recall@5 with keyword input 0.402 → 0.461; with full-sentence input 0.000 → 0.088. The remaining gap is the all-terms-AND semantics, which this patch does not change.

Apply to an installed copy (do not patch the global install in place; copy the package first):

```sh
cp -R "$(npm root -g)/@tobilu/qmd" ./qmd-patched && ln -sfn "$(npm root -g)/@tobilu/qmd/node_modules" ./qmd-patched/node_modules
patch -d ./qmd-patched -p1 < qmd-intl-segmenter.patch
XDG_CACHE_HOME=./qmd-cache QMD_CONFIG_DIR=./qmd-config ./qmd-patched/bin/qmd collection add <dir> --name <name>
```

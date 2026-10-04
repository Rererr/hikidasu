# 第三者のモデルとソフトウェア

[English](NOTICE.en.md)

このリポジトリにモデルの重みは含みません。
スクリプトは実行時に次のものを取得または参照し、それぞれのライセンスに従います。

| 対象 | ライセンス | 配布元 |
|---|---|---|
| cl-nagoya/ruri-v3-310m（既定の埋め込みモデル） | Apache-2.0 | https://huggingface.co/cl-nagoya/ruri-v3-310m |
| sentence-transformers/all-MiniLM-L6-v2（任意、英語の比較用） | Apache-2.0 | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 |
| tobi/qmd（計測対象。`third_party/qmd-patch/` にパッチと MIT 表示を同梱） | MIT | https://github.com/tobi/qmd |
| ggml-org/embeddinggemma-300M-GGUF（qmd が取得する。このリポジトリは取得しない） | Gemma Terms of Use | https://ai.google.dev/gemma/terms |
| ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF（qmd が取得する） | Apache-2.0 | https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF |
| tobil/qmd-query-expansion-1.7B-gguf（qmd が取得する） | MIT | https://huggingface.co/tobil/qmd-query-expansion-1.7B-gguf |
| ollama の qwen3:8b（任意、`bench/translate.sh` だけが使う） | Apache-2.0（ollama のライブラリページで確認すること） | https://ollama.com/library/qwen3 |
| sentence-transformers、torch、numpy（利用者が pip で導入する） | Apache-2.0、BSD 系、BSD 系 | PyPI |

Gemma は ai.google.dev/gemma/terms の Gemma Terms of Use のもとで提供されています。
このリポジトリは Gemma の重みを配布も改変もしません。

README の計測値は、ある個人の日本語ノート 104 本という 1 つのコーパスで測ったもので、一般化はできません。
計測に引用した LLM エージェントの出力は例示であり、内容の正しさを別に検証していません。

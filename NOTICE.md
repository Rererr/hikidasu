# Third-party models and software

This repository does not bundle any model weights. The scripts download or reference the following at run time; each is governed by its own license.

| Component | License | Source |
|---|---|---|
| cl-nagoya/ruri-v3-310m (default embedding model) | Apache-2.0 | https://huggingface.co/cl-nagoya/ruri-v3-310m |
| sentence-transformers/all-MiniLM-L6-v2 (optional, English baseline) | Apache-2.0 | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 |
| tobi/qmd (benchmark target; `third_party/qmd-patch/` carries a patch and its MIT license) | MIT | https://github.com/tobi/qmd |
| ggml-org/embeddinggemma-300M-GGUF (downloaded by qmd, not by this repo) | Gemma Terms of Use | https://ai.google.dev/gemma/terms |
| ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF (downloaded by qmd) | Apache-2.0 | https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF |
| tobil/qmd-query-expansion-1.7B-gguf (downloaded by qmd) | MIT | https://huggingface.co/tobil/qmd-query-expansion-1.7B-gguf |
| qwen3:8b via ollama (optional, used only by `bench/translate.sh`) | Apache-2.0 (verify on the ollama library page) | https://ollama.com/library/qwen3 |
| sentence-transformers / torch / numpy (installed by the user via pip) | Apache-2.0 / BSD-style / BSD-style | PyPI |

Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms. This repository neither distributes nor modifies Gemma weights.

Benchmark figures in README were measured on one private 104-note Japanese corpus and do not generalize. Outputs of LLM agents quoted in the benchmark are illustrative and were not independently verified for factual accuracy.

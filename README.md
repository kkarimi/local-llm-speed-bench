<h1 align="center">Local LLM Speed Bench</h1>

<p align="center">How long do you wait for the first token? How long for the whole reply?<br>
Run the same prompts across your local models and share the results in one offline leaderboard.</p>

<p align="center">
  <a href="https://github.com/kkarimi/local-llm-speed-bench/actions/workflows/ci.yml"><img alt="CI status on main" src="https://github.com/kkarimi/local-llm-speed-bench/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="MIT licence" src="docs/badges/license.svg"></a>
  <a href="https://karimi.info/lab/"><img alt="Explore the RTX 5090 leaderboard" src="docs/badges/leaderboard.svg"></a>
</p>

## Install and run

```sh
curl -fsSL https://raw.githubusercontent.com/kkarimi/local-llm-speed-bench/main/install.sh | bash
~/.local/bin/llm-speed-bench
```

On **macOS or Linux**, you’ll need Git, npm, Node.js 22.18+ and Python 3.9+. Start an OpenAI-compatible chat server with streaming and final token counts, then give the wizard its base URL (e.g. `http://127.0.0.1:8080/v1`). For authenticated endpoints, set `LAB_API_KEY` before launching.

Choose **Full recommended run** to test every listed model on short, long and 8K prompts, or **Custom run** to pick models, prompt lengths, repetitions and output cap. When it finishes, open the printed `league.html` path. That single file contains the interactive report.

## Which benchmark should I use?

| If you want to… | Reach for |
| --- | --- |
| Time a single chat request end to end across models or runtimes, then share a sortable offline report | **Local LLM Speed Bench** |
| Measure prompt processing and token generation directly inside llama.cpp for a GGUF model | [llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench) |
| See how serving latency and throughput change as concurrent requests increase | [vLLM bench serve](https://docs.vllm.ai/en/latest/cli/bench/serve/) |
| Compare installed models on speed, memory use and answer quality | [HomeBench](https://github.com/david-g-3654/homebench) |

### One GPU, two different winners

In our RTX 5090 trial, the faster Qwen3.8 27B configuration depended on prompt length. Each cell is the median time to finish a 256-token reply over three requests.

| Prompt | DFlash2 | EXL3 |
| --- | ---: | ---: |
| Short | **1.79 s** | 2.01 s |
| 8K | 4.31 s | **4.11 s** |

The leaderboard lets you switch between total time, first-token latency and tokens per second for the same runs. [Explore the RTX 5090 results →](https://karimi.info/lab/)

## Using the wizard

The wizard reads model IDs from `/models`, or accepts IDs by hand if discovery is unavailable. Your server handles model loading. Use **Custom run** if the server lists embedding models or a model has too little context for an 8K prompt plus its reply. In selection lists, use the arrows to move, Space to toggle and C to continue.

A full run makes **ten requests per model** in sequence. It sends one warm-up followed by three measured requests at each prompt length, capped at 256 output tokens per reply. The wizard shows the request count before you start. Successful runs go into a fresh `bench-runs/run-*/` folder under your working directory. If a model fails, the wizard continues and builds the report from the models that finished.

## Command-line use

If `~/.local/bin` is on your PATH, use `llm-speed-bench` directly. For example:

```sh
llm-speed-bench models --url http://127.0.0.1:8080/v1
llm-speed-bench bench --model YOUR_MODEL_ID --runtime "llama.cpp Q4" --out llama.json
llm-speed-bench report llama.json --machine "My workstation" --out league.html
```

Use `--url` with `bench` if your endpoint differs from the example. To compare endpoints or runtimes, save each configuration to a separate JSON file and pass the files together to `report`. Keep the seed, workloads, output limit, hardware and cache conditions consistent across runs.

From a source checkout, use `python3 lab.py` with the same subcommands for the Python-only CLI. For the wizard, run `npm ci` and then `npm start`. Set `PYTHON` if your Python executable has a different name.

## Measurements

Each measured prompt has a SHA-256 fingerprint. When comparing saved runs, the report checks their seed, output cap and ordered prompt fingerprints for each shared workload. Tokenisers, chat templates and early stopping can still affect the amount of work each server does.

The Python CLI default protocol makes one warm-up request and three measured requests at each of two prompt lengths. Add --include-8k to include three more requests at approximately 8,192 input tokens. The server-reported length must fall within 128 tokens of the target for that case. Tokenisation varies across models. Set --samples and --tokens to change repetitions and the reply limit. Run new comparison sessions with a fresh shared --seed to reduce prefix reuse.

The report ranks median first-token latency, elapsed response time, client-estimated decode throughput, engine-reported decode throughput and server-reported prefill throughput when available. Select either decode metric to rank by it and see the other alongside it. The JSON field `decode` retains its original client-side meaning. The optional `engine_decode` field reads TabbyAPI’s `usage.completion_tokens_per_sec` or llama.cpp’s `timings.predicted_per_second`. A native median requires valid engine rates for every measured sample in that workload. Older runs still display their client estimates. Grouped stream chunks can skew the decode estimate. Native prefill timings may differ between engines. These ratings measure performance only.

Run files contain the model and runtime labels, protocol settings, token counts and measurements. The standalone HTML embeds the aggregated results and chosen machine label. Publishing either file is optional.

## Updates and CI

Re-run the installer to update. It installs locked runtime packages and switches the command after the new copy passes its checks. For a reproducible install, replace `main` in the URL with a reviewed commit SHA and pass that same SHA as `LLM_BENCH_REVISION` to Bash. To uninstall, remove `~/.local/bin/llm-speed-bench` and the `local-llm-speed-bench` folder under `${XDG_DATA_HOME:-$HOME/.local/share}`.

GitHub Actions runs on pull requests and pushes to `main`. Linux and macOS jobs install the tool in a temporary home directory, exercise both wizard modes against a local test server, check TypeScript and run the Python tests. Linux also checks npm dependencies for high and critical advisories. [View CI runs](https://github.com/kkarimi/local-llm-speed-bench/actions/workflows/ci.yml).

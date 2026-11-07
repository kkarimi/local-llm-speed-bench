# Local LLM Speed Bench

Benchmark local LLM inference speed across runtimes on your own hardware. Measure **tokens per second**, **time to first token (TTFT)** and **total response time**, then share the interactive leaderboard as a single HTML file. [Explore the RTX 5090 leaderboard](https://karimi.info/lab/).

## Which runtime gets the answer to you sooner?

In the RTX 5090 trial behind this project, two Qwen3.8 27B configurations answered identical 8K prompts with 256-token replies. DFlash2 finished the short-prompt workload in **1.79 s** versus **2.01 s** for EXL3. At 8K the order reversed: **4.31 s** versus **4.11 s**. Each figure is the median of three requests. Select a prompt length and sort by total response time to see where a change actually helps.

Use this tool when you already have two serving configurations and want a controlled, single-user comparison you can send to someone. It runs with stock Python. Each new run records a SHA-256 fingerprint of each measured user prompt. The report checks the seed, output cap and the ordered prompt samples for every shared workload. It also checks server-reported input length before accepting an 8K sample. Chat templates, tokenisers and early stopping can still change the actual work done.

## Which benchmark fits your question?

| Question | Tool to use | Why |
|---|---|---|
| Which of my two running servers responds sooner to the same short, long or 8K chat prompts? | Local LLM Speed Bench | Compare matching prompts across endpoints and switch between TTFT, generation, prefill and total time in the offline report. |
| How fast is a particular GGUF and llama.cpp build at prompt processing and generation? | [llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench) | Measures those operations directly inside llama.cpp. |
| What happens as incoming requests and concurrency increase? | [vLLM bench serve](https://docs.vllm.ai/en/latest/cli/bench/serve/) | Supports controlled request rates, concurrent requests and serving latency statistics. |
| Which installed model balances speed, memory and answer quality? | [HomeBench](https://github.com/david-g-3654/homebench) | Includes model discovery, quality tasks, run history and self-contained HTML reports. |

Scores and speeds from different tools depend on their timing boundaries, prompts, output lengths, concurrency and cache behaviour. The comparison above describes documented capabilities. No head-to-head accuracy or performance advantage over these tools has been measured.

## Install on macOS or Linux

Requires Git, npm, Node.js 22.18+ and Python 3.9+. Run:

```sh
curl -fsSL https://raw.githubusercontent.com/kkarimi/local-llm-speed-bench/main/install.sh | bash
llm-speed-bench
```

The command opens the interactive wizard. Use `llm-speed-bench --help` for scripting. If your shell cannot find it, run `~/.local/bin/llm-speed-bench`. The installer uses your own account and leaves your shell configuration alone. Results go in the directory where you start the wizard.

Re-run the installer to update. It installs locked runtime packages and switches the command after the new copy passes its checks. For a reproducible install, replace `main` in the URL with a reviewed commit SHA and pass that same SHA as `LLM_BENCH_REVISION` to Bash. To uninstall, remove `~/.local/bin/llm-speed-bench` and the `local-llm-speed-bench` folder under `${XDG_DATA_HOME:-$HOME/.local/share}`.

## Quick start

Requires Python 3.9+ and a running OpenAI-compatible chat server supporting streaming and final token usage. Load the desired model using your usual runtime. For authenticated endpoints, supply the key through the LAB_API_KEY environment variable.

    python3 lab.py bench --model YOUR_MODEL_ID --runtime "llama.cpp Q4" --out llama.json
    python3 lab.py report llama.json --machine "My workstation" --out league.html

Open league.html in a browser. To compare configurations, benchmark each one separately and pass all run files to the report command. Use identical hardware, seed, output limit, thinking settings and cache conditions. Each model/runtime label must identify one configuration. Use --url to change the default endpoint (http://127.0.0.1:8080/v1).

## Interactive benchmark

From this checkout, run `npm ci` and then `npm start` in a terminal. The wizard requires Node.js 22.18+ and Python 3.9+. Set `PYTHON` if your Python executable has a different name.

Enter an OpenAI-compatible base URL. The wizard reads the IDs from its `/models` endpoint, or accepts IDs by hand if discovery is unavailable. Your server controls model loading. If the catalogue also lists embedding or other non-chat models, use **Custom run** to select streaming chat models.

- **Full recommended run** benchmarks every listed model sequentially with one warm-up and three requests per prompt length (short, long and 8K), capped at 256 output tokens. That is ten requests per model. The 8K workload needs enough context for both prompt and reply.
- **Custom run** lets you select models and prompt lengths, repetitions and the output cap. Use the arrow keys to move, Space to toggle and C to continue.

The plan shows the request count before starting. Each session uses a fresh shared seed and writes successful model runs and an offline `league.html` to a new folder under `bench-runs/`. A model that fails a workload is excluded from the report, and the wizard continues with the next model. The Python CLI remains available for automation, including `lab.py models --url BASE_URL` and `lab.py bench --cases short 8k ...`.

## Measurements

The default protocol makes one warm-up request and three measured requests at each of two prompt lengths. Add --include-8k to include three more requests at approximately 8,192 input tokens. The server-reported length must fall within 128 tokens of the target for that case. Tokenisation varies across models. Set --samples and --tokens to change repetitions and the reply limit. Run new comparison sessions with a fresh shared --seed to reduce prefix reuse.

The report ranks median first-token latency, elapsed response time, client-estimated decode throughput, engine-reported decode throughput and server-reported prefill throughput when available. Select either decode metric to rank by it and see the other alongside it. The JSON field `decode` retains its original client-side meaning. The optional `engine_decode` field reads TabbyAPI’s `usage.completion_tokens_per_sec` or llama.cpp’s `timings.predicted_per_second`. A native median requires valid engine rates for every measured sample in that workload. Older runs still display their client estimates. Grouped stream chunks can skew the decode estimate. Native prefill timings may differ between engines. These ratings measure performance only.

Run files contain the model and runtime labels, protocol settings, token counts and measurements. The standalone HTML embeds the aggregated results and chosen machine label. Publishing either file is optional.

MIT licensed.

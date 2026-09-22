# Step 1 evidence — Moonshot API foundations

## Current status

I now have a small command-line program that can check its configuration, list
models, ask a text question, and turn a request into a validated JSON object.
The assistant wrote the implementation at my request. This report and reflection
answers are assistant-assisted drafts in a beginner's voice for me to review;
they do not prove that I can build or explain everything independently yet.

The technical checks pass: **48 offline tests**, plus the successful live results
I previously pasted from my terminal. Formal Step 1 acceptance is still pending.
The outside-Python curl exercise is not evidenced here, and human mentor sign-off
has not been recorded. No Step 2 implementation has been added.

## Repository and environment

Reviewed on 2026-09-21 against commit `b8a7ac5` and the working tree.

- Local project and Python package distribution: `lab-workflow-agent`.
- Git branch: `main`, tracking `origin/main`; the existing commits have been pushed.
- Remote: [xfeng167/lab_workflow_agent](https://github.com/xfeng167/lab_workflow_agent).
  The GitHub name uses underscores, while the assignment asks for
  `lab-workflow-agent`. This naming difference remains for mentor review.
- This documentation update is not yet committed or pushed.
- Python 3.11.15; uv 0.11.26.
- Locked dependencies: openai 2.54.0, pydantic 2.13.5,
  pydantic-settings 2.15.0, httpx 0.28.1, pytest 9.1.1. See `uv.lock`.
- Provider: international Kimi, `https://api.moonshot.ai/v1`.
- Selected model: `kimi-k2.6`. I kept the assignment default because my recorded
  models response included it and the live smoke test succeeded with it.
- Configuration uses a secret environment source or ignored `.env` file.
  No API key is included in this report.

## What the code does

| File | How I understand its job |
| --- | --- |
| `src/lab_workflow_agent/config.py` | Checks settings, including the key, endpoint, model, and 1–300 completion-token limit. |
| `src/lab_workflow_agent/provider.py` | Contains the SDK connection and turns provider errors into short application errors. |
| `src/lab_workflow_agent/service.py` | Rejects incomplete answers and validates the extracted JSON fields. |
| `src/lab_workflow_agent/cli.py` | Provides `doctor`, `models`, `chat`, `extract-intent`, and `smoke`. Live commands require `--live`. |
| `tests/test_foundations.py` | Uses fake responses and mocked HTTP to check behavior without spending API credit. |
| `tests/conftest.py` | Keeps tests away from real credentials and blocks socket connections. |

The program has no Lab Storage API calls, tools, agent loop, or inventory writes.
Extracting “find 20 samples” only produces an interpretation of text; it does
not search real stock or place an order.

## Offline checks

The assistant reran these checks for this documentation review:

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=/private/tmp/lab-workflow-agent-uv-cache uv run --frozen --offline pytest` | **48 passed in 0.76s**. |
| `.venv/bin/labops-agent doctor` | Passed: key present, international endpoint, `kimi-k2.6`, limit 300, thinking disabled, network not used. |
| `uv --version` / `.venv/bin/python --version` | uv 0.11.26 / Python 3.11.15. |

The first test command could not access the default uv cache because of sandbox
permissions. Using a writable temporary cache let the offline test run complete.
This was an environment access problem, not a failing test.

The original implementation review also recorded `uv sync --frozen --offline`
passing, 48 tests passing in 1.87s, `.env` and `.env.local` being ignored, a safe
missing-key error, and rejection of a live command without `--live`.

Tests cover missing/invalid settings, redaction, live opt-in, text and JSON
responses, wrong JSON fields/types, invalid quantities and QC values, empty or
truncated output, malformed provider responses, provider errors, and stopping the
smoke test after failure. Mocked HTTP checks also verify request settings and that
no automatic retries occur. These simulated errors are not live provider results.

## Recorded live checks

These results were supplied by me from my terminal on 2026-09-21 and preserved
in the earlier evidence report. The assistant did not rerun live requests during
this update or inspect my API key.

1. `uv run labops-agent models --live` initially failed authentication. I was
   advised to check the international key and any stale exported value. The exact
   cause and corrective action were not established in the record.
2. A later `models --live` succeeded and listed `kimi-k2.6`, `kimi-k2.7-code`,
   `kimi-k2.7-code-highspeed`, and `kimi-k3`. This records what I observed then,
   not a fresh claim about which models are available today.
3. `uv run labops-agent smoke --live` completed all three checks:

| Check | Recorded result |
| --- | --- |
| Models | Authenticated listing succeeded. |
| Text completion | “An API is a set of rules that lets different software applications talk to each other.” Model `kimi-k2.6`; finish reason `stop`; 15 prompt + 20 completion = 35 tokens. |
| Structured extraction | Intent `find_material`, query `control samples`, quantity 20, QC `passed`. Local validation passed; model `kimi-k2.6`; finish reason `stop`; 109 prompt + 24 completion = 133 tokens. |

The two completions used **168 reported tokens** in total. Currency cost was not
reported. The recorded count is **four successful requests and one authentication
failure: five known attempts**. The repeated models output in the original paste
was treated as the same result, not another invocation. This is a minimum observed
count, not an account-wide usage audit. No new live requests were made for this
review, and the program does not automatically retry.

## My reflection draft

1. **API key, base URL, and model ID:** The key identifies my account, the base URL
   tells the program where to send the request, and the model ID chooses the model.
2. **Why keep the model configurable?** I may need a different available model
   later. Changing a setting is simpler than changing the workflow code.
3. **What does `finish_reason` mean?** It tells me why generation ended. `stop`
   means it finished normally; `length` means it ran out of room. This program
   rejects truncated output instead of treating it as a complete answer.
4. **Why is valid JSON still untrusted?** JSON can be readable but contain the
   wrong fields, types, or facts. The schema checks its shape. It cannot prove
   that the requested samples exist in the lab.
5. **Why use a fake provider in tests?** Tests can run without a key, network,
   or API cost. I can also test failures without causing them on a live account.
6. **Which errors could be retried?** A temporary connection or server problem
   might allow a limited retry later. A timeout may still have used provider
   resources. Wrong credentials, balance problems, or rate limits mean I should
   stop and investigate. This implementation retries nothing automatically.
7. **What belongs in errors and traces?** A user needs a short explanation and
   a useful next action. A development trace can include safe timing and request
   IDs. Neither should contain keys, authorization headers, or secret payloads.
8. **Why no tools or agent loop yet?** I am first learning to send requests and
   check responses. Adding real lab actions now would make failures harder to
   understand and introduce changes to business data before this foundation is ready.

## Short beginner review answers

These answers were drafted with assistant help and added at my request.

1. **What is the difference between an API key, a base URL, and a model ID?**
   An API key identifies my account, the base URL tells my program where to send
   requests, and the model ID selects which model to use.
2. **Does valid JSON requesting 20 samples prove those samples exist?**
   No. Valid JSON only means the response has a valid format. I still need to
   check the Lab Storage API to see whether the samples exist.
3. **Why use fake responses instead of calling Kimi in tests?**
   Fake responses make tests repeatable, free, and usable without internet or
   a real API key. They also let me test errors safely.

## Limitations and next review steps

- My live results are user-supplied terminal evidence, not an independently
  captured provider log. They support the recorded smoke behavior only.
- The request budget across separate commands is tracked manually. I should
  count any further curl exercise against the assignment's ten-success limit.
- The SDK uses 30-second operation timeouts; that is not a total process deadline.
- JSON validation checks structure, not truth. The smoke example additionally
  checks the expected intent, quantity, QC, and a nonempty material query.
- I still need evidence for the required outside-Python curl exercise. The
  successful smoke behavior does not need to be repeated for this report.
- I need to review these reflection answers, explain the code in my own words,
  and obtain mentor acceptance. The GitHub naming difference should be resolved
  or acknowledged in that review. Step 2 has not been supplied or started.

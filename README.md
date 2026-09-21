# lab-workflow-agent

Minimal Moonshot API foundations for a future Lab Storage workflow assistant.
The existing Lab Storage API remains the business system of record. This milestone
only learns the provider protocol: it has no Lab Storage calls, tools, agent loop,
frontend, or inventory writes.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

Open the [Kimi international console](https://platform.kimi.ai/), create a
project-specific API key, and check usable credit. Enter the key privately in the
ignored `.env` file or supply `MOONSHOT_API_KEY` through your secret environment.
Never paste it in chat, screenshots, logs, Git, or command-line arguments.

```bash
uv run labops-agent doctor
uv run pytest
```

`doctor` is offline. Missing/invalid configuration returns exit code 1 with safe
field names. Tokens must be 1–300. The base URL is restricted to
`https://api.moonshot.ai/v1`; redirects and SDK retries are disabled. Requests have
30-second SDK timeouts. Default tests use fakes and block socket connections,
clear Moonshot environment variables, and ignore your `.env`.

## Explicit live checks

Live commands spend API credit and send their prompt to Kimi. Use short synthetic
prompts only. Every command below requires `--live`.

```bash
uv run labops-agent models --live
uv run labops-agent chat "Explain an API in one sentence." --live
uv run labops-agent extract-intent "Find twenty passed QC control samples." --live
```

The default model is the assignment's `kimi-k2.6`, pending authenticated model
verification. Confirm it appears in `models` before chat requests. Do not guess
another model if unavailable: review its capabilities first and update
`MOONSHOT_MODEL`. `MOONSHOT_THINKING=disabled` keeps the K2.6 smoke request small;
models without this switch need `omit`. A reasoning-only model may exhaust the
300-token cap; report truncation rather than silently raising the cap or retrying.

After offline tests pass, the standalone live smoke command checks the models
endpoint (also authentication), text completion, and validated intent extraction:

```bash
uv run labops-agent smoke --live
```

This makes exactly three HTTP requests on success and stops on the first error.
It reports completed request counts after each successful check; a failing
completion may still be billable. Track attempts and successes in the evidence
report. Do not exceed ten successful requests across all milestone commands,
including any curl checks. Stop on authentication, balance, or rate-limit errors.
The CLI does not maintain a persistent cross-invocation request budget.

JSON mode uses `response_format=json_object` plus local strict Pydantic validation.
Unknown fields, wrong types, invalid QC statuses, nonpositive quantities, missing
fields, malformed JSON, empty content, and truncated output are rejected. Model
extraction is unverified interpretation, not a fact about real inventory.

## Design and review

- `config.py`: validated, secret-safe environment configuration.
- `provider.py`: small message/completion protocol and the only SDK adapter.
- `service.py`: complete-response checks and strict intent validation.
- `cli.py`: offline doctor and explicit live commands.
- `tests/`: deterministic fake-provider and mock-HTTP tests, no live pytest tests.

Provider errors expose application-owned messages, never provider exception text.
SDK HTTP logging is disabled by the CLI. No automatic retries are used, including
for timeouts; inspect the error before choosing a later manual retry.

The source assignments are preserved under `milestones/`; project overview,
roadmap, and mentor checklist remain the review references. See
`docs/step-00-review-update.md` and `docs/step-01-evidence.md` for verified results
and pending work. Step 1 is not accepted until live evidence and learner review
are complete. Step 2 is not implemented.

References: [Chat Completions](https://platform.kimi.ai/docs/api/chat),
[JSON mode](https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api),
[models](https://platform.kimi.ai/docs/api/list-models).

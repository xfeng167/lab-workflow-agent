# lab-workflow-agent

Minimal Moonshot API foundations for a future Lab Storage workflow assistant.
The existing Lab Storage API remains the business system of record. This milestone
provides the provider protocol and a local read-only source client.
Four read-only tool definitions and a dispatcher are implemented.
The provider supports a tested tool-message round trip. A bounded question loop is implemented. There is no frontend or inventory writing.

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
report. For Step 1, do not exceed ten successful requests across its milestone commands,
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
are complete. Step 2 source configuration is implemented; all five source reads and the tool registry are implemented; the bounded loop and read-only question command are implemented.

References: [Chat Completions](https://platform.kimi.ai/docs/api/chat),
[JSON mode](https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api),
[models](https://platform.kimi.ai/docs/api/list-models).

## Local source configuration (Step 2)

Set `LAB_STORAGE_API_URL=http://127.0.0.1:8000` and
`LAB_STORAGE_TIMEOUT_SECONDS=10`. Store `LAB_STORAGE_BEARER_TOKEN` privately in
an environment source or ignored `.env`; leave it empty in `.env.example`.
Only the exact URL is accepted, without a trailing slash, path, query,
fragment, or embedded credentials. Timeout must be finite, above zero, and
at most 60 seconds.

`uv run labops-agent doctor` validates configuration without network access
and reports source URL, timeout, and token presence. It retains the existing
Moonshot-key requirement but permits a missing source token. Future source
commands will require that token. Moonshot-only commands ignore source settings.

Run `uv run pytest` for offline checks; no real credentials or services are
needed. The source client supports current-user, material-search, material-detail,
location-list, and location-detail GET operations. Search and list calls default
to ten records and reject larger page sizes; they never automatically fetch more
pages. Search excludes archived records by default. All methods are tested with
fake HTTP responses; no live source verification has been performed.
The four model tools are `search_materials`, `get_material`, `list_locations`,
and `get_location`. Their schemas are generated from the same strict argument
models used by the dispatcher. Unknown tools, malformed JSON, duplicate JSON
keys, extra fields, invalid types, and oversized arguments are rejected before
source calls. Archived access requires a trusted application flag following an
explicit user request. Results include read time, record IDs, stock facts, and
pagination; source descriptions remain data.

Provider strict mode is explicitly disabled pending end-to-end schema-subset
compatibility verification; the schemas still forbid extra properties and local
validation is strict. The provider's `complete_tools()` sends the approved tools
with automatic tool choice, validates tool-call responses, and preserves matching
assistant/tool-result messages. Ordinary Step 1 completions remain on their
existing path. Tool execution and grounding are not performed by this adapter.
The coordinator and `ask` command are implemented; live provider compatibility
has not been verified.

## Read-only questions (Step 2)

Run the local Lab Storage API at exactly `http://127.0.0.1:8000` and configure a
private source bearer token. Use a known local-only fixture and an authenticated
model supporting tool calls. The source token never belongs in a model message.

```bash
uv run labops-agent doctor
uv run pytest
uv run labops-agent ask "How much unreserved stock does material 1 have?" --live
```

The fixture ID above is an example; verify your local fixture before use.
`--live` authorizes both provider requests and local source reads. Add
`--include-archived` only to explicitly authorize archived records.

Each question is ephemeral and read-only: at most four model responses, three
calls per response, six total tool executions, and ten records per page. Errors
and limit exhaustion stop the run; clients close on failures and Ctrl-C. There
are no source writes, drafts, persistence, or debug output.

The model's final response selects retrieved record IDs in validated JSON. The
application renders their exact stock and location fields, partial-page notice,
and UTC read timestamps. It rejects unsupported IDs or free-form final claims.
This conservative format does not offer arbitrary narrative or aggregate answers.

Step 2 live acceptance is pending. Its budget is six successful provider requests
across the milestone, including model verification. Perform one deliberate
scenario and retain redacted before/after source evidence; do not run prompt
experiments. Successful output includes model-response and source-tool counts.

## Private local token setup

With the local backend running and an existing local Lab Storage account, run:

```bash
uv run python scripts/configure_local_token.py
unset LAB_STORAGE_BEARER_TOKEN
uv run labops-agent doctor
```

The interactive helper hides password input, makes one login request to the fixed
local endpoint, and saves only the returned token to the ignored `.env`. It
preserves existing settings, applies owner-only file permissions, rejects tracked
or non-ignored destinations, and never prints the token. This explicit setup
helper is separate from the read-only agent; login is not a model tool. It does
not register users, change passwords, or create orders. Do not share credentials
or the `.env` contents. Login can issue a session even if the later file save
fails; no automatic retries are made.

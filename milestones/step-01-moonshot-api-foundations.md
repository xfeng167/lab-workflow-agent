# Milestone 1: Moonshot API Foundations

## Unlock condition

Begin this milestone only after the mentor accepts Milestone 0.

## Goal

Build the smallest safe LLM application for `lab-workflow-agent` using the Kimi
international API platform.

At the end of this milestone, the project has:

- Safe Moonshot configuration.
- A small provider boundary.
- A command-line entry point.
- One bounded text response.
- One locally validated structured response.
- Deterministic tests using a fake provider.
- Explicit, opt-in live smoke checks.

Do not implement Lab Storage tools or an agent loop in this milestone.

## Why this milestone matters

Before a model can choose tools, you must understand the provider protocol,
credentials, messages, model IDs, response metadata, structured output,
failures, and testing boundary.

The goal is not to create a chatbot. The goal is to create one reliable model
client that later workflows can use without spreading provider-specific code
through the application.

## Official references

Use the international documentation paths:

- Console: <https://platform.kimi.ai/>
- [API overview](https://platform.kimi.ai/docs/api/overview)
- [Quickstart](https://platform.kimi.ai/docs/api/quickstart)
- [List models](https://platform.kimi.ai/docs/api/list-models)
- [Chat Completions reference](https://platform.kimi.ai/docs/api/chat)
- [JSON Mode guide](https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api)

The documented international base URL is:

```text
https://api.moonshot.ai/v1
```

Do not use the mainland-China `api.moonshot.cn` endpoint in this project.

The official documentation currently uses `kimi-k2.6`, but model availability
must be checked with the authenticated models endpoint before relying on that
name.

## Prerequisites

- Milestone 0 accepted.
- A Git repository named `lab-workflow-agent` containing the supplied project
  documents.
- Python 3.11 or newer.
- `uv` installed.
- A Kimi international API-platform account.
- Permission to create a project-specific API key and use a small amount of API
  credit.

## Allowed scope

- Initialize the Python package in `lab-workflow-agent`.
- Add provider and configuration dependencies.
- Create the Moonshot configuration and provider client.
- Create a minimal CLI.
- Add unit tests and explicitly marked live smoke tests.
- Update project documentation with setup and verification instructions.

## Out of scope

- Calls to the Lab Storage API.
- Lab Storage login or bearer tokens.
- Tool or function calling.
- Multi-turn workflow state beyond a small protocol-learning demonstration.
- Order drafts, confirmations, or writes.
- Agent frameworks.
- LangChain, LangGraph, vector databases, or RAG.
- Streaming.
- Web API or frontend work.

## Safety and cost rules

- Never commit, print, log, screenshot, or send the API key to another person.
- Unit tests must pass when `MOONSHOT_API_KEY` is absent.
- Default test commands must never call the live provider.
- Every live command must require an explicit `--live` or equivalent opt-in.
- Keep milestone live prompts short.
- Set a bounded `max_completion_tokens`; start at 300 or lower.
- Use at most 10 successful live provider requests for the milestone evidence.
- Do not add retries for authentication, balance, or rate-limit failures.
- Stop live testing on `401`, repeated `429`, an unexpected balance problem, or
  a response that exposes sensitive configuration.

## Task 1.1: Create a project-specific API key

1. Open <https://platform.kimi.ai/>.
2. Sign in to the Kimi international API platform.
3. Confirm that you are in the API platform or console, not only the consumer
   chat application.
4. Create a separate platform project for `lab-workflow-agent` when the console
   supports project organization.
5. Open the API-key management page.
6. Create a project-specific API key.
7. Copy the key once and store it in a local password manager or approved secret
   location.
8. Check that the account has usable balance or trial credit.

Do not paste the key into a committed file or the milestone evidence.

## Task 1.2: Verify the provider outside Python

Set temporary shell variables:

```bash
export MOONSHOT_API_KEY='paste-your-key-in-this-shell-only'
export MOONSHOT_BASE_URL='https://api.moonshot.ai/v1'
export MOONSHOT_MODEL='kimi-k2.6'
```

List models:

```bash
curl -sS \
  "$MOONSHOT_BASE_URL/models" \
  -H "Authorization: Bearer $MOONSHOT_API_KEY"
```

Confirm whether `kimi-k2.6` is available. If it is not, choose an appropriate
chat model returned by the API and record the non-secret model decision.

Make one small Chat Completions request:

```bash
curl -sS \
  -X POST "$MOONSHOT_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"$MOONSHOT_MODEL\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": \"Reply with one short sentence explaining what an API is.\"
      }
    ],
    \"max_completion_tokens\": 120
  }"
```

Inspect without copying secrets into documentation:

- Response model.
- Assistant content.
- `finish_reason`.
- Token usage when returned.
- Error shape if the request fails.

## Task 1.3: Initialize the Python package

Run from the root of the separate `lab-workflow-agent` repository. Preserve the
supplied README and documentation:

```bash
uv init \
  --package \
  --name lab-workflow-agent \
  --python 3.11 \
  --no-readme \
  --vcs none \
  --no-workspace \
  .
```

Add runtime dependencies:

```bash
uv add 'openai>=1.0' 'pydantic-settings[dotenv]>=2.5'
```

Add test dependencies:

```bash
uv add --dev 'pytest>=8.3'
```

Do not add an agent framework.

Before continuing, inspect the generated files and remove only irrelevant
placeholder code. Do not delete the supplied project documents.

## Task 1.4: Define safe configuration

Create `.env.example` containing names and non-secret defaults only:

```text
MOONSHOT_API_KEY=
MOONSHOT_BASE_URL=https://api.moonshot.ai/v1
MOONSHOT_MODEL=kimi-k2.6
MOONSHOT_MAX_COMPLETION_TOKENS=300
```

Create or update `.gitignore` so `.env` and other local secret files are not
tracked.

Create configuration code that:

- Reads the key from `MOONSHOT_API_KEY`.
- Defaults the base URL to `https://api.moonshot.ai/v1`.
- Reads the model from configuration.
- Validates that the maximum completion token value is positive and bounded.
- Fails early with a concise, user-safe error when required configuration is
  missing.
- Never includes the API key in `repr`, logs, exception text, or CLI output.

Add a CLI configuration diagnostic, such as:

```bash
uv run labops-agent doctor
```

The command should report whether required configuration is present, the base
URL, model, and output limit. It must never display the key.

## Task 1.5: Create a small provider boundary

Create one application-facing LLM client abstraction and one Moonshot-backed
implementation.

The rest of the application should not construct the OpenAI SDK client directly.

The provider boundary must support the minimum behavior needed in this
milestone:

- List models.
- Send a list of chat messages.
- Request a bounded plain-text completion.
- Request a structured JSON response.
- Return normalized content, model, finish reason, and usage metadata.
- Convert provider exceptions into a small set of application-level errors.

Do not design a universal provider framework. One clear boundary and one
Moonshot implementation are enough.

## Task 1.6: Implement the minimal CLI

Provide commands equivalent to:

```bash
uv run labops-agent doctor
uv run labops-agent models --live
uv run labops-agent chat "Explain tool calling in one sentence." --live
uv run labops-agent extract-intent "Find twenty passed QC control samples." --live
```

Required behavior:

- `doctor` performs no network request.
- Live commands refuse to run without explicit live opt-in.
- `models` displays model IDs without dumping raw response objects.
- `chat` prints the assistant answer plus concise non-secret metadata.
- `extract-intent` requests a JSON object containing fields such as `intent`,
  `material_query`, `quantity`, and `qc_status`.
- Structured content is parsed and validated locally before display.
- Invalid or truncated structured output produces an honest error.

Kimi supports `response_format` JSON modes. A valid JSON response is still
untrusted input and must pass local schema validation.

## Task 1.7: Create a fake provider and unit tests

Default tests must use a deterministic fake client, not the network.

Cover at least:

- Valid configuration.
- Missing API key.
- Secret redaction.
- Fake plain-text success.
- Fake structured-output success.
- Invalid JSON.
- Valid JSON with invalid fields.
- `finish_reason=length` or equivalent truncation.
- Authentication error mapping.
- Rate-limit error mapping.
- Provider timeout or unavailable error mapping.
- Live commands rejected without explicit opt-in.

Running this command must not require a key or network:

```bash
uv run pytest
```

## Task 1.8: Add explicit live smoke tests

Live tests must be separated from the default test suite. Use an explicit marker,
flag, command, or environment gate so accidental `pytest` execution remains
offline.

The live smoke set should contain only:

- Configuration and authentication check.
- Models-list check.
- One bounded plain-text completion.
- One bounded structured-output completion.

Do not add automatic retries or repeated parameter experiments.

## Required documentation

Update `README.md` with:

- Python and `uv` prerequisites.
- Kimi international console link.
- API-key creation summary.
- `.env` setup.
- Install and run commands.
- Offline test command.
- Explicit live smoke command.
- Cost and secret warnings.
- Current milestone limitations.

Create `docs/step-01-evidence.md` containing:

- Python and `uv` versions.
- Dependency versions.
- Provider platform and base URL, without the key.
- Model IDs observed from `/v1/models`.
- Selected model and reason.
- CLI commands run.
- Concise successful output evidence.
- Unit-test result.
- Live-smoke result and total number of live requests.
- Error cases verified with fakes.
- Known limitations.
- Answers to the reflection questions.

## Required checks

Run:

```bash
uv run pytest
uv run labops-agent doctor
git diff --check
git status --short
```

Run the live smoke command only once the offline checks pass and only with the
documented explicit opt-in.

Also verify that these commands do not reveal secrets:

```bash
git diff
git grep -n 'sk-'
```

If `git grep` finds a value that resembles a real key, stop, revoke the key if
necessary, remove it from the working tree and Git history, and notify the
mentor. Do not merely add the already-committed file to `.gitignore`.

## Definition of done

Milestone 1 is complete only when:

- The repository and package are named `lab-workflow-agent`.
- International Kimi configuration uses `https://api.moonshot.ai/v1`.
- The API key is supplied only through a secret environment source.
- `doctor` validates configuration without network access or key disclosure.
- The authenticated models endpoint has been checked.
- One configured model completes a bounded text request.
- One structured response is parsed and locally validated.
- Provider-specific construction is isolated behind one small boundary.
- Unit tests pass without network access and without a real key.
- Live checks require explicit opt-in and stay within the request budget.
- Provider failures become clear, non-secret application errors.
- Documentation and evidence are complete.
- No Lab Storage tool, workflow, or write action has been implemented.
- The mentor accepts Milestone 1.

## Stop conditions

Stop and ask for help if:

- The account appears to belong to a different Kimi platform region.
- The international models endpoint does not accept the key.
- The account has no expected balance or permission.
- A real key is committed, printed in evidence, or exposed in a log.
- The documented model is unavailable and model selection is unclear.
- Default unit tests make a network call.
- The implementation begins to include Lab Storage tools or agent frameworks.
- Live requests repeatedly return `429` or an unexpected provider error.

## Reflection questions

Answer these in `docs/step-01-evidence.md`:

1. What is the difference between an API key, a base URL, and a model ID?
2. Why must model names be configuration rather than business logic?
3. What does `finish_reason` tell the application?
4. Why is syntactically valid JSON still untrusted?
5. Why must unit tests use a fake provider?
6. Which provider errors are safe to retry, and which should stop immediately?
7. What information belongs in a user-facing error versus a development trace?
8. Why are there no tools or agent loop in this milestone?

## Submission

Provide the mentor with:

- A concise implementation summary.
- Files changed.
- `git diff --stat` and `git status --short`.
- Offline test results.
- Bounded live-smoke results and request count.
- `docs/step-01-evidence.md`.
- Known limitations and open questions.

Do not begin or write Milestone 2. It will be supplied only after Milestone 1 is
accepted.

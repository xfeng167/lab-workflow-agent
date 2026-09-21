# Step 1 implementation evidence

Status: offline implementation ready; live provider evidence and final acceptance
pending. Implementation was assistant-authored at the user's explicit request.
This is not evidence of unaided learner implementation or understanding.

## Scope and provenance

Separate project: `/Users/snowflake2.0/Desktop/lab-workflow-agent`.
Source backend remains at base commit `c96978c7da0a97942d0bb0b452b64f49b411c7a7`
plus the previously disclosed unrelated changes. Existing Step 0 docs preserved.
Agent changes are uncommitted; no remote, push, or deployment was created.

Added packaging, configuration, provider protocol/adapter, CLI, strict intent
validation, offline tests, lockfile, setup docs, and preserved curriculum files.
There are no Lab Storage calls, tools, agent loop, frameworks, or business writes.

## Environment and verification

Python 3.11.15; uv 0.11.26. Resolved SDK openai 2.54.0,
pydantic 2.13.5, pydantic-settings 2.15.0, httpx 0.28.1, pytest 9.1.1.
Exact dependency versions are in `uv.lock`.

Offline verification results are appended after final installation below.
Default tests remove Moonshot variables, change to an empty temporary directory,
and block socket connections. Mock HTTP tests exercise the actual SDK adapter,
including bounded request arguments, no automatic retries, and error mapping.
Fakes cover text/JSON, invalid JSON/fields, strict quantity types, truncation,
missing credentials, offline doctor, live opt-in, redaction, and smoke stopping.

Provider: international Kimi, `https://api.moonshot.ai/v1`.
Model: assignment default `kimi-k2.6`, not yet verified for this account.
Authenticated models observed: **pending**.
Live requests performed by this implementation: **0**.
Project key creation, balance check, curl protocol exercise, live text and JSON
results: **pending user setup**. No key was read or created.

Official Chat Completions and JSON mode documentation were checked on 2026-09-21.
K2.6 supports disabling thinking, used for the small token budget. Model availability
must still be checked with authentication. Documentation examples now also mention
other models; no silent model upgrade was made.

## Live evidence to add

After key setup and passing offline checks, run `labops-agent models --live`,
verify the model, then run `labops-agent smoke --live` once. Record model IDs,
non-secret outputs, usage, finish reasons, successes and attempts. Combined this
is four requests on success, leaving room for the assignment's two curl checks
within ten successful requests. Stop and diagnose failures rather than repeatedly
retrying. Do not paste keys or authorization headers into evidence.

## Learning notes for discussion

These are assistant-provided explanations, not the learner's reflection answers.

1. Key authenticates the account; base URL locates the service; model ID selects
   the available model. None is a business rule.
2. Configurable models allow capability/account changes without rewriting workflow logic.
3. Finish reason distinguishes a completed answer from truncation or an unexpected
   tool/refusal outcome; incomplete structured output cannot be accepted.
4. Valid JSON may have wrong types, unknown fields, or invented facts. Local schema
   validation checks structure, not truth about inventory.
5. Fakes make unit tests repeatable, offline, inexpensive, and independent of keys.
6. No automatic retry occurs here. Authentication, balance, and rate-limit errors
   require investigation. A later bounded retry policy could handle transient
   transport/server errors for non-mutating requests.
7. User errors contain safe categories/actions; development traces may contain
   sanitized request IDs and timing, never credentials or raw secret-bearing payloads.
8. Separating provider foundations from tools isolates protocol failures before
   introducing business state and authorization.

## Limitations

No live availability or compatibility claim until authenticated smoke evidence is
provided. Request budget across CLI invocations is tracked manually. Timeouts use
SDK per-operation limits, not a total process deadline. The international endpoint
is intentionally allowlisted and HTTP redirects disabled. Strict local validation
does not establish semantic correctness for arbitrary model extractions. The fixed
smoke example additionally checks its expected quantity, QC, and intent.

## Final offline results — 2026-09-21

- Initialized this separate repository on `main`; no commit or remote created.
- `uv sync --frozen --offline`: passed in the destination project.
- `uv run --frozen --offline pytest`: **48 passed in 1.87s**, exit 0.
- `.venv/bin/labops-agent doctor` without a key: expected safe `api_key` error.
- Same doctor command with a temporary fake diagnostic key: configuration printed
  with `api_key: present`, no key disclosure, and `network: not used`.
- `labops-agent chat hello` without `--live`: refused before configuration/provider
  access, as required.
- `git diff --check`: passed. Since files are untracked in the new repository,
  additionally checked all 24 non-ignored files for trailing whitespace: none.
- Checked all non-ignored files for key-shaped strings without printing matches:
  none found. This is a heuristic, not proof that arbitrary secrets cannot exist.
- `git check-ignore .env .env.local`: both ignored.
- Git status: all new project files untracked; `.env` is not created. Existing
  Step 0 evidence is included, and the backend working-tree status is unchanged.
- Zero live requests; authenticated `/models`, text and structured smoke results
  remain pending. Step 1 is not yet accepted.

## User-supplied live verification — 2026-09-21

This section supersedes the pending live-result entries above. These results were
pasted by the user from their terminal; the assistant did not make live requests
or inspect the API key.

- Offline doctor independently passed after user key setup: key present,
  international endpoint, model `kimi-k2.6`, limit 300, thinking disabled.
- First reported `models --live` attempt failed authentication. The user was
  advised to verify the international key and clear any stale exported value.
  The exact cause and corrective action were not established.
- Subsequent `models --live` succeeded and listed `kimi-k2.6`, `kimi-k2.7-code`,
  `kimi-k2.7-code-highspeed`, and `kimi-k3`. Retained `kimi-k2.6` because the
  assignment default is available and supports the configured bounded requests.
- `uv run labops-agent smoke --live` completed all three checks:
  1. Authenticated models listing succeeded.
  2. Text: “An API is a set of rules that lets different software applications
     talk to each other.” Model `kimi-k2.6`, finish reason `stop`; prompt 15,
     completion 20, total 35 tokens.
  3. Locally validated extraction: intent `find_material`, material query
     `control samples`, quantity 20, QC `passed`. Model `kimi-k2.6`, finish reason
     `stop`; prompt 109, completion 24, total 133 tokens.
- Smoke completions used 168 reported tokens total. No currency cost was reported.
- Visible conversation records show four successful requests (one standalone
  models call and three smoke calls), plus one authentication failure: five
  known attempts. The models output repeated in the final paste is treated as
  the previously supplied result, not evidence of a further invocation. This is
  a minimum observed count, not a provider-side account usage audit.
- No automatic retries were used. No further live checks are needed to repeat
  the already successful smoke behavior.

Technical runtime checks now pass: 48 offline tests and the user-supplied live
smoke. Formal milestone submission still needs learner reflection/review and any
required outside-Python curl exercise (not evidenced here). No Step 2 assignment
or implementation was added. No commit or push has been performed.

# Step 2 Evidence: Read-only Material Finder

Last updated: 2026-09-30.

## Current status

I have a read-only material finder with validated source settings, five source
reads, four model tools, a bounded coordinator, and an `ask --live` command.
My latest offline run passed **209 tests**. My bounded live scenario succeeded
with **two model responses and one source tool call**.

I still need order-state verification evidence and mentor acceptance. I have
not marked Step 2 accepted or implemented Step 3.

## Repository versions and contract review

I recorded these committed baselines:

- Agent: `01845c89cb769221d52dfb5da770cfa304c07ca0`.
- Source backend: `c96978c7da0a97942d0bb0b452b64f49b411c7a7`.
- Assignment reference: `d7f3d3362afdfa97a492345a6060db192278f61a`.

I used `git rev-parse HEAD` in both repositories. These hashes do not include
uncommitted work. My implementation changes remain uncommitted, and new
modules and tests are untracked at the latest status check.

I inspected the source routes and schemas for materials, locations, and users;
`src/main.py`; pagination and error helpers; authentication dependencies; role
permissions; and relevant material-service expressions. Comparing the reviewed
contract files with the reference commit showed whitespace changes only. I did
not review unrelated source changes as part of this milestone.

I confirmed:

- All five approved reads require an opaque bearer token.
- Viewer, staff, and admin can read materials and locations. Viewer also has
  some order-write permissions, so I enforce read-only scope in application code.
- Search supports keyword, type, source, QC status, availability, location,
  low-stock, archive, and pagination filters. Keyword length is limited to 255.
- Search excludes archived materials by default.
- Source pagination uses `items`, `page`, `size`, `total`, and `pages`, with
  page numbering from 1, default size 25, maximum size 100, and zero pages for
  empty results. My client limits page size to 10.
- Unreserved stock equals `quantity_available - quantity_reserved`.
- `availability_status=low_stock` requires positive unreserved stock;
  `low_stock=true` also includes stock at or below zero when below the threshold.
- A material supplies a nullable location ID; I need a location read for its name.
- QC status is current metadata, not evidence that QC work occurred.
- Errors use `error.code`, `error.message`, and optional details. I branch on
  status and code, not display wording, and preserve safe `X-Request-ID` metadata.

I reviewed the official [Tool Use](https://platform.kimi.ai/docs/api/tool-use)
and [Chat Completions](https://platform.kimi.ai/docs/api/chat) documentation.
I preserve call IDs, function names, JSON argument strings, finish reasons,
usage counts, and optional reasoning content. I retain the model's call message
before appending each matching `role="tool"` result.

## Implementation and file responsibilities

I separated configuration, HTTP access, tool dispatch, provider messages, and
coordination so each boundary can be tested independently.

| File or area | What I implemented |
|---|---|
| `src/lab_workflow_agent/config.py` | Separate source settings, secret token, exact local URL, bounded timeout |
| `src/lab_workflow_agent/source_models.py` | Material, user, location, page, error, and argument models |
| `src/lab_workflow_agent/source_client.py` | Five approved GET operations, safe errors, response checks, cleanup |
| `src/lab_workflow_agent/tools.py` | Fixed registry, generated schemas, validation, normalized results |
| `src/lab_workflow_agent/provider.py` | Tool-call types, message serialization, response validation |
| `src/lab_workflow_agent/coordinator.py` | Sequential bounded loop and source-backed final rendering |
| `src/lab_workflow_agent/cli.py` | Offline doctor, explicit live question command, counts, cleanup |
| `tests/` | Fake-provider, mock-transport, model, CLI, and setup tests |
| `.env.example`, `.gitignore`, `README.md` | Non-secret defaults, private-file exclusions, usage instructions |
| `scripts/configure_local_token.py` | Separate interactive local credential setup |

### Tool-to-endpoint mapping

| Tool | Source endpoint |
|---|---|
| `search_materials` | `GET /materials/search` |
| `get_material` | `GET /materials/{material_id}` |
| `list_locations` | `GET /locations` |
| `get_location` | `GET /locations/{location_id}` |

I expose `GET /users/me` only to application code, not as a fifth model tool.
I found no write operation in the agent's source-client path. Its public methods
construct routes; the private HTTP helper performs GET requests only.

### Configuration and safety controls

I accept only `http://127.0.0.1:8000`. I reject alternative hosts, ports, paths,
query strings, fragments, and embedded credentials. My timeout must be finite,
greater than zero, and at most 60 seconds. I disable redirects and retries.

I keep the source token in a secret type and attach it only to the source
client's authorization header. Doctor reports presence without printing it or
making requests. Moonshot-only commands do not load source settings.

I generate tool schemas from the same strict Pydantic models used locally.
I reject unknown tools, extra fields, malformed or non-object JSON, duplicate
keys, non-finite values, invalid IDs/types/enums, oversized filters, and argument
strings over 8192 characters before source access. Provider `strict=false`
remains intentional; local validation is mandatory. The live test verified one
schema path, not comprehensive provider strict-mode compatibility.

I fetch one page per call and preserve pagination metadata. Archived access
requires the explicit `--include-archived` flag. I never let model arguments or
source descriptions set that authorization policy.

### Coordinator and output

I enforce at most **four model responses**, **three calls per response**,
**six total tool executions**, and **ten records per page**. I validate the
whole batch before dispatch, execute sequentially, and reject repeated call IDs.

I require the model's final JSON to select IDs found in tool results. I render
facts from those records instead of accepting unsupported prose. My output
includes material IDs/codes, stock quantities, archive flags, retrieved location
names, read timestamps, and partial-page notices. This format supports factual
record answers, not arbitrary narrative or aggregate answers.

I require `--live` before provider or source access and validate both
configurations before constructing clients. I close clients on success, failure,
or Ctrl-C. I do not persist conversations, create order drafts, or write inventory.

## Offline verification

I recorded this test progression as functionality was added:

| Checkpoint | Result |
|---|---|
| Step 1 baseline: `uv run pytest` | 48 passed in 0.80s |
| Source configuration | 75 passed in 0.77s |
| First source read | 103 passed in 0.94s |
| All five source reads | 137 passed |
| Tool registry and dispatcher | 165 passed in 1.09s |
| Provider tool protocol | 183 passed in 1.01s |
| Coordinator and CLI | 202 passed in 0.95s |
| Latest regression, including setup helper | **209 passed in 1.15s** |

I used `.venv/bin/python -m pytest -q` for these incremental runs. When the
sandbox blocked uv's default cache, I also verified the suite using
`UV_CACHE_DIR=/private/tmp/lab-workflow-agent-uv-cache uv run --frozen --offline pytest -q`.
That run passed 202 tests before the setup-helper tests were added.

My fake tests cover successful parsing for all reads; missing tokens; invalid
URLs, IDs, filters, and pagination; redaction; HTTP 401/403/404/422/500; timeouts;
connection errors; redirects; malformed JSON; schema mismatches; mismatched
records; archive handling; and deterministic cleanup.

I also test call/result ID matching, malformed provider responses, empty or
unsupported final answers, every loop bound, invalid batches with zero source
calls, explicit live opt-in, and instruction-like source text treated as data.
The default suite uses no real credentials or services and blocks socket connections.

I ran `git diff --check` successfully and inspected `git status --short` and
`git diff --stat`. The diff statistic excludes untracked files, so I also list
the new modules and tests above. I ran the required pattern searches with
filename-only output to avoid displaying potential credentials. The `sk-`
match was the assignment's scan command. Endpoint/deployment terms occurred in
planning, assignments, evidence, and the negative provider-URL test.

I ran offline doctor checks for URL, timeout, and token presence. Token presence
only confirms configuration; it does not prove authentication succeeds.

## Private local setup

I added a separate interactive helper for my local account setup. It hides
password input, refuses visible-input fallback, performs one local login POST,
and saves the returned token in ignored `.env` without printing it. It preserves
other settings, applies owner-only permissions, and rejects unsafe destinations.

This helper is outside the read-only agent and tool registry. It is a setup
extension requested during development, not an approved model write capability.
I used local viewer registration and token refresh to prepare the live check.
Seven fake tests cover local routing, safe errors, no redirects/retries, preserved
settings, file permissions, and symlink refusal.

## Live scenario and failures

I recorded two unsuccessful attempts before the successful run:

1. I verified the local viewer and fixture, but the provider model-list request
   returned “Provider unavailable.” I recorded one provider attempt, zero
   successful requests, and no completion request or fixture transfer to Kimi.
   I did not complete an after-read or order-state comparison in that attempt.
2. My next attempt stopped at local authentication. I made zero provider
   requests. Token expiry was possible but not confirmed; the backend default
   lifetime is 60 minutes. I refreshed the token before continuing.

### Successful run — 2026-09-30

After refreshing the viewer token, I verified that the configured model appeared
in the authenticated model list and completed one approved fixture question:

> Read material 1 using get_material. How much unreserved stock does it have?

I used a temporary acceptance harness restricted to `get_material(1)` to keep
the external payload within the approved scope. The run exercised the real
provider adapter, coordinator, dispatcher, and source client. It did not launch
a live CLI subprocess; I tested CLI behavior offline.

| Observed field | Value |
|---|---|
| Material ID/code | 1 / `AGENT-MAT-001` |
| Name | Agent Workflow Control Sample |
| Available | 80 units |
| Reserved | 0 units |
| Unreserved | 80 units |
| Minimum quantity | 20 units |
| Availability / QC metadata | `available` / `passed` |
| Location ID / archived | 1 / false |
| Tool read time | `2026-09-30T19:41:06.889298+00:00` |

I recorded **two model responses**, **one source tool execution**, and **three
successful provider requests**, including model verification. There were no
retries. Across the documented attempts, I used **three of the six allowed
successful provider requests**.

I read the current user and the material before and after the question. Every
field retained by my `MaterialRead` model was unchanged. I did not compare
omitted source fields or order state. The absence of order-write tools does not
replace the required order-state evidence.

My answer included the source ID/code, exact stock facts, archive status, read
time, and a statement that QC metadata does not prove QC work occurred. I kept
credential values out of prompts, tool results, and this evidence.

## Reflection questions

1. **How do a schema, call, dispatcher, and source client differ?**
   I use the schema to define arguments, the call to request an operation, the
   dispatcher to validate it, and the client to perform the GET.
2. **Why validate locally even with provider strict mode?**
   I must enforce my own types, limits, and authorization rules.
3. **Why preserve the model's tool-call message?**
   I retain the request context needed to match each returned result.
4. **What does `tool_call_id` protect against?**
   I use it to detect mismatched, missing, duplicate, and orphaned results.
5. **Why are source descriptions untrusted data?**
   I cannot let stored text override my instructions or authorize actions.
6. **How does the loop stop?**
   I stop on a validated final answer, an error, or a response/tool limit.
7. **How does the answer demonstrate grounding?**
   I render retrieved facts with record IDs, timestamps, and pagination notices.
8. **Why forbid writes despite backend authorization?**
   I enforce a narrower read-only scope than the token's permissions may allow.

## Remaining work and acceptance

I still need to collect order-state verification evidence and obtain mentor
acceptance. My before/after material comparison covers only retained model fields,
and my successful live run used the service-level harness rather than the CLI.
I have not verified every tool or thinking configuration against the live provider.

I need the detailed Step 3 assignment before implementing its clarification and
order-draft workflow. I have not marked Step 2 accepted.

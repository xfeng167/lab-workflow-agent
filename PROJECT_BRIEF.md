# Project Brief: lab-workflow-agent

## 1. Project statement

Build a backend and command-line product that lets authenticated Lab Storage
users complete real material-request workflows through an LLM-guided
conversation.

The project is designed as a practical way to learn agentic workflow
engineering. It is not a classroom simulator and does not contain instructor,
grading, or training-mode product features. The product itself should be shaped
like a real operational system.

## 2. Learning objective

By completing the project, the learner should be able to explain and implement:

- The difference between an LLM response and a verified business fact.
- Structured model output and schema validation.
- Function or tool calling.
- A bounded agent loop with explicit exit conditions.
- The boundary between deterministic workflows and model-directed decisions.
- Human confirmation before state-changing actions.
- Durable workflow state that is separate from conversation history.
- Authentication, authorization, idempotency, retries, and stale-state handling.
- Tracing and outcome-based evaluation of an agentic workflow.
- When a single coordinator is sufficient and when specialization may be
  justified.

## 3. Product users

The product uses the source system's existing account roles.

### Viewer

A mixed requester role, which may represent a researcher, vendor, partner, or
internal user. A viewer can read materials and locations and manage eligible
owned requests.

### Staff

A viewer with additional catalogue, location, and operational-report access.
Staff cannot adjust inventory, review orders, read audit logs, or manage users.

### Admin

A staff user with inventory operations, material archive operations, review of
all orders, audit-log access, and user-role management.

Account role is an authorization level, not a fixed conversational persona. An
admin may still use the product as a requester.

## 4. Target product outcome

The first complete vertical workflow is request-to-fulfillment:

1. A user describes a material need in natural language.
2. The agent searches the source API and presents grounded candidates.
3. The agent asks only for information required to remove ambiguity.
4. The agent prepares a structured order draft.
5. The user reviews and confirms the exact action.
6. The agent refreshes relevant source state and submits the order.
7. An admin asks for pending work.
8. The agent previews the inventory impact of approval.
9. The admin confirms approval or rejection.
10. The agent executes and verifies the transition.
11. The admin later confirms fulfillment.
12. The agent verifies the final order, inventory, and audit state.

The workflow is complete only when the source system confirms the final state.
The model saying that an operation succeeded is never sufficient evidence.

## 5. System boundary

### lab-workflow-agent owns

- LLM provider configuration and client behavior.
- CLI and future agent-backend API adapters.
- Conversation handling.
- Intent and structured-output validation.
- Tool descriptions and dispatch.
- Workflow orchestration.
- Drafts and action previews.
- Human-confirmation state.
- Durable workflow cases.
- Agent traces, evaluations, and user-safe error explanations.

### lab-storage-management owns

- User registration, login, logout, and bearer tokens.
- Viewer, staff, and admin authorization.
- Material and location records.
- Order state transitions.
- Inventory validation, reservation, release, and deduction.
- Database transactions, locking, and constraints.
- Business error codes.
- Inventory and order audit history.

### Prohibited boundary crossings

The agent project must not:

- Connect directly to the Lab Storage MySQL database.
- duplicate inventory or order business rules as an alternative source of truth;
- use an all-powerful service account to impersonate users;
- treat prompts as an authorization mechanism;
- claim success without reading the resulting source-system state;
- expose Moonshot credentials to a browser or frontend;
- run learner exercises against Railway or production data.

## 6. Agent design baseline

Begin with one user-facing coordinator. The coordinator may use narrowly scoped
tools but remains subject to application validation and source-system
authorization.

Every state-changing operation follows this contract:

1. Understand the goal.
2. Collect missing required information.
3. Read current source-system facts.
4. Produce a structured action preview.
5. Wait for explicit confirmation of that exact action.
6. Refresh facts that can become stale.
7. Execute the action once.
8. Read the resulting state.
9. Return a traceable receipt or an honest failure.

An approval applies only to the displayed action and version of its relevant
facts. A materially changed order or inventory state requires a new preview and
confirmation.

## 7. Runtime and environment baseline

### Agent project

- Language: Python 3.11 or newer.
- Environment and dependency workflow: `uv`.
- User interface in this repository: CLI.
- Later integration surface: a thin backend HTTP API over the same application
  service used by the CLI.
- Early agent implementation: an explicit, small tool-calling loop rather than
  a high-level agent framework.

### LLM provider

- Provider: Kimi international API platform.
- Console: <https://platform.kimi.ai/>.
- Base URL: `https://api.moonshot.ai/v1`.
- Protocol: OpenAI-compatible Chat Completions.
- Initial configured model: `kimi-k2.6`.
- Actual model availability must be checked through `/v1/models`.
- Credential environment variable: `MOONSHOT_API_KEY`.
- Base URL environment variable: `MOONSHOT_BASE_URL`.
- Model environment variable: `MOONSHOT_MODEL`.

Official references, verified on 2026-09-14:

- [Kimi API overview](https://platform.kimi.ai/docs/api/overview)
- [Kimi international quickstart](https://platform.kimi.ai/docs/api/quickstart)
- [List models](https://platform.kimi.ai/docs/api/list-models)
- [Structured output and response format](https://platform.kimi.ai/docs/api/chat)
- [Tool use](https://platform.kimi.ai/docs/api/tool-use)

### Source business environment

- Lab Storage API: local process, normally `http://127.0.0.1:8000`.
- Database: Docker MySQL from the source repository's development Compose file.
- Development schema: `lab_storage_db`.
- Automated source-system tests: dedicated `lab_storage_test_db` only.
- Production and Railway environments are out of scope.

## 8. Product scope

### Required by the end of the roadmap

- Authenticated CLI sessions for viewer and admin users.
- Grounded material search and detail answers.
- Required-field clarification and candidate disambiguation.
- Editable order drafts.
- Explicit confirmation before writes.
- Verified order submission.
- Durable workflow cases and resume behavior.
- Admin pending-order review, approval, rejection, and fulfillment.
- Honest handling of authorization, stock, state, provider, and network failures.
- Protection against duplicate side effects.
- Development traces and repeatable evaluations.
- A thin backend API contract suitable for integration by the separately owned
  frontend.

### Explicitly out of scope for the initial roadmap

- A web frontend in this repository.
- Direct database access from the agent.
- QC-run and shipment workflows that the source API does not yet implement.
- File retrieval or a vector database.
- General-purpose RAG.
- Voice or multimodal input.
- Autonomous background inventory mutation.
- Multi-agent orchestration without evidence that the single coordinator fails.
- Fine-tuning.
- Production deployment.

## 9. Testing strategy

### Unit tests

- Never call the live Kimi API.
- Never require the Lab Storage API.
- Use fake provider responses and fake tools.
- Cover workflow choices, validation, confirmation, and stopping behavior.

### Lab integration tests

- Call the local Lab Storage API.
- Use Docker MySQL.
- Use a resettable, non-production dataset.
- Do not call the live Kimi API.

### Provider smoke tests

- Call the live Kimi API only when explicitly enabled.
- Do not perform Lab Storage writes.
- Use short prompts and bounded output.
- Stop on authentication, balance, or rate-limit problems.

### End-to-end agent tests

- Begin only after deterministic and fake-provider tests pass.
- Use the live Kimi API plus the local Lab Storage API.
- Keep the number of scenarios small and deliberate.
- Verify final orders, inventory quantities, reservations, and audit records.

## 10. Delivery discipline

For every milestone, the learner provides:

- A concise implementation plan before coding.
- Scoped code or documentation changes.
- Automated tests appropriate to the milestone.
- Exact verification commands and their results.
- A short English evidence report.
- Known limitations and unanswered questions.
- One focused commit after review readiness.

The mentor explains goals and reasoning, reviews evidence, and helps diagnose
errors. The mentor does not implement the milestone for the learner.

## 11. Final definition of done

The project is complete when all of the following are demonstrated:

- A viewer can describe a material need and receive API-grounded results.
- Ambiguous or incomplete requests cause clarification rather than guessing.
- A viewer can review and confirm an order draft, and exactly one order is
  created.
- An admin can review, approve or reject, and fulfill eligible orders after
  seeing the exact inventory impact.
- The source API remains the final permission and transaction boundary.
- Rejected, stale, duplicated, unauthorized, and failed actions do not produce
  hidden or inconsistent side effects.
- A completed workflow can be traced from user goal through tools and
  confirmation to verified business state.
- Unit tests run without network access or a real provider key.
- Live-provider and full end-to-end checks are explicit and bounded.
- CLI and backend API adapters share one workflow implementation.
- The learner can justify whether the final design needs an agent framework or
  multiple agents.

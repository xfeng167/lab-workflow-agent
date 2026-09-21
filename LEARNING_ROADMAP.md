# Learning Roadmap

## Purpose

This roadmap builds one production-shaped agentic workflow through small,
review-gated vertical increments. Each milestone must leave the project
working, tested, and understandable.

Only Milestones 0 and 1 currently have implementation assignments. Milestone 2
must not be authored or started until Milestone 1 has been reviewed and
accepted.

## Roadmap

| Step | Milestone | Product increment | Primary learning outcome | Assignment |
| --- | --- | --- | --- | --- |
| 0 | Current System Contract | Verified source-system baseline | Business state, RBAC, transactions, evidence | Ready |
| 1 | Moonshot API Foundations | Minimal validated LLM CLI | API keys, SDK calls, structured output, fakes | Ready |
| 2 | Read-only Material Finder | Grounded material questions | Tool schemas, dispatch, tool-result grounding | Locked |
| 3 | Clarification and Order Draft | Editable request draft | Multi-turn collection, ambiguity, draft state | Locked |
| 4 | Confirmed Order Submission | First real write action | Approval boundary, refresh, execute, verify | Locked |
| 5 | Durable Workflow Case | Resumable work | Conversation vs. workflow state, persistence | Locked |
| 6 | Admin Review and Fulfillment | Cross-role order lifecycle | RBAC, approval impact, asynchronous handoff | Locked |
| 7 | Failure, Safety, and Recovery | Trustworthy exception paths | Idempotency, stale state, retries, injection | Locked |
| 8 | Tracing and Evaluations | Measurable agent behavior | Traces, fake scenarios, outcome evaluation | Locked |
| 9 | Production CLI and Backend API | Frontend-ready backend | Adapters, stable contract, shared core logic | Locked |
| 10 | Architecture Review | Evidence-based next design | Framework and multi-agent decision | Locked |

## Step 0: Current System Contract

### Product increment

A verified description of the existing Lab Storage system and a reproducible
local workflow baseline.

### Learning outcomes

- Trace an HTTP request through the source system.
- Explain roles and permissions.
- Explain the order state machine and inventory side effects.
- Distinguish API documentation from runtime evidence.
- Verify outcomes through source-system reads and audit records.

### Exit gate

The learner can manually demonstrate the normal request-to-fulfillment flow and
the required authorization, stock, and cancellation failure paths without an
LLM.

## Step 1: Moonshot API Foundations

### Product increment

A minimal CLI that calls the international Kimi API through one configuration
and provider boundary, plus deterministic tests that do not use the live API.

### Learning outcomes

- Create and protect a provider API key.
- Understand base URL, model ID, messages, response, usage, and finish reason.
- Use OpenAI-compatible Chat Completions through the SDK.
- Request structured output and validate it locally.
- Separate live smoke tests from unit tests.
- Normalize provider failures without leaking secrets.

### Exit gate

The CLI can validate configuration, list available models, perform one bounded
chat request, and return a locally validated structured result. Unit tests pass
without network access or `MOONSHOT_API_KEY`.

## Step 2: Read-only Material Finder

### Planned product increment

An authenticated coordinator that answers material and location questions from
the local Lab Storage API using read-only tools.

### Planned learning outcomes

- Function and tool schemas.
- Model-selected tool calls.
- Deterministic argument validation and dispatch.
- Tool-result messages.
- Grounded final answers and bounded agent loops.

### Unlock condition

Step 1 must pass mentor review. The detailed Step 2 assignment will be written
only after that review.

## Step 3: Clarification and Order Draft

Collect material, quantity, and notes over multiple turns. Resolve missing or
ambiguous information and create an editable structured draft without any
business write.

## Step 4: Confirmed Order Submission

Add the first state-changing tool. Display the exact action, wait for explicit
confirmation, refresh material state, submit once, and verify the resulting
order.

## Step 5: Durable Workflow Case

Separate messages from workflow state. Persist intent, collected fields, draft,
pending action, confirmation, entity IDs, and final outcome so interrupted work
can resume safely.

## Step 6: Admin Review and Fulfillment

Add pending-order review, approval, rejection, and fulfillment. Demonstrate a
viewer-to-admin workflow while preserving each user's actual authorization.

## Step 7: Failure, Safety, and Recovery

Handle missing resources, insufficient stock, stale confirmations, duplicate
requests, timeouts, ambiguous outcomes, invalid transitions, permission
failures, prompt injection, and malformed tool results.

## Step 8: Tracing and Evaluations

Trace goals, model decisions, tool calls, confirmations, errors, and verified
outcomes. Build deterministic scenario tests and a small, explicit set of live
provider checks.

## Step 9: Production CLI and Backend API

Complete the CLI experience and expose the same application service through a
thin backend HTTP API for the separately owned Lab Storage frontend. Do not
duplicate workflow logic between adapters.

## Step 10: Architecture Review

Use observed failures and evaluation evidence to decide whether a high-level
agent framework, specialist agents, or handoffs would improve the product.
Avoid an architecture change whose only justification is demonstrating a new
technology.

## Milestone execution protocol

For every step:

1. Read the milestone assignment completely.
2. Restate the goal and scope in your own words.
3. Submit a short plan before editing.
4. Implement only the current milestone.
5. Run required checks.
6. Write the evidence report without secrets.
7. Request mentor review.
8. Address review findings.
9. Commit the accepted, scoped result.
10. Begin the next step only after its unlock condition is satisfied.

## Required evidence pack

Every milestone evidence report must include:

- Commit or working-tree reference.
- Files changed.
- Commands run.
- Concise command results.
- Manual scenarios performed.
- Expected and observed outcomes.
- Known limitations.
- Questions or decisions needed for the next milestone.

Never include passwords, bearer tokens, API keys, raw authorization headers, or
unredacted secret-bearing configuration.

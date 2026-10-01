# Step 4 evidence: confirmed order submission

## Status and implementation reference

I implemented against Step 3 commit `abbb374`. The Step 4 implementation is in the commit containing this report.
I completed the offline implementation and tests. I have not performed the real
acceptance write or recorded mentor acceptance. I did not begin Step 5.

I rechecked the local source `src/order/schemas.py`, `router.py`, and `service.py`.
Creation accepts material ID, integer quantity, and optional trimmed notes. It
locks the material, rejects archive or insufficient stock, inserts one order,
and commits. It does not reserve stock or create an inventory audit entry.
The source has no creation idempotency key. I added no backend changes.

## Files changed

- `src/lab_workflow_agent/order_models.py`: strict canonical create payload and
  validated order read schema.
- `src/lab_workflow_agent/source_client.py`: narrow order list/detail reads and
  one-attempt `POST /orders`, with deterministic versus ambiguous error handling.
- `src/lab_workflow_agent/submission.py`: preview, confirmation, fresh checks,
  bounded baseline, one-time execution, verification, and reconciliation.
- `src/lab_workflow_agent/cli.py`: separate `order --live` interaction.
- `tests/test_submission.py` and `tests/test_order_client.py`: offline tests.
- `README.md` and this report: usage, limits, and evidence.

I left the ordinary four-tool model registry unchanged. Only the deterministic
submission flow calls order creation. The existing `draft` command remains
read-only.

## State and confirmation design

I keep transitions in `TRANSITIONS`: ready draft → previewed → confirmed →
executing → succeeded, failed, or needs_reconciliation. Edits and failed fresh
checks move pending actions to invalidated. Reconciliation may reach succeeded,
but never returns to confirmed. After one POST, the session cannot make another.

I bind a random 192-bit capability to canonical payload, draft revision, user
ID/name/role, material snapshot, and preview read time. I mark it displayed only
after the output callback succeeds. I accept only `confirm <current-preview-id>`
through the deterministic CLI route; it never becomes a model tool or prompt.
I retain used capabilities in memory so pasted old capabilities cannot enter the
provider through subsequent messages. Receipts use a separate non-secret preview
reference rather than the capability.

My preview displays the method/path, all canonical draft fields, stock and
metadata timestamps, expected submitted status and zero reservation, warning,
exact confirmation command, and cancel/edit alternatives. I normalize note
whitespace and serialize payload keys consistently before execution.

Before sending, I read a complete material-filtered order baseline, including
archived records, within ten pages of ten records. I then re-read user and
material. Identity, role, code, name, unit, QC, location, archive, quantities,
source update timestamp, payload, and revision changes invalidate confirmation.
A changed preview requires a new explicit command.

I consume confirmation under a lock before sending one POST with a random
correlation request ID. There are no HTTP retries or redirects. I verify a claimed
success by reading the order and material. A verification read failure is an
ambiguous outcome, even when its HTTP status is 404; it does not prove the create
failed. I preserve known IDs and the request ID in the result.

I reconcile ambiguous outcomes using new IDs, detailed candidate reads, payload,
requester, status, reservation, and creation timestamps. A candidate without a
usable timestamp prevents claiming a unique reconciled success. Local naive
source timestamps are treated as UTC with two seconds of precision tolerance.
One verified match can yield a receipt explicitly marked reconciliation, with a
warning that this is not an idempotency guarantee. Zero/multiple matches or
incomplete reads remain unresolved; I never resend automatically.

## Offline verification

I ran `.venv/bin/python -m pytest -q`: **357 passed in 1.24s**.
The suite blocks socket connections and uses fakes; it creates no real orders.
The final verification also used `uv run --frozen --offline pytest -q` with a
local temporary uv cache. Offline doctor passed configuration validation; it
reports token presence, not token validity. `git diff --check` passed. The tracked
secret-pattern scan found only existing assignment/evidence references; scanning
source, tests, README, and evidence for the actual configured credentials found
no matches. I inspected the source-client diff: `POST /orders` is the only new
source write. The tool registry has no diff. Before staging, `git diff --stat` showed only the three modified tracked files;
the commit includes all eight files listed above.
I cover:

- Ready preview, canonical payload, display-before-confirmation, wrong/missing/
  stale/consumed capabilities, generic agreement, and model-generated confirmation.
- Material, quantity, notes, reset, and abandon edits; source identity, archive,
  stock, QC, location, unit, code/name, and timestamp changes.
- Repeated and concurrent confirmation with exactly one POST attempt.
- HTTP 401/403/404/409/422, unknown errors, redirects, timeout, connection loss,
  malformed response, schema failure, and post-create verification failures.
- Wrong requester/material/quantity/notes/status/reservation/archive fields.
- Unique-match reconciliation, zero/multiple matches, old/missing timestamps,
  incomplete pagination, and retained ambiguity after failed verification.
- Complete multi-page baseline, baseline bound before sending, observed stock
  changes without unsupported causation, interruption, CLI cleanup, and redaction.
- Absence of other write methods and order actions in the model tool registry.

Write-path tests assert the exact fake POST count: zero before authorization or
after invalidation, and at most one after confirmed execution.

## Live preflight and pending acceptance

I attempted a read-only local preflight on 2026-09-30. The saved token was rejected
at `GET /users/me`, before material or order-list reads. I stopped immediately.
This used **one attempted source read, zero model requests, and zero POSTs**.
After the private token refresh, I verified user 6 (`shirley`, viewer), material
1 (`AGENT-MAT-001`, Agent Workflow Control Sample), and the complete matching
order list. The material was active, QC passed, location 1, unit `units`, with
80 available, zero reserved, and 80 unreserved. Its source update timestamp was
`2026-09-18T04:30:09`. The matching order list was empty (`total=0`, IDs `[]`).
This successful preflight used three source reads, zero provider requests, and
zero POSTs. Including the rejected-token preflight, four reads were attempted.
The proposed action remains quantity 1 with notes none; live submission awaits
the exact manual confirmation in the private terminal.

I have no Step 4 live order ID, receipt, or live confirmation-reuse proof yet.
The Step 3 fixture was material 1 (`AGENT-MAT-001`), but I must revalidate its
current facts before a write.

The concrete proposed acceptance action is one local order for material 1,
quantity 1, notes none, under the authenticated local user. I will not create it
until the owner reviews the current canonical preview and enters its exact
confirmation command manually. If the source fixture or identity differs from
what the owner approves, I will stop.

Pending manual sequence:

```bash
uv run python scripts/configure_local_token.py
uv run labops-agent order "/material 1" --live
```

```text
/quantity 1
/preview
confirm <PRIVATE_CURRENT_PREVIEW_ID>
confirm <SAME_PRIVATE_PREVIEW_ID>
/show
/exit
```

I must replace the placeholders only in the private terminal. I will retain a
redacted preview and confirmation, baseline order IDs, source request ID, returned
and re-read order ID/status, before/after material quantities, zero reservation,
verification time, call counts, and the rejected reuse result. I will not repeat
the acceptance write for presentation quality. If the outcome is ambiguous, I
will review the source instead of starting another write.

I will rerun offline tests after the one real acceptance scenario. No cleanup is
needed yet because no real order has been created. Any eventual cleanup belongs
to the trusted source UI/API; I did not add cancellation here.

## Limitations

I cannot restore confirmation, baselines, or outcome knowledge after process
termination. The one-attempt guard is per session/process, not a durable
idempotency guarantee. A concurrent matching order can make reconciliation
uncertain. My read bounds stop large or incomplete baselines. I keep all new
workflow state in memory, and the backend remains authoritative for permission
and locked stock checks. The live acceptance and mentor review remain pending.

## Reflection

1. **Why is agreement insufficient?** It does not bind authorization to one exact,
   displayed action and revision.
2. **Which facts are bound?** I bind payload, revision, identity, displayed material
   facts, and read time so changes require a new decision.
3. **Why refresh after confirmation?** Mutable identity and inventory facts may
   have changed since the preview.
4. **Why is the backend authoritative?** Its transaction locks and validates the
   actual source state at execution time.
5. **How do I prevent double submission?** I consume confirmation under a lock
   before POST and prohibit further writes in that session.
6. **Why is request ID not idempotency?** The backend uses it for correlation and
   does not deduplicate order creation with it.
7. **Why is an outcome ambiguous?** A request can commit before its response is
   lost; retrying could create a duplicate.
8. **Why verify a 201?** I must confirm the source order matches the authorization
   and report the observed material state.
9. **What is missing without durability?** I lose attempt history and reconciliation
   state at exit, so a new process cannot safely resume the old confirmation.

## Push verification

On 2026-10-01, I reran the offline suite before committing: **357 passed in 1.32s**.
Whitespace validation passed, and the eight files contained no configured API key
or source token. Manual live acceptance remains unverified.

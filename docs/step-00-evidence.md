# Milestone 0 evidence

## Current status

I used Step 0 to learn how the existing Lab Storage API handles orders, stock,
and permissions. The recorded normal workflow and three exception checks have
supporting HTTP evidence. The [Step 0 review update](step-00-review-update.md)
records technical foundation acceptance on 2026-09-21, including an assistant-run
backend test result of **82 passed in 25.35s**.

This report was updated against the repositories on 2026-09-21. The API events
below were recorded on September 17 local time and September 18 UTC; they were
not rerun during this documentation update. 

## Environment and provenance

- Backend: `/Users/snowflake2.0/Desktop/lab-storage-management`.
- Base commit: `c96978c7da0a97942d0bb0b452b64f49b411c7a7`.
- API: `http://127.0.0.1:8000`; MySQL at localhost:3306, `lab_storage_db`.
- Dedicated test target instructed: localhost:3306, `lab_storage_test_db`.
- Docker development containers: `lab-storage-mysql-dev` (mysql:8.0) and
  `lab-storage-adminer-dev`; no volumes were deleted.
- Readiness: `200`, database `ok`, migration `20260812_0004`.
- I was instructed to launch the API from this checkout. Exact process
  provenance has not independently been confirmed.
- Final documents are in
  `/Users/snowflake2.0/Desktop/lab-workflow-agent/docs`, outside the backend.
  This is now a separate Git repository on `main`, tracking `origin/main` at
  `https://github.com/xfeng167/lab_workflow_agent`. The reviewed commit is `b8a7ac5`.

## Checks and commands

| Check | Result and evidence source |
| --- | --- |
| `uv sync --extra dev --frozen` | Assistant run, exit 0, 33 packages checked |
| Development Docker Compose status | Assistant observed both containers running |
| `uv run alembic upgrade head` on documented local development DB | Assistant run, exit 0, already current |
| `/health`, `/health/ready`, `/docs`, `/openapi.json` | Assistant initially observed 200; I subsequently confirmed readiness |
| Backend tests | I originally reported 82 passed in 24.22s. The later review records an assistant-run dedicated-test-database check: 82 passed in 25.35s. No backend tests rerun for this update. |
| Unauthenticated `/materials` | Assistant observed 401 `AUTH_HEADER_MISSING` |
| Verification script | I executed; assistant inspected saved HTTP responses and checked audit snapshots |
| Backend `git diff --check` | Assistant rerun, exit 0 |
| Original destination checks | Whitespace, JSON, and relative-link checks passed before Git initialization; Git is now configured and the existing code has been pushed. |

The local HTTP verifier was invoked with:

```bash
.venv/bin/python /private/tmp/lab-workflow-agent-step00-20260917/verify_exceptions.py
```

Passwords were prompted without echo. Login/logout payloads and bearer headers
are excluded from its output evidence. No direct database access is used by this
verifier. Both verification sessions were logged out by the script.

## Fixture IDs and actual outcomes

| Record | ID | Result |
| --- | --- | --- |
| Admin `agent_admin` | 3 | `/users/me` confirmed admin |
| Viewer `agent_viewer_step00` | 4 | `/users/me` confirmed viewer |
| Agent Training Freezer | 1 | I reported 201; material references location 1 |
| Material `AGENT-MAT-001` | 1 | Final available 80, reserved 0, QC passed, availability available |
| Normal request for 20 | 1 | Fulfilled; order reservation 0 |
| Viewer-denial request for 1 | 2 | Submitted; order reservation 0; intentionally left as evidence |
| Cancellation request for 10 | 3 | Canceled by owner; order reservation 0 |

### Normal flow

I created the fixture, searched/read it, submitted order 1, approved it,
and fulfilled it through Swagger. Screenshots show material 1 at 100/0 before
approval, 100/20 after approval, and order 1 fulfilled with reservation 0.
I reported submitted status for order 1; the initial search had no captured response. I later supplied a search result
for `Agent Workflow`: total 1, material 1, stock 80/0, QC passed, not archived.
The pasted response did not include an HTTP status. The saved verifier subsequently read the
fulfilled order, final 80/0 material state, and both original inventory audits.

| Stage | Material available | Material reserved | Order reservation |
| --- | --- | --- | --- |
| Before approval / submitted | 100 | 0 | 0 |
| Approved order 1 | 100 | 20 | 20 |
| Fulfilled order 1 | 80 | 0 | 0 |

### Exception checks

1. Viewer 4 created order 2 for one unit. Viewer approval returned
   **403 `PERMISSION_DENIED`**. Full before/after order and material responses
   and audit lists matched: submitted, stock 80/0, no audit mutation.
2. Viewer requested 999999 units. Submission returned
   **409 `ORDER_STOCK_INSUFFICIENT`**. Filtered order total remained 2,
   order-list contents matched, and material/audits remained unchanged.
3. Viewer created order 3 for 10 units. Admin approval returned approved with
   reservation 10 and material 80/10. Owner cancellation returned canceled with
   reservation 0 and material 80/0. Audit actor and both snapshots matched.

### Audit chain

All rows belong to material 1. Values below are available/reserved. Order IDs
are associated through the audit reason text.

| Audit ID | Order | Actor ID | Operation | Before → after | API timestamp |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 3 | `order_reservation_created` | 100/0 → 100/20 | 2026-09-18T04:01:52 |
| 2 | 1 | 3 | `order_fulfilled` | 100/20 → 80/0 | 2026-09-18T04:26:05 |
| 3 | 3 | 3 | `order_reservation_created` | 80/0 → 80/10 | 2026-09-18T04:30:09 |
| 4 | 3 | 4 | `order_reservation_released` | 80/10 → 80/0 | 2026-09-18T04:30:09 |

Audit 2 contains the literal outcome note `string`, apparently left from the
Swagger example. Its state transition and inventory snapshots are correct;
retain the recorded audit instead of rewriting history.

Full credential-free request/response evidence:
[Successful verification](evidence/exception-evidence-20260918T043009165947Z.json).

## Failures, recovery, and discrepancies

- A later readiness probe found the API stopped; I restarted it and
  reported readiness success.
- Bootstrap returned `admin_exists`. The owner explicitly requested admin
  deletion/recreation. Checks found old local admin `tongtong` (id 1) had no
  order, archive, inventory-audit, or token references. One transaction replaced
  it with admin 3. No other records were deleted. **This direct-database account
  recovery is an owner-authorized exception to the milestone scope. The later
  technical review acknowledges it as a setup exception.** It is not API workflow evidence.
- Initial viewer registration returned `409 USER_IDENTITY_CONFLICT`; a distinct
  username/email produced viewer 4 successfully.
- Browser automation lost access to the authorized tab. Remaining exception
  checks were completed using an HTTP script I ran, not browser automation.
- The first verifier run stopped at material 100/20 instead of expected 80/0.
  It created no orders. I then completed fulfillment; the later run
  passed all checks. The earlier claim that all normal-flow checks were verified
  was premature and has been replaced by actual state/audit evidence.
- A screenshot showed `409 ORDER_STATUS_CONFLICT`, followed by a fulfilled order
  read. The exact rejected action was not established; do not count this as a
  formally verified duplicate-fulfillment test.
- README says rejection/cancellation releases reservations, but rejection only
  accepts submitted orders. Approved reservations are released by cancellation.
- Null `error.details` is omitted by the serializer, despite a README example
  showing null. Order archive exists but is omitted from README API tables.
- Staff may set initial stock at material creation and edit location through
  metadata; reports expose broader activity than owner-scoped order reads.
- Some of my screenshots exposed credentials. They are not included in these
  deliverables. I later confirmed changing those passwords. This was my confirmation,
  not an independent check of the passwords.

## Source and workspace checks

Required routes, schemas, services, permission constants, migrations, and
relevant tests were reviewed. Detailed source mapping and invariants are in
[current system contract](current-system-contract.md).

Backend status at the original verification (historical):

```text
 M src/audit/router.py
 M src/main.py
 M src/material/schemas.py
 M src/order/router.py
 M src/order/service.py
?? Xuetong_Feng_Pharma_Software_Engineer_Resume.docx
?? pharma_sde_resume.tex
```

Tracked changes are seven blank-line deletions across five files. Four files
were already modified at the initial inspection; `src/main.py` changed during
my session. The assistant introduced no backend source edits. Existing
unrelated files remain untouched. Do not include them in the milestone submission.

```text
 src/audit/router.py     | 1 -
 src/main.py             | 1 -
 src/material/schemas.py | 2 --
 src/order/router.py     | 2 --
 src/order/service.py    | 1 -
 5 files changed, 7 deletions(-)
```

## Reflection draft

1. **Why use HTTP instead of changing the database?** I should use the API because
   it checks who I am, what I can do, and whether the change is allowed. A direct
   database edit could skip those checks and leave stock or audit records wrong.
2. **When is stock actually reserved?** Submitting an order checks stock, but
   approval checks it again and reserves it. Stock can change between those steps.
3. **What do available and reserved mean here?** In this API, available includes
   reserved stock. If available is 100 and reserved is 20, only 80 can be reserved
   for another order. Fulfillment reduces available and removes the reservation.
4. **Which rules belong in code?** Permissions, order states, quantities, stock
   checks, and audit records belong in the backend. A model cannot override them.
5. **Why check more than a successful response?** I could send the wrong quantity
   and still get success. I need to read the order, stock, and audit records to
   see whether the intended change happened.
6. **What can change after I read it?** Stock, order status, material details,
   and permissions can change. I should read current information and let the
   backend check the action when it runs.

## Current repository review and remaining work

- The backend still points to `c96978c7da0a97942d0bb0b452b64f49b411c7a7`.
  Its current status shows the same five source files modified and the two
  unrelated resume files added in the index. The historical status above is
  retained as the original snapshot, not the current staging state.
- The separate agent repository contains the contract, state-machine notes,
  this report, the review update, and saved HTTP evidence. Its existing commits
  have been pushed to GitHub. This documentation update is not yet committed.
- The original temporary verifier script is not included, so the saved JSON
  is the evidence available here, not a packaged replay tool.
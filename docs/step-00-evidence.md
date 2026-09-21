# Milestone 0 evidence

> Updated review: see [Step 0 review update](step-00-review-update.md) for the
> verified 82-test run, password-change confirmation, search result, and technical acceptance.
> The dated report below is retained as historical evidence.

## Current status

The normal order workflow and all three required exception checks have supporting
HTTP evidence. Backend tests were reported by the learner as **82 passed in
24.22s**. Document placement and equivalent destination checks are complete. Mentor
acceptance remains pending. This report does not claim mentor acceptance.

Reviewed on 2026-09-17 America/Los_Angeles; captured API events extend into
2026-09-18 UTC. Earlier incomplete draft entries are superseded by this report.

## Environment and provenance

- Backend: `/Users/snowflake2.0/Desktop/lab-storage-management`.
- Base commit: `c96978c7da0a97942d0bb0b452b64f49b411c7a7`.
- API: `http://127.0.0.1:8000`; MySQL at localhost:3306, `lab_storage_db`.
- Dedicated test target instructed: localhost:3306, `lab_storage_test_db`.
- Docker development containers: `lab-storage-mysql-dev` (mysql:8.0) and
  `lab-storage-adminer-dev`; no volumes were deleted.
- Readiness: `200`, database `ok`, migration `20260812_0004`.
- The learner was instructed to launch the API from this checkout. Exact process
  provenance has not independently been confirmed.
- Final documents are in
  `/Users/snowflake2.0/Desktop/lab-workflow-agent/docs`, outside the backend.
  This folder has not been initialized as a Git repository.

## Checks and commands

| Check | Result and evidence source |
| --- | --- |
| `uv sync --extra dev --frozen` | Assistant run, exit 0, 33 packages checked |
| Development Docker Compose status | Assistant observed both containers running |
| `uv run alembic upgrade head` on documented local development DB | Assistant run, exit 0, already current |
| `/health`, `/health/ready`, `/docs`, `/openapi.json` | Assistant initially observed 200; learner subsequently confirmed readiness |
| `uv run pytest` | Learner reported 82 passed in 24.22s; raw test output not independently captured |
| Unauthenticated `/materials` | Assistant observed 401 `AUTH_HEADER_MISSING` |
| Verification script | Learner executed; assistant inspected saved HTTP responses and checked audit snapshots |
| Backend `git diff --check` | Assistant rerun, exit 0 |
| Destination checks | No Git repository initialized; equivalent whitespace, JSON, and relative-link checks passed |

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
| Agent Training Freezer | 1 | Learner reported 201; material references location 1 |
| Material `AGENT-MAT-001` | 1 | Final available 80, reserved 0, QC passed, availability available |
| Normal request for 20 | 1 | Fulfilled; order reservation 0 |
| Viewer-denial request for 1 | 2 | Submitted; order reservation 0; intentionally left as evidence |
| Cancellation request for 10 | 3 | Canceled by owner; order reservation 0 |

### Normal flow

The learner created the fixture, searched/read it, submitted order 1, approved it,
and fulfilled it through Swagger. Screenshots show material 1 at 100/0 before
approval, 100/20 after approval, and order 1 fulfilled with reservation 0.
The learner reported submitted status for order 1; search success was reported
without a captured search response. The saved verifier subsequently read the
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

- Initial GitHub instructions were inaccessible; resolved by the user providing
  the milestone file locally.
- A later readiness probe found the API stopped; the learner restarted it and
  reported readiness success.
- Bootstrap returned `admin_exists`. The owner explicitly requested admin
  deletion/recreation. Checks found old local admin `tongtong` (id 1) had no
  order, archive, inventory-audit, or token references. One transaction replaced
  it with admin 3. No other records were deleted. **This direct-database account
  recovery is an owner-authorized exception to the milestone scope and needs
  mentor acknowledgment.** It is not API workflow evidence.
- Initial viewer registration returned `409 USER_IDENTITY_CONFLICT`; a distinct
  username/email produced viewer 4 successfully.
- Browser automation lost access to the authorized tab. Remaining exception
  checks were completed using a learner-run HTTP script, not browser automation.
- The first verifier run stopped at material 100/20 instead of expected 80/0.
  It created no orders. The learner then completed fulfillment; the later run
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
- Some learner screenshots exposed credentials. They are not included in these
  deliverables. Password rotation was advised; completion has not been verified.

## Source and workspace checks

Required routes, schemas, services, permission constants, migrations, and
relevant tests were reviewed. Detailed source mapping and invariants are in
[current system contract](current-system-contract.md).

Final backend status:

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
the learner session. The assistant introduced no backend source edits. Existing
unrelated files remain untouched. Do not include them in the milestone submission.

```text
 src/audit/router.py     | 1 -
 src/main.py             | 1 -
 src/material/schemas.py | 2 --
 src/order/router.py     | 2 --
 src/order/service.py    | 1 -
 5 files changed, 7 deletions(-)
```

## Reflection answers


1. **Why HTTP instead of direct database writes?** The API applies the actual
   permissions, ownership checks, request validation, transactional transitions,
   and audit writes. Direct writes bypass that contract and can corrupt related
   records. Existing migration/test internals are not a license for agent SQL.
2. **Which transition is authoritative for stock?** Approval rechecks unreserved
   stock while locking order and material rows, then reserves atomically.
   Submission only checks current stock; another request can consume it later.
3. **Available, reserved, unreserved?** Available is total recorded on-hand stock,
   including allocations. Reserved is the allocated portion. Unreserved is their
   difference. At A=100/R=20, only 80 is available for new reservations.
4. **Which rules stay deterministic?** Auth/roles/ownership, allowed states,
   positive quantities, archive checks, stock constraints, transaction locking,
   exactly-once transition effects, and audit consistency stay in backend code.
   An LLM choosing a tool cannot relax these rules.
5. **Why is HTTP success insufficient?** The wrong target or quantity can still
   be a successful request; a response alone does not prove the intended
   inventory delta or audit chain. Re-read state and correlate audit records.
6. **What can become stale?** Stock/reservations, order status and ownership
   context, archive flags, material identity/metadata/unit/QC/location, destination
   location, role permissions, and token validity. Re-read before action and rely
   on backend checks during execution.

## Remaining submission and acceptance steps

1. Have the learner explain the invariants and exception outcomes to the mentor;
   disclose that exception checks used a script and account recovery used SQL.
2. Obtain mentor acceptance, including any request for a manual exception replay.
   Do not mark Milestone 0 accepted or begin Milestone 1 prematurely.

## Final delivery checks

The owner authorized creation of the separate Desktop folder. The three Markdown
files and supporting JSON evidence were copied there. No backend files changed
during delivery. No Git repository was initialized, so destination Git diff/status
results are unavailable; equivalent whitespace, relative-link, and JSON checks
passed. The temporary verification script was not included in the deliverables.

# Current system contract

Status: source-reviewed contract with normal-flow and exception HTTP evidence;
documents are placed in the separate project folder; mentor acceptance is pending.
See [the evidence report](step-00-evidence.md) for observed results and blockers.

## System boundary and provenance

The source system is the existing FastAPI backend in `lab-storage-management`.
Its HTTP API owns authentication, authorization, validation, order transitions,
inventory mutations, transactions, and audit writes. MySQL is accessed by the
backend through SQLAlchemy; Alembic owns schema changes. Future agent tools must
call this API and must not write the database or implement alternative business
rules in prompts. No agent, LLM, frontend, QC-run, or shipment implementation is
part of this milestone. `qc_status` is existing editable metadata, not a QC engine
or a prerequisite for order approval.

Source base commit: `c96978c7da0a97942d0bb0b452b64f49b411c7a7`.
The inspected checkout also has seven blank-line deletions in five
backend files, recorded in the evidence report. This is not a clean-commit audit.
Local API: `http://127.0.0.1:8000`. Expected schema: `20260812_0004`.

Source references are relative to the backend checkout:

| Contract area | Authoritative source |
| --- | --- |
| Registered API boundary | `src/main.py` |
| Permissions and bearer validation | `src/utils/constant.py`, `src/auth/dependencies.py`, `src/auth/service.py` |
| Authentication and account operations | `src/user/router.py`, `src/user/schemas.py`, `src/user/service.py` |
| Material validation, queries, inventory | `src/material/router.py`, `src/material/schemas.py`, `src/material/service.py` |
| Order state and atomic inventory effects | `src/order/router.py`, `src/order/schemas.py`, `src/order/service.py` |
| Audit and reporting access | `src/audit/router.py`, `src/report/router.py`, `src/report/service.py` |
| Error envelope and session cleanup | `src/core/errors.py`, `src/db/connection.py` |
| Persistent invariants | `migrations/versions/20260812_0001_initial_schema.py` through `20260812_0004_auth_hardening.py` |
| Regression coverage | `tests/test_app.py`, `tests/test_migrations.py`, `tests/test_config.py` |

## Authentication

1. `POST /users/register` accepts `{username, email, password}` and creates a
   viewer, regardless of a caller's desired role. Success is `201` with `UserRead`.
   Username: 3–30 characters, letter first, then letters, digits, underscores.
   Password: 8–72 characters including a letter and a digit. Email is normalized
   and validated. Never record a real password in evidence.
2. `POST /users/login` accepts `{username, password}` and returns
   `{user: UserRead, token: string}`. The token is opaque, not a client-decoded JWT.
3. Send `Authorization: Bearer <token>` to protected routes. `GET /users/me`
   returns `{id, username, email, role, profile_picture}`; verify the actual role.
4. Token lifetime defaults to 60 minutes and is configurable. Invalid or expired
   tokens return `401 AUTH_TOKEN_INVALID`. Missing headers return
   `401 AUTH_HEADER_MISSING`. Password and role changes revoke the account's tokens.
5. `POST /users/logout` accepts `{token}` in its body, retiring that token.
   The route itself does not require a bearer header. Success returns a message.
6. Login failures are persisted and rate limited; `429 LOGIN_RATE_LIMITED`
   includes `Retry-After`. Do not repeatedly guess credentials.

Registration, login, logout, health, and generated documentation are public.
The guarded bootstrap CLI creates only the first admin and refuses an existing
admin or identity. It is setup machinery, not a future agent tool.

## Role-permission matrix

“Yes” means the route permits that role, still subject to validation and state.

| Operation | Viewer | Staff | Admin |
| --- | --- | --- | --- |
| Read/search materials and locations | Yes | Yes | Yes |
| Create an order | Yes | Yes | Yes |
| Read/list orders | Own | Own | All |
| Cancel submitted/approved order | Own | Own | Any |
| Archive terminal order with reason | Own | Own | Any |
| Create/edit material and location metadata | No | Yes | Yes |
| Inventory adjustment, check-in/out, dedicated move | No | No | Yes |
| Archive/restore material | No | No | Yes |
| Approve/reject/fulfill orders | No | No | Yes |
| Operational reports | No | Yes | Yes |
| Direct audit-log endpoint | No | No | Yes |
| User directory and role changes | No | No | Yes |
| Read/edit own account and change own password | Yes | Yes | Yes |

Important scope details: inaccessible orders return `404 ORDER_NOT_FOUND`, not
an ownership-revealing `403`. Staff reports include all pending requests and
recent inventory activity, even though staff order-list access is owner-scoped.
Staff material creation accepts initial `quantity_available`; metadata updates
accept `location_id`. Thus “admin-only inventory operations” describes the
specific inventory routes, not a blanket prohibition on staff setting initial
stock or changing location through metadata. No stricter policy is invented here.

## Relevant endpoints and shapes

`{id}` below means the relevant positive record identifier. Protected GETs are
business read-only, although authentication may remove an expired token.

| Method and path | Effect | Request / response |
| --- | --- | --- |
| `GET /health`, `/health/ready` | Read | Liveness; readiness adds database and migration |
| `GET /materials` | Read | Active `Page[MaterialRead]` |
| `GET /materials/search` | Read | Filtered `Page[MaterialRead]` |
| `GET /materials/{id}` | Read | `MaterialRead`, including an archived record by ID |
| `POST /materials` | Write | `MaterialCreate` → `201 MaterialRead` |
| `PATCH /materials/{id}` | Write | Partial metadata → `MaterialRead` |
| `POST /materials/{id}/archive?reason=...` | Write | Required nonblank query reason → message |
| `POST /materials/{id}/restore` | Write | No body → message |
| `POST /materials/{id}/adjust-quantity` | Write | `{quantity_available: integer >= 0, reason}` → `MaterialRead` |
| `POST /materials/{id}/check-in`, `/check-out` | Write | `{quantity: integer > 0, reason}` → `MaterialRead` |
| `POST /materials/{id}/move` | Write | `{location_id: positive integer or null, reason}` → `MaterialRead` |
| `GET /locations`, `/locations/{id}` | Read | `Page[LocationRead]` or `LocationRead` |
| `POST /locations`, `PATCH /locations/{id}` | Write | Create/partial metadata → location; create returns `201` |
| `GET /orders`, `/orders/{id}` | Read | Owner-scoped page or single `OrderRead`; admins see all |
| `POST /orders` | Write | `{material_id, requested_quantity, request_notes?}` → `201 OrderRead` |
| `POST /orders/{id}/approve`, `/reject`, `/fulfill`, `/cancel` | Write | Optional `{outcome_notes: string or null}` → `OrderRead` |
| `POST /orders/{id}/archive` | Write | `{reason: nonblank string}` → `OrderRead` |
| `GET /audit-logs` | Read | `Page[InventoryAuditLogRead]` |
| `GET /reports/low-stock`, `/pending-orders`, `/recent-inventory-activity`, `/materials-by-location` | Read | Arrays of report rows; not page envelopes |
| `GET /users` | Read | Admin-only page of user directory records |
| `PATCH /users/{id}/role` | Write | `{role: viewer/staff/admin}`; last admin cannot be demoted |
| `PATCH /users/me`, `POST /users/me/password` | Write | Profile / current and new password; see user schemas |

`Page[T]` is `{items: T[], page, size, total, pages}`. Page starts at 1; size
is 1–100, default 25. Material list, search, locations, orders, audit, and user
list use this envelope. Clients must follow all pages when completeness matters.

Material search accepts `keyword` (code/name/description), `material_type`,
`source`, `qc_status`, `availability_status`, `location_id`, `low_stock`, and
`include_archived`. These filters belong to `/materials/search`, not the plain
material-list route. `low_stock=true` also includes zero unreserved stock;
`availability_status=low_stock` requires positive unreserved stock.

Order list accepts `status`, `material_id`, `requested_by_user_id`,
`reviewed_by_user_id`, `include_archived`, `page`, `size`. Non-admins cannot use
requester filters to escape ownership. Audit filters are `user_id`, `material_id`,
and `operation_type`; recent-activity reports add `limit` (1–100, default 20).

### Material and location records

`MaterialCreate` requires `material_code`, `material_name`, `material_type`,
`description`, `source`, `quantity_available`, `unit`, `minimum_quantity`,
`qc_status`, and `storage_condition`; `location_id` is optional/null. Quantities
and minimum are nonnegative integers. QC is `pending`, `passed`, or `failed`.

`MaterialRead` includes those fields plus `id`, `quantity_reserved`, computed
`availability_status`, `is_archived`, `archived_at`, `archived_by_user_id`,
`archive_reason`, `created_at`, and `updated_at`. Nullable response fields may
contain null. `MaterialUpdate` does not expose quantities or `material_code`.

`LocationCreate` requires `name` and `location_type`; `parent_location_id`,
`temperature_zone`, and `description` are optional/null. `LocationRead` adds
`id`, `created_at`, and `updated_at`. Cyclic parent changes fail with a conflict.

### Order and audit records

`OrderRead` fields are `id`, `requested_by_user_id`, `material_id`,
`requested_quantity`, `reserved_quantity`, `status`, `request_notes`,
`reviewed_by_user_id`, `reviewed_at`, `outcome_notes`, `is_archived`,
`archived_at`, `archived_by_user_id`, `archive_reason`, `created_at`, `updated_at`.
Requested quantity and material ID must be positive integers. Notes are optional,
trimmed, and limited to 5,000 characters. Archive reasons are trimmed, nonblank,
and at most 5,000 characters.

Audit rows contain `id`, `user_id`, `material_id`, `operation_type`,
`before_value`, `after_value`, `reason`, and `created_at`. Order inventory values
are JSON-encoded strings containing available/reserved quantities. Parse these
strings to compare values. The order ID appears in `reason`, not a dedicated
order foreign-key field. Other audit operations use different string formats.

## Error contract

```json
{"error":{"code":"ORDER_STOCK_INSUFFICIENT","message":"Insufficient unreserved stock to submit order"}}
```

`error.code` is the machine-readable discriminator. `message` is display text.
`details` is omitted when null; validation errors include details. An
`X-Request-ID` response header supports request correlation; it is not an
idempotency key. Never retain credential-bearing validation inputs in evidence.

| HTTP | Relevant code | Meaning |
| --- | --- | --- |
| 400 | `ORDER_OPERATION_FAILED` | Generic order-operation failure |
| 401 | `AUTH_HEADER_MISSING`, `AUTH_HEADER_INVALID`, `AUTH_TOKEN_MISSING`, `AUTH_TOKEN_INVALID` | Authentication failure |
| 403 | `PERMISSION_DENIED`, `ROLE_INVALID` | Role/permission failure |
| 404 | `ORDER_NOT_FOUND`, `MATERIAL_NOT_FOUND` | Missing resource, or inaccessible order |
| 409 | `ORDER_STATUS_CONFLICT` | Transition disallowed from current status |
| 409 | `ORDER_STOCK_INSUFFICIENT` | Submission/approval lacks unreserved stock |
| 409 | `ORDER_RESERVATION_INCONSISTENT` | Fulfillment/cancellation reservation check failed |
| 409 | `MATERIAL_ARCHIVED` | Archived material blocks submission, approval, fulfillment |
| 409 | `MATERIAL_HAS_ACTIVE_RESERVATION` | Material cannot be archived yet |
| 409 | `ORDER_ALREADY_ARCHIVED` | Duplicate order archive |
| 422 | `VALIDATION_ERROR` | Invalid payload/query |
| 429 | `LOGIN_RATE_LIMITED` | Login throttle |
| 500 | `DATABASE_ERROR`, `INTERNAL_SERVER_ERROR` | Unexpected failure; reconcile before retry |
| 503 | `SERVICE_NOT_READY` | Readiness cannot confirm database/schema |

## Business invariants

1. Available quantity A includes reserved stock R. Unreserved stock is A − R.
   The schema enforces A ≥ 0 and 0 ≤ R ≤ A; requested quantity q is positive.
2. Submission requires an active material and A − R ≥ q, but changes neither
   A nor R. Multiple submitted requests may compete for the same stock.
3. Approval is the authoritative check under order/material row locks. It adds
   q to R and records order reservation q in the same transaction and audit write.
4. Fulfillment requires approved status, an active material, and A and R each
   covering the order reservation r. It subtracts r from both A and R and sets
   order reservation to zero. Repeat fulfillment cannot deduct stock again.
5. Canceling an approved order releases r from R without reducing A; submitted
   cancellation has no inventory effect. Owners or admins may cancel.
6. Only submitted orders can be rejected; rejection has no inventory effect.
   There is no approved-to-rejected transition.
7. Database constraints require approved reservation = requested quantity and
   non-approved reservation = zero. Cross-row totals rely on transactional services.
8. Direct quantity adjustment/check-out cannot reduce A below R.
9. Material archive fails while reserved stock or an approved order exists.
   Legacy archived-material fulfillment is blocked, but cancellation can recover
   its reservation.
10. Order archive is a separate immutable flag on a terminal status, requires a
    reason, and preserves audit history. No order restore endpoint exists.
11. Availability is derived on reads: A − R ≤ 0 → unavailable; otherwise
    A − R ≤ minimum → low_stock; otherwise available. It is not stored.
12. Order inventory changes and their audit entries commit together. Expected
    business failures do not commit partial order/inventory changes; database
    session closure rolls back uncommitted work.

## Re-read before action, verify after action

Re-read identity/role, target order owner/status/reservation/archive flag, material
identity/archive flag/A/R/unit/QC/location, and any proposed destination location.
Search results, stock, review state, role, and token validity may change between
preview and execution. Re-reading helps the preview; backend locks and checks
remain authoritative at execution time.

After a write, GET the order and material and correlate relevant audit entries.
For insufficient-stock submission, compare order-list total/IDs before and after;
for denied approval, compare order, inventory, and audit history. A successful
HTTP response alone does not prove the intended target, quantity, or audit chain.
There is no exposed idempotency-key mechanism; reconcile ambiguous outcomes
before retrying a write, particularly order creation.

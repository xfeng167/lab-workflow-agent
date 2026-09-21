# Milestone 0: Current System Contract

## Goal

Build a verified understanding of the existing Lab Storage Management backend
before adding an LLM.

At the end of this milestone, you must be able to explain and manually prove the
request-to-fulfillment workflow, its role boundaries, its inventory effects,
and its failure behavior.

Do not implement agent code in this milestone.

## Why this milestone matters

An agent cannot safely operate a business workflow that its developer does not
understand. Prompt text must not become an alternative implementation of the
source system's permissions, state machine, or inventory rules.

Your output is a verified contract that later milestones will use when defining
tools and evaluating outcomes.

## Prerequisites

- Git, Python, HTTP, JSON, and command-line basics.
- Docker Desktop or an equivalent Docker runtime.
- `uv` installed.
- Local access to the `lab-storage-management` repository.
- A terminal and an HTTP client such as `curl`.

## Allowed scope

- Read the existing Lab Storage source code and documentation.
- Start its development Docker services.
- Run its migrations and tests against the documented local databases.
- Create local-only demo users and records.
- Call its local HTTP API.
- Add the required Step 0 documentation to the `lab-workflow-agent` repository.

## Out of scope

- LLM or Moonshot API calls.
- Agent code.
- Changes to `lab-storage-management`.
- Direct MySQL reads or writes as a substitute for API verification.
- Railway, production, or shared cloud environments.
- QC-run or shipment features that the source API does not implement.
- Frontend work.

## Safety rules

- Confirm that every URL is local before sending a request.
- Never use production credentials or data.
- Do not remove Docker volumes or reset a database unless the owner explicitly
  authorizes it.
- `TEST_DATABASE_URL` must point to `lab_storage_test_db`; never point tests at
  `lab_storage_db` or a production database.
- Do not save passwords or bearer tokens in committed files or evidence.
- Clear sensitive shell variables when the manual session ends.

## Source references

Read these files in the existing `lab-storage-management` repository:

- `README.md`
- `docs/development.md`
- `src/main.py`
- `src/utils/constant.py`
- `src/auth/dependencies.py`
- `src/material/router.py`
- `src/material/schemas.py`
- `src/material/service.py`
- `src/order/router.py`
- `src/order/schemas.py`
- `src/order/service.py`
- `src/audit/router.py`
- `src/report/router.py`
- `migrations/versions/`
- `tests/`

Do not assume that a README statement is current until you locate the matching
route, service behavior, or test.

## Task 0.1: Prepare the local source system

Open a terminal in the `lab-storage-management` repository.

Install dependencies:

```bash
uv sync --extra dev
```

Start the development database:

```bash
docker compose -f docker/docker-compose.dev.yaml up -d
```

Set the documented local connections:

```bash
export DATABASE_URL='mysql+pymysql://lab_user:lab_password@localhost:3306/lab_storage_db'
export TEST_DATABASE_URL='mysql+pymysql://lab_user:lab_password@localhost:3306/lab_storage_test_db'
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Run backend tests:

```bash
uv run pytest
```

Start the API in a separate terminal with the same `DATABASE_URL`:

```bash
uv run uvicorn src.main:app --reload
```

Verify:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/health/ready
```

Expected result:

- Both requests return a successful response.
- `/health/ready` confirms database connectivity and the expected migration.
- API documentation loads at `http://127.0.0.1:8000/docs`.

If a command fails, stop and diagnose it. Record the error and resolution in
the evidence report instead of silently switching databases or environments.

## Task 0.2: Prepare local users

You need one viewer and one admin.

For a fresh local database, create the first admin with temporary shell
variables:

```bash
export BOOTSTRAP_ADMIN_USERNAME='agent_admin'
export BOOTSTRAP_ADMIN_EMAIL='agent_admin@example.com'
export BOOTSTRAP_ADMIN_PASSWORD='replace-with-a-local-password1'
uv run python -m src.cli bootstrap-admin
unset BOOTSTRAP_ADMIN_USERNAME BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_PASSWORD
```

If the command reports that an admin already exists, do not delete or demote
that account. Use an authorized existing local admin or ask the repository owner
how to proceed.

Set the local API URL:

```bash
export LAB_API_URL='http://127.0.0.1:8000'
```

Register a local viewer. Use a local-only password that is not reused anywhere:

```bash
curl -i \
  -X POST "$LAB_API_URL/users/register" \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "agent_viewer",
    "email": "agent_viewer@example.com",
    "password": "replace-with-a-local-password1"
  }'
```

If the viewer already exists, use the existing local account or create a
different valid local identity.

Log in as the viewer:

```bash
curl -sS \
  -X POST "$LAB_API_URL/users/login" \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "agent_viewer",
    "password": "replace-with-a-local-password1"
  }'
```

Copy the returned token into a temporary shell variable. Do not place it in a
document or commit:

```bash
export VIEWER_TOKEN='paste-the-local-viewer-token-here'
```

Log in as the local admin in the same way and store the returned token only in
the current shell:

```bash
export ADMIN_TOKEN='paste-the-local-admin-token-here'
```

Verify both identities:

```bash
curl -sS "$LAB_API_URL/users/me" -H "Authorization: Bearer $VIEWER_TOKEN"
curl -sS "$LAB_API_URL/users/me" -H "Authorization: Bearer $ADMIN_TOKEN"
```

Expected roles are `viewer` and `admin` respectively.

## Task 0.3: Create a local workflow fixture through the API

Create a location as the admin:

```bash
curl -sS \
  -X POST "$LAB_API_URL/locations" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Agent Training Freezer",
    "location_type": "freezer",
    "parent_location_id": null,
    "temperature_zone": "-20 C",
    "description": "Local fixture for lab-workflow-agent Milestone 0"
  }'
```

Copy its returned `id` into a temporary variable:

```bash
export LOCATION_ID='replace-with-returned-location-id'
```

Create a material as the admin:

```bash
curl -sS \
  -X POST "$LAB_API_URL/materials" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"material_code\": \"AGENT-MAT-001\",
    \"material_name\": \"Agent Workflow Control Sample\",
    \"material_type\": \"control sample\",
    \"description\": \"Local fixture for learning the order lifecycle\",
    \"source\": \"Training supplier\",
    \"quantity_available\": 100,
    \"unit\": \"units\",
    \"minimum_quantity\": 20,
    \"qc_status\": \"passed\",
    \"storage_condition\": \"Store at -20 C\",
    \"location_id\": $LOCATION_ID
  }"
```

Copy its returned `id`:

```bash
export MATERIAL_ID='replace-with-returned-material-id'
```

If `AGENT-MAT-001` already exists, use the existing local fixture after
verifying its fields, or choose another unique local code. Do not delete someone
else's data to make the command succeed.

## Task 0.4: Demonstrate discovery and the normal order lifecycle

Search as the viewer:

```bash
curl -sS \
  "$LAB_API_URL/materials/search?keyword=Agent%20Workflow&size=10" \
  -H "Authorization: Bearer $VIEWER_TOKEN"
```

Read the material directly:

```bash
curl -sS \
  "$LAB_API_URL/materials/$MATERIAL_ID" \
  -H "Authorization: Bearer $VIEWER_TOKEN"
```

Before the order, record:

- `quantity_available`
- `quantity_reserved`
- `availability_status`
- `qc_status`

Submit an order for 20 units as the viewer:

```bash
curl -sS \
  -X POST "$LAB_API_URL/orders" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"material_id\": $MATERIAL_ID,
    \"requested_quantity\": 20,
    \"request_notes\": \"Milestone 0 normal workflow\"
  }"
```

Copy the returned order `id`:

```bash
export ORDER_ID='replace-with-returned-order-id'
```

Verify the order is `submitted`, then read the material again. Submission must
not increase `quantity_reserved`.

Approve as the admin:

```bash
curl -sS \
  -X POST "$LAB_API_URL/orders/$ORDER_ID/approve" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"outcome_notes":"Approved for Milestone 0"}'
```

Read the material again. For the clean fixture, the expected state is:

- `quantity_available`: 100
- `quantity_reserved`: 20
- unreserved stock: 80

Fulfill as the admin:

```bash
curl -sS \
  -X POST "$LAB_API_URL/orders/$ORDER_ID/fulfill" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"outcome_notes":"Fulfilled for Milestone 0"}'
```

Read the order and material again. For the clean fixture, the expected state is:

- Order status: `fulfilled`
- Order reserved quantity: 0
- Material available quantity: 80
- Material reserved quantity: 0

Read audit records:

```bash
curl -sS \
  "$LAB_API_URL/audit-logs?material_id=$MATERIAL_ID&size=25" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Identify the entries associated with reservation and fulfillment. Explain the
before and after values in your evidence report.

## Task 0.5: Demonstrate required exception paths

### Viewer cannot approve

Create a second small order as the viewer, then attempt to approve it with the
viewer token:

```bash
curl -i \
  -X POST "$LAB_API_URL/orders/REPLACE_WITH_SECOND_ORDER_ID/approve" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Expected result: `403` and no order or inventory mutation.

### Request cannot exceed unreserved stock

Attempt a request larger than the current unreserved quantity:

```bash
curl -i \
  -X POST "$LAB_API_URL/orders" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"material_id\": $MATERIAL_ID,
    \"requested_quantity\": 999999,
    \"request_notes\": \"Expected stock failure\"
  }"
```

Expected result: `409` with a stable business error code and no new order.

### Canceling an approved order releases its reservation

1. Submit a new order for 10 units as the viewer.
2. Approve it as the admin.
3. Verify that `quantity_reserved` increased by 10.
4. Cancel the order as its viewer owner.
5. Verify that the order is `canceled` and the 10 reserved units were released.
6. Verify the reservation-release audit entry.

Write the requests yourself by adapting the normal-flow commands. Do not copy a
solution from another implementation.

## Task 0.6: Write the verified contract

Add these files to `lab-workflow-agent`:

### `docs/current-system-contract.md`

Include:

- System boundary.
- Authentication flow.
- Role-permission matrix.
- Relevant API endpoints and request/response shapes.
- Stable business error envelope.
- Which operations are read-only and which mutate state.
- Which facts later agent tools must re-read before executing.
- At least five business invariants.

### `docs/order-state-machine.md`

Include:

- All order states.
- Every allowed transition.
- Actor or role for each transition.
- Inventory effect of each transition.
- Failure behavior.
- A Mermaid state diagram.

### `docs/step-00-evidence.md`

Include:

- Environment used, without secrets.
- Commit hash of the source backend that you inspected.
- Commands run and concise results.
- Test result.
- IDs of local-only fixture records.
- Before and after inventory values.
- Normal-flow evidence.
- Authorization, stock, and cancellation evidence.
- Any discrepancy between documentation and observed behavior.
- Known limitations.

Do not paste bearer tokens, passwords, complete environment dumps, or database
credentials into the evidence file.

## Required checks

Run in `lab-storage-management`:

```bash
uv run pytest
git status --short
```

Run in `lab-workflow-agent` after writing the documents:

```bash
git diff --check
git status --short
```

If the new repository has not yet been initialized, report that fact and run an
equivalent whitespace check when possible. Do not create a nested repository in
the temporary directory.

## Definition of done

Milestone 0 is complete only when:

- The local Docker MySQL environment is running and migrated.
- The current backend tests pass, or every failure is documented and reviewed.
- The learner manually demonstrates the normal request-to-fulfillment flow.
- Submission, approval, fulfillment, and approved-order cancellation effects are
  correctly explained.
- Viewer authorization failure and insufficient-stock failure are demonstrated.
- Audit evidence is connected to the corresponding inventory transitions.
- All three required documents are complete and consistent with runtime results.
- No source-backend changes, secrets, or production activity are present.
- The mentor marks Milestone 0 as accepted.

## Stop conditions

Stop and ask for help if:

- A command would target a non-local API or database.
- `TEST_DATABASE_URL` does not clearly identify a dedicated test database.
- You do not have a valid local admin and creating one would overwrite data.
- Migration or test behavior suggests the local schema differs from the current
  repository.
- A request produces an unexpected state mutation.
- You are unsure whether a credential or token is safe to record.

## Reflection questions

Answer these in the evidence report:

1. Why must an agent use the HTTP API instead of writing the database directly?
2. Which order transition is the authoritative stock check, and why?
3. What is the difference between available, reserved, and unreserved stock?
4. Which rules must remain deterministic even when an LLM chooses the next tool?
5. Why is a successful HTTP response not always enough to prove the intended
   business outcome?
6. Which source facts could become stale between an action preview and execution?

## Submission

Provide the mentor with:

- A concise summary.
- The three documentation files.
- `git diff --stat` and `git status --short`.
- Required check results.
- Answers to the reflection questions.

Do not begin Milestone 1 until the mentor accepts Milestone 0.

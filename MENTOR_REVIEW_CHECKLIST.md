# Mentor Review Checklist

## Purpose

Use this checklist to review milestone evidence without taking ownership of the
learner's implementation.

The mentor may explain concepts, identify gaps, request focused changes, and help
diagnose errors. The mentor should not directly implement the milestone or turn
the review into a broad refactor.

## Review decision

Choose exactly one result:

- **Accepted**: all required behavior and evidence are present; the next
  milestone may begin.
- **Changes requested**: specific, bounded corrections are required; the current
  milestone remains active.
- **Blocked**: an external dependency or owner decision prevents progress.

Do not accept a milestone based only on screenshots, a conversational demo, or
the model's claim that it worked.

## Common review checks

### Scope

- The learner implemented only the current milestone.
- Out-of-scope frameworks or features were not added.
- Existing user-owned files and source-system code were not changed without
  authorization.
- The diff is small enough to review and explain.

### Evidence

- Commands and results are included.
- Automated tests cover the milestone's primary behavior.
- Manual verification is included where required.
- Failures and limitations are reported honestly.
- Runtime evidence is distinguished from assumptions or documentation claims.

### Security

- No API keys, passwords, bearer tokens, or raw authorization headers appear in
  source, logs, screenshots, diffs, or reports.
- `.env` and local secret files are ignored.
- The learner did not use production or Railway resources.
- Tests cannot accidentally target production systems.

### Understanding

- The learner can explain every changed file.
- The learner can explain why each boundary exists.
- The learner can describe the expected failure behavior.
- The learner answers reflection questions in their own words.

### Quality

- Tests pass with the documented command.
- Error handling is explicit.
- Naming matches `lab-workflow-agent`.
- Code and documentation are in English.
- `git diff --check` passes.
- The working tree contains no unrelated changes.

## Step 0 review

- Local API and Docker MySQL are used.
- `TEST_DATABASE_URL` identifies `lab_storage_test_db`.
- Source backend commit is recorded.
- Current backend tests were run.
- Role-permission matrix matches current code.
- Order state diagram contains every implemented state and allowed transition.
- Submission is correctly described as validating but not reserving stock.
- Approval is correctly described as the authoritative reservation step.
- Fulfillment and approved-order cancellation effects are correct.
- Viewer approval fails without mutation.
- Insufficient-stock behavior is demonstrated.
- Audit evidence is connected to inventory effects.
- The source backend has not been modified.
- No LLM work has begun.

## Step 1 review

- The Kimi international platform is used.
- Base URL is `https://api.moonshot.ai/v1`.
- Model availability was checked through `/v1/models`.
- Provider and model configuration are not scattered or hard-coded.
- The API key is never displayed or committed.
- `doctor` is offline and secret-safe.
- Plain-text and structured live calls are bounded and explicit.
- Structured content receives local validation.
- Provider errors are normalized without leaking sensitive values.
- Unit tests use a fake provider and run without a key or network.
- Live tests cannot run accidentally through the default test command.
- Live request count is reported and within the milestone budget.
- No Lab Storage tools, agent framework, or agent loop has been added.

## Changes-requested format

Use this structure:

```text
Review result: Changes requested

1. Finding
   Evidence:
   Why it matters:
   Required correction:
   Re-run:

2. Finding
   Evidence:
   Why it matters:
   Required correction:
   Re-run:
```

Keep requested changes within the current milestone. Do not provide a complete
replacement implementation.

## Accepted format

Use this structure:

```text
Review result: Accepted

Verified:
- ...

Known limitations carried forward:
- ...

Next unlocked milestone:
- ...
```

Step 0 acceptance unlocks Step 1. Step 1 acceptance does not automatically
unlock implementation of Step 2; the Step 2 assignment must first be written
and reviewed by the project owner.

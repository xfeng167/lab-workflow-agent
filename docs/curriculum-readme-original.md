# lab-workflow-agent

`lab-workflow-agent` is a learning-first, production-shaped project for building
an AI-native workflow over the existing Lab Storage Management API.

The finished product will let lab requesters and operators use natural language
to find materials, prepare requests, confirm sensitive actions, and complete
real inventory and order workflows. The existing Lab Storage Management API
remains the system of record and the final authority for authentication,
permissions, transactions, inventory, and audit history.

This directory is a temporary curriculum package. Its contents are intended to
be moved into a separate Git repository also named `lab-workflow-agent` before
implementation begins. Do not initialize a nested Git repository while this
directory remains inside `lab-storage-management`.

## Start here

1. Read [PROJECT_BRIEF.md](PROJECT_BRIEF.md).
2. Read [LEARNING_ROADMAP.md](LEARNING_ROADMAP.md).
3. Complete [Milestone 0](milestones/step-00-current-system-contract.md).
4. Ask for a milestone review.
5. After Milestone 0 passes, complete
   [Milestone 1](milestones/step-01-moonshot-api-foundations.md).
6. Do not begin Milestone 2 until Milestone 1 has been reviewed and accepted.

## Available milestones

| Milestone | Assignment | Status |
| --- | --- | --- |
| Step 0 | Current System Contract | Ready |
| Step 1 | Moonshot API Foundations | Ready; begins after Step 0 passes |
| Step 2 | Read-only Material Finder | Locked; assignment not written yet |
| Steps 3-10 | See the roadmap | Locked |

## Working rules

- The learner owns the implementation. A mentor may explain, review, and help
  diagnose errors, but should not implement the milestone for the learner.
- Complete one milestone at a time and provide evidence before moving forward.
- Keep code, comments, commit messages, and project documentation in English.
- Never commit API keys, passwords, bearer tokens, or `.env` files.
- Use the local Lab Storage API and its Docker MySQL database. Never use the
  Railway or other production environment for this project.
- The agent must use the Lab Storage HTTP API. It must never read or write the
  Lab Storage MySQL database directly.
- Unit tests must not call a live LLM provider.

## Source system

The source business system is:

- Repository: `xfeng167/lab-storage-management`
- Local API default: `http://127.0.0.1:8000`
- Local database: Docker MySQL from `docker/docker-compose.dev.yaml`
- API documentation: `http://127.0.0.1:8000/docs`

## LLM provider baseline

- Provider: Kimi international API platform
- Console: <https://platform.kimi.ai/>
- Base URL: `https://api.moonshot.ai/v1`
- API format: OpenAI-compatible Chat Completions
- Initial model setting: `kimi-k2.6`, subject to verification through the
  provider's `/v1/models` endpoint

Provider and model names are configuration, not hard-coded business logic.

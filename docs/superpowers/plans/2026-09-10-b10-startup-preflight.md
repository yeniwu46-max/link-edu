# B-10 Startup Preflight Implementation Plan

> **For agentic workers:** Execute this plan inline with verification checkpoints.

**Goal:** Make the B-10 startup preflight reproducible in a clean local checkout without treating missing production configuration as success.

**Architecture:** Keep an existing `backend/.env` or explicit `-DatabaseUrl` as the source of truth. When neither is available, use a clearly reported local SQLite database for loopback smoke testing; `-RequireEnv` preserves a strict configuration gate for deployment-like runs.

**Tech Stack:** PowerShell, Flask/SQLAlchemy, Vite, Node test runner.

---

### Task 1: Lock the startup contract

**Files:**
- Modify: `frontend/tests/startupRegressionContract.test.mjs`

- [ ] Assert that the startup script exposes a strict configuration switch and a local SQLite fallback.
- [ ] Run the focused test and confirm it fails before the implementation.

### Task 2: Implement local startup fallback

**Files:**
- Modify: `scripts/start-classroom.ps1`

- [ ] Add explicit database and runtime-directory parameters.
- [ ] Prefer `backend/.env` or `-DatabaseUrl`.
- [ ] When configuration is absent, set a loopback-only SQLite URL, seed data, and a local JWT key, and print that this is a smoke-test fallback.
- [ ] Add `-RequireEnv` to retain a hard failure when production configuration is required.

### Task 3: Verify B-10 end to end

**Files:**
- Verify: `scripts/start-classroom.ps1`
- Verify: `scripts/run-regression.ps1`

- [ ] Run the focused frontend contract test.
- [ ] Run the startup script on isolated ports and confirm backend health, demo login, and frontend health.
- [ ] Stop only the processes started by the verification.
- [ ] Run the full backend tests, frontend tests, build, regression script, and `git diff --check`.


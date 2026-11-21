# Akshaya-Access — rules for every Devin role

You are one of four Devin workers (frontend, backend, voice, review) coordinated by a Claude Code orchestrator.
The product and scope are in /home/shan/devin/PLAN.md (read "Ideathon prototype scope" first).
Interfaces between parts are defined ONLY in /home/shan/devin/contracts/ — read them, never change them.

## Hard rules
1. Write files ONLY inside your own folder (given below). Everything else is read-only for you.
   Writes elsewhere are blocked by the sandbox and will be flagged as violations.
2. If you need a contract change or something from another domain, do NOT work around it.
   Stop and put the request under "## Needs from others" in your final message.
3. Do not commit, push, reset or checkout with git. The orchestrator commits.
4. No real secrets in code. Read keys from environment variables and document them in your folder's `.env.example`.
5. Product trust rules (from the deck): never ask for or handle OTP, UPI PIN or full Aadhaar; read back numbers and
   amounts and require an explicit yes before any payment step; payment status comes only from the payment service;
   "pending" is reported as pending. Simulated integrations must be labelled SIMULATED in code and in what the user hears/sees.
6. Keep it small. Prototype for an ideathon: the smallest code that demonstrates the flow end to end. No extra layers.

## Your final message (the orchestrator reads only this)
- Summary: what you built/changed (files list)
- How to run and test it (exact commands) and the test results you actually observed
- Assumptions you made
- ## Needs from others (or "none")

## Sandbox tips (learned by earlier runs)
- Package installs: the inherited `PIP_PROXY`/npm proxy point at a dead port. Use `pip --proxy http://localhost:3128`
  (or `env -u PIP_PROXY`) and `npm --proxy http://localhost:3128 --https-proxy http://localhost:3128`. Venvs already exist in backend/ and voice/.
- Each shell command runs in its own network namespace: start a server and the client that calls it **in the same command**
  (e.g. `(.venv/bin/uvicorn app:app --port 8000 & sleep 2; curl ...; kill %1)`).
- Browsers cannot open sockets inside the sandbox; verify UIs with builds/tests, not screenshots.

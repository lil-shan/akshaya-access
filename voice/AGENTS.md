# Notes for agents working in voice/

- Test: `.venv/bin/pytest -q` (backend mocked through `httpx.MockTransport`, see `tests/fakes.py`).
- Work test-first: add the failing test, then the code.
- `pytest.ini` blocks two ROS pytest plugins that this machine's `PYTHONPATH` injects; without that pytest crashes on start.
- Inside the Devin sandbox pip needs the sandbox proxy: `.venv/bin/pip install --proxy http://localhost:3128 -r requirements.txt`
  (the inherited `PIP_PROXY` points at a port that is not reachable there).
- Inside the Devin sandbox each command has its own network: to try the simulator against the real backend, start
  the server and run `sim.py` in the same shell command (use a private port and `BACKEND_DB_PATH` inside `voice/`
  so nothing is written to `backend/`).
- The backend client uses `trust_env=False` on purpose: the machine sets `ALL_PROXY=socks5h://...`.

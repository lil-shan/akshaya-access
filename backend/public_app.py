"""Public phone port 8001 for Sarvam Voice Agents (contracts/README.md, "Phone line via Sarvam
Voice Agents"). Same DB and handlers as app.py; serves only the call-write/tools endpoints behind
`Authorization: Bearer <PHONE_TOOLS_TOKEN>`. Run: PHONE_TOOLS_TOKEN=... uvicorn public_app:app --port 8001"""
from app import create_app

# Raises RuntimeError at import if PHONE_TOOLS_TOKEN is unset, so uvicorn refuses to start.
app = create_app(public=True)

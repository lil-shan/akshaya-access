"""Supabase access (service role, server side only). Tests use FakeDb with the same methods (tests/fakes.py)."""
import datetime as dt
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUCKET = "case-files"


def load_env() -> None:
    """Service-role key from ../.cloud.env, Sarvam key from ../voice/.env (last sk_ line). Values are never printed."""
    f = ROOT / ".cloud.env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if v.strip().strip("\"'"):
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
    if not os.environ.get("SARVAM_API_KEY", "").startswith("sk_"):
        f = ROOT / "voice/.env"
        if f.exists():
            vals = [ln.split("=", 1)[1].strip().strip("\"'") for ln in f.read_text().splitlines()
                    if ln.startswith("SARVAM_API_KEY=")]
            vals = [v for v in vals if v.startswith("sk_")]
            if vals:
                os.environ["SARVAM_API_KEY"] = vals[-1]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Db:
    def __init__(self):
        from supabase import create_client
        load_env()
        self.c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    def services(self):
        return self.c.table("services").select("*").eq("active", True).order("id").execute().data

    def find_citizens(self, phone_masked):
        return self.c.table("citizens").select("*").eq("phone_masked", phone_masked).execute().data

    def add_citizen(self, row):
        return self.c.table("citizens").insert(row).execute().data[0]

    def add_case(self, row):
        return self.c.table("cases").insert(row).execute().data[0]

    def get_case(self, case_id):
        return self.c.table("cases").select("*").eq("id", case_id).single().execute().data

    def set_case(self, case_id, **kw):
        self.c.table("cases").update(dict(kw, updated_at=now())).eq("id", case_id).execute()

    def event(self, case_id, type, message, data=None):
        self.c.table("case_events").insert({"case_id": case_id, "actor": "voice", "type": type,
                                            "message": message, "data": data or {}}).execute()

    def add_consent(self, case_id, kind, text):
        self.c.table("consents").insert({"case_id": case_id, "kind": kind, "text": text, "channel": "phone"}).execute()

    def add_job(self, case_id, kind, mode):
        return self.c.table("automation_jobs").insert({"case_id": case_id, "kind": kind, "mode": mode,
                                                       "status": "queued"}).execute().data[0]

    def get_job(self, job_id):
        return self.c.table("automation_jobs").select("*").eq("id", job_id).single().execute().data

    def open_prompts(self, job_id):
        return (self.c.table("job_prompts").select("*").eq("job_id", job_id).eq("status", "open")
                .order("created_at").execute().data)

    def answer_prompt(self, prompt_id, answer):
        self.c.table("job_prompts").update({"answer": answer, "status": "answered", "answered_at": now()}) \
            .eq("id", prompt_id).eq("status", "open").execute()

    def download(self, path):
        return self.c.storage.from_(BUCKET).download(path)

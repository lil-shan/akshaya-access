import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import worker

class FakeDb:
    def __init__(self): self.fail = 1; self.claimed = []
    def queued_jobs(self):
        if self.fail: self.fail -= 1; raise RuntimeError("Server disconnected")
        return [{"id": "j1", "case_id": "c1", "kind": "x"}]
    def get_case(self, i): return {"service_id": "s"}
    def get_service(self, i): return {"submission": "portal"}
    def claim(self, i): self.claimed.append(i); return True

def test_loop_survives_transient_error(monkeypatch):
    db = FakeDb(); done = []; sleeps = []
    monkeypatch.setattr(worker, "process", lambda d, j: done.append(j["id"]))
    class Stop(Exception): pass
    def sleep(n):
        sleeps.append(n)
        if len(sleeps) >= 2: raise Stop
    try: worker.loop(db, sleep=sleep)
    except Stop: pass
    assert done == ["j1"] and sleeps[0] == 2

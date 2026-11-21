"""Call simulator: the same engine as a phone call, without a phone line.

  python sim.py                 interactive: type what the citizen says (Ctrl-D = hang up)
  python sim.py --script FILE   one citizen line per line; prints the conversation
  python sim.py --audio         microphone + speaker through Sarvam STT/TTS (needs SARVAM_API_KEY)
"""
import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

import sarvam
from backend import Backend, BackendError, GuardFailed
from engine import Engine

LABELS = {"agent": "AGENT  ", "citizen": "CITIZEN"}


class TextIO:
    def __init__(self, script: list[str] | None = None):
        self.script = script  # None = interactive

    def listen(self) -> str | None:
        if self.script is not None:
            return self.script.pop(0) if self.script else None
        try:
            return input("you> ")
        except EOFError:
            return None

    def show(self, kind: str, text: str, text_en: str = "", both: bool = False) -> bool:
        """Returns True when the line reached the citizen (here: was printed)."""
        if kind in LABELS:
            print(f"{LABELS[kind]} {text}\n        {text_en}", flush=True)
        else:
            print(f"-- {kind}: {text}", flush=True)
        return True


class AudioIO(TextIO):
    """Citizen: microphone -> Saaras STT. Agent: Bulbul TTS -> speaker. Uses ALSA's arecord/aplay.

    The microphone is open only between the two Enter presses of a citizen turn, and the engine asks for no
    citizen turn during the PIN step. Each recording is deleted as soon as it has been transcribed.
    """

    def __init__(self):
        super().__init__()
        sarvam.api_key()
        for tool in ("arecord", "aplay"):
            if not shutil.which(tool):
                sys.exit(f"Audio mode needs `{tool}` (Linux: sudo apt install alsa-utils).")

    def listen(self) -> str | None:
        try:
            if input("[Enter, then speak; q + Enter = hang up] ").strip().lower() == "q":
                return None
            with tempfile.TemporaryDirectory() as folder:
                wav = Path(folder, "citizen.wav")
                recorder = subprocess.Popen(["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", str(wav)])
                try:
                    input("[recording... Enter when done] ")
                finally:  # never leave the microphone open
                    recorder.send_signal(signal.SIGINT)
                    recorder.wait()
                return sarvam.transcribe(wav.read_bytes())
        except EOFError:
            return None
        except (httpx.HTTPError, OSError) as error:  # treated as an unclear answer; the engine asks again
            print(f"-- speech-to-text unavailable: {error}", file=sys.stderr)
            return ""

    def show(self, kind: str, text: str, text_en: str = "", both: bool = False) -> bool:
        super().show(kind, text, text_en, both)
        if kind != "agent":
            return True
        try:
            for words, language in [(text, "ml-IN")] + ([(text_en, "en-IN")] if both else []):
                subprocess.run(["aplay", "-q", "-"], input=sarvam.synthesize(words, language), check=True)
        except (httpx.HTTPError, OSError, subprocess.CalledProcessError) as error:
            print(f"-- text-to-speech unavailable: {error}", file=sys.stderr)
            return False
        return True


def main(argv: list[str] | None = None, backend: Backend | None = None) -> int:
    parser = argparse.ArgumentParser(description="Akshaya-Access call simulator (payments and bills are SIMULATED)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--script", metavar="FILE", help="file with one citizen line per line (# = comment)")
    mode.add_argument("--audio", action="store_true", help="speak and listen through Sarvam STT/TTS")
    args = parser.parse_args(argv)

    if args.audio:
        io = AudioIO()
    elif args.script:
        said = [line.strip() for line in Path(args.script).read_text(encoding="utf-8").splitlines()]
        io = TextIO([line for line in said if line and not line.startswith("#")])
    else:
        io = TextIO()
    engine = Engine(backend or Backend(), io,
                    poll_interval=float(os.environ.get("PAYMENT_POLL_INTERVAL_S", "2")),
                    poll_timeout=float(os.environ.get("PAYMENT_POLL_TIMEOUT_S", "60")))
    try:
        outcome = engine.run(os.environ.get("CALLER_PHONE", "+919999904321"), "audio" if args.audio else "simulator")
    except (BackendError, GuardFailed) as error:
        print(f"Backend problem, call stopped: {error}", file=sys.stderr)
        return 1
    print(f"-- call ended: outcome={outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""SIMULATED_DIGILOCKER: local stand-in for the API Setu DigiLocker sandbox.
Checked 2026-11-21: sandbox.api-setu.in is a login-gated testing environment (needs an API Setu partner account +
client credentials), so it cannot be called without credentials. This module returns clearly-labelled DUMMY issued
documents (no real citizen data) behind fetch(); swap in a real sandbox client with the same signature later."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
LABEL = "SIMULATED_DIGILOCKER - DUMMY DOCUMENT, NOT ISSUED BY ANY AUTHORITY"

def _pdf(title, rows):
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); y = 800
    c.setFont("Helvetica-Bold", 14); c.drawString(50, y, title); y -= 20
    c.setFont("Helvetica", 8); c.drawString(50, y, LABEL); y -= 35; c.setFont("Helvetica", 11)
    for k, v in rows: c.drawString(50, y, f"{k}: {v}"); y -= 20
    c.save(); return buf.getvalue()

def fetch(citizen_name="Dummy Citizen", dob="1980-01-01"):
    """Returns [(kind, filename, pdf_bytes)] - dummy issued documents."""
    return [
     ("aadhaar_ekyc", "aadhaar-ekyc-summary.pdf", _pdf("Aadhaar e-KYC summary (masked)", [("Name", citizen_name), ("DOB", dob), ("Aadhaar", "XXXX XXXX 0000"), ("Address", "1 Test Road, Kochi (dummy)")])),
     ("pan_card", "pan-card.pdf", _pdf("PAN card (e-copy)", [("Name", citizen_name), ("PAN", "ABCDE0000F"), ("DOB", dob)])),
     ("driving_licence", "driving-licence.pdf", _pdf("Driving licence", [("Name", citizen_name), ("DL No", "KL00 00000000000"), ("Valid till", "2040-01-01"), ("Class", "LMV")])),
    ]

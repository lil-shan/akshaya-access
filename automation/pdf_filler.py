"""Replica claim-cum-discharge PDFs (official PMJJBY/PMSBY forms from Jan Suraksha / banks are flat, non-fillable PDFs,
so we regenerate the same Part 1/Part 2 sections + attached-documents checklist). Dummy data only."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_COMMON_P2 = [("Name of nominee / claimant", "claimant_name"), ("Relationship with the deceased", "claimant_relationship"),
    ("Claimant date of birth", "claimant_dob"), ("Contact address", "claimant_address"), ("Contact mobile number", "claimant_mobile"),
    ("Bank account number for claim", "claimant_account"), ("Name of bank", "claimant_bank_name"), ("Branch IFS Code", "claimant_ifsc")]
P1 = [("Name of insured member", "insured_name"), ("Date of birth", "insured_dob"), ("Date of death", "date_of_death"),
      ("Cause of death", "cause_of_death"), ("Place of death / accident", "place_of_death"), ("Policy number", "policy_number"),
      ("Bank / post office account number", "insured_bank_account")]
SPECS = {
 "pmjjby_claim": {"title": "PRADHAN MANTRI JEEVAN JYOTI BIMA YOJANA (PMJJBY)", "source": "jansuraksha.gov.in PMJJBY claim-cum-discharge form (Annexure II, HO Cir. 121/2022)",
  "p1": P1,
  "p2": _COMMON_P2,
  "docs": ["Proof of death of the insured member (proof of accidental death if within 30 days of joining)",
           "Aadhaar and PAN of deceased member and nominee/claimant (optional)", "KYC document of nominee/appointee/claimant",
           "First two pages of passbook / statement / cancelled cheque of the claimant's account", "Proof of death of nominee, if nominee predeceased",
           "Proof of legal heir, if claimant is not the nominee", "Advance receipt for discharge, duly filled and signed"]},
 "pmsby_claim": {"title": "PRADHAN MANTRI SURAKSHA BIMA YOJANA (PMSBY)", "source": "jansuraksha.gov.in PMSBY claim-cum-discharge form",
  "p1": P1,
  "p2": _COMMON_P2,
  "docs": ["Proof of death or permanent disability (FIR / post-mortem / medical certificate as applicable)",
           "Aadhaar and PAN of member and nominee/claimant (optional)", "KYC document of claimant",
           "First two pages of passbook / statement / cancelled cheque of the claimant's account", "Proof of death of nominee, if nominee predeceased",
           "Proof of legal heir, if claimant is not the nominee", "Advance receipt for discharge, duly filled and signed"]},
}

def fill(service_id, data, case_number="", job_id=""):
    """Return PDF bytes. data = cases.data (keys above; unknown keys go to 'Additional details')."""
    spec = SPECS[service_id]; buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4; y = [H - 20 * mm]
    def line(txt, size=10, bold=False, dy=6):
        if y[0] < 25 * mm: c.showPage(); y[0] = H - 20 * mm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size); c.drawString(18 * mm, y[0], txt[:110]); y[0] -= dy * mm
    def part(name, rows):
        line(name, 11, True, 7)
        for label, key in rows:
            v = str(data.get(key) or "")
            line(f"{label}: {v if v else '______________________'}", 9.5)
        y[0] -= 3 * mm
    line(spec["title"], 13, True, 7); line("CLAIM-CUM-DISCHARGE FORM", 12, True, 7)
    line("(To be submitted preferably within 30 days)  -  GENERATED REPLICA, DUMMY DATA, NOT SUBMITTED", 8, False, 8)
    part("Part 1. Details of the member enrolled", spec["p1"]); part("Part 2. Details of the nominee / claimant", spec["p2"])
    known = {k for _, k in spec["p1"] + spec["p2"]}; extra = [(k, k) for k in data if k not in known]
    if extra: part("Additional details", extra)
    line("Declaration: I hereby declare that the details submitted above are true to the best of my knowledge, the documents", 9)
    line("attached are genuine and I have not claimed the amount earlier.", 9, dy=10)
    line("Date: ____________        Signature of nominee/appointee/claimant: ____________________", 9)
    c.showPage(); y[0] = H - 20 * mm
    line("DOCUMENT CHECKLIST", 13, True, 8); line(f"Case {case_number}  Job {job_id}", 9, dy=8)
    for d in spec["docs"]: line("[ ]  " + d, 9.5)
    line(""); line(f"Source form: {spec['source']}", 8)
    c.save(); return buf.getvalue()


# ---------------- v1.6 preparation sheets (labels/fields come from portals/<id>/service.json) ----------------
import json
from pathlib import Path
from reportlab.lib.utils import simpleSplit
_PORTALS = Path(__file__).parent / "portals"
FOOTER = "Prepared by Akshaya-Access - citizen must submit on the official portal"
SHEETS = {
 "pmfby_crop_loss": {"title": "PMFBY - CROP LOSS INTIMATION SHEET", "official": "pmfby.gov.in / Crop Insurance app / toll-free 14447",
   "banner": "DEADLINE: report the loss within 72 HOURS of the event (Crop Insurance app, 14447, insurer or agriculture office). Photos help.",
   "sections": [("Farmer and policy", ["farmer_name", "mobile", "policy_number"]), ("Crop and land", ["crop_name", "season", "survey_number", "village", "district", "area_hectare"]),
                ("Loss details", ["cause_of_loss", "loss_date", "loss_percent"]), ("Bank (for claim)", ["bank_account", "ifsc"])]},
 "pan_form49a_prep": {"title": "PAN APPLICATION (FORM 49A) - DETAILS SHEET", "official": "Protean (NSDL) / UTIITSL / incometax.gov.in",
   "sections": [("Applicant", ["full_name", "dob", "gender", "father_name", "mother_name", "applicant_status"]), ("Contact and address", ["address_line", "pincode", "mobile", "email"]),
                ("Other", ["aadhaar_last4", "source_of_income", "area_code", "proof_identity"])]},
 "passport_prep": {"title": "PASSPORT APPLICATION - DETAILS SHEET", "official": "passportindia.gov.in (Passport Seva)",
   "sections": [("Applicant", ["given_name", "surname", "dob", "place_of_birth", "gender", "marital_status"]), ("Family", ["father_name", "mother_name", "spouse_name"]),
                ("Contact and address", ["address_line", "pincode", "mobile", "email"]), ("Application", ["application_type", "booklet_pages", "scheme", "passport_office", "ecr_check"])],
   "extra": ["Appointment: book the PSK slot on the portal and carry the receipt + originals of every document below."]},
 "epf_withdrawal_prep": {"title": "EPF WITHDRAWAL (FORM 31 / 19 / 10C) - DETAILS SHEET", "official": "unifiedportal-mem.epfindia.gov.in (member portal)",
   "sections": [("Member", ["member_name", "uan", "dob", "father_or_spouse", "mobile"]), ("Claim", ["claim_type", "advance_purpose", "amount_required", "last_employer", "exit_date"]),
                ("Bank", ["bank_account", "ifsc", "aadhaar_last4"])],
   "extra": ["Do not share your UAN password or OTP with anyone; log in yourself on the EPFO portal."]},
}
def load_service(sid): return json.loads((_PORTALS / sid / "service.json").read_text())

def fill_sheet(service_id, data, case_number="", job_id=""):
    """Clean A4 preparation sheet: sections of label/value rows, optional banner, document checklist, fixed footer. Dummy data only."""
    spec, svc = SHEETS[service_id], load_service(service_id); labels = {f["key"]: f["label"] for f in svc["fields"]}
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); W, H = A4; y = [H - 20 * mm]
    def foot():
        c.setFont("Helvetica-Oblique", 8); c.drawString(18 * mm, 12 * mm, FOOTER + f"   |   Case {case_number}")
    def room(n=8):
        if y[0] < 25 * mm + n * mm: foot(); c.showPage(); y[0] = H - 20 * mm
    def text(t, size=10, bold=False, indent=0, gap=5):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for ln in simpleSplit(t, "Helvetica-Bold" if bold else "Helvetica", size, W - 36 * mm - indent * mm):
            room(); c.drawString((18 + indent) * mm, y[0], ln); y[0] -= gap * mm
    text(spec["title"], 14, True, gap=7); text(f"Official channel: {spec['official']}", 9, gap=6)
    text("GENERATED PREPARATION SHEET - DUMMY/TEST DATA - NOT SUBMITTED ANYWHERE", 8, gap=7)
    if spec.get("banner"):
        room(14); c.setFillGray(.9); c.rect(16 * mm, y[0] - 9 * mm, W - 32 * mm, 12 * mm, fill=1, stroke=0); c.setFillGray(0); y[0] -= 2 * mm
        text(spec["banner"], 9.5, True, 1, 4.5); y[0] -= 5 * mm
    known = set()
    for name, keys in spec["sections"]:
        room(20); text(name, 11, True, gap=6)
        for k in keys:
            known.add(k); v = str(data.get(k) or ""); text(f"{labels.get(k, k)}: {v if v else '______________________'}", 9.5, indent=3, gap=5)
        y[0] -= 3 * mm
    extra = [(k, str(v)) for k, v in data.items() if k not in known and not k.startswith("_") and k in labels]
    if extra:
        text("Additional details", 11, True, gap=6)
        for k, v in extra: text(f"{labels[k]}: {v}", 9.5, indent=3)
    for e in spec.get("extra", []): text(e, 9, gap=5)
    room(30); y[0] -= 4 * mm; text("DOCUMENT CHECKLIST", 12, True, gap=7)
    for d in svc["documents"]: text(("[ ]  " if d["required"] else "[ ]  (optional) ") + d["label"], 9.5, indent=3)
    fee = svc.get("fee") or {}
    if fee.get("note"): y[0] -= 2 * mm; text("Fee: " + fee["note"], 9)
    y[0] -= 3 * mm; text("Next steps: log in yourself on the official portal above, enter these details, upload the documents and submit there.", 9)
    text(f"Job {job_id}", 7); foot(); c.save(); return buf.getvalue()

_fill_claim = fill
def fill(service_id, data, case_number="", job_id=""):
    return fill_sheet(service_id, data, case_number, job_id) if service_id in SHEETS else _fill_claim(service_id, data, case_number, job_id)

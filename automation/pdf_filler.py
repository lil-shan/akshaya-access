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

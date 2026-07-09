"""
Renders a prescription record into a PDF document designed to look like a
real hospital-issued prescription, not a generic demo template:

  - A thin double-rule "security border" around the page.
  - A proper letterhead (doctor + hospital identity).
  - A classic "Rx" symbol before the medicines table.
  - The doctor's saved signature image, not a placeholder line.
  - A QR code linking to the public verification page, plus a short
    human-readable fingerprint of the content hash so someone can
    sanity-check by eye without even scanning the code.

This file only renders. It does not touch the database or encryption.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Any

import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from ..core.config import settings

PAGE_W, PAGE_H = A4

INK = HexColor("#1a1a18")
MUTED = HexColor("#5f5e5a")
ACCENT = HexColor("#0c447c")
LINE = HexColor("#b4b2a9")
PANEL = HexColor("#f6f5f1")
WARN_BG = HexColor("#faeeda")
WARN_TEXT = HexColor("#633806")


def render_prescription_pdf(prescription: dict[str, Any], doctor: Any, patient: Any) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    _draw_security_border(c)
    y = PAGE_H - 22 * mm
    y = _draw_letterhead(c, y, doctor)
    y -= 6 * mm
    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    c.line(18 * mm, y, PAGE_W - 18 * mm, y)
    y -= 8 * mm

    y = _draw_meta_row(c, y, prescription)
    y -= 6 * mm
    y = _draw_patient_panel(c, y, patient)
    y -= 10 * mm

    medicines = prescription.get("medicines") or []
    if medicines:
        y = _draw_rx_heading(c, y)
        y = _draw_medicines_table(c, y, medicines)
        y -= 6 * mm

    sick_note = prescription.get("sickNote")
    if sick_note:
        y = _draw_sick_note(c, y, sick_note)
        y -= 6 * mm

    doctor_notes = prescription.get("doctorNotes")
    if doctor_notes:
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(MUTED)
        c.drawString(18 * mm, y, f"Doctor's notes: {doctor_notes}")
        y -= 8 * mm

    _draw_footer(c, doctor, prescription)

    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_security_border(c: canvas.Canvas) -> None:
    c.setStrokeColor(LINE)
    c.setLineWidth(1.4)
    c.rect(10 * mm, 10 * mm, PAGE_W - 20 * mm, PAGE_H - 20 * mm)
    c.setLineWidth(0.4)
    c.rect(12 * mm, 12 * mm, PAGE_W - 24 * mm, PAGE_H - 24 * mm)


def _draw_letterhead(c: canvas.Canvas, y: float, doctor: Any) -> float:
    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(INK)
    c.drawString(18 * mm, y, doctor.displayName or doctor.name)

    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    sub_y = y - 5.5 * mm
    if doctor.specialization:
        c.drawString(18 * mm, sub_y, doctor.specialization)
        sub_y -= 4.2 * mm
    if doctor.registrationNumber:
        c.drawString(18 * mm, sub_y, f"Registration no. {doctor.registrationNumber}")
        sub_y -= 4.2 * mm

    if doctor.hospitalName:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(INK)
        c.drawRightString(PAGE_W - 18 * mm, y, doctor.hospitalName)
        c.setFont("Helvetica", 9)
        c.setFillColor(MUTED)
        if doctor.hospitalLocation:
            c.drawRightString(PAGE_W - 18 * mm, y - 5.5 * mm, doctor.hospitalLocation)

    return min(sub_y, y - 11 * mm)


def _draw_meta_row(c: canvas.Canvas, y: float, prescription: dict[str, Any]) -> float:
    c.setFont("Helvetica", 8.5)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, y, "Prescription no.")
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(INK)
    c.drawString(45 * mm, y, prescription.get("prescriptionNumber", ""))

    issued_at = str(prescription.get("issuedAt") or "")[:19].replace("T", "  ")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - 18 * mm, y, f"Issued {issued_at} UTC")
    return y - 6 * mm


def _draw_patient_panel(c: canvas.Canvas, y: float, patient: Any) -> float:
    box_h = 14 * mm
    c.setFillColor(PANEL)
    c.rect(18 * mm, y - box_h, PAGE_W - 36 * mm, box_h, stroke=0, fill=1)

    cols = [
        ("Patient", getattr(patient, "name", None)),
        ("Age", _format_age(getattr(patient, "dob", None))),
        ("Patient ID", getattr(patient, "username", None)),
        ("Gender", getattr(patient, "gender", None) or "-"),
    ]
    col_w = (PAGE_W - 36 * mm) / len(cols)
    for i, (label, value) in enumerate(cols):
        x = 18 * mm + i * col_w + 4 * mm
        c.setFont("Helvetica", 8)
        c.setFillColor(MUTED)
        c.drawString(x, y - 5 * mm, label)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(x, y - 10.5 * mm, str(value or "-"))

    return y - box_h


def _format_age(dob_value: Any) -> str:
    if not dob_value:
        return "-"

    if isinstance(dob_value, str):
        try:
            dob = datetime.fromisoformat(dob_value.replace("Z", "+00:00"))
        except ValueError:
            return "-"
    elif isinstance(dob_value, datetime):
        dob = dob_value
    else:
        return "-"

    today = datetime.now(dob.tzinfo) if getattr(dob, "tzinfo", None) else datetime.now()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return f"{age} years" if age >= 0 else "-"


def _draw_rx_heading(c: canvas.Canvas, y: float) -> float:
    c.setFont("Times-Bold", 18)
    c.setFillColor(ACCENT)
    c.drawString(18 * mm, y, "Rx")
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawString(28 * mm, y + 1 * mm, "Medicines")
    return y - 8 * mm


def _draw_medicines_table(c: canvas.Canvas, y: float, medicines: list[dict[str, Any]]) -> float:
    col_x = [18 * mm, 78 * mm, 108 * mm, 145 * mm, 192 * mm]
    headers = ["Medicine", "Dosage", "Frequency", "Duration"]

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(MUTED)
    for i, h in enumerate(headers):
        c.drawString(col_x[i], y, h)
    y -= 3 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(18 * mm, y, PAGE_W - 18 * mm, y)
    y -= 6 * mm

    c.setFont("Helvetica", 9.5)
    for idx, m in enumerate(medicines):
        if idx % 2 == 1:
            c.setFillColor(PANEL)
            c.rect(18 * mm, y - 3.5 * mm, PAGE_W - 36 * mm, 7.5 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.drawString(col_x[0], y, str(m.get("name", ""))[:34])
        c.drawString(col_x[1], y, str(m.get("dosage", ""))[:18])
        c.drawString(col_x[2], y, str(m.get("frequency", ""))[:18])
        c.drawString(col_x[3], y, str(m.get("duration", ""))[:18])
        if m.get("notes"):
            y -= 4.6 * mm
            c.setFont("Helvetica-Oblique", 7.5)
            c.setFillColor(MUTED)
            c.drawString(col_x[0], y, f"-> {m['notes']}"[:80])
            c.setFont("Helvetica", 9.5)
        y -= 7.5 * mm

    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(18 * mm, y + 3 * mm, PAGE_W - 18 * mm, y + 3 * mm)
    return y


def _draw_sick_note(c: canvas.Canvas, y: float, sick_note: dict[str, Any]) -> float:
    box_h = 13 * mm
    c.setFillColor(WARN_BG)
    c.rect(18 * mm, y - box_h, PAGE_W - 36 * mm, box_h, stroke=0, fill=1)
    c.setFillColor(WARN_TEXT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(21 * mm, y - 5 * mm, "Sick note / fitness certificate")
    c.setFont("Helvetica", 8.5)
    start = sick_note.get("startDate", "")
    end = sick_note.get("endDate", "")
    c.drawString(21 * mm, y - 9.5 * mm, f"{sick_note.get('reason', '')} - rest advised {start} to {end}")
    return y - box_h


def _draw_footer(c: canvas.Canvas, doctor: Any, prescription: dict[str, Any]) -> None:
    footer_y = 30 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(18 * mm, footer_y + 20 * mm, PAGE_W - 18 * mm, footer_y + 20 * mm)

    sig_x = PAGE_W - 70 * mm
    sig_b64 = getattr(doctor, "signatureImageBase64", None)
    if sig_b64:
        try:
            if "," in sig_b64:
                sig_b64 = sig_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(sig_b64)
            img = ImageReader(io.BytesIO(img_bytes))
            c.drawImage(
                img, sig_x, footer_y + 12 * mm, width=45 * mm, height=15 * mm,
                preserveAspectRatio=True, anchor="s", mask="auto",
            )
        except Exception:
            pass

    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.line(sig_x, footer_y + 11 * mm, sig_x + 45 * mm, footer_y + 11 * mm)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawString(sig_x, footer_y + 8 * mm, f"Digitally signed by {doctor.name}")
    if doctor.registrationNumber:
        c.drawString(sig_x, footer_y + 5 * mm, f"Reg. no. {doctor.registrationNumber}")

    qr_token = prescription.get("qrToken", "")
    verify_url = f"{settings.frontend_base_url.rstrip('/')}/verify/{qr_token}"
    qr_img = qrcode.make(verify_url, border=1)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    c.drawImage(ImageReader(qr_buf), 18 * mm, footer_y, width=20 * mm, height=20 * mm)
    c.setFont("Helvetica", 6.7)
    c.setFillColor(MUTED)
    c.drawString(41 * mm, footer_y + 15 * mm, "Scan to verify authenticity")
    c.drawString(41 * mm, footer_y + 11.5 * mm, "and confirm this document")
    c.drawString(41 * mm, footer_y + 8 * mm, "has not been altered.")

    content_hash = str(prescription.get("contentHash") or "")
    fingerprint = " ".join(content_hash[i:i + 4] for i in range(0, min(16, len(content_hash)), 4))
    c.setFont("Courier", 6.5)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, footer_y - 4 * mm, f"Fingerprint {fingerprint}...")

    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(MUTED)
    c.drawCentredString(
        PAGE_W / 2,
        13 * mm,
        "This is a digitally signed document. Any alteration to its contents invalidates the signature above.",
    )

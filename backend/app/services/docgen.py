import io
from datetime import date, datetime, timedelta

import cv2
import numpy as np
import pikepdf
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.providers import sandbox_data

FOOTER = "SYNTHETIC SPECIMEN generated for demonstration. Not a real document."


def money(value: float) -> str:
    return f"INR {value:,.2f}"


def render_pdf(title: str, rows: list[tuple[str, str]], producer: str, edited_labels: frozenset = frozenset(), modified_days: int = 0) -> bytes:
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    page.setFont("Helvetica-Bold", 16)
    page.drawString(50, height - 70, title)
    page.line(50, height - 80, width - 50, height - 80)
    y = height - 110
    for label, value in rows:
        if label == "---":
            y -= 8
            continue
        page.setFont("Helvetica", 11)
        prefix = f"{label}: "
        page.drawString(50, y, prefix)
        x = 50 + stringWidth(prefix, "Helvetica", 11)
        if label in edited_labels:
            page.setFont("Courier-Bold", 11)
        page.drawString(x, y, value)
        y -= 18
    page.setFont("Helvetica-Oblique", 8)
    page.drawString(50, 40, FOOTER)
    page.showPage()
    page.save()
    created = datetime.combine(date.today(), datetime.min.time()) - timedelta(days=3)
    return set_metadata(buffer.getvalue(), producer, created, created + timedelta(days=modified_days))


def set_metadata(data: bytes, producer: str, created: datetime, modified: datetime) -> bytes:
    pdf = pikepdf.open(io.BytesIO(data))
    stamp = lambda moment: "D:" + moment.strftime("%Y%m%d%H%M%S") + "+05'30'"
    pdf.docinfo["/Producer"] = producer
    pdf.docinfo["/Creator"] = producer
    pdf.docinfo["/CreationDate"] = stamp(created)
    pdf.docinfo["/ModDate"] = stamp(modified)
    output = io.BytesIO()
    pdf.save(output)
    return output.getvalue()


def salary_components(net: float) -> dict:
    gross = round(net * 1.13 / 100) * 100
    basic = round(gross * 0.40)
    hra = round(gross * 0.16)
    special = gross - basic - hra
    pf = round(basic * 0.12)
    professional_tax = 200
    tds = gross - net - pf - professional_tax
    return {"basic": basic, "hra": hra, "special": special, "gross": gross, "pf": pf, "pt": professional_tax, "tds": tds, "deductions": pf + professional_tax + tds, "net": net}


def to_scan(pdf_bytes: bytes, skew_degrees: float = 1.2) -> bytes:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pixmap = doc[0].get_pixmap(dpi=200)
    image = cv2.imdecode(np.frombuffer(pixmap.tobytes("png"), dtype=np.uint8), cv2.IMREAD_COLOR)
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), skew_degrees, 1.0)
    image = cv2.warpAffine(image, matrix, (width, height), borderValue=(255, 255, 255))
    noise = np.random.default_rng(7).normal(0, 6, image.shape).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    return encoded.tobytes()


def make_document(doc_type: str, application: dict, applicant: dict, edited: bool = False) -> bytes:
    employer = applicant.get("employer") or "Sample Employer Pvt Ltd"
    name = applicant["full_name"]
    pan = applicant["pan"]
    survey = application["survey_no"]
    address = application.get("property_address") or application["property_city"]
    income = float(applicant["monthly_income"])
    factor = sandbox_data.bank_profile(applicant)["income_factor"]
    period = (date.today().replace(day=1) - timedelta(days=1)).strftime("%B %Y")
    if doc_type == "PAN":
        return render_pdf("INCOME TAX DEPARTMENT - PERMANENT ACCOUNT NUMBER CARD", [
            ("Name", name.upper()), ("Date of Birth", str(applicant["dob"])), ("Permanent Account Number", pan)], "ITD-eFiling-Export")
    if doc_type in ("ADDRESS_PROOF", "IDENTITY_PROOF"):
        title = "ADDRESS PROOF - UTILITY ACCOUNT STATEMENT" if doc_type == "ADDRESS_PROOF" else "IDENTITY PROOF - OFFLINE VERIFICATION SUMMARY"
        return render_pdf(title, [("Name", name), ("Address", applicant.get("address") or applicant.get("city") or "-"), ("Document Reference", "SPECIMEN-" + pan[5:9])], "Specimen-PDF")
    if doc_type == "SALARY_SLIP":
        if edited:
            honest = salary_components(round(income * factor))
            gross_shown = round(income * 1.13 / 100) * 100
            rows = [("Employee Name", name), ("PAN", pan), ("Employer", employer), ("Pay Period", period), ("---", ""),
                    ("Basic Pay", money(honest["basic"])), ("House Rent Allowance", money(honest["hra"])), ("Special Allowance", money(honest["special"])),
                    ("Gross Earnings", money(gross_shown)), ("---", ""), ("Provident Fund", money(honest["pf"])), ("Professional Tax", money(honest["pt"])),
                    ("Income Tax (TDS)", money(honest["tds"])), ("Total Deductions", money(gross_shown - income)), ("---", ""), ("Net Pay", money(income))]
            return render_pdf("PAYSLIP", rows, "Microsoft Word", frozenset({"Gross Earnings", "Total Deductions", "Net Pay"}), 2)
        g = salary_components(income)
        rows = [("Employee Name", name), ("PAN", pan), ("Employer", employer), ("Pay Period", period), ("---", ""),
                ("Basic Pay", money(g["basic"])), ("House Rent Allowance", money(g["hra"])), ("Special Allowance", money(g["special"])),
                ("Gross Earnings", money(g["gross"])), ("---", ""), ("Provident Fund", money(g["pf"])), ("Professional Tax", money(g["pt"])),
                ("Income Tax (TDS)", money(g["tds"])), ("Total Deductions", money(g["deductions"])), ("---", ""), ("Net Pay", money(g["net"]))]
        return render_pdf("PAYSLIP", rows, "HRMS-PayslipGen 4.2")
    if doc_type == "FORM16":
        g = salary_components(income)
        return render_pdf("FORM 16 - PART B SUMMARY", [("Employee Name", name), ("PAN", pan), ("Employer", employer), ("Assessment Year", "2026-27"),
                          ("Gross Salary (annual)", money(g["gross"] * 12)), ("Tax Deducted at Source (annual)", money(g["tds"] * 12))], "ITD-eFiling-Export")
    if doc_type == "ITR":
        declared = float(applicant.get("annual_itr_income") or income * 12)
        return render_pdf("INCOME TAX RETURN - ACKNOWLEDGEMENT SUMMARY", [("Assessee Name", name), ("PAN", pan), ("Assessment Year", "2026-27"),
                          ("Gross Total Income (annual)", money(declared)), ("Business Turnover (annual)", money(float(applicant.get("annual_turnover") or 0)))], "ITD-eFiling-Export")
    if doc_type == "BANK_STATEMENT":
        base = income if applicant["employment_type"] != "SELF_EMPLOYED" else float(applicant.get("annual_turnover") or income * 12) / 12
        return render_pdf("BANK STATEMENT - LAST 6 MONTHS", [("Account Holder", name), ("Bank", "Sample Bank (synthetic)"), ("Period", "Last 6 months"),
                          ("Average Monthly Credit", money(round(base * factor, 2))), ("Average Balance", money(120000.0)), ("Returned Cheques", str(sandbox_data.bank_profile(applicant)["bounces"]))], "Bank-eStatement")
    if doc_type == "GST_RETURN":
        return render_pdf("GST RETURN SUMMARY", [("Legal Name", employer or name), ("GSTIN", "33XXXXX" + pan[5:9] + "1Z5"), ("Turnover (Annual)", money(float(applicant.get("annual_turnover") or 0)))], "GST-Export")
    if doc_type == "BUSINESS_FINANCIALS":
        turnover = float(applicant.get("annual_turnover") or 0)
        return render_pdf("PROFIT AND LOSS STATEMENT - BUSINESS FINANCIAL SUMMARY", [("Name", name), ("Financial Year", "2025-26"), ("Turnover (Annual)", money(turnover)),
                          ("Net Profit (Annual)", money(float(applicant.get("annual_itr_income") or income * 12)))], "CA-Report")
    owner = application.get("owner_name") or name
    if doc_type == "SALE_AGREEMENT":
        return render_pdf("AGREEMENT FOR SALE", [("Seller", application.get("seller_name") or "Seller (synthetic)"), ("Buyer", name), ("Property", address), ("Survey No", survey),
                          ("Built-up Area", f"{application['property_area_sqft']} sq ft"), ("Sale Consideration", money(float(application["declared_value"])))], "Registrar-eDocs")
    if doc_type == "SALE_DEED":
        return render_pdf("TITLE DEED - CHAIN SUMMARY", [("Registered Owner", owner), ("Survey No", survey), ("Property", address), ("Last Registration", "2019-06-18")], "Registrar-eDocs")
    if doc_type == "ENCUMBRANCE_CERTIFICATE":
        charge = sandbox_data.profile_for(pan).get("cersai_charge")
        rows = [("Survey No", survey), ("Period Searched", "2016-01-01 to " + date.today().isoformat())]
        rows.append(("Subsisting Charge", f"Mortgage in favour of {charge['holder']} dated {charge['date']} for {money(charge['amount'])}") if charge else ("Result", "NIL - no subsisting encumbrance"))
        return render_pdf("ENCUMBRANCE CERTIFICATE", rows, "Registrar-eDocs")
    if doc_type == "VALUATION_REPORT":
        market = float(application["declared_value"])
        return render_pdf("PROPERTY VALUATION REPORT", [("Valuer", "Empanelled valuer (synthetic)"), ("Property", address), ("Survey No", survey),
                          ("Market Value", money(market)), ("Realisable Value", money(round(market * 0.92, 2))), ("Inspection", "Completed")], "Valuer-Portal")
    if doc_type == "LEGAL_REPORT":
        return render_pdf("LEGAL OPINION REPORT", [("Advocate", "Panel advocate (synthetic)"), ("Survey No", survey), ("Property", address), ("Title Opinion", "CLEAR AND MARKETABLE"), ("Litigation", "NIL")], "Advocate-Portal")
    if doc_type == "TECHNICAL_REPORT":
        return render_pdf("TECHNICAL INSPECTION REPORT", [("Engineer", "Panel engineer (synthetic)"), ("Survey No", survey), ("Property", address),
                          ("Construction Status", "Completed"), ("Structural Condition", "Satisfactory")], "Engineer-Portal")
    raise ValueError(f"No generator for {doc_type}")

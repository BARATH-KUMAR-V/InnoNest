import io
import re
from collections import Counter

import pikepdf
import pymupdf

from app.services import ocr
from app.services.catalog import DOC_TITLES, FIELD_LABELS, NUMERIC_FIELDS

AMOUNT = re.compile(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", re.I)
EDITING_TOOLS = ("word", "photoshop", "canva", "illustrator", "gimp", "libreoffice", "paint", "wps", "pdf editor")
LABEL_LOOKUP = {label: field for field, labels in FIELD_LABELS.items() for label in labels}
MIN_TEXT_LENGTH = 20
LOW_FIELD_CONFIDENCE = 0.80


def classify(text: str) -> str | None:
    upper = text.upper()
    for doc_type, titles in DOC_TITLES.items():
        if any(title in upper for title in titles):
            return doc_type
    return None


def parse_number(value: str) -> float | None:
    match = AMOUNT.search(value)
    cleaned = match.group(1) if match else value
    cleaned = cleaned.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_fields(text: str, confidence: float) -> list[dict]:
    fields = []
    seen = set()
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        field = LABEL_LOOKUP.get(label.strip().lower())
        value = value.strip()
        if not field or not value or field in seen:
            continue
        seen.add(field)
        numeric = parse_number(value) if field in NUMERIC_FIELDS else None
        fields.append({"name": field, "value": value, "numeric_value": numeric, "confidence": confidence})
    return fields


def font_spans(page) -> list[tuple[str, str]]:
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if AMOUNT.search(span["text"]):
                    spans.append((span["text"], span["font"]))
    return spans


def metadata_findings(data: bytes) -> tuple[dict, list[dict]]:
    findings = []
    try:
        pdf = pikepdf.open(io.BytesIO(data))
        info = pdf.docinfo
        producer = str(info.get("/Producer", ""))
        created = str(info.get("/CreationDate", ""))
        modified = str(info.get("/ModDate", ""))
        meta = {"producer": producer, "created": created, "modified": modified}
        if any(tool in producer.lower() for tool in EDITING_TOOLS):
            findings.append({"id": "DOC-META-PRODUCER", "severity": "MEDIUM", "text": f"The PDF was last saved by '{producer}', which is a general editing tool.", "evidence": producer})
        if created and modified and created[2:10] != modified[2:10]:
            findings.append({"id": "DOC-META-MODIFIED", "severity": "MEDIUM", "text": f"The modified date ({modified[2:10]}) differs from the creation date ({created[2:10]}).", "evidence": [created, modified]})
        return meta, findings
    except Exception:
        return {}, findings


def arithmetic_findings(doc_type: str, values: dict) -> list[dict]:
    findings = []
    if doc_type != "SALARY_SLIP" or not all(k in values for k in ("basic", "gross", "total_deductions", "net_pay")):
        return findings
    components = values["basic"] + values.get("hra", 0) + values.get("special_allowance", 0)
    if abs(components - values["gross"]) > 2:
        findings.append({"id": "DOC-ARITH-GROSS", "severity": "HIGH", "text": f"The earnings lines add up to {components:,.0f} but gross earnings show {values['gross']:,.0f}.", "evidence": [components, values["gross"]]})
    if abs(values["gross"] - values["total_deductions"] - values["net_pay"]) > 2:
        findings.append({"id": "DOC-ARITH-NET", "severity": "HIGH", "text": "Gross earnings minus total deductions does not equal net pay.", "evidence": [values["gross"], values["total_deductions"], values["net_pay"]]})
    deductions = values.get("pf", 0) + values.get("professional_tax", 0) + values.get("tds", 0)
    if abs(deductions - values["total_deductions"]) > 2:
        findings.append({"id": "DOC-ARITH-DED", "severity": "HIGH", "text": f"The deduction lines add up to {deductions:,.0f} but total deductions show {values['total_deductions']:,.0f}.", "evidence": [deductions, values["total_deductions"]]})
    return findings


def rendered_net_pay(page) -> float | None:
    pixmap = page.get_pixmap(dpi=170)
    text, _ = ocr.read_text(ocr.pixmap_to_image(pixmap.tobytes("png")))
    match = re.search(r"Net\s*Pay[^\d]{0,12}([\d,]+(?:\.\d+)?)", text, re.I)
    return float(match.group(1).replace(",", "")) if match else None


def read_pdf(data: bytes) -> dict:
    result = {"text": "", "pages": 0, "ocr_used": False, "confidence": 0.0, "findings": [], "metadata": {}, "page": None, "doc": None}
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        result["findings"].append({"id": "DOC-UNREADABLE", "severity": "HIGH", "text": "The file could not be opened as a PDF.", "evidence": None})
        return result
    result["pages"] = doc.page_count
    result["doc"] = doc
    if doc.is_encrypted or doc.page_count == 0:
        result["findings"].append({"id": "DOC-UNREADABLE", "severity": "HIGH", "text": "The PDF is encrypted or has no pages.", "evidence": None})
        return result
    text = "\n".join(doc[i].get_text() for i in range(min(doc.page_count, 5)))
    result["confidence"] = 0.99
    if len(text.strip()) < MIN_TEXT_LENGTH:
        pieces, confidences = [], []
        for index in range(min(doc.page_count, 3)):
            pixmap = doc[index].get_pixmap(dpi=200)
            page_text, page_conf = ocr.read_text(ocr.pixmap_to_image(pixmap.tobytes("png")))
            pieces.append(page_text)
            confidences.append(page_conf)
        text = "\n".join(pieces)
        result["ocr_used"] = True
        result["confidence"] = sum(confidences) / len(confidences) if confidences else 0.0
    result["text"] = text
    result["metadata"], meta_findings = metadata_findings(data)
    result["findings"].extend(meta_findings)
    return result


def read_image(data: bytes) -> dict:
    result = {"text": "", "pages": 1, "ocr_used": True, "confidence": 0.0, "findings": [], "metadata": {}, "page": None, "doc": None}
    image = ocr.decode_image(data)
    if image is None:
        result["findings"].append({"id": "DOC-UNREADABLE", "severity": "HIGH", "text": "The file could not be decoded as an image.", "evidence": None})
        return result
    import cv2
    result["metadata"] = {"width": int(image.shape[1]), "height": int(image.shape[0]), "sharpness": round(ocr.sharpness(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)), 1)}
    if result["metadata"]["sharpness"] < 40:
        result["findings"].append({"id": "DOC-BLURRY", "severity": "MEDIUM", "text": "The image is blurry. A sharper scan or photo will read more reliably.", "evidence": result["metadata"]["sharpness"]})
    result["text"], result["confidence"] = ocr.read_text(image)
    return result


def analyse(data: bytes, extension: str, check_rendered_values: bool = True) -> dict:
    extension = extension.lower().lstrip(".")
    raw = read_pdf(data) if extension == "pdf" else read_image(data)
    findings = raw["findings"]
    text = raw["text"]
    doc_type = classify(text)
    fields = parse_fields(text, raw["confidence"]) if doc_type else []
    values = {f["name"]: f["numeric_value"] for f in fields if f["numeric_value"] is not None}
    findings.extend(arithmetic_findings(doc_type or "", values))
    page_doc = raw.pop("doc")
    if page_doc is not None and doc_type and raw["pages"] and not raw["ocr_used"]:
        spans = font_spans(page_doc[0])
        if len(spans) >= 3:
            majority = Counter(font for _, font in spans).most_common(1)[0][0]
            odd = [text_ for text_, font in spans if font != majority]
            if odd:
                findings.append({"id": "DOC-FONT-MISMATCH", "severity": "HIGH", "text": f"{len(odd)} amount(s) use a different typeface from the rest of the page, which can indicate an edit.", "evidence": odd[:3]})
        if check_rendered_values and doc_type == "SALARY_SLIP" and "net_pay" in values:
            rendered = rendered_net_pay(page_doc[0])
            if rendered is not None and abs(rendered - values["net_pay"]) > 0.01 * values["net_pay"]:
                findings.append({"id": "DOC-OCR-MISMATCH", "severity": "HIGH", "text": f"The rendered page reads net pay {rendered:,.0f} but the text layer says {values['net_pay']:,.0f}.", "evidence": [rendered, values["net_pay"]]})
    if len(text.strip()) < MIN_TEXT_LENGTH and not any(f["id"] == "DOC-UNREADABLE" for f in findings):
        findings.append({"id": "DOC-UNREADABLE", "severity": "HIGH", "text": "No readable text could be extracted from this file.", "evidence": None})
    elif doc_type is None and not any(f["id"] == "DOC-UNREADABLE" for f in findings):
        findings.append({"id": "DOC-UNCLASSIFIED", "severity": "MEDIUM", "text": "The document type could not be identified from its content.", "evidence": None})
    low = [f["name"] for f in fields if f["confidence"] < LOW_FIELD_CONFIDENCE]
    if low:
        findings.append({"id": "DOC-LOW-CONFIDENCE", "severity": "MEDIUM", "text": f"{len(low)} field(s) were read with low confidence and should be confirmed.", "evidence": low[:8]})
    unreadable = any(f["id"] == "DOC-UNREADABLE" for f in findings)
    if unreadable:
        status = "UNREADABLE"
    elif any(f["severity"] == "HIGH" for f in findings):
        status = "INTEGRITY_INDICATOR"
    elif findings:
        status = "NEEDS_REVIEW"
    else:
        status = "EXTRACTED"
    return {"detected_type": doc_type, "fields": fields, "findings": findings, "status": status, "confidence": round(raw["confidence"], 3),
            "page_count": raw["pages"], "ocr_used": raw["ocr_used"], "metadata": raw["metadata"], "text_excerpt": text[:2000]}

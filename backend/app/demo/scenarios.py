from dataclasses import dataclass, field

from app.services import docgen
from app.services.catalog import DOC_LABELS

ALL_CONSENTS = {"data_processing": True, "kyc": True, "credit_bureau": True, "bank_statement": True}


@dataclass
class Scenario:
    key: str
    title: str
    description: str
    expected: str
    application: dict
    omit: list[str] = field(default_factory=list)
    edited_slip: bool = False


def applicant(name: str, dob: str, pan: str, employment: str, income: float, **extra) -> dict:
    base = {"role": "PRIMARY", "full_name": name, "dob": dob, "pan": pan, "phone": "98765" + pan[5:9][::-1].ljust(5, "0")[:5], "email": name.lower().replace(" ", ".") + "@example.com",
            "address": "14 Lakeview Road, Adyar", "city": "Chennai", "employment_type": employment, "employer": "Meridian Software Pvt Ltd" if employment != "SELF_EMPLOYED" else "",
            "years_in_job": 5, "monthly_income": income, "other_income": 0, "existing_emi": 0}
    base.update(extra)
    return base


def home_loan(applicants: list[dict], loan: float, rate: float, months: int, value: float, **extra) -> dict:
    base = {"product": "HOME_LOAN", "loan_amount": loan, "interest_rate": rate, "tenure_months": months, "purpose": "Purchase of residence", "property_type": "APARTMENT",
            "property_city": "Chennai", "property_address": "Flat 4B, Palm Grove Apartments, Velachery", "property_pincode": "600042", "property_area_sqft": 1150, "survey_no": "142/3A",
            "declared_value": value, "seller_name": "Seller Constructions Pvt Ltd", "owner_name": "Seller Constructions Pvt Ltd", "applicants": applicants}
    base.update(extra)
    return base


def lap(applicants: list[dict], loan: float, rate: float, months: int, value: float, owner: str, **extra) -> dict:
    base = {"product": "LAP", "loan_amount": loan, "interest_rate": rate, "tenure_months": months, "purpose": "Business expansion", "end_use": "BUSINESS_EXPANSION",
            "property_type": "COMMERCIAL", "property_subtype": "COMMERCIAL", "property_city": "Coimbatore", "property_address": "Unit 12, Trade Centre, RS Puram", "property_pincode": "641002",
            "property_area_sqft": 2200, "survey_no": "88/1B", "declared_value": value, "owner_name": owner, "applicants": applicants}
    base.update(extra)
    return base


SCENARIOS = {
    "clean_home_loan": Scenario("clean_home_loan", "Clean salaried home loan", "Complete application with consistent evidence and comfortable ratios.", "APPROVED",
                                home_loan([applicant("Priya Raman", "1990-03-14", "ASHPR1234A", "SALARIED", 95000, existing_emi=3000)], 4500000, 8.5, 240, 6000000)),
    "high_foir": Scenario("high_foir", "Stretched repayment capacity", "Rejected under Balanced and Conservative, approved under Flexible. Useful for the policy comparison.", "REJECTED",
                          home_loan([applicant("Karthik Subramanian", "1988-07-22", "BMNKS2345B", "SALARIED", 75000, existing_emi=10000, years_in_job=4)], 3800000, 8.75, 240, 5500000)),
    "tampered_slip": Scenario("tampered_slip", "Salary slip edited after issue", "Salary slip shows edit indicators and bank credits are well below the slip. Referred for review.", "REFERRED",
                              home_loan([applicant("Meera Nair", "1988-11-05", "CQRTV3456C", "SALARIED", 80000, existing_emi=2000)], 2500000, 8.6, 240, 5000000), edited_slip=True),
    "aml_potential_match": Scenario("aml_potential_match", "Potential sanctions or PEP match", "Name and date of birth match a synthetic watchlist entry. Referred to authorised AML review.", "REFERRED",
                                    home_loan([applicant("Rohan Mehra", "1971-04-09", "DRNMH4567D", "SALARIED", 120000, years_in_job=12)], 2000000, 8.4, 48, 4500000)),
    "lap_encumbered": Scenario("lap_encumbered", "LAP on a mortgaged property", "The encumbrance certificate and security interest search show a subsisting charge. Referred.", "REFERRED",
                               lap([applicant("Suresh Babu Lakshmanan", "1979-01-30", "EVLSB5678E", "SELF_EMPLOYED", 220000, business_type="Manufacturing", annual_turnover=22000000, annual_itr_income=2640000, years_in_job=9)],
                                   5000000, 10.5, 120, 11000000, "Suresh Babu Lakshmanan")),
    "weak_credit": Scenario("weak_credit", "Weak credit history", "Credit score and recent delinquency fall below policy floors. Rejected.", "REJECTED",
                            home_loan([applicant("Anita Gopalan", "1993-09-18", "FTGKA6789F", "SALARIED", 85000, years_in_job=3)], 3000000, 8.75, 240, 4500000)),
    "clean_lap": Scenario("clean_lap", "Clean LAP for a business owner", "Self-employed borrower with ITR, GST and bank evidence that agree. Approved.", "APPROVED",
                          lap([applicant("Vikram Desai", "1984-05-27", "GHPQW7890G", "SELF_EMPLOYED", 250000, business_type="Trading", annual_turnover=24000000, annual_itr_income=3000000, years_in_job=11)],
                              5000000, 10.5, 120, 12000000, "Vikram Desai")),
    "incomplete_application": Scenario("incomplete_application", "Missing salary slip and bank statement", "Submitted without two documents. Enters ACTION_REQUIRED, then resumes after upload.", "ACTION_REQUIRED",
                                       home_loan([applicant("Lakshmi Venkatesan", "1991-12-02", "HJRDS8901H", "SALARIED", 90000, existing_emi=4000, years_in_job=6)], 4000000, 8.5, 240, 5500000),
                                       omit=["SALARY_SLIP", "BANK_STATEMENT"]),
}


def required_types(application: dict) -> list[tuple[str, int]]:
    items = []
    for index, person in enumerate(application["applicants"]):
        items += [("PAN", index), ("ADDRESS_PROOF", index)]
        if person["employment_type"] in ("SALARIED", "GOVT"):
            items += [("SALARY_SLIP", index), ("BANK_STATEMENT", index), ("FORM16", index)]
        else:
            items += [("ITR", index), ("BANK_STATEMENT", index), ("BUSINESS_FINANCIALS", index)]
            if person.get("annual_turnover"):
                items.append(("GST_RETURN", index))
    items.append(("SALE_AGREEMENT" if application["product"] == "HOME_LOAN" else "SALE_DEED", 0))
    items += [("ENCUMBRANCE_CERTIFICATE", 0), ("VALUATION_REPORT", 0)]
    if application["loan_amount"] >= (5_000_000 if application["product"] == "HOME_LOAN" else 0):
        items += [("LEGAL_REPORT", 0), ("TECHNICAL_REPORT", 0)]
    return items


def generate_documents(scenario: Scenario, only: list[str] | None = None) -> list[dict]:
    application = scenario.application
    flat = {**application, "property_area_sqft": application["property_area_sqft"]}
    out = []
    for doc_type, index in required_types(application):
        if only is not None and doc_type not in only:
            continue
        if only is None and doc_type in scenario.omit:
            continue
        person = application["applicants"][index]
        edited = scenario.edited_slip and doc_type == "SALARY_SLIP"
        content = docgen.make_document(doc_type, flat, person, edited)
        out.append({"doc_type": doc_type, "applicant_index": index, "filename": f"{doc_type.lower()}_{index + 1}.pdf", "content": content, "label": DOC_LABELS[doc_type]})
    return out

DOC_LABELS = {
    "PAN": "PAN card",
    "ADDRESS_PROOF": "Address proof",
    "IDENTITY_PROOF": "Identity proof",
    "SALARY_SLIP": "Latest salary slip",
    "BANK_STATEMENT": "Bank statement (last 6 months)",
    "FORM16": "Form 16",
    "ITR": "Income tax return",
    "GST_RETURN": "GST return summary",
    "BUSINESS_FINANCIALS": "Business financial statements",
    "SALE_AGREEMENT": "Agreement for sale",
    "SALE_DEED": "Sale deed or title deed",
    "ENCUMBRANCE_CERTIFICATE": "Encumbrance certificate",
    "VALUATION_REPORT": "Property valuation report",
    "LEGAL_REPORT": "Legal opinion report",
    "TECHNICAL_REPORT": "Technical inspection report",
}

DOC_TITLES = {
    "PAN": ("PERMANENT ACCOUNT NUMBER",),
    "ADDRESS_PROOF": ("ADDRESS PROOF", "PROOF OF ADDRESS"),
    "IDENTITY_PROOF": ("IDENTITY PROOF", "PROOF OF IDENTITY"),
    "SALARY_SLIP": ("PAYSLIP", "SALARY SLIP"),
    "BANK_STATEMENT": ("BANK STATEMENT", "STATEMENT OF ACCOUNT"),
    "FORM16": ("FORM 16",),
    "ITR": ("INCOME TAX RETURN",),
    "GST_RETURN": ("GST RETURN",),
    "BUSINESS_FINANCIALS": ("PROFIT AND LOSS", "BUSINESS FINANCIAL"),
    "SALE_AGREEMENT": ("AGREEMENT FOR SALE",),
    "SALE_DEED": ("TITLE DEED", "SALE DEED"),
    "ENCUMBRANCE_CERTIFICATE": ("ENCUMBRANCE CERTIFICATE",),
    "VALUATION_REPORT": ("VALUATION REPORT",),
    "LEGAL_REPORT": ("LEGAL OPINION",),
    "TECHNICAL_REPORT": ("TECHNICAL INSPECTION",),
}

FIELD_LABELS = {
    "name": ("name", "employee name", "assessee name", "account holder", "applicant name", "registered owner name"),
    "pan": ("pan", "permanent account number"),
    "dob": ("date of birth", "dob"),
    "father_name": ("father's name",),
    "address": ("address", "residential address"),
    "document_reference": ("document reference",),
    "employer": ("employer",),
    "pay_period": ("pay period",),
    "basic": ("basic pay",),
    "hra": ("house rent allowance",),
    "special_allowance": ("special allowance",),
    "gross": ("gross earnings", "gross salary (annual)"),
    "pf": ("provident fund",),
    "professional_tax": ("professional tax",),
    "tds": ("income tax (tds)", "tax deducted at source (annual)"),
    "total_deductions": ("total deductions",),
    "net_pay": ("net pay",),
    "assessment_year": ("assessment year",),
    "gross_total_income": ("gross total income (annual)",),
    "turnover": ("business turnover (annual)", "turnover (annual)"),
    "net_profit": ("net profit (annual)",),
    "financial_year": ("financial year",),
    "bank": ("bank",),
    "period": ("period", "period searched"),
    "average_monthly_credit": ("average monthly credit",),
    "average_balance": ("average balance",),
    "returned_cheques": ("returned cheques",),
    "gstin": ("gstin",),
    "legal_name": ("legal name",),
    "seller": ("seller",),
    "buyer": ("buyer",),
    "property": ("property",),
    "survey_no": ("survey no",),
    "area": ("built-up area",),
    "sale_consideration": ("sale consideration",),
    "stamp_duty": ("stamp duty and registration",),
    "registered_owner": ("registered owner",),
    "last_registration": ("last registration",),
    "encumbrance_result": ("result",),
    "subsisting_charge": ("subsisting charge",),
    "valuer": ("valuer",),
    "market_value": ("market value",),
    "realisable_value": ("realisable value",),
    "inspection": ("inspection",),
    "advocate": ("advocate",),
    "title_opinion": ("title opinion",),
    "litigation": ("litigation",),
    "engineer": ("engineer",),
    "construction_status": ("construction status",),
    "structural_condition": ("structural condition",),
}

NUMERIC_FIELDS = {
    "basic", "hra", "special_allowance", "gross", "pf", "professional_tax", "tds", "total_deductions", "net_pay", "gross_total_income",
    "turnover", "net_profit", "average_monthly_credit", "average_balance", "sale_consideration", "stamp_duty", "market_value", "realisable_value",
}

REQUIRED_CONSENTS = {
    "data_processing": "Processing of my application data for underwriting",
    "kyc": "KYC and identity verification, including authorised Aadhaar offline verification",
    "credit_bureau": "Retrieval of my credit report from credit information companies",
    "bank_statement": "Retrieval of bank statements through an Account Aggregator",
}

STATUSES = ("DRAFT", "SUBMITTED", "PROCESSING", "ACTION_REQUIRED", "DOCUMENTS_RECEIVED", "VERIFICATION_PENDING", "REFERRED", "APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN")
OPEN_STATUSES = ("SUBMITTED", "PROCESSING", "ACTION_REQUIRED", "DOCUMENTS_RECEIVED", "VERIFICATION_PENDING", "REFERRED")
FINAL_STATUSES = ("APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN")
EDITABLE_STATUSES = ("DRAFT", "ACTION_REQUIRED")

EMPLOYMENT_TYPES = ("SALARIED", "GOVT", "SELF_EMPLOYED")
PRODUCTS = ("HOME_LOAN", "LAP")
LAP_END_USES = ("BUSINESS_EXPANSION", "WORKING_CAPITAL", "EDUCATION", "MEDICAL", "DEBT_CONSOLIDATION", "PERSONAL", "SPECULATIVE_INVESTMENT")
PROPERTY_TYPES = ("APARTMENT", "INDEPENDENT_HOUSE", "PLOT", "COMMERCIAL", "AGRICULTURAL")

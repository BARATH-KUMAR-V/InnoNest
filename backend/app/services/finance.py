from datetime import date

from app.core.errors import invalid

NO_CAPACITY = 9.99


def check_loan_inputs(principal: float, annual_rate_pct: float, months: int) -> None:
    problems = []
    if principal is None or principal <= 0:
        problems.append({"field": "loan_amount", "message": "Loan amount must be greater than zero"})
    if annual_rate_pct is None or annual_rate_pct < 0 or annual_rate_pct > 40:
        problems.append({"field": "interest_rate", "message": "Interest rate must be between 0 and 40 percent a year"})
    if months is None or months <= 0 or months > 480:
        problems.append({"field": "tenure_months", "message": "Tenure must be between 1 and 480 months"})
    if problems:
        raise invalid("The loan inputs are not valid", problems)


def emi(principal: float, annual_rate_pct: float, months: int) -> float:
    check_loan_inputs(principal, annual_rate_pct, months)
    r = annual_rate_pct / 1200.0
    if r == 0:
        return principal / months
    growth = (1 + r) ** months
    return principal * r * growth / (growth - 1)


def max_principal(emi_capacity: float, annual_rate_pct: float, months: int) -> float:
    if emi_capacity <= 0 or months <= 0 or annual_rate_pct < 0:
        return 0.0
    r = annual_rate_pct / 1200.0
    if r == 0:
        return emi_capacity * months
    growth = (1 + r) ** months
    return emi_capacity * (growth - 1) / (r * growth)


def foir(existing_emi: float, proposed_emi: float, eligible_income: float) -> float:
    if eligible_income is None or eligible_income <= 0:
        return NO_CAPACITY
    return (max(existing_emi, 0) + proposed_emi) / eligible_income


def ltv(total_exposure: float, accepted_value: float) -> float:
    if accepted_value is None or accepted_value <= 0:
        return NO_CAPACITY
    return total_exposure / accepted_value


def max_eligible_emi(eligible_income: float, existing_emi: float, foir_limit: float) -> float:
    return max(0.0, eligible_income * foir_limit - max(existing_emi, 0))


def amortization(principal: float, annual_rate_pct: float, months: int) -> list[dict]:
    payment = emi(principal, annual_rate_pct, months)
    r = annual_rate_pct / 1200.0
    balance = principal
    rows = []
    for month in range(1, months + 1):
        interest = balance * r
        repaid = payment - interest
        balance = max(0.0, balance - repaid)
        rows.append({"month": month, "emi": round(payment, 2), "interest": round(interest, 2), "principal": round(repaid, 2), "balance": round(balance, 2)})
    return rows


def age_on(dob: date, on: date) -> float:
    return (on - dob).days / 365.25


def inr(value: float) -> str:
    n = int(round(value))
    digits = str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + "INR " + digits


def round2(value: float) -> float:
    return round(value, 2)

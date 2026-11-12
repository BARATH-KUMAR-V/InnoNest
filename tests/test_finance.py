import pytest

from app.core.errors import AppError
from app.services import finance


def test_emi_matches_reference_value():
    assert finance.emi(5_000_000, 8.5, 240) == pytest.approx(43391.16, abs=0.01)


def test_emi_zero_interest_divides_evenly():
    assert finance.emi(1_200_000, 0, 120) == pytest.approx(10_000.0)


def test_emi_short_tenure_boundary():
    assert finance.emi(100_000, 12, 1) == pytest.approx(101_000.0)


def test_amortization_repays_principal_in_full():
    schedule = finance.amortization(1_000_000, 9.0, 60)
    assert schedule[-1]["balance"] == pytest.approx(0, abs=0.5)
    assert sum(row["principal"] for row in schedule) == pytest.approx(1_000_000, abs=1)


@pytest.mark.parametrize("principal,rate,months", [(0, 8, 120), (-5, 8, 120), (100000, -1, 120), (100000, 41, 120), (100000, 8, 0), (100000, 8, 481)])
def test_invalid_loan_inputs_are_rejected(principal, rate, months):
    with pytest.raises(AppError) as error:
        finance.emi(principal, rate, months)
    assert error.value.status_code == 422
    assert error.value.details


def test_foir_adds_existing_and_proposed_emi():
    assert finance.foir(10_000, 30_000, 100_000) == pytest.approx(0.40)


def test_foir_with_no_income_is_flagged_as_no_capacity():
    assert finance.foir(0, 10_000, 0) == finance.NO_CAPACITY
    assert finance.foir(0, 10_000, -5) == finance.NO_CAPACITY


def test_ltv_uses_total_exposure_over_accepted_value():
    assert finance.ltv(4_500_000, 6_000_000) == pytest.approx(0.75)


def test_ltv_with_no_value_is_flagged():
    assert finance.ltv(1_000_000, 0) == finance.NO_CAPACITY


def test_max_principal_inverts_emi():
    emi = finance.emi(2_500_000, 9.25, 180)
    assert finance.max_principal(emi, 9.25, 180) == pytest.approx(2_500_000, rel=1e-9)


def test_max_principal_zero_interest():
    assert finance.max_principal(10_000, 0, 100) == 1_000_000


def test_max_eligible_emi_never_negative():
    assert finance.max_eligible_emi(50_000, 40_000, 0.5) == 0
    assert finance.max_eligible_emi(100_000, 10_000, 0.5) == 40_000


def test_indian_number_grouping():
    assert finance.inr(4_500_000) == "INR 45,00,000"
    assert finance.inr(999) == "INR 999"

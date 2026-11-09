from decimal import Decimal

import pytest

from app.integrations.gemini import validate_intent_consistency
from app.schemas.intent import IntentAction, IntentAnalysis
from app.services.operation_planner import (
    calculate_line_total,
    rupees_to_paise,
)


def make_intent(action, **kwargs):
    return IntentAnalysis(
        language="en",
        actions=[action],
        summary="Test intent",
        **kwargs,
    )


def test_valid_cash_sale():
    intent = make_intent(
        IntentAction(
            action_type="record_sale",
            product_name="Maggi",
            quantity=Decimal(2),
            payment_type="FULL_PAYMENT",
            payment_method="CASH",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is False


def test_credit_sale_normalizes_payment_type():
    intent = make_intent(
        IntentAction(
            action_type="record_credit_sale",
            product_name="Maggi",
            customer_name="Rahul",
            quantity=Decimal(2),
        )
    )

    result = validate_intent_consistency(intent)

    assert result.actions[0].payment_type == "CREDIT"
    assert result.needs_clarification is False


def test_sale_without_product_or_quantity_requires_clarification():
    intent = make_intent(
        IntentAction(
            action_type="record_sale",
            payment_type="FULL_PAYMENT",
            payment_method="CASH",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True
    assert "product" in result.clarification_question.lower()


def test_full_payment_without_method_requires_clarification():
    intent = make_intent(
        IntentAction(
            action_type="record_sale",
            product_name="Milk",
            quantity=Decimal(2),
            payment_type="FULL_PAYMENT",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True
    assert "payment" in result.clarification_question.lower()


def test_partial_payment_without_amount_requires_clarification():
    intent = make_intent(
        IntentAction(
            action_type="record_sale",
            product_name="Rice",
            quantity=Decimal(1),
            customer_name="Rahul",
            payment_type="PARTIAL_PAYMENT",
            payment_method="CASH",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True
    assert "how much" in result.clarification_question.lower()


def test_partial_payment_without_customer_requires_clarification():
    intent = make_intent(
        IntentAction(
            action_type="record_sale",
            product_name="Rice",
            quantity=Decimal(1),
            payment_type="PARTIAL_PAYMENT",
            amount_paid_rupees=Decimal(100),
            payment_method="CASH",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True
    assert "customer" in result.clarification_question.lower()


def test_credit_repayment_requires_customer_and_amount():
    intent = make_intent(
        IntentAction(
            action_type="record_credit_repayment",
            customer_name="Rahul",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True
    assert "repayment amount" in result.clarification_question.lower()


def test_valid_credit_repayment():
    intent = make_intent(
        IntentAction(
            action_type="record_credit_repayment",
            customer_name="Rahul",
            amount_rupees=Decimal(250),
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is False


def test_unknown_action_requires_clarification():
    intent = make_intent(
        IntentAction(action_type="unknown")
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True


def test_rupees_to_paise():
    assert rupees_to_paise(Decimal(100)) == 10000
    assert rupees_to_paise(Decimal("12.50")) == 1250
    assert rupees_to_paise(Decimal("0.01")) == 1


def test_rupees_to_paise_rejects_fractional_paise():
    with pytest.raises(ValueError):
        rupees_to_paise(Decimal("10.001"))


def test_calculate_line_total():
    assert calculate_line_total(Decimal(2), 1500) == 3000
    assert calculate_line_total(Decimal(3), 1250) == 3750


def test_calculate_line_total_rounds_half_up():
    assert calculate_line_total(Decimal("0.5"), 1) == 1
    assert calculate_line_total(Decimal("1.5"), 1) == 2


def test_valid_inventory_adjustment():
    intent = make_intent(
        IntentAction(
            action_type="adjust_inventory",
            product_name="Maggi",
            quantity=Decimal(10),
            adjustment_direction="ADD",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is False
    assert result.actions[0].adjustment_direction == "ADD"


def test_inventory_adjustment_defaults_direction_to_add():
    intent = make_intent(
        IntentAction(
            action_type="adjust_inventory",
            product_name="Maggi",
            quantity=Decimal(10),
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is False
    assert result.actions[0].adjustment_direction == "ADD"


def test_inventory_adjustment_requires_product_and_quantity():
    intent = make_intent(
        IntentAction(
            action_type="adjust_inventory",
        )
    )

    result = validate_intent_consistency(intent)

    assert result.needs_clarification is True

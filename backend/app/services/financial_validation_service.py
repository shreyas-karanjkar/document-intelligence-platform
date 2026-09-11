from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.extraction import ExtractionResult


class ValidationCheck(BaseModel):
    check: str
    formula: str
    input_values: dict[str, float | None] = Field(
        default_factory=dict
    )
    calculated: float | None = None
    reported: float | None = None
    variance: float | None = None
    status: str


class FinancialValidationResult(BaseModel):
    document_type: str
    checks: list[ValidationCheck] = Field(
        default_factory=list
    )
    overall_status: str


def _normalize_field_name(name: str) -> str:
    value = name.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _find_field(
    extraction: ExtractionResult,
    aliases: list[str],
    period: str | None = None,
):
    normalized_aliases = [
        _normalize_field_name(alias)
        for alias in aliases
    ]

    # First prefer exact matches.
    exact_matches = []

    for field in extraction.fields:
        field_name = _normalize_field_name(
            field.field_name
        )

        if field_name not in normalized_aliases:
            continue

        if period is not None and field.period != period:
            continue

        exact_matches.append(field)

    # If multiple exact matches exist, prefer one
    # that contains a numeric value.
    for field in exact_matches:
        if field.normalized_number is not None:
            return field

    if exact_matches:
        return exact_matches[0]

    # If no exact match exists, use fuzzy matching.
    # Prefer the longest alias so that a specific field
    # such as "capital and liabilities total" is chosen
    # instead of the generic field "capital".
    candidates = []

    for field in extraction.fields:
        field_name = _normalize_field_name(
            field.field_name
        )

        if period is not None and field.period != period:
            continue

        for alias in normalized_aliases:
            if (
                alias in field_name
                or field_name in alias
            ):
                candidates.append(
                    (
                        len(alias),
                        field.normalized_number
                        is not None,
                        field,
                    )
                )

    if candidates:
        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        return candidates[0][2]

    return None


def _value(field) -> float | None:
    if field is None:
        return None

    return field.normalized_number


def _compare(
    calculated: float,
    reported: float,
) -> tuple[float, str]:

    variance = calculated - reported

    status = (
        "PASS"
        if abs(variance) <= settings.financial_tolerance
        else "FAIL"
    )

    return variance, status


def _validate_invoice(
    extraction: ExtractionResult,
) -> list[ValidationCheck]:

    checks: list[ValidationCheck] = []

    if extraction.invoice_line_items:

        for index, item in enumerate(
            extraction.invoice_line_items,
            start=1,
        ):

            quantity = item.quantity
            unit_price = item.unit_price
            line_total = item.line_total

            if (
                quantity is None
                or unit_price is None
                or line_total is None
            ):

                checks.append(
                    ValidationCheck(
                        check=(
                            f"Invoice line item {index} "
                            "calculation"
                        ),
                        formula=(
                            "Quantity × Unit Price ≈ Line Total"
                        ),
                        input_values={
                            "quantity": quantity,
                            "unit_price": unit_price,
                            "line_total": line_total,
                        },
                        calculated=None,
                        reported=line_total,
                        variance=None,
                        status="NOT_APPLICABLE",
                    )
                )

                continue

            calculated = quantity * unit_price

            variance, status = _compare(
                calculated,
                line_total,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        f"Invoice line item {index} "
                        "calculation"
                    ),
                    formula=(
                        "Quantity × Unit Price ≈ Line Total"
                    ),
                    input_values={
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                    },
                    calculated=calculated,
                    reported=line_total,
                    variance=variance,
                    status=status,
                )
            )

    line_totals = [
        item.line_total
        for item in extraction.invoice_line_items
        if item.line_total is not None
    ]

    subtotal_field = _find_field(
        extraction,
        [
            "subtotal",
            "sub total",
            "taxable amount",
            "amount before tax",
            "net worth",
            "net amount",
        ],
    )

    subtotal = _value(subtotal_field)

    if line_totals and subtotal is not None:

        calculated = sum(line_totals)

        variance, status = _compare(
            calculated,
            subtotal,
        )

        checks.append(
            ValidationCheck(
                check=(
                    "Invoice line-item subtotal "
                    "reconciliation"
                ),
                formula=(
                    "Sum of Line Totals ≈ "
                    "Reported Subtotal"
                ),
                input_values={
                    "sum_of_line_totals": calculated,
                    "reported_subtotal": subtotal,
                },
                calculated=calculated,
                reported=subtotal,
                variance=variance,
                status=status,
            )
        )

    else:

        checks.append(
            ValidationCheck(
                check=(
                    "Invoice line-item subtotal "
                    "reconciliation"
                ),
                formula=(
                    "Sum of Line Totals ≈ "
                    "Reported Subtotal"
                ),
                input_values={
                    "sum_of_line_totals": (
                        sum(line_totals)
                        if line_totals
                        else None
                    ),
                    "reported_subtotal": subtotal,
                },
                calculated=None,
                reported=subtotal,
                variance=None,
                status="NOT_APPLICABLE",
            )
        )

    tax_field = _find_field(
        extraction,
        [
            "tax_amount",
            "tax",
            "sales tax",
            "sales tax amount",
            "gst",
            "cgst",
            "sgst",
            "igst",
            "vat",
            "tax total",
        ],
    )

    discount_field = _find_field(
        extraction,
        [
            "discount",
            "discount amount",
            "total discount",
        ],
    )

    total_field = _find_field(
        extraction,
        [
            "total_amount",
            "total amount",
            "grand total",
            "invoice total",
            "amount due",
            "total due",
        ],
    )

    additional_charge_field = _find_field(
        extraction,
        [
            "shipping",
            "shipping and handling",
            "shipping handling",
            "handling",
            "freight",
            "delivery charge",
            "delivery charges",
            "service charge",
            "service charges",
            "other charges",
            "additional charges",
        ],
    )

    tax = _value(tax_field)
    discount = _value(discount_field)
    total = _value(total_field)
    additional_charge = _value(
        additional_charge_field
    )

    if (
        subtotal is not None
        and tax is not None
        and total is not None
    ):

        discount_value = (
            discount
            if discount is not None
            else 0.0
        )

        charge_value = (
            additional_charge
            if additional_charge is not None
            else 0.0
        )

        calculated = (
            subtotal
            + tax
            - discount_value
            + charge_value
        )

        variance, status = _compare(
            calculated,
            total,
        )

        checks.append(
            ValidationCheck(
                check="Invoice total reconciliation",
                formula=(
                    "Subtotal + Tax - Discount "
                    "+ Additional Charges ≈ Total Amount"
                ),
                input_values={
                    "subtotal": subtotal,
                    "tax_amount": tax,
                    "discount": discount,
                    "additional_charges": additional_charge,
                    "total_amount": total,
                },
                calculated=calculated,
                reported=total,
                variance=variance,
                status=status,
            )
        )

    else:

        checks.append(
            ValidationCheck(
                check="Invoice total reconciliation",
                formula=(
                    "Subtotal + Tax - Discount "
                    "+ Additional Charges ≈ Total Amount"
                ),
                input_values={
                    "subtotal": subtotal,
                    "tax_amount": tax,
                    "discount": discount,
                    "additional_charges": additional_charge,
                    "total_amount": total,
                },
                calculated=None,
                reported=total,
                variance=None,
                status="NOT_APPLICABLE",
            )
        )

    cash_paid_field = _find_field(
        extraction,
        [
            "cash paid",
            "amount paid",
            "paid amount",
            "cash received",
        ],
    )

    change_field = _find_field(
        extraction,
        [
            "change",
            "change due",
            "balance returned",
        ],
    )

    cash_paid = _value(cash_paid_field)
    change = _value(change_field)

    if (
        cash_paid is not None
        and total is not None
        and change is not None
    ):

        calculated = cash_paid - total

        variance, status = _compare(
            calculated,
            change,
        )

        checks.append(
            ValidationCheck(
                check="Invoice cash/change reconciliation",
                formula=(
                    "Cash Paid - Total Amount ≈ Change"
                ),
                input_values={
                    "cash_paid": cash_paid,
                    "total_amount": total,
                    "change": change,
                },
                calculated=calculated,
                reported=change,
                variance=variance,
                status=status,
            )
        )

    else:

        checks.append(
            ValidationCheck(
                check="Invoice cash/change reconciliation",
                formula=(
                    "Cash Paid - Total Amount ≈ Change"
                ),
                input_values={
                    "cash_paid": cash_paid,
                    "total_amount": total,
                    "change": change,
                },
                calculated=None,
                reported=change,
                variance=None,
                status="NOT_APPLICABLE",
            )
        )

    return checks


def _validate_cash_flow(
    extraction: ExtractionResult,
) -> list[ValidationCheck]:

    checks: list[ValidationCheck] = []

    operating_aliases = [
        "operating_cash_flow",
        "net cash flow from operating activities",
        "net cash flow (used in) / from operating activities",
        "net cash from operating activities",
        "net cash (used in) / from operating activities",
    ]

    investing_aliases = [
        "investing_cash_flow",
        "net cash flow from investing activities",
        "net cash flow used in investing activities",
        "net cash from investing activities",
        "net cash used in investing activities",
    ]

    financing_aliases = [
        "financing_cash_flow",
        "net cash flow from financing activities",
        "net cash flow from / (used in) financing activities",
        "net cash from financing activities",
        "net cash used in financing activities",
        "net cash (used in) / from financing activities",
        "net cash (used in) from financing activities",
    ]

    fx_aliases = [
        "foreign_exchange",
        "foreign exchange",
        "fx",
        "effect of exchange fluctuation on translation reserve",
        "exchange fluctuation",
        "translation reserve",
    ]

    net_change_aliases = [
        "net_change_in_cash",
        "net increase in cash and cash equivalents",
        "net change in cash and cash equivalents",
    ]

    opening_aliases = [
        "opening_cash",
        "opening cash",
        "cash and cash equivalents as at april 1st",
        "cash and cash equivalents at april 1st",
    ]

    closing_aliases = [
        "closing_cash",
        "closing cash",
        "cash and cash equivalents as at march 31st",
        "cash and cash equivalents at march 31st",
    ]

    periods = extraction.periods

    if not periods:
        periods = [None]

    for period in periods:

        operating = _value(
            _find_field(
                extraction,
                operating_aliases,
                period,
            )
        )

        investing = _value(
            _find_field(
                extraction,
                investing_aliases,
                period,
            )
        )

        financing = _value(
            _find_field(
                extraction,
                financing_aliases,
                period,
            )
        )

        fx = _value(
            _find_field(
                extraction,
                fx_aliases,
                period,
            )
        )

        net_change = _value(
            _find_field(
                extraction,
                net_change_aliases,
                period,
            )
        )

        period_label = (
            period
            if period is not None
            else "document period"
        )

        # FX and other cash adjustments are optional.
        # If they are not present in the extracted document,
        # treat them as zero rather than making the whole
        # reconciliation NOT_APPLICABLE.
        fx_value = fx if fx is not None else 0.0
        other_adjustment = _value(
            _find_field(
                extraction,
                [
                    "cash and cash equivalents on amalgamation",
                    "cash and cash equivalents on acquisition",
                    "cash and cash equivalents on merger",
                    "cash acquired",
                    "cash adjustment",
                    "other cash adjustments",
                ],
                period,
            )
        )
        other_adjustment_value = (
            other_adjustment
            if other_adjustment is not None
            else 0.0
        )

        if (
            operating is not None
            and investing is not None
            and financing is not None
            and net_change is not None
        ):

            calculated = (
                operating
                + investing
                + financing
                + fx_value
                + other_adjustment_value
            )

            variance, status = _compare(
                calculated,
                net_change,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Cash flow reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Operating + Investing + Financing "
                        "+ FX + Other Cash Adjustments "
                        "≈ Net Increase in Cash"
                    ),
                    input_values={
                        "operating_cash_flow": operating,
                        "investing_cash_flow": investing,
                        "financing_cash_flow": financing,
                        "foreign_exchange": fx,
                        "other_cash_adjustment": other_adjustment,
                        "reported_net_increase": net_change,
                    },
                    calculated=calculated,
                    reported=net_change,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Cash flow reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Operating + Investing + Financing "
                        "+ FX + Other Cash Adjustments "
                        "≈ Net Increase in Cash"
                    ),
                    input_values={
                        "operating_cash_flow": operating,
                        "investing_cash_flow": investing,
                        "financing_cash_flow": financing,
                        "foreign_exchange": fx,
                        "other_cash_adjustment": other_adjustment,
                        "reported_net_increase": net_change,
                    },
                    calculated=None,
                    reported=net_change,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

        opening_cash = _value(
            _find_field(
                extraction,
                opening_aliases,
                period,
            )
        )

        closing_cash = _value(
            _find_field(
                extraction,
                closing_aliases,
                period,
            )
        )

        if (
            opening_cash is not None
            and net_change is not None
            and closing_cash is not None
        ):

            calculated = (
                opening_cash
                + net_change
            )

            variance, status = _compare(
                calculated,
                closing_cash,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Opening/closing cash reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Opening Cash + Net Increase = Closing Cash"
                    ),
                    input_values={
                        "opening_cash": opening_cash,
                        "net_increase": net_change,
                        "reported_closing_cash": closing_cash,
                    },
                    calculated=calculated,
                    reported=closing_cash,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Opening/closing cash reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Opening Cash + Net Increase = Closing Cash"
                    ),
                    input_values={
                        "opening_cash": opening_cash,
                        "net_increase": net_change,
                        "reported_closing_cash": closing_cash,
                    },
                    calculated=None,
                    reported=closing_cash,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

    return checks


def _validate_balance_sheet(
    extraction: ExtractionResult,
) -> list[ValidationCheck]:

    checks: list[ValidationCheck] = []

    total_capital_liabilities_aliases = [
        "total capital and liabilities",
        "capital and liabilities total",
        "total capital liabilities",
        "capital liabilities total",
        "total capital & liabilities",
        "capital & liabilities total",
    ]

    total_assets_aliases = [
        "total assets",
        "assets total",
        "total asset",
        "asset total",
    ]

    capital_liability_components = [
        (
            "capital",
            [
                "capital",
                "share capital",
            ],
        ),
        (
            "reserves_and_surplus",
            [
                "reserves and surplus",
                "reserves & surplus",
            ],
        ),
        (
            "minority_interest",
            [
                "minority interest",
            ],
        ),
        (
            "deposits",
            [
                "deposits",
            ],
        ),
        (
            "borrowings",
            [
                "borrowings",
            ],
        ),
        (
            "other_liabilities_and_provisions",
            [
                "other liabilities and provisions",
                "other liabilities",
                "liabilities and provisions",
            ],
        ),
    ]

    asset_components = [
        (
            "cash_and_reserve_bank",
            [
                "cash and balances with reserve bank of india",
                "cash and balances with reserve bank",
            ],
        ),
        (
            "balances_with_banks",
            [
                "balances with banks and money at call and short notice",
                "balances with banks",
            ],
        ),
        (
            "investments",
            [
                "investments",
            ],
        ),
        (
            "advances",
            [
                "advances",
            ],
        ),
        (
            "fixed_assets",
            [
                "fixed assets",
            ],
        ),
        (
            "other_assets",
            [
                "other assets",
            ],
        ),
    ]

    periods = extraction.periods

    if not periods:
        periods = [None]

    for period in periods:

        period_label = (
            period
            if period is not None
            else "document period"
        )

        total_capital_liabilities = _value(
            _find_field(
                extraction,
                total_capital_liabilities_aliases,
                period,
            )
        )

        total_assets = _value(
            _find_field(
                extraction,
                total_assets_aliases,
                period,
            )
        )

        if (
            total_capital_liabilities is not None
            and total_assets is not None
        ):

            variance, status = _compare(
                total_capital_liabilities,
                total_assets,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Balance sheet equation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Total Capital and Liabilities "
                        "≈ Total Assets"
                    ),
                    input_values={
                        "total_capital_and_liabilities": (
                            total_capital_liabilities
                        ),
                        "total_assets": total_assets,
                    },
                    calculated=total_capital_liabilities,
                    reported=total_assets,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Balance sheet equation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Total Capital and Liabilities "
                        "≈ Total Assets"
                    ),
                    input_values={
                        "total_capital_and_liabilities": (
                            total_capital_liabilities
                        ),
                        "total_assets": total_assets,
                    },
                    calculated=None,
                    reported=total_assets,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

        liability_values = {}

        for component_name, aliases in (
            capital_liability_components
        ):

            value = _value(
                _find_field(
                    extraction,
                    aliases,
                    period,
                )
            )

            liability_values[
                component_name
            ] = value

        if (
            total_capital_liabilities is not None
            and all(
                value is not None
                for value in liability_values.values()
            )
        ):

            calculated = sum(
                liability_values.values()
            )

            variance, status = _compare(
                calculated,
                total_capital_liabilities,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Capital and liabilities "
                        "component reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Capital + Reserves and Surplus "
                        "+ Minority Interest + Deposits "
                        "+ Borrowings + Other Liabilities "
                        "and Provisions "
                        "≈ Total Capital and Liabilities"
                    ),
                    input_values={
                        **liability_values,
                        "reported_total": (
                            total_capital_liabilities
                        ),
                    },
                    calculated=calculated,
                    reported=total_capital_liabilities,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Capital and liabilities "
                        "component reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Capital + Reserves and Surplus "
                        "+ Minority Interest + Deposits "
                        "+ Borrowings + Other Liabilities "
                        "and Provisions "
                        "≈ Total Capital and Liabilities"
                    ),
                    input_values={
                        **liability_values,
                        "reported_total": (
                            total_capital_liabilities
                        ),
                    },
                    calculated=None,
                    reported=total_capital_liabilities,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

        asset_values = {}

        for component_name, aliases in asset_components:

            value = _value(
                _find_field(
                    extraction,
                    aliases,
                    period,
                )
            )

            asset_values[
                component_name
            ] = value

        if (
            total_assets is not None
            and all(
                value is not None
                for value in asset_values.values()
            )
        ):

            calculated = sum(
                asset_values.values()
            )

            variance, status = _compare(
                calculated,
                total_assets,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Asset component reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Cash + Bank Balances + Investments "
                        "+ Advances + Fixed Assets "
                        "+ Other Assets "
                        "≈ Total Assets"
                    ),
                    input_values={
                        **asset_values,
                        "reported_total_assets": total_assets,
                    },
                    calculated=calculated,
                    reported=total_assets,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Asset component reconciliation - "
                        f"{period_label}"
                    ),
                    formula=(
                        "Cash + Bank Balances + Investments "
                        "+ Advances + Fixed Assets "
                        "+ Other Assets "
                        "≈ Total Assets"
                    ),
                    input_values={
                        **asset_values,
                        "reported_total_assets": total_assets,
                    },
                    calculated=None,
                    reported=total_assets,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

    return checks


def _validate_profit_loss(
    extraction: ExtractionResult,
) -> list[ValidationCheck]:

    checks: list[ValidationCheck] = []

    total_income_aliases = [
        "total income",
    ]

    interest_earned_aliases = [
        "interest earned",
        "interest income",
    ]

    other_income_aliases = [
        "other income",
    ]

    total_expenditure_aliases = [
        "total expenditure",
        "total expenses",
    ]

    interest_expended_aliases = [
        "interest expended",
        "interest expense",
    ]

    operating_expenses_aliases = [
        "operating expenses",
        "operating expense",
    ]

    provisions_aliases = [
        "provisions and contingencies",
        "provisions & contingencies",
        "provisions and contingency",
    ]

    profit_before_minority_aliases = [
        "consolidated net profit before minority interest",
        "profit before minority interest",
        "net profit before minority interest",
    ]

    minority_interest_aliases = [
        "minority interest",
    ]

    consolidated_net_profit_aliases = [
        "consolidated net profit attributable to the group",
        "consolidated net profit",
        "net profit attributable to the group",
    ]

    periods = extraction.periods

    if not periods:
        periods = [None]

    for period in periods:

        total_income = _value(
            _find_field(
                extraction,
                total_income_aliases,
                period,
            )
        )

        interest_earned = _value(
            _find_field(
                extraction,
                interest_earned_aliases,
                period,
            )
        )

        other_income = _value(
            _find_field(
                extraction,
                other_income_aliases,
                period,
            )
        )

        if (
            interest_earned is not None
            and other_income is not None
            and total_income is not None
        ):

            calculated = (
                interest_earned
                + other_income
            )

            variance, status = _compare(
                calculated,
                total_income,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Profit and loss total income "
                        "reconciliation - "
                        f"{period or 'document period'}"
                    ),
                    formula=(
                        "Interest Earned + Other Income "
                        "≈ Total Income"
                    ),
                    input_values={
                        "interest_earned": interest_earned,
                        "other_income": other_income,
                        "reported_total_income": total_income,
                    },
                    calculated=calculated,
                    reported=total_income,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Profit and loss total income "
                        "reconciliation - "
                        f"{period or 'document period'}"
                    ),
                    formula=(
                        "Interest Earned + Other Income "
                        "≈ Total Income"
                    ),
                    input_values={
                        "interest_earned": interest_earned,
                        "other_income": other_income,
                        "reported_total_income": total_income,
                    },
                    calculated=None,
                    reported=total_income,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

        total_expenditure = _value(
            _find_field(
                extraction,
                total_expenditure_aliases,
                period,
            )
        )

        interest_expended = _value(
            _find_field(
                extraction,
                interest_expended_aliases,
                period,
            )
        )

        operating_expenses = _value(
            _find_field(
                extraction,
                operating_expenses_aliases,
                period,
            )
        )

        provisions = _value(
            _find_field(
                extraction,
                provisions_aliases,
                period,
            )
        )

        if (
            interest_expended is not None
            and operating_expenses is not None
            and provisions is not None
            and total_expenditure is not None
        ):

            calculated = (
                interest_expended
                + operating_expenses
                + provisions
            )

            variance, status = _compare(
                calculated,
                total_expenditure,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Profit and loss total expenditure "
                        "reconciliation - "
                        f"{period or 'document period'}"
                    ),
                    formula=(
                        "Interest Expended + Operating Expenses "
                        "+ Provisions & Contingencies "
                        "≈ Total Expenditure"
                    ),
                    input_values={
                        "interest_expended": interest_expended,
                        "operating_expenses": operating_expenses,
                        "provisions_and_contingencies": provisions,
                        "reported_total_expenditure": (
                            total_expenditure
                        ),
                    },
                    calculated=calculated,
                    reported=total_expenditure,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Profit and loss total expenditure "
                        "reconciliation - "
                        f"{period or 'document period'}"
                    ),
                    formula=(
                        "Interest Expended + Operating Expenses "
                        "+ Provisions & Contingencies "
                        "≈ Total Expenditure"
                    ),
                    input_values={
                        "interest_expended": interest_expended,
                        "operating_expenses": operating_expenses,
                        "provisions_and_contingencies": provisions,
                        "reported_total_expenditure": (
                            total_expenditure
                        ),
                    },
                    calculated=None,
                    reported=total_expenditure,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

        profit_before_minority = _value(
            _find_field(
                extraction,
                profit_before_minority_aliases,
                period,
            )
        )

        minority_interest = _value(
            _find_field(
                extraction,
                minority_interest_aliases,
                period,
            )
        )

        consolidated_net_profit = _value(
            _find_field(
                extraction,
                consolidated_net_profit_aliases,
                period,
            )
        )

        if (
            profit_before_minority is not None
            and minority_interest is not None
            and consolidated_net_profit is not None
        ):

            calculated = (
                profit_before_minority
                - minority_interest
            )

            variance, status = _compare(
                calculated,
                consolidated_net_profit,
            )

            checks.append(
                ValidationCheck(
                    check=(
                        "Profit after minority interest "
                        "reconciliation - "
                        f"{period or 'document period'}"
                    ),
                    formula=(
                        "Profit Before Minority Interest "
                        "- Minority Interest "
                        "≈ Consolidated Net Profit"
                    ),
                    input_values={
                        "profit_before_minority_interest": (
                            profit_before_minority
                        ),
                        "minority_interest": (
                            minority_interest
                        ),
                        "reported_consolidated_net_profit": (
                            consolidated_net_profit
                        ),
                    },
                    calculated=calculated,
                    reported=consolidated_net_profit,
                    variance=variance,
                    status=status,
                )
            )

        else:

            checks.append(
                ValidationCheck(
                    check=(
                        "Profit after minority interest "
                        "reconciliation - "
                        f"{period or 'document period'}"
                    ),
                    formula=(
                        "Profit Before Minority Interest "
                        "- Minority Interest "
                        "≈ Consolidated Net Profit"
                    ),
                    input_values={
                        "profit_before_minority_interest": (
                            profit_before_minority
                        ),
                        "minority_interest": (
                            minority_interest
                        ),
                        "reported_consolidated_net_profit": (
                            consolidated_net_profit
                        ),
                    },
                    calculated=None,
                    reported=consolidated_net_profit,
                    variance=None,
                    status="NOT_APPLICABLE",
                )
            )

    return checks


def validate_financial_document(
    extraction: ExtractionResult,
) -> FinancialValidationResult:

    document_type = extraction.document_type

    if document_type == "invoice":

        checks = _validate_invoice(
            extraction
        )

    elif document_type == "cash_flow":

        checks = _validate_cash_flow(
            extraction
        )

    elif document_type == "balance_sheet":

        checks = _validate_balance_sheet(
            extraction
        )

    elif document_type == "profit_loss":

        checks = _validate_profit_loss(
            extraction
        )

    else:

        checks = []

    statuses = [
        check.status
        for check in checks
    ]

    if "FAIL" in statuses:

        overall_status = "FAIL"

    elif "PASS" in statuses:

        overall_status = "PASS"

    else:

        overall_status = "NOT_APPLICABLE"

    return FinancialValidationResult(
        document_type=document_type,
        checks=checks,
        overall_status=overall_status,
    )
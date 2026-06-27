"""
Excel cell mapping and automation metadata for Solar Load Calculator template.

Single source of truth for AI-populated fields.
Edit field definitions here — then run: python scripts/create_template.py
"""

from __future__ import annotations

from typing import TypedDict


class FieldSpec(TypedDict):
    field_name: str
    cell: str
    data_type: str
    required: str
    description: str
    number_format: str
    comment: str


# Sheet name for the main calculator (openpyxl must target this explicitly)
CALCULATOR_SHEET_NAME = "Solar Calculator"
MAPPING_SHEET_NAME = "Automation_Mapping"

# AI-populated input fields — order matches template layout
AUTOMATION_FIELDS: list[FieldSpec] = [
    {
        "field_name": "consumer_name",
        "cell": "B4",
        "data_type": "Text",
        "required": "Yes",
        "description": "Full name of electricity consumer as printed on bill",
        "number_format": "@",
        "comment": "Consumer Name\nExpected: Text\nExample: Rajesh Kumar Sharma",
    },
    {
        "field_name": "consumer_number",
        "cell": "B5",
        "data_type": "Text",
        "required": "Yes",
        "description": "MSEDCL consumer / account number",
        "number_format": "@",
        "comment": "Consumer Number\nExpected: Alphanumeric\nExample: 123456789012",
    },
    {
        "field_name": "billing_month",
        "cell": "B6",
        "data_type": "Text",
        "required": "Yes",
        "description": "Billing month label from bill header",
        "number_format": "@",
        "comment": "Billing Month\nExpected: Text\nExample: Jan-2025",
    },
    {
        "field_name": "billing_period",
        "cell": "B7",
        "data_type": "Text",
        "required": "No",
        "description": "From–to billing period dates",
        "number_format": "@",
        "comment": "Billing Period\nExpected: Text\nExample: 01/12/2024 to 31/12/2024",
    },
    {
        "field_name": "bill_date",
        "cell": "B8",
        "data_type": "Date",
        "required": "No",
        "description": "Date the bill was issued",
        "number_format": "DD-MMM-YYYY",
        "comment": "Bill Date\nExpected: Date\nExample: 05-Jan-2025",
    },
    {
        "field_name": "due_date",
        "cell": "B9",
        "data_type": "Date",
        "required": "No",
        "description": "Payment due date",
        "number_format": "DD-MMM-YYYY",
        "comment": "Due Date\nExpected: Date\nExample: 20-Jan-2025",
    },
    {
        "field_name": "address",
        "cell": "B10",
        "data_type": "Text",
        "required": "No",
        "description": "Consumer service address",
        "number_format": "@",
        "comment": "Address\nExpected: Text\nExample: Flat 12, Pune, MH 411001",
    },
    {
        "field_name": "tariff_category",
        "cell": "B11",
        "data_type": "Text",
        "required": "No",
        "description": "Tariff / category code (e.g. LT-I, HT-II)",
        "number_format": "@",
        "comment": "Tariff Category\nExpected: Text\nExample: LT-I Domestic",
    },
    {
        "field_name": "meter_number",
        "cell": "B12",
        "data_type": "Text",
        "required": "No",
        "description": "Electricity meter serial number",
        "number_format": "@",
        "comment": "Meter Number\nExpected: Alphanumeric\nExample: MH12345678",
    },
    {
        "field_name": "division",
        "cell": "B13",
        "data_type": "Text",
        "required": "No",
        "description": "MSEDCL division name",
        "number_format": "@",
        "comment": "Division\nExpected: Text\nExample: Pune Rural",
    },
    {
        "field_name": "sub_division",
        "cell": "B14",
        "data_type": "Text",
        "required": "No",
        "description": "MSEDCL sub-division name",
        "number_format": "@",
        "comment": "Sub Division\nExpected: Text\nExample: Haveli",
    },
    {
        "field_name": "tariff_code",
        "cell": "B15",
        "data_type": "Text",
        "required": "No",
        "description": "Internal tariff code if shown on bill",
        "number_format": "@",
        "comment": "Tariff Code\nExpected: Text\nExample: 010",
    },
    {
        "field_name": "contract_load",
        "cell": "D4",
        "data_type": "Number",
        "required": "No",
        "description": "Contracted load in kW",
        "number_format": '0.00" kW"',
        "comment": "Contract Load\nExpected: Numeric (kW)\nExample: 5.00",
    },
    {
        "field_name": "connected_load",
        "cell": "D5",
        "data_type": "Number",
        "required": "No",
        "description": "Connected load in kW",
        "number_format": '0.00" kW"',
        "comment": "Connected Load\nExpected: Numeric (kW)\nExample: 4.50",
    },
    {
        "field_name": "sanctioned_load",
        "cell": "D6",
        "data_type": "Number",
        "required": "No",
        "description": "Sanctioned load in kW",
        "number_format": '0.00" kW"',
        "comment": "Sanctioned Load\nExpected: Numeric (kW)\nExample: 5.00",
    },
    {
        "field_name": "voltage",
        "cell": "D7",
        "data_type": "Text",
        "required": "No",
        "description": "Supply voltage level",
        "number_format": "@",
        "comment": "Voltage\nExpected: Text\nExample: 230V",
    },
    {
        "field_name": "power_factor",
        "cell": "D8",
        "data_type": "Number",
        "required": "No",
        "description": "Power factor (0–1 or percentage as printed)",
        "number_format": "0.00",
        "comment": "Power Factor\nExpected: Numeric\nExample: 0.98",
    },
    {
        "field_name": "billing_cycle",
        "cell": "D9",
        "data_type": "Text",
        "required": "No",
        "description": "Billing cycle frequency",
        "number_format": "@",
        "comment": "Billing Cycle\nExpected: Text\nExample: Monthly",
    },
    {
        "field_name": "GST_number",
        "cell": "D10",
        "data_type": "Text",
        "required": "No",
        "description": "GSTIN if present on bill",
        "number_format": "@",
        "comment": "GST Number\nExpected: Alphanumeric\nExample: 27AABCU9603R1ZM",
    },
    {
        "field_name": "previous_reading",
        "cell": "D11",
        "data_type": "Number",
        "required": "No",
        "description": "Previous meter reading (kWh)",
        "number_format": "0",
        "comment": "Previous Reading\nExpected: Numeric meter index (no kWh suffix)\nExample: 18292",
    },
    {
        "field_name": "units_consumed",
        "cell": "D12",
        "data_type": "Number",
        "required": "Yes",
        "description": "Units consumed in billing period — drives solar sizing",
        "number_format": '#,##0" kWh"',
        "comment": "Units Consumed\nExpected: Numeric\nExample: 450",
    },
    {
        "field_name": "current_reading",
        "cell": "D13",
        "data_type": "Number",
        "required": "No",
        "description": "Current meter reading (numeric index, not consumption)",
        "number_format": "0",
        "comment": "Current Reading\nExpected: Numeric meter index (no kWh suffix)\nExample: 18429",
    },
    {
        "field_name": "bill_amount",
        "cell": "D14",
        "data_type": "Currency",
        "required": "Yes",
        "description": "Total bill amount in INR — drives savings estimate",
        "number_format": '₹#,##0.00',
        "comment": "Bill Amount\nExpected: Currency (INR)\nExample: 3200",
    },
    {
        "field_name": "fixed_charges",
        "cell": "D15",
        "data_type": "Currency",
        "required": "No",
        "description": "Fixed / demand charges component",
        "number_format": '₹#,##0.00',
        "comment": "Fixed Charges\nExpected: Currency (INR)\nExample: 150",
    },
    {
        "field_name": "energy_charges",
        "cell": "D16",
        "data_type": "Currency",
        "required": "No",
        "description": "Energy charges component",
        "number_format": '₹#,##0.00',
        "comment": "Energy Charges\nExpected: Currency (INR)\nExample: 2800",
    },
    {
        "field_name": "fuel_adjustment",
        "cell": "D17",
        "data_type": "Currency",
        "required": "No",
        "description": "Fuel adjustment / FCA charge",
        "number_format": '₹#,##0.00',
        "comment": "Fuel Adjustment\nExpected: Currency (INR)\nExample: 120",
    },
    {
        "field_name": "electricity_duty",
        "cell": "D18",
        "data_type": "Currency",
        "required": "No",
        "description": "Electricity duty amount",
        "number_format": '₹#,##0.00',
        "comment": "Electricity Duty\nExpected: Currency (INR)\nExample: 80",
    },
    {
        "field_name": "tax_on_sale",
        "cell": "D19",
        "data_type": "Currency",
        "required": "No",
        "description": "Tax on sale / other levies",
        "number_format": '₹#,##0.00',
        "comment": "Tax on Sale\nExpected: Currency (INR)\nExample: 50",
    },
]

# Calculated output cells — formulas only, never written by automation
FORMULA_CELLS: list[dict[str, str]] = [
    {
        "cell": "B22",
        "label": "Avg Monthly Consumption (kWh)",
        "formula": '=IF(D12="","",D12)',
        "description": "Mirrors units consumed for solar sizing",
    },
    {
        "cell": "B23",
        "label": "Recommended Solar Capacity (kW)",
        "formula": '=IF(B22="","",ROUND(B22/120,2))',
        "description": "Capacity = monthly kWh / 120 (standard rule of thumb)",
    },
    {
        "cell": "B24",
        "label": "Estimated Annual Savings (₹)",
        "formula": '=IF(OR(D12="",D14=""),"",D14*12)',
        "description": "Annual savings = monthly bill × 12",
    },
    {
        "cell": "B25",
        "label": "Payback Period (Years)",
        "formula": '=IF(B24="","",ROUND((B23*50000)/B24,1))',
        "description": "Payback = system cost (₹50k/kW) / annual savings",
    },
    {
        "cell": "B26",
        "label": "CO₂ Offset (tons/year)",
        "formula": '=IF(B22="","",ROUND(B22*0.82/1000,2))',
        "description": "CO₂ offset using 0.82 kg/kWh grid factor",
    },
]

# Derived dicts for excel_writer (backwards compatible)
CELL_MAPPING: dict[str, str] = {
    f["field_name"]: f["cell"] for f in AUTOMATION_FIELDS if f["required"] == "Yes"
}
EXTRA_CELL_MAPPING: dict[str, str] = {
    f["field_name"]: f["cell"]
    for f in AUTOMATION_FIELDS
    if f["required"] != "Yes"
}

EXTRACTABLE_FIELDS: list[str] = [f["field_name"] for f in AUTOMATION_FIELDS]

FIELD_BY_NAME: dict[str, FieldSpec] = {f["field_name"]: f for f in AUTOMATION_FIELDS}

INPUT_CELLS: list[str] = [f["cell"] for f in AUTOMATION_FIELDS]

OUTPUT_CELLS: list[str] = [f["cell"] for f in FORMULA_CELLS]

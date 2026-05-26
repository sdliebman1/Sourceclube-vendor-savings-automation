from __future__ import annotations

import io
import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any

import pandas as pd
import streamlit as st

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


st.set_page_config(
    page_title="SourceClub Savings Analysis",
    page_icon="SC",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px;}
    h1, h2, h3 {letter-spacing: 0;}
    div[data-testid="stMetricValue"] {font-size: 2rem;}
    .small-note {color: #667085; font-size: 0.92rem; line-height: 1.45;}
    .success-box {
        border: 1px solid #b7e4c7; background: #f0fdf4; border-radius: 8px;
        padding: 0.85rem 1rem; color: #14532d;
    }
    .review-box {
        border: 1px solid #fedf89; background: #fffbeb; border-radius: 8px;
        padding: 0.85rem 1rem; color: #7a2e0e;
    }
    .risk-box {
        border: 1px solid #fecaca; background: #fff1f2; border-radius: 8px;
        padding: 0.85rem 1rem; color: #7f1d1d;
    }
    .flow-card {
        border: 1px solid #d0d5dd; background: #ffffff; border-radius: 10px;
        padding: 1rem; min-height: 112px;
    }
    .flow-card strong {display: block; margin-bottom: 0.35rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


CATALOG = pd.DataFrame(
    [
        {
            "SourceClub_Item_Name": "GRAHAM LIDOCAINE 1:100 RED 50",
            "Manufacturer": "Benco",
            "Manufacturer_SKU": "3306-638",
            "Pack_Size": 50,
            "Unit": "Box",
            "SourceClub_Price": 28.75,
            "Category": "Anesthetic",
        },
        {
            "SourceClub_Item_Name": "GRAHAM MEPIVACAINE 3% BX50",
            "Manufacturer": "Benco",
            "Manufacturer_SKU": "3306-656",
            "Pack_Size": 50,
            "Unit": "Box",
            "SourceClub_Price": 32.50,
            "Category": "Anesthetic",
        },
        {
            "SourceClub_Item_Name": "ORABLOC 4% W/EPI 1:100 GLD 50",
            "Manufacturer": "Pierrel",
            "Manufacturer_SKU": "4707-113",
            "Pack_Size": 50,
            "Unit": "Box",
            "SourceClub_Price": 35.00,
            "Category": "Anesthetic",
        },
        {
            "SourceClub_Item_Name": "NITRILE EXAM GLOVES POWDER FREE MEDIUM",
            "Manufacturer": "Medline",
            "Manufacturer_SKU": "GLV-MED-NIT",
            "Pack_Size": 100,
            "Unit": "Box",
            "SourceClub_Price": 8.50,
            "Category": "Gloves",
        },
        {
            "SourceClub_Item_Name": "FACE MASKS ASTM LEVEL 3 EARLOOP",
            "Manufacturer": "Medline",
            "Manufacturer_SKU": "MASK-L3",
            "Pack_Size": 50,
            "Unit": "Box",
            "SourceClub_Price": 12.99,
            "Category": "Masks",
        },
        {
            "SourceClub_Item_Name": "SURGICAL GOWNS FLUID RESISTANT",
            "Manufacturer": "Cardinal",
            "Manufacturer_SKU": "GOWN-FR",
            "Pack_Size": 10,
            "Unit": "Each",
            "SourceClub_Price": 45.00,
            "Category": "PPE",
        },
    ]
)


def money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def number(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if cleaned in {"", ".", "-", "-."}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def normalize(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9.% ]+", " ", text)
    text = re.sub(
        r"\b(box|bx|bag|pack|pkg|case|of|with|and|the|each|ea|ct|count|red|blue|clear)\b",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def token_overlap(left: str, right: str) -> float:
    left_tokens = set(normalize(left).split())
    right_tokens = set(normalize(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def confidence_band(score: float) -> str:
    if score >= 0.78:
        return "High"
    if score >= 0.55:
        return "Medium"
    return "Low"


def extract_metadata(raw: pd.DataFrame) -> dict[str, str]:
    metadata = {
        "Prepared For": "Unknown prospect",
        "Account Number": "",
        "Report Description": "",
        "Supplier": "Benco Dental",
    }
    scan_rows = raw.head(30).fillna("").astype(str).values.tolist()
    for row in scan_rows:
        joined = " ".join(cell.strip() for cell in row if cell.strip())
        cells = [cell.strip() for cell in row if cell.strip()]
        for idx, cell in enumerate(cells):
            lower = cell.lower()
            next_value = cells[idx + 1] if idx + 1 < len(cells) else ""
            if "prepared for" in lower and next_value:
                metadata["Prepared For"] = next_value
            if "account number" in lower and next_value:
                metadata["Account Number"] = next_value
            if "report description" in lower and next_value:
                metadata["Report Description"] = next_value
        if "prepared for" in joined.lower():
            match = re.search(r"prepared for:?\s+(.+?)(account number|$)", joined, re.I)
            if match:
                metadata["Prepared For"] = match.group(1).strip()
        if "account number" in joined.lower():
            match = re.search(r"account number:?\s+([0-9A-Za-z\-]+)", joined, re.I)
            if match:
                metadata["Account Number"] = match.group(1).strip()
    return metadata


HEADER_ALIASES = {
    "order": "Order",
    "order #": "Order",
    "invoice": "Order",
    "item": "Vendor_Item_Number",
    "item number": "Vendor_Item_Number",
    "item #": "Vendor_Item_Number",
    "mfgr": "Manufacturer",
    "mfg": "Manufacturer",
    "manufacturer": "Manufacturer",
    "description": "Description",
    "item description": "Description",
    "order date": "Order_Date",
    "date": "Order_Date",
    "price": "Current_Unit_Price",
    "unit price": "Current_Unit_Price",
    "qty": "Quantity",
    "quantity": "Quantity",
    "amount": "Current_Total",
    "total": "Current_Total",
}


REQUIRED_COLUMNS = [
    "Order",
    "Vendor_Item_Number",
    "Manufacturer",
    "Description",
    "Order_Date",
    "Current_Unit_Price",
    "Quantity",
    "Current_Total",
]


def canonical_header(value: Any) -> str | None:
    cleaned = normalize(value).replace(" ", " ")
    return HEADER_ALIASES.get(cleaned)


def find_vendor_rows(raw: pd.DataFrame) -> pd.DataFrame:
    rows = raw.fillna("").astype(str).values.tolist()
    records: list[dict[str, str]] = []
    active_map: dict[int, str] | None = None

    for row in rows:
        mapped = {idx: canonical_header(cell) for idx, cell in enumerate(row)}
        mapped = {idx: name for idx, name in mapped.items() if name}
        mapped_values = set(mapped.values())
        if {"Order", "Vendor_Item_Number", "Description", "Current_Unit_Price", "Quantity"} <= mapped_values:
            active_map = mapped
            continue

        if not active_map:
            continue

        record = {column: "" for column in REQUIRED_COLUMNS}
        for idx, column in active_map.items():
            if idx < len(row):
                record[column] = row[idx].strip()

        joined = " ".join(record.values()).lower()
        if not any(record.values()):
            continue
        if "total for" in joined or "purchase analysis" in joined:
            continue
        if normalize(record["Order"]) in {"order", ""}:
            continue
        if normalize(record["Vendor_Item_Number"]) in {"item", ""}:
            continue
        if not record["Description"] or not record["Quantity"]:
            continue
        records.append(record)

    return pd.DataFrame(records, columns=REQUIRED_COLUMNS)


def clean_purchase_history(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    metadata = extract_metadata(raw)

    if set(REQUIRED_COLUMNS) <= set(raw.columns):
        cleaned = raw[REQUIRED_COLUMNS].copy()
    else:
        direct_columns = {canonical_header(column): column for column in raw.columns if canonical_header(column)}
        if {"Order", "Vendor_Item_Number", "Description", "Current_Unit_Price", "Quantity"} <= set(direct_columns):
            cleaned = pd.DataFrame()
            for target in REQUIRED_COLUMNS:
                source = direct_columns.get(target)
                cleaned[target] = raw[source] if source else ""
        else:
            cleaned = find_vendor_rows(raw)

    if cleaned.empty:
        return cleaned, metadata

    if "Supplier" in raw.columns and not raw["Supplier"].dropna().empty:
        metadata["Supplier"] = str(raw["Supplier"].dropna().iloc[0])

    cleaned["Supplier"] = metadata["Supplier"]
    cleaned["Current_Unit_Price"] = cleaned["Current_Unit_Price"].map(number)
    cleaned["Quantity"] = cleaned["Quantity"].map(number)
    cleaned["Current_Total"] = cleaned["Current_Total"].map(number)
    cleaned.loc[cleaned["Current_Total"] == 0, "Current_Total"] = (
        cleaned["Current_Unit_Price"] * cleaned["Quantity"]
    )
    cleaned = cleaned[cleaned["Quantity"] > 0].copy()
    cleaned["Prospect_Item_Name"] = (
        cleaned["Manufacturer"].astype(str).str.strip()
        + " "
        + cleaned["Description"].astype(str).str.strip()
    ).str.strip()
    return cleaned.reset_index(drop=True), metadata

def aggregate_history(cleaned: pd.DataFrame) -> pd.DataFrame:
    if cleaned.empty:
        return cleaned
    grouped = (
        cleaned.groupby(["Supplier", "Vendor_Item_Number", "Manufacturer", "Description"], dropna=False)
        .agg(
            Quantity=("Quantity", "sum"),
            Current_Total=("Current_Total", "sum"),
            Orders=("Order", "nunique"),
            First_Order_Date=("Order_Date", "min"),
            Last_Order_Date=("Order_Date", "max"),
        )
        .reset_index()
    )
    grouped["Current_Unit_Price"] = grouped["Current_Total"] / grouped["Quantity"]
    grouped["Prospect_Item_Name"] = (
        grouped["Manufacturer"].astype(str).str.strip()
        + " "
        + grouped["Description"].astype(str).str.strip()
    ).str.strip()
    return grouped


def score_catalog_match(row: pd.Series, catalog_row: pd.Series) -> tuple[float, str]:
    reasons = []
    prospect_name = f"{row.get('Manufacturer', '')} {row.get('Description', '')} {row.get('Vendor_Item_Number', '')}"
    source_name = (
        f"{catalog_row['Manufacturer']} {catalog_row['SourceClub_Item_Name']} "
        f"{catalog_row['Manufacturer_SKU']}"
    )

    sku_exact = normalize(row.get("Vendor_Item_Number")) == normalize(catalog_row["Manufacturer_SKU"])
    manufacturer_exact = normalize(row.get("Manufacturer")) == normalize(catalog_row["Manufacturer"])
    text_score = similarity(prospect_name, source_name)
    token_score = token_overlap(prospect_name, source_name)

    score = (0.45 * text_score) + (0.35 * token_score)
    if sku_exact:
        score += 0.35
        reasons.append("Strong SKU match")
    if manufacturer_exact:
        score += 0.12
        reasons.append("manufacturer match")
    if token_score >= 0.45:
        reasons.append("shared product terms")
    if text_score >= 0.72:
        reasons.append("strong description match")

    final_score = min(score, 1.0)
    if final_score < 0.55:
        return final_score, "Needs review: weak description/SKU signal"
    if final_score < 0.78:
        return final_score, "Partial match: " + (", ".join(reasons) or "closest description match")
    return final_score, ", ".join(reasons) or "Strong description match"


def match_items(history: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history

    matched_rows = []
    for _, row in history.iterrows():
        ranked = []
        for _, catalog_row in catalog.iterrows():
            score, reason = score_catalog_match(row, catalog_row)
            ranked.append((score, reason, catalog_row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        best_score, best_reason, best = ranked[0]

        if best_score >= 0.78:
            status = "Matched"
        elif best_score >= 0.55:
            status = "Needs Review"
        else:
            status = "No Match"

        current_price = float(row["Current_Unit_Price"])
        quantity = float(row["Quantity"])
        source_price = float(best["SourceClub_Price"]) if status != "No Match" else 0.0
        current_spend = current_price * quantity
        source_spend = source_price * quantity if status != "No Match" else 0.0

        matched_rows.append(
            {
                **row.to_dict(),
                "Suggested_SourceClub_Match": best["SourceClub_Item_Name"] if status != "No Match" else "",
                "SourceClub_Manufacturer_SKU": best["Manufacturer_SKU"] if status != "No Match" else "",
                "SourceClub_Price": source_price if status != "No Match" else None,
                "Match_Status": status,
                "Match_Confidence": round(best_score, 2),
                "Confidence_Band": confidence_band(best_score),
                "Match_Reason": best_reason if status != "No Match" else "Needs review: below confidence threshold",
                "Current_Spend": current_spend,
                "SourceClub_Spend": source_spend,
                "Projected_Savings": current_spend - source_spend if status != "No Match" else 0.0,
            }
        )

    return pd.DataFrame(matched_rows)


def apply_manual_review(reviewed: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    result = reviewed.copy()
    if "Reviewer_Selected_Match" not in result:
        result["Reviewer_Selected_Match"] = ""
    if "Reviewer_SourceClub_Price" not in result:
        result["Reviewer_SourceClub_Price"] = None
    catalog_lookup = catalog.set_index("SourceClub_Item_Name").to_dict("index")

    for idx, row in result.iterrows():
        selected = row.get("Reviewer_Selected_Match", "")
        override_price = number(row.get("Reviewer_SourceClub_Price"))
        if selected and selected in catalog_lookup:
            item = catalog_lookup[selected]
            source_price = override_price if override_price > 0 else float(item["SourceClub_Price"])
            result.at[idx, "Suggested_SourceClub_Match"] = selected
            result.at[idx, "SourceClub_Manufacturer_SKU"] = item["Manufacturer_SKU"]
            result.at[idx, "SourceClub_Price"] = source_price
            result.at[idx, "Match_Status"] = "Reviewed Match"
            result.at[idx, "Match_Confidence"] = 1.0
            result.at[idx, "Confidence_Band"] = "High"
            result.at[idx, "Match_Reason"] = "Human approved override"
            result.at[idx, "SourceClub_Spend"] = source_price * float(row["Quantity"])
            result.at[idx, "Projected_Savings"] = float(row["Current_Spend"]) - result.at[idx, "SourceClub_Spend"]
        current_source_price = number(row.get("SourceClub_Price"))
        price_changed = override_price > 0 and abs(override_price - current_source_price) > 0.005
        if not selected and price_changed and pd.notna(row.get("SourceClub_Price")):
            result.at[idx, "SourceClub_Price"] = override_price
            result.at[idx, "Match_Status"] = "Reviewed Price"
            result.at[idx, "Match_Confidence"] = max(float(row.get("Match_Confidence", 0)), 0.78)
            result.at[idx, "Confidence_Band"] = "High"
            result.at[idx, "Match_Reason"] = "Human price override"
            result.at[idx, "SourceClub_Spend"] = override_price * float(row["Quantity"])
            result.at[idx, "Projected_Savings"] = float(row["Current_Spend"]) - result.at[idx, "SourceClub_Spend"]
    return result


def benco_demo_raw() -> pd.DataFrame:
    rows = [
        ["", "", "", "", "", "", "", "", ""],
        ["Benco Dental", "", "", "", "", "Purchase Analysis:", "Item Detail", "", ""],
        ["Prepared For:", "CAROLINA DTL ARTS OF GOLDSBORO", "", "", "Account Number:", "90293215", "", "", ""],
        ["Report Description:", "This report includes All purchases between 8/4/2024 and 8/30/2025", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["1200 ANESTHETIC & ACCESSORIES", "", "", "", "", "", "", "", ""],
        ["Anesthetic - Lidocaines", "", "", "", "", "", "", "", ""],
        ["Order", "Item", "Mfgr", "Description", "Order Date", "Price", "Qty", "Amount", ""],
        ["BX900215", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "09/06/24", "$39.89", "2", "$79.78", ""],
        ["BX935041", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "09/17/24", "$39.89", "2", "$79.78", ""],
        ["BX994503", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "10/04/24", "$39.89", "2", "$79.78", ""],
        ["BY080297", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "10/29/24", "$39.89", "2", "$79.78", ""],
        ["BY124675", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "11/12/24", "$39.89", "1", "$39.89", ""],
        ["BY470898", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "03/04/25", "$50.15", "1", "$50.15", ""],
        ["BY518869", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "03/18/25", "$50.15", "2", "$100.30", ""],
        ["BY752939", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "05/28/25", "$50.15", "2", "$100.30", ""],
        ["BY793439", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "06/10/25", "$50.15", "1", "$50.15", ""],
        ["BY837162", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "06/24/25", "$50.15", "2", "$100.30", ""],
        ["BY892613", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "07/11/25", "$50.15", "1", "$50.15", ""],
        ["BZ034330", "3306-638", "BENCO", "GRAHAM LIDOCAINE 1:100 RED 50", "08/19/25", "$50.15", "3", "$150.45", ""],
        ["", "", "", "", "", "", "Total for Anesthetic - Lidocaines:", "", "$960.81"],
        ["Anesthetic - Mepivicaines", "", "", "", "", "", "", "", ""],
        ["Order", "Item", "Mfgr", "Description", "Order Date", "Price", "Qty", "Amount", ""],
        ["BY220583", "3306-656", "BENCO", "GRAHAM MEPIVACAINE 3% BX50", "12/11/24", "$51.56", "1", "$51.56", ""],
        ["", "", "", "", "", "", "Total for Anesthetic - Mepivicaines:", "", "$51.56"],
        ["Anesthetic - Articaine", "", "", "", "", "", "", "", ""],
        ["Order", "Item", "Mfgr", "Description", "Order Date", "Price", "Qty", "Amount", ""],
        ["BX840418", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "08/19/24", "$47.69", "5", "$238.45", ""],
        ["BX900215", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "09/06/24", "$47.69", "6", "$286.14", ""],
        ["BX935041", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "09/17/24", "$47.69", "3", "$143.07", ""],
        ["BX994503", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "10/04/24", "$47.69", "3", "$143.07", ""],
        ["BY037670", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "10/16/24", "$47.69", "5", "$238.45", ""],
        ["BY080297", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "10/29/24", "$47.69", "3", "$143.07", ""],
        ["BY124675", "4707-113", "PIERREL", "ORABLOC 4% W/EPI 1:100 GLD 50", "11/12/24", "$47.69", "3", "$143.07", ""],
        ["", "", "", "", "", "", "Total for Anesthetic - Articaine:", "", "$906.11"],
        ["Gloves", "", "", "", "", "", "", "", ""],
        ["Order", "Item", "Mfgr", "Description", "Order Date", "Price", "Qty", "Amount", ""],
        ["BZ100001", "GLV-MED-NIT", "MEDLINE", "Nitrile Gloves - Medium", "08/12/25", "$11.90", "20", "$238.00", ""],
        ["Preventive", "", "", "", "", "", "", "", ""],
        ["Order", "Item", "Mfgr", "Description", "Order Date", "Price", "Qty", "Amount", ""],
        ["BZ100114", "UNKNOWN-PASTE", "3M", "PROPHY PASTE MEDIUM MINT 200CT", "08/14/25", "$28.50", "4", "$114.00", ""],
    ]
    return pd.DataFrame(rows)


def read_upload(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, header=None, dtype=str)
    return pd.read_excel(uploaded_file, header=None, dtype=str)


def build_excel(
    metadata: dict[str, str],
    raw_cleaned: pd.DataFrame,
    aggregated: pd.DataFrame,
    final: pd.DataFrame,
    catalog: pd.DataFrame,
) -> bytes:
    output = io.BytesIO()
    summary = pd.DataFrame(
        [
            ["Prospect", metadata.get("Prepared For", "")],
            ["Supplier", metadata.get("Supplier", "")],
            ["Account Number", metadata.get("Account Number", "")],
            ["Current Spend", final["Current_Spend"].sum() if not final.empty else 0],
            ["SourceClub Spend", final["SourceClub_Spend"].sum() if not final.empty else 0],
            ["Projected Savings", final["Projected_Savings"].sum() if not final.empty else 0],
            ["Items Needing Review", int(final["Match_Status"].isin(["Needs Review", "No Match"]).sum()) if not final.empty else 0],
        ],
        columns=["Metric", "Value"],
    )
    architecture = pd.DataFrame(
        {
            "Step": [
                "Vendor cleanup",
                "Normalization",
                "Aggregation",
                "Matching",
                "Human review",
                "Export",
            ],
            "What happens": [
                "Find repeated Benco table headers and remove report headers/subtotals.",
                "Standardize columns into SourceClub's canonical purchase-history schema.",
                "Combine duplicate item purchases and calculate weighted current unit price.",
                "Use SKU, manufacturer, token overlap, and description similarity.",
                "Route low-confidence matches to a reviewer for approval.",
                "Generate the prospect-facing PDF and operator spreadsheet.",
            ],
        }
    )
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="Executive Summary", index=False)
        final.to_excel(writer, sheet_name="Savings Analysis", index=False)
        final[final["Match_Status"].isin(["Needs Review", "No Match"])].to_excel(
            writer, sheet_name="Review Queue", index=False
        )
        aggregated.to_excel(writer, sheet_name="Aggregated History", index=False)
        raw_cleaned.to_excel(writer, sheet_name="Cleaned Raw Lines", index=False)
        catalog.to_excel(writer, sheet_name="SourceClub Catalog", index=False)
        architecture.to_excel(writer, sheet_name="Architecture Notes", index=False)
    return output.getvalue()


def build_pdf(metadata: dict[str, str], final: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    if not REPORTLAB_AVAILABLE:
        return b""

    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=0.35 * inch,
        leftMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"{metadata.get('Prepared For', 'Prospect')} Savings Analysis", styles["Title"]),
        Paragraph(
            f"Supplier analyzed: {metadata.get('Supplier', 'Unknown')} | Prepared {date.today().isoformat()}",
            styles["Normal"],
        ),
        Spacer(1, 0.15 * inch),
    ]

    current = final["Current_Spend"].sum() if not final.empty else 0
    source = final["SourceClub_Spend"].sum() if not final.empty else 0
    savings = final["Projected_Savings"].sum() if not final.empty else 0
    review_count = int(final["Match_Status"].isin(["Needs Review", "No Match"]).sum()) if not final.empty else 0
    story.append(
        Paragraph(
            f"<b>Current spend:</b> {money(current)}    "
            f"<b>SourceClub spend:</b> {money(source)}    "
            f"<b>Projected savings:</b> {money(savings)}    "
            f"<b>Review items:</b> {review_count}",
            styles["Heading3"],
        )
    )

    table_rows = [["Prospect Item", "SourceClub Match", "Current", "SourceClub", "Qty", "Savings", "Status"]]
    for _, row in final.head(26).iterrows():
        table_rows.append(
            [
                str(row["Description"])[:36],
                str(row["Suggested_SourceClub_Match"] or "Needs review")[:38],
                money(row["Current_Unit_Price"]),
                money(row["SourceClub_Price"]) if pd.notna(row["SourceClub_Price"]) else "-",
                f"{row['Quantity']:,.0f}",
                money(row["Projected_Savings"]),
                str(row["Match_Status"]),
            ]
        )
    table = Table(table_rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6b73")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd")),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            "Notes: low-confidence and unmatched items are intentionally flagged for human review. "
            "Approved matches should be stored so future analyses become faster and more accurate.",
            styles["Normal"],
        )
    )
    doc.build(story)
    return output.getvalue()


def run_pipeline(raw: pd.DataFrame, catalog: pd.DataFrame):
    cleaned, metadata = clean_purchase_history(raw)
    aggregated = aggregate_history(cleaned)
    matched = match_items(aggregated, catalog)
    return cleaned, metadata, aggregated, matched


st.title("SourceClub Savings Analysis Automation")
st.caption("Built around the real Benco workflow: messy purchase-history export in, matched PDF and spreadsheet out.")

catalog = st.data_editor(
    CATALOG,
    hide_index=True,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "SourceClub_Price": st.column_config.NumberColumn("SourceClub Price", format="$%.2f"),
        "Pack_Size": st.column_config.NumberColumn("Pack Size"),
    },
)

tab_upload, tab_demo, tab_manual, tab_architecture = st.tabs(
    ["Vendor Upload + Cleanup", "Benco Demo", "Manual Entry", "Architecture"]
)

raw_df: pd.DataFrame | None = None
data_source = ""

with tab_upload:
    st.subheader("Upload raw vendor purchase history")
    st.markdown(
        "<div class='small-note'>This accepts the messy Benco-style export shown in the Loom: branded header rows, repeated table headers, category rows, subtotals, and line items in one sheet.</div>",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader("Upload Benco CSV/XLSX", type=["csv", "xlsx", "xls"])
    if uploaded:
        raw_df = read_upload(uploaded)
        data_source = uploaded.name
        st.write("Raw upload preview")
        st.dataframe(raw_df.head(25), use_container_width=True)

with tab_demo:
    st.subheader("Realistic Benco demo")
    st.markdown(
        "<div class='small-note'>Use this in the Loom walkthrough to show the before/after cleanup and matching flow without needing a private customer file.</div>",
        unsafe_allow_html=True,
    )
    if st.button("Load realistic Benco export", type="primary"):
        st.session_state["demo_loaded"] = True
    if st.session_state.get("demo_loaded"):
        raw_df = benco_demo_raw()
        data_source = "Built-in Benco demo"
        st.dataframe(raw_df, use_container_width=True, height=360)

with tab_manual:
    st.subheader("Manual entry fallback")
    st.markdown(
        "<div class='small-note'>This is the fallback when a prospect sends only a few line items or an export format the parser does not know yet.</div>",
        unsafe_allow_html=True,
    )
    manual = st.data_editor(
        pd.DataFrame(
            [
                {
                    "Order": "MANUAL-1",
                    "Vendor_Item_Number": "3306-638",
                    "Manufacturer": "Benco",
                    "Description": "GRAHAM LIDOCAINE 1:100 RED 50",
                    "Order_Date": "",
                    "Current_Unit_Price": 39.89,
                    "Quantity": 12,
                    "Current_Total": 478.68,
                }
            ]
        ),
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
    )
    if st.button("Use manual rows"):
        raw_df = manual
        data_source = "Manual entry"

with tab_architecture:
    st.subheader("Production architecture")
    st.markdown(
        """
        1. **Intake:** upload, email attachment, or vendor portal export.
        2. **Vendor parser:** detect Benco/Patterson/Henry Schein layouts, remove branded report chrome, normalize columns.
        3. **Aggregation:** combine duplicate purchases so savings are calculated on true volume.
        4. **Matching engine:** exact SKU, approved match memory, fuzzy text, pack-size/unit logic, and AI for ambiguous descriptions.
        5. **Human review:** low-confidence matches go to a review queue; approved decisions become match memory.
        6. **Output:** prospect PDF, operator spreadsheet, HubSpot attachment, and sales notification.
        """
    )
    st.info(
        "The key design choice is not full automation at all costs. The system should automate the obvious 70-85%, make the uncertain 15-30% easy to review, and learn from every approved match."
    )

if raw_df is None:
    st.info("Load the Benco demo, upload a vendor file, or use manual rows to run the savings analysis.")
    st.stop()

cleaned, metadata, aggregated, matched = run_pipeline(raw_df, catalog)

if cleaned.empty:
    st.error(
        "No purchase-history rows were found. The parser looks for Benco-style repeated headers with Order, Item, Mfgr, Description, Order Date, Price, Qty, and Amount."
    )
    st.stop()

st.divider()
initial_current_total = matched["Current_Spend"].sum() if not matched.empty else 0
initial_savings_total = matched["Projected_Savings"].sum() if not matched.empty else 0
confidence_counts = matched["Confidence_Band"].value_counts().to_dict() if "Confidence_Band" in matched else {}

st.subheader("Executive snapshot")
snapshot_cols = st.columns(5)
snapshot_cols[0].metric("Total items processed", f"{len(aggregated):,}")
snapshot_cols[1].metric("Potential savings", money(initial_savings_total))
snapshot_cols[2].metric("High confidence", f"{confidence_counts.get('High', 0):,}")
snapshot_cols[3].metric("Medium confidence", f"{confidence_counts.get('Medium', 0):,}")
snapshot_cols[4].metric("Low confidence", f"{confidence_counts.get('Low', 0):,}")

flow_cols = st.columns(4)
flow_cols[0].markdown("<div class='flow-card'><strong>1. Clean vendor export</strong><span class='small-note'>Remove Benco headers, subtotals, blanks, and repeated table chrome.</span></div>", unsafe_allow_html=True)
flow_cols[1].markdown("<div class='flow-card'><strong>2. Normalize purchases</strong><span class='small-note'>Convert raw rows into one canonical purchase-history table.</span></div>", unsafe_allow_html=True)
flow_cols[2].markdown("<div class='flow-card'><strong>3. Match and review</strong><span class='small-note'>Auto-match confident rows and route uncertain rows to review.</span></div>", unsafe_allow_html=True)
flow_cols[3].markdown("<div class='flow-card'><strong>4. Export package</strong><span class='small-note'>Generate the prospect PDF, detailed spreadsheet, and cleaned CSV.</span></div>", unsafe_allow_html=True)

st.subheader("1. Vendor cleanup result")
meta_cols = st.columns(4)
meta_cols[0].metric("Prospect", metadata.get("Prepared For", "Unknown"))
meta_cols[1].metric("Supplier", metadata.get("Supplier", "Unknown"))
meta_cols[2].metric("Raw lines found", f"{len(cleaned):,}")
meta_cols[3].metric("Unique items", f"{len(aggregated):,}")

with st.expander("Show cleaned purchase-history lines"):
    st.dataframe(cleaned, use_container_width=True)

st.subheader("2. Aggregated purchase history")
st.dataframe(
    aggregated[
        [
            "Vendor_Item_Number",
            "Manufacturer",
            "Description",
            "Quantity",
            "Current_Unit_Price",
            "Current_Total",
            "Orders",
        ]
    ],
    use_container_width=True,
    column_config={
        "Current_Unit_Price": st.column_config.NumberColumn("Weighted Current Price", format="$%.2f"),
        "Current_Total": st.column_config.NumberColumn("Current Spend", format="$%.2f"),
    },
)

st.subheader("3. Match review queue")
review_options = [""] + catalog["SourceClub_Item_Name"].tolist()
review_input = matched.copy()
review_input["Reviewer_Selected_Match"] = ""
review_input["Reviewer_SourceClub_Price"] = review_input["SourceClub_Price"]

low_confidence = review_input[review_input["Confidence_Band"].isin(["Medium", "Low"])]
if not low_confidence.empty:
    st.warning(
        f"{len(low_confidence)} row(s) need an operator look before sending. Use the override columns on the right to approve a different item or price."
    )
    st.dataframe(
        low_confidence[
            [
                "Vendor_Item_Number",
                "Description",
                "Suggested_SourceClub_Match",
                "Confidence_Band",
                "Match_Confidence",
                "Match_Reason",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("All matched rows cleared the high-confidence threshold. Review is still available for price overrides.")

reviewed = st.data_editor(
    review_input,
    hide_index=True,
    use_container_width=True,
    column_order=[
        "Vendor_Item_Number",
        "Manufacturer",
        "Description",
        "Quantity",
        "Current_Unit_Price",
        "Suggested_SourceClub_Match",
        "SourceClub_Price",
        "Match_Status",
        "Confidence_Band",
        "Match_Confidence",
        "Match_Reason",
        "Reviewer_Selected_Match",
        "Reviewer_SourceClub_Price",
    ],
    column_config={
        "Current_Unit_Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
        "SourceClub_Price": st.column_config.NumberColumn("SourceClub Price", format="$%.2f"),
        "Match_Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
        "Confidence_Band": st.column_config.TextColumn("Band"),
        "Reviewer_Selected_Match": st.column_config.SelectboxColumn(
            "Reviewer Override",
            options=review_options,
            help="Use this when the suggested match is wrong or the item was below the auto-match threshold.",
        ),
        "Reviewer_SourceClub_Price": st.column_config.NumberColumn(
            "Override Price",
            format="$%.2f",
            help="Optional. Enter a corrected SourceClub price without changing the catalog.",
        ),
    },
    disabled=[
        "Vendor_Item_Number",
        "Manufacturer",
        "Description",
        "Quantity",
        "Current_Unit_Price",
        "Suggested_SourceClub_Match",
        "SourceClub_Price",
        "Match_Status",
        "Match_Confidence",
        "Confidence_Band",
        "Match_Reason",
    ],
)

final = apply_manual_review(reviewed, catalog)

current_total = final["Current_Spend"].sum()
source_total = final["SourceClub_Spend"].sum()
savings_total = final["Projected_Savings"].sum()
review_count = int(final["Match_Status"].isin(["Needs Review", "No Match"]).sum())
savings_rate = savings_total / current_total if current_total else 0
final_confidence_counts = final["Confidence_Band"].value_counts().to_dict() if "Confidence_Band" in final else {}

st.subheader("4. Prospect-ready savings package")
metric_cols = st.columns(6)
metric_cols[0].metric("Items Processed", f"{len(final):,}")
metric_cols[1].metric("Current Spend", money(current_total))
metric_cols[2].metric("SourceClub Spend", money(source_total))
metric_cols[3].metric("Projected Savings", money(savings_total))
metric_cols[4].metric("Savings Rate", f"{savings_rate:.1%}")
metric_cols[5].metric("Needs Review", f"{review_count:,}")

band_cols = st.columns(3)
band_cols[0].metric("High Confidence", f"{final_confidence_counts.get('High', 0):,}")
band_cols[1].metric("Medium Confidence", f"{final_confidence_counts.get('Medium', 0):,}")
band_cols[2].metric("Low Confidence", f"{final_confidence_counts.get('Low', 0):,}")

if review_count:
    st.markdown(
        f"<div class='review-box'><b>{review_count} item(s) need review.</b> This is intentional: the system automates confident matches and exposes uncertain matches before the prospect sees the final report.</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='success-box'><b>All items are matched or reviewed.</b> The prospect PDF and detailed operator spreadsheet are ready to export.</div>",
        unsafe_allow_html=True,
    )

st.dataframe(
    final[
        [
            "Description",
            "Suggested_SourceClub_Match",
            "Current_Unit_Price",
            "SourceClub_Price",
            "Quantity",
            "Current_Spend",
            "SourceClub_Spend",
            "Projected_Savings",
            "Match_Status",
            "Confidence_Band",
            "Match_Reason",
        ]
    ],
    use_container_width=True,
    column_config={
        "Current_Unit_Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
        "SourceClub_Price": st.column_config.NumberColumn("SourceClub Price", format="$%.2f"),
        "Current_Spend": st.column_config.NumberColumn("Current Spend", format="$%.2f"),
        "SourceClub_Spend": st.column_config.NumberColumn("SourceClub Spend", format="$%.2f"),
        "Projected_Savings": st.column_config.NumberColumn("Projected Savings", format="$%.2f"),
    },
)

xlsx = build_excel(metadata, cleaned, aggregated, final, catalog)
pdf = build_pdf(metadata, final)

download_cols = st.columns(3)
download_cols[0].download_button(
    "Download detailed spreadsheet",
    data=xlsx,
    file_name="sourceclub_savings_analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
if REPORTLAB_AVAILABLE and pdf:
    download_cols[1].download_button(
        "Download prospect PDF",
        data=pdf,
        file_name="sourceclub_savings_analysis.pdf",
        mime="application/pdf",
        type="primary",
    )
else:
    download_cols[1].warning("PDF export needs reportlab in requirements.txt.")
download_cols[2].download_button(
    "Download cleaned CSV",
    data=cleaned.to_csv(index=False).encode("utf-8"),
    file_name="cleaned_purchase_history.csv",
    mime="text/csv",
)

st.caption(f"Data source: {data_source}. Prototype assumes annual period if the vendor export covers the trailing 12 months.")

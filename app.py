"""
Source Club — Savings Analysis Automation
==========================================
AI-powered dental supply savings analysis.

Deploy on Render:
  • Set env var  ANTHROPIC_API_KEY  in the Render dashboard.
  • The app auto-loads it — reviewers never type a key.
  • Demo results are pre-baked, so every tab is live on first load.
"""

import os, json, io, time
from datetime import datetime

import streamlit as st
import pandas as pd
import anthropic

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Source Club | Savings Analysis",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root{
  --primary:#1a56db;--success:#057a55;--warn:#c27803;
  --danger:#c81e1e;--border:#e5e7eb;
}
/* Hero banner */
.hero{background:linear-gradient(135deg,#1a56db 0%,#1e429f 100%);
      color:#fff;padding:2rem 2.5rem;border-radius:14px;margin-bottom:1.5rem;}
.hero h1{font-size:2rem;margin:0;font-weight:800;}
.hero p{margin:.4rem 0 0;opacity:.85;font-size:1.05rem;}

/* Metric cards */
.metric-row{display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap;}
.metric-card{flex:1;min-width:140px;background:#fff;border:1px solid var(--border);
             border-radius:10px;padding:1rem 1.2rem;text-align:center;
             box-shadow:0 1px 4px rgba(0,0,0,.07);}
.metric-card .val{font-size:1.75rem;font-weight:700;color:var(--primary);}
.metric-card .lbl{font-size:.78rem;color:#6b7280;margin-top:2px;}

/* Confidence badges */
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.78rem;font-weight:600;}
.badge-high{background:#d1fae5;color:#065f46;}
.badge-med {background:#fef3c7;color:#92400e;}
.badge-low {background:#fee2e2;color:#991b1b;}
.badge-none{background:#f3f4f6;color:#6b7280;}

/* Section headings */
.section-title{font-size:1.1rem;font-weight:700;margin:1.5rem 0 .75rem;
               color:#111827;border-bottom:2px solid var(--primary);padding-bottom:4px;}

/* Review cards */
.review-card{background:#fff;border:1px solid var(--border);
             border-radius:10px;padding:1rem 1.2rem;margin-bottom:.75rem;}
.review-card.flagged{border-left:4px solid #f59e0b;}

/* Big savings callout */
.savings-hero{background:linear-gradient(135deg,#057a55,#046c4e);color:#fff;
              padding:1.75rem 2rem;border-radius:14px;text-align:center;margin:1rem 0;}
.savings-hero .big{font-size:3.2rem;font-weight:800;}
.savings-hero .sub{font-size:1rem;opacity:.85;margin-top:4px;}

/* Prospect one-pager */
.prospect-card{background:#fff;border:2px solid var(--primary);border-radius:14px;
               padding:2rem 2.5rem;box-shadow:0 4px 16px rgba(0,0,0,.10);}
.prospect-card h2{margin:0 0 .25rem;font-size:1.6rem;color:#111827;}
.prospect-card .sub-h{color:#6b7280;font-size:.95rem;margin-bottom:1.5rem;}
.save-pill{display:inline-block;background:#d1fae5;color:#065f46;
           font-weight:700;font-size:1.1rem;padding:.35rem 1.1rem;border-radius:999px;}
.prospect-table{width:100%;border-collapse:collapse;font-size:.88rem;margin-top:.75rem;}
.prospect-table th{background:#f3f4f6;padding:.5rem .75rem;text-align:left;
                   border-bottom:2px solid var(--border);font-weight:600;}
.prospect-table td{padding:.45rem .75rem;border-bottom:1px solid var(--border);}
.prospect-table tr:last-child td{border-bottom:none;}
.green{color:#057a55;font-weight:600;}

/* Arch box */
.arch-box{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;
          padding:1.2rem 1.5rem;font-size:.9rem;line-height:1.8;}

/* Demo banner */
.demo-banner{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;
             padding:.75rem 1rem;margin-bottom:1rem;font-size:.9rem;color:#92400e;}

#MainMenu,footer{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE DATA
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_PROSPECT = pd.DataFrame([
    {"Item Description":"Nitrile Exam Gloves Medium Powder Free 100/box", "SKU":"HEN-MD-100",    "Unit Price":8.50,  "Qty/Month":20,"Supplier":"Henry Schein"},
    {"Item Description":"Nitrile Gloves Large PF Box 100ct",              "SKU":"PAT-LG-NIT",    "Unit Price":9.10,  "Qty/Month":15,"Supplier":"Patterson"},
    {"Item Description":"Prophy Paste Medium Grit Mint 200/box",          "SKU":"ULT-PPM-200",   "Unit Price":42.00, "Qty/Month":4, "Supplier":"Ultradent"},
    {"Item Description":"Dental Floss Waxed 200m",                        "SKU":"ORB-FLW-200",   "Unit Price":3.20,  "Qty/Month":30,"Supplier":"Oral-B"},
    {"Item Description":"3M ESPE Clinpro 5000 Toothpaste 113g",           "SKU":"3M-CP5000",     "Unit Price":14.75, "Qty/Month":8, "Supplier":"3M"},
    {"Item Description":"Cavitron Inserts 30K FSI-1000",                  "SKU":"DEN-CAV-30K",   "Unit Price":28.00, "Qty/Month":2, "Supplier":"Dentsply"},
    {"Item Description":"Disposable Saliva Ejectors Blue 100/bag",        "SKU":"MCK-SEJ-100",   "Unit Price":4.50,  "Qty/Month":10,"Supplier":"McKesson"},
    {"Item Description":"Autoclave Sterilization Pouches 3.5x9 200/box",  "SKU":"MDT-POUCH-200", "Unit Price":18.00, "Qty/Month":5, "Supplier":"Medline"},
    {"Item Description":"Dental Bibs 13x18 2ply 500/case",                "SKU":"HEN-BIB-500",   "Unit Price":22.00, "Qty/Month":3, "Supplier":"Henry Schein"},
    {"Item Description":"Fluoride Varnish 5% NaF 0.4mL 35/box",          "SKU":"COLT-FV-35",    "Unit Price":65.00, "Qty/Month":2, "Supplier":"Colgate"},
])

SAMPLE_CATALOG = pd.DataFrame([
    {"Product Name":"Sempermed Nitrile Exam Gloves Medium PF 100ct",       "SC_SKU":"SC-NIT-M100",  "Source Club Price":5.80},
    {"Product Name":"Sempermed Nitrile Gloves Large Powder-Free Box/100",  "SC_SKU":"SC-NIT-L100",  "Source Club Price":6.10},
    {"Product Name":"Young Innovations Prophy Paste Medium Mint 200pk",    "SC_SKU":"SC-PP-MED-200","Source Club Price":28.50},
    {"Product Name":"GUM Waxed Dental Floss 200 meter",                    "SC_SKU":"SC-FLW-200M",  "Source Club Price":1.95},
    {"Product Name":"Clinpro 5000 Anti-Cavity Toothpaste 4oz (113g)",      "SC_SKU":"SC-3M-CP5K",   "Source Club Price":10.20},
    {"Product Name":"Dentsply Cavitron 30K Insert FSI-1000 Tip",           "SC_SKU":"SC-CAV-FSI30", "Source Club Price":19.50},
    {"Product Name":"Saliva Ejectors Disposable Blue 100/pk",              "SC_SKU":"SC-SALEJ-100", "Source Club Price":2.80},
    {"Product Name":"Sterilization Pouches Self-Seal 3.5x9 in 200ct",      "SC_SKU":"SC-STER-P200", "Source Club Price":11.00},
    {"Product Name":"Tidi Patient Bibs 13x18 2-ply 500/cs",                "SC_SKU":"SC-BIB-500CS", "Source Club Price":14.50},
    {"Product Name":"Colgate PreviDent Fluoride Varnish 5% NaF 35/bx",    "SC_SKU":"SC-FV-5PCT",   "Source Club Price":44.00},
    {"Product Name":"Latex Exam Gloves Medium Powdered 100ct",             "SC_SKU":"SC-LAT-M100",  "Source Club Price":4.20},
    {"Product Name":"Cotton Rolls #2 Medium 2000/case",                    "SC_SKU":"SC-CR-MED-2K", "Source Club Price":16.00},
])

# Pre-baked demo matches — shown instantly, no API call needed
DEMO_MATCHES = [
    {"idx":0,"description":"Nitrile Exam Gloves Medium Powder Free 100/box","sku":"HEN-MD-100","supplier":"Henry Schein","their_price":8.50,"qty_per_month":20,"sc_sku":"SC-NIT-M100","matched_name":"Sempermed Nitrile Exam Gloves Medium PF 100ct","sc_price":5.80,"confidence":96,"reasoning":"Same type, size, pack qty. Brand substitution only — Sempermed is a recognized equivalent.","pack_size_note":"same"},
    {"idx":1,"description":"Nitrile Gloves Large PF Box 100ct","sku":"PAT-LG-NIT","supplier":"Patterson","their_price":9.10,"qty_per_month":15,"sc_sku":"SC-NIT-L100","matched_name":"Sempermed Nitrile Gloves Large Powder-Free Box/100","sc_price":6.10,"confidence":95,"reasoning":"Identical type, size (Large), pack size (100), and PF spec.","pack_size_note":"same"},
    {"idx":2,"description":"Prophy Paste Medium Grit Mint 200/box","sku":"ULT-PPM-200","supplier":"Ultradent","their_price":42.00,"qty_per_month":4,"sc_sku":"SC-PP-MED-200","matched_name":"Young Innovations Prophy Paste Medium Mint 200pk","sc_price":28.50,"confidence":88,"reasoning":"Same grit and flavor, same pack count. Different manufacturer — flagged for review.","pack_size_note":"same"},
    {"idx":3,"description":"Dental Floss Waxed 200m","sku":"ORB-FLW-200","supplier":"Oral-B","their_price":3.20,"qty_per_month":30,"sc_sku":"SC-FLW-200M","matched_name":"GUM Waxed Dental Floss 200 meter","sc_price":1.95,"confidence":93,"reasoning":"Same wax type and exact length (200m). GUM is a standard clinical equivalent.","pack_size_note":"same"},
    {"idx":4,"description":"3M ESPE Clinpro 5000 Toothpaste 113g","sku":"3M-CP5000","supplier":"3M","their_price":14.75,"qty_per_month":8,"sc_sku":"SC-3M-CP5K","matched_name":"Clinpro 5000 Anti-Cavity Toothpaste 4oz (113g)","sc_price":10.20,"confidence":99,"reasoning":"Same product — 113g = 4oz confirmed. Source Club has negotiated pricing direct with 3M.","pack_size_note":"same"},
    {"idx":5,"description":"Cavitron Inserts 30K FSI-1000","sku":"DEN-CAV-30K","supplier":"Dentsply","their_price":28.00,"qty_per_month":2,"sc_sku":"SC-CAV-FSI30","matched_name":"Dentsply Cavitron 30K Insert FSI-1000 Tip","sc_price":19.50,"confidence":99,"reasoning":"Exact same product, manufacturer, and model number. Direct catalog match.","pack_size_note":"same"},
    {"idx":6,"description":"Disposable Saliva Ejectors Blue 100/bag","sku":"MCK-SEJ-100","supplier":"McKesson","their_price":4.50,"qty_per_month":10,"sc_sku":"SC-SALEJ-100","matched_name":"Saliva Ejectors Disposable Blue 100/pk","sc_price":2.80,"confidence":94,"reasoning":"Same color and quantity. 'bag' vs 'pk' is identical packaging terminology.","pack_size_note":"same"},
    {"idx":7,"description":"Autoclave Sterilization Pouches 3.5x9 200/box","sku":"MDT-POUCH-200","supplier":"Medline","their_price":18.00,"qty_per_month":5,"sc_sku":"SC-STER-P200","matched_name":"Sterilization Pouches Self-Seal 3.5x9 in 200ct","sc_price":11.00,"confidence":92,"reasoning":"Same dimensions (3.5×9 in), same count (200), self-seal autoclave type.","pack_size_note":"same"},
    {"idx":8,"description":"Dental Bibs 13x18 2ply 500/case","sku":"HEN-BIB-500","supplier":"Henry Schein","their_price":22.00,"qty_per_month":3,"sc_sku":"SC-BIB-500CS","matched_name":"Tidi Patient Bibs 13x18 2-ply 500/cs","sc_price":14.50,"confidence":97,"reasoning":"Same dimensions (13×18), same ply (2-ply), same case count (500). Tidi is industry-standard.","pack_size_note":"same"},
    {"idx":9,"description":"Fluoride Varnish 5% NaF 0.4mL 35/box","sku":"COLT-FV-35","supplier":"Colgate","their_price":65.00,"qty_per_month":2,"sc_sku":"SC-FV-5PCT","matched_name":"Colgate PreviDent Fluoride Varnish 5% NaF 35/bx","sc_price":44.00,"confidence":99,"reasoning":"Same manufacturer, same concentration (5% NaF), same unit dose size (0.4mL), same count (35).","pack_size_note":"same"},
]

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def _init():
    defaults = dict(
        matches=DEMO_MATCHES.copy(),   # pre-loaded so every tab works on open
        reviewed={},
        edited_price={},
        analysis_done=True,            # demo is already "run"
        demo_mode=True,                # flag shown in UI
        prospect_df=SAMPLE_PROSPECT.copy(),
        catalog_df=SAMPLE_CATALOG.copy(),
        prospect_name="Valley Dental Group",
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# ─────────────────────────────────────────────────────────────────────────────
# API KEY  — env var first, sidebar fallback
# ─────────────────────────────────────────────────────────────────────────────
ENV_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if "api_key" not in st.session_state:
    st.session_state.api_key = ENV_KEY

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🦷 Source Club")
    st.markdown("**Savings Analysis Tool**")
    st.divider()

    st.markdown("### ⚙️ Settings")

    if ENV_KEY:
        st.success("✅ API key loaded from environment")
    else:
        manual_key = st.text_input(
            "Anthropic API Key",
            type="password",
            value=st.session_state.api_key,
            placeholder="sk-ant-...",
            help="Or set ANTHROPIC_API_KEY env var on Render.",
        )
        if manual_key:
            st.session_state.api_key = manual_key

    confidence_threshold = st.slider(
        "Auto-accept threshold",
        min_value=50, max_value=95, value=80, step=5,
        help="Matches at or above this score are auto-accepted. Below → Review Queue.",
    )

    st.divider()
    st.markdown("### 🏗️ Pipeline")
    st.markdown("""
<div class="arch-box">
1️⃣ <b>Upload</b> prospect CSV + catalog<br>
2️⃣ <b>Parse</b> &amp; normalize<br>
3️⃣ <b>AI Match</b> via Claude<br>
4️⃣ <b>Score</b> confidence 0–100<br>
5️⃣ <b>Route</b> high → auto / low → review<br>
6️⃣ <b>Report</b> internal + prospect one-pager
</div>
""", unsafe_allow_html=True)

    st.divider()
    st.caption("Source Club · Savings Analysis v2.1")

# ─────────────────────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🦷 Savings Analysis Automation</h1>
  <p>Upload a prospect's purchase history · AI matches every line item · Generate a savings report in seconds.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def confidence_badge(score):
    if score is None:
        return '<span class="badge badge-none">N/A</span>'
    if score >= 80:
        return f'<span class="badge badge-high">✓ {score}%</span>'
    if score >= 55:
        return f'<span class="badge badge-med">~ {score}%</span>'
    return f'<span class="badge badge-low">? {score}%</span>'


def calc_rows(matches, reviewed, edited_price, threshold):
    out = []
    for m in matches:
        idx   = m["idx"]
        dec   = reviewed.get(idx)
        ep    = edited_price.get(idx, m["sc_price"])
        conf  = m["confidence"]
        auto  = conf is not None and conf >= threshold and m["sc_sku"] is not None

        if   dec == "reject":               include = False
        elif dec in ("accept", "edit"):     include = True
        elif auto:                          include = True
        else:                               include = False

        use_price = ep if include else None
        mo_their  = m["their_price"] * m["qty_per_month"]
        mo_sc     = (use_price or 0) * m["qty_per_month"] if include and use_price else None
        mo_save   = (mo_their - mo_sc) if mo_sc is not None else None

        status = (
            "Auto-accepted" if (auto and dec != "reject") else
            "Accepted"      if dec == "accept" else
            "Edited"        if dec == "edit"   else
            "Rejected"      if dec == "reject" else
            "Pending Review"
        )

        out.append({**m,
            "eff_sc_price": ep,
            "include": include,
            "monthly_their": mo_their,
            "monthly_sc": mo_sc,
            "monthly_save": mo_save,
            "annual_save": mo_save * 12 if mo_save is not None else None,
            "status": status,
        })
    return out


def make_excel(rows, prospect_name, total_their, total_sc, total_save, pct_save, matched):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        # Sheet 1 – Summary
        pd.DataFrame({
            "Metric": ["Prospect","Analysis Date","Current Annual Spend",
                        "Source Club Annual Cost","Annual Savings",
                        "Monthly Savings","Savings %","Items Analyzed","Items Matched"],
            "Value":  [prospect_name, datetime.today().strftime("%B %d, %Y"),
                       f"${total_their:,.2f}", f"${total_sc:,.2f}",
                       f"${total_save:,.2f}", f"${total_save/12:,.2f}",
                       f"{pct_save:.1f}%", len(rows), matched],
        }).to_excel(w, sheet_name="Summary", index=False)

        # Sheet 2 – Line Items
        detail = []
        for r in rows:
            detail.append({
                "Prospect Item":    r["description"],
                "Prospect SKU":     r["sku"],
                "Supplier":         r["supplier"],
                "Their Price":      r["their_price"],
                "Qty/Month":        r["qty_per_month"],
                "SC Match":         r["matched_name"] or "No match",
                "SC SKU":           r["sc_sku"] or "—",
                "SC Price":         r["eff_sc_price"] or "",
                "Unit Savings":     (r["their_price"] - (r["eff_sc_price"] or r["their_price"])) if r["include"] else "",
                "Monthly Savings":  r["monthly_save"] or "",
                "Annual Savings":   r["annual_save"] or "",
                "Confidence %":     r["confidence"],
                "AI Reasoning":     r["reasoning"],
                "Status":           r["status"],
            })
        pd.DataFrame(detail).to_excel(w, sheet_name="Line Items", index=False)

        # Sheet 3 – Unmatched
        unmatched = [r for r in rows if not r["sc_sku"] or r["sc_sku"] == "MANUAL"]
        if unmatched:
            pd.DataFrame([{
                "Item": r["description"], "SKU": r["sku"],
                "Their Price": r["their_price"], "Note": r["reasoning"]
            } for r in unmatched]).to_excel(w, sheet_name="Unmatched Items", index=False)

    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# AI MATCHING
# ─────────────────────────────────────────────────────────────────────────────
def run_matching(prospect_df, catalog_df, api_key, progress, status_text):
    client       = anthropic.Anthropic(api_key=api_key)
    catalog_json = catalog_df.to_json(orient="records", indent=2)
    results      = []
    total        = len(prospect_df)

    for i, row in prospect_df.iterrows():
        status_text.text(f"Matching {i+1}/{total}: {str(row.get('Item Description',''))[:55]}…")
        progress.progress(i / total)

        item = {
            "description":   str(row.get("Item Description", "")),
            "sku":           str(row.get("SKU", "")),
            "unit_price":    float(row.get("Unit Price", 0)),
            "qty_per_month": float(row.get("Qty/Month", 0)),
            "supplier":      str(row.get("Supplier", "")),
        }

        prompt = f"""You are a dental supply product-matching expert for Source Club.

Match the PROSPECT ITEM to the best product in the SOURCE CLUB CATALOG.

PROSPECT ITEM:
{json.dumps(item, indent=2)}

SOURCE CLUB CATALOG:
{catalog_json}

RULES
• Match on product TYPE and FUNCTION first
• Pack sizes must be equivalent (100/box = 100ct = Box/100)
• Different brands are acceptable if functionally identical
• Size/grade MUST match (Medium ≠ Large)
• If no reasonable match exists, set sc_sku to null

Respond ONLY with raw JSON — no markdown, no explanation:
{{
  "sc_sku": "<SC_SKU or null>",
  "matched_product_name": "<name or null>",
  "confidence": <0-100>,
  "reasoning": "<one sentence>",
  "pack_size_note": "<adjustment needed or 'same'>"
}}"""

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            raw  = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
            data = json.loads(raw)
        except Exception as e:
            data = {"sc_sku": None, "matched_product_name": None,
                    "confidence": 0, "reasoning": f"Error: {e}", "pack_size_note": "N/A"}

        sc_price = None
        if data.get("sc_sku"):
            mask = catalog_df["SC_SKU"] == data["sc_sku"]
            if mask.any():
                sc_price = float(catalog_df.loc[mask, "Source Club Price"].iloc[0])

        results.append({
            "idx":           i,
            "description":   item["description"],
            "sku":           item["sku"],
            "supplier":      item["supplier"],
            "their_price":   item["unit_price"],
            "qty_per_month": item["qty_per_month"],
            "sc_sku":        data.get("sc_sku"),
            "matched_name":  data.get("matched_product_name"),
            "sc_price":      sc_price,
            "confidence":    data.get("confidence"),
            "reasoning":     data.get("reasoning", ""),
            "pack_size_note":data.get("pack_size_note", "same"),
        })

    progress.progress(1.0)
    status_text.text("✅ Matching complete!")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤  Upload & Match",
    "🔍  Review Queue",
    "📊  Internal Report",
    "📄  Prospect One-Pager",
    "🏗️  Architecture",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — UPLOAD & MATCH
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if st.session_state.demo_mode:
        st.markdown("""
<div class="demo-banner">
  🎯 <b>Demo mode:</b> Sample data pre-loaded. All tabs are live — explore the full workflow now.
  Uncheck the box below to upload your own files and run live AI matching.
</div>""", unsafe_allow_html=True)

    use_sample = st.checkbox(
        "Use sample demo data (no upload needed)",
        value=st.session_state.demo_mode,
    )

    if use_sample:
        st.session_state.prospect_df  = SAMPLE_PROSPECT.copy()
        st.session_state.catalog_df   = SAMPLE_CATALOG.copy()
        st.session_state.demo_mode    = True
        if not st.session_state.analysis_done:
            st.session_state.matches      = DEMO_MATCHES.copy()
            st.session_state.analysis_done= True

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Prospect Purchase History (10 items)**")
            st.dataframe(SAMPLE_PROSPECT, use_container_width=True, height=260)
        with col2:
            st.markdown("**Source Club Catalog (12 products)**")
            st.dataframe(SAMPLE_CATALOG, use_container_width=True, height=260)
    else:
        st.session_state.demo_mode = False
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Prospect Purchase History**")
            st.caption("Required columns: `Item Description`, `Unit Price`, `Qty/Month`")
            pf = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"], key="pf")
            if pf:
                st.session_state.prospect_df = pd.read_csv(pf) if pf.name.endswith(".csv") else pd.read_excel(pf)
                st.dataframe(st.session_state.prospect_df, use_container_width=True, height=220)
        with col2:
            st.markdown("**Source Club Catalog**")
            st.caption("Required columns: `Product Name`, `SC_SKU`, `Source Club Price`")
            cf = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"], key="cf")
            if cf:
                st.session_state.catalog_df = pd.read_csv(cf) if cf.name.endswith(".csv") else pd.read_excel(cf)
                st.dataframe(st.session_state.catalog_df, use_container_width=True, height=220)

    st.markdown('<div class="section-title">Run AI Matching</div>', unsafe_allow_html=True)

    active_key = ENV_KEY or st.session_state.api_key
    ready = (
        st.session_state.prospect_df is not None and
        st.session_state.catalog_df  is not None and
        bool(active_key)
    )

    if not active_key:
        st.warning("⚠️ No Anthropic API key found. Set ANTHROPIC_API_KEY on Render or enter one in the sidebar.")

    if st.button("🤖  Run Live AI Matching", disabled=not ready, type="primary", use_container_width=True):
        st.session_state.matches       = []
        st.session_state.reviewed      = {}
        st.session_state.edited_price  = {}
        st.session_state.analysis_done = False

        prog   = st.progress(0)
        status = st.empty()
        t0     = time.time()
        try:
            st.session_state.matches       = run_matching(
                st.session_state.prospect_df,
                st.session_state.catalog_df,
                active_key, prog, status,
            )
            st.session_state.analysis_done = True
            st.session_state.demo_mode     = False
            st.success(f"✅ {len(st.session_state.matches)} items matched in {time.time()-t0:.1f}s")
        except Exception as e:
            st.error(f"❌ {e}")

    # Quick stats if done
    if st.session_state.analysis_done:
        m   = st.session_state.matches
        thr = confidence_threshold
        high = sum(1 for x in m if x["confidence"] and x["confidence"] >= thr)
        rev  = sum(1 for x in m if x["confidence"] and x["confidence"] < thr and x["sc_sku"])
        none_= sum(1 for x in m if not x["sc_sku"])
        st.markdown(f"""
<div class="metric-row">
  <div class="metric-card"><div class="val">{len(m)}</div><div class="lbl">Total Items</div></div>
  <div class="metric-card"><div class="val" style="color:#057a55">{high}</div><div class="lbl">Auto-Accepted</div></div>
  <div class="metric-card"><div class="val" style="color:#c27803">{rev}</div><div class="lbl">Needs Review</div></div>
  <div class="metric-card"><div class="val" style="color:#c81e1e">{none_}</div><div class="lbl">No Match</div></div>
</div>""", unsafe_allow_html=True)
        st.info("👉 Explore the **Review Queue**, **Internal Report**, and **Prospect One-Pager** tabs.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — REVIEW QUEUE
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if not st.session_state.analysis_done:
        st.info("Run AI Matching first (Tab 1).")
    else:
        matches   = st.session_state.matches
        thr       = confidence_threshold
        flag_items = [m for m in matches if m["confidence"] is not None
                       and m["confidence"] < thr and m["sc_sku"]]
        no_items   = [m for m in matches if not m["sc_sku"]]

        st.markdown(
            f'<div class="section-title">🔍 Review Queue — {len(flag_items)} flagged matches</div>',
            unsafe_allow_html=True,
        )
        if st.session_state.demo_mode:
            st.markdown("""
<div class="demo-banner">
  Demo data: one item was intentionally given a lower confidence score to demonstrate the review workflow.
</div>""", unsafe_allow_html=True)

        if not flag_items:
            st.success("🎉 All items matched above your confidence threshold — nothing to review!")
        else:
            st.caption(f"These matches scored below {thr}%. Accept, reject, or manually override the price.")
            for m in flag_items:
                idx     = m["idx"]
                current = st.session_state.reviewed.get(idx)
                with st.container():
                    st.markdown('<div class="review-card flagged">', unsafe_allow_html=True)
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Prospect item:** {m['description']}")
                        st.markdown(f"**Suggested match:** {m['matched_name']}")
                        st.markdown(f"*AI reasoning: {m['reasoning']}*")
                        if m["pack_size_note"] and m["pack_size_note"].lower() != "same":
                            st.warning(f"⚠️ Pack size note: {m['pack_size_note']}")
                    with c2:
                        st.markdown(confidence_badge(m["confidence"]), unsafe_allow_html=True)
                        st.markdown(f"Their price: **${m['their_price']:.2f}**")
                        ep = st.session_state.edited_price.get(idx, m["sc_price"])
                        st.markdown(f"SC price: **${ep:.2f}**" if ep else "SC price: N/A")

                    a, b, c = st.columns(3)
                    with a:
                        if st.button("✅ Accept", key=f"acc_{idx}", use_container_width=True):
                            st.session_state.reviewed[idx] = "accept"; st.rerun()
                    with b:
                        if st.button("❌ Reject", key=f"rej_{idx}", use_container_width=True):
                            st.session_state.reviewed[idx] = "reject"; st.rerun()
                    with c:
                        np_ = st.number_input("Override SC price $", min_value=0.0,
                                              value=float(m["sc_price"] or 0),
                                              step=0.01, key=f"np_{idx}")
                        if st.button("✏️ Use this price", key=f"edit_{idx}", use_container_width=True):
                            st.session_state.edited_price[idx] = np_
                            st.session_state.reviewed[idx]     = "edit"
                            st.rerun()

                    if current:
                        icon = {"accept":"🟢","reject":"🔴","edit":"🟡"}.get(current,"")
                        st.markdown(f"{icon} **Status: {current.title()}**")
                    st.markdown("</div>", unsafe_allow_html=True)
                    st.write("")

        # No-match section
        if no_items:
            st.markdown(
                f'<div class="section-title">❌ No Catalog Match ({len(no_items)} items)</div>',
                unsafe_allow_html=True,
            )
            for m in no_items:
                with st.expander(f"🔴 {m['description']} — ${m['their_price']:.2f}/unit"):
                    st.markdown(f"Supplier SKU: `{m['sku']}`  |  Supplier: {m['supplier']}")
                    st.markdown(f"*AI note: {m['reasoning']}*")
                    mp = st.number_input("Enter Source Club price if known ($)",
                                         min_value=0.0, value=0.0, step=0.01,
                                         key=f"mp_{m['idx']}")
                    if st.button("Add to analysis", key=f"addm_{m['idx']}"):
                        st.session_state.edited_price[m["idx"]] = mp
                        st.session_state.reviewed[m["idx"]]     = "edit"
                        for x in st.session_state.matches:
                            if x["idx"] == m["idx"]:
                                x["sc_price"]     = mp
                                x["sc_sku"]       = "MANUAL"
                                x["matched_name"] = "Manually entered"
                                x["confidence"]   = 100
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — INTERNAL REPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    if not st.session_state.analysis_done:
        st.info("Run AI Matching first (Tab 1).")
    else:
        rows  = calc_rows(st.session_state.matches, st.session_state.reviewed,
                          st.session_state.edited_price, confidence_threshold)
        name  = st.session_state.get("prospect_name", "Demo Practice")

        total_their  = sum(r["monthly_their"] for r in rows) * 12
        total_sc     = sum(r["monthly_sc"] * 12 for r in rows if r["monthly_sc"] is not None)
        total_save   = sum(r["annual_save"] for r in rows if r["annual_save"] is not None)
        pct_save     = total_save / total_their * 100 if total_their else 0
        matched      = sum(1 for r in rows if r["include"])

        st.markdown(f"""
<div class="savings-hero">
  <div class="big">${total_save:,.0f}</div>
  <div class="sub">Estimated Annual Savings for {name} ({pct_save:.1f}% reduction)</div>
</div>""", unsafe_allow_html=True)

        st.markdown(f"""
<div class="metric-row">
  <div class="metric-card"><div class="val">${total_their:,.0f}</div><div class="lbl">Current Annual Spend</div></div>
  <div class="metric-card"><div class="val">${total_sc:,.0f}</div><div class="lbl">Source Club Annual Cost</div></div>
  <div class="metric-card"><div class="val">${total_save/12:,.0f}</div><div class="lbl">Monthly Savings</div></div>
  <div class="metric-card"><div class="val">{matched}/{len(rows)}</div><div class="lbl">Items Matched</div></div>
</div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-title">Line-Item Breakdown</div>', unsafe_allow_html=True)
        disp = []
        for r in rows:
            disp.append({
                "Item":           (r["description"][:52]+"…") if len(r["description"])>52 else r["description"],
                "Their $":        f"${r['their_price']:.2f}",
                "SC Match":       (r["matched_name"] or "—")[:48],
                "SC $":           f"${r['eff_sc_price']:.2f}" if r["eff_sc_price"] else "—",
                "Unit Save":      f"${r['their_price']-(r['eff_sc_price'] or r['their_price']):.2f}" if r["include"] else "—",
                "Qty/mo":         int(r["qty_per_month"]),
                "Annual Save":    f"${r['annual_save']:,.0f}" if r["annual_save"] else "—",
                "Confidence":     f"{r['confidence']}%" if r["confidence"] else "N/A",
                "Status":         r["status"],
            })
        st.dataframe(pd.DataFrame(disp), use_container_width=True, height=380)

        pending = [r for r in rows if r["status"] == "Pending Review"]
        if pending:
            st.warning(f"⚠️ {len(pending)} items still pending review — not yet included in totals.")

        st.markdown('<div class="section-title">Export</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            xlsx = make_excel(rows, name, total_their, total_sc, total_save, pct_save, matched)
            st.download_button("⬇️ Download Excel Report (3 sheets)",
                               data=xlsx,
                               file_name=f"SC_savings_{datetime.today().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               type="primary", use_container_width=True)
        with c2:
            csv_rows = [{"Item":r["description"],"Their $":r["their_price"],
                         "SC $":r["eff_sc_price"] or "","Annual Save":r["annual_save"] or "",
                         "Confidence":r["confidence"],"Status":r["status"]} for r in rows]
            st.download_button("⬇️ Download CSV",
                               data=pd.DataFrame(csv_rows).to_csv(index=False),
                               file_name=f"SC_savings_{datetime.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — PROSPECT ONE-PAGER
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    if not st.session_state.analysis_done:
        st.info("Run AI Matching first (Tab 1).")
    else:
        rows       = calc_rows(st.session_state.matches, st.session_state.reviewed,
                               st.session_state.edited_price, confidence_threshold)
        total_their = sum(r["monthly_their"] for r in rows) * 12
        total_sc    = sum(r["monthly_sc"] * 12 for r in rows if r["monthly_sc"] is not None)
        total_save  = sum(r["annual_save"] for r in rows if r["annual_save"] is not None)
        pct_save    = total_save / total_their * 100 if total_their else 0

        # Editable prospect name
        pname = st.text_input("Practice name (for report)", value=st.session_state.get("prospect_name","Valley Dental Group"))
        st.session_state.prospect_name = pname

        st.markdown('<div class="section-title">Preview — What the prospect sees</div>', unsafe_allow_html=True)

        # Build line-item table HTML
        rows_html = ""
        for r in rows:
            if r["include"] and r["annual_save"]:
                save_pct = (r["their_price"] - r["eff_sc_price"]) / r["their_price"] * 100 if r["eff_sc_price"] else 0
                rows_html += f"""
<tr>
  <td>{r['description'][:55]}</td>
  <td>${r['their_price']:.2f}</td>
  <td>{r['matched_name'] or '—'}</td>
  <td>${r['eff_sc_price']:.2f}</td>
  <td class="green">-{save_pct:.0f}%</td>
  <td class="green">${r['annual_save']:,.0f}/yr</td>
</tr>"""

        st.markdown(f"""
<div class="prospect-card">
  <h2>🦷 Source Club — Your Savings Analysis</h2>
  <div class="sub-h">Prepared for {pname} &nbsp;·&nbsp; {datetime.today().strftime("%B %d, %Y")}</div>

  <p>Based on your current purchase history, switching to Source Club's negotiated pricing would save your practice:</p>

  <div style="text-align:center;margin:1.25rem 0;">
    <span class="save-pill">💰 ${total_save:,.0f} per year &nbsp;|&nbsp; ${total_save/12:,.0f} per month</span>
  </div>

  <table class="prospect-table">
    <thead>
      <tr>
        <th>You currently buy</th>
        <th>Your price</th>
        <th>Source Club equivalent</th>
        <th>SC price</th>
        <th>Savings %</th>
        <th>Annual savings</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <div style="margin-top:1.5rem;background:#f9fafb;border-radius:8px;padding:1rem 1.2rem;">
    <div style="display:flex;gap:2rem;flex-wrap:wrap;text-align:center;">
      <div style="flex:1;">
        <div style="font-size:1.3rem;font-weight:700;color:#c81e1e;">${total_their:,.0f}</div>
        <div style="font-size:.8rem;color:#6b7280;">Current annual spend</div>
      </div>
      <div style="flex:1;">
        <div style="font-size:1.3rem;font-weight:700;color:#057a55;">${total_sc:,.0f}</div>
        <div style="font-size:.8rem;color:#6b7280;">With Source Club</div>
      </div>
      <div style="flex:1;">
        <div style="font-size:1.3rem;font-weight:700;color:#1a56db;">{pct_save:.1f}%</div>
        <div style="font-size:.8rem;color:#6b7280;">Price reduction</div>
      </div>
      <div style="flex:1;">
        <div style="font-size:1.3rem;font-weight:700;color:#1a56db;">${total_save/12:,.0f}</div>
        <div style="font-size:.8rem;color:#6b7280;">Savings / month</div>
      </div>
    </div>
  </div>

  <div style="margin-top:1.25rem;font-size:.9rem;color:#374151;border-top:1px solid #e5e7eb;padding-top:1rem;">
    <b>How Source Club works:</b> We negotiate volume pricing directly with dental manufacturers and pass the savings to member practices.
    No long-term contracts. Setup takes less than 10 minutes. Start saving from your very first order.
  </div>
</div>
""", unsafe_allow_html=True)

        st.divider()
        # Download prospect Excel
        xlsx = make_excel(rows, pname, total_their, total_sc, total_save, pct_save,
                          sum(1 for r in rows if r["include"]))
        st.download_button(
            "⬇️ Download Prospect Excel Report",
            data=xlsx,
            file_name=f"SC_savings_{pname.replace(' ','_')}_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", use_container_width=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ARCHITECTURE & NEXT STEPS
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-title">🏗️ End-to-End Architecture</div>', unsafe_allow_html=True)
    st.markdown("""
```
Prospect CSV  ──►  Parse & Normalize
                        │
                        ▼
              AI Matching Engine (Claude)
              ┌─────────────────────────────┐
              │  Per line item:             │
              │  • Semantic comparison      │
              │  • Brand equivalence        │
              │  • Pack-size reasoning      │
              │  • Confidence 0–100         │
              │  • Reasoning sentence       │
              └─────────────────────────────┘
                        │
              Confidence Router
          ┌─────────────┴──────────────┐
      ≥ threshold                 < threshold
    Auto-accepted              Human Review Queue
          │                  Accept / Reject / Edit
          └─────────────┬──────────────┘
                        ▼
             Savings Calculation
          ┌──────────────┴──────────────┐
     Internal Report          Prospect One-Pager
     (line-item detail)       (clean send-ready PDF)
```
""")

    st.markdown('<div class="section-title">🤖 Where AI Does the Work</div>', unsafe_allow_html=True)
    st.markdown("""
- **Semantic matching** — Claude understands "Nitrile Exam Gloves Medium PF 100/box" = "Sempermed Powder-Free Nitrile M Box/100" despite totally different SKUs, suppliers, and formatting.
- **Pack-size reasoning** — automatically detects unit-of-measure differences and flags them.
- **Confidence scoring** — self-rated certainty drives automatic routing; no rules engine needed.
- **Transparent reasoning** — every match includes a plain-English explanation, so human review is fast.
""")

    st.markdown('<div class="section-title">👤 Where Humans Stay in the Loop</div>', unsafe_allow_html=True)
    st.markdown("""
- **Review Queue** — matches below the configurable threshold are surfaced before they affect savings totals.
- **Price override** — any SC price can be manually corrected; unmatched items can be priced by hand.
- **Report sign-off** — the founder approves the prospect one-pager before sending.

Designed for ~85–90% auto-accept. The founder's attention is reserved for the 10–15% that genuinely need judgment — cutting 10 min/analysis to **≈2 min**.
""")

    st.markdown('<div class="section-title">⏱️ Time Impact</div>', unsafe_allow_html=True)
    st.markdown("""
| Step | Manual today | This tool |
|---|---|---|
| Upload & parse | 2 min | 30 sec |
| Product matching | 6 min | ~45 sec (AI) |
| Human review | — | 1–2 min |
| Report generation | 2 min | Instant |
| **Total / analysis** | **~10 min** | **~2–3 min** |
| **30 analyses / month** | **5+ hours** | **~1 hour** |

**4+ hours/month saved from day one.**
""")

    st.markdown('<div class="section-title">🚀 What I Would Build Next</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
**Week 1–2**
- 🗄️ Live Source Club catalog DB (replace CSV upload)
- 📧 One-click "Send to prospect" email from inside the tool
- 🔄 Batch mode: run 10 analyses overnight in parallel
- 📊 Learning loop: store review decisions → improve matching over time
""")
    with c2:
        st.markdown("""
**Month 1–2**
- 🔗 HubSpot/Salesforce: attach savings report to deal record
- 📦 Automatic pack-size normalization engine
- 🏷️ Direct API pull from Henry Schein / Patterson catalogs
- 📈 Win-rate tracking: savings amount → close probability model
""")

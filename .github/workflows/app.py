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
        "Match_Confidence",
        "Match_Reason",
        "Reviewer_Selected_Match",
    ],
    column_config={
        "Current_Unit_Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
        "SourceClub_Price": st.column_config.NumberColumn("SourceClub Price", format="$%.2f"),
        "Match_Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
        "Reviewer_Selected_Match": st.column_config.SelectboxColumn(
            "Reviewer Override",
            options=review_options,
            help="Use this when the suggested match is wrong or the item was below the auto-match threshold.",
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
        "Match_Reason",
    ],
)

final = apply_manual_review(reviewed, catalog)

current_total = final["Current_Spend"].sum()
source_total = final["SourceClub_Spend"].sum()
savings_total = final["Projected_Savings"].sum()
review_count = int(final["Match_Status"].isin(["Needs Review", "No Match"]).sum())
savings_rate = savings_total / current_total if current_total else 0

st.subheader("4. Prospect-ready savings summary")
metric_cols = st.columns(5)
metric_cols[0].metric("Current Spend", money(current_total))
metric_cols[1].metric("SourceClub Spend", money(source_total))
metric_cols[2].metric("Projected Savings", money(savings_total))
metric_cols[3].metric("Savings Rate", f"{savings_rate:.1%}")
metric_cols[4].metric("Needs Review", f"{review_count:,}")

if review_count:
    st.markdown(
        f"<div class='review-box'><b>{review_count} item(s) need review.</b> This is intentional: the system automates confident matches and exposes uncertain matches before the prospect sees the final report.</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='success-box'><b>All items are matched or reviewed.</b> The report is ready to send.</div>",
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


import pandas as pd

def generate_monthly_report(output_excel_file, last30DaySheet, monthlyReportSheet):

    # -------------------------------
    # Input file and sheet
    # -------------------------------

    # -------------------------------
    # Read Excel file
    # -------------------------------
    df = pd.read_excel(output_excel_file, sheet_name=last30DaySheet)

    # Ensure Date column is datetime
    df["Date"] = pd.to_datetime(df["Date"])

    # Create Month column (YYYY-MM)
    df["Month"] = df["Date"].dt.to_period("M").astype(str)

    # -------------------------------
    # Group by Month and aggregate
    # -------------------------------
    monthly_df = (
        df.groupby("Month", as_index=False).agg({"InvestedValue": "sum","SoldValue": "sum"})
    )

    # -------------------------------
    # Calculate Gain/Loss and Percent
    # -------------------------------
    monthly_df["Month GainLoss"] = (
        monthly_df["SoldValue"] - monthly_df["InvestedValue"]
    )

    monthly_df["Month GainLoss Percent"] = (
        (monthly_df["Month GainLoss"] / monthly_df["InvestedValue"]) * 100
    )

    # Rename columns to match requirement
    monthly_df.rename(columns={
        "InvestedValue": "Month InvestedValue",
        "SoldValue": "MonthSoldValue"
    }, inplace=True)

    # -------------------------------
    # Write to same Excel file
    # -------------------------------
    with pd.ExcelWriter(output_excel_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        monthly_df.to_excel(writer, sheet_name=monthlyReportSheet, index=False)

    print("MonthlyReport sheet created successfully.")

def get_details_df(txn_data):
    # Build details DataFrame
    details_cols = ["Date","Symbol","Name","BoughtPrice","BoughtTime","SoldPrice","SoldTime","GainLoss","GainLossPercent","InvestedValue","SoldValue","Volatility","Open","Close"]
    details_df = pd.DataFrame(txn_data)[details_cols]
    # Round numeric columns where not None
    for c in ["BoughtPrice","SoldPrice","GainLoss","GainLossPercent","InvestedValue","SoldValue","Volatility","Open", "Close"]:
        if c in details_df.columns:
            details_df[c] = details_df[c].apply(lambda x: round(x,2) if pd.notnull(x) else x)

    return details_df

def get_summary_data(details_df):

    # Summary per Symbol
    summary_rows = []
    grouped = details_df.groupby("Symbol")

    totalInvestedAll = 0.0
    totalSoldAll = 0.0
    for sym, group in grouped:
        name = group["Name"].dropna().unique()
        name = name[0] if len(name) > 0 else sym
        invested_sum = group["InvestedValue"].dropna().sum()
        sold_sum = group["SoldValue"].dropna().sum()
        gain_loss = sold_sum - invested_sum
        gain_loss_pct = (gain_loss / invested_sum * 100) if invested_sum != 0 else 0.0

        summary_rows.append({
            "Symbol": sym,
            "Name": name,
            "TotalInvested": round(invested_sum, 2),
            "TotalSoldValue": round(sold_sum, 2),
            "TotalGainLoss": round(gain_loss, 2),
            "TotalGainLossPercent": round(gain_loss_pct, 2)
        })

        totalInvestedAll += invested_sum
        totalSoldAll += sold_sum

    return summary_rows, totalInvestedAll, totalSoldAll


import os
import pandas as pd

def read_stocks_file(path):
    """Read stock symbols from file, strip, uppercase, remove blanks.
       Returns (unique_symbols_list, duplicates_list)
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = [line.strip() for line in f.readlines() if line.strip()
                    and not line.strip().startswith("#")]

    normalized = [s.split()[0].upper() for s in raw]  # take first token if user added name
    seen = set()
    uniques = []
    duplicates = []
    for s in normalized:
        if s in seen:
            duplicates.append(s)
        else:
            seen.add(s)
            uniques.append(s)
    return uniques, duplicates

def normalize_weights(df: pd.DataFrame, target: float = 100.0) -> pd.DataFrame:
    """
    Normalize stock weights so total equals target (default = 100).

    Expected columns:
      - stock
      - weight

    :param df: Input DataFrame
    :param target: Target total weight
    :return: DataFrame with adjusted weights
    """

    # Validate required columns
    required_cols = {"stock", "weight"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"DataFrame must contain columns: {required_cols}")

    # Ensure weight is numeric
    df = df.copy()
    df["weight"] = pd.to_numeric(df["weight"], errors="raise")

    total_weight = df["weight"].sum()
    count = len(df)

    if count == 0:
        return df

    # Difference from target
    diff = target - total_weight

    # Adjustment per stock
    adjustment = diff / count

    # Apply adjustment
    df["weight"] = df["weight"] + adjustment

    return df

def process_stock_file(
    input_excel_path: str,
    sheet_name: str = 0
) -> pd.DataFrame:
 
    # Read Excel. Assumption - excel file has columns - stock, weight, Ignore
    df = pd.read_excel(input_excel_path, sheet_name=sheet_name)

    # Normalize column names (optional but safer)
    df.columns = df.columns.str.strip().str.lower()

    # Filter out ignored stocks (Ignore == 'Y')
    df_filtered = df[
        df["ignore"].fillna("").str.upper() != "Y"
    ]

    # Remove duplicates based on stock symbol
    df_unique = df_filtered.drop_duplicates(
        subset=["stock"],
        keep="first"
    )

    # Select required columns
    result_df = df_unique[["stock", "weight"]]

    #Make sure the sum of all weights is 100
    #if < 100, find val=100-sumof(wt), Divide that by len(df) and add that value to each wt
    #if > 100, find val=sumof(wt)-, Divide that by len(df) and subtract that value to each wt
    result_df = normalize_weights(result_df)
    return result_df



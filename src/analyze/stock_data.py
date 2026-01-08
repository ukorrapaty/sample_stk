
import pandas as pd
import yfinance as yf
from tqdm import tqdm
import numpy as np

def fetch_intraday_30min(symbols, period_days=30):
    """
    Fetch 30-minute interval data for the past period_days for a list of symbols using yfinance.
    Returns dict: symbol -> DataFrame with columns ['Symbol','Name','Datetime','Price']
    """
    result = {}
    # period string for yfinance
    period_str = f"{period_days}d"
    for symbol in tqdm(symbols["stock"], desc="Downloading data"):
        try:
            # download one ticker at a time (avoids grouping complexities)
            ticker = yf.Ticker(symbol)
            #Changing interval to 5 minutes or 30 minutes reduced gain.
            #Changing it back to 15m. 
            hist = ticker.history(period=period_str, interval="15m", actions=False, auto_adjust=False, back_adjust=False)
            # If empty, store empty df
            if hist is None or hist.empty:
                result[symbol] = pd.DataFrame(columns=["Symbol","Name","Datetime","Price","Open","High","Low","Close","TimeInEpoch"])
                continue
            # hist index is DatetimeIndex, uses 'Close'
            #df = hist.reset_index()[["Datetime","Close"]].rename(columns={"Close":"Price"})
            df = hist.reset_index()[["Datetime","Open","High","Low","Close"]]
            df["Symbol"] = symbol
            # Attempt to get long name
            name = ticker.info.get("longName") if ticker.info and "longName" in ticker.info else ticker.info.get("shortName") if ticker.info and "shortName" in ticker.info else symbol
            df["Name"] = name
            # Round price to 2 decimals
            df["Price"] = df["Close"].round(2)
            dt_obj = df["Datetime"].dt.tz_convert('America/New_York')
            df["TimeInEpoch"] = dt_obj.values.astype(np.int64)
            df = df[["Symbol","Name","Datetime","Price","Open","High","Low","Close","TimeInEpoch"]]
            result[symbol] = df
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            result[symbol] = pd.DataFrame(columns=["Symbol","Name","Datetime","Price","Open","High","Low","Close","TimeInEpoch"])
    return result


def combine_to_master_df(symbol_data_map):
    # Combine all symbol frames into one master dataframe (for easy queries)
    all_rows = []
    for sym, df in symbol_data_map.items():
        if df is None or df.empty:
            continue
        all_rows.append(df)
    if all_rows:
        master_df = pd.concat(all_rows, ignore_index=True)
    else:
        master_df = pd.DataFrame(columns=["Symbol","Name","Datetime","Price"])




#
# Module takes the current stock values data frame, calculates RSI and MA20 for all stocks in the 
# df and saves as static values.
# Other modules can query a particular stock RSI/MA20 as needed.
#

# ----------------------------------
# RSI Calculations
# ----------------------------------

import pandas as pd
import tqdm
import yfinance as yf
from datetime import datetime, timedelta, date
import numpy as np
from scipy.ndimage import gaussian_filter1d # For smoothing
import stock_volatility as sv
import buy_and_sell_patterns as bsp

RSI_MA_df = pd.DataFrame()
RSI_OVERSOLD_IDX=30
RSI_OVERBOUGHT_IDX=70
MA20_BACK_DAYS=20
RSI_BACK_DAYS=14

INTRADAY_DROP_PCT=3
INTRADAY_RAISE_PCT=1.5

def daterange_days(num_days, end_date=None):
    """Yield dates for the past num_days (excluding today if end_date is None use today-1),
       returns dates in YYYY-MM-DD (date objects)
    """
    if end_date is None:
        # We consider past days up to yesterday (market days could be included; user specified past 30 days)
        #end = datetime.now().date() - timedelta(days=1)
        end = datetime.now().date()
    else:
        end = end_date
    dt_df=[]
    for i in range(num_days):
       #yield (end - timedelta(days=i))
       iter_date = end - timedelta(days=i)
       dt_str = iter_date.strftime('%Y-%m-%d')
       #yield dt_str
       dt_df.append(dt_str)
    return dt_df

def calculate_rsi( df, period=RSI_BACK_DAYS):

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
  
    df["RSI"] = 100 - (100 / (1 + rs))

    return df["RSI"]

def calculate_ma(df, period=MA20_BACK_DAYS):
    df["MA20"] = df["Close"].rolling(period).mean()
    return df["MA20"]

# ----------------------------------
# Buy / Sell Rules
# ----------------------------------
def buy_signal(row):
    val1 = row["RSI"].item() < 30
    val2 = row["Close"].item() > row["MA20"].item()

    print ("RSI:",row["RSI"].item(),val1)
    print ("MA20:",row["MA20"].item(),val2)
    return row["RSI"].item() < 30 and row["Close"].item() > row["MA20"].item()

def sell_signal(row, entry_price):
    stop_loss = entry_price * 0.98
    target = entry_price * 1.04

    return (
        row["RSI"] > 70 or
        row["Close"] <= stop_loss or
        row["Close"] >= target
    )

def build_RSI_MA20_data(stocks,NumberOfDays) :

    #RSI generates no data for initial 14 days and MA20 for initial 20 days
    #Add extra 20 days to NumberOfDays to ignore the first 20 days. 
    days=daterange_days(NumberOfDays+MA20_BACK_DAYS)
    global RSI_MA_df
    #RSI_MA_df=yf.download(stocks, start=days[-1], end=days[0],auto_adjust=True)
    #print (len(RSI_MA_df))
    #print (RSI_MA_df)
    #for stk in stocks:
    for stk in stocks["stock"]:
        #for stk in stocks:
        if stk == "stock":
            continue
        stk_df=yf.download(stk, start=days[-1], end=days[0],auto_adjust=True,progress=False)
        #print (stk_df)
        df = pd.DataFrame()
        df = pd.concat([df,calculate_rsi(stk_df)],axis=1) #Concat RSI Column Data
        df = pd.concat([df,calculate_ma(stk_df)],axis=1)  #Concat MA20 column data
        df["Close"] = stk_df["Close"]
        df["Open"] = stk_df["Open"]

        df["Symbol"] = stk #Add Symbol column with value as Stock Symbol
        df["Date"] = df.index.astype(str).str.split(' ') .str[0]  #Add Date column using the index data
        volative_val = sv.get_volatility(df)
        df["Volatility"] = volative_val
        RSI_MA_df = pd.concat([RSI_MA_df, df]) #Concat the created df for the current stock to the global Data Frame


    #print(RSI_MA_df[RSI_MA_df["Symbol"] == "NVDA"]) #To get a given stock data like NVDA
    return RSI_MA_df

def normalize_to_0_100(data_list):
    # 1. Convert to NumPy array & Filter NaNs
    # Use np.isfinite to check for non-NaN/non-inf values
    valid_data = np.array(data_list)[np.isfinite(data_list)]

    if valid_data.size == 0:
        return [] # Return empty if no valid data

    # 2. Find Min/Max of Valid Data
    min_val = np.min(valid_data)
    max_val = np.max(valid_data)

    # Handle case where all valid data is the same (avoid division by zero)
    if max_val == min_val:
        # Normalize to 0-100 (all same value -> 50 or 0, depending on preference)
        # Let's map to 50 for central value, or 0 if preferred
        normalized_valid = np.full_like(valid_data, 50)
    else:
        # 3. Normalize valid data to 0-100
        normalized_valid = 100 * (valid_data - min_val) / (max_val - min_val)

    # 4. Apply Smoothing (e.g., Gaussian filter for gentle curve)
    # sigma controls the degree of smoothing (larger sigma = smoother)
    smoothed_valid = gaussian_filter1d(normalized_valid, sigma=1) # Adjust sigma

    # 5. Reconstruct original structure (if needed, mapping back NaNs)
    # This part depends heavily on your input structure (list/array/DataFrame)
    # For a simple list, we can create a result array and fill:
    result = np.full(len(data_list), np.nan) # Start with NaNs
    valid_indices = np.where(np.isfinite(data_list))[0] # Get indices of valid data
    result[valid_indices] = smoothed_valid
    
    return list(result)

def find_row_between_values(df, column_name, target_value):
    # Ensure the column is sorted for the logic to work correctly
    # If not already sorted, you might want to sort it first:
    # df = df.sort_values(by=column_name).reset_index(drop=True)

    # Get the current and next entries in the column
    current_values = df[column_name].sort_values()
    next_values = df[column_name].shift(-1).sort_values() # Shift up by 1

    # Find the row where the condition is met
    # The condition is: current_value < target_value < next_value
    # Use boolean indexing to find all rows that match the criteria
    matches = (current_values <= target_value) & (next_values > target_value)

    # Get the index of the first matching row
    match_index = matches.idxmax() if matches.any() else None

    # Return the index of the row just before the range starts
    # Note: idxmax() returns the index of the first True value
    if match_index is not None:
        # The target value falls *after* the value at match_index
        # So we return the match_index itself as the "current entry"
        return match_index.item()
    else:
        return None
    
def calculate_rvi_indicator(df, for_time, period=3):
    """Calculates the Relative Vigor Index (RVI)."""
    df['Close_Open'] = df['Close'] - df['Open']
    df['High_Low'] = df['High'] - df['Low']
    
    # Calculate moving averages of the differences
    df['RVI'] = df['Close_Open'].rolling(window=period).mean() / df['High_Low'].rolling(window=period).mean()
    
    # Calculate the Signal Line (e.g., 4-period SMA of RVI)
    df['RVI_Signal'] = df['RVI'].rolling(window=2).mean() # Common signal period

    df['RVI'] = normalize_to_0_100(df['RVI'])
    df['RVI_Signal'] = normalize_to_0_100(df['RVI_Signal'])

    for_time_in_epoch = pd.to_datetime(for_time).tz_convert('America/New_York').value

    indx = find_row_between_values(df, "TimeInEpoch", for_time_in_epoch)

    retVal = False
    if indx is not None:
        last_rvi_sgnal = df.loc[indx,"RVI_Signal"]
        if last_rvi_sgnal > 50:
            retVal = True
    return retVal

def trend_line(stk_data_for_date, prc, prc_time):
    ROLLING_WINDOW=3 #2 #10 #Incresing reducing the gain
    dt_obj = stk_data_for_date["Datetime"].dt.tz_convert('America/New_York')
 
    epoch_ns = dt_obj.values.astype(np.int64)
    #epoch_ns = dt_obj.value

    time_in_epoch = pd.to_datetime(prc_time).tz_convert('America/New_York').value

    entries_before_current_tm = np.where(epoch_ns < time_in_epoch)
    df = pd.DataFrame(entries_before_current_tm)
    if (df.size > 0):
        #print("Break Here")
        #print(type(entries_before_current_tm))
        ##print(entries_before_current_tm)
        #print(entries_before_current_tm[0])
        #print(len(entries_before_current_tm[0]))
        df = stk_data_for_date.iloc[entries_before_current_tm[0]]
        ema = df["Price"].ewm(span=ROLLING_WINDOW,adjust=True).mean()
        #ema = df["Price"].ewm(span=ROLLING_WINDOW,adjust=True,com=0.5).mean()
        #ema = df["Price"].rolling(window=ROLLING_WINDOW).mean()
        retVal = ema > prc
        if retVal.empty:
            return False
        val = retVal.values[0]
        #val1 = bool(val[len(val)-1])
        val1 = bool(val)
        #if val1:
            #print("Break Here")
        return val1
    else:
        return False
   



def is_it_a_buy(stk, trade_date, rsi_ma_df_data):

    stk_rows = rsi_ma_df_data[ (rsi_ma_df_data["Symbol"] == stk)]
    #print (stk_rows)
    dt_rows = rsi_ma_df_data[(rsi_ma_df_data["Date"] == trade_date.strftime("%Y-%m-%d") )]
    #print(dt_rows)

    row = rsi_ma_df_data[ (rsi_ma_df_data["Symbol"] == stk) & (rsi_ma_df_data["Date"] == trade_date.strftime("%Y-%m-%d") ) ]
    if row.empty:
        return False, -10000, -10000
    val1 = row["RSI"].item() < RSI_OVERSOLD_IDX
    val2 = row["Close"].item() > row["MA20"].item()

    #print(stk,":",trade_date,":","RSI Indicator:",val1,"MA20 Indicator:", val2, "Is It A Buy:",val1&val2)

    #print ("RSI:",row["RSI"].item(),val1)
    #print ("MA20:",row["MA20"].item(),val2)
    return row["RSI"].item() < RSI_OVERSOLD_IDX and row["Close"].item() > row["MA20"].item(), row["Open"].item(), row["Close"].item()

#Check if the price for current day dropped by INTRADAY_DROP_PCT. If so, mark it as buy
def buy_intra_day_decision(stk, trade_date, rsi_ma_df_data, stk_data_for_date, stk_open_prc, price, price_time):
    intra_day_buy = False
    dt_str = trade_date.strftime("%Y-%m-%d")
    volatility=0

    if trade_date == date.today():
        open_prc = stk_open_prc
        close_prc=price
        intra_day_buy = trend_line(stk_data_for_date, price, price_time)
    else:
        row = rsi_ma_df_data[ (rsi_ma_df_data["Symbol"] == stk) & (rsi_ma_df_data["Date"] == dt_str ) ]
        try:
            open_prc = row["Open"].values[0]
            close_prc = row["Close"].values[0]
            volatility = row["Volatility"].values[0]
            intra_day_buy = trend_line(stk_data_for_date, price, price_time)
        except Exception as e:
            print("Exception for symobol:",stk," for date:", dt_str)
            return False, volatility, -10000, -10000

    intra_day_drop_threshold = open_prc - (open_prc * INTRADAY_DROP_PCT)/100
    #intra_day_raise_threshold = open_prc + (open_prc * INTRADAY_RAISE_PCT)/100
    #if ((price < intra_day_drop_threshold) or (price > intra_day_raise_threshold))  :
        #intra_day_buy=True 
    if not intra_day_buy:
        intra_day_buy = decide_pattern_rvi_indicators(stk_data_for_date, stk, trade_date, price_time)
    
    return intra_day_buy, volatility, open_prc, close_prc

def decide_pattern_rvi_indicators(stk_data_for_date, stk, trade_date, price_time):
    rvi_indicator = calculate_rvi_indicator (stk_data_for_date, price_time)
    bsp_indicator = bsp.buy_or_sell(trade_date, stk)
    retVal = False
    if rvi_indicator:
        if bsp_indicator == -1: #Sell
            retVal = False
        else:  #Buy or Neutral
            retVal = True
    return retVal
    
def ignore():
#stocks = pd.DataFrame(columns=["Symbol"])
#stocks.loc[len(stocks)] = ["NVDA"]
#stocks.loc[len(stocks)] = ["DDOG"]
    stocks=["NVDA","DDOG","GOOG","AMZN","NFLX","ADBE"]
    build_RSI_MA20_data(stocks,80)

    for stk in stocks:
        for d in daterange_days(60):
            ret = is_it_a_buy(stk, d)
            #row = RSI_MA_df[ (RSI_MA_df["Symbol"] == stk) & (RSI_MA_df["Date"] == d ) ]
            #row = RSI_MA_df[ RSI_MA_df["Symbol"] == stk ]
            #row = RSI_MA_df[ RSI_MA_df["Date"] == d ]
            val="SELL"
            if ret:
                val="BUY"
            print(stk, d, val)

    frst_column=RSI_MA_df.columns[0]
    #print(frst_column)

    #dt_mask = (RSI_MA_df['Price'] == "2025-10-20")
    #stk_mask = (RSI_MA_df['Stock'] == "NVDA")

    #row=RSI_MA_df[dt_mask & stk_mask]
    #print(row)







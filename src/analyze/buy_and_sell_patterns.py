import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import matplotlib.pyplot as plt
import yfinance as yf
import pandas as pd
import time
from collections import defaultdict
from datetime import datetime, date, time, timedelta
import pytz

_interval_start=1
_last_ticker=""

def generate_15min_intervals(target_date):
    eastern = pytz.timezone('America/New_York')
    start_dt = datetime.combine(target_date, time(9, 30))
    start_dt = eastern.localize(start_dt)
    market_close_dt = datetime.combine(target_date, time(15, 30))
    market_close_dt = eastern.localize(market_close_dt)

    now = datetime.now()
    now = eastern.localize(now)
    intervals = []

    dtDiff = now.date() - target_date
    if dtDiff.days >= 30:
        return intervals

    # Determine end time
    if target_date == now.date():
        end_dt = min(now, market_close_dt)
    else:
        end_dt = market_close_dt

    # Round end_dt down to nearest 15 minutes
    end_dt = end_dt.replace(
        minute=(end_dt.minute // 15) * 15,
        second=0,
        microsecond=0
    )

    current = start_dt
    while current <= end_dt:
        intervals.append(current)
        current += timedelta(minutes=15)

    return intervals

def get_max_min(data_series, window=10, smoothing=3):
    """
    Identifies local max and min points in a price series using a rolling window.
    This is a simplified representation; actual implementations are more complex.
    """
    maxima = data_series.rolling(window=window, center=True).max()
    minima = data_series.rolling(window=window, center=True).min()
    
    # Filter points where actual price matches local max/min
    local_maxs = data_series[data_series == maxima].dropna()
    local_mins = data_series[data_series == minima].dropna()
    
    # Combine and sort all potential peak/trough points
    max_min_points = pd.concat([local_maxs, local_mins]).sort_index()
    # Remove consecutive points of the same type and filter for significance (smoothing is needed for robustness)
    # The actual filtering logic is complex and usually requires a dedicated library or custom logic
    
    return max_min_points

def is_it_ihs_or_hs(max_min_points):
    """
    Iterates over max/min points to find a head and shoulders pattern (bearish reversal) 
    or inverse head and shoulders patter (bullish)
    A H&S pattern has 5 points (2 minima forming the neckline, 3 maxima forming the shoulders and head):
    A (left shoulder peak)
    B (left neckline trough)
    C (head peak - highest)
    D (right neckline trough)
    E (right shoulder peak)

    Conditions for H&S:
    1. C is the highest peak (Head)
    2. A and E are peaks (Shoulders), lower than C
    3. B and D are troughs (Neckline), roughly around the same level
    4. A, B, C, D, E are sequential points.

    # IHS Pattern Criteria:
    # 1. Head (C) is the lowest point
    # 2. Shoulders (A, E) are higher than the head
    # 3. Peaks (B, D) are higher than shoulders and head
    # 4. Neckline (formed by B and D) is roughly horizontal (optional, within a tolerance)
        
    """
    h_s_patterns = []
    i_h_s_patterns = []
    retVal = 0 #Neutral
    # Check windows of 5 points
    for i in range(5, len(max_min_points) + 1):
        window = max_min_points.iloc[i-5:i]
        if len(window) < 5:
            continue

        a, b, c, d, e = window.iloc[0], window.iloc[1], window.iloc[2], window.iloc[3], window.iloc[4]
        is_ihs = (c < a and c < e and c < b and c < d) and \
                 (a < b and e < d) and \
                 (abs(b - d) <= ((b + d) / 2) * 0.05) # Neckline tolerance of 5%
        is_hs = ( c > a and c > e and c > b and c > d) and \
                ( a > b and e > d) and \
                ( abs(b - d) > np.mean([b, d]) * 0.05)
        
        # If all conditions pass, a pattern is detected
        if (is_hs):
            h_s_patterns.append({
                'left_shoulder': a,
                'left_neckline': b,
                'head': c,
                'right_neckline': d,
                'right_shoulder': e,
                'indices': list(window.index)
            })
        if (is_ihs):
            i_h_s_patterns.append({
                'left_shoulder': a,
                'left_neckline': b,
                'head': c,
                'right_neckline': d,
                'right_shoulder': e,
                'indices': list(window.index)
            })

    return i_h_s_patterns, h_s_patterns

def fetch_latest_ohlc(symbol, sd, ed):
    """Fetches the latest 1-minute OHLC data using yfinance."""
    # Fetch today's data with 1-minute interval, period="1d" is typically sufficient for intraday
    ticker = yf.Ticker(symbol)
    #data = yf.download(ticker, period="3d", interval="1m", progress=False)
    #data = ticker.history(period="3d", interval="1m", actions=False, auto_adjust=False, back_adjust=False)
    data = ticker.history(start=sd,end=ed,interval="1m",actions=False, auto_adjust=False, back_adjust=False)
    return data
    if not data.empty:
        # Return the latest bar as a Series
        return data.iloc[-1]
    return None

"""
    Return 1 - Buy (Inverse Head and Shoulder Pattern found)
    Return -1 - Sell (Head and Shoulder Pattern found)
    Return 0 - Neutral (No pattern found - Use other trend information for decision)
"""
def buy_or_sell(trade_date, ticker):
    ohlc_history = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
    intervals = generate_15min_intervals(trade_date)
    global _interval_start
    global _last_ticker
    if _last_ticker != ticker:
        _interval_start=1
        _last_ticker=ticker
    if len(intervals) == 0: 
        return 0
    bought_flag=False
    sold_flag=False
    current_price = 0
    for interval_idx in range(_interval_start,len(intervals)):
        sd = intervals[interval_idx-1]
        ed = intervals[interval_idx]
        data = fetch_latest_ohlc(ticker,sd, ed)
        if data.empty: 
                return 0
        row = data.iloc[-1]
        current_price = row["Close"]
        for idx in range(0,len(data)): 
            # Append the new data point to history
            if ohlc_history.empty:
                ohlc_history = pd.DataFrame([data.iloc[idx]])
            else:
                ohlc_history = pd.concat([ohlc_history, pd.DataFrame([data.iloc[idx]])])
                ohlc_history = ohlc_history[~ohlc_history.index.duplicated(keep='last')] # Avoid duplicates on same timestamp
        prices = ohlc_history['Close']
        smoothing = 10
        window = 100
        minmax_points = get_max_min(prices, smoothing, window)
        i_h_s_patterns, h_s_patterns = is_it_ihs_or_hs(minmax_points)

        _interval_start = interval_idx + 1
        if _interval_start == len(intervals):
            _interval_start = 1

        if len(i_h_s_patterns) > 0:
            return 1 #Buy
        if len(h_s_patterns) > 0:
            return -1 #Sell
        if len(i_h_s_patterns) == 0 and len(h_s_patterns) == 0:
            return 0 #Neutral
    return 0



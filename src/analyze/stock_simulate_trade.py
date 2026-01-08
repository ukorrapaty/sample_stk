
import pandas as pd
import math
import yfinance as yf
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
import time
import numpy as np
import pandas_market_calendars as mcal
import stock_rule_data as rd
import buy_and_sell_patterns as bsp

txn_data=[]
def is_market_holiday(nyse,date):
    schedule = nyse.schedule(start_date=date, end_date=date)
    return schedule.empty

def stock_txn_for_date(symbol, name, trade_date, bought_prc, bought_tm, sold_prc, sold_tm,inv_val, sld_val, volatile_val,open_prc, close_prc):
    
    gain_loss = sld_val - inv_val
    gain_loss_pct = (gain_loss / inv_val) * 100 if inv_val != 0 else 0.0

    txn = {
        "Date": trade_date.strftime("%Y-%m-%d"),
        "Symbol": symbol,
        "Name": name,
        "BoughtPrice": round(bought_prc, 2),
        "BoughtTime": bought_tm,
        "SoldPrice": round(sold_prc, 2),
        "SoldTime": sold_tm,
        "GainLoss": gain_loss,
        "GainLossPercent": gain_loss_pct,
        "InvestedValue": round(inv_val, 2),
        "SoldValue": round(sld_val, 2),
        "Volatility": round(volatile_val,2),
        "Open": round(open_prc,2),
        "Close":round(close_prc,2)
    }
    return txn


def ignoreNoneData(txn_data, sym,symbol_data_map, d, bought_prc=None, bought_tm=None, sold_prc=None,sold_time=None, gl=None, glpct=None, inv_val=None, sld_val=None) :
               txn_data.append({
                    "Date": d.strftime("%Y-%m-%d"),
                    "Symbol": sym,
                    "Name": symbol_data_map.get(sym).iloc[0]["Name"] if (symbol_data_map.get(sym) is not None and not symbol_data_map.get(sym).empty) else sym,
                    "BoughtPrice": bought_prc,
                    "BoughtTime": bought_tm,
                    "SoldPrice": sold_prc,
                    "SoldTime": sold_time,
                    "GainLoss": gl,
                    "GainLossPercent": glpct,
                    #"InvestedValue": round(invested_per_stock, 2),
                    "InvestedValue": inv_val,
                    "SoldValue": sld_val
                })

def get_consecutive_closed_lower(df, x_percent):
    no_of_recent_consecutive_days_closed_lower=0
    for _, row in df.iterrows():
        open_price = row["Open"]
        close_price = row["Close"]

        if (close_price < (open_price*x_percent)):
                no_of_recent_consecutive_days_closed_lower += 1
        else:
            no_of_recent_consecutive_days_closed_lower=0
    return no_of_recent_consecutive_days_closed_lower
        #percent_drop = ((open_price - close_price) / open_price) * 100

        #if percent_drop < x_percent:
        #    return False


def is_close_x_percent_lower(ticker, n_days, x_percent):
    """
    Returns True if for the last n_days the closing price
    is at least x_percent lower than the open price for EACH day.
    Otherwise returns False.
    """

    # Fetch last n_days of historical data
    stock = yf.Ticker(ticker)
    df = stock.history(period=f"{n_days + 5}d")  # buffer for non-trading days

    # Keep only last n trading days
    df = df.tail(n_days)

    if len(df) < n_days:
        raise ValueError("Not enough trading data available")

    no_of_recent_consecutive_days_closed_lower=get_consecutive_closed_lower(df,x_percent)

    if no_of_recent_consecutive_days_closed_lower >= 2:
        return False
    return True

def get_buy_sell_details(invested_val, current_price, current_time):
    shares = invested_val/ current_price
    price = current_price
    time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    flag = True

    return shares, price, time, flag

# -------------------------
# Trading logic
# -------------------------
def trade_stock_for_date(nyse,df_stock, trade_date, invested_value, rsi_ma_df):
    """
    df_stock: DataFrame with columns ['Symbol','Name','Datetime','Price'] (Datetime is timezone-aware or naive)
    trade_date: datetime.date
    invested_value: float
    Returns: one txn dict or None (if no data at all)
    txn dict fields:
     Date, StockSymbol, StockName, OriginalPrice, SoldPrice, SoldTime (string), GainLoss, GainLossPercent
    Logic:
     - OriginalPrice = first available price on trade_date
     - shares = invested_value / OriginalPrice
     - iterate through intraday prices in chronological order for that date
       if shares * price <= lower_pct * invested_value OR >= upper_pct * invested_value -> record sale at that price/time and break
     - if not sold -> SoldPrice = last available price for trade_date, SoldTime = "EndOfDay"
    """

    global txn_data

    if trade_date.weekday() >= 5 or is_market_holiday(nyse,trade_date):
        return None

    # Filter df_stock for the given date
    if df_stock.empty:
        return None

    # Make sure Datetime column is datetime dtype
    df_stock = df_stock.copy()
    df_stock["Datetime"] = pd.to_datetime(df_stock["Datetime"])
    df_stock_date = df_stock[df_stock["Datetime"].dt.date == trade_date].sort_values("Datetime")
    
    if df_stock_date.empty:
        # no intraday rows for that date
        return None

    symbol = df_stock_date.iloc[0]["Symbol"]
    name = df_stock_date.iloc[0]["Name"]

    # Original price - first sample of the day
    original_price = float(df_stock_date.iloc[0]["Price"])
    if original_price == 0 or math.isnan(original_price):
        # invalid
        return None

    lower_pct, upper_pct = get_thresholds(original_price)
    shares = invested_value / original_price

    lower_threshold = lower_pct * invested_value
    upper_threshold = upper_pct * invested_value

    #if (is_close_x_percent_lower(symbol, 1, lower_pct) == False):
    rsi_ma20_inidcator, open_prc, close_prc =rd.is_it_a_buy(symbol, trade_date, rsi_ma_df)
        #txn = donot_trade_stock_for_date(symbol, name, trade_date, invested_value, original_price)
        
        #return txn
    
    sold_price = None
    sold_time = None
    sold_flag = False

    bought_flag = False

    frst_row = df_stock_date.iloc[0]

    if rsi_ma20_inidcator == True:
        #Buying prices using open price instead of intra day drop price. 
        shares, bought_price, bought_time, bought_flag = get_buy_sell_details(invested_value, frst_row["Price"], frst_row["Datetime"])
        bought_flag = True

    volatility = 0
    for idx, row in df_stock_date.iterrows():
        current_price = float(row["Price"])
        current_time = row["Datetime"]
        if rsi_ma20_inidcator == False:
            if not bought_flag:
                #RSI MA20 indicates that don't buy. We are doing next check
                #Check if price trend line is positive for intra day 
                intra_day_buy,volatility, open_prc, close_prc = rd.buy_intra_day_decision(symbol, trade_date, rsi_ma_df, df_stock_date, frst_row["Price"], current_price, current_time)
                if intra_day_buy:
                    #Readjust shared since the shares are not bought using open price but using intra day drop price
                    shares, bought_price, bought_time, bought_flag = get_buy_sell_details(invested_value, current_price, current_time)
        else: #RSI and MA20 indicator says buy. Check the ternd line to decide when to buy
            if not bought_flag:
                #RSI and MA20 indicator inform as Buy, decide when to buy using the trend line. 
                trend_flag = rd.trend_line(df_stock_date, current_price, current_time)
                rvi_pattern_decision = rd.decide_pattern_rvi_indicators(df_stock_date,symbol, trade_date, current_time)
                if rvi_pattern_decision == 1 or trend_flag: #Pattern says Buy or Trend line is postive
                    shares, bought_price, bought_time, bought_flag = get_buy_sell_details(invested_value, current_price, current_time)

        portfolio_value = shares * current_price

        #Sell Decision
        if bought_flag: 
            price_trend = rd.trend_line(df_stock_date, current_price, current_time)
            #Sell if trend line is False (trending down) and -- value is < lower threshold or > threshold
            #if not price_trend and (portfolio_value <= lower_threshold or portfolio_value >= upper_threshold):
            #rvi_indicator = rd.calculate_rvi_indicator(df_stock_date, current_time)
            #if portfolio_value <= lower_threshold or portfolio_value >= upper_threshold:
            #if not price_trend:
            rvi_pattern_decision = rd.decide_pattern_rvi_indicators(df_stock_date,symbol, trade_date, current_time)
            if not rvi_pattern_decision and (portfolio_value <= lower_threshold or portfolio_value >= upper_threshold):
                shares, sold_price, sold_time, sold_flag = get_buy_sell_details(portfolio_value, current_price, current_time)
                wait_time = datetime.strptime(sold_time,"%Y-%m-%d %H:%M:%S") - datetime.strptime(bought_time,"%Y-%m-%d %H:%M:%S")
                #wait_time_in_mins = wait_time.total_seconds() / 60
                #Waiting 1 hour rule brought down gain from +ve 1200 to -ve 940 for stocks in stocks.xlsx (with some as ignore). 
                #Includes stockls are AAPL, AMZN, DDOG, SNOW, AMZN, GOOG etc. 
                #So, not a good rule 
                #if (wait_time_in_mins > 60): # Don't sell if the time since buy is less than one hour
                #break #sold_flag is set to true
                #don't break even if sold. Reiterate to buy multiple times if possible.
                txn = stock_txn_for_date (symbol, name, trade_date, bought_price, bought_time, sold_price, sold_time, invested_value, sold_price*shares, volatility, open_prc, close_prc)
                #print(len(txn_data))
                #if not txn_data or txn_data.empty:
                #    print ("Breakpoint here")
                if txn:
                    txn_data.append(txn)
                    break #Break - Doing transaction only one for the stock for the day. 
                #bought_flag=False
                #sold_flag = False


            
    if bought_flag and not sold_flag:
        # end of day price = last price available
        last_row = df_stock_date.iloc[-1]
        shares, sold_price, sold_time, sold_flag = get_buy_sell_details(shares*last_row["Price"], last_row["Price"], last_row["Datetime"])
        sold_flag = True

    if bought_flag:
         txn = stock_txn_for_date (symbol, name, trade_date, bought_price, bought_time, sold_price, sold_time, invested_value, sold_price*shares, volatility, open_prc, close_prc)
    else:   
         txn = stock_txn_for_date (symbol, name, trade_date, frst_row["Price"], frst_row["Datetime"].strftime("%Y-%m-%d %H:%M:%S"), frst_row["Price"], frst_row["Datetime"].strftime("%Y-%m-%d %H:%M:%S"), invested_value, invested_value, volatility, open_prc, close_prc)  
    if txn:
        txn_data.append(txn)

def get_thresholds(price):
    """
    Returns (lowerThreshold, upperThreshold) for a given price.
    """
    df = pd.read_excel("C:/Users/ukorr/OneDrive/Documents/Projects/work/stockmarket/TrackStocks/src/input/lower_and_upper_table.xlsx")
    for _, row in df.iterrows():
        low = row['Lower Range']
        high = row['Upper Range']

        # Handle last row where Upper Range is NaN (open-ended)
        if pd.isna(high):
            if price >= low:
                return row['LowerThreshold'], row['UpperThreshold']

        # Standard range match
        if low <= price < high:
            return row['LowerThreshold'], row['UpperThreshold']

    return None, None  # If price doesn't match any row

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
    for i in range(num_days):
        yield end - timedelta(days=i)

def get_txn_data(stocks, DailyInitialInvestment, NumberOfDays, symbol_data_map):

    global txn_data
    nyse = mcal.get_calendar("NYSE")

    # daily invested per stock
    invested_per_stock = DailyInitialInvestment / len(stocks)

    RSI_MA_df = rd.build_RSI_MA20_data(stocks,NumberOfDays)
    #print(stocks)

    # For each day in date range
    print("Simulating daily trades...")
    for d in tqdm(list(daterange_days(NumberOfDays)), desc="Days"):
        # trade for each symbol
        for index, sym_row in stocks.iterrows():
            sym=sym_row["stock"]
            wt = sym_row["weight"]
            df_stock = symbol_data_map.get(sym, pd.DataFrame(columns=["Symbol","Name","Datetime","Price"]))

            invested_per_stock=DailyInitialInvestment*wt/100
            #print ("Trade Stock", sym, " for the date ", d, ".....")
            trade_stock_for_date(nyse,df_stock, d, invested_per_stock, RSI_MA_df)
            #if txn:
                #txn_data.append(txn)
            #else: Don't capture None Data. It is either weekend or holiday.
               # ignoreNoneData(txn_data,sym,symbol_data_map, d)
                # even if no data, record a "no data" line? We'll record a row with NaN prices to indicate missed data
    return txn_data



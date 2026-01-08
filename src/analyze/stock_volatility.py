import yfinance as yf
import pandas as pd
import numpy as np

# 1. Define the stock ticker and period

def get_volatility(stock_data):

    # We focus on the 'Adj Close' price for consistency
    close_prices = stock_data['Close']

    # 3. Calculate daily logarithmic returns
    # Log returns are often preferred in finance for mathematical properties
    daily_returns = np.log(close_prices / close_prices.shift(1))

    # Optional: Drop the first row which will be a NaN value
    daily_returns = daily_returns.dropna()

    # 4. Calculate the daily volatility (standard deviation of returns)
    daily_volatility = daily_returns.std()

    # 5. monthlyize the daily volatility
    # The number of trading days in a year is often assumed to be 252
    monthly_volatility = (daily_volatility * np.sqrt(21))
    typ = type(monthly_volatility)
    #print(monthly_volatility)
    ret_val = monthly_volatility.item()

    return ret_val

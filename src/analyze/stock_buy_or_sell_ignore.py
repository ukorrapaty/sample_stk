#
# Stock Buy / Sell rules
#
# For a given stock decide Buy or Sell as below
#
# BUY:
#    RSI Logic:
#    if RSI in last RSIDays is < RSIBuyIndex - buy
#    if RST in last RSIDays is > RSISellIndex - don't buy today
#    if RSI in last RSIDays is > RSIBuyIndex < RSISellIndex - use MA20 to decide Buy or Sell
#    MA20 Logic:
#     if prior day closing price or today morning opening price is < MA20, don't buy
#     else Buy
# Intra Day SELL:
#    Check if stock is bought for today using the RSI/MA20 logic.
#    if bought:
#       if time of the day is 30 minutes before market close, sell.
#       else:
#        if stock value lower than lower threshold: sell
#        if higher than higher threshold: tag it as as crossed the high threshold
#        if stock is lower than higher threshold and marked crossed high threshold, sell
#

# ----------------------------------
# RSI Calculations
# ----------------------------------
def calculate_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df
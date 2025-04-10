# Script covers the following aspect.

# Input Parameters via Command Line
  Read the script (NIFTY or BANKNIFTY), option type (Call or Put), strike price, and number of lots.

# Determine Expiry & Script Name
  Fetch the upcoming expiry date and construct the option symbol (e.g., NIFTY31OCT2425000CE).
  Retrieve the corresponding symbol token for LTP (Last Traded Price) and margin verification.
  
# Check Margin Availability
  Ensure sufficient margin is available in the trading account to execute the trade.
  
# Calculate Stop-Loss
  Based on the LTP, compute a 2% stop-loss price.

# Execute Trades
  If margin is sufficient, place a Sell order and a corresponding Stop-Loss Buy order.

**TO RUN THE SCRIPT,**
**python ./main.py --fetchtoken 1**
- To fetch the latest symbol token.

**python ./main.py --call 21000 --lot 1 --script NIFTY**
- To execute the Option Call Selling with Stoploss order.
  
**python ./main.py --put 21000 --lot 1 --script NIFTY**
- To execute the Option Put Selling with Stoploss order.

**python ./main.py --call 21000 --lot 1 --script NIFTY -mc 1**
- mc 1 flag used to check for margin

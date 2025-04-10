from SmartApi import SmartConnect #or from SmartApi.smartConnect import SmartConnect
import pyotp
import argparse
import datetime
import threading
from prettytable import PrettyTable
import requests
import json
from dateutil.relativedelta import relativedelta, TH, WE, FR

import logging
logging.basicConfig(filename="log.log", format='%(asctime)s %(message)s', filemode='w')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

config = {
    "NIFTY": {
        "lot": 25,
        "weekDay": 3, # Thursday
        "expiry": "WEEK"
    },
    "BANKNIFTY": {
        "lot": 15,
        "weekDay": 3, # Thursday
        "expiry": "MONTH"
    }
}

def storeOrderData(data):
    jsonData = {}
    with open("order-data-main.json") as file:
        first_char = file.read(1)
        if not first_char:
            logger.info("order-data-main JSON is empty\n")
        else:
            with open("order-data-main.json", "r") as fp:
                jsonData = json.load(fp)
        
    jsonData.update(data)

    with open('order-data-main.json', 'w+') as outfile:
        json.dump(jsonData, outfile, indent=4)

def getOrderData(property):
    with open("order-data-main.json") as file:
        data = json.load(file)
        return data.get(property)
    
def getCredtialOrderData(property):
    with open("cred.json") as file:
        data = json.load(file)
        return data.get(property)

def getSymbolToken(symbolName = None):
    response = []
    with open("market-symbol-token.txt", "r") as fp:
        first_char = fp.read(1)
        if not first_char:
            logger.info("File (market-symbol-token) is empty, processing request...\n")
            res = requests.get('https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json')
            response = json.loads(res.text)
            # write-in-file
            with open("market-symbol-token.txt", "w") as fp1:
                json.dump(response, fp1)
            logger.info("Response written to the file.\n")
        else:
            logger.info("File (market-symbol-token) is NOT empty\n")
            with open("market-symbol-token.txt", "r") as fp:
                response = json.load(fp)

    if (symbolName != None):
        filtered_list = [d for d in response if d['symbol'] == symbolName]

        return {
            'status': True if (len(filtered_list) > 0) else False,
            'data': [
                {
                    "symboltoken": filtered_list[0]['token']
                } 
            ] if (len(filtered_list) > 0) else []
        }

def roundToPaise(amount):
    paise = round(amount * 100)
    rounded_paise = round(paise / 5) * 5
    rounded_amount = rounded_paise / 100.0
    return rounded_amount

def getExpiryDayAsStr(sybmbolName):
    dayConfig = config.get(sybmbolName)
    expiryWeekday = dayConfig.get("weekDay")
    expiry = dayConfig.get("expiry")
    
    if (expiry == "WEEK"):
        logger.info("Weekly expiry\n")
        today = datetime.date.today()
        return (today + relativedelta(weekday=expiryWeekday)).strftime("%d%b%y").upper()
    else: # MONTH
        logger.info("Monthly expiry\n")
        expiryDate = getExpiry(expiryWeekday)
        # If the expiry date of contract is past
        if (expiryDate.date() < datetime.datetime.now().date()):
            today = datetime.date.today()
            next_month_first_date = today + relativedelta(months=1, day=1)
            expiryDate = getExpiry(expiryWeekday, next_month_first_date)
    
    return expiryDate.strftime("%d%b%y").upper()

def getExpiry(expiryWeekday, datetimeObj = None):
    expiryIdentification = datetimeObj if datetimeObj != None else datetime.datetime.now()
    if (expiryWeekday == 2):
        expiryDate = (expiryIdentification + relativedelta(day=31, weekday=WE(-1)))
    elif (expiryWeekday == 3):
        expiryDate = (expiryIdentification + relativedelta(day=31, weekday=TH(-1)))
    elif (expiryWeekday == 4):
        expiryDate = (expiryIdentification + relativedelta(day=31, weekday=FR(-1)))
    return expiryDate
    
def calculateQuantity():
    givenLot = getOrderData("lot")
    symbolName = getOrderData("symbol")
    _lotsConfig = config.get(symbolName)
    symbolQty = _lotsConfig.get("lot")    
    return str(symbolQty * givenLot)

# symbolName - MRPL-EQ
# symbolToken - 2283
# variety - NORMAL | STOPLOSS
# ordertype - MARKET | STOPLOSS_LIMIT
# transactiontype - BUY | SELL
# strike - CE | PE
# triggerPrice - If STOPPLOSS order
def placeOrder(symbolName, symbolToken, variety, ordertype, transactiontype, strike, triggerPrice = None):
    logger.info(f"...........Proceeding {variety} order placement request...........\n")
    try:
        orderparams = {
            "variety": variety,
            "tradingsymbol": symbolName,
            "symboltoken": symbolToken,
            "transactiontype": transactiontype,
            "exchange": "NFO",
            "ordertype": ordertype,
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            "quantity": calculateQuantity()
        }
        if (variety == "STOPLOSS"):
            orderparams['triggerprice'] = roundToPaise(triggerPrice)
            orderparams['price'] = roundToPaise((triggerPrice + 1))

        logger.info(f"Order meta data ({symbolName}), {orderparams}\n")

        response = smartApi.placeOrderFullResponse(orderparams)

        logger.info(f"Order response...{response}\n")

        if (response['status']):
            logger.info(f"Order has been placed successfully...\n")
            
            if (variety == "STOPLOSS"):
                sl_order_id = response['data']['orderid']
                logger.info(f"Order id of the SL order - {sl_order_id}\n")

                # Write into json file
                orderData = {
                    symbolName: sl_order_id
                }
                storeOrderData(orderData)
            else:
                logger.info(f"Time of order executed - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n")
        else:
            logger.info(f"Failed to execute the order...\n")
    except Exception as e:
        logger.critical(f"Order placement failed with exception for {symbolName}:\n")
        logger.critical(e)
    logger.info("................................................................................\n")

def modifySLOrder(orderId, symbolName, symbolToken, triggerPrice):
    logger.info("...........Proceeding order modification request...........\n")
    try:
        orderparams = {
            "variety": "STOPLOSS",
            "orderid": orderId,
            "ordertype": "STOPLOSS_LIMIT",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            "quantity": calculateQuantity(),
            "tradingsymbol": symbolName,
            "symboltoken": symbolToken,
            "exchange": "NFO",
            "triggerprice": roundToPaise(triggerPrice),
            "price": roundToPaise(triggerPrice + 1)
        }
        logger.info(f"Order modification meta data ({symbolName}), {orderparams}\n")

        modifyOrderRes = smartApi.modifyOrder(orderparams)
        logger.info(f"Modify order response...{modifyOrderRes}\n")

        if (modifyOrderRes['status']):
            logger.info(f"Order has been modified successfully...\n")
        else:
            logger.info(f"Failed to execute the order...\n")
    except Exception as e:
        logger.critical(f"Order modification failed with exception for {symbolName}\n")
        logger.critical(e)
    logger.info("................................................................................\n")

def cancelSLOrder(orderId):
    logger.info("...........Proceeding order cancel request...........\n")
    param = {
        "variety":"STOPLOSS",
        "orderid":orderId
    }
    cancelOrder = smartApi.cancelOrder(param)
    if (cancelOrder['status']):
        logger.info("SL has been cancelled successfully...\n")
    else: 
        logger.info("Failed to cancel the  SL order...\n")

# script - NIFTY | BANKNIFTY
# strike - CE | PE
# strike price - 24500
def prepareForTrade(script, strike, strikePrice, marginCheck):
    logger.info("...........Get the script token...........\n")
    
    # get next expiry thrusday (NIFTY), wednesday (BANKNIFTY)
    expiry = getExpiryDayAsStr(script)
    scriptName = f"{script}{expiry}{strikePrice}{strike}" # NIFTY31OCT2425000CE
    logger.info(f"Script name prepared - {scriptName}\n")

    logger.info("Searching script...\n")
    # fetchScriptToken = smartApi.searchScrip("NFO", scriptName)
    fetchScriptToken = getSymbolToken(scriptName)
    
    if fetchScriptToken['status'] and len(fetchScriptToken["data"]) > 0:
        logger.info("Script searching request success. data found\n")

        scirptToken = fetchScriptToken["data"][0]["symboltoken"]
        logger.info(f"Script ({scriptName}) token - {scirptToken}\n")

        logger.info("...........Margin calculation begin...........\n")
        positions= {
            "positions": [
                {
                    "qty": calculateQuantity(),
                    "exchange": "NFO",
                    "token": scirptToken,
                    "tradeType": "SELL",
                    "productType": "CARRYFORWARD",
                    "orderType": "MARKET"
                }
            ]
        }
        
        getMargin = smartApi.getMarginApi(positions)
        marginRequired = getMargin['data']['totalMarginRequired']
        logger.info(f"Margin required for the SELL order of strike {scriptName} - {marginRequired}\n")

        logger.info("Verifying the available cash...\n")
        avaiableMarginRes = smartApi.rmsLimit()        
        if avaiableMarginRes["status"]:
            avaiableMargin = float(avaiableMarginRes["data"]["availablecash"])
            logger.info(f"Available cash - {avaiableMargin}\n")
            if (marginRequired < avaiableMargin):
                logger.info("Required margin available to execute the trade\n")
            else:
                logger.info(f"No required margin available, Req Margin - {marginRequired}, Avail Margin - {avaiableMargin}, existing func...\n")
                return
            
            logger.info("...........Get LTP and SL calculation...........\n")
            getLTP = smartApi.ltpData("NFO", scriptName, scirptToken)
            if getLTP['status'] and bool(getLTP['data']['ltp']):
                logger.info(f"LTP of {scriptName} - {getLTP['data']['ltp']}\n")
                
                stopLoss = round((float(getLTP['data']['ltp']) * 0.2), 2) # 20% Stop loss from average price
                stopLossPrice = round((getLTP['data']['ltp'] + stopLoss), 2)
                logger.info(f"Stoploss (20%) - {stopLoss}, Stoploss price - {stopLossPrice}\n")
                logger.info(f"Slip away - {stopLoss * calculateQuantity()}\n")
                
                if (marginCheck):
                    logger.info("Exiting margin check.\n")
                    logger.info("................................................................................\n")
                    return

                # place SELL order
                placeOrder(scriptName, scirptToken, "NORMAL", "MARKET", "SELL", strike)
                # place SL (BUY) order
                placeOrder(scriptName, scirptToken, "STOPLOSS", "STOPLOSS_LIMIT", "BUY", strike, stopLossPrice)
            else:
                logger.info(f"Failed to fetch LTP data for {scriptName}\n")
        else:
            logger.info(f"Failed to fetch margin info ({scriptName}): {avaiableMarginRes}\n")
    else:
        logger.info("Failed to fetch script token.\n")

def checkPositionsPnL():
    logger.info(f"\n----------------------------| {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |-----------------------------\n")
    positionResponse = smartApi.position()
    positions = positionResponse["data"]

    if (len(positions) == 0):
        logger.info("No postions found...\n")
        return
    
    totalPnL = 0
    for item in positions:
        totalPnL += float(item["pnl"])
    
    orderTable = PrettyTable(["symboltoken", "tradingsymbol", "exchange", "sellavgprice", "buyavgprice", "ltp", "netqty", "pnl"])
    for x in positions:
        orderTable.add_row([x["symboltoken"], x["tradingsymbol"], x["exchange"], x["sellavgprice"], x["buyavgprice"], x["ltp"], x["netqty"], x["pnl"]])
    orderTable.add_row(["", "", "","", "", "", "", totalPnL])
    logger.info(orderTable)
    
    threading.Timer(30.0, checkPositionsPnL).start()

api_key = getCredtialOrderData("api_key")
username = getCredtialOrderData("username") # client id
pwd = getCredtialOrderData("pwd") # pin
smartApi = SmartConnect(api_key)
try:
    token = getCredtialOrderData("totptoken") # TOTP code
    totp = pyotp.TOTP(token).now()
except Exception as e:
    logger.critical(e)
    raise e
logger.info("...........Initiating session...........\n")
data = smartApi.generateSession(username, pwd, totp)

if data['status'] == False:
    logger.info(f"Failed to login, {data}\n")
    
else:
    # login api call
    authToken = data['data']['jwtToken']
    refreshToken = data['data']['refreshToken']
    # fetch the feedtoken
    feedToken = smartApi.getfeedToken()
    logger.info("Logged in successfully...\n")
    
    logger.info("...........Get arguments from the command line...........\n")
    parser = argparse.ArgumentParser()
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--call', default='')
    parser.add_argument('-p', '--put', default='')
    parser.add_argument('-l', '--lot', default='')
    parser.add_argument('-s', '--script', default='')
    parser.add_argument('-mc', '--margincheck', default='')
    parser.add_argument('-pnl', '--checkpnl', default='')
    parser.add_argument('-ftkn', '--fetchtoken', default='')
    args = parser.parse_args()

    if (args.lot != ""):
        logger.info(f"Lot size argument received - {args.lot}\n")
        storeOrderData({"lot": int(args.lot)})

    if (args.script != ""):
        logger.info(f"Script name argument received - {args.script}\n")
        storeOrderData({"symbol": args.script})

    marginCheck = False

    if (args.margincheck == "1"):
        marginCheck = True
    
    if (args.call != ""):
        logger.info(f"Call strike argument received - {args.call}\n")
        prepareForTrade(args.script, "CE", args.call, marginCheck)

    if (args.put != ""):
        logger.info(f"Put strike argument received - {args.put}\n")
        prepareForTrade(args.script, "PE", args.put, marginCheck)

    if (args.checkpnl != ""):
        logger.info(f"Argument received to check PnL...\n")
        checkPositionsPnL()

    if (args.fetchtoken != ""):
        logger.info(f"Argument received to fetch latest token...\n")
        open('market-symbol-token.txt', 'w').close()
        getSymbolToken()
     
    if (args.call == "" and args.put == "" and args.lot == "" and args.checkpnl == "" and args.fetchtoken == ""):
        logger.info("No arguments received.\n")

    # TO RUN THE SCRIPT,
    # python ./main.py --fetchtoken 1
    # python ./main.py --call 123 --lot 1 --script NIFTY -mc 1
    # python ./main.py --put 123 --lot 1 --script NIFTY -mc 1
#!/usr/bin/env python
# coding: utf-8

# In[1]:


import importlib
import threading
import time
import json
import datetime
import os
import codecs
    
from tcoreapi_mq import * 
import tcoreapi_mq

from pathlib import Path

import shioaji as sj
import shioaji_login
# Need to reload this for some reason that I can't remember.
importlib.reload(shioaji_login)


# In[2]:


def write_log(text):
    """
    Write into log file.
    
    :param text: (str)
    :return: None
    """

    now = datetime.datetime.now()
    path = 'auto_order_logs'
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        # directory already exists
        pass
    
    log_name = now.strftime('%Y%m%d') + '.log'
    path = os.path.join(path, log_name)

    # In order to let json dumps chinese correctly, codecs is needed.
    # When ever use json dumps, specify ensure_ascii=False
    fp = codecs.open(path, 'a+', 'utf16')
    fp.write(str(datetime.datetime.now()) + ": " + text + "\n")
    fp.close()
    


# In[3]:


def place_order(quantity, action):
    """
    Place a FOK order with price=MKT.
    :param: action = sj.constant.Action.Buy or sj.constant.Action.Sell
    :global param: api (shioaji.shioaji.Shioaji)
    :return: None
    """
    
    global auto_order_testing
    
    if not auto_order_testing:
        fut_order = api.Order(
            action=action,
            price=0,
            quantity=quantity,
            price_type=sj.constant.FuturesPriceType.MKT,
            order_type=sj.constant.FuturesOrderType.FOK, 
            octype=sj.constant.FuturesOCType.Auto,
            account=api.futopt_account
        )

        # Placing order
        trade = api.place_order(contract, fut_order)

        print('***')
        log_msg = f'A FOK order with action={action}, quantity={quantity} has been placed!'
        print(log_msg)
        write_log(log_msg)
        print(f'Trade msg: {trade.status.msg}')
        write_log(f'Trade msg: {trade.status.msg}')
        print('***\n')
    else:
        print('***')
        log_msg = f'A TESTING FOK order with action={action}, quantity={quantity} has been placed!'
        print(log_msg)
        write_log(log_msg)
        print('***\n')


# In[4]:


def get_future_code(future_name):
    """
    Return future code based on future name
    
    :param future_name: (str)
    
    :return: future_code (str)
    """
    
    now = datetime.datetime.now()
    month = now.month
    year = now.year
    first_weekday = now.replace(day=1).weekday()
    
    # Calculate the dayt of the third wednesday
    if(first_weekday < 3):
        third_wednesday = 17 - first_weekday
    else:
        third_wednesday = 24 - first_weekday
    
    if(
        now.day == third_wednesday and now.time() > datetime.time(13, 30) or
        now.day > third_wednesday
    ):
        month = month + 1
        if(month == 13):
            month = 1
            year += 1
    
    month_to_code = '0ABCDEFGHIJKL'
    
    future_code = future_name
    future_code += month_to_code[month]
    future_code += str(year%10)
    
    return future_code


# In[5]:


def update_config():
    
    global future_name, future_code, auto_order_time, auto_buy_trigger, auto_sell_trigger, auto_order_testing
    
    pre_future_code = pre_auto_order_time = pre_auto_buy_trigger = pre_auto_sell_trigger = pre_auto_order_testing = None
    
    
    while(True):
        
        with open('config.json') as f:
            config_data = json.load(f)
            
            future_name = config_data['future_name']
            auto_order_time = int(config_data['auto_order_time'])
            auto_buy_trigger = float(config_data['auto_buy_trigger'])
            auto_sell_trigger = float(config_data['auto_sell_trigger'])
            auto_order_testing = bool(config_data['auto_order_testing'])
        
            # If auto_recent_future, get the most recent future code.
            if(config_data['auto_recent_future'].lower() == 'true'):
                future_code = get_future_code(future_name)
            else:
                future_code = config_data['future_code']
        
            if(pre_future_code != future_code):
                print(f'Future code has been set to {future_code}')
                pre_future_code = future_code
            
            if(pre_auto_order_time != auto_order_time):
                print(f'Auto order time has been set to {auto_order_time}')
                pre_auto_order_time = auto_order_time
            
            if(pre_auto_buy_trigger != auto_buy_trigger):
                print(f'Auto buy trigger has been set to {auto_buy_trigger}')
                pre_auto_buy_trigger = auto_buy_trigger
                
            if(pre_auto_sell_trigger != auto_sell_trigger):
                print(f'Auto sell trigger has been set to {auto_sell_trigger}')
                pre_auto_sell_trigger = auto_sell_trigger
                
            if(pre_auto_order_testing != auto_order_testing):
                print(f'Auto order testing has been set to {auto_order_testing}')
                pre_auto_order_testing = auto_order_testing
                
            time.sleep(1)


# In[6]:


def OnRealTimeQuote(symbol):
    global NQ_price, price_history
    NQ_price = float(symbol['TradingPrice'])
    price_history.append([NQ_price, datetime.datetime.now()])
    if NQ_price - price_history[0][0] > auto_buy_trigger:
        msg_log = "A huge increasing in price has been detected!\n"
        msg_log += "Price " + str((datetime.datetime.now() - price_history[0][1]).total_seconds()) + " seconds ago: " + str(price_history[0][0]) + "\n"
        msg_log += "Price now: " + str(NQ_price)
        write_log(msg_log)
        print(msg_log)
        place_order(1, sj.constant.Action.Buy)
        price_history = []
    elif price_history[0][0] - NQ_price > auto_sell_trigger:
        msg_log = "A huge decreasing in price has been detected!\n"
        msg_log += "Price " + str((datetime.datetime.now() - price_history[0][1]).total_seconds()) + " seconds ago: " + str(price_history[0][0]) + "\n"
        msg_log += "Price now: " + str(NQ_price)
        write_log(msg_log)
        print(msg_log)
        place_order(1, sj.constant.Action.Sell)
        price_history = []
    else:
        while (datetime.datetime.now() - price_history[0][1]).total_seconds() > auto_order_time:
            # Delete data that is too old
            del price_history[0]
            


# In[7]:


def quote_sub_th(obj,sub_port,filter = ""):
    socket_sub = obj.context.socket(zmq.SUB)
    #socket_sub.RCVTIMEO=7000   #ZMQ超時設定
    socket_sub.connect("tcp://127.0.0.1:%s" % sub_port)
    socket_sub.setsockopt_string(zmq.SUBSCRIBE,filter)
    while(True):
        message = (socket_sub.recv()[:-1]).decode("utf-8")
        index =  re.search(":",message).span()[1]  # filter
        message = message[index:]
        message = json.loads(message)
        #for message in messages:
        if(message["DataType"]=="REALTIME"):
            OnRealTimeQuote(message["Quote"])
        elif(message["DataType"]=="GREEKS"):
            OnGreeks(message["Quote"])
        elif(message["DataType"]=="TICKS" or message["DataType"]=="1K" or message["DataType"]=="DK" ):
            #print("@@@@@@@@@@@@@@@@@@@@@@@",message)
            strQryIndex = ""
            while(True):
                s_history = obj.GetHistory(g_QuoteSession, message["Symbol"], message["DataType"], message["StartTime"], message["EndTime"], strQryIndex)
                historyData = s_history["HisData"]
                if len(historyData) == 0:
                    break
                last = ""
                for data in historyData:
                    last = data
                    print("歷史行情：Time:%s, Volume:%s, QryIndex:%s" % (data["Time"], data["Volume"], data["QryIndex"]))
                
                strQryIndex = last["QryIndex"]
                    
    return


# In[8]:


future_name = future_code = None

auto_order_time = auto_buy_trigger = auto_sell_trigger = None

auto_order_testing = None

update_config_thread = threading.Thread(target = update_config)
update_config_thread.start()

time.sleep(3)

api = shioaji_login.login()

contract = api.Contracts.Futures[future_code]
try:
    if(not contract):
        raise ValueError(f'Error: contract {future_code} does not exsits.')
except ValueError as err:
    traceback.print_exc()


# In[9]:


NQ_price = 0

price_history = []

g_QuoteZMQ = None
g_QuoteSession = ""

#登入(與 TOUCHANCE zmq 連線用，不可改)
g_QuoteZMQ = QuoteAPI("ZMQ","8076c9867a372d2a9a814ae710c256e2")
q_data = g_QuoteZMQ.Connect("51237")
print(q_data)

if q_data["Success"] != "OK":
    print("[quote]connection failed")

g_QuoteSession = q_data["SessionKey"]


#查詢指定合约訊息
quoteSymbol = "TC.F.CME.NQ.HOT"

print("Subscribing to CME.NQ .")

t2 = threading.Thread(target = quote_sub_th,args=(g_QuoteZMQ,q_data["SubPort"],))
t2.start()
#實時行情訂閱
#解除訂閱
g_QuoteZMQ.UnsubQuote(g_QuoteSession, quoteSymbol)
#訂閱實時行情
g_QuoteZMQ.SubQuote(g_QuoteSession, quoteSymbol)





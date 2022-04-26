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


def report_time():
    global NQ_price
    
    while True:
        print("Time report:", datetime.datetime.now().strftime("%H:%M:%S"), ", price:", NQ_price)
        time.sleep(auto_order_time_report)


# In[3]:


def write_log(text):
    """
    Write into log file.
    
    :param text: (str)
    :return: None
    """

    now = datetime.datetime.now()
    path = 'auto_order_nq_logs'
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
    


# In[4]:


def list_positions():
    """
    List all positions.
    :global param: positions
    """
    
    print('The position currently tracking:')

    if not positions:
        print('Empty.')

    for p in positions:

        if(p[0] == 1):
            action_text = "Long"
        else:
            action_text = "Short"

        print(f'[Type: {action_text}, quantity: {p[1]}, deal price: {p[2]}, best price: {p[3]}, cover order had been sent: {p[4]}]')
    


# In[5]:


def send_test_msg(
    price,
    quantity,
    action,
    stat=sj.constant.OrderState.FDeal,
    code='MXF',
    delivery_month='202201',
    security_type='FUT'
):
    """
    For test purpose.
    """
    # Testing with msg

    msg = {}
    msg['price'] = price
    msg['quantity'] = quantity
    msg['action'] = action
    msg['code'] = code
    msg['delivery_month'] = delivery_month
    msg["security_type"] = security_type

    place_cb(stat, msg)


# In[6]:


def place_order(quantity, action):
    """
    Place a FOK order with price=MKT.
    :param: action = sj.constant.Action.Buy or sj.constant.Action.Sell
    :global param: api (shioaji.shioaji.Shioaji)
    :return: None
    """
    
    global auto_order_testing_day, auto_order_testing_night, positions
    
    auto_order_testing = True
    
    now = datetime.datetime.now()
    
    if now.time() < datetime.time(5, 0, 0) or now.time() >= datetime.time(15, 0, 0):
        auto_order_testing = auto_order_testing_night
    elif now.time() >= datetime.time(8, 45, 0) and now.time() < datetime.time(13, 45, 0):
        auto_order_testing = auto_order_testing_day
    
    if positions:
        print('***')
        log_msg = f'A order with action={action}, quantity={quantity} should be place, but there is still position in hold, so the order will not be sent.'
        
        print(log_msg)
        write_log(log_msg)
        
        list_positions()
        print('***')
        time.sleep(10)
        return
    
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
        
    time.sleep(10)


# In[7]:


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
    
    # Calculate the day of the third wednesday
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


# In[8]:


def update_config():
    
    global future_name, future_code
    global order_quantity
    global auto_order_consec_tick, auto_order_time, auto_buy_trigger, auto_sell_trigger
    global auto_order_testing_day, auto_order_testing_night
    global auto_order_time_report
    
    pre_order_quantity = None
    pre_future_code = pre_auto_order_time = None
    pre_auto_buy_trigger = pre_auto_sell_trigger = None
    pre_auto_order_testing_day = pre_auto_order_testing_night = None
    pre_auto_order_consec_tick = pre_auto_order_time_report = None
    
    
    
    while(True):
        
        with open('auto_order_nq_config.json') as f:
            config_data = json.load(f)
            
            future_name = config_data['future_name']
            order_quantity = int(config_data['order_quantity'])
            auto_order_time = float(config_data['auto_order_time'])
            auto_buy_trigger = float(config_data['auto_buy_trigger'])
            auto_sell_trigger = float(config_data['auto_sell_trigger'])
            if config_data['auto_order_testing_day'].lower() == "false":
                auto_order_testing_day = False
            else:
                auto_order_testing_day = True
                
            if config_data['auto_order_testing_night'].lower() == "false":
                auto_order_testing_night = False
            else:
                auto_order_testing_night = True
                
            auto_order_consec_tick = int(config_data['auto_order_consec_tick'])
            auto_order_time_report = float(config_data['auto_order_time_report'])
            
            # If auto_recent_future, get the most recent future code.
            if(config_data['auto_recent_future'].lower() == 'true'):
                future_code = get_future_code(future_name)
            else:
                future_code = config_data['future_code']
        
            if(pre_future_code != future_code):
                print(f'Future code has been set to {future_code}')
                pre_future_code = future_code
            
            if(pre_order_quantity != order_quantity):
                print(f'Order quantity has been set to {order_quantity}')
                pre_order_quantity = order_quantity
            
            if(pre_auto_order_time != auto_order_time):
                print(f'Auto order time has been set to {auto_order_time}')
                pre_auto_order_time = auto_order_time
            
            if(pre_auto_order_consec_tick != auto_order_consec_tick):
                print(f'Auto consecutive tick has been set to {auto_order_consec_tick}')
                pre_auto_order_consec_tick = auto_order_consec_tick
            
            if(pre_auto_buy_trigger != auto_buy_trigger):
                print(f'Auto buy trigger has been set to {auto_buy_trigger}')
                pre_auto_buy_trigger = auto_buy_trigger
                
            if(pre_auto_sell_trigger != auto_sell_trigger):
                print(f'Auto sell trigger has been set to {auto_sell_trigger}')
                pre_auto_sell_trigger = auto_sell_trigger
                
            if(pre_auto_order_testing_day != auto_order_testing_day):
                print(f'Auto order testing day has been set to {auto_order_testing_day}')
                pre_auto_order_testing_day = auto_order_testing_day
                
            if(pre_auto_order_testing_night != auto_order_testing_night):
                print(f'Auto order testing night has been set to {auto_order_testing_night}')
                pre_auto_order_testing_night = auto_order_testing_night
                
            if(pre_auto_order_time_report != auto_order_time_report):
                print(f'Auto order time report period has been set to {auto_order_time_report}')
                pre_auto_order_time_report = auto_order_time_report    
                
            time.sleep(1)


# In[9]:


count = 0


# In[10]:



# 在這裡下單
def OnRealTimeQuote(symbol):
    
    
    global count
    count += 1
    
    global NQ_price, price_history, trade_lock
    
    #print("OnRealTimeQuote: " + str(NQ_price))
    
    #print(NQ_price, count)
    # price_history(不含最新的一個price)的長度即為中間間隔幾個tick的長度
    while len(price_history) > auto_order_consec_tick:
        del price_history[0]
    
    NQ_price = float(symbol['TradingPrice'])
    if NQ_price == 0:
        return
    
    
    price_history.append([NQ_price, datetime.datetime.now()])
    
    if len(price_history) < 2:
        return
    
    pre_price_diff = 0
    
    if trade_lock: # trade_lock=True時仍然會記錄價格，但不會判斷是否要trade
        return
    
    for i in range(len(price_history) - 1, 0, -1): # 從倒數第二個traverse到第一個
        
        price_diff = price_history[i][0] - price_history[i-1][0]
        
        
        #print(pre_price_diff, price_diff)
        if pre_price_diff > 0 and pre_price_diff <= price_diff:
            return
        elif pre_price_diff < 0 and pre_price_diff >= price_diff:
            return
        
        pre_price_diff = price_diff
        
        tick_diff = price_history[-1][0] - price_history[i-1][0]
        
        if (price_history[-1][1] - price_history[i-1][1]).total_seconds() > auto_order_time:
            # 超時
            break
        

        
        if price_diff > 0 and         tick_diff > auto_buy_trigger:
            msg_log = "A huge increasing in price has been detected!\n"
            msg_log += "NQ_Price " + str((price_history[-1][1] - price_history[i-1][1]).total_seconds()) +             " seconds ago: \n" + str(price_history[i-1][0]) +             ", " + str(price_history[i-1][1]) +             "\n"
            msg_log += "Ticks in between:\n"
            for j in range(i, len(price_history)-1):
                msg_log += str(price_history[j][0]) + ", " + str(price_history[j][1]) + "\n"
            msg_log += "NQ_Price now: \n" + str(price_history[-1][0]) + ", " + str(price_history[-1][1])
            write_log(msg_log)
            print(msg_log)
            trade_lock = True
            place_order(order_quantity, sj.constant.Action.Buy)
            price_history = []
            trade_lock = False
            return
        
        if price_diff < 0 and         tick_diff < -auto_sell_trigger:
            msg_log = "A huge decreasing in price has been detected!\n"
            msg_log += "NQ_Price " + str((price_history[-1][1] - price_history[i-1][1]).total_seconds()) +             " seconds ago: \n" + str(price_history[i-1][0]) +             ", " + str(price_history[i-1][1]) +             "\n"
            msg_log += "Ticks in between:\n"
            for j in range(i, len(price_history)-1):
                msg_log += str(price_history[j][0]) + ", " + str(price_history[j][1]) + "\n"
            msg_log += "NQ_Price now: \n" + str(price_history[-1][0]) + ", " + str(price_history[-1][1])
            write_log(msg_log)
            print(msg_log)
            trade_lock = True
            place_order(order_quantity, sj.constant.Action.Sell)
            price_history = []
            trade_lock = False
            return


# In[11]:


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


# In[12]:


def fill_positions(deal):
    """
    :global param positions: (list)
    
    :return: None
    """

    global positions
    # First check if the type and month match the tracking future.
    if(
        deal['code'] != contract['category'] or
        deal['delivery_month'] != contract['delivery_month'] or
        deal["security_type"] != 'FUT'
      ):
        print("This deal is not as same as the future currently tracking.")
        return
    
    price = int(deal['price'])
    quantity = int(deal['quantity'])
    try:
        if(deal['action'] == 'Buy'):
            action = 1
        elif(deal['action'] == 'Sell'):
            action = -1
        else:
            raise ValueError('The action of this deal is neither "Buy" or "Sell".')
    except ValueError as err:
        traceback.print_exc()
    
    if(action == 1):
        action_text = "Long"
    else:
        action_text = "Short"
    
    # While there are still some positions and it is the oppsite of the deal:
    ori_quantity = quantity
    while(positions and positions[0][0] == -action and quantity > 0):
        
        if(positions[0][1] > quantity):
            positions[0][1] -= quantity
            quantity = 0
            # The deal has been recorded, exit the function
            break
        else:
            quantity -= positions[0][1]
            del positions[0]

    print('***')
    log_msg = f'A position with type={action_text}, quantity={ori_quantity}, price={price} has been recorded!'
    print(log_msg)
    write_log(log_msg)
    print('***\n')
    
    if (quantity > 0):
        
        # Ensure the data type is int
        
        
        if(action == 1):
            positions.append([action, int(quantity), int(price), int(price), False])
            positions = sorted(positions, key=lambda p: p[2], reverse=False)
        else:
            positions.append([action, int(quantity), int(price), int(price), False])
            positions = sorted(positions, key=lambda p: p[2], reverse=True)

        print('***')
        log_msg = f'A position with type={action_text}, quantity={quantity}, price={price} has been added to the track list!'
        print(log_msg)
        write_log(log_msg)
        print('***\n')


# In[13]:


msg_list = []

def place_cb(stat, msg):
    """
    Called every time an order or a deal has been detected.
    
    :global param: msg_list ()
    """
    
    global msg_list
    
    if(stat == sj.constant.OrderState.FOrder):
        print('An order has been detected.')
        print(f'op_msg: \"{msg["operation"]["op_msg"]}\"')
        write_log('stat: ' + stat + '\nmsg: ' + json.dumps(msg, ensure_ascii=False) )
        msg_list.append(msg)
    elif(stat == sj.constant.OrderState.FDeal):
        print('A deal has been detected.')
        print(f'Deal information: code:{msg["code"]}, action:{msg["action"]}, price:{msg["price"]}, quantity:{msg["quantity"]}')
        print(f'Delivery month:{msg["delivery_month"]}, security type: {msg["security_type"]}')
        write_log('stat: ' + stat + '\nmsg: ' + json.dumps(msg, ensure_ascii=False) )
        msg_list.append(msg)
        fill_positions(msg)


# In[14]:


future_name = future_code = None

order_quantity = None

auto_order_time = auto_buy_trigger = auto_sell_trigger = None

auto_order_testing_day = auto_order_testing_night = auto_order_time_report = None

trade_lock = False

update_config_thread = threading.Thread(target = update_config)
update_config_thread.start()

time.sleep(3)

api = shioaji_login.login()

contract = api.Contracts.Futures[future_code]

api.set_order_callback(place_cb)

try:
    if(not contract):
        raise ValueError(f'Error: contract {future_code} does not exsits.')
except ValueError as err:
    traceback.print_exc()
    
positions = []


# In[15]:


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
#quoteSymbol = "TC.F.CME.NQ.HOT"
quoteSymbol = "TC.F.TWF.FITX.HOT"


print("Subscribing to TWF.FITX.HOT")

t2 = threading.Thread(target = quote_sub_th,args=(g_QuoteZMQ,q_data["SubPort"],))
t2.start()
#實時行情訂閱
#解除訂閱
g_QuoteZMQ.UnsubQuote(g_QuoteSession, quoteSymbol)
#訂閱實時行情
g_QuoteZMQ.SubQuote(g_QuoteSession, quoteSymbol)

time.sleep(5)
report_time_thread = threading.Thread(target = report_time)
report_time_thread.start()

"""
台灣是UTC＋8
那斯達克: 標準時間（EST）為UTC-5，夏令時間（EDT）為UTC-4。開盤時間：週一至週五上午9:30至下午4：00
也就是說開盤時間為台灣時間周一22:30~週五17:00，平常為22:30~17:00


"""


#!/usr/bin/env python
# coding: utf-8

# In[1]:


DEBUG_MSG = False


# In[2]:


import os
import sys
import json
import time
import datetime
import traceback
import threading
import importlib
import codecs

from pathlib import Path

import shioaji as sj
import shioaji_login
# Need to reload this for some reason that I can't remember.
importlib.reload(shioaji_login)


# In[3]:


def write_log(text):
    """
    Write into log file.
    
    :param text: (str)
    :return: None
    """

    now = datetime.datetime.now()
    path = 'coverer_logs'
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
    fp.write(text)
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


def stop_price_updater():
    """
    Threading function.
    Update stop price every single seconds.
    If the time for now is inside of the range intense time, set the prices to intense version.
    Otherwise, set them to normal version.
    This thread will run as long as the program is running.
    
    :global param profit_stop: (int)
    :global param loss_stop: (int)
    :global param normal_profit_stop: (int)
    :global param normal_loss_stop: (int)
    :global param intense_profit_stop: (int)
    :global param intense_loss_stop: (int)
    
    :return: None
    """
    
    global profit_stop, loss_stop
    
    pre_profit_stop = 0
    pre_loss_stop = 0
    
    while(True):
        now = datetime.datetime.now().time()
        
        if(now > intense_begin_time or now < intense_end_time):
            profit_stop = intense_profit_stop
            loss_stop = intense_loss_stop
        else:
            profit_stop = normal_profit_stop
            loss_stop = normal_loss_stop
        
        if(pre_profit_stop != profit_stop or pre_loss_stop != loss_stop):
            
            print(f'Profit stop has been set to {profit_stop}')
            print(f'Loss stop has been set to {loss_stop}')
        
        pre_profit_stop = profit_stop
        pre_loss_stop = loss_stop
        
        time.sleep(1)
        
    return


# In[6]:


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


# In[7]:


def place_cover_order(quantity, action, original_price, market_price):
    """
    Place the cover order.
    
    :global param: api (shioaji.shioaji.Shioaji)
    :return: None
    """
    fut_order = api.Order(
        action=action,
        price=0,
        quantity=quantity,
        price_type=sj.constant.FuturesPriceType.MKT,
        order_type=sj.constant.FuturesOrderType.FOK, 
        octype=sj.constant.FuturesOCType.Cover,
        account=api.futopt_account
    )
        
    # Placing order
    trade = api.place_order(contract, fut_order)
    
    print('***')
    log_msg = f'An cover order with action={action}, quantity={quantity} has been placed!'
    print(log_msg)
    write_log(log_msg)
    print(f'Trade msg: {trade.status.msg}')
    write_log(f'Trade msg: {trade.status.msg}')
    print('***\n')


# In[8]:


def auto_cover():
    """
    Threading function.
    If the time now is auto_cover_time, cover all of the tracking position.
    
    :global param: auto_cover_time
    :global param: positions
    :return: None
    """
    
    while(True):
        
        now = datetime.datetime.now()
        
        if(now.time().replace(microsecond=0) == auto_cover_time):
            print('***It is now auto cover time. All tracking positions will be covered.***')
            list_positions()
            
            for p in positions:
                if(p[4]):
                    continue
                if(p[0] == 1):
                    cover_action = sj.constant.Action.Sell
                else:
                    cover_action = sj.constant.Action.Buy
                    
                p[4] = True
                place_cover_order(p[1], cover_action, p[2], market_price)
                
        time.sleep(1)


# In[9]:


def price_checker(market_price):
    """
    Called every time market price is updated.
    Update best price of every tracking positions based on market price.
    Try to cover positions if stop price has been met.
    :global param: positions (list)
    :return: None
    """
    
    global positions
    
    for p in positions:
        if(p[0] == 1):
            if(market_price > (p[2] + profit_stop)):
                # Best price should at least be greater than buy price + profit_stop
                p[3] = int(max(p[3], market_price))
        elif(p[0] == -1 and market_price != 0):
            if(market_price < (p[2] - profit_stop)):
                # Best price should at least be less than sell price - profit_stop
                p[3] = int(min(p[3], market_price))
    
    #p[3] is the best price
    for p in positions:
        
        # Check if this positions is being cover
        if(p[4]):
            continue
        
        if(p[0] == 1):
            cover_action = sj.constant.Action.Sell
            if(market_price <= (p[2] - loss_stop)):
                p[4] = True
                print(f"A loss stop has been detected. Market price: {market_price}, buy price: {p[2]}, best price: {p[3]}")
                place_cover_order(p[1], cover_action, p[2], market_price)
                break
            elif(market_price <= (p[3] - profit_stop) and (market_price > p[2])):
                # Sell price should be greater than original price
                p[4] = True
                print(f"A profit stop has been detected. Market price: {market_price}, buy price: {p[2]}, best price: {p[3]}")
                place_cover_order(p[1], cover_action, p[2], market_price)
                break
        elif(p[0] == -1):
            cover_action = sj.constant.Action.Buy
            if(market_price >= (p[2] + loss_stop)):
                p[4] = True
                print(f"A loss stop has been detected. Market price: {market_price}, sell price: {p[2]}, best price: {p[3]}")
                place_cover_order(p[1], cover_action, p[2], market_price)
                break
            elif(market_price >= (p[3] + profit_stop) and (market_price < p[2])):
                # Buy price should be less than original price
                p[4] = True
                print(f"A profit stop has been detected. Market price: {market_price}, sell price: {p[2]}, best price: {p[3]}")
                place_cover_order(p[1], cover_action, p[2], market_price)
                break


# In[10]:


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


# In[11]:


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
        
    # TODO: update_status may be useful?
    #api.update_status(api.future_account)


# In[12]:


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


# In[13]:


def update_config():
    
    global intense_begin_time, intense_end_time, normal_profit_stop, normal_loss_stop, intense_profit_stop, intense_loss_stop
    global auto_cover_time
    global future_name, future_code
    
    pre_future_code = None
    pre_auto_cover_time = None
    while(True):
        
        with open('config.json') as f:
            config_data = json.load(f)

            intense_begin_time = datetime.datetime.strptime(config_data['intense_begin'], '%H:%M').time()
            intense_end_time = datetime.datetime.strptime(config_data['intense_end'], '%H:%M').time()
            auto_cover_time = datetime.datetime.strptime(config_data['auto_cover'], '%H:%M:%S').time()
            
            normal_profit_stop = int(config_data['normal_profit_stop'])
            normal_loss_stop = int(config_data['normal_loss_stop'])
            intense_profit_stop = int(config_data['intense_profit_stop'])
            intense_loss_stop = int(config_data['intense_loss_stop'])

            future_name = config_data['future_name']
        
            # If auto_recent_future, get the most recent future code.
            if(config_data['auto_recent_future'].lower() == 'true'):
                future_code = get_future_code(future_name)
            else:
                future_code = config_data['future_code']
        
            if(pre_future_code != future_code):
                print(f'Future code has been set to {future_code}')
                pre_future_code = future_code
            if(auto_cover_time != pre_auto_cover_time):
                print(f'Auto cover time has been set to {auto_cover_time}, Time is now {datetime.datetime.now().strftime("%H:%M:%S")}.')
                pre_auto_cover_time = auto_cover_time
            
            time.sleep(1)


# In[14]:


# This is a navie UI implementation. I wonder if there is some framework-like UI availible?

def UI():
    """
    Threading function.
    User Interface.
    
    :global param: market_price (int)
    """
    print("Waiting for commands...")
    while(True):
        
        try:
            input_text = input()
        except EOFError:
            pass
        
        if(input_text == str('price')):
            
            print(f'Market price for {contract["code"]}: {market_price}')
            print(f'Profit stop: {profit_stop}, loss stop: {loss_stop}')
            
        elif(input_text == 'list'):
            
            list_positions()
            
        elif(input_text == 'contract'):
            
            print(f'Currently contract: {contract["code"]}')
            
        elif(input_text == 'quit'):
            
            quit()
            return
        
        elif(input_text == 'help'):
            
            print('price: Get the market price of currently contract. Also show the stop prices.')
            print('list: List the position currently tracking.')
            print('contract: Get the currently contract.')
            print('quit: Exit the program.')
            
        else:
            print(f'Command "{input_text}" is not recognized.')


# In[15]:


# Main

api = shioaji_login.login()

api.set_order_callback(place_cb)

# Parsing config.json every second

intense_begin_time = intense_end_time = normal_profit_stop = normal_loss_stop = intense_profit_stop = intense_loss_stop = None
auto_cover_time = None
future_name = future_code = None

# Start update config thread. All config variable will be updated every second.
update_config_thread = threading.Thread(target = update_config)
update_config_thread.start()

time.sleep(3)

# profit_stop and loss_stop need to be initialize as None before calling stop_price_updater
profit_stop = None
loss_stop = None

# Start stop price updater thread.
stop_price_updater_thread = threading.Thread(target = stop_price_updater)
stop_price_updater_thread.start()

# Start auto cover thread.
auto_cover_thread = threading.Thread(target = auto_cover)
auto_cover_thread.start()

# Get contract
contract = api.Contracts.Futures[future_code]
try:
    if(not contract):
        raise ValueError(f'Error: contract {future_code} does not exsits.')
except ValueError as err:
    traceback.print_exc()

# positions is a list of list
# Each single list cotains 5 values: Position_type, quantity, price, best_price, is_covering
# Position_type determine the type of positions holding. 0: Neutral, 1: Long, -1: short
positions = []

# Update price with each tick and check.
market_price = 0

@api.on_tick_fop_v1()
def quote_callback(exchange:sj.Exchange, tick:sj.TickFOPv1):
    """
    Quoting subscribe function. It is called every tick(theoretically)
    
    :global param: market_price (int)
    :return: None
    """
    
    global market_price
    market_price = int(tick['close'])
    if(DEBUG_MSG):
        print(market_price)
    price_checker(market_price)



# Subscribe to the close price of the contract
api.quote.subscribe(
    contract,
    quote_type = sj.constant.QuoteType.Tick, # or 'tick'
    version = sj.constant.QuoteVersion.v1, # or 'v1'
)


# Simply run UI without threading.
UI()

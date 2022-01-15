import json
import time
import datetime
import traceback
import threading
import importlib

import shioaji as sj
import shioaji_login
# Need to reload this for some reason that I can't remember.
importlib.reload(shioaji_login)

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
            
            print(f'Time is now {now.strftime("%H:%M:%S")}')
            print(f'Profit stop has been set to {profit_stop}')
            print(f'Loss stop has been set to {loss_stop}')
        
        pre_profit_stop = profit_stop
        pre_loss_stop = loss_stop
        
        time.sleep(1)
        
    return

def get_future_code(future_name):
    """
    Return future code based on future name
    
    :param future_name: (str)
    
    :return: future_code (str)
    """
    
    now = datetime.datetime.now().replace()
    month = now.month
    year = now.year
    first_weekday = now.replace(day=1).weekday()
    
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

def place_cover_order(quantity, action, market_price):
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
    print(f'An cover order with action={action}, quantity={quantity} has been placed! Market price: {market_price}.')
    print('***')
    
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
            p[3] = max(p[3], market_price)
        elif(p[0] == -1 and market_price != 0):
            p[3] = min(p[3], market_price)
    
    for p in positions:
        if(p[0] == 1):
            cover_action = sj.constant.Action.Sell
            if(market_price < p[2] - loss_stop):
                place_cover_order(p[1], cover_action, market_price)
                break
            if(market_price < p[3] - profit_stop):
                place_cover_order(p[1], cover_action, market_price)
                break
        elif(p[0] == -1):
            cover_action = sj.constant.Action.Buy
            if(market_price > p[2] + loss_stop):
                place_cover_order(p[1], cover_action, market_price)
                break
            if(market_price > p[3] + profit_stop):
                place_cover_order(p[1], cover_action, market_price)
                break
                
def fill_positions(deal):
    """
    :global param watch_list: (list)
    
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
    print(f'A position with type={action_text}, quantity={ori_quantity}, price={price} has been recorded!')
    print('***')
    
    if (quantity > 0):
        positions.append([action, quantity, price, price])
        
        if(action == 1):
            positions = sorted(positions, key=lambda p: p[2], reverse=False)
        else:
            positions = sorted(positions, key=lambda p: p[2], reverse=True)
            
        print('***')
        print(f'A position with type={action_text}, quantity={quantity}, price={price} has been added to the watch list!')
        print('***')
        
def place_cb(stat, msg):
    """
    Called every time an order or a deal has been detected.
    """
    
    if(stat == sj.constant.OrderState.FOrder):
        print('An order has been detected.')
        print(f'op_msg: \"{msg["operation"]["op_msg"]}\"')
    elif(stat == sj.constant.OrderState.FDeal):
        print('A deal has been detected.')
        print(f'Deal information: code:{msg["code"]}, action:{msg["action"]}, price:{msg["price"]}, quantity:{msg["quantity"]}')
        print(f'Delivery month:{msg["delivery_month"]}, security type: {msg["security_type"]}')
        fill_positions(msg)
    
    # TODO: update_status may be useful?
    #api.update_status(api.future_account)

api = shioaji_login.login()

api.set_order_callback(place_cb)


# Parsing config.json

with open('config.json') as f:
    config_data = json.load(f)
    
    intense_begin_time = datetime.datetime.strptime(config_data['intense_begin'], '%H:%M').time()
    intense_end_time = datetime.datetime.strptime(config_data['intense_end'], '%H:%M').time()
    
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

# profit_stop and loss_stop need to be initialize as None before calling stop_price_updater
profit_stop = None
loss_stop = None

stop_price_updater_thread = threading.Thread(target = stop_price_updater)
stop_price_updater_thread.start()

# Get contract
contract = api.Contracts.Futures[future_code]
try:
    if(not contract):
        raise ValueError(f'Error: contract {future_code} does not exsits.')
except ValueError as err:
    traceback.print_exc()
    
# positions is a list of list
# Each single list cotains 4 values: Position_type, quantity, price, best_price
# Position_type determine the type of positions holding. 0: Neutral, 1: Long, -1: short
positions = []

# TODO: Track price.

market_price = 0

@api.on_tick_fop_v1()
def quote_callback(exchange:sj.Exchange, tick:sj.TickFOPv1):
    market_price = tick['close']
    price_checker(market_price)

api.quote.subscribe(
    contract,
    quote_type = sj.constant.QuoteType.Tick, # or 'tick'
    version = sj.constant.QuoteVersion.v1, # or 'v1'
)
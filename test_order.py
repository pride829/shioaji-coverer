#!/usr/bin/env python
# coding: utf-8

# In[46]:


import codecs
import datetime
import importlib
import os
import json

from pathlib import Path

import shioaji as sj
import shioaji_login
importlib.reload(shioaji_login)


# In[38]:


def write_log(text):
    """
    Write into log file.
    
    :param text: (str)
    :return: None
    """

    now = datetime.datetime.now()
    path = 'test_logs'
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


# In[47]:


api = shioaji_login.login()


# In[55]:


# Get contract
contract = api.Contracts.Futures['TXFB2']

# 下單
fut_order = api.Order(
    action=sj.constant.Action.Buy, # 購買
    price=16000, # 用16000點
    quantity=1, # 買一口
    price_type=sj.constant.FuturesPriceType.LMT,
    order_type=sj.constant.FuturesOrderType.FOK, 
    octype=sj.constant.FuturesOCType.New,
    account=api.futopt_account
)

# Placing order
trade = api.place_order(contract, fut_order)

print('***')
print(f'Trade msg: {trade.status.msg}')
write_log(f'Trade msg: {trade.status.msg}')
write_log('\n')
print(repr(trade))
write_log(f'Full trade: {repr(trade)}')
print('***\n')

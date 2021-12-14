import importlib
import shioaji_login
importlib.reload(shioaji_login)
import shioaji as sj
from shioaji import TickFOPv1, Exchange
import time
import threading
from shioaji import constant
import json
from datetime import datetime


msg_test = None

class AutoStopper:
    
    def __init__(self):
        
        self.deal_list = [] #為msg的list
        self.order_list = []
        self.cover_deal_list = [] #為seqno的list
        
        #如果使用threading可以讓api完全登入之後再繼續嗎?
        '''
        thread_api = threading.Thread(
            target = shioaji_login.shioaji_login
        )
        self.api = thread_api.start()
        thread_api.join()
        '''
        self.api = shioaji_login.shioaji_login()
        
        #TODO: 讓AutoStopper可以自動獲取近月的合約
        #預設指定contract為近月小台期期貨合約
        #預設指定停損停利皆為10點
        
        self.profit_stop = 10
        self.loss_stop = 10
        self.future_name = 'MXFL1'
        
        #不能使用自動單！否則會導致程式判斷錯誤
        print("目前的系統時間為", datetime.now().strftime("%Y-%m-%d %H:%M:%S %p"))
        #從config.json之中讀取時間，停損停利點位，和合約名稱
        with open('config.json') as f:
            data = json.load(f)
            if(
                datetime.now().hour < int(data['morning_intense_hour']) 
                or
                datetime.now().hour == int(data['morning_intense_hour']) and
                datetime.now().minute < int(data['morning_intense_minute']) 
                or
                datetime.now().hour == int(data['afternoon_intense_hour']) and 
                datetime.now().minute > int(data['afternoon_intense_minute'])  
            ):
                self.profit_stop = int(data['profit_stop_intense'])
                self.loss_stop = int(data['loss_stop_intense'])
            else:
                self.profit_stop = int(data['profit_stop'])
                self.loss_stop = int(data['loss_stop'])
                
                
            self.future_name = data['future_name']
        
        print(f"將設定移動停利點位為{self.profit_stop}點。")
        print(f"將設定固定停損點位為{self.profit_stop}點。")
        
        self.contract = self.api.Contracts.Futures[self.future_name]
        
        if(not self.contract):
            print("警告：合約不存在，請確認設定檔。")
            
        self.market_price = 0
        
    def startAutoStopper(self):
        
        #更改api的order callback
        def place_cb(stat, msg):
            
            #print(msg)
            global msg_test
            msg_test = msg

            if(stat == constant.OrderState.FOrder):
                self.order_list.append(msg)
                
            elif(stat == constant.OrderState.FDeal):
                
                #Debug message
                #if(msg['seqno'] in self.cover_deal_list):
                #    print('Blocked by cover_deal_list')
                
                if(
                    msg['security_type'] == 'FUT' and
                    #API沒辦法判斷FDeal是否是程式自己送出的或者是由使用者送出的
                    #因此，必須要有self.cover_deal_list來紀錄由程式自己送出的單
                    msg['seqno'] not in self.cover_deal_list
                  ):
                    for o in self.order_list:
                        if o['order']['seqno'] == msg['seqno']:
                            if o['order']['oc_type'] != 'New':
                                print('*******Wrong type.*******')
                                return
                            
                    print(f'偵測到在價格 {msg["price"]} 的成交')
                    self.deal_list.append(msg)
                    thread_auto_stop = threading.Thread(
                        target = self.auto_stop,
                        args = (msg,)
                    )
                    thread_auto_stop.start()
        
        print(f"自動停損停利程式啟動，正在追蹤{self.future_name}的倉位...")
        
        self.api.set_order_callback(place_cb)
        
        #追蹤近月期貨價格為self.market_price
        thread_price_tracking = threading.Thread(target = self.price_tracking)
        thread_price_tracking.start()
        
    def price_tracking(self):
        
        @self.api.on_tick_fop_v1()
        def quote_callback(exchange:Exchange, tick:TickFOPv1):
            self.market_price = tick['close']

        self.api.quote.subscribe(
            self.contract,
            quote_type = sj.constant.QuoteType.Tick, # or 'tick'
            version = sj.constant.QuoteVersion.v1, # or 'v1'
        )
    
    def auto_stop(self, msg):
        
        while(self.market_price == 0):
            pass
        
        print(f'開始追蹤成交價為{msg["price"]}的倉位')
        print(f'固定停損價為 {msg["price"]-self.loss_stop}')
        action = None
        if(msg['action'] == 'Buy'):
            action = sj.constant.Action.Sell
            
            deal_price = float(msg['price'])
            max_price = deal_price
            print(type(max_price))
            high_stop = float(max_price) - float(self.profit_stop)
            low_stop = float(deal_price) - float(self.loss_stop)
            
            while(self.market_price > high_stop and self.market_price > low_stop):
                time.sleep(0.1)
                max_price = max(max_price, self.market_price)
                high_stop = max_price - self.profit_stop
            
            print(f'買單觸發停損！市價為 {self.market_price} \n停利價為 {high_stop} \n停損價為 {low_stop} ')
            
        else:
            action = sj.constant.Action.Buy
            
            deal_price = float(msg['price'])
            min_price = deal_price
            high_stop = float(deal_price) + float(self.loss_stop)
            low_stop = float(min_price) + float(self.profit_stop)
            
            while(self.market_price < high_stop and self.market_price < low_stop):
                time.sleep(0.1)
                min_price = min(min_price, self.market_price)
                low_stop = min_price + self.profit_stop
            
            print(f'賣單觸發停損！市價為 {self.market_price} \n停利價為 {low_stop} \n停損價為 {high_stop} ')
            
        #平倉
        
        fut_order = self.api.Order(
            action=action,
            price=0,
            quantity=msg['quantity'],
            price_type=sj.constant.FuturesPriceType.MKT,
            order_type=sj.constant.FuturesOrderType.FOK, 
            octype=sj.constant.FuturesOCType.Auto,
            account=self.api.futopt_account
        )
        
        #下單
        trade = self.api.place_order(self.contract, fut_order)
        
        print(f'已經送出口數為{msg["quantity"]}的平倉單！')
        self.cover_deal_list.append(trade['order']['seqno'])

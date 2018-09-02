# -*- coding: utf-8 -*-
from optopus.data_objects import (Asset, AssetType, SignalData, OrderAction,
                                  StrategyType, OptionRight)
import datetime
from optopus.optopus import Optopus


class Taco():
    def __init__(self, opt: Optopus):
        self._opt = opt
 
    def evaluate(self):
        symbol = 'SPY'
        u = Asset(symbol, AssetType.Stock)
        strike = 283
        exp = '21092018'
        strategy_id = symbol + '_' + StrategyType.SellNakedPut.value + '_' + str(strike) + '_' + exp  
        
        
        s = SignalData(asset=u, 
                       action=OrderAction.Sell, 
                       quantity=1, 
                       price=0.9, 
                       expiration=datetime.datetime.strptime(exp, "%d%m%Y").date(),
                       strike=strike,
                       right=OptionRight.Put,
                       algorithm='foo',
                       strategy=strategy_id,
                       rol='1')  
        
        self._opt.process([s])
        
    
    def manage(self):
        pass
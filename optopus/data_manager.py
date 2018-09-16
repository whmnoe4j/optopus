# -*- coding: utf-8 -*-
import copy
import datetime
import logging
from typing import Dict
from optopus.data_objects import (Asset, Strategy, Portfolio)
from optopus.computation import (assets_loop_computation,
                                 assets_vector_computation,
                                 assets_directional_assumption,
                                 portfolio_bwd)
from optopus.strategy_repository import StrategyRepository
from optopus.settings import CURRENCY, MARKET_BENCHMARK

class DataAdapter:
    pass


class DataManager():
    """
    A class used to store the data and manage the their updates

    Attributes
    ----------
    _account : Account
        the data of the broker account
    _assets : Dict[str, Asset]
        the assets we can trade
    _strategies : Dict[str, Strategy]
        the strategies grouping the positions
    _da : DataAdapter
        adapter object for ib_insyinc
    _logger: Looger
        class logger
    """
    def __init__(self,  data_adapter: DataAdapter, watch_list: dict) -> None:
        self._da = data_adapter
        self.account = None
        self.portfolio = Portfolio()
        self._assets = {code: Asset(code, asset_type, CURRENCY)
                        for code, asset_type in watch_list.items()}
        
        self._strategies = {}

        self._strategy_repository = StrategyRepository()
        self._strategies = self._strategy_repository.all_items()

        self._log = logging.getLogger(__name__)

    def update_account(self) -> None:
        self.account = self._da.get_account_values()

    def initialize_assets(self) -> None:
        """Retrieves the ids of the assets (contracts) from IB
        """
        contracts = self._da.initialize_assets(self._assets.values())
        for i in contracts:
                self._assets[i].contract = contracts[i]

    def update_current_assets(self) -> None:
        """Updates the current asset values.
        """
        ads = self._da.get_assets(self._assets.values())
        for ad in ads:
            self._assets[ad.code].current = ad

    def update_historical_assets(self) -> None:
        """Updates historical assets values
        """
        for a in self._assets.values():
            if not a.historical_is_updated():
                a.historical = self._da.get_historical(a)
                a._historical_updated = datetime.datetime.now()

    def update_historical_IV_assets(self) -> None:
        """Updates historical IV asset values
        """
        for a in self._assets.values():
            if not a.historical_IV_is_updated():
                a.historical_IV = self._da.get_historical_IV(a)
                a._historical_IV_updated = datetime.datetime.now()

    def compute(self) -> None:
        """Computes some asset measures
        """
        assets_loop_computation(self._assets)
        assets_vector_computation(self._assets, self.assets_matrix('bar_close'))
        #print({k: a.current.market_price for (k, a) in self._assets.items()})
        assets_directional_assumption(self._assets, self.assets_matrix('bar_close'))
        self.portfolio.bwd = portfolio_bwd(self._da.get_positions(),
                                           self._assets[MARKET_BENCHMARK].market_price)
        

    def assets_matrix(self, field: str) -> dict:
        """Returns a attribute from historical for every asset
        """
        d = {}
        for a in self._assets.values():
            d[a.code] = [getattr(bd, field) for bd in a._historical_data]
        return d

    def update_option_chain(self, code: str) -> None:
        """Update option chain values
        """
        a = self._assets[code]
        a._option_chain = self._da.get_optionchain(a)

    def update_strategy_options(self) -> None:
        for strategy_key, strategy in self._strategies.items():
            for leg_key, leg in strategy.legs.items():
                leg.option = self._da.get_options([leg.contract])[0]
                self._log.debug(f'Updated contract {leg.contract}')

    def check_strategy_positions(self):
        positions = self._da.get_positions()
        for strategy_key, strategy in self._strategies.items():
            strategy_positions = 0     
            for leg_key, leg in strategy.legs.items():
                try:
                    position = positions[leg.leg_id]
                    if position.ownership == leg.ownership:
                        if position.quantity >= leg.quantity:
                            position.quantity -= leg.quantity
                            strategy_positions += leg.quantity
                            if not position.quantity:
                                del positions[position.position_id]
                        else:
                            strategy_positions += position.quantity
                            self._log.warning(f'Leg {leg.leg_id} doesn\'t have enough positions')
                    else:
                        self._log.warning(f'Leg {leg.leg_id} and position ownership don\'t match')
                except KeyError as e:
                    self._log.warning(f'Leg {leg.leg_id} doesn\'t have any position')       

            if strategy_positions == sum([leg.quantity 
                                          for leg in strategy.legs.values()]) and not strategy.opened:
                strategy.opened = datetime.datetime.now()
                self.update_strategy(strategy)
                self._log.info(f'Strategy {strategy_key} opened')
            
            if not strategy_positions and strategy.opened and not strategy.closed:
                strategy.closed = datetime.datetime.now()
                self.update_strategy(strategy)
                self.delete_strategy(strategy)
                self._log.info(f'Strategy {strategy_key} closed')

        if len(positions):
            self._log.warning(f'There are excess positions')

        self._strategies = self._strategy_repository.all_items()

    def get_strategy(self, strategy_id: str) -> Strategy:
        return copy.deepcopy(self._strategies[strategy_id])

    def get_strategies(self) -> Dict[str, Strategy]:
        strategies={}
        for k, s in self._strategies.items():
            strategies[k] = self.get_strategy(k)
        return strategies

    def add_strategy(self, strategy: Strategy) -> None:
        self._strategy_repository.add(strategy)
        self._strategies[strategy.strategy_id] = copy.deepcopy(strategy)

    def update_strategy(self, strategy: Strategy) -> None:
        self._strategy_repository.update(strategy)
        self._strategies[strategy.strategy_id] = copy.deepcopy(strategy)
        self._strategies[strategy.strategy_id].updated = datetime.datetime.now()

    def delete_strategy(self, strategy: Strategy) -> None:
        self._strategy_repository.delete(strategy)

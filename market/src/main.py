# -*- coding:utf-8 -*-

"""
Market Server.

Market Server will get market data from Exchange via Websocket or REST as soon as possible, then packet market data into
MarketEvent and publish into EventCenter.

Author: HuangTao
Date:   2018/05/04
Email:  huangtao@ifclover.com
"""

import sys

from quant import const
from quant.quant import quant
from quant.config import config


def initialize():
    """Initialize Server."""

    for platform in config.markets:
        if platform == const.OKEX or platform == const.OKEX_MARGIN:
            from markets.okex import OKEx as Market
        elif platform == const.OKEX_FUTURE or platform == const.OKEX_SWAP:
            from markets.okex_ftu import OKExFuture as Market
        elif platform == const.BINANCE:
            from markets.binance import Binance as Market
        elif platform == const.BINANCE_FUTURE:
            from markets.binance_future import BinanceFuture as Market
        elif platform == const.DERIBIT:
            from markets.deribit import Deribit as Market
        elif platform == const.BITMEX:
            from markets.bitmex import Bitmex as Market
        elif platform == const.HUOBI:
            from markets.huobi import Huobi as Market
        elif platform == const.COINSUPER:
            from markets.coinsuper import CoinsuperMarket as Market
        elif platform == const.COINSUPER_PRE:
            from markets.coinsuper_pre import CoinsuperPreMarket as Market
        elif platform == const.KRAKEN:
            from markets.kraken import KrakenMarket as Market
        elif platform == const.GATE:
            from markets.gate import GateMarket as Market
        elif platform == const.GEMINI:
            from markets.gemini import GeminiMarket as Market
        elif platform == const.COINBASE_PRO:
            from markets.coinbase import CoinbaseMarket as Market
        elif platform == const.KUCOIN:
            from markets.kucoin import KucoinMarket as Market
        elif platform == const.HUOBI_FUTURE:
            from markets.huobi_future import HuobiFutureMarket as Market
        else:
            from quant.utils import logger
            logger.error("platform error! platform:", platform)
            continue
        cc = config.markets[platform]
        cc["platform"] = platform
        Market(**cc)


def main():
    config_file = sys.argv[1]  # config file, e.g. config.json.
    quant.initialize(config_file)
    initialize()
    quant.start()


if __name__ == "__main__":
    main()

# -*- coding:utf-8 -*-

"""
Asset Server.

NOTE:
    1. Asset information will be updated every 10 seconds;
    2. The newest asset information will be published to EventCenter via AssetEvent.
    3. The following is the asset data struct:
        assets
        {
            "BTC": {
                "free": 11.11,  # free currency for BTC.
                "locked": 22.22,  # locked currency for BTC.
                "total": 33.33  # total currency for BTC.
            },
            ...
        }

Author: HuangTao
Date:   2018/09/20
Email:  huangtao@ifclover.com
"""

import sys

from quant import const
from quant.quant import quant


def initialize():
    """ initialize project."""
    from quant.utils import logger
    from quant.config import config

    for item in config.accounts:
        platform = item["platform"]
        if platform == const.OKEX:
            from assets.okex import OKExAsset as AssetServer
        elif platform == const.OKEX_SWAP:
            from assets.okex_swap import OKExSwapAsset as AssetServer
        elif platform == const.OKEX_FUTURE:
            from assets.okex_future import OKExFutureAsset as AssetServer
        elif platform == const.BINANCE:
            from assets.binance import BinanceAsset as AssetServer
        elif platform == const.HUOBI:
            from assets.huobi import HuobiAsset as AssetServer
        elif platform == const.DERIBIT:
            from assets.deribit import DeribitAsset as AssetServer
        elif platform == const.BITMEX:
            from assets.bitmex import BitmexAsset as AssetServer
        elif platform == const.COINSUPER:
            from assets.coinsuper import CoinsuperAsset as AssetServer
        elif platform == const.COINSUPER_PRE:
            from assets.coinsuper_pre import CoinsuperPreAsset as AssetServer
        elif platform == const.KRAKEN:
            from assets.kraken import KrakenAsset as AssetServer
        elif platform == const.GATE:
            from assets.gate import GateAsset as AssetServer
        elif platform == const.KUCOIN:
            from assets.kucoin import KucoinAsset as AssetServer
        elif platform == const.HUOBI_FUTURE:
            from assets.huobi_future import HuobiFutureAsset as AssetServer
        else:
            logger.error("platform error! platform:", platform)
            continue
        AssetServer(**item)


def main():
    config_file = sys.argv[1]  # config file, e.g. config.json.
    quant.initialize(config_file)
    initialize()
    quant.start()


if __name__ == "__main__":
    main()

# -*— coding:utf-8 -*-

"""
Coinsuper Market Server.

Author: HuangTao
Date:   2018/11/14
Email:  huangtao@ifclover.com

NOTE:   1. Fetching market information via REST API.
        2. DO NOT config too many trade pairs in `symbols` (no more than 10), because REST API has a request limit.
"""

import asyncio

from quant import const
from quant.utils import tools
from quant.utils import logger
from quant.config import config
from quant.heartbeat import heartbeat
from quant.event import EventTrade, EventKline, EventOrderbook
from quant.platform.coinsuper import CoinsuperRestAPI


class CoinsuperMarket:
    """ Coinsuper Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `coinsuper`.
            host: HTTP request host. (default is "https://api.coinsuper.com")
            symbols: Symbol name list, e.g. BTC/USD. (Trade pair name list)
            channels: What are channels to be subscribed, only support `orderbook` / `trade` / `kline_5min` / `kline_15min`.
            orderbook_interval: The interval time to fetch a orderbook information, default is 2 seconds.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 10.
            trade_interval: The interval time to fetch a trade information, default is 5 seconds.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._host = None
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._access_key = None
        self._secret_key = None
        for item in config.accounts:
            if item["platform"] == self._platform:
                self._host = item.get("host", "https://api.coinsuper.com")
                self._access_key = item["access_key"]
                self._secret_key = item["secret_key"]
        if not self._host or not self._access_key or not self._access_key:
            logger.error("no find coinsuper account in ACCOUNTS from config file.", caller=self)
            return

        self._orderbook_interval = kwargs.get("orderbook_interval", 2)
        self._orderbook_length = kwargs.get("orderbook_length", 10)
        self._trade_interval = kwargs.get("trade_interval", 5)

        # REST API client.
        self._rest_api = CoinsuperRestAPI(self._host, self._access_key, self._secret_key)

        self._initialize()

    def _initialize(self):
        """ Initialize."""
        for channel in self._channels:
            if channel == "orderbook":
                heartbeat.register(self.do_orderbook_update, self._orderbook_interval)
            elif channel == const.MARKET_TYPE_KLINE_5M:
                heartbeat.register(self.create_kline_tasks, 60 * 5, const.MARKET_TYPE_KLINE_5M)
            elif channel == const.MARKET_TYPE_KLINE_15M:
                heartbeat.register(self.create_kline_tasks, 60 * 15, const.MARKET_TYPE_KLINE_15M)
            elif channel == "trade":
                heartbeat.register(self.do_trade_update, self._trade_interval)
            else:
                logger.error("channel error! channel:", channel, caller=self)

    async def do_orderbook_update(self, *args, **kwargs):
        """ Fetch orderbook information."""
        for symbol in self._symbols:
            result, error = await self._rest_api.get_orderbook(symbol, self._orderbook_length)
            if error:
                continue
            bids = []
            asks = []
            for item in result["asks"]:
                a = [item["limitPrice"], item["quantity"]]
                asks.append(a)
            for item in result["bids"]:
                b = [item["limitPrice"], item["quantity"]]
                bids.append(b)

            if not bids and not asks:
                logger.warn("no orderbook data", caller=self)
                continue

            if len(bids) > 0 and len(asks) > 0 and float(bids[0][0]) >= float(asks[0][0]):
                logger.warn("symbol:", symbol, "bids one is grate than asks one! asks:", asks, "bids:",
                            bids, caller=self)
                continue

            orderbook = {
                "platform": self._platform,
                "symbol": symbol,
                "asks": asks,
                "bids": bids,
                "timestamp": tools.get_cur_timestamp_ms()
            }
            EventOrderbook(**orderbook).publish()
            logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

            # await 0.1 second before next request.
            await asyncio.sleep(0.1)

    async def do_trade_update(self, *args, **kwargs):
        """ Fetch trade information."""
        for symbol in self._symbols:
            result, error = await self._rest_api.get_ticker(symbol)
            if error:
                continue
            for data in result:
                trade = {
                    "platform": self._platform,
                    "symbol": symbol,
                    "action": data["tradeType"],
                    "price": data["price"],
                    "quantity": data["volume"],
                    "timestamp": data["timestamp"]
                }
                EventTrade(**trade).publish()
                logger.info("symbol:", symbol, "trade:", trade, caller=self)

            # await 0.1 second before next request.
            await asyncio.sleep(0.1)

    async def create_kline_tasks(self, kline_type, *args, **kwargs):
        """ Create some tasks to fetch kline information

        Args:
            kline_type: Type of line, kline or kline_5m or kline_15m

        NOTE: Because of REST API request limit, we only send one request pre minute.
        """
        for index, symbol in enumerate(self._symbols):
            asyncio.get_event_loop().call_later(index, self.delay_kline_update, symbol, kline_type)

    def delay_kline_update(self, symbol, kline_type):
        """ Do kline update.
        """
        asyncio.get_event_loop().create_task(self.do_kline_update(symbol, kline_type))

    async def do_kline_update(self, symbol, kline_type):
        if kline_type == const.MARKET_TYPE_KLINE_5M:
            range_type = "5min"
        elif kline_type == const.MARKET_TYPE_KLINE_15M:
            range_type = "15min"
        else:
            return
        result, error = await self._rest_api.get_kline(symbol, 1, range_type)
        if error:
            return

        kline = {
            "platform": self._platform,
            "symbol": symbol,
            "open": "%.8f" % float(result[0]["open"]),
            "high": "%.8f" % float(result[0]["high"]),
            "low": "%.8f" % float(result[0]["low"]),
            "close": "%.8f" % float(result[0]["close"]),
            "volume": "%.8f" % float(result[0]["volume"]),
            "timestamp": result[0]["timestamp"],
            "kline_type": kline_type
        }
        EventKline(**kline).publish()
        logger.info("symbol:", symbol, "kline:", kline, caller=self)

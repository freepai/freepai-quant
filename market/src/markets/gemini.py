# -*— coding:utf-8 -*-

"""
Gemini Market Server.
https://docs.gemini.com/websocket-api/#market-data-version-2

Author: HuangTao
Date:   2019/07/25
Email:  huangtao@ifclover.com
"""

import copy

from quant.utils import tools
from quant.utils import logger
from quant.utils.web import Websocket
from quant.event import EventOrderbook
from quant.utils.decorator import async_method_locker


class GeminiMarket:
    """ Gemini Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `gemini`.
            wss: Exchange Websocket host address, default is "wss://api.gemini.com".
            symbols: Trade pair list, e.g. ["ETH/BTC"].
            channels: channel list, only `orderbook` to be enabled.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 10.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._wss = kwargs.get("wss", "wss://api.gemini.com")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_length = kwargs.get("orderbook_length", 10)

        self._orderbooks = {}  # orderbook datas {"symbol": {"bids": {"price": quantity, ...}, "asks": {...}}}
        self._symbols_map = {}  # config symbol name to raw symbol name, e.g. {"BTCUSD": "BTC/USD"}

        url = self._wss + "/v2/marketdata"
        self._ws = Websocket(url, connected_callback=self.connected_callback, process_callback=self.process)
        self._ws.initialize()

    async def connected_callback(self):
        """After create Websocket connection successfully, we will subscribing orderbook events."""
        symbols = []
        for s in self._symbols:
            t = s.replace("/", "")
            symbols.append(t)
            self._symbols_map[t] = s

        if not symbols:
            logger.warn("symbols not found in config file.", caller=self)
            return
        if not self._channels:
            logger.warn("channels not found in config file.", caller=self)
            return

        subscriptions = []
        for ch in self._channels:
            if ch == "orderbook":
                sub = {"name": "l2", "symbols": symbols}
                subscriptions.append(sub)
            else:
                logger.error("channel error! channel:", ch, caller=self)
        if subscriptions:
            msg = {
                "type": "subscribe",
                "subscriptions": subscriptions
            }
            await self._ws.send(msg)
            logger.info("subscribe orderbook success.", caller=self)

    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: Message data that received from Websocket connection.
        """
        logger.debug("msg:", msg, caller=self)

        t = msg.get("type")
        if t == "l2_updates":
            symbol = msg["symbol"]
            datas = msg["changes"]
            await self.process_orderbook_update(symbol, datas)

    @async_method_locker("process_orderbook_update")
    async def process_orderbook_update(self, symbol_raw, datas):
        """ Deal with orderbook message that updated.

        Args:
            symbol_raw: Trade pair raw name.
            datas: Newest orderbook data.
        """
        if symbol_raw not in self._symbols_map:
            return
        symbol = self._symbols_map[symbol_raw]
        if symbol not in self._orderbooks:
            self._orderbooks[symbol] = {"asks": {}, "bids": {}}

        for item in datas:
            side = item[0]
            price = float(item[1])
            quantity = float(item[2])
            if side == "sell":
                if quantity == 0:
                    if price in self._orderbooks[symbol]["asks"]:
                        self._orderbooks[symbol]["asks"].pop(price)
                else:
                    self._orderbooks[symbol]["asks"][price] = quantity
            elif side == "buy":
                if quantity == 0:
                    if price in self._orderbooks[symbol]["bids"]:
                        self._orderbooks[symbol]["bids"].pop(price)
                else:
                    self._orderbooks[symbol]["bids"][price] = quantity

        await self.publish_orderbook_event(symbol)

    async def publish_orderbook_event(self, symbol):
        """Publish OrderbookEvent."""
        ob = copy.copy(self._orderbooks[symbol])
        if not ob["asks"] or not ob["bids"]:
            logger.warn("symbol:", symbol, "asks:", ob["asks"], "bids:", ob["bids"], caller=self)
            return

        ask_keys = sorted(list(ob["asks"].keys()))
        bid_keys = sorted(list(ob["bids"].keys()), reverse=True)
        if ask_keys[0] <= bid_keys[0]:
            logger.warn("symbol:", symbol, "ask1:", ask_keys[0], "bid1:", bid_keys[0], caller=self)
            return

        # asks
        asks = []
        for k in ask_keys[:self._orderbook_length]:
            price = "%.8f" % k
            quantity = "%.8f" % ob["asks"].get(k)
            asks.append([price, quantity])

        # bids
        bids = []
        for k in bid_keys[:self._orderbook_length]:
            price = "%.8f" % k
            quantity = "%.8f" % ob["bids"].get(k)
            bids.append([price, quantity])

        # Publish OrderbookEvent.
        orderbook = {
            "platform": self._platform,
            "symbol": symbol,
            "asks": asks,
            "bids": bids,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        EventOrderbook(**orderbook).publish()
        logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

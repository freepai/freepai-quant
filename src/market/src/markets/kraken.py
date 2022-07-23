# -*— coding:utf-8 -*-

"""
Kraken Market Server.
https://www.kraken.com/en-us/features/websocket-api

Author: HuangTao
Date:   2019/07/11
Email:  huangtao@ifclover.com
"""

import copy

from quant.utils import tools
from quant.utils import logger
from quant.utils.web import Websocket
from quant.tasks import LoopRunTask, SingleTask
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.event import EventTrade, EventOrderbook
from quant.platform.kraken import KrakenRestAPI


class KrakenMarket:
    """ Kraken Market Server

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `kraken`.
            host: HTTP host, default is `https://api.kraken.com`.
            wss: Wss host, default is `wss://ws.kraken.com`.
            symbols: Symbol name list, e.g. XTB/USD. (Trade pair name list)
            channels: What are channels to be subscribed, only support `orderbook` and `trade`.
            orderbook_interval: The interval time to fetch a orderbook information, default is 2 seconds.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 10.
    """

    def __init__(self, **kwargs):
        """Initialize."""
        self._platform = kwargs["platform"]
        self._host = kwargs.get("host", "https://api.kraken.com")
        self._wss = kwargs.get("wss", "wss://ws.kraken.com")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_interval = kwargs.get("orderbook_interval", 2)
        self._orderbook_length = kwargs.get("orderbook_length", 10)

        self.heartbeat_msg = {}
        self._orderbooks = {}  # orderbook data, e.g. {"symbol": {"bids": {"price": quantity, ...}, "asks": {...}, "timestamp": 0}, ... }

        self._rest_api = KrakenRestAPI(self._host, None, None)

        url = self._wss
        self._ws = Websocket(url, connected_callback=self.connected_callback, process_callback=self.process)
        self._ws.initialize()

        # Register a loop run task to reset heartbeat message request id.
        LoopRunTask.register(self.send_heartbeat_msg, 5)

    async def connected_callback(self):
        """After create Websocket connection successfully, we will subscribing orderbook/trade/kline."""
        if not self._symbols:
            logger.warn("symbols not found in config file.", caller=self)
            return
        if not self._channels:
            logger.warn("channels not found in config file.", caller=self)
            return
        for ch in self._channels:
            if ch == "orderbook":
                # subscription = {"name": "book"}
                LoopRunTask.register(self.on_event_update_orderbook, self._orderbook_interval)
                continue
            elif ch == "trade":
                subscription = {"name": "trade"}
            # elif ch == "kline":  # TODO: something wrong from exchange server? subscribe ohlc-1 but receive ohlc-5 ?
            #     subscription = {"name": "ohlc", "interval": 1}
            else:
                logger.error("channel error:", ch, caller=self)
                continue

            d = {
                "event": "subscribe",
                "pair": self._symbols,
                "subscription": subscription
            }
            await self._ws.send(d)
            logger.info("subscribe", ch, "success.", caller=self)

    async def send_heartbeat_msg(self, *args, **kwargs):
        data = {
            "event": "ping",
            "reqid": tools.get_cur_timestamp()
        }
        if not self._ws:
            logger.error("Websocket connection not yeah!", caller=self)
            return
        await self._ws.send(data)

    async def process(self, msg):
        """ Process message that received from Websocket connection.
        """
        logger.debug("msg:", msg, caller=self)

        if not isinstance(msg, list):
            return

        if msg[-2] == "book-10":
            await self.deal_orderbook_update(msg)
        elif msg[-2] == "trade":
            await self.deal_trade_update(msg)

    @async_method_locker("deal_orderbook_update")
    async def deal_orderbook_update(self, msg):
        """ Deal with orderbook message that updated.
        """
        data = msg[1]
        symbol = msg[-1]
        if symbol not in self._symbols:
            return
        if symbol not in self._orderbooks:
            self._orderbooks[symbol] = {"asks": {}, "bids": {}, "timestamp": 0}
            a = data["as"]
            b = data["bs"]
        else:
            a = data.get("a", [])
            b = data.get("b", [])
        for item in a:
            price = float(item[0])
            quantity = float(item[1])
            if quantity == 0:
                if price in self._orderbooks[symbol]["asks"]:
                    self._orderbooks[symbol]["asks"].pop(price)
            else:
                self._orderbooks[symbol]["asks"][price] = quantity
                self._orderbooks[symbol]["timestamp"] = int(float(item[2]) * 1000)
        for item in b:
            price = float(item[0])
            quantity = float(item[1])
            if quantity == 0:
                if price in self._orderbooks[symbol]["bids"]:
                    self._orderbooks[symbol]["bids"].pop(price)
            else:
                self._orderbooks[symbol]["bids"][price] = quantity
                self._orderbooks[symbol]["timestamp"] = int(float(item[2]) * 1000)

        await self.publish_orderbook()

    async def publish_orderbook(self, *args, **kwargs):
        """ Publish OrderbookEvent.
        """
        for symbol, data in self._orderbooks.items():
            ob = copy.copy(data)
            if not ob["asks"] or not ob["bids"]:
                logger.warn("symbol:", symbol, "asks:", ob["asks"], "bids:", ob["bids"], caller=self)
                continue

            ask_keys = sorted(list(ob["asks"].keys()))
            bid_keys = sorted(list(ob["bids"].keys()), reverse=True)
            if ask_keys[0] <= bid_keys[0]:
                logger.warn("symbol:", symbol, "ask1:", ask_keys[0], "bid1:", bid_keys[0], caller=self)
                continue

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
                "timestamp": ob["timestamp"]
            }
            EventOrderbook(**orderbook).publish()
            logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

    async def deal_trade_update(self, msg):
        """ Deal with trade message that updated.
        """
        data = msg[1]
        symbol = msg[-1]
        if symbol not in self._symbols:
            return

        for item in data:
            price = "%.8f" % float(item[0])
            quantity = "%.8f" % float(item[1])
            timestamp = int(float(item[2]) * 1000)
            action = ORDER_ACTION_BUY if item[3] == "b" else ORDER_ACTION_SELL

            # Publish TradeEvent.
            trade = {
                "platform": self._platform,
                "symbol": symbol,
                "action": action,
                "price": price,
                "quantity": quantity,
                "timestamp": timestamp
            }
            EventTrade(**trade).publish()
            logger.info("symbol:", symbol, "trade:", trade, caller=self)

    async def on_event_update_orderbook(self, *args, **kwargs):
        """ Loop run to fetch orderbook information.
        """
        for symbol in self._symbols:
            SingleTask.run(self.get_newest_orderbook, symbol)

    async def get_newest_orderbook(self, symbol):
        """ Get the newest orderbook information.
        """
        result, error = await self._rest_api.get_orderbook(symbol.replace("/", ""), self._orderbook_length)
        key = list(result.keys())[0]

        asks, bids = [], []
        for item in result.get(key)["asks"]:
            asks.append(item[:2])
        for item in result.get(key)["bids"]:
            bids.append(item[:2])
        orderbook = {
            "platform": self._platform,
            "symbol": symbol,
            "asks": asks,
            "bids": bids,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        EventOrderbook(**orderbook).publish()
        logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

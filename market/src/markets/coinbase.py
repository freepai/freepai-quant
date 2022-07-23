# -*— coding:utf-8 -*-

"""
Coinbase Market Server.
https://docs.pro.coinbase.com/#websocket-feed

Author: HuangTao
Date:   2019/07/26
Email:  huangtao@ifclover.com
"""

import copy

from quant.utils import tools
from quant.utils import logger
from quant.utils.web import Websocket
from quant.event import EventOrderbook, EventTrade
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL


class CoinbaseMarket:
    """ Coinbase Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `coinbase`.
            wss: Exchange Websocket host address, default is "wss://ws-feed.pro.coinbase.com".
            symbols: Trade pair list, e.g. ["ETH/USD"].
            channels: channel list, only `orderbook` and `trade` to be enabled.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 10.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._wss = kwargs.get("wss", "wss://ws-feed.pro.coinbase.com")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_length = kwargs.get("orderbook_length", 10)

        self._orderbooks = {}  # orderbook datas {"symbol": {"bids": {"price": quantity, ...}, "asks": {...}}}
        self._symbols_map = {}  # config symbol name to raw symbol name, e.g. {"BTC-USD": "BTC/USD"}

        url = self._wss
        self._ws = Websocket(url, connected_callback=self.connected_callback, process_callback=self.process)
        self._ws.initialize()

    async def connected_callback(self):
        """ After create Websocket connection successfully, we will subscribing orderbook/trade events.
        """
        symbols = []
        for s in self._symbols:
            t = s.replace("/", "-")
            symbols.append(t)
            self._symbols_map[t] = s

        if not symbols:
            logger.warn("symbols not found in config file.", caller=self)
            return
        if not self._channels:
            logger.warn("channels not found in config file.", caller=self)
            return

        channels = []
        for ch in self._channels:
            if ch == "orderbook":
                sub = {"name": "level2", "product_ids": symbols}
                channels.append(sub)
            elif ch == "trade":
                sub = {"name": "ticker", "product_ids": symbols}
                channels.append(sub)
            else:
                logger.error("channel error! channel:", ch, caller=self)
        if channels:
            msg = {
                "type": "subscribe",
                "channels": channels
            }
            await self._ws.send(msg)
            logger.info("subscribe orderbook/trade success.", caller=self)

    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: Message data that received from Websocket connection.
        """
        logger.debug("msg:", msg, caller=self)

        t = msg.get("type")
        if t == "snapshot":
            await self.process_orderbook_snapshot(msg)
        elif t == "l2update":
            await self.process_orderbook_update(msg)
        elif t == "ticker":
            await self.process_trade(msg)

    @async_method_locker("process_orderbook_update")
    async def process_orderbook_snapshot(self, msg):
        """ Deal with orderbook snapshot message.

        Args:
            msg: Orderbook snapshot message.
        """
        symbol = msg["product_id"].replace("-", "/")
        if symbol not in self._symbols:
            return
        asks = msg.get("asks")
        bids = msg.get("bids")
        self._orderbooks[symbol] = {"asks": {}, "bids": {}, "timestamp": 0}
        for ask in asks[:200]:
            price = float(ask[0])
            quantity = float(ask[1])
            self._orderbooks[symbol]["asks"][price] = quantity
        for bid in bids[:200]:
            price = float(bid[0])
            quantity = float(bid[1])
            self._orderbooks[symbol]["bids"][price] = quantity

    @async_method_locker("process_orderbook_update")
    async def process_orderbook_update(self, msg):
        """ Deal with orderbook message that updated.

        Args:
            msg: Orderbook update message.
        """
        symbol = msg["product_id"].replace("-", "/")
        if symbol not in self._symbols:
            return

        self._orderbooks[symbol]["timestamp"] = tools.utctime_str_to_mts(msg["time"][:23] + "Z")
        for item in msg["changes"]:
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

    async def process_trade(self, msg):
        """Process trade data and publish TradeEvent."""
        symbol = msg["product_id"].replace("-", "/")
        if symbol not in self._symbols:
            return
        if not msg.get("trade_id"):  # The first ticker message received from Websocket maybe no this field, dropped.
            return
        action = ORDER_ACTION_BUY if msg.get("side") == "buy" else ORDER_ACTION_SELL
        price = "%.8f" % float(msg["price"])
        quantity = "%.8f" % float(msg["last_size"])
        timestamp = tools.utctime_str_to_mts(msg["time"][:23] + "Z")

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

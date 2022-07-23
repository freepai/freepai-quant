# -*— coding:utf-8 -*-

"""
Gate.io Market Server.
https://gateio.news/docs/websocket/index.html

Author: HuangTao
Date:   2019/07/15
Email:  huangtao@ifclover.com
"""

import copy

from quant import const
from quant.utils import tools
from quant.utils import logger
from quant.tasks import LoopRunTask
from quant.utils.web import Websocket
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.event import EventOrderbook, EventKline, EventTrade


class GateMarket:
    """ Gate.io Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `gate`.
            wss: Wss host, default is `wss://ws.gate.io`.
            symbols: Trade pair list, e.g. ["ETH/BTC"].
            channels: What are channels to be subscribed, only support `orderbook` / `trade` / `kline`.
            orderbook_length: The length of orderbook"s data to be published via OrderbookEvent, default is 10.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._wss = kwargs.get("wss", "wss://ws.gate.io")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_length = kwargs.get("orderbook_length", 10)
        self._orderbook_price_precious = kwargs.get("orderbook_price_precious", "0.00000001")

        self._request_id = 0  # unique request id for per request message.
        self._orderbooks = {}  # orderbook data, e.g. {"symbol": {"bids": {"price": quantity, ...}, "asks": {...}, "timestamp": 0}, ... }

        url = self._wss + "/v3/"
        self._ws = Websocket(url, connected_callback=self.connected_callback, process_callback=self.process)
        self._ws.initialize()
        LoopRunTask.register(self.send_heartbeat_msg, 10)

    async def connected_callback(self):
        """After create Websocket connection successfully, we will subscribing orderbook/trade/kline events."""
        if not self._symbols:
            logger.warn("symbols not found in config file.", caller=self)
            return
        if not self._channels:
            logger.warn("channels not found in config file.", caller=self)
            return
        for ch in self._channels:
            if ch == "trade":
                params = []
                for s in self._symbols:
                    params.append(s.replace("/", "_"))
                request_id = await self._generate_request_id()
                d = {"id": request_id, "method": "trades.subscribe", "params": params}
                await self._ws.send(d)
                logger.info("subscribe trade success.", caller=self)
            elif ch == "orderbook":
                await self.subscribe_orderbook()
            elif ch == "kline":
                for s in self._symbols:
                    params = [s.replace("/", "_"), 60]
                    request_id = await self._generate_request_id()
                    d = {"id": request_id, "method": "kline.subscribe", "params": params}
                    await self._ws.send(d)
                    logger.info("subscribe kline success.", caller=self)
            else:
                logger.error("channel error:", ch, caller=self)
                continue

    async def subscribe_orderbook(self):
        self._orderbooks = {}
        params = []
        for s in self._symbols:
            params.append([s.replace("/", "_"), int(self._orderbook_length), str(self._orderbook_price_precious)])
        request_id = await self._generate_request_id()
        d = {"id": request_id, "method": "depth.subscribe", "params": params}
        await self._ws.send(d)
        logger.info("subscribe orderbook success.", caller=self)

    async def unsubscribe_orderbook(self):
        request_id = await self._generate_request_id()
        d = {"id": request_id, "method": "depth.unsubscribe", "params": []}
        await self._ws.send(d)
        logger.info("unsubscribe orderbook success.", caller=self)

    async def send_heartbeat_msg(self, *args, **kwargs):
        request_id = await self._generate_request_id()
        data = {
            "id": request_id,
            "method": "server.ping",
            "params": []
        }
        if not self._ws:
            logger.error("Websocket connection not yeah!", caller=self)
            return
        await self._ws.send(data)

    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: Message data that received from Websocket connection.
        """
        logger.debug("msg:", msg, caller=self)

        if not isinstance(msg, dict):
            return

        method = msg.get("method")
        if method == "trades.update":
            await self.process_trade_update(msg["params"])
        elif method == "depth.update":
            await self.process_orderbook_update(msg["params"])
        elif method == "kline.update":
            await self.process_kline_update(msg["params"])

    async def process_trade_update(self, data):
        """ Deal with trade data, and publish trade message to EventCenter via TradeEvent.

        Args:
            data: Newest trade data.
        """
        symbol = data[0].replace("_", "/")
        for item in data[1]:
            action = ORDER_ACTION_BUY if item["type"] == "buy" else ORDER_ACTION_SELL
            price = "%.8f" % float(item["price"])
            quantity = "%.8f" % float(item["amount"])
            timestamp = int(item["time"] * 1000)

            # Publish EventTrade.
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

    @async_method_locker("process_orderbook_update")
    async def process_orderbook_update(self, data):
        """ Deal with orderbook message that updated.

        Args:
            data: Newest orderbook data.
        """
        symbol = data[2].replace("_", "/")
        if symbol not in self._symbols:
            return
        if symbol not in self._orderbooks:
            self._orderbooks[symbol] = {"asks": {}, "bids": {}, "timestamp": 0}

        for item in data[1].get("asks", []):
            price = float(item[0])
            quantity = float(item[1])
            if quantity == 0:
                if price in self._orderbooks[symbol]["asks"]:
                    self._orderbooks[symbol]["asks"].pop(price)
            else:
                self._orderbooks[symbol]["asks"][price] = quantity
        for item in data[1].get("bids", []):
            price = float(item[0])
            quantity = float(item[1])
            if quantity == 0:
                if price in self._orderbooks[symbol]["bids"]:
                    self._orderbooks[symbol]["bids"].pop(price)
            else:
                self._orderbooks[symbol]["bids"][price] = quantity
        self._orderbooks[symbol]["timestamp"] = tools.get_cur_timestamp_ms()

        await self.publish_orderbook(symbol)

    async def publish_orderbook(self, symbol):
        """ Publish OrderbookEvent.
        """
        ob = copy.copy(self._orderbooks[symbol])
        if not ob["asks"] or not ob["bids"]:
            logger.warn("symbol:", symbol, "asks:", ob["asks"], "bids:", ob["bids"], caller=self)
            return

        ask_keys = sorted(list(ob["asks"].keys()))
        bid_keys = sorted(list(ob["bids"].keys()), reverse=True)
        if ask_keys[0] <= bid_keys[0]:
            logger.warn("symbol:", symbol, "ask1:", ask_keys[0], "bid1:", bid_keys[0], caller=self)
            await self.unsubscribe_orderbook()
            await self.subscribe_orderbook()
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
            "timestamp": ob["timestamp"]
        }
        EventOrderbook(**orderbook).publish()
        logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

    async def process_kline_update(self, data):
        """ Deal with 1min kline data, and publish kline message to EventCenter via KlineEvent.

        Args:
            data: Newest kline data.
        """
        for item in data:
            timestamp = item[0] * 1000
            _open = "%.8f" % float(item[1])
            close = "%.8f" % float(item[2])
            high = "%.8f" % float(item[3])
            low = "%.8f" % float(item[4])
            volume = "%.8f" % float(item[6])
            symbol = item[-1].replace("_", "/")

            # Publish EventKline
            kline = {
                "platform": self._platform,
                "symbol": symbol,
                "open": _open,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "timestamp": timestamp,
                "kline_type": const.MARKET_TYPE_KLINE
            }
            EventKline(**kline).publish()
            logger.info("symbol:", symbol, "kline:", kline, caller=self)

    @async_method_locker("_generate_request_id")
    async def _generate_request_id(self):
        self._request_id += 1
        return self._request_id

# -*— coding:utf-8 -*-

"""
Kucoin Market Server.
https://docs.kucoin.com/#websocket-feed

Author: HuangTao
Date:   2019/08/02
Email:  huangtao@ifclover.com
"""

import copy
import asyncio

from quant.utils import tools
from quant.utils import logger
from quant.utils.web import Websocket
from quant.utils.decorator import async_method_locker
from quant.tasks import LoopRunTask, SingleTask
from quant.platform.kucoin import KucoinRestAPI
from quant.event import EventOrderbook, EventTrade
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL


class KucoinMarket:
    """ Kucoin Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `kucoin`.
            host: Exchange Websocket host address, default is "https://openapi-v2.kucoin.com".
            symbols: symbol list, OKEx Future instrument_id list.
            channels: channel list, only `orderbook` , `kline` and `trade` to be enabled.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 20.
            orderbook_interval: The interval time to fetch a orderbook information, default is 2 seconds.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._host = kwargs.get("host", "https://openapi-v2.kucoin.com")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_length = kwargs.get("orderbook_length", 20)  # only support for 20 or 100.
        self._orderbook_interval = kwargs.get("orderbook_interval", 2)

        if self._orderbook_length != 20:
            self._orderbook_length = 100

        self._request_id = 0  # Unique request id for pre request.
        self._orderbooks = {}  # Orderbook data, e.g. {"symbol": {"bids": {"price": quantity, ...}, "asks": {...}, timestamp: 123, "sequence": 123}}
        self._last_publish_ts = 0  # The latest publish timestamp for OrderbookEvent.
        self._ws = None  # Websocket object.

        # REST API client.
        self._rest_api = KucoinRestAPI(self._host, None, None, None)

        SingleTask.run(self._initialize)

    async def _initialize(self):
        """Initialize."""
        for channel in self._channels:
            if channel == "orderbook":
                LoopRunTask.register(self.do_orderbook_update, self._orderbook_interval)
            elif channel == "trade":
                # Create Websocket connection.
                success, error = await self._rest_api.get_websocket_token()
                if error:
                    logger.error("get websocket token error!", caller=self)
                    return
                url = "{}?token={}".format(success["instanceServers"][0]["endpoint"], success["token"])
                self._ws = Websocket(url, self.connected_callback, self.process)
                self._ws.initialize()
                LoopRunTask.register(self.send_heartbeat_msg, 30)

    async def connected_callback(self):
        """ After create connection to Websocket server successfully, we will subscribe orderbook/kline/trade event.
        """
        symbols = []
        for s in self._symbols:
            t = s.replace("/", "-")
            symbols.append(t)
        if not symbols:
            logger.warn("symbols not found in config file.", caller=self)
            return
        if not self._channels:
            logger.warn("channels not found in config file.", caller=self)
            return
        for ch in self._channels:
            request_id = await self.generate_request_id()
            # if ch == "orderbook":
            #     d = {
            #         "id": request_id,
            #         "type": "subscribe",
            #         "topic": "/market/level2:" + ",".join(symbols),
            #         "response": True
            #     }
            #     await self._ws.send(d)
            #     logger.info("subscribe orderbook success.", caller=self)
            if ch == "trade":
                d = {
                    "id": request_id,
                    "type": "subscribe",
                    "topic": "/market/match:" + ",".join(symbols),
                    "privateChannel": False,
                    "response": True
                }
                await self._ws.send(d)
                logger.info("subscribe trade success.", caller=self)
            else:
                logger.error("channel error! channel:", ch, caller=self)

    async def send_heartbeat_msg(self, *args, **kwargs):
        request_id = await self.generate_request_id()
        data = {
            "id": request_id,
            "type": "ping"
        }
        if not self._ws:
            logger.error("")
            return
        await self._ws.send(data)

    @async_method_locker("_generate_request_id")
    async def generate_request_id(self):
        self._request_id = tools.get_cur_timestamp_ms()
        return self._request_id

    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: Message received from Websocket connection.
        """
        logger.debug("msg:", msg, caller=self)

        topic = msg.get("topic", "")
        if "level2" in topic:
            await self.process_orderbook_update(msg["data"])
        elif "match" in topic:
            await self.process_trade_update(msg["data"])

    @async_method_locker("process")
    async def process_orderbook_update(self, data):
        """ Deal with orderbook update message.
        """
        symbol = data["symbol"].replace("-", "/")
        if symbol not in self._orderbooks:
            return

        if self._orderbooks[symbol]["sequence"] > data["sequenceStart"]:
            return

        self._orderbooks[symbol]["timestamp"] = tools.get_cur_timestamp_ms()

        for ask in data["changes"]["asks"]:
            price = float(ask[0])
            quantity = float(ask[1])
            if price == 0:
                continue
            if quantity == 0 and price in self._orderbooks[symbol]["asks"]:
                self._orderbooks[symbol]["asks"].pop(price)
            else:
                self._orderbooks[symbol]["asks"][price] = quantity

        for bid in data["changes"]["bids"]:
            price = float(bid[0])
            quantity = float(bid[1])
            if price == 0:
                continue
            if quantity == 0 and price in self._orderbooks[symbol]["bids"]:
                self._orderbooks[symbol]["bids"].pop(price)
            else:
                self._orderbooks[symbol]["bids"][price] = quantity

        if self._orderbooks[symbol]["timestamp"] - self._last_publish_ts > 1000:  # Only publish one per minute.
            self._last_publish_ts = self._orderbooks[symbol]["timestamp"]
            ob = copy.copy(self._orderbooks[symbol])
            SingleTask.run(self.publish_orderbook, symbol, ob)

    async def publish_orderbook(self, symbol, data):
        """ Publish orderbook message to EventCenter via OrderbookEvent.
        """
        if not data["asks"] or not data["bids"]:
            logger.warn("symbol:", symbol, "asks:", data["asks"], "bids:", data["bids"], caller=self)
            return

        ask_keys = sorted(list(data["asks"].keys()))
        bid_keys = sorted(list(data["bids"].keys()), reverse=True)
        if ask_keys[0] <= bid_keys[0]:
            logger.warn("symbol:", symbol, "ask1:", ask_keys[0], "bid1:", bid_keys[0], caller=self)
            return

        asks = []
        for k in ask_keys[:self._orderbook_length]:
            price = "%.8f" % k
            quantity = str(data["asks"].get(k))
            asks.append([price, quantity])

        bids = []
        for k in bid_keys[:self._orderbook_length]:
            price = "%.8f" % k
            quantity = str(data["bids"].get(k))
            bids.append([price, quantity])

        orderbook = {
            "platform": self._platform,
            "symbol": symbol,
            "asks": asks,
            "bids": bids,
            "timestamp": data["timestamp"]
        }
        EventOrderbook(**orderbook).publish()
        logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

    async def process_trade_update(self, data):
        """ Deal with trade data, and publish trade message to EventCenter via TradeEvent.
        """
        symbol = data["symbol"].replace("-", "/")
        if symbol not in self._symbols:
            return
        action = ORDER_ACTION_BUY if data["side"] == "buy" else ORDER_ACTION_SELL
        price = "%.8f" % float(data["price"])
        quantity = "%.8f" % float(data["size"])
        timestamp = int(int(data["time"]) / 1000000)

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

    async def do_orderbook_update(self, *args, **kwargs):
        """ Fetch orderbook information."""
        for symbol in self._symbols:
            result, error = await self._rest_api.get_orderbook(symbol.replace("/", "-"), self._orderbook_length)
            if error:
                continue
            orderbook = {
                "platform": self._platform,
                "symbol": symbol,
                "asks": result["asks"],
                "bids": result["bids"],
                "timestamp": result["time"]
            }
            EventOrderbook(**orderbook).publish()
            logger.info("symbol:", symbol, "orderbook:", orderbook, caller=self)

            # await 0.1 second before next request.
            await asyncio.sleep(0.1)

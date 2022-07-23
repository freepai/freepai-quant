# -*— coding:utf-8 -*-

"""
Bitmex Market Server.
https://www.bitmex.com/app/wsAPI

Author: HuangTao
Date:   2018/09/13
Email:  huangtao@ifclover.com
"""

from quant.utils import tools
from quant.utils import logger
from quant.tasks import LoopRunTask
from quant.utils.web import Websocket
from quant.const import MARKET_TYPE_KLINE
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.event import EventOrderbook, EventTrade, EventKline


class Bitmex:
    """ Bitmex Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `bitmex`.
            wss: Exchange Websocket host address, default is `wss://www.bitmex.com`.
            symbols: Symbol list.
            channels: Channel list, only `orderbook` / `trade` / `kline` to be enabled.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._wss = kwargs.get("wss", "wss://www.bitmex.com")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")

        self._c_to_s = {}  # {"channel": "symbol"}
        url = self._wss + "/realtime"
        self._ws = Websocket(url, self.connected_callback, process_callback=self.process)
        self._ws.initialize()
        LoopRunTask.register(self.send_heartbeat_message, 30)

    async def connected_callback(self):
        """After create connection to Websocket server successfully, we will subscribe orderbook/trade/kline event."""
        channels = []
        for ch in self._channels:
            if ch == "orderbook":
                for symbol in self._symbols:
                    channel = self._symbol_to_channel(symbol, "orderBook10")
                    channels.append(channel)
            if ch == "trade":
                for symbol in self._symbols:
                    channel = self._symbol_to_channel(symbol, "trade")
                    channels.append(channel)
            if ch == "kline":
                for symbol in self._symbols:
                    channel = self._symbol_to_channel(symbol, "tradeBin1m")
                    channels.append(channel)
        while channels:
            data = {
                "op": "subscribe",
                "args": channels[:10]
            }
            await self._ws.send(data)
            channels = channels[10:]
            logger.info("subscribe orderbook/trade/kline successfully.", caller=self)

    async def send_heartbeat_message(self, *args, **kwargs):
        """Send ping message to server."""
        msg = "ping"
        await self._ws.send(msg)

    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: Message data received from Websocket connection.
        """
        # logger.debug("msg:", msg, caller=self)
        if not isinstance(msg, dict):
            return
        if msg.get("error"):
            logger.error("msg:", msg, caller=self)
            return

        table = msg.get("table")
        if table == "orderBook10":
            await self.process_orderbook(msg["data"])
        elif table == "trade":
            await self.process_trade(msg["data"])
        elif table == "tradeBin1m":
            await self.process_kline(msg["data"])

    async def process_orderbook(self, data):
        """Process orderbook data and publish OrderbookEvent."""
        for item in data:
            symbol = item.get("symbol")
            orderbook = {
                "platform": self._platform,
                "symbol": symbol,
                "asks": item.get("asks"),
                "bids": item.get("bids"),
                "timestamp": tools.utctime_str_to_mts(item["timestamp"])
            }
            EventOrderbook(**orderbook).publish()
            logger.debug("symbol:", symbol, "orderbook:", orderbook, caller=self)

    async def process_kline(self, data):
        """Process kline data and publish KlineEvent."""
        for item in data:
            symbol = item["symbol"]
            kline = {
                "platform": self._platform,
                "symbol": symbol,
                "open": "%.8f" % item["open"],
                "high": "%.8f" % item["high"],
                "low": "%.8f" % item["low"],
                "close": "%.8f" % item["close"],
                "volume": str(item["volume"]),
                "timestamp": tools.utctime_str_to_mts(item["timestamp"]),
                "kline_type": MARKET_TYPE_KLINE
            }
            EventKline(**kline).publish()
            logger.debug("symbol:", symbol, "kline:", kline, caller=self)

    async def process_trade(self, data):
        """Process trade data and publish TradeEvent."""
        for item in data:
            symbol = item["symbol"]
            trade = {
                "platform": self._platform,
                "symbol": symbol,
                "action":  ORDER_ACTION_BUY if item["side"] == "Buy" else ORDER_ACTION_SELL,
                "price": "%.8f" % item["price"],
                "quantity": str(item["size"]),
                "timestamp": tools.utctime_str_to_mts(item["timestamp"])
            }
            EventTrade(**trade).publish()
            logger.debug("symbol:", symbol, "trade:", trade, caller=self)

    def _symbol_to_channel(self, symbol, channel_type):
        channel = "{channel_type}:{symbol}".format(channel_type=channel_type, symbol=symbol)
        self._c_to_s[channel] = symbol
        return channel

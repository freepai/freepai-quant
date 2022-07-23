# -*— coding:utf-8 -*-

"""
Huobi Market Server.
https://github.com/huobiapi/API_Docs

Author: HuangTao
Date:   2018/08/28
Email:  huangtao@ifclover.com
"""

import gzip
import json

from quant.utils import logger
from quant.utils.web import Websocket
from quant.const import MARKET_TYPE_KLINE
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.event import EventTrade, EventKline, EventOrderbook


class Huobi:
    """ Huobi Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `huobi`.
            wss: Exchange Websocket host address, default is "wss://api.huobi.pro".
            symbols: Trade pair list, e.g. ["ETH/BTC"].
            channels: channel list, only `orderbook`, `kline` and `trade` to be enabled.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 10.
            price_precious: The price precious, default is 8.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._wss = kwargs.get("wss", "wss://api.huobi.pro")
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_length = kwargs.get("orderbook_length", 10)
        self._price_precious = kwargs.get("price_precious", 8)

        self._c_to_s = {}  # {"channel": "symbol"}

        url = self._wss + "/ws"
        self._ws = Websocket(url, connected_callback=self.connected_callback,
                             process_binary_callback=self.process_binary)
        self._ws.initialize()

    async def connected_callback(self):
        """After create Websocket connection successfully, we will subscribing orderbook/trade/kline events."""
        for ch in self._channels:
            if ch == "kline":
                for symbol in self._symbols:
                    channel = self._symbol_to_channel(symbol, "kline")
                    if not channel:
                        continue
                    kline = {
                        "sub": channel
                    }
                    await self._ws.send(kline)
            elif ch == "orderbook":
                for symbol in self._symbols:
                    channel = self._symbol_to_channel(symbol, "depth")
                    if not channel:
                        continue
                    data = {
                        "sub": channel
                    }
                    await self._ws.send(data)
            elif ch == "trade":
                for symbol in self._symbols:
                    channel = self._symbol_to_channel(symbol, "trade")
                    if not channel:
                        continue
                    data = {
                        "sub": channel
                    }
                    await self._ws.send(data)
            else:
                logger.error("channel error! channel:", ch, caller=self)

    async def process_binary(self, msg):
        """ Process binary message that received from Websocket connection.

        Args:
            msg: Binary message received from Websocket connection.
        """
        data = json.loads(gzip.decompress(msg).decode())
        # logger.debug("data:", json.dumps(data), caller=self)
        channel = data.get("ch")
        if not channel:
            if data.get("ping"):
                hb_msg = {"pong": data.get("ping")}
                await self._ws.send(hb_msg)
            return

        symbol = self._c_to_s[channel]

        if channel.find("kline") != -1:
            d = data.get("tick")
            kline = {
                "platform": self._platform,
                "symbol": symbol,
                "open": "%.{}f".format(self._price_precious) % d["open"],
                "high": "%.{}f".format(self._price_precious) % d["high"],
                "low": "%.{}f".format(self._price_precious) % d["low"],
                "close": "%.{}f".format(self._price_precious) % d["close"],
                "volume": "%.{}f".format(self._price_precious) % d["amount"],
                "timestamp": int(data.get("ts")),
                "kline_type": MARKET_TYPE_KLINE
            }
            EventKline(**kline).publish()
            logger.debug("symbol:", symbol, "kline:", kline, caller=self)
        elif channel.find("depth") != -1:
            d = data.get("tick")
            asks, bids = [], []
            for item in d.get("asks")[:self._orderbook_length]:
                price = "%.{}f".format(self._price_precious) % item[0]
                quantity = "%.{}f".format(self._price_precious) % item[1]
                asks.append([price, quantity])
            for item in d.get("bids")[:self._orderbook_length]:
                price = "%.{}f".format(self._price_precious) % item[0]
                quantity = "%.{}f".format(self._price_precious) % item[1]
                bids.append([price, quantity])
            orderbook = {
                "platform": self._platform,
                "symbol": symbol,
                "asks": asks,
                "bids": bids,
                "timestamp": d.get("ts")
            }
            EventOrderbook(**orderbook).publish()
            logger.debug("symbol:", symbol, "orderbook:", orderbook, caller=self)
        elif channel.find("trade") != -1:
            tick = data.get("tick")
            direction = tick["data"][0].get("direction")
            price = tick["data"][0].get("price")
            quantity = tick["data"][0].get("amount")
            trade = {
                "platform": self._platform,
                "symbol": symbol,
                "action": ORDER_ACTION_BUY if direction == "buy" else ORDER_ACTION_SELL,
                "price": "%.{}f".format(self._price_precious) % price,
                "quantity": "%.{}f".format(self._price_precious) % quantity,
                "timestamp": tick.get("ts")
            }
            EventTrade(**trade).publish()
            logger.debug("symbol:", symbol, "trade:", trade, caller=self)
        else:
            logger.error("event error! msg:", msg, caller=self)

    def _symbol_to_channel(self, symbol, channel_type):
        """ Convert symbol to channel.

        Args:
            symbol: Trade pair name.
            channel_type: channel name, kline / ticker / depth.
        """
        if channel_type == "kline":
            channel = "market.{s}.kline.1min".format(s=symbol.replace("/", '').lower())
        elif channel_type == "depth":
            channel = "market.{s}.depth.step0".format(s=symbol.replace("/", '').lower())
        elif channel_type == "trade":
            channel = "market.{s}.trade.detail".format(s=symbol.replace("/", '').lower())
        else:
            logger.error("channel type error! channel type:", channel_type, calle=self)
            return None
        self._c_to_s[channel] = symbol
        return channel

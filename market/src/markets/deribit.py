# -*— coding:utf-8 -*-

"""
Deribit Market Server.
https://www.deribit.com/main#/pages/docs/api
https://www.deribit.com/api/v1/public/getinstruments

Author: HuangTao
Date:   2018/10/08
Email:  huangtao@ifclover.com
"""

import base64
import hashlib

from quant.utils import tools
from quant.utils import logger
from quant.config import config
from quant.tasks import LoopRunTask
from quant.utils.web import Websocket
from quant.event import EventOrderbook, EventTrade
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL


class Deribit:
    """ Deribit Market Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `deribit`.
            wss: Exchange Websocket host address, default is `wss://deribit.com`.
            symbols: Symbol list.
            channels: Channel list, only `orderbook` / `trade` to be enabled.
            orderbook_length: The length of orderbook's data to be published via OrderbookEvent, default is 10.
    """

    def __init__(self, **kwargs):
        self._platform = kwargs["platform"]
        self._wss = None
        self._symbols = list(set(kwargs.get("symbols")))
        self._channels = kwargs.get("channels")
        self._orderbook_length = kwargs.get("orderbook_length", 10)
        self._access_key = None
        self._secret_key = None
        self._last_msg_ts = tools.get_cur_timestamp_ms()  # 上次接收到消息的时间戳

        for item in config.accounts:
            if item["platform"] == self._platform:
                self._wss = item.get("wss", "wss://deribit.com")
                self._access_key = item["access_key"]
                self._secret_key = item["secret_key"]
        if not self._wss or not self._access_key or not self._access_key:
            logger.error("no find deribit account in ACCOUNTS from config file.", caller=self)
            return

        url = self._wss + "/ws/api/v1/"
        self._ws = Websocket(url, connected_callback=self.connected_callback, process_callback=self.process)
        self._ws.initialize()
        LoopRunTask.register(self.send_heartbeat_msg, 10)

    async def connected_callback(self):
        """After create connection to Websocket server successfully, we will subscribe orderbook/trade/kline event."""
        if not self._symbols:
            logger.warn("symbols not found in config file.", caller=self)
            return
        events = []
        for channel in self._channels:
            if channel == "orderbook":
                events.append("order_book")
            elif channel == "trade":
                events.append("trade")
        if not events:
            logger.warn("channels not found in config file.", caller=self)
            return

        nonce = tools.get_cur_timestamp_ms()
        uri = "/api/v1/private/subscribe"
        params = {
            "instrument": self._symbols,
            "event": events
        }
        sign = self.deribit_signature(nonce, uri, params, self._access_key, self._secret_key)
        data = {
            "id": "thenextquant",
            "action": uri,
            "arguments": params,
            "sig": sign
        }
        await self._ws.send(data)
        logger.info("subscribe orderbook success.", caller=self)

    async def send_heartbeat_msg(self, *args, **kwargs):
        data = {"action": "/api/v1/public/ping"}
        if not self._ws:
            logger.error("Websocket connection not yeah!", caller=self)
            return
        await self._ws.send(data)

    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: Message data received from Websocket connection.
        """
        # logger.debug("msg:", msg, caller=self)
        if tools.get_cur_timestamp_ms() <= self._last_msg_ts:
            return
        if not isinstance(msg, dict):
            return
        notifications = msg.get("notifications")
        if not notifications:
            return
        for item in notifications:
            message = item["message"]
            data = item["result"]
            if message == "order_book_event":
                await self.process_orderbook(data)
            elif message == "trade_event":
                await self.process_trade(data)

    async def process_orderbook(self, data):
        """Process orderbook data and publish OrderbookEvent."""
        symbol = data["instrument"]
        if symbol not in self._symbols:
            return
        bids = []
        for item in data["bids"][:self._orderbook_length]:
            b = [item.get("price"), item.get("quantity")]
            bids.append(b)
        asks = []
        for item in data["asks"][:self._orderbook_length]:
            a = [item.get("price"), item.get("quantity")]
            asks.append(a)
        self._last_msg_ts = tools.get_cur_timestamp_ms()
        orderbook = {
            "platform": self._platform,
            "symbol": symbol,
            "asks": asks,
            "bids": bids,
            "timestamp": self._last_msg_ts
        }
        EventOrderbook(**orderbook).publish()
        logger.debug("symbol:", symbol, "orderbook:", orderbook, caller=self)

    async def process_trade(self, data):
        """Process trade data and publish TradeEvent."""
        for item in data:
            symbol = item["instrument"]
            if symbol not in self._symbols:
                return
            trade = {
                "platform": self._platform,
                "symbol": symbol,
                "action":  ORDER_ACTION_SELL if item["direction"] == "sell" else ORDER_ACTION_BUY,
                "price": item.get("price"),
                "quantity": item.get("quantity"),
                "timestamp": item["timeStamp"]
            }
            EventTrade(**trade).publish()
            logger.info("symbol:", symbol, "trade:", trade, caller=self)

    def deribit_signature(self, nonce, uri, params, access_key, access_secret):
        """ 生成signature
        """
        sign = "_=%s&_ackey=%s&_acsec=%s&_action=%s" % (nonce, access_key, access_secret, uri)
        for key in sorted(params.keys()):
            sign += "&" + key + "=" + "".join(params[key])
        return "%s.%s.%s" % (access_key, nonce, base64.b64encode(hashlib.sha256(sign.encode()).digest()).decode())

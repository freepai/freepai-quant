# -*- coding:utf-8 -*-

"""
Deribit Asset Server.

Author: HuangTao
Date:   2019/04/20
Email:  huangtao@ifclover.com
"""

import json
import asyncio

from quant.utils import tools
from quant.utils import logger
from quant.event import EventAsset
from quant.tasks import LoopRunTask
from quant.utils.websocket import Websocket
from quant.utils.decorator import async_method_locker


class DeribitAsset(Websocket):
    """ Deribit Asset Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `deribit`.
            wss: Exchange Websocket host address, default is "wss://deribit.com".
            account: Account name. e.g. test@gmail.com.
            access_key: Account's ACCESS KEY.
            secret_key: Account's SECRETE KEY.
            update_interval: Interval time(second) for fetching asset information via Websocket, default is 10s.
    """

    def __init__(self, **kwargs):
        """Initialize object."""
        self._platform = kwargs["platform"]
        self._wss = kwargs.get("wss", "wss://deribit.com")
        self._account = kwargs["account"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._update_interval = kwargs.get("update_interval", 10)

        self._assets = {"BTC": {}, "ETH": {}}  # All currencies
        self._last_assets = {}  # last updated currencies information

        url = self._wss + "/ws/api/v2"
        super(DeribitAsset, self).__init__(url, send_hb_interval=5)

        self._query_id = 0  # Unique query id for every query message.
        self._queries = {}  # Uncompleted query message.

        self.initialize()

        # Register a loop run task to re-authentication, per 1 hour.
        LoopRunTask.register(self._do_auth, 60 * 60)

        # Register a loop run task to fetching asset information.
        LoopRunTask.register(self._publish_asset, self._update_interval)

        self._ok = False  # If websocket connection authentication successful.

    async def connected_callback(self):
        """ After websocket connection created successfully, we will send a message to server for authentication.
        """
        # Authentication
        success, error = await self._do_auth()
        if error or not success.get("access_token"):
            logger.error("Websocket connection authorized failed:", error, caller=self)
            return
        self._ok = True

        # Subscribe asset
        method = "private/subscribe"
        params = {
            "channels": [
                "user.portfolio.btc",
                "user.portfolio.eth"
            ]
        }
        _, error = await self._send_message(method, params)
        if error:
            logger.error("subscribe asset error:", error, caller=self)
        else:
            logger.info("subscribe asset success.",caller=self)

    async def _do_auth(self, *args, **kwargs):
        """ Authentication
        """
        method = "public/auth"
        params = {
            "grant_type": "client_credentials",
            "client_id": self._access_key,
            "client_secret": self._secret_key
        }
        success, error = await self._send_message(method, params)
        return success, error

    async def _send_message(self, method, params):
        """ Send message.

        Args:
            method: message method.
            params: message params.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        f = asyncio.futures.Future()
        request_id = await self._generate_query_id()
        self._queries[request_id] = f
        data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        await self.ws.send_json(data)
        logger.debug("send message:", data, caller=self)
        success, error = await f
        if error:
            logger.error("data:", data, "error:", error, caller=self)
        return success, error

    @async_method_locker("generate_query_id.locker")
    async def _generate_query_id(self):
        """ Generate a unique query id to distinguish query message.

        Returns:
            query_id: unique query id.
        """
        self._query_id += 1
        return self._query_id

    @async_method_locker("process.locker")
    async def process(self, msg):
        """ Process message that received from websocket connection.

        Args:
            msg: message that received from websocket connection.
        """
        logger.debug("msg:", json.dumps(msg), caller=self)

        # query message.
        request_id = msg.get("id")
        if request_id:
            f = self._queries.pop(request_id)
            if f.done():
                return
            success = msg.get("result")
            error = msg.get("error")
            f.set_result((success, error))

        # subscribe message.
        if msg.get("method") != "subscription":
            return
        if msg["params"]["channel"] == "user.portfolio.btc":
            name = "BTC"
            total = float(msg["params"]["data"]["equity"])
            locked = float(msg["params"]["data"]["initial_margin"])
        elif msg["params"]["channel"] == "user.portfolio.eth":
            name = "ETH"
            total = float(msg["params"]["data"]["equity"])
            locked = float(msg["params"]["data"]["initial_margin"])
        else:
            return
        self._assets[name] = {
            "free": "%.8f" % (total - locked),
            "locked": "%.8f" % locked,
            "total": "%.8f" % total
        }

    async def _publish_asset(self, *args, **kwargs):
        """ Publish asset information."""
        if self._last_assets == self._assets:
            update = False
        else:
            update = True
        self._last_assets = self._assets
        timestamp = tools.get_cur_timestamp_ms()
        EventAsset(self._platform, self._account, self._assets, timestamp, update).publish()
        logger.info("platform:", self._platform, "account:", self._account, "asset:", self._assets, caller=self)

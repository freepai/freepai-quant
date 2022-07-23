# -*- coding:utf-8 -*-

"""
OKEx Trade module.
https://www.okex.me/docs/zh/

Author: HuangTao
Date:   2019/01/19
Email:  huangtao@ifclover.com
"""

import time
import json
import copy
import hmac
import zlib
import base64
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import OKEX
from quant.order import Order
from quant.tasks import SingleTask
from quant.utils.websocket import Websocket
from quant.asset import Asset, AssetSubscribe
from quant.utils.decorator import async_method_locker
from quant.utils.http_client import AsyncHttpRequests
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("OKExRestAPI", "OKExTrade", )


class OKExRestAPI:
    """ OKEx REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        passphrase: API KEY Passphrase.
    """

    def __init__(self, host, access_key, secret_key, passphrase):
        """initialize."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key
        self._passphrase = passphrase

    async def get_user_account(self):
        """ Get account asset information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        result, error = await self.request("GET", "/api/spot/v3/accounts", auth=True)
        return result, error

    async def create_order(self, action, symbol, price, quantity, order_type=ORDER_TYPE_LIMIT, client_oid=None):
        """ Create an order.
        Args:
            action: Action type, `BUY` or `SELL`.
            symbol: Trading pair, e.g. `BTCUSDT`.
            price: Order price.
            quantity: Order quantity.
            order_type: Order type, `MARKET` or `LIMIT`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        info = {
            "side": "buy" if action == ORDER_ACTION_BUY else "sell",
            "instrument_id": symbol,
            "margin_trading": 1
        }
        if order_type == ORDER_TYPE_LIMIT:
            info["type"] = "limit"
            info["price"] = price
            info["size"] = quantity
        elif order_type == ORDER_TYPE_MARKET:
            info["type"] = "market"
            if action == ORDER_ACTION_BUY:
                info["notional"] = quantity  # buy price.
            else:
                info["size"] = quantity  # sell quantity.
        else:
            logger.error("order_type error! order_type:", order_type, caller=self)
            return None
        if client_oid:
            info["client_oid"] = client_oid
        result, error = await self.request("POST", "/api/spot/v3/orders", body=info, auth=True)
        return result, error

    async def revoke_order(self, symbol, order_no):
        """ Cancelling an unfilled order.
        Args:
            symbol: Trading pair, e.g. BTCUSDT.
            order_no: order ID.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        body = {
            "instrument_id": symbol
        }
        uri = "/api/spot/v3/cancel_orders/{order_no}".format(order_no=order_no)
        result, error = await self.request("POST", uri, body=body, auth=True)
        if error:
            return order_no, error
        if result["result"]:
            return order_no, None
        return order_no, result

    async def revoke_orders(self, symbol, order_nos):
        """ Cancelling multiple open orders with order_id，Maximum 10 orders can be cancelled at a time for each
            trading pair.

        Args:
            symbol: Trading pair, e.g. BTCUSDT.
            order_nos: order IDs.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if len(order_nos) > 10:
            logger.warn("only revoke 10 orders per request!", caller=self)
        body = [
            {
                "instrument_id": symbol,
                "order_ids": order_nos[:10]
            }
        ]
        result, error = await self.request("POST", "/api/spot/v3/cancel_batch_orders", body=body, auth=True)
        return result, error

    async def get_open_orders(self, symbol, limit=100):
        """ Get order details by order ID.

        Args:
            symbol: Trading pair, e.g. BTCUSDT.
            limit: order count to return, max is 100, default is 100.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/spot/v3/orders_pending"
        params = {
            "instrument_id": symbol,
            "limit": limit
        }
        result, error = await self.request("GET", uri, params=params, auth=True)
        return result, error

    async def get_order_status(self, symbol, order_no):
        """ Get order status.
        Args:
            symbol: Trading pair, e.g. BTCUSDT.
            order_no: order ID.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "instrument_id": symbol
        }
        uri = "/api/spot/v3/orders/{order_no}".format(order_no=order_no)
        result, error = await self.request("GET", uri, params=params, auth=True)
        return result, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """ Do HTTP request.

        Args:
            method: HTTP request method. GET, POST, DELETE, PUT.
            uri: HTTP request uri.
            params: HTTP query params.
            body:   HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if params:
            query = "&".join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
            uri += "?" + query
        url = urljoin(self._host, uri)

        if auth:
            timestamp = str(time.time()).split(".")[0] + "." + str(time.time()).split(".")[1][:3]
            if body:
                body = json.dumps(body)
            else:
                body = ""
            message = str(timestamp) + str.upper(method) + uri + str(body)
            mac = hmac.new(bytes(self._secret_key, encoding="utf8"), bytes(message, encoding="utf-8"),
                           digestmod="sha256")
            d = mac.digest()
            sign = base64.b64encode(d)

            if not headers:
                headers = {}
            headers["Content-Type"] = "application/json"
            headers["OK-ACCESS-KEY"] = self._access_key.encode().decode()
            headers["OK-ACCESS-SIGN"] = sign.decode()
            headers["OK-ACCESS-TIMESTAMP"] = str(timestamp)
            headers["OK-ACCESS-PASSPHRASE"] = self._passphrase
        _, success, error = await AsyncHttpRequests.fetch(method, url, body=body, headers=headers, timeout=10)
        return success, error


class OKExTrade(Websocket):
    """ OKEx Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default "https://www.okex.com")
        wss: Websocket address. (default "wss://real.okex.com:8443")
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
        passphrase API KEY Passphrase.
        asset_update_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `asset_update_callback` is like `async def on_asset_update_callback(asset: Asset): pass` and this
            callback function will be executed asynchronous when received AssetEvent.
        order_update_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `order_update_callback` is like `async def on_order_update_callback(order: Order): pass` and this
            callback function will be executed asynchronous when some order state updated.
        init_success_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `init_success_callback` is like `async def on_init_success_callback(success: bool, error: Error, **kwargs): pass`
            and this callback function will be executed asynchronous after Trade module object initialized successfully.
    """

    def __init__(self, **kwargs):
        """Initialize."""
        e = None
        if not kwargs.get("account"):
            e = Error("param account miss")
        if not kwargs.get("strategy"):
            e = Error("param strategy miss")
        if not kwargs.get("symbol"):
            e = Error("param symbol miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://www.okex.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://real.okex.com:8443"
        if not kwargs.get("access_key"):
            e = Error("param access_key miss")
        if not kwargs.get("secret_key"):
            e = Error("param secret_key miss")
        if not kwargs.get("passphrase"):
            e = Error("param passphrase miss")
        if e:
            logger.error(e, caller=self)
            if kwargs.get("init_success_callback"):
                SingleTask.run(kwargs["init_success_callback"], False, e)
            return

        self._account = kwargs["account"]
        self._strategy = kwargs["strategy"]
        self._platform = OKEX
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._passphrase = kwargs["passphrase"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")

        self._raw_symbol = self._symbol.replace("/", "-")
        self._order_channel = "spot/order:{symbol}".format(symbol=self._raw_symbol)

        url = self._wss + "/ws/v3"
        super(OKExTrade, self).__init__(url, send_hb_interval=5)
        self.heartbeat_msg = "ping"

        self._assets = {}  # Asset object. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order objects. e.g. {"order_no": Order, ... }

        # Initializing our REST API client.
        self._rest_api = OKExRestAPI(self._host, self._access_key, self._secret_key, self._passphrase)

        # Subscribing AssetEvent.
        if self._asset_update_callback:
            AssetSubscribe(self._platform, self._account, self.on_event_asset_update)

        self.initialize()

    @property
    def assets(self):
        return copy.copy(self._assets)

    @property
    def orders(self):
        return copy.copy(self._orders)

    @property
    def rest_api(self):
        return self._rest_api

    async def connected_callback(self):
        """After websocket connection created successfully, we will send a message to server for authentication."""
        timestamp = str(time.time()).split(".")[0] + "." + str(time.time()).split(".")[1][:3]
        message = str(timestamp) + "GET" + "/users/self/verify"
        mac = hmac.new(bytes(self._secret_key, encoding="utf8"), bytes(message, encoding="utf8"), digestmod="sha256")
        d = mac.digest()
        signature = base64.b64encode(d).decode()
        data = {
            "op": "login",
            "args": [self._access_key, self._passphrase, timestamp, signature]
        }
        await self.ws.send_json(data)

    @async_method_locker("OKExTrade.process_binary.locker")
    async def process_binary(self, raw):
        """ Process binary message that received from websocket.

        Args:
            raw: Binary message received from websocket.

        Returns:
            None.
        """
        decompress = zlib.decompressobj(-zlib.MAX_WBITS)
        msg = decompress.decompress(raw)
        msg += decompress.flush()
        msg = msg.decode()
        if msg == "pong":
            return
        logger.debug("msg:", msg, caller=self)
        msg = json.loads(msg)

        # Authorization message received.
        if msg.get("event") == "login":
            if not msg.get("success"):
                e = Error("Websocket connection authorized failed: {}".format(msg))
                logger.error(e, caller=self)
                SingleTask.run(self._init_success_callback, False, e)
                return
            logger.info("Websocket connection authorized successfully.", caller=self)

            # Fetch orders from server. (open + partially filled)
            order_infos, error = await self._rest_api.get_open_orders(self._raw_symbol)
            if error:
                e = Error("get open orders error: {}".format(msg))
                SingleTask.run(self._init_success_callback, False, e)
                return

            if len(order_infos) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            for order_info in order_infos:
                order_info["ctime"] = order_info["created_at"]
                order_info["utime"] = order_info["timestamp"]
                self._update_order(order_info)

            # Subscribe order channel.
            data = {
                "op": "subscribe",
                "args": [self._order_channel]
            }
            await self.ws.send_json(data)
            return

        # Subscribe response message received.
        if msg.get("event") == "subscribe":
            if msg.get("channel") == self._order_channel:
                SingleTask.run(self._init_success_callback, True, None)
            else:
                e = Error("subscribe order event error: {}".format(msg))
                SingleTask.run(self._init_success_callback, False, e)
            return

        # Order update message received.
        if msg.get("table") == "spot/order":
            for data in msg["data"]:
                data["ctime"] = data["timestamp"]
                data["utime"] = data["last_fill_time"]
                self._update_order(data)

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, *args, **kwargs):
        """ Create an order.

        Args:
            action: Trade direction, `BUY` or `SELL`.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            order_type: Order type, `MARKET` or `LIMIT`.

        Returns:
            order_no: Order ID if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        price = tools.float_to_str(price)
        quantity = tools.float_to_str(quantity)
        client_order_id = kwargs.get("client_order_id")
        result, error = await self._rest_api.create_order(action, self._raw_symbol, price, quantity, order_type,
                                                          client_order_id)
        if error:
            return None, error
        if not result["result"]:
            return None, result
        return result["order_id"], None

    async def revoke_order(self, *order_nos):
        """ Revoke (an) order(s).

        Args:
            order_nos: Order id list, you can set this param to 0 or multiple items. If you set 0 param, you can cancel
                all orders for this symbol(initialized in Trade object). If you set 1 param, you can cancel an order.
                If you set multiple param, you can cancel multiple orders. Do not set param length more than 100.

        Returns:
            Success or error, see bellow.

        NOTEs:
            DO NOT INPUT MORE THAT 10 ORDER NOs, you can invoke many times.
        """
        # If len(order_nos) == 0, you will cancel all orders for this symbol(initialized in Trade object).
        if len(order_nos) == 0:
            order_infos, error = await self._rest_api.get_open_orders(self._raw_symbol)
            if error:
                return False, error
            if len(order_infos) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            for order_info in order_infos:
                order_no = order_info["order_id"]
                _, error = await self._rest_api.revoke_order(self._raw_symbol, order_no)
                if error:
                    return False, error
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(self._raw_symbol, order_nos[0])
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_nos) > 1:
            success, error = [], []
            for order_no in order_nos:
                _, e = await self._rest_api.revoke_order(self._raw_symbol, order_no)
                if e:
                    error.append((order_no, e))
                else:
                    success.append(order_no)
            return success, error

    async def get_open_order_nos(self):
        """ Get open order id list.

        Args:
            None.

        Returns:
            order_nos: Open order id list, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            return None, error
        else:
            if len(success) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            order_nos = []
            for order_info in success:
                order_nos.append(order_info["order_id"])
            return order_nos, None

    def _update_order(self, order_info):
        """ Order update.

        Args:
            order_info: Order information.

        Returns:
            None.
        """
        order_no = str(order_info["order_id"])
        state = order_info["state"]
        remain = float(order_info["size"]) - float(order_info["filled_size"])
        ctime = tools.utctime_str_to_mts(order_info["ctime"])
        utime = tools.utctime_str_to_mts(order_info["utime"])

        if state == "-2":
            status = ORDER_STATUS_FAILED
        elif state == "-1":
            status = ORDER_STATUS_CANCELED
        elif state == "0":
            status = ORDER_STATUS_SUBMITTED
        elif state == "1":
            status = ORDER_STATUS_PARTIAL_FILLED
        elif state == "2":
            status = ORDER_STATUS_FILLED
        else:
            logger.error("status error! order_info:", order_info, caller=self)
            return None

        order = self._orders.get(order_no)
        if order:
            order.remain = remain
            order.status = status
            order.price = order_info["price"]
        else:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "client_order_id": order_info["client_oid"],
                "action": ORDER_ACTION_BUY if order_info["side"] == "buy" else ORDER_ACTION_SELL,
                "symbol": self._symbol,
                "price": order_info["price"],
                "quantity": order_info["size"],
                "remain": remain,
                "status": status,
                "avg_price": order_info["price"]
            }
            order = Order(**info)
            self._orders[order_no] = order
        order.ctime = ctime
        order.utime = utime

        SingleTask.run(self._order_update_callback, copy.copy(order))

        if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_no)

    async def on_event_asset_update(self, asset: Asset):
        """ Asset event data callback.

        Args:
            asset: Asset object callback from EventCenter.

        Returns:
            None.
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

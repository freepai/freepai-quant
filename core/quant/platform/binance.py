# -*- coding:utf-8 -*-

"""
Binance Trade module.
https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md

Author: HuangTao
Date:   2018/08/09
Email:  huangtao@ifclover.com
"""

import json
import copy
import hmac
import hashlib
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import BINANCE
from quant.order import Order
from quant.utils.websocket import Websocket
from quant.asset import Asset, AssetSubscribe
from quant.tasks import SingleTask, LoopRunTask
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("BinanceRestAPI", "BinanceTrade", )


class BinanceRestAPI:
    """ Binance REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
    """

    def __init__(self, host, access_key, secret_key):
        """initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_user_account(self):
        """ Get user account information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        ts = tools.get_cur_timestamp_ms()
        params = {
            "timestamp": str(ts)
        }
        success, error = await self.request("GET", "/api/v3/account", params, auth=True)
        return success, error

    async def get_server_time(self):
        """ Get server time.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self.request("GET", "/api/v1/time")
        return success, error

    async def get_exchange_info(self):
        """ Get exchange information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self.request("GET", "/api/v1/exchangeInfo")
        return success, error

    async def get_latest_ticker(self, symbol):
        """ Get latest ticker.

        Args:
            symbol: Symbol name, e.g. BTCUSDT.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "symbol": symbol
        }
        success, error = await self.request("GET", "/api/v1/ticker/24hr", params=params)
        return success, error

    async def get_orderbook(self, symbol, limit=10):
        """ Get orderbook.

        Args:
            symbol: Symbol name, e.g. BTCUSDT.
            limit: Number of results per request. (default 10)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "symbol": symbol,
            "limit": limit
        }
        success, error = await self.request("GET", "/api/v1/depth", params=params)
        return success, error

    async def create_order(self, action, symbol, price, quantity, client_order_id=None):
        """ Create an order.
        Args:
            action: Trade direction, BUY or SELL.
            symbol: Symbol name, e.g. BTCUSDT.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        info = {
            "symbol": symbol,
            "side": action,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": quantity,
            "price": price,
            "recvWindow": "5000",
            "newOrderRespType": "FULL",
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if client_order_id:
            info["newClientOrderId"] = client_order_id
        success, error = await self.request("POST", "/api/v3/order", body=info, auth=True)
        return success, error

    async def revoke_order(self, symbol, order_id, client_order_id):
        """ Cancelling an unfilled order.
        Args:
            symbol: Symbol name, e.g. BTCUSDT.
            order_id: Order id.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "symbol": symbol,
            "orderId": str(order_id),
            "origClientOrderId": client_order_id,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("DELETE", "/api/v3/order", params=params, auth=True)
        return success, error

    async def get_order_status(self, symbol, order_id, client_order_id):
        """ Get order details by order id.

        Args:
            symbol: Symbol name, e.g. BTCUSDT.
            order_id: Order id.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "symbol": symbol,
            "orderId": str(order_id),
            "origClientOrderId": client_order_id,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", "/api/v3/order", params=params, auth=True)
        return success, error

    async def get_all_orders(self, symbol):
        """ Get all account orders; active, canceled, or filled.
        Args:
            symbol: Symbol name, e.g. BTCUSDT.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", "/api/v3/allOrders", params=params, auth=True)
        return success, error

    async def get_open_orders(self, symbol):
        """ Get all open order information.
        Args:
            symbol: Symbol name, e.g. BTCUSDT.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", "/api/v3/openOrders", params=params, auth=True)
        return success, error

    async def get_listen_key(self):
        """ Get listen key, start a new user data stream

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self.request("POST", "/api/v1/userDataStream")
        return success, error

    async def put_listen_key(self, listen_key):
        """ Keepalive a user data stream to prevent a time out.

        Args:
            listen_key: Listen key.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "listenKey": listen_key
        }
        success, error = await self.request("PUT", "/api/v1/userDataStream", params=params)
        return success, error

    async def delete_listen_key(self, listen_key):
        """ Delete a listen key.

        Args:
            listen_key: Listen key.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        params = {
            "listenKey": listen_key
        }
        success, error = await self.request("DELETE", "/api/v1/userDataStream", params=params)
        return success, error

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
        url = urljoin(self._host, uri)
        data = {}
        if params:
            data.update(params)
        if body:
            data.update(body)

        if data:
            query = "&".join(["=".join([str(k), str(v)]) for k, v in data.items()])
        else:
            query = ""
        if auth and query:
            signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
            query += "&signature={s}".format(s=signature)
        if query:
            url += ("?" + query)

        if not headers:
            headers = {}
        headers["X-MBX-APIKEY"] = self._access_key
        _, success, error = await AsyncHttpRequests.fetch(method, url, headers=headers, timeout=10, verify_ssl=False)
        return success, error


class BinanceTrade(Websocket):
    """ Binance Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default "https://api.binance.com")
        wss: Websocket address. (default "wss://stream.binance.com:9443")
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
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
        """Initialize Trade module."""
        e = None
        if not kwargs.get("account"):
            e = Error("param account miss")
        if not kwargs.get("strategy"):
            e = Error("param strategy miss")
        if not kwargs.get("symbol"):
            e = Error("param symbol miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://api.binance.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://stream.binance.com:9443"
        if not kwargs.get("access_key"):
            e = Error("param access_key miss")
        if not kwargs.get("secret_key"):
            e = Error("param secret_key miss")
        if e:
            logger.error(e, caller=self)
            if kwargs.get("init_success_callback"):
                SingleTask.run(kwargs["init_success_callback"], False, e)
            return

        self._account = kwargs["account"]
        self._strategy = kwargs["strategy"]
        self._platform = BINANCE
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")

        super(BinanceTrade, self).__init__(self._wss)

        self._raw_symbol = self._symbol.replace("/", "")  # Row symbol name, same as Binance Exchange.

        self._listen_key = None  # Listen key for Websocket authentication.
        self._assets = {}  # Asset data. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order data. e.g. {order_no: order, ... }

        # Initialize our REST API client.
        self._rest_api = BinanceRestAPI(self._host, self._access_key, self._secret_key)

        # Subscribe our AssetEvent.
        if self._asset_update_callback:
            AssetSubscribe(self._platform, self._account, self.on_event_asset_update)

        # Create a loop run task to reset listen key every 30 minutes.
        LoopRunTask.register(self._reset_listen_key, 60 * 30)

        # Create a coroutine to initialize Websocket connection.
        SingleTask.run(self._init_websocket)

    @property
    def assets(self):
        return copy.copy(self._assets)

    @property
    def orders(self):
        return copy.copy(self._orders)

    @property
    def rest_api(self):
        return self._rest_api

    async def _init_websocket(self):
        """ Initialize Websocket connection.
        """
        # Get listen key first.
        success, error = await self._rest_api.get_listen_key()
        if error:
            e = Error("get listen key failed: {}".format(error))
            logger.error(e, caller=self)
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        self._listen_key = success["listenKey"]
        uri = "/ws/" + self._listen_key
        self._url = urljoin(self._wss, uri)
        self.initialize()

    async def _reset_listen_key(self, *args, **kwargs):
        """ Reset listen key.
        """
        if not self._listen_key:
            logger.error("listen key not initialized!", caller=self)
            return
        await self._rest_api.put_listen_key(self._listen_key)
        logger.info("reset listen key success!", caller=self)

    async def connected_callback(self):
        """ After websocket connection created successfully, pull back all open order information.
        """
        logger.info("Websocket connection authorized successfully.", caller=self)
        order_infos, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            e = Error("get open orders error: {}".format(error))
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        for order_info in order_infos:
            order_no = "{}_{}".format(order_info["orderId"], order_info["clientOrderId"])
            if order_info["status"] == "NEW":
                status = ORDER_STATUS_SUBMITTED
            elif order_info["status"] == "PARTIALLY_FILLED":
                status = ORDER_STATUS_PARTIAL_FILLED
            elif order_info["status"] == "FILLED":
                status = ORDER_STATUS_FILLED
            elif order_info["status"] == "CANCELED":
                status = ORDER_STATUS_CANCELED
            elif order_info["status"] == "REJECTED":
                status = ORDER_STATUS_FAILED
            elif order_info["status"] == "EXPIRED":
                status = ORDER_STATUS_FAILED
            else:
                logger.warn("unknown status:", order_info, caller=self)
                continue

            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": order_info["side"],
                "order_type": order_info["type"],
                "symbol": self._symbol,
                "price": order_info["price"],
                "quantity": order_info["origQty"],
                "remain": float(order_info["origQty"]) - float(order_info["executedQty"]),
                "status": status,
                "ctime": order_info["time"],
                "utime": order_info["updateTime"]
            }
            order = Order(**info)
            self._orders[order_no] = order
            if self._order_update_callback:
                SingleTask.run(self._order_update_callback, copy.copy(order))

        if self._init_success_callback:
            SingleTask.run(self._init_success_callback, True, None)

    async def create_order(self, action, price, quantity, *args, **kwargs):
        """ Create an order.

        Args:
            action: Trade direction, BUY or SELL.
            price: Price of each contract.
            quantity: The buying or selling quantity.

        Returns:
            order_no: Order ID if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        price = tools.float_to_str(price)
        quantity = tools.float_to_str(quantity)
        client_order_id = kwargs.get("client_order_id")
        result, error = await self._rest_api.create_order(action, self._raw_symbol, price, quantity,
                                                          client_order_id=client_order_id)
        if error:
            return None, error
        order_no = "{}_{}".format(result["orderId"], result["clientOrderId"])
        return order_no, None

    async def revoke_order(self, *order_nos):
        """ Revoke (an) order(s).

        Args:
            order_nos: Order id list, you can set this param to 0 or multiple items. If you set 0 param, you can cancel
                all orders for this symbol(initialized in Trade object). If you set 1 param, you can cancel an order.
                If you set multiple param, you can cancel multiple orders. Do not set param length more than 100.

        Returns:
            Success or error, see bellow.
        """
        # If len(order_nos) == 0, you will cancel all orders for this symbol(initialized in Trade object).
        if len(order_nos) == 0:
            order_infos, error = await self._rest_api.get_open_orders(self._raw_symbol)
            if error:
                return False, error
            for order_info in order_infos:
                _, error = await self._rest_api.revoke_order(self._raw_symbol, order_info["orderId"],
                                                             order_info["clientOrderId"])
                if error:
                    return False, error
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_nos) == 1:
            order_id, client_order_id = order_nos[0].split("_")
            success, error = await self._rest_api.revoke_order(self._raw_symbol, order_id, client_order_id)
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_nos) > 1:
            success, error = [], []
            for order_no in order_nos:
                order_id, client_order_id = order_no.split("_")
                _, e = await self._rest_api.revoke_order(self._raw_symbol, order_id, client_order_id)
                if e:
                    error.append((order_no, e))
                else:
                    success.append(order_no)
            return success, error

    async def get_open_order_nos(self):
        """ Get open order no list.
        """
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            return None, error
        else:
            order_nos = []
            for order_info in success:
                order_no = "{}_{}".format(order_info["orderId"], order_info["clientOrderId"])
                order_nos.append(order_no)
            return order_nos, None

    @async_method_locker("BinanceTrade.process.locker")
    async def process(self, msg):
        """ Process message that received from Websocket connection.

        Args:
            msg: message received from Websocket connection.
        """
        logger.debug("msg:", json.dumps(msg), caller=self)
        e = msg.get("e")
        if e == "executionReport":  # Order update.
            if msg["s"] != self._raw_symbol:
                return
            order_no = "{}_{}".format(msg["i"], msg["c"])
            if msg["X"] == "NEW":
                status = ORDER_STATUS_SUBMITTED
            elif msg["X"] == "PARTIALLY_FILLED":
                status = ORDER_STATUS_PARTIAL_FILLED
            elif msg["X"] == "FILLED":
                status = ORDER_STATUS_FILLED
            elif msg["X"] == "CANCELED":
                status = ORDER_STATUS_CANCELED
            elif msg["X"] == "REJECTED":
                status = ORDER_STATUS_FAILED
            elif msg["X"] == "EXPIRED":
                status = ORDER_STATUS_FAILED
            else:
                logger.warn("unknown status:", msg, caller=self)
                return
            order = self._orders.get(order_no)
            if not order:
                info = {
                    "platform": self._platform,
                    "account": self._account,
                    "strategy": self._strategy,
                    "order_no": order_no,
                    "client_order_id": msg["c"],
                    "action": msg["S"],
                    "order_type": msg["o"],
                    "symbol": self._symbol,
                    "price": msg["p"],
                    "quantity": msg["q"],
                    "ctime": msg["O"]
                }
                order = Order(**info)
                self._orders[order_no] = order
            order.remain = float(msg["q"]) - float(msg["z"])
            order.status = status
            order.utime = msg["T"]
            if self._order_update_callback:
                SingleTask.run(self._order_update_callback, copy.copy(order))

    async def on_event_asset_update(self, asset: Asset):
        """ Asset data update callback.

        Args:
            asset: Asset object.
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

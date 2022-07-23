# -*- coding:utf-8 -*-

"""
Gate.io Trade module.
https://gateio.news/api2#spot

Author: HuangTao
Date:   2019/07/15
Email:  huangtao@ifclover.com
"""

import copy
import hmac
import hashlib
import urllib
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import logger
from quant.const import GATE
from quant.order import Order
from quant.asset import Asset, AssetSubscribe
from quant.tasks import SingleTask, LoopRunTask
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_TYPE_LIMIT, ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("GateRestAPI", "GateTrade", )


class GateRestAPI:
    """ Gate.io REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
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
        uri = "/api2/1/private/balances"
        success, error = await self.request("POST", uri)
        return success, error

    async def create_order(self, action, symbol, price, quantity):
        """ Create an order.
        Args:
            action: Trade direction, BUY or SELL.
            symbol: Symbol name, e.g. ltc_btc.
            price: Price of each contract.
            quantity: The buying or selling quantity.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if action == ORDER_ACTION_BUY:
            uri = "/api2/1/private/buy"
        elif action == ORDER_ACTION_SELL:
            uri = "/api2/1/private/sell"
        else:
            return None, "action error"
        data = {
            "currencyPair": symbol,
            "rate": price,
            "amount": quantity
        }
        success, error = await self.request("POST", uri, data)
        return success, error

    async def revoke_order(self, symbol, order_no):
        """ Cancelling an unfilled order.
        Args:
            symbol: Symbol name, e.g. ltc_btc.
            order_no: Order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api2/1/private/cancelOrder"

        data = {
            "currencyPair": symbol,
            "orderNumber": order_no
        }
        success, error = await self.request("POST", uri, data)
        return success, error

    async def revoke_orders(self, symbol, order_nos):
        """ Cancelling multiple unfilled orders.
        Args:
            symbol: Symbol name, e.g. ltc_btc.
            order_nos: Order id list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api2/1/private/cancelOrders"
        orders_json = []
        for order_no in order_nos:
            orders_json.append({"currencyPair": symbol, "orderNumber": order_no})

        data = {
            "orders_json": orders_json
        }
        success, error = await self.request("POST", uri, data)
        return success, error

    async def revoke_orders_all(self, symbol, order_type=-1):
        """ Cancelling all unfilled orders.
        Args:
            symbol: Symbol name, e.g. ltc_btc.
            order_type: Order type (0: sell,1: buy,-1: unlimited).

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api2/1/private/cancelAllOrders"
        data = {
            "currencyPair": symbol,
            "type": order_type
        }
        success, error = await self.request("POST", uri, data)
        return success, error

    async def get_order_status(self, symbol, order_no):
        """ Get order details by order id.

        Args:
            symbol: Symbol name, e.g. ltc_btc.
            order_no: Order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api2/1/private/getOrder"
        data = {
            "currencyPair": symbol,
            "orderNumber": order_no
        }
        success, error = await self.request("POST", uri, data)
        return success, error

    async def get_open_orders(self, symbol):
        """ Get all open order information.
        Args:
            symbol: Symbol name, e.g. ltc_btc.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api2/1/private/openOrders"
        body = {
            "currencyPair": symbol
        }
        success, error = await self.request("POST", uri, body)
        return success, error

    async def request(self, method, uri, body=None):
        """ Do HTTP request.

        Args:
            method: HTTP request method. GET, POST, DELETE, PUT.
            uri: HTTP request uri.
            body:   HTTP request body.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        if body:
            query = "&".join(["=".join([str(k), str(v)]) for k, v in body.items()])
        else:
            query = ""
        signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha512).hexdigest()
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "KEY": self._access_key,
            "SIGN": signature
        }
        b = urllib.parse.urlencode(body) if body else ""
        _, success, error = await AsyncHttpRequests.fetch(method, url, body=b, headers=headers, timeout=10)
        if error:
            return None, error
        if not success.get("result"):
            return None, success
        return success, None


class GateTrade:
    """ Gate.io Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default is "https://api.gateio.co")
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
        check_order_interval: The interval time(seconds) for loop run task to check order status. (default is 2 seconds)
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
            kwargs["host"] = "https://api.gateio.co"
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
        self._platform = GATE
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")
        self._check_order_interval = kwargs.get("check_order_interval", 2)

        self._raw_symbol = self._symbol.replace("/", "_").lower()  # Raw symbol name for Exchange platform.

        self._assets = {}  # Asset information. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order details. e.g. {order_no: order-object, ... }

        # Initialize our REST API client.
        self._rest_api = GateRestAPI(self._host, self._access_key, self._secret_key)

        # Create a loop run task to check order status.
        LoopRunTask.register(self._check_order_update, self._check_order_interval)

        # Subscribe asset event.
        if self._asset_update_callback:
            AssetSubscribe(self._platform, self._account, self.on_event_asset_update)

        SingleTask.run(self._initialize)

    @property
    def assets(self):
        return copy.copy(self._assets)

    @property
    def orders(self):
        return copy.copy(self._orders)

    @property
    def rest_api(self):
        return self._rest_api

    async def _initialize(self):
        """ Initialize. fetch all open order information."""
        result, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            e = Error("get open order nos failed: {}".format(error))
            logger.error(e, caller=self)
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        for order_info in result["orders"]:
            await self._update_order(order_info)
        if self._init_success_callback:
            SingleTask.run(self._init_success_callback, True, None)

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, *args, **kwargs):
        """ Create an order.

        Args:
            action: Trade direction, BUY or SELL.
            price: Price of order.
            quantity: The buying or selling quantity.
            order_type: order type, MARKET or LIMIT.

        Returns:
            order_no: Order ID if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self._rest_api.create_order(action, self._raw_symbol, price, quantity)
        if error:
            return None, error
        if not success["result"]:
            return None, success
        order_no = str(success["orderNumber"])
        infos = {
            "account": self._account,
            "platform": self._platform,
            "strategy": self._strategy,
            "order_no": order_no,
            "symbol": self._symbol,
            "action": action,
            "price": price,
            "quantity": quantity,
            "order_type": order_type
        }
        order = Order(**infos)
        self._orders[order_no] = order
        if self._order_update_callback:
            SingleTask.run(self._order_update_callback, copy.copy(order))
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
            success, error = await self._rest_api.revoke_orders_all(self._raw_symbol)
            if error:
                return False, error
            if not success["result"]:
                return False, success
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(self._raw_symbol, order_nos[0])
            if error:
                return order_nos[0], error
            if not success["result"]:
                return False, success
            else:
                return order_nos[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_nos) > 1:
            success, error = await self._rest_api.revoke_orders(self._raw_symbol, order_nos)
            if error:
                return False, error
            if not success["result"]:
                return False, success
            return True, None

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
            return False, error
        if not success["result"]:
            return False, success
        order_nos = []
        for order_info in success["orders"]:
            order_nos.append(str(order_info["orderNumber"]))
        return order_nos, None

    async def _check_order_update(self, *args, **kwargs):
        """ Loop run task for check order status.
        """
        order_nos = list(self._orders.keys())
        if not order_nos:
            return
        for order_no in order_nos:
            success, error = await self._rest_api.get_order_status(self._raw_symbol, order_no)
            if error or not success["result"]:
                return
            await self._update_order(success["order"])

    @async_method_locker("GateTrade.order.locker")
    async def _update_order(self, order_info):
        """ Update order object.

        Args:
            order_info: Order information.
        """
        if not order_info:
            return
        status_updated = False
        order_no = str(order_info["orderNumber"])
        state = order_info["status"]

        order = self._orders.get(order_no)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": ORDER_ACTION_BUY if order_info["type"] == "buy" else ORDER_ACTION_SELL,
                "symbol": self._symbol,
                "price": order_info["rate"],
                "quantity": order_info["amount"],
                "remain": order_info["amount"],
                "avg_price": order_info["filledRate"]
            }
            order = Order(**info)
            self._orders[order_no] = order

        if state == "open":
            filled_amount = float(order_info["filledAmount"])
            if filled_amount == 0:
                state = ORDER_STATUS_SUBMITTED
                if order.status != state:
                    order.status = ORDER_STATUS_SUBMITTED
                    status_updated = True
            else:
                remain = float(order.quantity) - filled_amount
                if order.remain != remain:
                    order.status = ORDER_STATUS_PARTIAL_FILLED
                    order.remain = remain
                    status_updated = True
        elif state == "closed":
            order.status = ORDER_STATUS_FILLED
            order.remain = 0
            status_updated = True
        elif state == "cancelled":
            order.status = ORDER_STATUS_CANCELED
            filled_amount = float(order_info["filledAmount"])
            remain = float(order.quantity) - filled_amount
            if order.remain != remain:
                order.remain = remain
            status_updated = True
        else:
            logger.warn("state error! order_info:", order_info, caller=self)
            return

        if status_updated:
            order.avg_price = order_info["filledRate"]
            order.ctime = int(order_info["timestamp"] * 1000)
            order.utime = int(order_info["timestamp"] * 1000)
            if self._order_update_callback:
                SingleTask.run(self._order_update_callback, copy.copy(order))

        # Delete order that already completed.
        if order.status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_no)

    async def on_event_asset_update(self, asset: Asset):
        """ Asset update callback.

        Args:
            asset: Asset object.
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

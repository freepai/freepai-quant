# -*- coding:utf-8 -*-

"""
Kucoin Trade module.
https://docs.kucoin.com

Author: HuangTao
Date:   2019/08/01
Email:  huangtao@ifclover.com
"""

import json
import copy
import hmac
import base64
import hashlib
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import KUCOIN
from quant.order import Order
from quant.asset import Asset, AssetSubscribe
from quant.tasks import SingleTask, LoopRunTask
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED, ORDER_STATUS_NONE


__all__ = ("KucoinRestAPI", "KucoinTrade", )


class KucoinRestAPI:
    """ Kucoin REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account"s ACCESS KEY.
        secret_key: Account"s SECRET KEY.
        passphrase: API KEY passphrase.
    """

    def __init__(self, host, access_key, secret_key, passphrase):
        """initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key
        self._passphrase = passphrase

    async def get_sub_users(self):
        """Get the user info of all sub-users via this interface.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/sub/user"
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def get_accounts(self, account_type=None, currency=None):
        """Get a list of accounts.

        Args:
           account_type: Account type, main or trade.
           currency: Currency name, e.g. BTC, ETH ...

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/accounts"
        params = {}
        if account_type:
            params["type"] = account_type
        if currency:
            params["currency"] = currency
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_account(self, account_id):
        """Information for a single account.

        Args:
           account_id: Account id.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/accounts/{}".format(account_id)
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def create_account(self, account_type, currency):
        """Create a account.

        Args:
           account_type: Account type, main or trade.
           currency: Currency name, e.g. BTC, ETH ...

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/accounts"
        body = {
            "type": account_type,
            "currency": currency
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def create_order(self, client_id, side, symbol, order_type, price, size):
        """ Add standard order.

        Args:
            client_id: Unique order id selected by you to identify your order.
            side: Trade side, buy or sell.
            symbol: A valid trading symbol code. e.g. ETH-BTC.
            order_type: Order type, limit or market (default is limit).
            price: Price per base currency.
            size: Amount of base currency to buy or sell.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/orders"
        body = {
            "clientOid": client_id,
            "side": side,
            "symbol": symbol,
            "type": order_type,
            "price": price,
            "size": size
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def revoke_order(self, order_id):
        """ Cancel a previously placed order.

        Args:
            order_id: Order ID, unique identifier of an order.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/orders/{}".format(order_id)
        success, error = await self.request("DELETE", uri, auth=True)
        return success, error

    async def revoke_orders_all(self, symbol=None):
        """ Attempt to cancel all open orders. The response is a list of ids of the canceled orders.

        Args:
            symbol: A valid trading symbol code. e.g. ETH-BTC.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/orders"
        params = {}
        if symbol:
            params["symbol"] = symbol
        success, error = await self.request("DELETE", uri, params=params, auth=True)
        return success, error

    async def get_order_list(self, status="active", symbol=None, order_type=None, start=None, end=None):
        """ Get order information list.

        Args:
            status: Only list orders with a specific status, `active` or `done`, default is `active`.
            symbol: A valid trading symbol code. e.g. ETH-BTC.
            order_type: Order type, limit, market, limit_stop or market_stop.
            start: Start time. Unix timestamp calculated in milliseconds will return only items which were created
                after the start time.
            end: End time. Unix timestamp calculated in milliseconds will return only items which were created
                before the end time.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/orders"
        params = {"status": status}
        if symbol:
            params["symbol"] = symbol
        if order_type:
            params["type"] = order_type
        if start:
            params["startAt"] = start
        if end:
            params["endAt"] = end
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_order_detail(self, order_id):
        """ Get a single order by order ID.

        Args:
            order_id: Order ID, unique identifier of an order.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        uri = "/api/v1/orders/{}".format(order_id)
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def get_websocket_token(self, private=False):
        """ Get a Websocket token from server.

        Args:
            private: If a private token, default is False.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        if private:
            uri = "/api/v1/bullet-private"
            success, error = await self.request("POST", uri, auth=True)
        else:
            uri = "/api/v1/bullet-public"
            success, error = await self.request("POST", uri)
        return success, error

    async def get_orderbook(self, symbol, count=20):
        """ Get orderbook information.

        Args:
            symbol: A valid trading symbol code. e.g. ETH-BTC.
            count: Orderbook length, only support 20 or 100.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        if count == 20:
            uri = "/api/v1/market/orderbook/level2_20?symbol={}".format(symbol)
        else:
            uri = "/api/v2/market/orderbook/level2_100?symbol={}".format(symbol)
        success, error = await self.request("GET", uri)
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
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        if params:
            query = "&".join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
            uri += "?" + query
        url = urljoin(self._host, uri)
        if auth:
            if not headers:
                headers = {}
            timestamp = str(tools.get_cur_timestamp_ms())
            signature = self._generate_signature(timestamp, method, uri, body)
            headers["KC-API-KEY"] = self._access_key
            headers["KC-API-SIGN"] = signature
            headers["KC-API-TIMESTAMP"] = timestamp
            headers["KC-API-PASSPHRASE"] = self._passphrase
        _, success, error = await AsyncHttpRequests.fetch(method, url, data=body, headers=headers, timeout=10)
        if error:
            return None, error
        if success["code"] != "200000":
            return None, success
        return success["data"], error

    def _generate_signature(self, nonce, method, path, data):
        """Generate the call signature."""
        data = json.dumps(data) if data else ""
        sig_str = "{}{}{}{}".format(nonce, method, path, data)
        m = hmac.new(self._secret_key.encode("utf-8"), sig_str.encode("utf-8"), hashlib.sha256)
        return base64.b64encode(m.digest()).decode("utf-8")


class KucoinTrade:
    """ Kucoin Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default is "https://openapi-v2.kucoin.com")
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        passphrase: API KEY passphrase.
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
            kwargs["host"] = "https://openapi-v2.kucoin.com"
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
        self._platform = KUCOIN
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._passphrase = kwargs["passphrase"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")
        self._check_order_interval = kwargs.get("check_order_interval", 2)

        self._raw_symbol = self._symbol.replace("/", "-")  # Raw symbol name.

        self._assets = {}  # Asset information. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order details. e.g. {order_no: order-object, ... }

        # Initialize our REST API client.
        self._rest_api = KucoinRestAPI(self._host, self._access_key, self._secret_key, self._passphrase)

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
        result, error = await self._rest_api.get_order_list(symbol=self._raw_symbol)
        if error:
            e = Error("get open order nos failed: {}".format(error))
            logger.error(e, caller=self)
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        for item in result["items"]:
            if item["symbol"] != self._raw_symbol:
                continue
            await self._update_order(item)
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
        if action == ORDER_ACTION_BUY:
            action_type = "buy"
        elif action == ORDER_ACTION_SELL:
            action_type = "sell"
        else:
            return None, "action error"
        if order_type == ORDER_TYPE_MARKET:
            order_type_2 = "market"
        elif order_type == ORDER_TYPE_LIMIT:
            order_type_2 = "limit"
        else:
            return None, "order_type error"

        client_id = tools.get_uuid1()
        price = tools.float_to_str(price)
        quantity = tools.float_to_str(quantity)
        success, error = await self._rest_api.create_order(client_id, action_type, self._raw_symbol, order_type_2,
                                                           price, quantity)
        if error:
            return None, error
        order_no = success["orderId"]
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
            _, error = await self._rest_api.revoke_orders_all(self._raw_symbol)
            if error:
                return False, error
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(order_nos[0])
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_nos) > 1:
            s, e, = [], []
            for order_no in order_nos:
                success, error = await self._rest_api.revoke_order(order_no)
                if error:
                    e.append(error)
                else:
                    s.append(order_no)
            return s, e

    async def get_open_order_nos(self):
        """ Get open order id list.

        Args:
            None.

        Returns:
            order_nos: Open order id list, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        result, error = await self._rest_api.get_order_list(symbol=self._raw_symbol)
        if error:
            return False, error
        order_nos = []
        for item in result["items"]:
            if item["symbol"] != self._raw_symbol:
                continue
            order_nos.append(item["id"])
        return order_nos, None

    async def _check_order_update(self, *args, **kwargs):
        """ Loop run task for check order status.
        """
        order_nos = list(self._orders.keys())
        if not order_nos:
            return
        for order_no in order_nos:
            success, error = await self._rest_api.get_order_detail(order_no)
            if error:
                return
            await self._update_order(success)

    @async_method_locker("KucoinTrade.order.locker")
    async def _update_order(self, order_info):
        """ Update order object.

        Args:
            order_info: Order information.
        """
        if not order_info:
            return

        order_no = order_info["id"]
        size = float(order_info["size"])
        deal_size = float(order_info["dealSize"])
        order = self._orders.get(order_no)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": ORDER_ACTION_BUY if order_info["side"] == "buy" else ORDER_ACTION_SELL,
                "symbol": self._symbol,
                "price": order_info["price"],
                "quantity": order_info["size"],
                "remain": order_info["size"],
                "avg_price": order_info["price"]
            }
            order = Order(**info)
            self._orders[order_no] = order

        if order_info["isActive"]:
            if size == deal_size:
                status = ORDER_STATUS_SUBMITTED
            else:
                status = ORDER_STATUS_PARTIAL_FILLED
        else:
            if size == deal_size:
                status = ORDER_STATUS_FILLED
            else:
                status = ORDER_STATUS_CANCELED

        if status != order.status:
            order.status = status
            order.remain = size - deal_size
            order.ctime = order_info["createdAt"]
            order.utime = tools.get_cur_timestamp_ms()
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

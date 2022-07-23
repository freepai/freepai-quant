# -*- coding:utf-8 -*-

"""
Coinsuper Premium Trade Module
https://premium.coinsuper.com/api/docs/v1/api_en.html

Author: HuangTao
Date:   2019/07/18
Email:  huangtao@ifclover.com
"""

import copy
import hashlib
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import COINSUPER_PRE
from quant.order import Order
from quant.asset import Asset, AssetSubscribe
from quant.tasks import SingleTask, LoopRunTask
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("CoinsuperPreRestAPI", "CoinsuperPreTrade", )


class CoinsuperPreRestAPI:
    """ Coinsuper Premium Trade module.

    Attributes:
        host: HTTP request host.
        access_key: Account"s ACCESS KEY.
        secret_key: Account"s SECRET KEY.
    """

    def __init__(self, host, access_key, secret_key):
        """initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_user_account(self):
        """ Get user account information.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        data = {}
        success, error = await self.request("/api/v1/asset/userAssetInfo", data)
        return success, error

    async def create_order(self, action, symbol, price, quantity, order_type=ORDER_TYPE_LIMIT):
        """ Create an order.

        Args:
            action: Type of order (BUY/SELL).
            symbol: Trade pair. e.g. ETH/BTC.
            price: Price of order.
            quantity: Order volume in lots.
            order_type: order type (MARKET/LIMIT).

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        if action == ORDER_ACTION_BUY:
            url = "/api/v1/order/buy"
        elif action == ORDER_ACTION_SELL:
            url = "/api/v1/order/sell"
        else:
            return None, "action error"
        if order_type == ORDER_TYPE_LIMIT:
            data = {
                "orderType": "LMT",
                "symbol": symbol,
                "priceLimit": price,
                "quantity": quantity,
                "amount": 0
            }
        elif order_type == ORDER_TYPE_MARKET:
            data = {
                "orderType": "MKT",
                "symbol": symbol,
                "priceLimit": 0,
                "quantity": 0,
                "amount": quantity
            }
        else:
            return None, "order_type error"
        success, error = await self.request(url, data)
        return success, error

    async def revoke_order(self, order_no):
        """ Cancelling an unfilled order.
        Args:
            order_no: Order ID.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "orderNo": order_no
        }
        success, error = await self.request("/api/v1/order/cancel", data)
        return success, error

    async def revoke_orders(self, order_nos):
        """ Cancelling multiple open orders with order_no list.

        Args:
            order_nos: Order ID list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "orderNoList": ",".join(order_nos)
        }
        success, error = await self.request("/api/v1/order/batchCancel", data)
        return success, error

    async def get_order_list(self, order_nos):
        """ Get multiple orders information.

        Args:
            order_nos: Order ID list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "orderNoList": ",".join(order_nos)
        }
        success, error = await self.request("/api/v1/order/list", data)
        return success, error

    async def get_order_details(self, order_nos):
        """ Get multiple orders details, including trade information.

        Args:
            order_nos: Order ID list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "orderNoList": ",".join(order_nos)
        }
        success, error = await self.request("/api/v1/order/details", data)
        return success, error

    async def get_open_order_nos(self, symbol=None, num=1000):
        """ Get open order id list, max length is 1000.

        Args:
            symbol: Trade pair, e.g. ETH/BTC.
            num: The max length to fetch, default is 1000, max length is 1000.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "num": num
        }
        if symbol:
            data["symbol"] = symbol
        success, error = await self.request("/api/v1/order/openList", data)
        return success, error

    async def get_kline(self, symbol, num=300, _range="5min"):
        """ Get kline information.

        Args:
            symbol: Trade pair, e.g. ETH/BTC.
            num: The max length to fetch, default is 300.
            _range: Range of kline, default is `5min`, allow 5min, 15min , 30min, 1hour, 6hour, 12hour, 1day.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "symbol": symbol,
            "num": num,
            "range": _range
        }
        success, error = await self.request("/api/v1/market/kline", data)
        return success, error

    async def get_ticker(self, symbol):
        """ Get ticker information.

        Args:
            symbol: Trade pair, e.g. ETH/BTC.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "symbol": symbol
        }
        success, error = await self.request("/api/v1/market/tickers", data)
        return success, error

    async def get_orderbook(self, symbol, length=10):
        """ Get orderbook information.

        Args:
            symbol: Trade pair, e.g. ETH/BTC.
            length: Number of results to return, default is 10.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        data = {
            "symbol": symbol,
            "num": length
        }
        success, error = await self.request("/api/v1/market/orderBook", data)
        return success, error

    async def request(self, uri, data):
        """ Do HTTP request.

        Args:
            uri: HTTP request uri.
            data:   HTTP request body.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        timestamp = tools.get_cur_timestamp()
        data["accesskey"] = self._access_key
        data["secretkey"] = self._secret_key
        data["timestamp"] = timestamp
        sign = "&".join(["{}={}".format(k, data[k]) for k in sorted(data.keys())])
        md5_str = hashlib.md5(sign.encode("utf8")).hexdigest()
        del data["secretkey"]
        del data["accesskey"]
        del data["timestamp"]
        body = {
            "common": {
                "accesskey": self._access_key,
                "timestamp": timestamp,
                "sign": md5_str
            },
            "data": data
        }
        trace_id = md5_str[:16]  # A 16th length of random string.
        headers = {
            "X-B3-Traceid": trace_id,
            "X-B3-Spanid": trace_id
        }
        _, success, error = await AsyncHttpRequests.fetch("POST", url, data=body, headers=headers, timeout=10)
        if error:
            return None, error
        if str(success.get("code")) != "1000":
            return None, success
        return success["data"]["result"], None


class CoinsuperPreTrade:
    """ Coinsuper Premium Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default is "https://api-rest.premium.coinsuper.com")
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
            kwargs["host"] = "https://api-rest.premium.coinsuper.com"
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
        self._platform = COINSUPER_PRE
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")
        self._check_order_interval = kwargs.get("check_order_interval", 2)

        self._raw_symbol = self._symbol  # Row symbol name for Exchange platform.

        self._assets = {}  # Asset information. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order details. e.g. {order_no: order-object, ... }

        # Initialize our REST API client.
        self._rest_api = CoinsuperPreRestAPI(self._host, self._access_key, self._secret_key)

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
        """ Initialize of Fetching open orders information.
        """
        order_nos, error = await self._rest_api.get_open_order_nos(self._raw_symbol)
        if error:
            e = Error("get open order nos failed: {}".format(error))
            logger.error(e, caller=self)
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        while order_nos:
            nos = order_nos[:50]
            order_nos = order_nos[50:]
            success, error = await self._rest_api.get_order_list(nos)
            if error:
                e = Error("get order infos failed: {}".format(error))
                logger.error(e, caller=self)
                if self._init_success_callback:
                    SingleTask.run(self._init_success_callback, False, e)
                return
            for order_info in success:
                await self._update_order(order_info)
        if self._init_success_callback:
            SingleTask.run(self._init_success_callback, True, None)

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, *args, **kwargs):
        """ Create an order.

        Args:
            action: Trade direction, BUY or SELL.
            price: Price of order.
            quantity: The buying or selling quantity.
            order_type: Order type, MARKET or LIMIT.

        Returns:
            order_no: Order ID if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if action not in [ORDER_ACTION_BUY, ORDER_ACTION_SELL]:
            return None, "action error"
        if order_type not in [ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT]:
            return None, "order_type error"

        price = tools.float_to_str(price)
        quantity = tools.float_to_str(quantity)
        success, error = await self._rest_api.create_order(action, self._raw_symbol, price, quantity, order_type)
        if error:
            return None, error
        order_no = str(success["orderNo"])
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
            order_nos, error = await self._rest_api.get_open_order_nos(self._raw_symbol)
            if error:
                return False, error
            while order_nos:
                nos = order_nos[:50]
                order_nos = order_nos[50:]
                success, error = await self._rest_api.revoke_orders(nos)
                if error:
                    return False, error
                if len(success["failResultList"]) > 0:
                    return False, success["failResultList"]
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
            success, error = await self._rest_api.revoke_orders(order_nos)
            if error:
                return None, error
            if len(success["failResultList"]) > 0:
                return success["successNoList"], success["failResultList"]
            else:
                return success["successNoList"], None

    async def get_open_order_nos(self):
        """ Get open order id list.

        Args:
            None.

        Returns:
            order_nos: Open order id list, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self._rest_api.get_open_order_nos(self._raw_symbol)
        return success, error

    async def _check_order_update(self, *args, **kwargs):
        """ Loop run task for check order status.
        """
        order_nos = list(self._orders.keys())
        if not order_nos:
            return
        while order_nos:
            nos = order_nos[:50]
            success, error = await self._rest_api.get_order_list(nos)
            if error:
                return
            for order_info in success:
                await self._update_order(order_info)
            order_nos = order_nos[50:]

    @async_method_locker("CoinsuperPreTrade.order.locker")
    async def _update_order(self, order_info):
        """ Update order object.

        Args:
            order_info: Order information.
        """
        if not order_info:
            return
        status_updated = False
        order_no = str(order_info["orderNo"])
        state = order_info["state"]

        order = self._orders.get(order_no)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": order_info["action"],
                "symbol": self._symbol,
                "price": order_info["priceLimit"],
                "quantity": order_info["quantity"],
                "remain": order_info["quantityRemaining"],
                "avg_price": order_info["priceLimit"]
            }
            order = Order(**info)
            self._orders[order_no] = order

        if state == "UNDEAL" or state == "PROCESSING":
            if order.status != ORDER_STATUS_SUBMITTED:
                order.status = ORDER_STATUS_SUBMITTED
                status_updated = True
        elif state == "PARTDEAL":
            order.status = ORDER_STATUS_PARTIAL_FILLED
            if order.order_type == ORDER_TYPE_LIMIT:
                if float(order.remain) != float(order_info["quantityRemaining"]):
                    status_updated = True
                    order.remain = float(order_info["quantityRemaining"])
            else:
                if float(order.remain) != float(order_info["amountRemaining"]):
                    status_updated = True
                    order.remain = float(order_info["amountRemaining"])
        elif state == "DEAL":
            order.status = ORDER_STATUS_FILLED
            order.remain = 0
            status_updated = True
        elif state == "CANCEL":
            order.status = ORDER_STATUS_CANCELED
            if order.order_type == ORDER_TYPE_LIMIT:
                if float(order.remain) != float(order_info["quantityRemaining"]):
                    order.remain = float(order_info["quantityRemaining"])
            else:
                if float(order.remain) != float(order_info["amountRemaining"]):
                    order.remain = float(order_info["amountRemaining"])
            status_updated = True
        else:
            logger.warn("state error! order_info:", order_info, caller=self)
            return

        # If order status updated, callback newest order information.
        if status_updated:
            order.ctime = order_info["utcCreate"]
            order.utime = order_info["utcUpdate"]
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

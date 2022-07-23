# -*- coding:utf-8 -*-

"""
Kraken Trade module.
https://www.kraken.com/features/api

Author: HuangTao
Date:   2018/05/03
Email:  huangtao@ifclover.com
"""

import copy
import hmac
import base64
import hashlib
import urllib
import urllib.parse

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import KRAKEN
from quant.order import Order
from quant.asset import Asset, AssetSubscribe
from quant.tasks import SingleTask, LoopRunTask
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("KrakenRestAPI", "KrakenTrade", )


class KrakenRestAPI:
    """ Kraken Trade module.

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

    async def get_server_time(self):
        """ Get server time.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        success, error = await self.request("POST", "/0/public/Time")
        return success, error

    async def get_asset_info(self):
        """ Get asset info.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        success, error = await self.request("GET", "/0/public/Assets")
        return success, error

    async def get_asset_pairs(self):
        """ Get tradable asset pairs.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        success, error = await self.request("GET", "/0/public/AssetPairs")
        return success, error

    async def get_orderbook(self, pair, count=10):
        """ Get order book.

        Args:
            pair: asset pair to get market depth for.
            count: maximum number of asks/bids (optional), default is 10.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        body = {
            "pair": pair,
            "count": count
        }
        success, error = await self.request("POST", "/0/public/Depth", body=body)
        return success, error

    async def get_tickers(self, *pair):
        """ Get ticker information.

        Args:
            pair: comma delimited list of asset pairs to get info on.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        body = {
            "pair": ",".join(pair),
        }
        success, error = await self.request("POST", "/0/public/Ticker", body=body)
        return success, error

    async def get_trade(self, pair, since=None):
        """ Get recent trades.

        Args:
            pair: asset pair to get trade data for.
            since: return trade data since given id (optional.  exclusive)

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        body = {
            "pair": pair
        }
        if since:
            body["since"] = since
        success, error = await self.request("POST", "/0/public/Trades", body=body)
        return success, error

    async def get_account_balance(self):
        """ Get account balance.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        success, error = await self.request("POST", "/0/private/Balance", auth=True)
        return success, error

    async def get_trade_balance(self):
        """ Get trade balance.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        success, error = await self.request("POST", "/0/private/TradeBalance", auth=True)
        return success, error

    async def get_open_orders(self):
        """ Get open orders.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.

        NOTE:
            Success results maybe contains multiple pairs orders.
        """
        success, error = await self.request("POST", "/0/private/OpenOrders", auth=True)
        return success, error

    async def get_closed_orders(self):
        """ Get closed orders.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.

        NOTE:
            Success results maybe contains multiple pairs orders.
        """
        success, error = await self.request("POST", "/0/private/ClosedOrders", auth=True)
        return success, error

    async def get_order_infos(self, *txid):
        """ Query orders info.

        Args:
            txid: comma delimited list of transaction ids to query info about (50 maximum).

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        body = {
            "txid": ",".join(txid)
        }
        success, error = await self.request("POST", "/0/private/QueryOrders", body=body, auth=True)
        return success, error

    async def create_order(self, pair, _type, price, quantity, order_type="limit", leverage=None):
        """ Add standard order.

        Args:
            pair: asset pair.
            _type: type of order (buy/sell).
            price: price (optional.  dependent upon ordertype).
            quantity: order volume in lots.
            order_type: order type (market/limit).
            leverage: amount of leverage desired (optional.  default = none).

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        body = {
            "pair": pair,
            "type": _type,
            "ordertype": order_type,
            "price": price,
            "volume": quantity
        }
        if leverage:
            body["leverage"] = leverage
        success, error = await self.request("POST", "/0/private/AddOrder", body=body, auth=True)
        return success, error

    async def revoke_order(self, txid):
        """ Cancel open order

        Args:
            txid: transaction id.

        Returns:
            success: Success results, otherwise it"s None.
            error: Error information, otherwise it"s None.
        """
        body = {
            "txid": txid
        }
        success, error = await self.request("POST", "/0/private/CancelOrder", body=body, auth=True)
        return success, error

    async def request(self, method, uri, body=None, auth=False):
        """ Do HTTP request.
        """
        url = urllib.parse.urljoin(self._host, uri)
        headers = {}
        if method == "POST":
            body = body or {}
            # Sometimes requests can arrive out of order or NTP can cause your clock to rewind.
            body["nonce"] = tools.get_cur_timestamp_ms() + 3000
            if auth:
                headers = {
                    "API-Key": self._access_key,
                    "API-Sign": self._generate_signature(uri, body)
                }
        _, success, error = await AsyncHttpRequests.fetch(method, url, body=body, headers=headers, timeout=10)
        if error:
            return None, error
        if success["error"]:
            return success, success["error"]
        return success["result"], None

    def _generate_signature(self, url, data):
        """ Generate signature.
        """
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = url.encode() + hashlib.sha256(encoded).digest()
        sign = hmac.new(base64.b64decode(self._secret_key), message, hashlib.sha512)
        signature = base64.b64encode(sign.digest()).decode()
        return signature


class KrakenTrade:
    """ Kraken Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default is "https://api.kraken.com")
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
            kwargs["host"] = "https://api.kraken.com"
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
        self._platform = KRAKEN
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")
        self._check_order_interval = kwargs.get("check_order_interval", 2)

        self._raw_symbol = self._symbol.replace("/", "")  # Raw symbol name.

        self._assets = {}  # Asset information. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order details. e.g. {order_no: order-object, ... }

        # Initialize our REST API client.
        self._rest_api = KrakenRestAPI(self._host, self._access_key, self._secret_key)

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
        result, error = await self._rest_api.get_open_orders()
        if error:
            e = Error("get open order nos failed: {}".format(error))
            logger.error(e, caller=self)
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        for order_no, order_info in result["open"].items():
            if order_info["descr"]["pair"] != self._raw_symbol:
                continue
            await self._update_order(order_no, order_info)
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

        price = tools.float_to_str(price)
        quantity = tools.float_to_str(quantity)
        success, error = await self._rest_api.create_order(self._raw_symbol, action_type, price, quantity, order_type_2)
        if error:
            return None, error
        order_no = success["txid"][0]
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
            result, error = await self._rest_api.get_open_orders()
            if error:
                return False, error
            for order_no, order_info in result["open"].items():
                if order_info["descr"]["pair"] != self._raw_symbol:
                    continue
                _, error = await self._rest_api.revoke_order(order_no)
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
        result, error = await self._rest_api.get_open_orders()
        if error:
            return False, error
        order_nos = []
        for order_no, order_info in result["open"].items():
            if order_info["descr"]["pair"] != self._raw_symbol:
                continue
            order_nos.append(order_no)
        return order_nos, None

    async def _check_order_update(self, *args, **kwargs):
        """ Loop run task for check order status.
        """
        order_nos = list(self._orders.keys())
        if not order_nos:
            return
        while order_nos:
            nos = order_nos[:50]
            success, error = await self._rest_api.get_order_infos(*nos)
            if error:
                return
            for order_no, order_info in success.items():
                await self._update_order(order_no, order_info)
            order_nos = order_nos[50:]

    @async_method_locker("KrakenTrade.order.locker")
    async def _update_order(self, order_no, order_info):
        """ Update order object.

        Args:
            order_no: Order ID.
            order_info: Order information.
        """
        if not order_info:
            return
        status_updated = False
        state = order_info["status"]

        order = self._orders.get(order_no)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": ORDER_ACTION_BUY if order_info["descr"]["type"] == "buy" else ORDER_ACTION_SELL,
                "symbol": self._symbol,
                "price": order_info["descr"]["price"],
                "quantity": order_info["vol"],
                "remain": order_info["vol"],
                "avg_price": order_info["price"]
            }
            order = Order(**info)
            self._orders[order_no] = order

        if state == "pending":
            if order.status != ORDER_STATUS_SUBMITTED:
                order.status = ORDER_STATUS_SUBMITTED
                status_updated = True
        elif state == "open":
            vol_exec = float(order_info["vol_exec"])
            if vol_exec == 0:
                state = ORDER_STATUS_SUBMITTED
                if order.status != state:
                    order.status = ORDER_STATUS_SUBMITTED
                    status_updated = True
            else:
                remain = float(order.quantity) - vol_exec
                if order.remain != remain:
                    order.status = ORDER_STATUS_PARTIAL_FILLED
                    order.remain = remain
                    status_updated = True
        elif state == "closed":
            order.status = ORDER_STATUS_FILLED
            order.remain = 0
            status_updated = True
        elif state == "canceled":
            order.status = ORDER_STATUS_CANCELED
            vol_exec = float(order_info["vol_exec"])
            remain = float(order.quantity) - vol_exec
            if order.remain != remain:
                order.remain = remain
            status_updated = True
        elif state == 'expired':
            order.status = ORDER_STATUS_FAILED
            status_updated = True
        else:
            logger.warn("state error! order_info:", order_info, caller=self)
            return

        if status_updated:
            order.avg_price = order_info["price"]
            order.ctime = int(order_info["opentm"] * 1000)
            order.utime = int(order_info["expiretm"] * 1000)
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

# -*- coding:utf-8 -*-

"""
OKEx Swap Trade module
https://www.okex.me/docs/zh/

NOTE: Only Cross Margin Mode is supported in Trade module currently. Please change Margin Mode to `Cross`, not `Fixed`!

Author: HuangTao
Date:   2019/01/19
Email:  huangtao@ifclover.com
"""

import time
import zlib
import json
import copy
import hmac
import base64
from urllib.parse import urljoin

from quant.error import Error
from quant.order import Order
from quant.utils import tools
from quant.utils import logger
from quant.tasks import SingleTask
from quant.position import Position
from quant.const import OKEX_SWAP
from quant.utils.websocket import Websocket
from quant.asset import Asset, AssetSubscribe
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL, ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("OKExSwapRestAPI", "OKExSwapTrade", )


class OKExSwapRestAPI:
    """ OKEx Swap REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        passphrase: API KEY Passphrase.
    """

    def __init__(self, host, access_key, secret_key, passphrase):
        """initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key
        self._passphrase = passphrase

    async def get_user_account(self):
        """ Get the perpetual swap account info of all tokens. Margin ratio set as 10,000 when users have no open
            position.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self.request("GET", "/api/swap/v3/accounts", auth=True)
        return success, error

    async def get_position(self, instrument_id):
        """ Get the information of holding positions of a contract.
        Args:
            instrument_id: Contract ID, e.g. BTC-USD-SWAP.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/swap/v3/{instrument_id}/position".format(instrument_id=instrument_id)
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def create_order(self, instrument_id, trade_type, price, size, match_price=0, order_type=0, client_oid=None):
        """ Create an order.
        Args:
            instrument_id: Contract ID, e.g. BTC-USD-SWAP.
            trade_type: 1: open long, 2: open short, 3: close long, 4: close short.
            price: Price of each contract.
            size: The buying or selling quantity.
            match_price: Order at best counter party price? (0: no, 1: yes), When posting orders at best bid price,
                            order_type can only be 0 (regular order).
            order_type: Fill in number for parameter, 0: Normal limit order (Unfilled and 0 represent normal limit
                            order) 1: Post only, 2: Fill Or Kill, 3: Immediately Or Cancel.
            client_oid: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/swap/v3/order"
        body = {
            "instrument_id": instrument_id,
            "type": str(trade_type),
            "price": price,
            "size": size,
            "match_price": match_price,
            "order_type": order_type
        }
        if client_oid:
            body["client_oid"] = client_oid
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def revoke_order(self, instrument_id, order_id):
        """ Cancelling an unfilled order.
        Args:
            instrument_id: Contract ID, e.g. BTC-USD-SWAP.
            order_id: order ID.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/swap/v3/cancel_order/{instrument_id}/{order_id}".format(instrument_id=instrument_id,
                                                                            order_id=order_id)
        success, error = await self.request("POST", uri, auth=True)
        if error:
            return None, error
        if not success["result"]:
            return None, success
        return success, None

    async def revoke_orders(self, instrument_id, order_ids):
        """ Cancelling multiple open orders with order_id，Maximum 10 orders can be cancelled at a time for each
            trading pair.

        Args:
            instrument_id: Contract ID, e.g. BTC-USD-SWAP.
            order_ids: order ID list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        assert isinstance(order_ids, list)
        if len(order_ids) > 10:
            logger.warn("order id list too long! no more than 10!", caller=self)
        uri = "/api/swap/v3/cancel_batch_orders/{instrument_id}".format(instrument_id=instrument_id)
        body = {
            "ids": order_ids
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        if error:
            return None, error
        if not success["result"]:
            return None, success
        return success, None

    async def get_order_info(self, instrument_id, order_id):
        """ Get order details by order ID. Canceled unfilled orders will be kept in record for 2 hours only.

        Args:
            instrument_id: Contract ID, e.g. BTC-USD-SWAP.
            order_id: order ID.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/swap/v3/orders/{instrument_id}/{order_id}".format(instrument_id=instrument_id, order_id=order_id)
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def get_order_list(self, instrument_id, state, limit=100):
        """ List your orders. This API can retrieve the latest 20000 entries of data this week.

        Args:
            instrument_id: Contract ID, e.g. BTC-USD-SWAP.
            state: Order state for filter. ("-2": Failed, "-1": Cancelled, "0": Open , "1": Partially Filled,
                    "2": Fully Filled, "3": Submitting, "4": Cancelling, "6": Incomplete(open + partially filled),
                    "7": Complete(cancelled + fully filled)).
            limit: Number of results per request. Maximum 100. (default 100)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        TODO: Add args `from` & `to`.
        """
        uri = "/api/swap/v3/orders/{instrument_id}".format(instrument_id=instrument_id)
        params = {
            "state": state,
            "limit": limit
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
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
        if params:
            query = "&".join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
            uri += "?" + query
        url = urljoin(self._host, uri)

        # Add signature for authentication.
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
        if error:
            return None, error
        if not isinstance(success, dict):  # If response data is not dict format, convert it to json format.
            success = json.loads(success)
        return success, None


class OKExSwapTrade(Websocket):
    """ OKEx Swap Trade module. You can initialize trade object with some attributes in kwargs.

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
        position_update_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `position_update_callback` is like `async def on_position_update_callback(order: Position): pass` and
            this callback function will be executed asynchronous when some position state updated.
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
        self._platform = OKEX_SWAP
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._passphrase = kwargs["passphrase"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._position_update_callback = kwargs.get("position_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")

        url = self._wss + "/ws/v3"
        super(OKExSwapTrade, self).__init__(url, send_hb_interval=5)
        self.heartbeat_msg = "ping"

        self._assets = {}  # Asset object. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order objects. e.g. {"order_no": Order, ... }
        self._position = Position(self._platform, self._account, self._strategy, self._symbol)

        # Subscribing our channels.
        self._order_channel = "swap/order:{symbol}".format(symbol=self._symbol)
        self._position_channel = "swap/position:{symbol}".format(symbol=self._symbol)

        # If our channels that subscribed successfully.
        self._subscribe_order_ok = False
        self._subscribe_position_ok = False

        # Initializing our REST API client.
        self._rest_api = OKExSwapRestAPI(self._host, self._access_key, self._secret_key, self._passphrase)

        # Subscribing our asset event.
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
    def position(self):
        return copy.copy(self._position)

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

    @async_method_locker("OKExSwapTrade.process_binary.locker")
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

        # Heartbeat message received.
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
            result, error = await self._rest_api.get_order_list(self._symbol, 6)
            if error:
                e = Error("get open orders error: {}".format(error))
                SingleTask.run(self._init_success_callback, False, e)
                return
            if len(result) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            for order_info in result["order_info"]:
                self._update_order(order_info)

            # Fetch positions from server.
            position, error = await self._rest_api.get_position(self._symbol)
            if error:
                e = Error("get position error: {}".format(error))
                SingleTask.run(self._init_success_callback, False, e)
                return
            self._update_position(position)

            # Subscribe order channel and position channel.
            data = {
                "op": "subscribe",
                "args": [self._order_channel, self._position_channel]
            }
            await self.ws.send_json(data)
            return

        # Subscribe response message received.
        if msg.get("event") == "subscribe":
            if msg.get("channel") == self._order_channel:
                self._subscribe_order_ok = True
            if msg.get("channel") == self._position_channel:
                self._subscribe_position_ok = True
            if self._subscribe_order_ok and self._subscribe_position_ok:
                SingleTask.run(self._init_success_callback, True, None)
            return

        # Order update message received.
        if msg.get("table") == "swap/order":
            for data in msg["data"]:
                self._update_order(data)
            return

        # Position update message receive.
        if msg.get("table") == "swap/position":
            for data in msg["data"]:
                self._update_position(data)

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, match_price=0, *args, **kwargs):
        """ Create an order.

        Args:
            action: Trade direction, `BUY` or `SELL`.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            order_type: Order type, `MARKET` or `LIMIT`.
            match_price: Order at best counter party price? (0: no, 1: yes), When posting orders at best bid price,
                            order_type can only be 0 (regular order).
            order_type: Fill in number for parameter, 0: Normal limit order (Unfilled and 0 represent normal limit
                            order) 1: Post only, 2: Fill Or Kill, 3: Immediately Or Cancel.

        Returns:
            order_no: Order ID if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if int(quantity) > 0:
            if action == ORDER_ACTION_BUY:
                trade_type = "1"
            else:
                trade_type = "3"
        else:
            if action == ORDER_ACTION_BUY:
                trade_type = "4"
            else:
                trade_type = "2"
        quantity = abs(int(quantity))
        if order_type == ORDER_TYPE_LIMIT:
            order_type_2 = 0
        elif order_type == ORDER_TYPE_MARKET:
            order_type_2 = 2
        else:
            return None, "order type error"
        client_order_id = kwargs.get("client_order_id")
        result, error = await self._rest_api.create_order(self._symbol, trade_type, price, quantity, match_price,
                                                          order_type_2, client_oid=client_order_id)
        if error:
            return None, error
        order_no = result["order_id"]
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
            result, error = await self._rest_api.get_order_list(self._symbol, 6)
            if error:
                return False, error
            if len(result) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            for order_info in result["order_info"]:
                order_no = order_info["order_id"]
                _, error = await self._rest_api.revoke_order(self._symbol, order_no)
                if error:
                    return False, error
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(self._symbol, order_nos[0])
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_nos) > 1:
            success, error = [], []
            for order_no in order_nos:
                _, e = await self._rest_api.revoke_order(self._symbol, order_no)
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
        success, error = await self._rest_api.get_order_list(self._symbol, 6)
        if error:
            return None, error
        else:
            if len(success) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            order_nos = []
            for order_info in success["order_info"]:
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
        remain = int(order_info["size"]) - int(order_info["filled_qty"])
        ctime = tools.utctime_str_to_mts(order_info["timestamp"])
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
            return None

        order = self._orders.get(order_no)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "client_order_id": order_info["client_oid"],
                "action": ORDER_ACTION_BUY if order_info["type"] in ["1", "4"] else ORDER_ACTION_SELL,
                "symbol": self._symbol,
                "price": order_info["price"],
                "quantity": order_info["size"],
                "trade_type": int(order_info["type"])
            }
            order = Order(**info)
        order.remain = remain
        order.status = status
        order.avg_price = order_info["price_avg"]
        order.ctime = ctime
        order.utime = ctime
        self._orders[order_no] = order

        SingleTask.run(self._order_update_callback, copy.copy(order))

        if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_no)

    def _update_position(self, position_info):
        """ Position update.

        Args:
            position_info: Position information.

        Returns:
            None.
        """
        if len(position_info["holding"]) == 0:  # When the length of `holding` is 0, specific all the position is closed
            self._position.update(0, 0, 0, 0, 0)
            return
        for item in position_info["holding"]:
            if item["side"] == "long":
                self._position.liquid_price = item["liquidation_price"]
                self._position.long_quantity = int(item["position"])
                self._position.long_avg_price = item["avg_cost"]
            elif item["side"] == "short":
                self._position.short_quantity = int(item["position"])
                self._position.short_avg_price = item["avg_cost"]
            else:
                continue
            self._position.utime = tools.utctime_str_to_mts(item["timestamp"])
        SingleTask.run(self._position_update_callback, copy.copy(self.position))

    async def on_event_asset_update(self, asset: Asset):
        """ Asset event data callback.

        Args:
            asset: Asset object callback from EventCenter.

        Returns:
            None.
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

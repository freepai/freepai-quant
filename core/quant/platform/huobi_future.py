# -*- coding:utf-8 -*-

"""
Huobi Future Trade module.
https://www.hbdm.com/zh-cn/contract/exchange/

Author: HuangTao
Date:   2019/08/23
Email:  huangtao@ifclover.com
"""

import gzip
import json
import copy
import hmac
import base64
import urllib
import hashlib
import datetime
from urllib.parse import urljoin

from quant.error import Error
from quant.order import Order
from quant.utils import tools
from quant.utils import logger
from quant.tasks import SingleTask
from quant.position import Position
from quant.const import HUOBI_FUTURE
from quant.utils.web import Websocket
from quant.asset import Asset, AssetSubscribe
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED, TRADE_TYPE_BUY_OPEN, TRADE_TYPE_SELL_OPEN, TRADE_TYPE_BUY_CLOSE, \
    TRADE_TYPE_SELL_CLOSE


__all__ = ("HuobiFutureRestAPI", "HuobiFutureTrade", )


class HuobiFutureRestAPI:
    """ OKEx Swap REST API client.

    Attributes:
        host: HTTP request host.
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        passphrase: API KEY Passphrase.
    """

    def __init__(self, host, access_key, secret_key):
        """initialize REST API client."""
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_contract_info(self, symbol=None, contract_type=None, contract_code=None):
        """ Get contract information.

        Args:
            symbol: Trade pair, default `None` will return all symbols.
            contract_type: Contract type, `this_week` / `next_week` / `quarter`, default `None` will return all types.
            contract_code: Contract code, e.g. BTC180914.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        * NOTE: 1. If input `contract_code`, only matching this contract code.
                2. If not input `contract_code`, matching by `symbol + contract_type`.
        """
        uri = "/api/v1/contract_contract_info"
        params = {}
        if symbol:
            params["symbol"] = symbol
        if contract_type:
            params["contract_type"] = contract_type
        if contract_code:
            params["contract_code"] = contract_code
        success, error = await self.request("GET", uri, params)
        return success, error

    async def get_price_limit(self, symbol=None, contract_type=None, contract_code=None):
        """ Get contract price limit.

        Args:
            symbol: Trade pair, default `None` will return all symbols.
            contract_type: Contract type, `this_week` / `next_week` / `quarter`, default `None` will return all types.
            contract_code: Contract code, e.g. BTC180914.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        * NOTE: 1. If input `contract_code`, only matching this contract code.
                2. If not input `contract_code`, matching by `symbol + contract_type`.
        """
        uri = "/api/v1/contract_price_limit"
        params = {}
        if symbol:
            params["symbol"] = symbol
        if contract_type:
            params["contract_type"] = contract_type
        if contract_code:
            params["contract_code"] = contract_code
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_orderbook(self, symbol):
        """ Get orderbook information.

        Args:
            symbol: Symbol name, `BTC_CW` - current week, `BTC_NW` next week, `BTC_CQ` current quarter.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/market/depth"
        params = {
            "symbol": symbol,
            "type": "step0"
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_asset_info(self):
        """ Get account asset information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_account_info"
        success, error = await self.request("POST", uri, auth=True)
        return success, error

    async def get_position(self, symbol=None):
        """ Get position information.

        Args:
            symbol: Currency name, e.g. BTC. default `None` will return all types.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_position_info"
        body = {}
        if symbol:
            body["symbol"] = symbol
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def create_order(self, symbol, contract_type, contract_code, price, quantity, direction, offset, lever_rate,
                           order_price_type):
        """ Create an new order.

        Args:
            symbol: Currency name, e.g. BTC.
            contract_type: Contract type, `this_week` / `next_week` / `quarter`.
            contract_code: Contract code, e.g. BTC180914.
            price: Order price.
            quantity: Order amount.
            direction: Transaction direction, `buy` / `sell`.
            offset: `open` / `close`.
            lever_rate: Leverage rate, 10 or 20.
            order_price_type: Order type, `limit` - limit order, `opponent` - market order.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_order"
        body = {
            "symbol": symbol,
            "contract_type": contract_type,
            "contract_code": contract_code,
            "price": price,
            "volume": quantity,
            "direction": direction,
            "offset": offset,
            "lever_rate": lever_rate,
            "order_price_type": order_price_type
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def revoke_order(self, symbol, order_id):
        """ Revoke an order.

        Args:
            symbol: Currency name, e.g. BTC.
            order_id: Order ID.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_cancel"
        body = {
            "symbol": symbol,
            "order_id": order_id
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def revoke_orders(self, symbol, order_ids):
        """ Revoke multiple orders.

        Args:
            symbol: Currency name, e.g. BTC.
            order_ids: Order ID list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_cancel"
        body = {
            "symbol": symbol,
            "order_id": ",".join(order_ids)
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def revoke_order_all(self, symbol, contract_code=None, contract_type=None):
        """ Revoke all orders.

        Args:
            symbol: Currency name, e.g. BTC.
            contract_type: Contract type, `this_week` / `next_week` / `quarter`, default `None` will return all types.
            contract_code: Contract code, e.g. BTC180914.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        * NOTE: 1. If input `contract_code`, only matching this contract code.
                2. If not input `contract_code`, matching by `symbol + contract_type`.
        """
        uri = "/api/v1/contract_cancelall"
        body = {
            "symbol": symbol,
        }
        if contract_code:
            body["contract_code"] = contract_code
        if contract_type:
            body["contract_type"] = contract_type
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def get_order_info(self, symbol, order_ids):
        """ Get order information.

        Args:
            symbol: Currency name, e.g. BTC.
            order_ids: Order ID list. (different IDs are separated by ",", maximum 20 orders can be withdrew at one time.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_order_info"
        body = {
            "symbol": symbol,
            "order_id": ",".join(order_ids)
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def get_open_orders(self, symbol, index=1, size=50):
        """ Get open order information.

        Args:
            symbol: Currency name, e.g. BTC.
            index: Page index, default 1st page.
            size: Page size, Default 20，no more than 50.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v1/contract_openorders"
        body = {
            "symbol": symbol,
            "page_index": index,
            "page_size": size
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """ Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body: HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)

        if auth:
            timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            params = params if params else {}
            params.update({"AccessKeyId": self._access_key,
                           "SignatureMethod": "HmacSHA256",
                           "SignatureVersion": "2",
                           "Timestamp": timestamp})

            params["Signature"] = self.generate_signature(method, params, uri)

        if not headers:
            headers = {}
        if method == "GET":
            headers["Content-type"] = "application/x-www-form-urlencoded"
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                                    "Chrome/39.0.2171.71 Safari/537.36"
            _, success, error = await AsyncHttpRequests.fetch("GET", url, params=params, headers=headers, timeout=10)
        else:
            headers["Accept"] = "application/json"
            headers["Content-type"] = "application/json"
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0"
            _, success, error = await AsyncHttpRequests.fetch("POST", url, params=params, data=body, headers=headers,
                                                              timeout=10)
        if error:
            return None, error
        if not isinstance(success, dict):
            result = json.loads(success)
        else:
            result = success
        if result.get("status") != "ok":
            return None, result
        return result, None

    def generate_signature(self, method, params, request_path):
        host_url = urllib.parse.urlparse(self._host).hostname.lower()
        sorted_params = sorted(params.items(), key=lambda d: d[0], reverse=False)
        encode_params = urllib.parse.urlencode(sorted_params)
        payload = [method, host_url, request_path, encode_params]
        payload = "\n".join(payload)
        payload = payload.encode(encoding="UTF8")
        secret_key = self._secret_key.encode(encoding="utf8")
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature


class HuobiFutureTrade:
    """ Huobi Future Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for you strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. default `https://api.hbdm.com"`.
        wss: Websocket address. default `wss://www.hbdm.com`.
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
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
        if not kwargs.get("contract_type"):
            e = Error("param contract_type miss")
        if not kwargs.get("contract_code"):
            e = Error("param contract_code miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://api.hbdm.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://api.hbdm.com"
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
        self._platform = HUOBI_FUTURE
        self._symbol = kwargs["symbol"]
        self._contract_type = kwargs["contract_type"]
        self._contract_code = kwargs["contract_code"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._position_update_callback = kwargs.get("position_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")

        url = self._wss + "/notification"
        self._ws = Websocket(url, self.connected_callback, process_binary_callback=self.process_binary)
        self._ws.initialize()

        self._assets = {}  # Asset detail, {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }.
        self._orders = {}  # Order objects, {"order_id": order, ...}.
        self._position = Position(self._platform, self._account, self._strategy, self._contract_code)

        self._order_channel = "orders.{symbol}".format(symbol=self._symbol.lower())
        self._position_channel = "positions.{symbol}".format(symbol=self._symbol.lower())

        self._subscribe_order_ok = False
        self._subscribe_position_ok = False

        self._rest_api = HuobiFutureRestAPI(self._host, self._access_key, self._secret_key)

        # Subscribe AssetEvent.
        if self._asset_update_callback:
            AssetSubscribe(self._platform, self._account, self.on_event_asset_update)

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
        """After connect to Websocket server successfully, send a auth message to server."""
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        data = {
            "AccessKeyId": self._access_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": timestamp
        }
        sign = self._rest_api.generate_signature("GET", data, "/notification")
        data["op"] = "auth"
        data["type"] = "api"
        data["Signature"] = sign
        await self._ws.send(data)

    async def auth_callback(self, data):
        if data["err-code"] != 0:
            e = Error("Websocket connection authorized failed: {}".format(data))
            logger.error(e, caller=self)
            SingleTask.run(self._init_success_callback, False, e)
            return

        # subscribe order
        data = {
            "op": "sub",
            "cid": tools.get_uuid1(),
            "topic": self._order_channel
        }
        await self._ws.send(data)

        # subscribe position
        data = {
            "op": "sub",
            "cid": tools.get_uuid1(),
            "topic": self._position_channel
        }
        await self._ws.send(data)

    async def sub_callback(self, data):
        if data["err-code"] != 0:
            e = Error("subscribe {} failed!".format(data["topic"]))
            logger.error(e, caller=self)
            SingleTask.run(self._init_success_callback, False, e)
            return
        if data["topic"] == self._order_channel:
            self._subscribe_order_ok = True
        elif data["topic"] == self._position_channel:
            self._subscribe_position_ok = True
        if self._subscribe_order_ok and self._subscribe_position_ok:
            success, error = await self._rest_api.get_open_orders(self._symbol)
            if error:
                e = Error("get open orders failed!")
                SingleTask.run(self._init_success_callback, False, e)
            for order_info in success["data"]["orders"]:
                order_info["ts"] = order_info["created_at"]
                self._update_order(order_info)
            SingleTask.run(self._init_success_callback, True, None)

    @async_method_locker("HuobiFutureTrade.process_binary.locker")
    async def process_binary(self, raw):
        """ 处理websocket上接收到的消息
        @param raw 原始的压缩数据
        """
        data = json.loads(gzip.decompress(raw).decode())
        logger.debug("data:", data, caller=self)

        op = data.get("op")
        if op == "ping":
            hb_msg = {"op": "pong", "ts": data.get("ts")}
            await self._ws.send(hb_msg)

        elif op == "auth":
            await self.auth_callback(data)

        elif op == "sub":
            await self.sub_callback(data)

        elif op == "notify":
            if data["topic"] == self._order_channel:
                self._update_order(data)
            elif data["topic"] == "positions":
                self._update_position(data)
            elif data["topic"] == self._position_channel:
                self._update_position(data)

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, *args, **kwargs):
        """ Create an order.

        Args:
            action: Trade direction, BUY or SELL.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            order_type: Order type, LIMIT or MARKET.
            kwargs:
                lever_rate: Leverage rate, 10 or 20.

        Returns:
            order_no: Order ID if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if int(quantity) > 0:
            if action == ORDER_ACTION_BUY:
                direction = "buy"
                offset = "open"
            elif action == ORDER_ACTION_SELL:
                direction = "sell"
                offset = "close"
            else:
                return None, "action error"
        else:
            if action == ORDER_ACTION_BUY:
                direction = "buy"
                offset = "close"
            elif action == ORDER_ACTION_SELL:
                direction = "sell"
                offset = "open"
            else:
                return None, "action error"

        lever_rate = kwargs.get("lever_rate", 20)
        if order_type == ORDER_TYPE_LIMIT:
            order_price_type = "limit"
        elif order_type == ORDER_TYPE_MARKET:
            order_price_type = "opponent"
        else:
            return None, "order type error"

        quantity = abs(int(quantity))
        result, error = await self._rest_api.create_order(self._symbol, self._contract_type, self._contract_code,
                                                          price, quantity, direction, offset, lever_rate,
                                                          order_price_type)
        if error:
            return None, error
        return str(result["data"]["order_id"]), None

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
            success, error = await self._rest_api.revoke_order_all(self._symbol, self._contract_code, self._contract_type)
            if error:
                return False, error
            if success.get("errors"):
                return False, success["errors"]
            return True, None

        # If len(order_nos) == 1, you will cancel an order.
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(self._symbol, order_nos[0])
            if error:
                return order_nos[0], error
            if success.get("errors"):
                return False, success["errors"]
            else:
                return order_nos[0], None

        # If len(order_nos) > 1, you will cancel multiple orders.
        if len(order_nos) > 1:
            success, error = await self._rest_api.revoke_orders(self._symbol, order_nos)
            if error:
                return order_nos[0], error
            if success.get("errors"):
                return False, success["errors"]
            return success, error

    async def get_open_order_nos(self):
        """ Get open order id list.

        Args:
            None.

        Returns:
            order_nos: Open order id list, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self._rest_api.get_open_orders(self._symbol)
        if error:
            return None, error
        else:
            order_nos = []
            for order_info in success["data"]["orders"]:
                if order_info["contract_code"] != self._contract_code:
                    continue
                order_nos.append(str(order_info["order_id"]))
            return order_nos, None

    def _update_order(self, order_info):
        """ Order update.

        Args:
            order_info: Order information.
        """
        if order_info["contract_code"] != self._contract_code:
            return
        order_no = str(order_info["order_id"])
        status = order_info["status"]

        order = self._orders.get(order_no)
        if not order:
            if order_info["direction"] == "buy":
                if order_info["offset"] == "open":
                    trade_type = TRADE_TYPE_BUY_OPEN
                else:
                    trade_type = TRADE_TYPE_BUY_CLOSE
            else:
                if order_info["offset"] == "close":
                    trade_type = TRADE_TYPE_SELL_CLOSE
                else:
                    trade_type = TRADE_TYPE_SELL_OPEN

            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": ORDER_ACTION_BUY if order_info["direction"] == "buy" else ORDER_ACTION_SELL,
                "symbol": self._contract_code,
                "price": order_info["price"],
                "quantity": order_info["volume"],
                "trade_type": trade_type
            }
            order = Order(**info)
            self._orders[order_no] = order

        if status in [1, 2, 3]:
            order.status = ORDER_STATUS_SUBMITTED
        elif status == 4:
            order.status = ORDER_STATUS_PARTIAL_FILLED
            order.remain = int(order.quantity) - int(order_info["trade_volume"])
        elif status == 6:
            order.status = ORDER_STATUS_FILLED
            order.remain = 0
        elif status in [5, 7]:
            order.status = ORDER_STATUS_CANCELED
            order.remain = int(order.quantity) - int(order_info["trade_volume"])
        else:
            return

        order.avg_price = order_info["trade_avg_price"]
        order.ctime = order_info["created_at"]
        order.utime = order_info["ts"]

        SingleTask.run(self._order_update_callback, copy.copy(order))

        # Delete order that already completed.
        if order.status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_no)

    def _update_position(self, data):
        """ Position update.

        Args:
            position_info: Position information.

        Returns:
            None.
        """
        for position_info in data["data"]:
            if position_info["contract_code"] != self._contract_code:
                return
            if position_info["direction"] == "buy":
                self._position.long_quantity = int(position_info["volume"])
                self._position.long_avg_price = position_info["cost_hold"]
            else:
                self._position.short_quantity = int(position_info["volume"])
                self._position.short_avg_price = position_info["cost_hold"]
            # self._position.liquid_price = None
            self._position.utime = data["ts"]
            SingleTask.run(self._position_update_callback, copy.copy(self._position))

    async def on_event_asset_update(self, asset: Asset):
        """ Asset event data callback.

        Args:
            asset: Asset object callback from EventCenter.

        Returns:
            None.
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

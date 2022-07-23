# -*- coding:utf-8 -*-

"""
Bitmex REST API & Trade 模块
https://www.bitmex.com/app/wsAPI
https://www.bitmex.com/api/explorer/swagger.json

Author: HuangTao
Date:   2018/08/09
"""

import copy
import json
import hmac
import hashlib
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.position import Position
from quant.const import BITMEX
from quant.tasks import SingleTask
from quant.utils.websocket import Websocket
from quant.asset import Asset, AssetSubscribe
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import Order
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED
from quant.order import TRADE_TYPE_BUY_OPEN, TRADE_TYPE_SELL_OPEN, TRADE_TYPE_SELL_CLOSE, TRADE_TYPE_BUY_CLOSE


__all__ = ("BitmexAPI", "BitmexTrade", )


class BitmexAPI:
    """ 向交易所发起交易请求
    """

    def __init__(self, host, access_key, secret_key):
        """ 初始化
        @param host 请求的host
        @param access_key 请求的access_key
        @param secret_key 请求的secret_key
        """
        self.host = host
        self.access_key = access_key
        self.secret_key = secret_key

    async def get_wallet(self):
        """ 获取钱包
        """
        success, error = await self.request("GET", "/api/v1/user/wallet")
        return success, error

    async def get_wallet_summary(self):
        """ 获取钱包摘要
        """
        success, error = await self.request("GET", "/api/v1/user/walletSummary")
        return success, error

    async def get_margin(self):
        """ 获取资产净值
        """
        success, error = await self.request("GET", "/api/v1/user/margin")
        return success, error

    async def create_order(self, action, symbol, price, quantity, order_type="Limit", text=""):
        """ 创建委托单
        @param action 委托类型 Buy 买入,  Sell 卖出
        @param symbol 交易对(合约名称)
        @param price 委托价格
        @param quantity 委托数量
        @param order_type 订单类型 Market 市价单, Limit 限价单
        @param text 订单附带说明
        """
        body = {
            "side": action,
            "symbol": symbol,
            "price": price,
            "orderQty": quantity,
            "ordType": order_type,
            "text": text
        }
        success, error = await self.request("POST", "/api/v1/order", body=body)
        return success, error

    async def revoke_order(self, order_id):
        """ 撤销委托单
        @param order_id 委托单id
        """
        body = {
            "orderID": order_id
        }
        success, error = await self.request("DELETE", "/api/v1/order", body=body)
        return success, error

    async def revoke_orders(self, symbol=None):
        """ 撤销所有委托单
        @param symbol 交易对，默认None撤销所有交易对的所有委托单
        """
        if symbol:
            body = {
                "symbol": symbol
            }
        else:
            body = None
        success, error = await self.request("DELETE", "/api/v1/order/all", body=body)
        return success, error

    async def request(self, method, uri, params=None, body=None):
        """ 发起请求
        """
        if params:
            query = "&".join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
            url = uri + "?" + query
        else:
            url = uri
        ts = tools.get_cur_timestamp() + 5
        signature = self.generate_signature(method, url, ts, body)
        headers = {
            "api-expires": str(ts),
            "api-key": self.access_key,
            "api-signature": signature
        }
        url = urljoin(self.host, uri)
        _, success, error = await AsyncHttpRequests.fetch(method, url, headers=headers, data=body, timeout=10)
        return success, error

    def generate_signature(self, verb, url, nonce, data):
        """ 生成签名
        """
        data = json.dumps(data) if data else ""
        message = str(verb + url + str(nonce) + data)
        signature = hmac.new(self.secret_key.encode("utf-8"), message.encode("utf-8"),
                             digestmod=hashlib.sha256).hexdigest()
        return signature


class BitmexTrade(Websocket):
    """ Bitmex 交易模块
    """

    def __init__(self, **kwargs):
        """ 初始化
        """
        e = None
        if not kwargs.get("account"):
            e = Error("param account miss")
        if not kwargs.get("strategy"):
            e = Error("param strategy miss")
        if not kwargs.get("symbol"):
            e = Error("param symbol miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://www.bitmex.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://www.bitmex.com"
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
        self._platform = BITMEX
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._position_update_callback = kwargs.get("position_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")

        url = self._wss + "/realtime"
        super(BitmexTrade, self).__init__(url, send_hb_interval=5)
        self.heartbeat_msg = "ping"

        self._order_channel = "order:{symbol}".format(symbol=self._symbol)  # 订单订阅频道
        self._position_channel = "position:{symbol}".format(symbol=self._symbol)  # 持仓订阅频道

        # 标记订阅订单、持仓是否成功
        self._subscribe_order_ok = False
        self._subscribe_position_ok = False

        self._assets = {}  # 资产 {"XBT": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}
        self._position = Position(self._platform, self._account, self._strategy, self._symbol)  # 仓位

        # 初始化REST API对象
        self._rest_api = BitmexAPI(self._host, self._access_key, self._secret_key)

        # 初始化资产订阅
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
        """ 建立连接之后，鉴权、订阅频道
        """
        # 身份验证
        expires = tools.get_cur_timestamp() + 5
        signature = self._rest_api.generate_signature("GET", "/realtime", expires, None)
        data = {
            "op": "authKeyExpires",
            "args": [self._access_key, expires, signature]
        }
        await self.ws.send_json(data)

    @async_method_locker("BitmexTrade.process.locker")
    async def process(self, msg):
        """ 处理websocket上接收到的消息
        """
        if not isinstance(msg, dict):
            return
        logger.debug("msg:", json.dumps(msg), caller=self)

        # 请求授权、订阅
        if msg.get("request"):
            if msg["request"]["op"] == "authKeyExpires":  # 授权
                if msg["success"]:
                    # 订阅order和position
                    data = {
                        "op": "subscribe",
                        "args": [self._order_channel, self._position_channel]
                    }
                    await self.ws.send_json(data)
                    logger.info("Websocket connection authorized successfully.", caller=self)
                else:
                    e = Error("Websocket connection authorized failed: {}".format(msg))
                    logger.error(e, caller=self)
                    if self._init_success_callback:
                        SingleTask.run(self._init_success_callback, False, e)
            if msg["request"]["op"] == "subscribe":  # 订阅
                if msg["subscribe"] == self._order_channel and msg["success"]:
                    self._subscribe_order_ok = True
                    logger.info("subscribe order successfully.", caller=self)
                if msg["subscribe"] == self._position_channel and msg["success"]:
                    self._subscribe_position_ok = True
                    logger.info("subscribe position successfully.", caller=self)
                if self._subscribe_order_ok and self._subscribe_position_ok:
                    if self._init_success_callback:
                        SingleTask.run(self._init_success_callback, True, None)
            return

        # 订单更新
        if msg.get("table") == "order":
            for data in msg["data"]:
                order = self._update_order(data)
                if order and self._order_update_callback:
                    SingleTask.run(self._order_update_callback, copy.copy(order))
            return

        # 持仓更新
        if msg.get("table") == "position":
            for data in msg["data"]:
                self._update_position(data)
                if self._position_update_callback:
                    SingleTask.run(self._position_update_callback, copy.copy(self.position))

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, *args, **kwargs):
        """ 创建订单
        @param action 委托方向 BUY SELL
        @param price 委托价格
        @param quantity 委托数量
        @param order_type 委托类型 LIMIT / MARKET
        """
        if action == ORDER_ACTION_BUY:
            action_tmp = "Buy"
        else:
            action_tmp = "Sell"
        if int(quantity) > 0:
            if action == ORDER_ACTION_BUY:
                trade_type = TRADE_TYPE_BUY_OPEN
            else:
                trade_type = TRADE_TYPE_SELL_CLOSE
        else:
            if action == ORDER_ACTION_BUY:
                trade_type = TRADE_TYPE_BUY_CLOSE
            else:
                trade_type = TRADE_TYPE_SELL_OPEN
        if order_type == ORDER_TYPE_LIMIT:
            order_type_tmp = "Limit"
        elif order_type == ORDER_TYPE_MARKET:
            order_type_tmp = "Market"
        else:
            return None, "order type error"
        quantity = abs(int(quantity))
        success, error = await self._rest_api.create_order(action_tmp, self._symbol, price, quantity, order_type_tmp,
                                                           trade_type)
        if error:
            return None, error
        else:
            return success["orderID"], None

    async def revoke_order(self, *order_nos):
        """ 撤销订单
        @param order_nos 订单号，可传入任意多个，如果不传入，那么就撤销所有订单
        """
        # 如果传入order_nos为空，即撤销全部委托单
        if len(order_nos) == 0:
            result, error = await self._rest_api.revoke_orders(self._symbol)
            if error:
                return False, error
            return True, None

        # 如果传入order_nos为一个委托单号，那么只撤销一个委托单
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(order_nos[0])
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # 如果传入order_nos数量大于1，那么就批量撤销传入的委托单
        if len(order_nos) > 1:
            success, error = [], []
            for order_no in order_nos:
                _, e = await self._rest_api.revoke_order(order_no)
                if e:
                    error.append((order_no, e))
                else:
                    success.append(order_no)
            return success, error

    def _update_order(self, order_info):
        """ 更新订单信息
        @param order_info 订单信息
              | "New" -> `Open, `New_order_accepted
              | "PartiallyFilled" -> `Open, `Partially_filled
              | "Filled" -> `Filled, `Filled
              | "DoneForDay" -> `Open, `General_order_update
              | "Canceled" -> `Canceled, `Canceled
              | "PendingCancel" -> `Pending_cancel, `General_order_update
              | "Stopped" -> `Open, `General_order_update
              | "Rejected" -> `Rejected, `New_order_rejected
              | "PendingNew" -> `Pending_open, `General_order_update
              | "Expired" -> `Rejected, `New_order_rejected
              | _ -> invalid_arg' execType ordStatus
        """
        order_no = order_info["orderID"]
        state = order_info.get("ordStatus")
        if state == "New":
            status = ORDER_STATUS_SUBMITTED
        elif state == "PartiallyFilled":
            status = ORDER_STATUS_PARTIAL_FILLED
        elif state == "Filled":
            status = ORDER_STATUS_FILLED
        elif state == "Canceled":
            status = ORDER_STATUS_CANCELED
        elif state in ["PendingNew", "DoneForDay", "PendingCancel"]:
            return
        else:
            return

        order = self._orders.get(order_no)
        if not order:
            action = ORDER_ACTION_BUY if order_info["side"] == "Buy" else ORDER_ACTION_SELL
            text = order_info.get("text")
            trade_type = int(text.split("\n")[-1])
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "symbol": self._symbol,
                "order_no": order_no,
                "action": action,
                "price": order_info.get("price"),
                "quantity": int(order_info["orderQty"]),
                "remain": int(order_info["orderQty"]),
                "trade_type": trade_type
            }
            order = Order(**info)
            self._orders[order_no] = order
        order.status = status

        if order_info.get("cumQty"):
            order.remain = order.quantity - int(order_info.get("cumQty"))
        if order_info.get("avgPx"):
            order.avg_price = order_info.get("avgPx")
        if order.status in [ORDER_STATUS_FILLED, ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED]:
            self._orders.pop(order.order_no)
        if order_info.get("timestamp"):
            order.ctime = tools.utctime_str_to_mts(order_info.get("timestamp"))
        if order_info.get("transactTime"):
            order.utime = tools.utctime_str_to_mts(order_info.get("transactTime"))
        return order

    def _update_position(self, position_info):
        """ 更新持仓信息
        @param position_info 持仓信息
        """
        current_qty = position_info.get("currentQty")
        if current_qty > 0:
            self._position.long_quantity = abs(int(current_qty))
            self._position.short_quantity = 0
            if position_info.get("avgEntryPrice"):
                self._position.long_avg_price = position_info.get("avgEntryPrice")
        elif current_qty < 0:
            self._position.long_quantity = 0
            self._position.short_quantity = abs(int(current_qty))
            if position_info.get("avgEntryPrice"):
                self._position.short_avg_price = position_info.get("avgEntryPrice")
        else:
            self._position.short_quantity = 0
            self._position.long_avg_price = 0
            self._position.long_quantity = 0
            self._position.short_avg_price = 0
        if position_info.get("liquidationPrice"):
            self._position.liquid_price = position_info.get("liquidationPrice")
        if position_info.get("timestamp"):
            self._position.utime = tools.utctime_str_to_mts(position_info.get("timestamp"))

    async def on_event_asset_update(self, asset: Asset):
        """ 资产数据更新回调
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

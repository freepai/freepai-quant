# -*- coding:utf-8 -*-

"""
huobi 交易模块
https://huobiapi.github.io/docs/spot/v1/cn

Author: HuangTao
Date:   2018/08/30
"""

import json
import hmac
import copy
import gzip
import base64
import urllib
import hashlib
import datetime
from urllib import parse
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import HUOBI
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


__all__ = ("HuobiRestAPI", "HuobiTrade", )


class HuobiRestAPI:
    """ huobi REST API 封装
    """

    def __init__(self, host, access_key, secret_key):
        """ 初始化
        @param host 请求host
        @param access_key API KEY
        @param secret_key SECRET KEY
        """
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key
        self._account_id = None

    async def get_server_time(self):
        """ 获取服务器时间
        @return data int 服务器时间戳(毫秒)
        """
        success, error = await self.request("GET", "/v1/common/timestamp")
        return success, error

    async def get_user_accounts(self):
        """ 获取账户信息
        """
        success, error = await self.request("GET", "/v1/account/accounts")
        return success, error

    async def _get_account_id(self):
        """ 获取账户id
        """
        if self._account_id:
            return self._account_id
        success, error = await self.get_user_accounts()
        if error:
            return None
        for item in success:
            if item["type"] == "spot":
                self._account_id = item["id"]
                return self._account_id
        return None

    async def get_account_balance(self):
        """ 获取账户信息
        """
        account_id = await self._get_account_id()
        uri = "/v1/account/accounts/{account_id}/balance".format(account_id=account_id)
        success, error = await self.request("GET", uri)
        return success, error

    async def get_balance_all(self):
        """ 母账户查询其下所有子账户的各币种汇总余额
        """
        success, error = await self.request("GET", "/v1/subuser/aggregate-balance")
        return success, error

    async def create_order(self, symbol, price, quantity, order_type):
        """ 创建订单
        @param symbol 交易对
        @param quantity 交易量
        @param price 交易价格
        @param order_type 订单类型 buy-market, sell-market, buy-limit, sell-limit
        @return order_no 订单id
        """
        account_id = await self._get_account_id()
        info = {
            "account-id": account_id,
            "price": price,
            "amount": quantity,
            "source": "api",
            "symbol": symbol,
            "type": order_type
        }
        if order_type == "buy-market" or order_type == "sell-market":
            info.pop("price")
        success, error = await self.request("POST", "/v1/order/orders/place", body=info)
        return success, error

    async def revoke_order(self, order_no):
        """ 撤销委托单
        @param order_no 订单id
        @return True/False
        """
        uri = "/v1/order/orders/{order_no}/submitcancel".format(order_no=order_no)
        success, error = await self.request("POST", uri)
        return success, error

    async def revoke_orders(self, order_nos):
        """ 批量撤销委托单
        @param order_nos 订单列表
        * NOTE: 单次不超过50个订单id
        """
        body = {
            "order-ids": order_nos
        }
        result = await self.request("POST", "/v1/order/orders/batchcancel", body=body)
        return result

    async def get_open_orders(self, symbol):
        """ 获取当前还未完全成交的订单信息
        @param symbol 交易对
        * NOTE: 查询上限最多500个订单
        """
        account_id = await self._get_account_id()
        params = {
            "account-id": account_id,
            "symbol": symbol,
            "size": 500
        }
        result = await self.request("GET", "/v1/order/openOrders", params=params)
        return result

    async def get_order_status(self, order_no):
        """ 获取订单的状态
        @param order_no 订单id
        """
        uri = "/v1/order/orders/{order_no}".format(order_no=order_no)
        success, error = await self.request("GET", uri)
        return success, error

    async def request(self, method, uri, params=None, body=None):
        """ 发起请求
        @param method 请求方法 GET POST
        @param uri 请求uri
        @param params dict 请求query参数
        @param body dict 请求body数据
        """
        url = urljoin(self._host, uri)
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        params = params if params else {}
        params.update({"AccessKeyId": self._access_key,
                       "SignatureMethod": "HmacSHA256",
                       "SignatureVersion": "2",
                       "Timestamp": timestamp})

        host_name = urllib.parse.urlparse(self._host).hostname.lower()
        params["Signature"] = self.generate_signature(method, params, host_name, uri)

        if method == "GET":
            headers = {
                "Content-type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/39.0.2171.71 Safari/537.36"
            }
        else:
            headers = {
                "Accept": "application/json",
                "Content-type": "application/json"
            }
        _, success, error = await AsyncHttpRequests.fetch(method, url, params=params, data=body, headers=headers,
                                                          timeout=10)
        if error:
            return success, error
        if success.get("status") != "ok":
            return None, success
        return success.get("data"), None

    def generate_signature(self, method, params, host_url, request_path):
        """ 创建签名
        """
        query = "&".join(["{}={}".format(k, parse.quote(str(params[k]))) for k in sorted(params.keys())])
        payload = [method, host_url, request_path, query]
        payload = "\n".join(payload)
        payload = payload.encode(encoding="utf8")
        secret_key = self._secret_key.encode(encoding="utf8")
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature


class HuobiTrade(Websocket):
    """ huobi Trade模块
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
            kwargs["host"] = "https://api.huobi.pro"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://api.huobi.pro"
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
        self._platform = HUOBI
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")

        self._raw_symbol = self._symbol.replace("/", "").lower()  # 转换成交易所对应的交易对格式
        self._order_channel = "orders.{}".format(self._raw_symbol)  # 订阅订单更新频道

        url = self._wss + "/ws/v1"
        super(HuobiTrade, self).__init__(url, send_hb_interval=0)

        self._assets = {}  # 资产 {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # 订单

        # 初始化 REST API 对象
        self._rest_api = HuobiRestAPI(self._host, self._access_key, self._secret_key)

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
    def rest_api(self):
        return self._rest_api

    async def connected_callback(self):
        """ 建立连接之后，授权登陆，然后订阅order和position
        """
        # 身份验证
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        params = {
            "AccessKeyId": self._access_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": timestamp
        }
        signature = self._rest_api.generate_signature("GET", params, "api.huobi.pro", "/ws/v1")
        params["op"] = "auth"
        params["Signature"] = signature
        await self.ws.send_json(params)

    async def _auth_success_callback(self):
        """ 授权成功之后回调
        """
        # 获取当前未完成订单
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            e = Error("get open orders error: {}".format(error))
            if self._init_success_callback:
                SingleTask.run(self._init_success_callback, False, e)
            return
        for order_info in success:
            data = {
                "order-id": order_info["id"],
                "order-type": order_info["type"],
                "order-state": order_info["state"],
                "unfilled-amount": float(order_info["amount"]) - float(order_info["filled-amount"]),
                "order-price": float(order_info["price"]),
                "price": float(order_info["price"]),
                "order-amount": float(order_info["amount"]),
                "created-at": order_info["created-at"],
                "utime": order_info["created-at"],
            }
            self._update_order(data)
        # 订阅订单更新数据
        params = {
            "op": "sub",
            "topic": self._order_channel
        }
        await self.ws.send_json(params)

    @async_method_locker("HuobiTrade.process_binary.locker")
    async def process_binary(self, raw):
        """ 处理websocket上接收到的消息
        @param raw 原始的压缩数据
        """
        msg = json.loads(gzip.decompress(raw).decode())
        logger.debug("msg:", msg, caller=self)

        op = msg.get("op")

        if op == "auth":  # 授权
            if msg["err-code"] != 0:
                e = Error("Websocket connection authorized failed: {}".format(msg))
                logger.error(e, caller=self)
                if self._init_success_callback:
                    SingleTask.run(self._init_success_callback, False, e)
                return
            logger.info("Websocket connection authorized successfully.", caller=self)
            await self._auth_success_callback()
        elif op == "ping":  # ping
            params = {
                "op": "pong",
                "ts": msg["ts"]
            }
            await self.ws.send_json(params)
        elif op == "sub":   # 订阅频道返回消息
            if msg["topic"] != self._order_channel:
                return
            if msg["err-code"] != 0:
                if self._init_success_callback:
                    e = Error("subscribe order event error: {}".format(msg))
                    SingleTask.run(self._init_success_callback, False, e)
            else:
                if self._init_success_callback:
                    SingleTask.run(self._init_success_callback, True, None)
        elif op == "notify":  # 订单更新通知
            if msg["topic"] != self._order_channel:
                return
            data = msg["data"]
            data["utime"] = msg["ts"]
            self._update_order(data)

    async def create_order(self, action, price, quantity, order_type=ORDER_TYPE_LIMIT, *args, **kwargs):
        """ 创建订单
        @param action 交易方向 BUY / SELL
        @param price 委托价格
        @param quantity 委托数量
        @param order_type 委托类型 LIMIT / MARKET
        """
        if action == ORDER_ACTION_BUY:
            if order_type == ORDER_TYPE_LIMIT:
                t = "buy-limit"
            elif order_type == ORDER_TYPE_MARKET:
                t = "buy-market"
            else:
                logger.error("order_type error! order_type:", order_type, caller=self)
                return None, "order type error"
        elif action == ORDER_ACTION_SELL:
            if order_type == ORDER_TYPE_LIMIT:
                t = "sell-limit"
            elif order_type == ORDER_TYPE_MARKET:
                t = "sell-market"
            else:
                logger.error("order_type error! order_type:", order_type, caller=self)
                return None, "order type error"
        else:
            logger.error("action error! action:", action, caller=self)
            return None, "action error"
        price = tools.float_to_str(price)
        quantity = tools.float_to_str(quantity)
        result, error = await self._rest_api.create_order(self._raw_symbol, price, quantity, t)
        return result, error

    async def revoke_order(self, *order_nos):
        """ 撤销订单
        @param order_nos 订单号列表，可传入任意多个，如果不传入，那么就撤销所有订单
        """
        # 如果传入order_nos为空，即撤销全部委托单
        if len(order_nos) == 0:
            order_nos, error = await self.get_open_order_nos()
            if error:
                return [], error
            if not order_nos:
                return [], None

        # 如果传入order_nos为一个委托单号，那么只撤销一个委托单
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(order_nos[0])
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # 如果传入order_nos数量大于1，那么就批量撤销传入的委托单
        if len(order_nos) > 1:
            s, e = await self._rest_api.revoke_orders(order_nos)
            if e:
                return [], e
            success = s["success"]
            error = s["failed"]
            return success, error

    async def get_open_order_nos(self):
        """ 获取未完全成交订单号列表
        """
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            return None, error
        else:
            order_nos = []
            for order_info in success:
                order_nos.append(order_info["id"])
            return order_nos, None

    def _update_order(self, order_info):
        """ 更新订单信息
        @param order_info 订单信息
        * NOTE:
            order-state: 订单状态, submitting , submitted 已提交, partial-filled 部分成交, partial-canceled 部分成交撤销,
                filled 完全成交, canceled 已撤销
        """
        order_no = str(order_info["order-id"])
        action = ORDER_ACTION_BUY if order_info["order-type"] in ["buy-market", "buy-limit"] else ORDER_ACTION_SELL
        state = order_info["order-state"]
        remain = "%.8f" % float(order_info["unfilled-amount"])
        avg_price = "%.8f" %  float(order_info["price"])
        ctime = order_info["created-at"]
        utime = order_info["utime"]

        if state == "canceled":
            status = ORDER_STATUS_CANCELED
        elif state == "partial-canceled":
            status = ORDER_STATUS_CANCELED
        elif state == "submitting":
            status = ORDER_STATUS_SUBMITTED
        elif state == "submitted":
            status = ORDER_STATUS_SUBMITTED
        elif state == "partial-filled":
            status = ORDER_STATUS_PARTIAL_FILLED
        elif state == "filled":
            status = ORDER_STATUS_FILLED
        else:
            logger.error("status error! order_info:", order_info, caller=self)
            return None

        order = self._orders.get(order_no)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_no": order_no,
                "action": action,
                "symbol": self._symbol,
                "price": "%.8f" % float(order_info["order-price"]),
                "quantity": "%.8f" % float(order_info["order-amount"]),
                "remain": remain,
                "status": status
            }
            order = Order(**info)
            self._orders[order_no] = order
        order.remain = remain
        order.status = status
        order.avg_price = avg_price
        order.ctime = ctime
        order.utime = utime
        if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_no)
        if order and self._order_update_callback:
            SingleTask.run(self._order_update_callback, copy.copy(order))

    async def on_event_asset_update(self, asset: Asset):
        """ 资产数据更新回调
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

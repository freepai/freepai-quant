# -*- coding:utf-8 -*-

"""
Coinsuper Trade 模块
https://github.com/coinsuperapi/API_docs

Author: HuangTao
Date:   2018/05/03
"""

import copy
import hashlib
from urllib.parse import urljoin

from quant.error import Error
from quant.utils import tools
from quant.utils import logger
from quant.const import COINSUPER
from quant.order import Order
from quant.asset import Asset, AssetSubscribe
from quant.tasks import SingleTask, LoopRunTask
from quant.utils.http_client import AsyncHttpRequests
from quant.utils.decorator import async_method_locker
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from quant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from quant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("CoinsuperRestAPI", "CoinsuperTrade", )


class CoinsuperRestAPI:
    """ Coinsuper REST API
    """

    def __init__(self, host, access_key, secret_key):
        """ 初始化
        @param host 请求的host
        @param access_key 请求的access_key
        @param secret_key 请求的secret_key
        """
        self._host = host
        self._access_key = access_key
        self._secret_key = secret_key

    async def get_user_account(self):
        """ 获取账户资金信息
        """
        data = {}
        success, error = await self.request("/api/v1/asset/userAssetInfo", data)
        return success, error

    async def create_order(self, action, symbol, price, quantity, order_type=ORDER_TYPE_LIMIT):
        """ 创建订单
        @param action 操作类型 BUY SELL
        @param symbol 交易对
        @param price 交易价格
        @param quantity 交易量
        @param order_type 交易类型 LMT 限价单 / MKT 市价单
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
        """ 撤销委托单
        @param order_no 订单号
        """
        data = {
            "orderNo": order_no
        }
        success, error = await self.request("/api/v1/order/cancel", data)
        return success, error

    async def revoke_orders(self, order_nos):
        """ 批量撤销委托单
        @param order_nos 订单号列表
        """
        data = {
            "orderNoList": ",".join(order_nos)
        }
        success, error = await self.request("/api/v1/order/batchCancel", data)
        return success, error

    async def get_order_list(self, order_nos):
        """ 获取用户委托列表(单次查询最大限50条记录)
        @param order_nos 订单号id列表
        """
        data = {
            "orderNoList": ",".join(order_nos)
        }
        success, error = await self.request("/api/v1/order/list", data)
        return success, error

    async def get_order_details(self, order_nos):
        """ 根据委托单号，查询委托单交易详情
        @param order_nos 订单号id列表
        """
        data = {
            "orderNoList": ",".join(order_nos)
        }
        success, error = await self.request("/api/v1/order/details", data)
        return success, error

    async def get_open_order_nos(self, symbol=None, num=1000):
        """ 请求最新挂单单号列表(时间最近的委托单单号列表)
        @param symbol 交易对
        @param num 最多获取条数，默认1000条
        """
        data = {
            "num": num
        }
        if symbol:
            data["symbol"] = symbol
        success, error = await self.request("/api/v1/order/openList", data)
        return success, error

    async def get_history_orders(self, symbol, start, end, start_order_no=None, with_trade="true", size=100):
        """ 获取当前还未完全成交的订单信息
        @param symbol 交易对
        @param start 开始时间戳(毫秒)
        @param end 结束时间戳(毫秒)
        @param start_order_no 起始委托单号（查询结果中不含该单号的数据，不传则表示查第一页数据）
        @param with_trade 是否需要返回对应委托单的交易明细（true-返回，false-不返回（小写））
        @param size 查询条数(取值范围暂定为1~100)
        """
        data = {
            "symbol": symbol,
            "utcStart": str(start),
            "utcEnd": str(end),
            "withTrade": with_trade,
            "size": str(size)
        }
        if start_order_no:
            data["StartOrderNo"] = str(start_order_no)
        success, error = await self.request("/api/v1/order/history", data)
        return success, error

    async def get_kline(self, symbol, num=300, _range="5min"):
        """ 获取K线数据
        @param symbol 交易对
        @param num 获取最大条数，最大300条
        @param _range K线类型 5min,15min,30min,1hour,6hour,12hour,1day 默认值为5min
        """
        data = {
            "symbol": symbol,
            "num": num,
            "range": _range
        }
        success, error = await self.request("/api/v1/market/kline", data)
        return success, error

    async def get_ticker(self, symbol):
        """ 获取ticker行情
        @param symbol 交易对
        """
        data = {
            "symbol": symbol
        }
        success, error = await self.request("/api/v1/market/tickers", data)
        return success, error

    async def get_orderbook(self, symbol, length=10):
        """ 获取订单薄行情
        @param symbol 交易对
        @param length 订单薄长度
        """
        data = {
            "symbol": symbol,
            "num": length
        }
        success, error = await self.request("/api/v1/market/orderBook", data)
        return success, error

    async def request(self, uri, data):
        """ 发起请求
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
        trace_id = md5_str[:16]  # 16位的随机字符串
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


class CoinsuperTrade:
    """ Coinsuper Trade module
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
            kwargs["host"] = "https://api.coinsuper.com"
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
        self._platform = COINSUPER
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_success_callback = kwargs.get("init_success_callback")
        self._check_order_interval = kwargs.get("check_order_interval", 2)  # 检查订单状态更新时间间隔(秒)，默认2秒

        self._raw_symbol = self._symbol  # 原始交易对

        self._assets = {}  # 资产 {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # 订单

        # 初始化 REST API 对象
        self._rest_api = CoinsuperRestAPI(self._host, self._access_key, self._secret_key)

        # 循环更新订单状态
        LoopRunTask.register(self._check_order_update, self._check_order_interval)

        # 初始化资产订阅
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
        """ 初始化
        """
        # 获取当前所有未完全成交的订单
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
        """ 创建订单
        @param action 交易方向 BUY/SELL
        @param price 委托价格
        @param quantity 委托数量
        @param order_type 委托类型 LIMIT / MARKET
        """
        if action not in [ORDER_ACTION_BUY, ORDER_ACTION_SELL]:
            return None, "action error"
        if order_type not in [ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT]:
            return None, "order_type error"

        # 创建订单
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
        """ 撤销订单
        @param order_nos 订单号列表，可传入任意多个，如果不传入，那么就撤销所有订单
        """
        # 如果传入order_nos为空，即撤销全部委托单
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

        # 如果传入order_nos为一个委托单号，那么只撤销一个委托单
        if len(order_nos) == 1:
            success, error = await self._rest_api.revoke_order(order_nos[0])
            if error:
                return order_nos[0], error
            else:
                return order_nos[0], None

        # 如果传入order_nos数量大于1，那么就批量撤销传入的委托单
        if len(order_nos) > 1:
            success, error = await self._rest_api.revoke_orders(order_nos)
            if error:
                return None, error
            if len(success["failResultList"]) > 0:
                return success["successNoList"], success["failResultList"]
            else:
                return success["successNoList"], None

    async def get_open_order_nos(self):
        """ 获取未完全成交订单号列表
        """
        success, error = await self._rest_api.get_open_order_nos(self._raw_symbol)
        return success, error

    async def _check_order_update(self, *args, **kwargs):
        """ 检查订单更新
        """
        # 获取需要查询的订单列表
        order_nos = list(self._orders.keys())
        if not order_nos:  # 暂时没有需要更新的委托单
            return

        # 获取订单最新状态，每次最多请求50个订单
        while order_nos:
            nos = order_nos[:50]
            success, error = await self._rest_api.get_order_list(nos)
            if error:
                return
            for order_info in success:
                await self._update_order(order_info)
            order_nos = order_nos[50:]

    @async_method_locker("CoinsuperTrade.order.locker")
    async def _update_order(self, order_info):
        """ 处理委托单更新
        @param order_info 委托单详情
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

        # 已提交
        if state == "UNDEAL" or state == "PROCESSING":
            if order.status != ORDER_STATUS_SUBMITTED:
                order.status = ORDER_STATUS_SUBMITTED
                status_updated = True
        # 订单部分成交
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
        # 订单成交完成
        elif state == "DEAL":
            order.status = ORDER_STATUS_FILLED
            order.remain = 0
            status_updated = True
        # 订单取消
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

        # 有状态更新 执行回调
        if status_updated:
            order.ctime = order_info["utcCreate"]
            order.utime = order_info["utcUpdate"]
            if self._order_update_callback:
                SingleTask.run(self._order_update_callback, copy.copy(order))

        # 删除已完成订单
        if order.status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_no)

    async def on_event_asset_update(self, asset: Asset):
        """ 资产数据更新回调
        """
        self._assets = asset
        SingleTask.run(self._asset_update_callback, asset)

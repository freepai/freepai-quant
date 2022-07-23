# -*- coding:utf-8 -*-

# 策略实现

from quant import const
from quant.utils import tools
from quant.utils import logger
from quant.config import config
from quant.market import Market
from quant.trade import Trade
from quant.const import BINANCE
from quant.order import Order
from quant.market import Orderbook
from quant.order import ORDER_ACTION_BUY, ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED


class MyStrategy:

    def __init__(self):
        """ 初始化
        """
        self.strategy = "my_strategy"
        self.platform = BINANCE
        self.account = config.accounts[0]["account"]
        self.access_key = config.accounts[0]["access_key"]
        self.secret_key = config.accounts[0]["secret_key"]
        self.symbol = config.symbol

        self.order_no = None  # 创建订单的id
        self.create_order_price = "0.0"  # 创建订单的价格

        # 交易模块
        cc = {
            "strategy": self.strategy,
            "platform": self.platform,
            "symbol": self.symbol,
            "account": self.account,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "order_update_callback": self.on_event_order_update,
        }
        self.trader = Trade(**cc)

        # 订阅行情
        Market(const.MARKET_TYPE_ORDERBOOK, const.BINANCE, self.symbol, self.on_event_orderbook_update)

    async def on_event_orderbook_update(self, orderbook: Orderbook):
        """ 订单薄更新
        """
        logger.debug("orderbook:", orderbook, caller=self)
        bid3_price = orderbook.bids[2][0]  # 买三价格
        bid4_price = orderbook.bids[3][0]  # 买四价格

        # 判断是否需要撤单
        if self.order_no:
            if float(self.create_order_price) < float(bid3_price) or float(self.create_order_price) > float(bid4_price):
                return
            _, error = await self.trader.revoke_order(self.order_no)
            if error:
                logger.error("revoke order error! error:", error, caller=self)
                return
            self.order_no = None
            logger.info("revoke order:", self.order_no, caller=self)

        # 创建新订单
        new_price = (float(bid3_price) + float(bid4_price)) / 2
        quantity = "0.1"  # 假设委托数量为0.1
        action = ORDER_ACTION_BUY
        price = tools.float_to_str(new_price)
        quantity = tools.float_to_str(quantity)
        order_no, error = await self.trader.create_order(action, price, quantity)
        if error:
            logger.error("create order error! error:", error, caller=self)
            return
        self.order_no = order_no
        self.create_order_price = price
        logger.info("create new order:", order_no, caller=self)

    async def on_event_order_update(self, order: Order):
        """ 订单状态更新
        """
        logger.info("order update:", order, caller=self)

        # 如果订单失败、订单取消、订单完成交易
        if order.status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self.order_no = None

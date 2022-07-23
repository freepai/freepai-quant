# -*- coding:utf-8 -*-

"""
Binance 模块使用演示

为了在订单薄买盘提前埋伏订单，在 `BTC/USDT` 订单薄盘口距离10美金的位置挂买单，数量量为1。
随着订单薄盘口价格不断变化，需要将价格已经偏离的订单取消，再重新挂单，使订单始终保持距离盘口价差为 `10 ± 1` 美金。
这里设置了缓冲价差为 `1` 美金，即只要盘口价格变化在 `± 1` 内，都不必撤单之后重新挂单，这样设置的目的是尽量减少挂撤单的次数，
因为交易所开放的交易接口有调用频率的限制，如果调用太过频繁超过了限制可能会报错。
"""

import sys

from quant import const
from quant.utils import tools
from quant.utils import logger
from quant.config import config
from quant.market import Market
from quant.trade import Trade
from quant.order import Order
from quant.market import Orderbook
from quant.order import ORDER_ACTION_BUY, ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED


class MyStrategy:

    def __init__(self):
        """ 初始化
        """
        self.strategy = config.strategy
        self.platform = const.BINANCE
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
            "order_update_callback": self.on_event_order_update
        }
        self.trader = Trade(**cc)

        # 订阅行情
        Market(const.MARKET_TYPE_ORDERBOOK, self.platform, self.symbol, self.on_event_orderbook_update)

    async def on_event_orderbook_update(self, orderbook: Orderbook):
        """ 订单薄更新
        """
        logger.debug("orderbook:", orderbook, caller=self)
        ask1_price = float(orderbook.asks[0][0])  # 卖一价格
        bid1_price = float(orderbook.bids[0][0])  # 买一价格
        price = (ask1_price + bid1_price) / 2  # 为了方便，这里假设盘口价格为 卖一 和 买一 的平均值

        # 判断是否需要撤单
        if self.order_no:
            if (self.create_order_price + 10 > price - 1) and (self.create_order_price + 10 < price + 1):
                return
            _, error = await self.trader.revoke_order(self.order_no)
            if error:
                logger.error("revoke order error! error:", error, caller=self)
                return
            self.order_no = None
            logger.info("revoke order:", self.order_no, caller=self)

        # 创建新订单
        new_price = price + 10
        quantity = "1"  # 委托数量为1
        action = ORDER_ACTION_BUY
        new_price = tools.float_to_str(new_price)  # 将价格转换为字符串，保持精度
        quantity = tools.float_to_str(quantity)  # 将数量转换为字符串，保持精度
        order_no, error = await self.trader.create_order(action, new_price, quantity)
        if error:
            logger.error("create order error! error:", error, caller=self)
            return
        self.order_no = order_no
        self.create_order_price = float(new_price)
        logger.info("create new order:", order_no, caller=self)

    async def on_event_order_update(self, order: Order):
        """ 订单状态更新
        """
        logger.info("order update:", order, caller=self)

        # 如果订单失败、订单取消、订单完成交易
        if order.status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self.order_no = None


def main():
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = None

    from quant.quant import quant
    quant.initialize(config_file)
    MyStrategy()
    quant.start()


if __name__ == '__main__':
    main()

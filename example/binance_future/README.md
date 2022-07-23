
## Binance Future

本文主要介绍如何通过框架SDK开发 [Binance Future](https://binanceapitest.github.io/Binance-Futures-API-doc) 交易所的交易系统。

### 1. 准备条件

在开发策略之前，需要先对整套系统的运行原理有一个大致的了解，以及相应的开发环境和运行环境。

- Python3.x开发环境，并安装好 `thenextquant` 开发包；
- 部署 [RabbitMQ 事件中心服务](../../docs/others/rabbitmq_deploy.md) ---- 事件中心的核心组成部分；
- 部署 [Market 行情服务](https://github.com/TheNextQuant/Market) ---- 订阅行情事件，如果策略不需要行情数据，那么此服务可以不用部署；
- 部署 [Asset 资产服务](https://github.com/TheNextQuant/Asset) ---- 账户资产更新事件推送，如果策略不需要账户资产信息，那么此服务可以不用部署；
- 注册 [Binance Future](https://www.binance-cn.com/cn/futures/BTCUSDT)  的账户，并且创建 `ACCESS KEY` 和 `SECRET KEY`，AK有操作委托单权限；


### 2. 一个简单的策略

> 我们选用的交易对(合约)为 `BTCUSDT`， 策略执行的几个步骤:  
- 在当前盘口价差10美金的位置，挂一个买入10手的委托单，即开仓大小为10；
- 委托单成功成交之后，即持多仓大小10；
- 程序设置5分钟倒计时平仓，即开仓5分钟后平仓(为了简单此处按市价平仓)；
- 平仓成功之后，程序退出；

> 注意：这里只是演示框架的基本功能，包含挂单、撤单、查看订单状态等，不涉及具体策略以及盈亏。


##### 2.1 导入必要的模块

```python
import sys

from quant import const
from quant.utils import tools
from quant.utils import logger
from quant.config import config
from quant.market import Market
from quant.trade import Trade
from quant.order import Order
from quant.market import Orderbook
from quant.position import Position
from quant.tasks import LoopRunTask
from quant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL, ORDER_STATUS_FILLED
```

##### 2.1 策略逻辑代码

- 创建一个策略逻辑的类 ---- MyStrategy

```python
class MyStrategy:

    def __init__(self):
        """ 初始化
        """
        self.strategy = config.strategy
        self.platform = const.BINANCE_FUTURE
        self.account = config.accounts[0]["account"]
        self.access_key = config.accounts[0]["access_key"]
        self.secret_key = config.accounts[0]["secret_key"]
        self.symbol = config.symbol

        self.buy_open_order_no = None  # 开仓做多订单号
        self.buy_open_quantity = "10"  # 开仓数量(USD)
        self.sell_close_order_no = None  # 多仓平仓订单号
        self.sell_close_time_down = 0  # 平仓倒计时

        self.current_price = None  # 当前盘口价格，为了方便，这里假设盘口价格为 卖一 和 买一 的平均值

        # 交易模块
        cc = {
            "strategy": self.strategy,
            "platform": self.platform,
            "symbol": self.symbol,
            "account": self.account,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "order_update_callback": self.on_event_order_update,
            "position_update_callback": self.on_event_position_update
        }
        self.trader = Trade(**cc)

        # 订阅行情
        Market(const.MARKET_TYPE_ORDERBOOK, self.platform, self.symbol, self.on_event_orderbook_update)

        # 注册系统循环回调
        LoopRunTask.register(self.on_ticker, 1)  # 每隔1秒执行一次回调
```

> 在这里，我们创建了策略类 `MyStrategy`，初始化的时候设置了必要的参数、初始化交易模块、订阅相关的订单薄行情数据、注册系统循环回调。

- 订单薄更新回调

我们通过 `Market` 模块订阅订单薄行情，并且设置了订单薄更新回调函数 `self.on_event_orderbook_update`，订单薄数据将实时从交易所服务器更新并推送至此函数，
我们需要根据订单薄数据的实时价格，来创建委托单。

```python
    async def on_event_orderbook_update(self, orderbook: Orderbook):
        """ 订单薄更新
        """
        logger.debug("orderbook:", orderbook, caller=self)
        ask1_price = float(orderbook.asks[0][0])  # 卖一价格
        bid1_price = float(orderbook.bids[0][0])  # 买一价格
        self.current_price = (ask1_price + bid1_price) / 2  # 为了方便，这里假设盘口价格为 卖一 和 买一 的平均值

        # 如果没有挂单，那么执行挂单
        if not self.buy_open_order_no:
            price = self.current_price - 10
            quantity = self.buy_open_quantity
            action = ORDER_ACTION_BUY
            new_price = tools.float_to_str(price)  # 将价格转换为字符串，保持精度
            order_no, error = await self.trader.create_order(action, new_price, quantity)
            if error:
                logger.error("create order error! error:", error, caller=self)
                return
            self.buy_open_order_no = order_no
            logger.info("create buy open order:", order_no, caller=self)
```
> 这里是关于 [行情对象](../../docs/market.md) 的详细说明。 

- 订单更新回调

当我们创建订单、订单状态有任何的变化，都将通过 `self.on_event_order_update` 函数返回订单对象。

```python
    async def on_event_order_update(self, order: Order):
        """ 订单状态更新
        """
        logger.info("order update:", order, caller=self)

        if order.status == ORDER_STATUS_FILLED:
            if order.order_no == self.buy_open_order_no:  # 开仓委托单已经完全成交
                logger.info("buy open completed.", caller=self)
                self.sell_close_time_down = 60 * 5  # 设置平仓倒计时 5分钟
            if order.order_no == self.sell_close_order_no:  # 平仓委托单已经完全成交
                logger.info("sell close completed.", caller=self)
                exit(0)
```
> 这里是关于 [订单对象](../../docs/trade.md) 的详细说明。   

> 注意: 
> 1. 这里我们只判断了订单是否已完全成交(订单还包含别的状态，比如已提交、部分成交、取消、失败等)；
> 2. 已成交的订单，是否是开仓订单；如果是开仓订单，那么设置平仓倒计时为5分钟；
> 3. 已成交的订单，是否是平仓订单；如果是平仓订单，那么此策略的任务已完成，程序退出；

- 持仓更新回调

当委托单有成交的时候，对应的持仓会实时更新并通过回调函数将持仓信息反馈给策略。

```python
    async def on_event_position_update(self, position: Position):
        """ 持仓更新
        """
        logger.info("position:", position, caller=self)
```

> 这里是关于 [持仓对象](../../docs/trade.md) 的详细说明。

- 系统循环回调

我们在初始化的时候注册了系统循环回调，这里有关于 [循环回调](../../docs/others/tasks.md) 的详细说明。
初始化的时候我们注册了系统循环回调:

```python
    # 注册系统循环回调
    LoopRunTask.register(self.on_ticker, 1)  # 每隔1秒执行一次回调
```

我们在 `self.on_ticker` 回调函数里，执行了一个检查：即平仓倒计时检查。

```python
    async def on_ticker(self, *args, **kwargs):
        """ 系统循环回调，每秒钟执行一次
        """
        logger.info("do ticker ...", caller=self)
        if self.sell_close_time_down > 0:
            self.sell_close_time_down -= 1
            if self.sell_close_time_down <= 0:
                price = self.current_price - 2  # 当前盘口价格再减去2，尽量保证可以快速成交
                new_price = tools.float_to_str(price)  # 将价格转换为字符串，保持精度
                order_no, error = await self.trader.create_order(ORDER_ACTION_SELL, new_price, self.buy_open_quantity)
                if error:
                    logger.error("create order error! error:", error, caller=self)
                    return
                logger.info("create sell close order:", order_no, caller=self)
```

> 利用系统每秒执行一次的回调操作，我们设置倒计时，在倒计时结束之后，执行平仓操作。


##### 2.2 程序入口

我们的策略逻辑已经完成，现在我们需要初始化 `thenextquant` 框架，并加载我们的策略，让底层框架驱动策略运行起来。

```python
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
```

> 我们首先判断程序运行的第一个参数是否指定了配置文件，配置文件一般为 `config.json` 的json文件，如果没有指定配置文件，那么就设置配置文件为None。
其次，我们导入 `quant` 模块，调用 `quant.initialize(config_file)` 初始化配置，紧接着执行 `MyStrategy()` 初始化策略，最后执行 `quant.start()` 启动整个程序。


##### 2.3 配置文件

我们在配置文件里，加入了如下配置:
- RABBITMQ 指定事件中心服务器，此配置需要和 [Market 行情服务](https://github.com/TheNextQuant/Market) 、[Asset 资产服务](https://github.com/TheNextQuant/Asset) 一致；
- PROXY HTTP代理，翻墙，你懂的；（如果在不需要翻墙的环境运行，此参数可以去掉）
- ACCOUNTS 指定需要使用的交易账户，注意platform是 `binance_future`；
- strategy 策略的名称；
- symbol 策略运行的交易对(合约)，比如: `BTCUSDT` ；

配置文件比较简单，更多的配置可以参考 [配置文件说明](../../docs/configure/README.md)。


### 3. 启动程序

以上，我们介绍了如何使用 `thenextquant` 开发自己的策略，这里是完整的 [策略代码](./main.py) 以及 [配置文件](./config.json)。

现在让我们来启动程序:
```text
python src/main.py config.json
```

是不是非常简单，Enjoy yourself! 


### 4. 参考文档

- [config 服务配置](../../docs/configure/README.md)
- [Market 行情](../../docs/market.md)
- [Trade 交易](../../docs/trade.md)
- [Asset 资产](https://github.com/TheNextQuant/Asset)
- [EventCenter 安装RabbitMQ](../../docs/others/rabbitmq_deploy.md)
- [Logger 日志打印](../../docs/others/logger.md)
- [Tasks 协程任务](../../docs/others/tasks.md)

- [框架使用系列教程](https://github.com/TheNextQuant/Documents)
- [Python Asyncio](https://docs.python.org/3/library/asyncio.html)

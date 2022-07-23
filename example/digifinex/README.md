
## Digifinex

本文主要介绍如何通过框架SDK开发 [Digifinex](https://digifinex.vip/) 交易所的交易系统。

### 1. 准备条件

在开发策略之前，需要先对整套系统的运行原理有一个大致的了解，以及相应的开发环境和运行环境。

- Python3.x开发环境，并安装好 `thenextquant` 开发包；
- 部署 [RabbitMQ 事件中心服务](../../docs/others/rabbitmq_deploy.md) ---- 事件中心的核心组成部分；
- 部署 [Market 行情服务](https://github.com/TheNextQuant/Market) ---- 订阅行情事件，如果策略不需要行情数据，那么此服务可以不用部署；
- 部署 [Asset 资产服务](https://github.com/TheNextQuant/Asset) ---- 账户资产更新事件推送，如果策略不需要账户资产信息，那么此服务可以不用部署；
- 注册 [Digifinex](https://digifinex.vip/) 的账户，并且创建 `ACCESS KEY` 和 `SECRET KEY`，AK有操作委托单权限；


### 2. 一个简单的策略

为了在订单薄买盘提前埋伏订单，在 `BTC/USDT` 订单薄盘口距离10美金的位置挂买单，数量为1。
随着订单薄盘口价格不断变化，需要将价格已经偏离的订单取消，再重新挂单，使订单始终保持距离买盘盘口价差为 `10 ± 1` 美金。
这里设置了缓冲价差为 `1` 美金，即只要盘口价格变化在 `± 1` 美金内，都不必撤单之后重新挂单，这样设置的目的是尽量减少挂撤单的次数，因为交易所开放的交易接口有调用频率的限制，
如果调用太过频繁超过了限制可能会报错。


比如： 当前订单薄价格盘口价格为 8500.5，那么我们需要在 8490.5 的位置挂一个单买，数量为1。
如果此时订单薄价格变化为 8520.6，那么我们需要取消之前的订单，再重新在 8510.6 的位置挂一个买单，数量为1。

> 注意：这里只是演示框架的基本功能，包含挂单、撤单、查看订单状态等，不涉及具体策略以及盈亏。


##### 2.1 导入必要的模块

```python
import sys

from quant import const  # 必要的常量
from quant.utils import tools  # 工具集合
from quant.utils import logger  # 日志打印模块
from quant.config import config  # 系统加载的配置，根据 config.json 配置文件初始化
from quant.market import Market  # 行情模块
from quant.trade import Trade  # 交易模块
from quant.order import Order  # 订单模块
from quant.market import Orderbook  # 订单薄模块
from quant.order import ORDER_ACTION_BUY, ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED  # 订单属性常量
```

##### 2.1 策略逻辑代码

- 创建一个策略逻辑的类 ---- MyStrategy

```python
class MyStrategy:

    def __init__(self):
        """ 初始化
        """
        self.strategy = config.strategy
        self.platform = const.DIGIFINEX
        self.account = config.accounts[0]["account"]
        self.access_key = config.accounts[0]["access_key"]
        self.secret_key = config.accounts[0]["secret_key"]
        self.symbol = config.symbol

        self.order_no = None  # 创建订单的id
        self.create_order_price = "0.0"  # 创建订单的价格

        # 初始化交易模块，设置订单更新回调函数 self.on_event_order_update
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

        # 订阅行情，设置订单薄更新回调函数 self.on_event_orderbook_update
        Market(const.MARKET_TYPE_ORDERBOOK, const.platform, self.symbol, self.on_event_orderbook_update)
```

> 在这里，我们创建了策略类 `MyStrategy`，初始化的时候设置了必要的参数、初始化交易模块、订阅相关的订单薄行情数据。

- 订单薄更新回调

我们通过 `Market` 模块订阅订单薄行情，并且设置了订单薄更新回调函数 `self.on_event_orderbook_update`，订单薄数据将实时从服务器更新
并推送至此函数，我们需要根据订单薄数据的实时更新，来实时调整我们的挂单位置。

```python
    async def on_event_orderbook_update(self, orderbook: Orderbook):
        """ 订单薄更新
        """
        logger.debug("orderbook:", orderbook, caller=self)
        ask1_price = float(orderbook.asks[0][0])  # 卖一价格
        bid1_price = float(orderbook.bids[0][0])  # 买一价格
        price = (ask1_price + bid1_price) / 2  # 为了方便，这里假设盘口价格为 `卖一` 和 `买一` 的平均值

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
```
> 这里是关于 [行情对象](../../docs/market.md) 的详细说明。

- 订单更新回调

当我们创建订单、订单状态有任何的变化，都将通过 `self.on_event_order_update` 函数返回订单对象。

```python
    async def on_event_order_update(self, order: Order):
        """ 订单状态更新
        """
        logger.info("order update:", order, caller=self)

        # 如果订单失败、订单取消、订单完成交易
        if order.status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self.order_no = None
```
> 这里是关于 [订单对象](../../docs/trade.md) 的详细说明。  

> 注意: 
当订单的生命周期结束之后(订单失败、订单取消、订单完成)，我们需要重置订单号为空(self.order_no = None)，然后进入接下来的挂单逻辑;


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
- ACCOUNTS 指定需要使用的交易账户，注意platform是 `digifinex` ；
- strategy 策略的名称；
- symbol 策略运行的交易对；

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

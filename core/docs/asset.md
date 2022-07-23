## 资产

通过资产模块(asset)，可以订阅任意交易平台、任意交易账户的任意资产信息。

订阅 `资产事件` 之前，需要先部署 [Asset 资产服务器](https://github.com/TheNextQuant/Asset)，将需要订阅的资产信息配置到资产服务器，
资产服务器定时(默认10秒)将最新的资产信息通过 `资产事件` 的形式推送至 `事件中心` ，我们只需要订阅相关 `资产事件` 即可。


### 1. 资产模块使用

> 此处以订阅 `Binance(币安)` 交易平台的资产为例，假设我们的账户为 `test@gmail.com`。
```python
from quant.utils import logger
from quant.const import BINANCE
from quant.asset import Asset, AssetSubscribe


# 资产信息回调函数，注意此处回调函数是 `async` 异步函数，回调参数为 `asset Asset` 对象，数据结构请查看下边的介绍。
async def on_event_asset_update(asset: Asset):
    logger.info("platform:", asset.platform)  # 打印资产数据的平台信息
    logger.info("account:", asset.account)  # 打印资产数据的账户信息
    logger.info("asset data dict:", asset.assets)  # 打印资产数据的资产详情
    logger.info("asset data str:", asset.data)  # 打印资产数据的资产详情
    logger.info("timestamp:", asset.timestamp)  # 打印资产数据更新时间戳
    logger.info("update:", asset.update)  # 打印资产数据是否有更新


# 订阅资产信息
account = "test@gmail.com"
AssetSubscribe(BINANCE, account, on_event_asset_update)
```

> 以上订阅资产数据的方式是比较通用的做法，但如果你使用了 [Trade 交易模块](./trade.md)，那么通过初始化 `Trade` 模块即可订阅相应的资产数据。


### 2. 资产对象数据结构

- 资产模块
```python
from quant.asset import Asset

Asset.platform  # 交易平台名称
Asset.account  # 交易账户
Asset.assets  # 资产详细信息
Asset.timestamp  # 资产更新时间戳(毫秒)
Asset.update  # 资产是否有更新
Asset.data  # 资产信息
```

- 资产详细信息数据结构(assets)

> 资产数据结果比较简单，一个只有2层的json格式数据结构，`key` 是资产里币种名称大写字母，`value` 是对应币种的数量。

```json
{
    "BTC": {
        "free": "1.10000",
        "locked": "2.20000",
        "total": "3.30000"
    },
    "ETH": {
        "free": "1.10000",
        "locked": "2.20000",
        "total": "3.30000"
    }
}
```

- 字段说明
    - free `string` 可用资产
    - locked `string` 冻结资产
    - total `string` 总资产

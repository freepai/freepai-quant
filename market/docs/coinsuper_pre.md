
## Coinsuper Premium 行情

Coinsuper Premium的行情数据根据 [Coinsuper Premium](https://premium.coinsuper.com/api/docs/v1/api_en.html) 提供的方式，
通过REST API协议，获取Coinsuper Premium官网的行情数据。然后程序将源数据经过适当打包处理，并通过行情事件的形式发布到事件中心。

当前行情服务器能够收集Coinsuper Premium的行情数据包括：Orderbook(订单薄)、Trade(成交)、Kline(K线)。

##### 1. 服务配置

配置文件需要指定一些基础参数来告诉行情服务器应该做什么，一个完整的配置文件大致如下:

```json
{
    "LOG": {
        "console": true,
        "level": "DEBUG",
        "path": "/data/logs/servers/Market",
        "name": "market.log",
        "clear": true,
        "backup_count": 5
    },
    "RABBITMQ": {
        "host": "127.0.0.1",
        "port": 5672,
        "username": "test",
        "password": "213456"
    },
    "PROXY": "http://127.0.0.1:1087",

    "ACCOUNTS": [
        {
            "platform": "coinsuper_pre",
            "account": "test@gmail.com",
            "access_key": "abc1234",
            "secret_key": "abc1234"
        }
    ],

    "MARKETS": {
        "coinsuper_pre": {
            "symbols": [
                "BTC/USD"
            ],
            "channels": [
                "kline_5min", "kline_15m", "orderbook", "trade"
            ],
            "orderbook_interval": 2,
            "orderbook_length": 10,
            "trade_interval": 5
        }
    }
}
```
以上配置表示：订阅 `coinsuper_pre` 交易所里，交易对 `BTC/USD` 的 `kline_5min 5分钟K线` 、`kline_15m 15分钟K线` 、`orderbook 订单薄` 和 `trade 成交` 行情数据。

> 特别注意: 配置文件中需要配置 `ACCOUNTS` 并且包含 `coinsuper_pre` 的账户。

> 配置文件可以参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。
> 此处对 `MARKETS` 下的关键配置做一下说明:
- MARKETS `dict` 需要配置的交易平台，key为交易平台名称，value为对应的行情配置
- coinsuper_pre `dict` 交易平台行情配置
- symbols `list` 需要订阅行情数据的交易对，可以是一个或多个，注意此处配置的交易对都需要大写字母，交易对之间包含斜杠
- channels `list` 需要订阅的行情类型，可以是一个或多个，其中： kline_5m 5分钟K线 / kline_15m 15分钟K线 / orderbook 订单薄 / trade 成交
- orderbook_interval `int` `Orderbook` 行情推送时间间隔(秒)，`可选，默认2秒`
- orderbook_length `int` `Orderbook` 行情推送长度，`可选，默认10`
- trade_interval `int` `Trade` 行情推送时间间隔(秒)，`可选，默认5秒`


> 注意: 配置文件里 `symbols` 交易对数量不宜太多(最好不要超过10个)，因为使用REST API拉取数据，请求频率有限制； 

> 其它：
- [orderbook 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#21-%E8%AE%A2%E5%8D%95%E8%96%84orderbook)
- [Kline 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#22-k%E7%BA%BFkline)
- [Trade 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#23-%E6%88%90%E4%BA%A4trade)

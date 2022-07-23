
## Huobi Future Market Server

Huobi Future 的行情数据根据 [Huobi Future](https://github.com/huobiapi/API_Docs/wiki/WS_api_reference_Derivatives) 提供的方式，
通过websocket协议，订阅 Huobi Future 官方实时推送的行情数据。然后程序将源数据经过适当打包处理，并通过行情事件的形式发布到事件中心。

当前行情服务器能够收集 Huobi Future 的行情数据包括：Orderbook(订单薄)。

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

    "MARKETS": {
        "huobi_future": {
            "symbols": [
                "BTC_CW",
                "BTC_NW",
                "BTC_CQ"
            ],
            "channels": [
                "orderbook"
            ],
            "orderbook_length": 10
        }
    }
}
```
以上配置表示：订阅 `huobi_future` 交易所里，交易对 `BTC_CW` 和 `BTC_NW` 和 `BTC_CQ` 的 `orderbook 订单薄` 行情数据。

> 配置文件可以参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。
> 此处对 `MARKETS` 下的关键配置做一下说明:
- MARKETS `dict` 需要配置的交易平台，key为交易平台名称，value为对应的行情配置
- huobi_future `dict` 交易平台名称
- symbols `list` 需要订阅行情数据的交易对，可以是一个或多个，如 `BTC_CW` 表示BTC当周合约，`BTC_NW` 表示BTC次周合约，`BTC_CQ` 表示BTC季度合约
- channels `list` 需要订阅的行情类型 `orderbook 订单薄` 、`trade 成交`
- orderbook_length `int` 需要收集的订单薄长度，`可选，默认为10，最大20`


> 其它：
- [orderbook 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#21-%E8%AE%A2%E5%8D%95%E8%96%84orderbook)

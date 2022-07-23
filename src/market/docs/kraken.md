
## Kraken Market

Kraken 的行情数据根据 [Kraken官方文档](https://www.kraken.com/en-us/features/websocket-api) 提供的方式，
通过websocket协议，订阅 Kraken 官方实时推送的行情数据。然后程序将源数据经过适当打包处理，并通过行情事件的形式发布到事件中心。

当前行情服务器能够收集 Kraken 的行情数据包括：Orderbook(订单薄)、Trade(成交)。

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
        "kraken": {
            "wss": "wss://ws.kraken.com",
            "symbols": [
                "XBT/USD"
            ],
            "channels": [
                "orderbook", "trade"
            ],
            "orderbook_interval": 2,
            "orderbook_length": 10
        }
    }
}
```
以上配置表示：订阅 `kraken` 交易所里，交易对 `XBT/USD` 的 `orderbook 订单薄` 和 `trade 成交` 行情数据。

> 配置文件可以参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。
> 此处对 `MARKETS` 下的关键配置做一下说明:
- MARKETS `dict` 需要配置的交易平台，key为交易平台名称，value为对应的行情配置
- kraken `dict` 交易平台行情配置
- wss `string` kraken服务器的wss地址，`可选，默认为 "wss://ws.kraken.com"`
- symbols `list` 需要订阅行情数据的交易对，可以是一个或多个，注意此处配置的交易对都需要大写字母，交易对之间包含斜杠
- channels `list` 需要订阅的行情类型，可以是一个或多个，其中：orderbook 订单薄 / trade 成交
- orderbook_interval `int` `Orderbook` 行情推送时间间隔(秒)，`可选，默认2秒`
- orderbook_length `int` `Orderbook` 行情推送长度，`可选，默认为 10`


> 其它：
- [orderbook 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#21-%E8%AE%A2%E5%8D%95%E8%96%84orderbook)
- [Trade 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#23-%E6%88%90%E4%BA%A4trade)

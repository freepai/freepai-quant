
## OKEx Future行情

OKEx Future 的行情数据根据 [OKEx Future官方文档](https://www.okex.com/docs/zh) 提供的方式，
通过websocket协议，订阅 OKEx Future 官方实时推送的行情数据。然后程序将源数据经过适当打包处理，并通过行情事件的形式发布到事件中心。

当前行情服务器能够收集 OKEx Future 的行情数据包括：Orderbook(订单薄)，Trade(成交)，Kline(K线)。

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
        "okex_future": {
            "symbols": [
                "BTC-USD-190524"
            ],
            "channels": [
                "orderbook"
            ]
        },
        "orderbook_length": 10
    }
}
```
以上配置表示：订阅 `okex_future` 交易所里，交易对(合约) `BTC-USD-190524` 的 `orderbook 订单薄` 行情数据。

> 配置文件可以参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。
> 此处对 `MARKETS` 下的关键配置做一下说明:
- MARKETS `dict` 需要配置的交易平台，key为交易平台名称，value为对应的行情配置
- okex_future `dict` 交易平台行情配置
- symbols `list` 需要订阅行情数据的交易对(合约)，可以是一个或多个，注意此处配置的交易对都需要大写字母
- channels `list` 需要订阅的行情类型，其中： `orderbook 订单薄` / `kline K线` / `trade 成交`
- orderbook_length `int` 需要收集的订单薄长度，`可选，默认为10`


> 其它：
- [orderbook 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#21-%E8%AE%A2%E5%8D%95%E8%96%84orderbook)
- [Kline 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#22-k%E7%BA%BFkline)
- [Trade 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/market.md#23-%E6%88%90%E4%BA%A4trade)

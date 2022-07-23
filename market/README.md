
## 行情服务
行情服务根据各个交易所当前提供的不同方式，通过REST API或Websocket方式实现了对各大交易所平台实时行情数据的获取及推送。


![](docs/images/market_framework.png)


#### 安装
需要安装 `thenextquant` 量化交易框架，使用 `pip` 可以简单方便安装:
```text
pip install thenextquant
```

#### 运行
```text
git clone https://github.com/TheNextQuant/Market.git  # 下载项目
cd Market  # 进入项目目录
vim config.json  # 编辑配置文件

python src/main.py config.json  # 启动之前请修改配置文件
```

- 配置示例
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
        "binance": {
            "symbols": [
                "BTC/USDT",
                "LTC/USDT"
            ],
            "channels": [
                "kline", "orderbook", "trade"
            ]
        }
    }
}
```
> 以上配置表示：订阅 `binance` 交易所里，交易对 `BTC/USDT` 和 `LTC/USDT` 的 `kline K线` 、 `orderbook 订单薄` 和 `trade 成交` 行情数据。

> 配置请参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。


#### 各大交易所行情

- [Binance 币币](docs/binance.md)
- [OKEx 币币](docs/okex.md)
- [OKEx Margin 杠杆](docs/okex_margin.md)
- [OKEx Future 交割合约](docs/okex_future.md)
- [OKEx Swap 永续合约](docs/okex_swap.md)
- [Bitmex 合约](docs/bitmex.md)
- [Deribit 合约](docs/deribit.md)
- [Huobi 币币](docs/huobi.md)
- [Coinsuper 币币](docs/coinsuper.md)
- [Coinsuper Premium 币币](docs/coinsuper_pre.md)
- [Kraken 币币](docs/kraken.md)
- [Gate.io 币币](docs/gate.md)
- [Gemini 币币](docs/gemini.md)
- [Coinbase 币币](docs/coinbase.md)
- [Kucoin 币币](docs/kucoin.md)


## 资产服务
资产服务根据各个交易所当前提供的不同方式，通过REST API或Websocket方式实现了对各大交易所平台账户资产的的获取及推送。


![](docs/images/asset_framwork.png)


> 资产事件默认 `10秒` 推送一次，可以在配置通过设置 `update_interval` 来指定资产事件更新推送时间间隔。


#### 安装
需要安装 `thenextquant` 量化交易框架，使用 `pip` 可以简单方便安装:
```text
pip install thenextquant
```

#### 运行
```text
git clone https://github.com/TheNextQuant/Asset.git  # 下载项目
cd Asset  # 进入项目目录
vim config.json  # 编辑配置文件

python src/main.py config.json  # 启动之前请修改配置文件
```

- 配置示例
```json
{
    "RABBITMQ": {
        "host": "127.0.0.1",
        "port": 5672,
        "username": "test",
        "password": "123456"
    },
    "PROXY": "http://127.0.0.1:1087",

    "ACCOUNTS": [
        {
            "platform": "binance",
            "account": "test@gmail.com",
            "access_key": "abc123",
            "secret_key": "abc123"
        }
    ]
}
```
> 以上配置表示：增加 `binance` 平台的账户 `test@gmail.com` 到资产服务器。 

> 配置请参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。


#### 各大交易所资产服务

- [Binance 币币](docs/binance.md)
- [OKEx 币币](docs/okex.md)
- [OKEx Future 交割合约](docs/okex_future.md)
- [OKEx Swap 永续合约](docs/okex_swap.md)
- [Bitmex 合约](docs/bitmex.md)
- [Deribit 合约](docs/deribit.md)
- [Huobi 币币](docs/huobi.md)
- [Huobi Future 合约](docs/huobi_future.md)
- [Coinsuper 币币](docs/coinsuper.md)
- [Coinsuper Premium 币币](docs/coinsuper_pre.md)
- [Kraken 币币/杠杆](docs/kraken.md)
- [Gate.io 币币](docs/gate.md)
- [Kucoin 币币](docs/kucoin.md)

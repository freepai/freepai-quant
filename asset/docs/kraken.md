
## Kraken 资产

Kraken的资产数据根据 [Kraken官方文档](https://www.kraken.com) 提供的方式，
通过REST API的方式，定时请求Kraken服务器相关账户的资产详情，然后资产服务器打包处理数据，通过资产事件的形式推送至事件中心。


##### 1. 服务配置

配置文件需要指定一些基础参数来告诉资产服务器应该做什么，一个完整的配置文件大致如下:

```json
{
    "LOG": {
        "console": true,
        "level": "DEBUG",
        "path": "/data/logs/servers/Asset",
        "name": "asset.log",
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
            "platform": "kraken",
            "account": "test@gmail.com",
            "access_key": "abc123",
            "secret_key": "abc123",
            "update_interval": 10
        }
    ]
}
```
> 以上配置表示：增加 `kraken` 平台的账户 `test@gmail.com` 到资产服务器。

> 配置文件可以参考 [配置文件说明](https://github.com/TheNextQuant/thenextquant/blob/master/docs/configure/README.md)。
> 此处对 `ACCOUNTS` 下的关键配置做一下说明:
- ACCOUNTS `list` 需要配置的账户列表，可以配置多个账户
    - platform `string` 交易平台，恒为 `kraken`
    - account `string` 账户名称
    - access_key `string` 账户对应的ACCESS KEY
    - secret_key `string` 账户对应的SECRET KEY
    - update_interval `int` 资产更新间隔时间 `可选，默认10秒`

> 注意！  
> Kraken的资产推送数据中，仅包含 `total` 总资产数据，`free` 和 `locked` 字段为0，因为Kraken官方接口文档未提供资产详细信息，
> 无法计算剩余资产和冻结资产。


> 其它：
- [Asset 数据结构](https://github.com/TheNextQuant/thenextquant/blob/master/docs/asset.md#2-%E8%B5%84%E4%BA%A7%E5%AF%B9%E8%B1%A1%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84)

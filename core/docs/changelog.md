# Change Logs


### v0.2.2

*Date: 2019/10/09*  
*Summary:*
- Add [Digifinex](../example/digifinex) Trade module.
- Add `*args` `**kwargs` params for `create_order` function.
- Add `client_order_id` for `Binance` & `OKEx`.


### v0.2.1

*Date: 2019/10/09*  
*Summary:*
- Add [Binance Future](../example/binance_future) Trade module.


### v0.2.0

*Date: 2019/10/04*  
*Summary:*
- Upgrade OKEx trading module.
- Fix bug: update order remain quantity when status is CANCELED.
- Add volume field in kline data when save to db.
- Add routing_key for EventHeartbeat.
- Change Trade module's locker name to avoid that there was the same locker in one progress.
- Change AMQP login method to PLAIN.


### v0.1.9

*Date: 2019/08/24*  
*Summary:*
- Add [Huobi Future](../example/huobi_future) Trade module.


### v0.1.8

*Date: 2019/08/20*  
*Summary:*
- Upgrade config.PLATFORMS to config.ACCOUNTS.
- validator for string field when field is None will return "".
- logger module: printf stack information in exception.


### v0.1.7

*Date: 2019/08/02*  
*Summary:*
- Add [Kucoin](../example/kucoin) Trade module.
- Add WarningEvent.


### v0.1.6

*Date: 2019/07/29*  
*Summary:*
- Add ConfigEvent to realize run-time-update.
- Add web module, include http server.
- Add validator module.
- Add KeyboardInterrupt caught.
- Enable subscribe multiple events.
- Fix bug: When save kline to mongodb, convert symbol name to collection name.


### v0.1.5

*Date: 2019/07/22*  
*Summary:*
- Add [Coinsuper Premium](../example/coinsuper_pre) Trade module.
- Publish OrderEvent.
- Upgrade Mongodb client.


### v0.1.4

*Date: 2019/07/16*  
*Summary:*
- Add [Gate.io](../example/gate) Trade module.
- Add [Kraken](../example/kraken) Trade module.
- Fix bug for [Coinsuper](../example/coinsuper) : get order infos maybe more than 50 length.


### v0.1.3

*Date: 2019/07/11*  
*Summary:*
- Fix bug: order callback filter by symbol.


### v0.1.2

*Date: 2019/07/04*  
*Summary:*
- fix bug: order & position callback should be use copy.copy() to avoid modified.
- Add [OKEx Swap](../example/okex_swap) Trade module.


### v0.1.1

*Date: 2019/06/28*  
*Summary:*
- Add [Coinsuper](../example/coinsuper) Trade module.


### v0.1.0

*Date: 2019/06/24*  
*Summary:*
- Add [OKEx Margin](../example/okex_margin) Trade module.
- modify EventCenter's Queue name to specific different servers.


### v0.0.9

*Date: 2019/06/14*  
*Summary:*
- Add Asset data callback when create Trade module.
- Add initialize status callback when create Trade module.


### v0.0.8

*Date: 2019/06/03*  
*Summary:*
- Add [Huobi](../example/huobi) module.


### v0.0.7

*Date: 2019/05/31*  
*Summary:*
- Add [Bitmex](https://www.bitmex.com) module.


### v0.0.5

*Date: 2019/05/30*  
*Summary:*
- Add [Binance](../example/binance) module.
- upgrade websocket module.


### v0.0.4

*Date: 2019/05/29*  
*Summary:*
- delete Agent server
- Add [Deribit](../example/deribit) module.
- upgrade market module.


### v0.0.3

*Date: 2019/03/12*  
*Summary:*
- Upgrade Agent Server Protocol to newest version.
- Subscribe Asset.

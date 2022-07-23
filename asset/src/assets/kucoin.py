# -*- coding:utf-8 -*-

"""
Kucoin Asset Server.

Author: HuangTao
Date:   2019/08/02
Email:  huangtao@ifclover.com
"""

from quant.utils import tools
from quant.utils import logger
from quant.event import EventAsset
from quant.tasks import LoopRunTask
from quant.platform.kucoin import KucoinRestAPI


class KucoinAsset:
    """ Kucoin Asset Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `kucoin`.
            host: HTTP request host. (default is "https://openapi-v2.kucoin.com")
            account: Account name. e.g. test@gmail.com.
            access_key: Account's ACCESS KEY.
            secret_key: Account's SECRETE KEY.
            passphrase: API KEY passphrase.
            update_interval: Interval time(second) for fetching asset information via HTTP, default is 10s.
    """

    def __init__(self, **kwargs):
        """Initialize object."""
        self._platform = kwargs["platform"]
        self._host = kwargs.get("host", "https://openapi-v2.kucoin.com")
        self._account = kwargs["account"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._passphrase = kwargs["passphrase"]
        self._update_interval = kwargs.get("update_interval", 10)

        self._assets = {}  # All currencies

        # Create a REST API client.
        self._rest_api = KucoinRestAPI(self._host, self._access_key, self._secret_key, self._passphrase)

        # Register a loop run task to fetching asset information.
        LoopRunTask.register(self.check_asset_update, self._update_interval)

    async def check_asset_update(self, *args, **kwargs):
        """Fetch asset information."""
        result, error = await self._rest_api.get_accounts("trade")
        if error:
            return

        assets = {}
        for item in result:
            name = item["currency"]
            total = float(item["balance"])
            free = float(item["available"])
            locked = float(item["holds"])
            if not total:
                continue
            d = {
                "free": "%.8f" % free,
                "locked": "%.8f" % locked,
                "total": "%.8f" % total
            }
            assets[name] = d

        if assets == self._assets:
            update = False
        else:
            update = True
        self._assets = assets

        # Publish AssetEvent.
        timestamp = tools.get_cur_timestamp_ms()
        EventAsset(self._platform, self._account, self._assets, timestamp, update).publish()
        logger.info("platform:", self._platform, "account:", self._account, "asset:", self._assets, caller=self)

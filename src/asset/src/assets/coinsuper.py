# -*- coding:utf-8 -*-

"""
Coinsuper Asset Server.

Author: HuangTao
Date:   2018/09/12
Email:  huangtao@ifclover.com
"""

from quant.utils import tools
from quant.utils import logger
from quant.event import EventAsset
from quant.tasks import LoopRunTask
from quant.platform.coinsuper import CoinsuperRestAPI


class CoinsuperAsset:
    """ Coinsuper Asset Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `coinsuper`.
            host: Exchange HTTP host address, default is "https://api.coinsuper.com"
            account: Account name. e.g. test@gmail.com.
            access_key: Account's ACCESS KEY.
            secret_key: Account's SECRETE KEY.
            update_interval: Interval time(second) for fetching asset information via HTTP, default is 10s.
    """

    def __init__(self, **kwargs):
        """Initialize object."""
        self._platform = kwargs["platform"]
        self._host = kwargs.get("host", "https://api.coinsuper.com")
        self._account = kwargs["account"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._update_interval = kwargs.get("update_interval", 10)

        self._assets = {}  # All currencies

        # Create a REST API client.
        self._rest_api = CoinsuperRestAPI(self._host, self._access_key, self._secret_key)

        # Register a loop run task to fetching asset information.
        LoopRunTask.register(self.check_asset_update, self._update_interval)

    async def check_asset_update(self, *args, **kwargs):
        """Fetch asset information."""
        result, error = await self._rest_api.get_user_account()
        if error:
            return

        assets = {}
        for name, value in result["asset"].items():
            free = float(value.get("available"))
            total = float(value.get("total"))
            if not total:
                continue
            d = {
                "free": "%.8f" % free,
                "locked": "%.8f" % (total - free),
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

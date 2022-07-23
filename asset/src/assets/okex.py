# -*- coding:utf-8 -*-

"""
OKEx Spot Asset Server.

Author: HuangTao
Date:   2019/01/20
Email:  huangtao@ifclover.com
"""

from quant.utils import tools
from quant.utils import logger
from quant.event import EventAsset
from quant.tasks import LoopRunTask
from quant.platform.okex import OKExRestAPI


class OKExAsset:
    """ OKEx Spot Asset Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `okex`.
            host: Exchange HTTP host address, default is "https://www.okex.com".
            account: Account name. e.g. test@gmail.com.
            access_key: Account's ACCESS KEY.
            secret_key: Account's SECRETE KEY.
            passphrase: API KEY Passphrase.
            update_interval: Interval time(second) for fetching asset information via HTTP, default is 10s.
    """

    def __init__(self, **kwargs):
        """Initialize object."""
        self._platform = kwargs["platform"]
        self._host = kwargs.get("host", "https://www.okex.com")
        self._account = kwargs["account"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._passphrase = kwargs["passphrase"]
        self._update_interval = kwargs.get("update_interval", 10)

        self._assets = {}  # All currencies

        # Create a REST API client.
        self._rest_api = OKExRestAPI(self._host, self._access_key, self._secret_key, self._passphrase)

        # Register a loop run task to fetching asset information.
        LoopRunTask.register(self.check_asset_update, self._update_interval)

    async def check_asset_update(self, *args, **kwargs):
        """Fetch asset information."""
        result, error = await self._rest_api.get_user_account()
        if error:
            logger.warn("platform:", self._platform, "account:", self._account, "get asset info failed!", caller=self)
            return

        assets = {}
        for item in result:
            symbol = item["currency"]
            total = float(item["balance"])
            free = float(item["available"])
            locked = float(item["frozen"])
            if total > 0:
                assets[symbol] = {
                    "total": "%.8f" % total,
                    "free": "%.8f" % free,
                    "locked": "%.8f" % locked
                }

        if assets == self._assets:
            update = False
        else:
            update = True
        self._assets = assets

        # Publish AssetEvent.
        timestamp = tools.get_cur_timestamp_ms()
        EventAsset(self._platform, self._account, self._assets, timestamp, update).publish()
        logger.info("platform:", self._platform, "account:", self._account, "asset:", self._assets, caller=self)

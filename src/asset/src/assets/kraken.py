# -*- coding:utf-8 -*-

"""
Kraken Asset Server.

Author: HuangTao
Date:   2019/01/20
Email:  huangtao@ifclover.com
"""

from quant.utils import tools
from quant.utils import logger
from quant.event import EventAsset
from quant.tasks import LoopRunTask
from quant.platform.kraken import KrakenRestAPI


class KrakenAsset:
    """ Kraken Asset Server.

    Attributes:
        kwargs:
            platform: Exchange platform name, must be `kraken`.
            host: Exchange HTTP host address, default is "https://api.kraken.com".
            account: Account name. e.g. test@gmail.com.
            access_key: Account's ACCESS KEY.
            secret_key: Account's SECRETE KEY.
            passphrase: API KEY Passphrase.
            update_interval: Interval time(second) for fetching asset information via HTTP, default is 10s.
    """

    def __init__(self, **kwargs):
        """Initialize object."""
        self._platform = kwargs["platform"]
        self._host = kwargs.get("host", "https://api.kraken.com")
        self._account = kwargs["account"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._update_interval = kwargs.get("update_interval", 10)

        self._assets = {}  # All currencies
        self._currency_detail = {}

        # Create a REST API client.
        self._rest_api = KrakenRestAPI(self._host, self._access_key, self._secret_key)

        # Register a loop run task to fetching asset information.
        LoopRunTask.register(self.check_asset_update, self._update_interval)

    async def check_asset_update(self, *args, **kwargs):
        """Fetch asset information."""
        result, error = await self._rest_api.get_account_balance()
        if error:
            logger.warn("platform:", self._platform, "account:", self._account, "get asset info failed!", caller=self)
            return

        assets = {}
        for key, value in result.items():
            name = await self.convert_currency_name(key)
            if not name:
                logger.warn("convert currency error:", key, caller=self)
                continue
            total = float(value)
            assets[name] = {
                "total": "%.8f" % total,
                "free": 0,
                "locked": 0
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

    async def convert_currency_name(self, raw_name):
        """ Convert raw currency name to display name."""
        if raw_name not in self._currency_detail:
            success, error = await self._rest_api.get_asset_info()
            if error:
                return None
            self._currency_detail = success
        name = self._currency_detail.get(raw_name, {}).get("altname")
        return name

# -*- coding:utf-8 -*-

from distutils.core import setup


setup(
    name="thenextquant",
    version="0.2.2",
    packages=[
        "quant",
        "quant.utils",
        "quant.platform",
    ],
    description="Asynchronous driven quantitative trading framework.",
    url="https://github.com/TheNextQuant/thenextquant",
    author="huangtao",
    author_email="huangtao@ifclover.com",
    license="MIT",
    keywords=[
        "thenextquant", "quant", "framework", "async", "asynchronous", "digiccy", "digital", "currency",
        "marketmaker", "binance", "okex", "huobi", "bitmex", "deribit", "kraken", "gemini", "kucoin", "digifinex"
    ],
    install_requires=[
        "aiohttp==3.2.1",
        "aioamqp==0.13.0",
        "motor==2.0.0"
    ],
)

# -*- coding:utf-8 -*-

"""
Web module.
Author: HuangTao
Date:   2018/08/26
Email:  huangtao@ifclover.com
"""

import json
import base64

import aiohttp
from aiohttp import web
from urllib.parse import urlparse

from quant.utils import tools
from quant.utils import logger
from quant.config import config
from quant.utils import exceptions
from quant.tasks import LoopRunTask, SingleTask


__all__ = ("routes", "WebViewBase", "AuthToken", "auth_middleware", "error_middleware", "options_middleware",
           "Websocket", "AsyncHttpRequests")

routes = web.RouteTableDef()


class WebViewBase(web.View):
    """ Web view base.
    """

    @property
    def query_params(self):
        if not hasattr(self, "_query_params"):
            self._query_params = dict(self.request.query)
        return self._query_params

    @classmethod
    def success(cls, data=None, msg="success", headers=None):
        return cls.write(0, data, msg, headers)

    @classmethod
    def error(cls, code=400, msg="error", data=None):
        return cls.write(code, data, msg, status_code=code, reason=msg)

    @classmethod
    def write(cls, code, data, msg, headers=None, status_code=200, reason=None):
        if config.http_server.get("cors"):  # Cross domain.
            headers = headers if headers else {}
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Headers"] = "*"
            headers["Access-Control-Allow-Methods"] = "*"
        result = {
            "code": code,
            "msg": msg,
            "data": data
        }
        return web.json_response(result, headers=headers, status=status_code, reason=reason)


class AuthToken(object):
    """ Token encode & decode.
    """

    @classmethod
    def encode(cls, user_id, username):
        info = {
            "user_id": user_id,
            "username": username,
            "timestamp": tools.get_cur_timestamp()
        }
        bdata = json.dumps(info).encode("ascii")
        token = base64.b64encode(bdata)
        return token.decode()

    @classmethod
    def decode(cls, token):
        sdata = base64.b64decode(token).decode("utf-8")
        items = json.loads(sdata)
        user_id = items["user_id"]
        username = items["username"]
        timestamp = items["timestamp"]
        return user_id, username, timestamp


@web.middleware
async def auth_middleware(request, handler):
    """ Authentication middleware.
    """
    ext_uri = config.http_server.get("ext_uri", [])
    if request.path not in ext_uri:
        token = request.headers.get("Token")
        if not token:
            token = request.query.get("Token")
            if not token:
                raise exceptions.AuthenticationFailed(msg="Token miss.")
        try:
            user_id, username, timestamp = AuthToken.decode(token)
        except:
            raise exceptions.AuthenticationFailed(msg="Token error.")
        if tools.get_cur_timestamp() - timestamp > 60 * 60 * 24:  # expire time.
            raise exceptions.AuthenticationFailed(msg="Token expired.")
        request.user_id = user_id
    response = await handler(request)
    return response


@web.middleware
async def error_middleware(request, handler):
    """ Catch custom exception in http handler.
    """
    try:
        response = await handler(request)
    except Exception as e:
        logger.exception("Error:", e)
        if isinstance(e, exceptions.CustomException):
            response = WebViewBase.error(e.code, e.msg, e.data)
        else:
            response = WebViewBase.error(500, "INTERNAL SEVER ERROR")
    return response


@web.middleware
async def options_middleware(request, handler):
    """ All OPTION method.
    """
    if request.method == "OPTIONS":
        response = WebViewBase.success()
    else:
        response = await handler(request)
    return response


class Websocket:
    """ Websocket connection.

    Attributes:
        url: Websocket connection url.
        connected_callback: Asynchronous callback function will be called after connected to Websocket server successfully.
        process_callback: Asynchronous callback function will be called if any stream data receive from Websocket
            connection, this function only callback `text/json` message. e.g.
                async def process_callback(json_message): pass
        process_binary_callback: Asynchronous callback function will be called if any stream data receive from Websocket
            connection, this function only callback `binary` message. e.g.
                async def process_binary_callback(binary_message): pass
        check_conn_interval: Check Websocket connection interval time(seconds), default is 10s.
    """

    def __init__(self, url, connected_callback=None, process_callback=None, process_binary_callback=None,
                 check_conn_interval=10):
        """Initialize."""
        self._url = url
        self._connected_callback = connected_callback
        self._process_callback = process_callback
        self._process_binary_callback = process_binary_callback
        self._check_conn_interval = check_conn_interval
        self._ws = None  # Websocket connection object.

    @property
    def ws(self):
        return self._ws

    def initialize(self):
        LoopRunTask.register(self._check_connection, self._check_conn_interval)
        SingleTask.run(self._connect)

    async def _connect(self):
        logger.info("url:", self._url, caller=self)
        proxy = config.proxy
        session = aiohttp.ClientSession()
        try:
            self._ws = await session.ws_connect(self._url, proxy=proxy)
        except aiohttp.client_exceptions.ClientConnectorError:
            logger.error("connect to Websocket server error! url:", self._url, caller=self)
            return
        if self._connected_callback:
            SingleTask.run(self._connected_callback)
        SingleTask.run(self._receive)

    async def _reconnect(self):
        """Re-connect to Websocket server."""
        logger.warn("reconnecting to Websocket server right now!", caller=self)
        await self._connect()

    async def _receive(self):
        """Receive stream message from Websocket connection."""
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if self._process_callback:
                    try:
                        data = json.loads(msg.data)
                    except:
                        data = msg.data
                    SingleTask.run(self._process_callback, data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                if self._process_binary_callback:
                    SingleTask.run(self._process_binary_callback, msg.data)
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                logger.warn("receive event CLOSED:", msg, caller=self)
                SingleTask.run(self._reconnect)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("receive event ERROR:", msg, caller=self)
            else:
                logger.warn("unhandled msg:", msg, caller=self)

    async def _check_connection(self, *args, **kwargs):
        """Check Websocket connection, if connection closed, re-connect immediately."""
        if not self.ws:
            logger.warn("Websocket connection not connected yet!", caller=self)
            return
        if self.ws.closed:
            SingleTask.run(self._reconnect)

    async def send(self, data):
        """ Send message to Websocket server.

        Args:
            data: Message content, must be dict or string.

        Returns:
            If send successfully, return True, otherwise return False.
        """
        if not self.ws:
            logger.warn("Websocket connection not connected yet!", caller=self)
            return False
        if isinstance(data, dict):
            await self.ws.send_json(data)
        elif isinstance(data, str):
            await self.ws.send_str(data)
        else:
            logger.error("send message failed:", data, caller=self)
            return False
        logger.debug("send message:", data, caller=self)
        return True


class AsyncHttpRequests(object):
    """ Asynchronous HTTP Request Client.
    """

    # Every domain name holds a connection session, for less system resource utilization and faster request speed.
    _SESSIONS = {}  # {"domain-name": session, ... }

    @classmethod
    async def fetch(cls, method, url, params=None, body=None, data=None, headers=None, timeout=30, **kwargs):
        """ Create a HTTP request.

        Args:
            method: HTTP request method. (GET/POST/PUT/DELETE)
            url: Request url.
            params: HTTP query params.
            body: HTTP request body, string or bytes format.
            data: HTTP request body, dict format.
            headers: HTTP request header.
            timeout: HTTP request timeout(seconds), default is 30s.

            kwargs:
                proxy: HTTP proxy.

        Return:
            code: HTTP response code.
            success: HTTP response data. If something wrong, this field is None.
            error: If something wrong, this field will holding a Error information, otherwise it's None.

        Raises:
            HTTP request exceptions or response data parse exceptions. All the exceptions will be captured and return
            Error information.
        """
        session = cls._get_session(url)
        if not kwargs.get("proxy"):
            kwargs["proxy"] = config.proxy  # If there is a HTTP PROXY assigned in config file?
        try:
            if method == "GET":
                response = await session.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
            elif method == "POST":
                response = await session.post(url, params=params, data=body, json=data, headers=headers,
                                              timeout=timeout, **kwargs)
            elif method == "PUT":
                response = await session.put(url, params=params, data=body, json=data, headers=headers,
                                             timeout=timeout, **kwargs)
            elif method == "DELETE":
                response = await session.delete(url, params=params, data=body, json=data, headers=headers,
                                                timeout=timeout, **kwargs)
            else:
                error = "http method error!"
                return None, None, error
        except Exception as e:
            logger.error("method:", method, "url:", url, "headers:", headers, "params:", params, "body:", body,
                         "data:", data, "Error:", e, caller=cls)
            return None, None, e
        code = response.status
        if code not in (200, 201, 202, 203, 204, 205, 206):
            text = await response.text()
            logger.error("method:", method, "url:", url, "headers:", headers, "params:", params, "body:", body,
                         "data:", data, "code:", code, "result:", text, caller=cls)
            return code, None, text
        try:
            result = await response.json()
        except:
            result = await response.text()
            logger.warn("response data is not json format!", "method:", method, "url:", url, "headers:", headers,
                        "params:", params, "body:", body, "data:", data, "code:", code, "result:", result, caller=cls)
        logger.debug("method:", method, "url:", url, "headers:", headers, "params:", params, "body:", body,
                     "data:", data, "code:", code, "result:", json.dumps(result), caller=cls)
        return code, result, None

    @classmethod
    async def get(cls, url, params=None, body=None, data=None, headers=None, timeout=30, **kwargs):
        """ HTTP GET
        """
        result = await cls.fetch("GET", url, params, body, data, headers, timeout, **kwargs)
        return result

    @classmethod
    async def post(cls, url, params=None, body=None, data=None, headers=None, timeout=30, **kwargs):
        """ HTTP POST
        """
        result = await cls.fetch("POST", url, params, body, data, headers, timeout, **kwargs)
        return result

    @classmethod
    async def delete(cls, url, params=None, body=None, data=None, headers=None, timeout=30, **kwargs):
        """ HTTP DELETE
        """
        result = await cls.fetch("DELETE", url, params, body, data, headers, timeout, **kwargs)
        return result

    @classmethod
    async def put(cls, url, params=None, body=None, data=None, headers=None, timeout=30, **kwargs):
        """ HTTP PUT
        """
        result = await cls.fetch("PUT", url, params, body, data, headers, timeout, **kwargs)
        return result

    @classmethod
    def _get_session(cls, url):
        """ Get the connection session for url's domain, if no session, create a new.

        Args:
            url: HTTP request url.

        Returns:
            session: HTTP request session.
        """
        parsed_url = urlparse(url)
        key = parsed_url.netloc or parsed_url.hostname
        if key not in cls._SESSIONS:
            session = aiohttp.ClientSession()
            cls._SESSIONS[key] = session
        return cls._SESSIONS[key]

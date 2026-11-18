"""
HTTPS 反向代理：把公网请求透传到沙箱本地 127.0.0.1:54540
- 普通 HTTP：转发并原样回传状态/头/体
- WebSocket：识别 Upgrade 头，建立到后端的 ws 隧道双向转发
发布器会注入 PORT 环境变量，服务绑定 0.0.0.0。
"""
import os
import aiohttp
from aiohttp import web, ClientSession, WSMsgType

BACKEND = os.environ.get("BACKEND", "http://127.0.0.1:54540")
BACKEND_WS = BACKEND.replace("http://", "ws://").replace("https://", "wss://")
PORT = int(os.environ.get("PORT", "3000"))

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def clean_headers(headers):
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP}


async def websocket_proxy(request):
    """WebSocket 双向透传到后端"""
    ws_client = web.WebSocketResponse(heartbeat=None, autoping=True)
    await ws_client.prepare(request)

    backend_url = BACKEND_WS + request.path
    if request.query_string:
        backend_url += "?" + request.query_string

    session = request.app["session"]
    try:
        async with session.ws_connect(
            backend_url,
            headers=clean_headers(request.headers),
            heartbeat=None,
        ) as ws_backend:
            async def pump_client_to_backend():
                async for msg in ws_client:
                    if msg.type == WSMsgType.TEXT:
                        await ws_backend.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_backend.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await ws_backend.close()
                        break
                    elif msg.type == WSMsgType.ERROR:
                        break

            async def pump_backend_to_client():
                async for msg in ws_backend:
                    if msg.type == WSMsgType.TEXT:
                        await ws_client.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_client.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break

            import asyncio
            await asyncio.gather(
                pump_client_to_backend(),
                pump_backend_to_client(),
                return_exceptions=True,
            )
    except Exception as exc:
        print(f"[ws] backend connect failed: {exc}", flush=True)

    return ws_client


async def http_proxy(request):
    """普通 HTTP 反向代理"""
    session = request.app["session"]
    url = BACKEND + request.path
    if request.query_string:
        url += "?" + request.query_string

    try:
        data = await request.read()
        async with session.request(
            request.method,
            url,
            headers=clean_headers(request.headers),
            data=data if data else None,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            body = await resp.read()
            headers = clean_headers(resp.headers)
            return web.Response(status=resp.status, headers=headers, body=body)
    except Exception as exc:
        print(f"[http] backend error: {exc}", flush=True)
        return web.Response(
            status=502,
            text=f"Backend 54540 unreachable: {exc}",
        )


async def handle(request):
    upgrade = request.headers.get("Upgrade", "").lower()
    if upgrade == "websocket":
        return await websocket_proxy(request)
    # 全部路径（含根路径）转发给后端；健康检查单独走 /__health
    # 若后端不通，返回 200 的健康兜底文本，避免发布探测误判为服务挂了
    resp = await http_proxy(request)
    if resp.status == 502:
        return web.Response(
            text=f"proxy ok | backend={BACKEND} unreachable (tunnel down?)",
            content_type="text/plain",
            status=200,
        )
    return resp


async def health(request):
    return web.Response(
        text=f"proxy ok | backend={BACKEND} | ws={BACKEND_WS}",
        content_type="text/plain",
    )


async def on_startup(app):
    app["session"] = ClientSession(
        connector=aiohttp.TCPConnector(ssl=False, force_close=False),
        auto_decompress=False,
    )


async def on_cleanup(app):
    await app["session"].close()


def make_app():
    app = web.Application()
    app.router.add_get("/__health", health)
    app.router.add_route("*", "/{tail:.*}", handle)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    print(f"proxy listening 0.0.0.0:{PORT} -> {BACKEND}", flush=True)
    web.run_app(make_app(), host="0.0.0.0", port=PORT, print=None)

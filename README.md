# ubunt-openp2p-client

基于 [openp2p](https://github.com/openp2p-cn/openp2p) 的沙箱内网穿透客户端配置，配合一个 HTTPS/WSS 反向代理，把公网 HTTP 请求转发到本地游戏服务端口。

> 本项目为脱敏示例，所有 Token、服务器地址、节点名、端口映射均为占位符，请替换为你自己的信息后再使用。

## 目录结构

```
.
├── p2p/
│   ├── config.example.json   # openp2p 配置示例（需填入真实信息）
│   └── run_openp2p.sh        # 保活启动脚本（配合 supervisord）
└── https-proxy/
    └── main.py               # aiohttp 实现的 HTTP/WebSocket 反向代理
```

## 用途

链路：公网 HTTPS 请求 → 反向代理 → 本地 `127.0.0.1:54540` → openp2p 隧道 → 对端游戏服务。

- `p2p/`：openp2p 客户端配置与保活脚本。openp2p 主程序请自行从官方仓库下载，二进制不入库。
- `https-proxy/main.py`：把公网请求（含 WebSocket 升级）透传到后端端口，健康检查走 `/__health`。

## 快速开始

### 1. openp2p 客户端

```bash
cd p2p
cp config.example.json config.json
# 编辑 config.json：填入 Token、ServerHost/ServerIP/ServerPort、Node、PeerNode、端口映射
chmod 600 config.json
./run_openp2p.sh
```

如需开机自启，把 `run_openp2p.sh` 交给 supervisord 托管（`autostart=true` / `autorestart=true`）。

### 2. HTTPS 反向代理

```bash
cd https-proxy
pip install aiohttp
# 通过环境变量配置后端与端口
BACKEND=http://127.0.0.1:54540 PORT=3000 python main.py
```

- `BACKEND`：后端地址，默认 `http://127.0.0.1:54540`
- `PORT`：监听端口，默认 `3000`（发布平台通常会注入）

## 安全提示

- 不要把真实的 `Token`、服务器公网 IP、节点名提交到公开仓库。
- 日志文件可能包含拓扑与 IP 信息，未纳入本示例。

#!/usr/bin/env bash
# openp2p 保活启动脚本（配合 supervisord）
# 每次启动前用示例配置覆盖，避免运行过程中配置被改写。
set -e
cd "$(dirname "$0")"
# 使用前请将 config.example.json 复制为 config.json 并填入你自己的信息
if [ ! -f config.json ]; then
  cp -f config.example.json config.json
  chmod 600 config.json
fi
exec ./openp2p -loglevel 1 -maxlogsize 2097152

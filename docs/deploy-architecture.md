# 懂宝部署架构

2026-11-05 核对：当前采用腾讯云单机部署，生产 IP 为 `119.29.231.13`，实例 `ins-i46ao4p4` 位于广州；Tailscale 地址为 `100.110.87.73`。旧的「腾讯云入口 + 家庭 Ubuntu」方案已被替代。

## 服务分工

| 组件 | 位置与用途 |
|---|---|
| Nginx | 主机上的系统服务，处理公网 80/443、HTTPS 与同源反向代理 |
| v1.3 H5 | `apps/client-v13` 的本机生产构建，部署到 `/var/www/dongbao/current` |
| FastAPI | 现有 `dongbao-server-1` 容器，Nginx 代理到 `127.0.0.1:8000` |
| PostgreSQL | 现有 `dongbao-postgres-1` 容器及业务数据卷 |
| Qdrant | 现有 `dongbao-qdrant-1` 容器及向量数据卷 |
| 媒体与哭声模型 | `/home/ubuntu/dongbao/data/media`、`data/models` |

网页和小程序共同访问 `https://api.xiaomizhoubaobao.cn`。根路径提供 H5；`/api/v1/` 和 `/health` 转发给 FastAPI，不依赖家庭业务机在线。H5 使用 hash 路由和同源 API，小程序构建时写入完整 HTTPS API 地址。

## 运行配置

现有业务栈继续使用 `/home/ubuntu/dongbao` 中的 Compose 项目 `dongbao`。发布 H5 仅切换静态目录，不重建 API 镜像、不切换 Compose 项目名、不重建数据库。业务容器设置 `unless-stopped` 重启策略；旧的 `client-h5` 开发容器不作为生产网页入口。

Nginx 与 `certbot.timer` 使用系统服务。证书和原有 ACME 账户保存在 `/etc/letsencrypt`，自动续期保留公网 HTTP-01 验证路径。公网入口需要安全组放行 80、443，业务服务与数据库无需增加公网放行规则。

生产 `DEV_LOGIN` 为空，微信凭据和强随机 JWT 签名密钥只存在服务端。v1.3 H5 当前提供游客浏览，正式微信登录在小程序完成。

## 外部服务与验收边界

模型、腾讯云 ASR 和 Embedding 使用现有服务端配置；本次发布没有调用外部模型。API 健康检查、TLS 验证和静态资源校验用于证明部署链路；微信真机登录、授权、真实 AI 输出及审核需要另外验收。

发布和检查步骤见 [deploy/README.md](../deploy/README.md)，当前 Nginx 示例见 [nginx.cloud.conf.example](../deploy/nginx.cloud.conf.example)。旧的 `docker-compose.prod.yml` 和 `nginx.edge.conf.example` 仅保留作原混合部署方案的历史参考。

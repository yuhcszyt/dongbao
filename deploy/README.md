# 懂宝 · 腾讯云单机部署

当前生产机为腾讯云广州 `119.29.231.13`（`ubuntu`，实例 `ins-i46ao4p4`），Tailscale 地址 `100.110.87.73`。Nginx、H5、FastAPI、PostgreSQL、Qdrant 和哭声模型均位于这台机器。

旧的「腾讯云入口 + 家庭业务机」方案已不再用于当前部署。旧文件 `docker-compose.prod.yml`、`nginx.edge.conf.example` 保留作历史参考，不能直接用于切换当前数据库。架构见 [部署架构](../docs/deploy-architecture.md)。

## 访问入口

| 路径 | 服务 |
|---|---|
| `https://api.xiaomizhoubaobao.cn/` | 最新 `apps/client-v13` 的 H5 生产构建 |
| `/api/v1/` | 同源反向代理到 `127.0.0.1:8000` |
| `/health` | FastAPI 健康检查 |

DNS A 记录指向 `119.29.231.13`；公网需要放行 TCP `80`、`443`。HTTP 跳转 HTTPS，证书续期使用 HTTP-01。Nginx 配置见 [nginx.cloud.conf.example](nginx.cloud.conf.example)。

## 现有服务与数据

- 仓库：`/home/ubuntu/dongbao`，现有 Compose 项目名 `dongbao`。
- API / PostgreSQL / Qdrant 沿用现有容器及数据卷，不为发布静态前端重建镜像或数据库。
- 媒体与模型：`/home/ubuntu/dongbao/data/media`、`data/models`。
- Nginx：`/etc/nginx/sites-available/dongbao`；静态发布目录 `/var/www/dongbao/releases/<版本>`，`/var/www/dongbao/current` 指向当前版本。
- 业务容器的重启策略为 `unless-stopped`；Nginx 和 `certbot.timer` 随主机启动。重新创建业务容器后需保留该策略。
- 域名证书与 ACME 账户在 `/etc/letsencrypt`；密钥及服务器凭据均不入库。

## 构建最新前端

仓库根目录执行，使用本机依赖；不启动 GUI 或前端开发服务器：

```bash
make test-client CLIENT_DIR=apps/client-v13
npm run build:h5 --prefix apps/client-v13
VITE_API_BASE_URL=https://api.xiaomizhoubaobao.cn/api/v1 \
  npm run build:mp-weixin --prefix apps/client-v13
```

H5 使用同源 `/api/v1`；小程序构建必须显式使用上面的 HTTPS 地址。

## 发布 H5

把 `apps/client-v13/dist/build/h5/` 的全部文件上传到新的发布目录，保留旧版本用于回退。例如，先在本机构建和打包：

```bash
tar -czf /tmp/dongbao-h5.tar.gz -C apps/client-v13/dist/build/h5 .
scp /tmp/dongbao-h5.tar.gz ubuntu@119.29.231.13:/tmp/
```

在服务器中设置本次版本号，并切换目录：

```bash
revision=30eb404-20261105
sudo install -d -m 755 "/var/www/dongbao/releases/$revision"
sudo tar -xzf /tmp/dongbao-h5.tar.gz -C "/var/www/dongbao/releases/$revision"
sudo test -s "/var/www/dongbao/releases/$revision/index.html"
sudo ln -sfn "/var/www/dongbao/releases/$revision" /var/www/dongbao/current.next
sudo mv -Tf /var/www/dongbao/current.next /var/www/dongbao/current
sudo nginx -t
sudo systemctl reload nginx
```

首次配置 Nginx 时，将本目录的 `nginx.cloud.conf.example` 安装到 `/etc/nginx/sites-available/dongbao` 并启用相应链接；需要先准备域名证书。现有主机已安装 Nginx、certbot 及 Nginx 续期插件。

## 分层验证

从公网执行，不能把绕过公网的测试当成公网恢复：

```bash
curl --noproxy '*' -fsS --connect-timeout 5 --max-time 10 \
  https://api.xiaomizhoubaobao.cn/health
```

主机内部可用 `--resolve api.xiaomizhoubaobao.cn:443:127.0.0.1` 隔离验证 Nginx、真实证书及 API；另一台 Tailscale 设备可将该地址替换为 `100.110.87.73`。若这两层通过而公网 443 超时，需检查实例绑定安全组及公网链路。

```bash
sudo nginx -t
sudo systemctl status nginx certbot.timer
sudo certbot renew --dry-run --non-interactive \
  --cert-name api.xiaomizhoubaobao.cn
```

## 登录与小程序

生产环境保持 `DEV_LOGIN` 为空，并配置真实微信凭据及强随机 `JWT_SECRET`。当前 v1.3 的 H5 支持游客浏览，私有业务的正式微信登录通过小程序完成；H5 的开发 code 不可用于生产登录。

用户需自行在微信公众平台配置相同 HTTPS 域名的 request、uploadFile、downloadFile 合法域名，并在开发者工具导入 `apps/client-v13`、上传体验版。Agent 不控制 GUI。真机登录、录音拍照授权、真实模型输出及微信审核仍需实际验收；构建与单测不代替这些验收。

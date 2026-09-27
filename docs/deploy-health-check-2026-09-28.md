# 公网健康检查排障记录（2026-09-28）

检查时间：北京时间 2026-09-28 00:59–01:03。以下是当时的现场结果，不代表持续可用性。

## 结论与边界

`https://api.xiaomizhoubaobao.cn/health` 公网访问仍未恢复。已确认公网 HTTP 被腾讯云备案系统拦截；腾讯云公开状态查询将该域名识别为未完成备案。家庭后端、腾讯云经 Tailscale 到家庭机，以及 Nginx HTTPS 代理的健康检查均通过。

公网 TCP 443 另有连接超时现象：本次未读取腾讯云控制台的实例防火墙/安全组规则，不能仅凭 HTTP 的备案拦截断言 443 超时只有同一个原因。需同时核对云端 TCP 443 放行状态。

本次只进行只读排障和文档更新，没有改动线上配置、重启服务或重建镜像。`/health` 成功只证明健康检查链路，不代表微信登录、数据库业务、AI 或真机验收通过。

## 部署链路与现场证据

```text
公网域名 → 腾讯云 42.194.128.135（Nginx / HTTPS）
                         ↓ Tailscale
                家庭 Ubuntu 100.71.108.114:8000
```

| 检查层 | 实测结果 |
|---|---|
| DNS | A 记录为 `42.194.128.135`，没有 AAAA 记录 |
| 公网 HTTP `/health` | 返回 `302`，Location 指向 `https://dnspod.qcloud.com/static/webblock.html?d=api.xiaomizhoubaobao.cn` |
| 公网 HTTPS `/health` | 两次 TCP 连接均超时，未进入 TLS 握手 |
| 腾讯云 Nginx | 服务 active，监听 `0.0.0.0:80` 和 `0.0.0.0:443`，`nginx -t` 通过 |
| 腾讯云本机 HTTPS | 保留域名/SNI，连接 `127.0.0.1:443`，正常验证证书，返回 `200 {"status":"ok"}` |
| Mac 经 Tailscale 访问腾讯云 HTTPS | 保留域名/SNI，连接 `100.103.10.68:443`，返回 `200 {"status":"ok"}` |
| 腾讯云到家庭后端 | `http://100.71.108.114:8000/health` 返回 `200 {"status":"ok"}` |
| TLS 证书 | 域名匹配；Let's Encrypt；有效期为 UTC 2026-09-27 14:24:57 至 2026-12-26 14:24:56 |
| 主机防火墙 | UFW inactive；已检查的 INPUT 链及其跳转链未发现阻断公网 TCP 443 的规则 |

腾讯云备案拦截页调用的公开只读状态接口 `DescribeDomainIcpStatus` 对该域名返回：

```json
{"GovStatus": false, "LandedStatus": false, "AuditTicket": false, "Ban": false}
```

根据该页面同时返回的状态映射，这组值对应“您的网站未完成备案”。这是腾讯云当前识别结果；如已收到备案成功通知，需要在备案控制台核对信息同步或接入状态。

## 分层复查命令

在本地终端检查公网入口，禁用代理以明确测量路径；不要跟随 HTTP 跳转，以免把拦截页的成功响应误认为后端成功：

```bash
dig +short A api.xiaomizhoubaobao.cn
curl --noproxy '*' -i --connect-timeout 6 --max-time 10 \
  http://api.xiaomizhoubaobao.cn/health
curl --noproxy '*' -fsS --connect-timeout 6 --max-time 10 \
  https://api.xiaomizhoubaobao.cn/health
```

在腾讯云 SSH 终端检查家庭后端，再检查完整的 Nginx HTTPS 代理链路：

```bash
curl --noproxy '*' -fsS --connect-timeout 3 --max-time 10 \
  http://100.71.108.114:8000/health
curl --noproxy '*' -fsS --connect-timeout 3 --max-time 10 \
  --resolve api.xiaomizhoubaobao.cn:443:127.0.0.1 \
  https://api.xiaomizhoubaobao.cn/health
sudo nginx -t
```

`--resolve` 在这里仅用于隔离检查服务器内部链路，仍然验证真实域名证书；成功不表示公网入口已经恢复。

## 恢复步骤

1. 在[腾讯云 ICP 备案控制台](https://console.cloud.tencent.com/beian/manage)核对 `xiaomizhoubaobao.cn` 的备案状态。没有备案号则办理首次备案；已在其他接入商备案则办理腾讯云接入备案；已完成则核对同步状态或联系腾讯云。
2. 在腾讯云实例的防火墙/安全组中核对公网入站 TCP `80`、`443` 已放行。无需把家庭机 `8000`、PostgreSQL 或 Qdrant 暴露到公网。
3. 完成备案并解除拦截、确认端口放行后，重新执行公网 HTTPS 命令。只有公网直接返回 `200 {"status":"ok"}`，才算此故障恢复。

参考：[腾讯云网站/APP 阻断说明](https://cloud.tencent.com/document/product/243/20220)。部署架构仍按[腾讯云入口 + 家庭业务机](deploy-architecture.md)执行。

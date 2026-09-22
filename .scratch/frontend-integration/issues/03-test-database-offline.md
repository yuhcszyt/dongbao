# 03 Docker 恢复后重跑服务端回归

Status: ready-for-human

## 复现与实际

2026-09-23 执行 `make test`，在 db-up 阶段退出：

```text
Cannot connect to the Docker daemon at unix:///Users/yuhc/.docker/run/docker.sock
make: *** [db-up] Error 1
```

当前 context 为 desktop-linux；独立连接检查确认 127.0.0.1:55432 不可达。没有为了验证重建镜像，也没有启动或操作 Docker GUI。

## 预期与影响

Docker 可用时，make test 应仅启动 postgres-test，并在主机运行迁移、pytest、vue-tsc 与 Vitest。测试 Qdrant 已使用内存模式，不再依赖额外容器。

2026-09-22 该服务端版本的行为改动已通过 69 个测试，随后后端只清除了未使用的导入；2026-09-23 的最新整体重跑未完成。客户端可独立验证，不受此阻碍。

## 下一步

用户恢复本机 Docker 后，在仓库根目录运行 `make test`。不用 `docker compose build`、`up --build` 或重建服务镜像。远端部署另需对目标数据库应用 0007 迁移；此处测试库迁移不等同于远端部署。

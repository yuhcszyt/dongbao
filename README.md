# 懂宝

Phase 1 实现宝宝档案、十类日常记录、时间线与今日汇总，并支持语音或图片生成待确认草稿。前端使用 UniApp + Vue 3 + TypeScript，后端使用 FastAPI + PostgreSQL，开发、迁移、测试和构建统一由 Docker Compose 运行。

## 启动

```bash
cp .env.example .env
docker compose up --build
```

- H5：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- 微信开发者工具：导入仓库的 `apps/client` 目录；Compose 会把构建结果写入 `apps/client/dist/dev/mp-weixin/`。

数据库保存在 Compose 命名卷，上传文件保存在 `data/media/`。应用当前使用固定测试家庭与测试用户，不包含正式登录和家庭共享。

## Provider 配置

腾讯一句话识别和 OpenAI 兼容大模型的非密钥参数位于 `config/providers.toml`。密钥只放在本地 `.env`：

```dotenv
TENCENT_SECRET_ID=
TENCENT_SECRET_KEY=
MODEL_API_KEY=
```

大模型模板默认禁用且 `base_url`、`model` 留空。Provider 未启用、缺少凭证或请求失败时，系统保留媒体并返回可手动填写的草稿。

## 检查

```bash
docker compose config
docker compose build
docker compose run --rm server-test
docker compose run --rm client-test
docker compose run --rm client-build
```

自动化检查不调用真实 Provider。真实腾讯云或大模型验收需另行配置凭证并授权可能产生费用的请求。

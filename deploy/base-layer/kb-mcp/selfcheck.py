"""容器内自检：写入 -> 检索 -> 列表 -> 按项目删除。

用法（容器内）：
    docker compose exec kb-mcp python selfcheck.py

它只碰 project="__selftest__" 的数据，跑完自己清理，不动正式内容。
"""

from __future__ import annotations

import sys

import server as kb

PROJECT = "__selftest__"


def main() -> int:
    print(f"qdrant={kb.QDRANT_URL} model={kb.EMBEDDING_MODEL} collection={kb.DEFAULT_COLLECTION}")

    out = kb.kb_add(
        text="懂宝后端部署在腾讯云，nginx 反代到 uvicorn:8000，Postgres 与 Qdrant 不映射公网。",
        title="部署拓扑自检",
        project=PROJECT,
        tags=["deploy"],
        source="selfcheck",
    )
    print("add   ->", out)

    out = kb.kb_add(
        text="小程序体验版必须使用已备案域名，否则真机请求会被拦截。",
        title="备案自检",
        project=PROJECT,
        tags=["filing"],
        source="selfcheck",
    )
    print("add   ->", out)

    out = kb.kb_search(query="后端怎么部署的", project=PROJECT, limit=3)
    print("search->", out.splitlines()[0] if out.strip() else "(空)")
    if "部署拓扑自检" not in out:
        print("FAIL: 检索没有命中预期条目")
        return 1

    out = kb.kb_list(project=PROJECT)
    print("list  ->", len(out.splitlines()), "行")

    out = kb.kb_delete(project=PROJECT)
    print("delete->", out)

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 步骤十六：Redis 缓存 + Elasticsearch（阶段五 · 中间件）

> 依据：《IT运维集中管控平台_软件设计方案.html》V1.0 定稿 · §3.4 技术选型 / §4.18
> 范围：缓存抽象（Redis + 内存降级）、知识库全文检索（Elasticsearch + SQL 降级）、docker-compose 一键启用。

## 1. 目标

按设计「简化部署：Docker Compose 一键拉起 PostgreSQL / Redis / Elasticsearch」，引入两个可选中间件，均**优雅降级**——未配置或不可用时回退到进程内缓存 / SQL `ilike`，不影响现有功能与测试（测试环境无 Redis/ES，走降级路径）：

- **Redis 缓存**：热数据（列表/计数）缓存，`Cache` 抽象自动选后端（Redis → 内存）。
- **Elasticsearch**：知识库全文检索（分词/相关性排序），回退 SQL `ilike`；建改删时增量同步索引。

## 2. 配置（新增，均可选）

- `REDIS_URL`（空 = 禁用，默认空）
- `ELASTICSEARCH_URL`（空 = 禁用，默认空）

## 3. 文件清单

- `app/core/config.py` — 新增两个可选配置项
- `app/core/cache.py` — `Cache` 抽象（Redis 后端 + 内存后端，惰性选后端）
- `app/services/search_service.py` — ES 索引/检索 + SQL 降级 + `search_kb`
- `app/api/v1/kb.py` — 检索走 `search_kb`；建/改/删增量同步索引
- `docker-compose.yml` — 启用 redis + elasticsearch
- `requirements.txt` — 追加 `redis` / `elasticsearch`（可选，缺失自动降级）
- `tests/test_cache.py` / `tests/test_search_service.py` — 单测

## 4. 业务规则

- **缓存**：`cache.get/set/delete`，`set` 支持 TTL（秒）；Redis 不可达时内存字典兜底。
- **检索**：`search_kb(db, q, category, status, page, size)` 返回与 `paginate` 一致结构 `{items,total,page,size}`；ES 可用时走 ES（相关性排序），否则 SQL `ilike`。
- **索引同步**：知识条目增/改/删时 `index_kb_article` 尽力同步（ES 不可用静默跳过，不阻塞主流程）。
- **降级原则**：中间件异常不抛给用户，回退主路径。

## 5. 验证

```bash
cd backend && .venv/Scripts/activate
python -m pytest tests -q        # 无 Redis/ES 时走降级路径，全绿
# 有 Docker 时：docker compose up -d redis elasticsearch 后同一套测试亦绿
```

# 使用说明（Quickstart）

本项目是一个通用型“书源 → 搜索/章节/正文抓取 → REST API/WS 导出”的聚合框架。新增站点无需写代码，只需编写一份 JSON 书源配置，放入 `sources/` 目录即可热加载生效。

## 1. 环境与安装

- 系统要求：Python 3.9+
- 建议在虚拟环境中使用

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

依赖说明：
- FastAPI/Starlette：Web 服务与 OpenAPI 文档
- Uvicorn：ASGI Server
- Requests：HTTP 客户端
- BeautifulSoup4：默认解析后端（CSS 选择器）
- lxml + cssselect：可选解析后端（支持 XPath 与 CSSSelector）
- jsonschema：可选，严格校验书源 JSON 结构

## 2. 启动服务

两种方式任选其一：

A) 直接运行入口脚本
```bash
python3 main.py
```

B) 使用 Uvicorn 指定 ASGI 应用
```bash
uvicorn app.service.api:app --host 0.0.0.0 --port 8000 --reload
```

访问 OpenAPI 文档：
- http://127.0.0.1:8000/docs

## 3. 新增书源（零代码）

1) 在 `sources/` 目录下新增 `your_site.json`
2) 参考 `sources/example_source.json` 与 `app/schemas/source.schema.json` 填写字段
3) 保存后框架会自动热加载，无需重启服务

关键字段说明：
- site.name / site.base_url / site.encoding
- search
  - method: get|post
  - url_template: 必须包含 `{keyword}` 占位符
  - keyword_encoding: utf-8 | gbk | url-encode
  - list_selector: 定位搜索结果列表块
  - sub: 子选择器（title/author/cover/detail）
- chapters
  - list_selector / title_selector / link_selector
  - order: asc|desc
  - dedupe_key: title|url|both
- content
  - block_selector: 正文主要内容区域
  - filters: 需要过滤的广告/噪声关键词
  - next_page_selector: 下一页链接（可选）
  - paragraph_strategy: 段落合并策略（br_to_newline、compress_empty_lines）

解析后端：
- 默认 `parser_backend` = `bs4`
- 如果需要 XPath 或 lxml 的 CSS 解析，请确保安装 lxml 与 cssselect，并在书源中设置 `parser_backend` = `lxml`

## 4. API 调用示例

以搜索“凡人修仙”为例：

- 搜索
```bash
curl "http://127.0.0.1:8000/search?keyword=凡人修仙"
```
可选参数：`site=站点名称`（仅在指定站点搜索）

- 查询书籍信息
```bash
curl "http://127.0.0.1:8000/books/{book_id}"
```

- 获取章节列表
```bash
curl "http://127.0.0.1:8000/books/{book_id}/chapters"
```

- 获取章节正文
```bash
curl "http://127.0.0.1:8000/chapters/{chapter_id}/content"
```

- 导出整书 TXT（按章节顺序拼接）
```bash
curl -o book.txt "http://127.0.0.1:8000/export/txt/{book_id}"
```

提示：`book_id` 和 `chapter_id` 均由框架稳定生成，可通过搜索与章节列表接口获得。

## 5. WebSocket 实时推送（示例）

路径：`/ws`

消息示例：
```json
{"action": "search", "keyword": "凡人修仙", "site": "可选"}
```

返回：
- event=progress：过程提示
- event=result：返回搜索结果列表
- event=error：错误信息

可使用 wscat/websocat 等工具进行测试：
```bash
wscat -c ws://127.0.0.1:8000/ws
> {"action":"search","keyword":"凡人修仙"}
```

## 6. 性能、限流与缓存

- 服务层限流：内置 Token 桶（按 IP），默认容量 60，补充速率 1 token/s。触发时返回 429。
- 网络请求：
  - 指数退避重试（默认最多 3 次）
  - 随机 User-Agent
  - 域名级限速（令牌桶）
  - 响应缓存：TTL + ETag（命中 304 或 TTL 未过期时直接复用）

## 7. 热加载与回滚

- sources/ 中的 JSON 文件增加/修改/删除会自动热加载
- 管理器内部保留上一版本的编译结果，出现异常时可调用 `SourceManager.rollback()`（在代码层使用）

## 8. 常见问题（FAQ）

1) 搜索/正文为空？
- 一般为选择器不匹配，请在浏览器“检查元素”后调整 CSS/XPath
- 某些站点需要特定编码（如 gbk），请在 `site.encoding` 与 `search.keyword_encoding` 中正确配置

2) 使用 lxml 后 CSS 选择器失效？
- 请确认已安装 `cssselect`，并在 lxml 后端中使用（内部通过 `lxml.cssselect.CSSSelector` 实现）

3) 频繁 429？
- 客户端请求过快，服务端限流触发，稍候再试

4) 访问接口超时？
- 站点响应慢，或被目标站点限速；可在源码中调整 HttpClient 的超时、重试与 rps 配置

## 9. 进阶与扩展

- 插件机制（预留）：`app/plugins/plugin.py` 提供解析、导出、过滤等注册点
- 导出格式：可新增自定义导出器（例如 EPUB/MOBI）并在服务层挂载路由
- 分布式能力：建议结合 Celery + Redis、BloomFilter 去重等，在任务队列中实现大规模抓取

---

更多字段细节请参考：
- Schema：`app/schemas/source.schema.json`
- 示例：`sources/example_source.json`

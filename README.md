# Novel 聚合框架（FastAPI）

一句话用法：新增站点 = 写一份 JSON 书源 → 丢进 sources 文件夹 → 框架自动热加载 → 所有接口零代码生效。

## 功能概览

- 书源配置（Declarative Layer）
  - 站点信息：名称、根域名、字符编码
  - 搜索规则：请求方式、URL 模板、关键字编码、结果列表与子项选择器
  - 章节规则：章节列表、标题、链接选择器、排序与去重
  - 正文规则：正文块选择器、过滤词、下一页、段落合并策略
- 引擎核心（Core Engine）
  - 配置加载与 JSON Schema 校验、版本兼容检查、缓存编译
  - 网络请求器：指数退避重试、随机 UA、域名级限速、响应缓存（TTL + ETag）
  - 解析引擎：默认 BeautifulSoup，支持 CSS / XPath / 正则兜底
  - 清洗引擎：空白规范、广告过滤、段落还原、空行压缩
  - 统一接口：search / get_chapters / get_content / get_book_info
- 书源管理（Source Manager）
  - 本地 sources 目录热加载
  - 编译后缓存，加速启动
  - 同一站点多书源按 priority 优先级仲裁
- 服务层（Service Layer）
  - FastAPI RESTful API（自动 OpenAPI 文档）
  - Token 桶限流（按 IP）
  - WebSocket 实时推送（示例：搜索进度）
  - TXT 文本导出（按章节顺序拼接）

## 目录结构

- app/core
  - models.py：书源、选择器、实体模型
  - config_loader.py：JSON Schema 校验与缓存
  - http_client.py：重试、UA、限速、缓存
  - parser.py：选择器解析（bs4 / lxml 可选）
  - cleaner.py：正文清洗
  - engine.py：统一接口实现
- app/manager
  - source_manager.py：书源热加载与引擎初始化
- app/service
  - api.py：FastAPI 应用与接口
  - rate_limiter.py：限流中间件
- app/schemas
  - source.schema.json：书源 JSON Schema
- sources
  - example_source.json：示例书源
- main.py：本地启动入口

## 运行

1. 安装依赖（建议使用 virtualenv）：
   - fastapi
   - uvicorn
   - pydantic
   - requests
   - beautifulsoup4
   - lxml（可选，启用 lxml 解析时需要）
   - jsonschema（可选，用于严格校验）

2. 启动服务：

   python3 main.py

   访问 http://127.0.0.1:8000/docs 查看自动生成的 OpenAPI 文档。

## API 一览

- GET /sources：列出已加载的书源
- GET /search?keyword=xxx[&site=ExampleSite]
- GET /books/{book_id}
- GET /books/{book_id}/chapters
- GET /chapters/{chapter_id}/content
- GET /export/txt/{book_id}
- WebSocket /ws：发送 {"action":"search","keyword":"xxx","site":"可选"}

## 书源 JSON 结构（简要）

见 app/schemas/source.schema.json，示例参考 sources/example_source.json。

- version：Schema 版本（当前 1.0）
- priority：优先级（数值越小优先级越高）
- parser_backend：解析后端（bs4 | lxml | pyquery-预留）
- site：name、base_url、encoding
- search：method、url_template（包含 {keyword}）、keyword_encoding（gbk/utf-8/url-encode）、list_selector、子选择器（title/author/cover/detail）
- chapters：list_selector、title_selector、link_selector、order（asc/desc）、dedupe_key（title/url/both）
- content：block_selector、filters、next_page_selector、paragraph_strategy（br_to_newline、compress_empty_lines）

## 备注

- 解析后端默认 bs4，若需 XPath 请安装 lxml 并在书源中设置 parser_backend=lxml。
- 在线仓库、插件系统、定时任务、分布式队列等能力已在设计中，当前保留扩展点与目录结构，后续逐步完善。

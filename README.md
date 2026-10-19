# DeepSeek Harness 高电压文献助手

本地论文知识库 + 可溯源写作辅助 + OpenAlex 文献日报。以 **原生 Harness 插件卡片、MCP stdio 服务和 hv-literature Skill** 接入 DeepSeek Harness，也可在 Codex 或终端使用。

安装后在 **插件 → 已安装插件 → 高电压文献助手** 中查看，支持图标、中文说明、启用/停用开关、组件运行状态与卸载。v0.2.0 已在本机 Harness 桌面端验证卡片展示和组件启停；底层复用官方 MCP 桥接组件，提供 5 个文献工具。卡片是管理入口，检索与写作在对话中完成。

## 直接在 Harness 中使用

先确认卡片开关为启用，详情显示“1 运行中”，然后新建对话，复制任一示例：

> 使用 hv-literature，从我的本地论文中找“全纯嵌入方法的优势和局限”。给出论文题目、PDF 页码、本地路径和少量原句；回读原页后，分析句子如何组织，再帮我写一段中文论述，保留出处与适用条件。

> 使用 hv-literature，增量更新论文库，告诉我新增多少篇、有哪些页需要 OCR，并更新知识库看板。

> 使用 hv-literature，生成今天的文献日报：绝缘气体分子设计、声光电融合故障诊断两个方向合计约 10 篇。整理成中文阅读建议，标明发表日期、来源和推荐理由，保存 Markdown。较早论文明确标为补充阅读。

如果未自动选择 Skill，可明确要求调用 `mcp__hv_research__library_status`。模型访问凭据由 Harness 自己配置。看不到卡片时，先按下文检查实际客户端使用的 profile，避免把插件装到另一个隔离实例。

| 工具 | 用途 |
| --- | --- |
| `library_status` | 论文数量、路径、页数与索引质量 |
| `search_passages` | 主题 + 优势、局限、方法等意图检索 |
| `read_page` | 回读 PDF 物理页，核验上下文 |
| `sync_library` | 增量索引指定目录 |
| `daily_digest` | 检索 OpenAlex，去重并生成本地日报 |

## 新电脑安装

当前支持 macOS / Linux，Python 3.10+（含 SQLite FTS5）。本插件使用文件锁和符号链接，尚未验证 Windows。准备一个包含文字层 PDF 的目录；扫描件需要另做 OCR。

```sh
git clone git@github.com:xychendave/deepseek-hv-literature.git
cd deepseek-hv-literature
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./hv-literature init --library-root "$HOME/papers"
./hv-literature ingest
./hv-literature status
./hv-literature dashboard
```

仓库为私有，克隆账号需有访问权限。请把 `$HOME/papers` 替换成实际目录。多个目录重复传入 `--library-root`；后续直接修改本机的 `config.json`。`init` 不覆盖已有配置。

`hv-literature` 优先使用 `HV_PYTHON` 指定的解释器，其次使用本项目 `.venv`、本机 Codex bundled Python，最后使用 PATH 中的 `python3`。移动项目后需重新运行安装器，让 MCP 路径跟随新位置。

### 可选：学院期刊目录

在初始化时加 `--journal-file "/path/to/journals.xlsx"`，或编辑 `config.json` 的 `journal_file`、`journal_sheet`，然后执行：

```sh
./hv-literature journals
```

当前适配的 Excel 格式为首行标题，默认工作表 `期刊目录`：A 序号、B 刊名、C 国家/地区、D ISSN/EISSN、E 出版商、F 学科、G 期刊层级。B/D/G 标题必须分别为 `刊名`、`ISSN/EISSN`、`期刊层级`。匹配结果保留原始表行号；没有期刊表也能使用日报。层级来自用户目录，不代表最新 JCR 或中科院分区。

### 安装原生插件卡片

先启动一次官方 Harness，并安装其 `dsh` CLI（`dsh --version` 应能运行）。确认 **当前桌面客户端实际使用的 DSH_HOME**；若有多个隔离实例，必须选择对应目录。常规桌面安装通常是 `~/.dsh`，自定义启动时以实际路径为准。安装器不猜测该位置，也不修改其他 profile。安装还需要 CLI 可调用的 pnpm。

```sh
.venv/bin/python install_dsh.py --dsh-home "/absolute/path/to/dsh-home" --profile desktop --dry-run
.venv/bin/python install_dsh.py --dsh-home "/absolute/path/to/dsh-home" --profile desktop
```

如同时使用 web profile，增加 `--profile web`。也可以从环境变量 `DSH_HOME` 读取目录。

安装器会：

- 从 `harness-card/` 生成本机插件包 `data/harness-plugin/`，将当前项目的绝对路径写入生成的 MCP 配置；生成包不包含 PDF、凭据或数据库。
- 通过官方命令 `dsh plugin --profile <profile> add link:<生成目录>` 登记原生 bundle，使卡片出现在插件列表。包名为 `@xychendave/dsh-hv-literature`，无额外 npm 依赖。
- 如已安装旧版直接 MCP 配置，先备份并移除本插件的旧托管块，避免重复注册同一工具。安装命令失败或超时时恢复旧块；其他插件配置保留。
- 将 Skill 链接到 `~/.agents/skills/hv-literature` 和 `~/.codex/skills/hv-literature`，遇到其他同名 Skill 时停止，避免覆盖。
- 在本地 `data/card-installation.json` 记录安装位置与备份。重复安装更新生成包，保留卡片的启停状态。

在 Harness 的插件页面点击“刷新”。如宿主提示需要重启，再重启客户端。打开「高电压文献助手」卡片，确认开关开启、组件显示“运行中”，然后新建对话。

`harness-card/` 是模板源码，请使用安装器生成并登记本机包；不要直接把模板目录当作已构建插件安装。生成包链接到整个项目的 Python 程序，因此移动或删除项目会影响插件，移动后需重新安装。

仅需旧版 MCP 接入时，可加 `--mcp-only`，这不会创建卡片；已安装卡片时不能混用此选项。通过 `--dsh-command /path/to/dsh` 可指定另一份官方 CLI。

只使用 Codex 时，可将本项目 `skill/hv-literature` 链接到 Codex 的 skills 目录，然后让 Agent 使用 CLI。通用 MCP 客户端使用绝对路径 `<项目根目录>/hv-literature`，参数为 `["mcp"]`，无需 HTTP 端口。

### 卡片未显示或工具不可用

1. 确认安装命令中的 `--dsh-home` 对应正在打开的客户端，而非另一个 web/隔离实例。macOS 可只读查看 `ps -axo pid,ppid,command` 中 `dsh-desktop-host/lib/index.js` 后面的 profile 路径。
2. 在“插件”页面刷新，检查“已安装插件”中的卡片；打开详情查看组件运行状态。卡片可见但开关关闭时，手动启用。
3. 运行 `./hv-literature status` 与 `.venv/bin/python verify_mcp.py` 检查本地配置、Python 依赖和 MCP 服务。低文字量页不代表插件加载失败。
4. 仍无工具时检查宿主是否提示需要重启；不要重复在用户 patch 中添加第二份同名 MCP 配置。

### 配置 OpenAlex 日报凭据

本地全文检索无需 API key。日报读取 `OPENALEX_API_KEY` 环境变量，或 `config.json` 的 `credential_file`。可用隐藏输入写入本机权限 0600 的文件：

```sh
.venv/bin/python configure_key.py
./hv-literature daily
```

默认凭据文件在 `~/.config/hv-literature/credentials.json`。不要把 key 写进 Skill、聊天示例、Git 或安装参数。OpenAlex key 仅用于文献 API；生成写作建议使用宿主 Agent 的模型。

## 命令行与本地看板

在项目目录运行：

```sh
./hv-literature search '全纯嵌入 收敛' --role limitations --limit 6
./hv-literature evidence '全纯嵌入' --role advantages
./hv-literature page DOCUMENT_SHA256 1
./hv-literature daily
./hv-literature dashboard
```

`page` 的文档 ID 从检索结果获得。`--role` 支持 `all / advantages / limitations / methods / results / background`。

- `data/library.sqlite3`：本地 SQLite 数据库与 FTS5 索引。
- `outputs/`：带出处的 Markdown 写作证据包。
- `reports/YYYY/YYYY-MM-DD.md` 与同名 JSON：日报及原始候选证据。
- `知识库.html`：可在本地浏览器打开的静态快照；更新库后重新执行 `dashboard`。

看板里的搜索使用本地数据。AI 段落组织与改写在 Harness / Codex 对话中完成。仅运行 CLI 不会自动调用大模型或翻译摘要。

## 每天早上 8 点

**插件自身不附带定时器。** 已安装插件不等于已设置自动推送。可以在 Codex 中明确要求：

> 每天北京时间 08:00 在当前聊天运行本项目的文献日报，两个方向合计约 10 篇，整理成中文并保存本地 Markdown。更新本地论文库和知识库看板。失败时说明原因。

调度使用 Codex 的当前聊天自动化；首次设置后查看任务状态和时区。已有对应任务时更新原任务，不另建重复任务。本机、网络和宿主调度器需要可用；离线补跑行为取决于宿主。也可随时在 Harness 手动生成当天日报。

## 检索与证据边界

- 内容哈希去重、保留文件路径、按页引用；同名不同内容的论文分别保存。
- 检索使用 SQLite FTS5、术语扩展和意图关键词；尚未实现向量检索、OCR 或自动学术真实性核验。
- 原句可能受 PDF 分栏、连字符、公式识别影响；引用前回读原页，PDF 物理页与印刷页码分别处理。
- 日报默认先近 30 天，不足扩展到 365 天，每个查询最多 50 条。两个方向均衡挑选合计约 10 篇；不足则少报。
- 成功日报同日重跑使用缓存，并保留人工整理后的 Markdown；来源失败标记部分成功，保留重试可能。
- 日报证据来自 OpenAlex 元数据和摘要；不会自动下载全文，不能据此宣称已读完整论文。
- 当前提供文献管理和写作辅助，没有训练“分子构效关系”或“声光电故障诊断”科研模型。

## 数据如何流动

PDF 原文件只读，索引和摘录保存在本机。OpenAlex 只接收检索关键词与认证信息，不接收本地 PDF。调用宿主模型分析、改写时，返回的论文片段会进入该宿主的模型上下文，受其服务设置约束。

Git 忽略 `config.json`、凭据、PDF/Excel、数据库、报告、摘录与包含全文片段的 HTML；仓库只包含源码和示例配置。私有仓库也不应存放这些资料。

## 工程组成

| 文件或目录 | 内容 |
| --- | --- |
| `hv_literature.py`、`hv-literature` | SQLite 知识库、检索、OpenAlex 日报与 MCP 服务 |
| `dashboard.py` | 本地知识库 HTML 生成器 |
| `harness-card/` | 原生卡片的包声明、图标、中英文说明与入口 |
| `install_dsh.py`、`install_card.py` | 安装、旧配置迁移、生成本机 bundle 与失败恢复 |
| `skill/hv-literature/` | Agent 的检索、回读与写作工作流 |
| `config.example.json`、`configure_key.py` | 可移植示例配置与本机隐藏凭据输入 |
| `test_*.py`、`verify_mcp.py`、`.github/workflows/` | 离线测试、MCP 冒烟测试与 GitHub CI |

GitHub 保存完整可重建的工程；安装时生成的本机路径、运行数据和个人资料不进入 Git。

## 验证与卸载

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest -v
.venv/bin/python verify_mcp.py
```

测试使用临时合成 PDF、模拟 API 和临时 Harness profile，不读取真实论文或联网取文献。MCP 冒烟测试读取当前本地库状态与工具列表，输出统计，不打印论文原文或凭据。

卡片版可以在卡片详情点击“卸载”，或对同一 DSH_HOME 执行 `dsh plugin --profile desktop remove @xychendave/dsh-hv-literature`。再删除本项目对应的 Skill 符号链接即可；不要删除其他 Skill。库和原始 PDF 不会因此删除。

旧版 `--mcp-only` 安装需要删除相应 profile 的 `# BEGIN hv-literature managed block` 到 `# END hv-literature managed block` 部分。恢复备份前检查是否有其他后续配置改动，避免覆盖整份新配置。停用日报需要另外在 Codex 停用对应自动化；Harness 卡片开关只控制 Harness 中的工具。

接口参考：[DeepSeek Harness 官方项目](https://github.com/deepseek-ai/deepseek-harness)、[Harness 配置定义](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/config-catalog.md)、[OpenAlex 认证](https://help.openalex.org/api/authentication/)。

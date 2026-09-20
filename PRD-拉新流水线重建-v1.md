# 百度知道拉新流水线 · 重建 PRD v1

**文档状态**：待执行
**目标执行者**：Codex（或其他 AI 编码代理）
**产出日期**：2026-09-19

---

## 0. 给执行者的强制说明（先读完这一节）

### 0.1 这是重建，不是从零设计

原系统 `百度知道拉新大师 v1.0.4` 已编译分发并有真实付费用户，源码因设备损毁丢失，仅存 PyInstaller 打包产物。

**本文档中所有的接口地址、请求参数、正则表达式、阈值常量、错误码映射、prompt 原文，均从原系统字节码中提取，是既成事实，不是设计提案。**

因此：

| 禁止 | 原因 |
|---|---|
| ❌ 修改文档给定的阈值（重试次数、冷却秒数、页数上限、字数上限等） | 这些是实战调校的结果，改了会被风控 |
| ❌ "优化" prompt 文案 | prompt 是线上验证过的，改一个字都可能破坏输出格式 |
| ❌ 用更"优雅"的方案替换文档给定的实现要点 | 文档里标注 ⚠️ 的都是踩过坑的地方 |
| ❌ 跳过任何标注「已知陷阱」的条目 | 每一条都对应一次线上故障 |
| ❌ 引入文档未列出的第三方依赖 | 依赖清单见 §3.3 |

允许并鼓励：改进代码结构、补充类型标注、增加测试、改善错误信息可读性。

### 0.2 交付方式：模块化逐个交付

本项目拆为 **18 个 Python 模块 + 4 项 C# 改动**。

**每个模块必须独立完成、独立通过验收，才能进入下一个。** 不允许"先把架子全搭起来再填"。

每个模块的交付物固定为三件：
1. 模块源码
2. 该模块的单元测试（覆盖文档中列出的全部「验收标准」）
3. 一段可独立运行的 demo 脚本（`demo/<模块名>_demo.py`），证明模块可用

### 0.3 本文档的附件

以下文件与本 PRD 一同交付，是实现的必需输入：

```
assets/prompts/template_system_prompt.txt     模板生成 system prompt（4558 字）
assets/prompts/qa_style1_first_person.txt     问答风格1：第一人称生活化（1747 字）
assets/prompts/qa_style2_third_person.txt     问答风格2：客观第三人称（1755 字）
assets/prompts/qa_style3_helper.txt           问答风格3：过来人/帮手（1734 字）
assets/prompts/qa_human_suffix.txt            真人感强化后缀（325 字，追加到上述三套之后）
```

**这些文件必须原样使用，一个字符都不要改。**

---

## 1. 背景与目标

### 1.1 产品是什么

一个百度知道内容营销工具。完整业务链：

```
挖热门资源名 → 在百度知道搜这些名字，采集别人发的网盘链接
   → 把资源转存到自己的网盘、重新分享，得到自己的链接
   → 用 AI 生成问答内容（标题 + 含自己链接的回答）
   → 批量发布到百度知道
```

### 1.2 本次重建的范围

重建 **采集、模板生成、批量发布、AI问答、挖词** 五条主线，外加 **转存/分享** 作为对照实现。

**网盘转存的生产路径不在本项目内** —— 用户另有一套 C# 程序（`dakazhandian`，.NET 8 WPF）负责，两边通过 Excel 文件解耦。本项目重建的转存/分享模块（M08–M10）定位是**对照组与后备**，理由见 §1.3。

### 1.3 为什么还要重建转存/分享（M08–M10）

C# 那套程序架构更好（多账号并发、SQLite 持久化、18712 行测试），但**至今没有一次成功的真实端到端运行记录**，其输出目录至今为空。

本项目的转存/分享模块是唯一经过真实用户验证的实现，作用有三：

1. **对照组** —— 同一批链接两边各跑一次，结果不一致即可定位 C# 的问题
2. **验证工具** —— C# 的 `errno 12` 修复（§7.2）没有对照组就无法验证是否改对
3. **后备** —— C# 调通之前，本项目自成闭环，可独立出货

### 1.4 不做什么

- ❌ 不做 GUI（用户主程序已完成，本项目交付为 Python 包 + CLI）
- ❌ 不做授权/计费/登录（原系统的 `core.auth` / `core.billing` / `core.api_client` 不在范围内）
- ❌ 不做自动更新
- ❌ 不做其他网盘（仅百度网盘）

---

## 2. 技术选型与理由

### 2.1 语言决策

| 部分 | 语言 | 理由 |
|---|---|---|
| **全部 18 个模块** | **Python 3.12** | 见下 |
| C# 侧 4 项改动 | C# / .NET 8 | 在既有项目上做增量修补 |

**为什么流水线全用 Python 而不是并入 C# 解决方案：**

| 维度 | Python | 并入 C# |
|---|---|---|
| 工期 | 18.5 人日 | 约 35–45 人日（翻倍） |
| prompt / 正则迁移 | 原样复用 | 全部需要转译和重新验证 |
| HTTP 爬取 + HTML 正则解析 | requests + re，代码量最小 | HttpClient + Regex，样板代码多 2–3 倍 |
| LLM 调用与 JSON 处理 | 天然 | 需要额外序列化层 |
| AI 代理生成质量 | 高（生态样本多） | 爬虫类代码质量明显下降 |
| C# 的优势项（多账号并发、SQLite、强测试） | — | **在采集/生成/发布场景收益不明显**，采集本身受风控限速，并发不是瓶颈 |

**结论：C# 的架构优势集中在"批量转存调度"这一个场景，而那部分已经有了。其余部分用 C# 重写是纯粹的工期损失。**

### 2.2 语言决策的例外说明

M16（挖词站点解析器，20+ 个站点）曾考虑用 C#，因为它站点多、需长期维护。结论仍是 Python：解析逻辑是正则密集型，Python 的 `re` + 原系统现成正则可直接复用；用 C# 重写等于把 1639 行正则全部重新验证一遍，收益为零。

### 2.3 依赖清单（仅限这些）

```
requests          HTTP
openpyxl          Excel 读写
pywin32           DPAPI 凭据加密（仅 Windows）
pytest            测试
```

**不引入**：aiohttp、httpx、pandas、beautifulsoup4、lxml、selenium、playwright、scrapy、任何 ORM、任何 GUI 框架。

> 说明：原系统用纯正则解析 HTML，不用 BeautifulSoup。这是刻意的 —— 正则可以从字节码精确复原，换解析库等于重写全部解析逻辑。保持一致。

### 2.4 工程约定

- 包名 `lxds`，目录结构 `lxds/<模块名>.py`
- 全部模块**零 GUI 依赖**，不 import 任何 Qt
- 所有耗时操作接受 `stop_event: threading.Event` 和 `on_log: Callable[[str], None]` 两个参数（原系统约定，保持一致）
- 所有对外函数写类型标注
- 中文注释，保留原系统 docstring 中的"为什么这么做"（本文档已摘录，见各模块的「已知陷阱」）

---

## 3. 架构与数据契约

### 3.1 全局数据契约（最重要）

**整条流水线只有一种数据格式：三列 Excel。**

| 列名 | 含义 | 必需 |
|---|---|:---:|
| `资源名称` | 资源名 | ✅ |
| `资源链接` | 百度网盘分享链接（含 `?pwd=xxxx`） | ✅ |
| `提取码` | 4 位提取码 | 可选 |

**列识别规则（模糊匹配，不是精确匹配）：**

```
名称列：单元格文本包含 "名称" / "文件名" / "名字" / "资源名" / "资源名称"
链接列：单元格文本包含 "链接" / "网盘"，或该列数据含 "pan.baidu.com/s/"
表头行：在前 5 行内自动探测
附加列：允许存在（如"状态""账号""分享时间"），自动忽略
```

⚠️ **这条规则决定了与 C# 的互操作性**：C# 结果表的「分享链接」列因为包含"链接"二字，天然被识别。不要改成精确匹配。

### 3.2 模块依赖图

```
Layer 0  基础设施
  M01 config ──────────────┐
  M02 excelio ─────────────┤
                           │
Layer 1  独立能力          │
  M03 deepseek ────────────┤
  M04 qa ◀── M03           │
  M05 zhidao_bulk ─────────┤
                           │
Layer 2  内容生成          │
  M07 websearch ───────────┤
  M06 template_engine ◀── M03, M07, M02
                           │
Layer 3  网盘（对照组）    │
  M08 pan_auth ────────────┤
  M09 pan_transfer ◀── M08 │
  M10 pan_share ◀── M08    │
                           │
Layer 4  采集              │
  M11 zhidao_parse ────────┤
  M12 behavior ────────────┤
  M13 pool ◀── M12         │
  M15 checkpoint ──────────┤
  M14 collect ◀── M11, M13, M15, M07
                           │
Layer 5  挖词              │
  M16 miner_parsers ───────┤
  M17 miner ◀── M16, M15   │
                           │
Layer 6  编排              │
  M18 pipeline ◀── 全部 ───┘
```

**允许并行开发的批次**：
- 批次 A：M01, M02, M03, M11, M12, M16（互不依赖）
- 批次 B：M04, M05, M07, M08, M15
- 批次 C：M06, M09, M10, M13, M17
- 批次 D：M14
- 批次 E：M18

### 3.3 与 C# 程序的集成方式

**文件交接，不做进程间通信。**

```
Python 采集 ──导出 xlsx──▶ C# 导入 ──转存+分享──▶ 导出 xlsx ──▶ Python 模板生成 ──▶ Python 发布
```

不需要 REST / gRPC / FFI / 命名管道。两边各自读写约定目录下的 Excel 文件。

---

## 4. 模块规格

> 每个模块的格式：**职责 / 对外接口 / 关键实现 / 已知陷阱 / 验收标准 / 工期**

---

### M01 `config` — 配置与凭据存储

**工期：0.5 人日**

#### 职责
本地配置读写；敏感字段（百度知道 Cookie、网盘 Cookie、DeepSeek API Key）加密落盘。

#### 对外接口
```python
class ConfigStore:
    def load(self) -> None
    def save(self) -> None
    def get_deepseek_key(self) -> str
    def set_deepseek_key(self, key: str) -> None
    def get_zhidao_accounts(self) -> list[dict]   # [{name, remark, cookie}]
    def set_zhidao_accounts(self, accounts: list[dict]) -> None
    def get_pan_accounts(self) -> list[dict]
    def set_pan_accounts(self, accounts: list[dict]) -> None
    def get_setting(self, key: str, default=None)
    def set_setting(self, key: str, value) -> None
```

#### 关键实现
- 加密用 **Windows DPAPI**（`CryptProtectData` / `CryptUnprotectData`，通过 ctypes 调用 `crypt32.dll`），非 Windows 平台降级为明文并打印警告
- 配置文件位置：`%LOCALAPPDATA%/<app>/config.json`
- 保存后必须做 `verify_persisted()` —— 重新读一次确认写入成功（原系统有此步骤，防止磁盘满/权限问题静默失败）

#### 验收标准
- [ ] 写入 → 重启进程 → 读出，值一致
- [ ] 配置文件中 cookie / api_key 字段为密文（肉眼不可读）
- [ ] 目标目录不可写时，`save()` 抛出明确异常而非静默失败

---

### M02 `excelio` — Excel / CSV 读写

**工期：0.5 人日**

#### 职责
三列契约的读写；模糊列识别。

#### 对外接口
```python
def read_resource_table(path: str) -> tuple[list[dict], list[str]]
    """返回 (rows, skipped_reasons)。row = {name, link, index}"""

def write_resource_table(path: str, items: list[dict]) -> None
    """表头固定 (资源名称, 资源链接, 提取码)；列宽 A=40 B=60 C=16"""

def build_publish_workbook_bytes(rows: list[dict]) -> bytes
    """内存生成百度知道官方批量模板 xlsx；表头 (qid, 问题标题, 回答内容)
       qid 列留空；首行加粗居中；列宽 A=8 B=50 C=80"""
```

#### 关键实现
- 列识别规则见 §3.1，**必须是"包含"匹配**
- 表头行在前 5 行内探测
- 读入时跳过并记录原因：`链接为空` / `不是百度网盘链接`
- 名称为空时填 `资源{行号}`
- 支持 `.xlsx` / `.csv`；`.xls` 明确报错「请用 Excel 另存为 .xlsx 后上传」

#### 已知陷阱
⚠️ `build_publish_workbook_bytes` 的表头 **第一列必须是空的 `qid` 列**。百度知道批量上传接口要求这个格式，少一列会被拒。

#### 验收标准
- [ ] 能读入表头为「资源名称/资源链接/提取码」的表
- [ ] 能读入表头为「源标题/分享链接/提取码/状态/账号」的表（C# 输出格式，含附加列）
- [ ] 能读入无表头、按 A/B/C 列排列的表
- [ ] 表头不在第 1 行（在第 3 行）时仍能识别
- [ ] `build_publish_workbook_bytes` 输出可被 openpyxl 读回，表头为 `['qid','问题标题','回答内容']`

---

### M03 `deepseek` — LLM 客户端

**工期：0.5 人日**

#### 职责
DeepSeek 官方接口调用。

#### 对外接口
```python
class DeepSeekError(Exception): ...

def chat(api_key: str, messages: list[dict], max_tokens: int = None,
         json_mode: bool = False, timeout: int = 120) -> str
def test_key(api_key: str) -> tuple[bool, str]
```

#### 关键实现
```
端点：https://api.deepseek.com/chat/completions
模型：deepseek-chat          ← 固定，不要做成可配置
认证：Authorization: Bearer <key>
json_mode=True 时加 response_format = {"type": "json_object"}
返回取 choices[0].message.content
```

**错误映射（原样照抄）：**

| 情况 | 错误信息 |
|---|---|
| key 为空 | `请先在个人中心配置 DeepSeek API Key` |
| 超时 | `DeepSeek 请求超时，请稍后重试` |
| 网络异常 | `DeepSeek 网络错误：{}` |
| HTTP 401 | `DeepSeek API Key 无效，请检查个人中心配置` |
| HTTP 402 / 429 | `DeepSeek 余额不足或请求限流，请稍后重试` |
| 其他 HTTP | `DeepSeek 接口异常（HTTP {}）` |
| 返回结构不符 | `DeepSeek 返回格式异常` |
| content 为空 | `DeepSeek 返回内容为空` |

`test_key` 发最小请求：`messages=[{"role":"user","content":"ping"}]`

#### 验收标准
- [ ] 各错误分支均有对应单测（mock HTTP）
- [ ] `json_mode=True` 时请求体含 `response_format`

---

### M04 `qa` — AI 问答生成（原主线⑤）

**工期：0.5 人日**

#### 职责
输入一个百度知道问题，输出一条可直接发布的回答。

#### 对外接口
```python
STYLES = ("first_person", "third_person", "helper")

def generate_answer(api_key: str, question: str,
                    style: str = "first_person") -> str
```

#### 关键实现
- 三套 system prompt 见附件 `qa_style{1,2,3}_*.txt`
- **构造 system 消息时，必须在选中的风格 prompt 之后追加 `qa_human_suffix.txt` 的内容**（原系统行为）
- user 消息就是问题原文
- `json_mode=False`
- 返回内容直接用，不做后处理

#### 已知陷阱
⚠️ prompt 里明确要求"输出第一个字符必须是回答正文" —— 不要在代码里再加任何前缀、标题或包装。

#### 验收标准
- [ ] 三种 style 各能取到对应 prompt，且都拼接了 human_suffix
- [ ] 非法 style 抛 `ValueError`

---

### M05 `zhidao_bulk` — 批量发布（原主线④）

**工期：0.5 人日**

#### 职责
把生成好的问答表上传到百度知道批量任务。

#### 对外接口
```python
def userinfo(cookie: str) -> dict
def upload_file(cookie: str, filename: str, file_bytes: bytes,
                task_name: str) -> dict
```

#### 关键实现
```
账号信息：GET  https://zhidao.baidu.com/qa/api/bulkqa/userinfo
上传任务：POST https://zhidao.baidu.com/qa/api/bulkqa/upload

请求头：
  Accept: application/json, text/plain, */*
  Accept-Language: zh-CN,zh;q=0.9
  Origin:  https://zhidao.baidu.com
  Referer: https://zhidao.baidu.com/b/batch/batch-upload
  Cookie:  <传入>

上传为 multipart/form-data：
  file     = (filename, file_bytes,
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
  taskName = <task_name>

返回 JSON 判定：
  data.code != 200                → 失败
  data.hasPermission 为假          → 该账号无批量发布权限
  成功时取 data.taskId
```

#### 已知陷阱
⚠️ **这条链路必须直连，绝对不能走 Clash / 系统代理。** 原系统 docstring 原话：「直连，不经 Clash/系统代理；不打印 Cookie」。实现时显式设置 `proxies={"http": None, "https": None}` 或使用 `trust_env=False` 的 Session。

⚠️ 日志中禁止打印 Cookie 内容。

#### 验收标准
- [ ] Session 的 `trust_env` 为 False（单测断言）
- [ ] 无权限账号返回明确的 `PERM` 错误
- [ ] 未登录返回明确的 `LOGIN` 错误
- [ ] 日志输出中不含 cookie 字符串（单测扫描）

---

### M06 `template_engine` — 模板生成引擎（原主线③）

**工期：1.5 人日**

#### 职责
把「资源名 + 网盘链接」批量转成「问题标题 + 回答内容」。**这是整个产品的核心价值所在。**

#### 对外接口
```python
def should_search(name: str) -> bool
def build_title(resource_name: str, index: int) -> str
def enforce_title_format(title: str, index: int) -> str
def normalize_answer(raw: str, link: str, resource_name: str) -> str
def fallback_qa(name: str, link: str, index: int) -> dict
def post_process_row(ai_row: dict, name: str, link: str, index: int) -> dict
def ai_generate_batch(api_key: str, rows: list[dict],
                      backoff: float = 0, search_map: dict = None) -> list[dict]
```

#### 关键实现

**① 标题前后缀轮询（按 `index % 6`，成对，不得交叉）**

| index%6 | 前缀 | 后缀 |
|:---:|---|---|
| 0 | 求 | 完整网盘链接下载 |
| 1 | 求 | 完整网盘链接获取 |
| 2 | 哪里有 | 完整网盘资源链接 |
| 3 | 跪求 | 百度网盘链接获取 |
| 4 | 求 | 百度网盘链接下载 |
| 5 | 谁有 | 百度网盘资源链接 |

**标题总长硬上限 49 字符。** 超出时从资源名**结尾**截断，保留开头。绝不允许省略前缀或后缀。

**② 回答固定三段 HTML**
```html
<p><strong>点击链接获取完整素材：</strong><br/></p><p>{链接}<br/></p><p>{140-200字简介}</p>
```

**③ 是否联网搜资料（`should_search`）**

名称中已含类型词则跳过搜索。类型词正则（原样照抄）：
```
(?:游戏|单机|破解|手游|网游|小说|全本|精校|txt|电影|电视剧|综艺|纪录|动漫|动画|番剧|
课件|教案|讲义|习题|练习册|试卷|试题|题库|真题|模拟题|拼音|识字|数学|语文|英语|古诗|
成语|绘本|故事|儿歌|童谣|描红|字帖|手工|折纸|绘画|涂色|教程|课程|讲座|公开课|软件|
工具|模板|素材|合集|汇总|大全|全集|全套|字典|词典|百科|手册|指南|攻略|电子书|视频|
音频|音乐|幼小衔接|启蒙|早教|作业本|打卡|计算|思维|阅读|作文|写字|算术|复习|预习|教学|计划)
```

**④ 名称清洗正则**
```
行首序号：      ^\d+[_.\-\s]+
文件扩展名：    \.(xlsx|xls|doc|docx|pdf|txt|epub|mobi|mp4|mp3|zip|rar|7z|apk|exe|iso|ppt|pptx)$
控制字符：      [\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffd]
括号类：        [【】\[\]{}()（）]
```

**⑤ 发给 DeepSeek 的 payload**
```json
{"index": 0, "name": "...", "link": "...", "search": "...", "skip_search": false}
```
system prompt = 附件 `template_system_prompt.txt` 原文。`json_mode=True`。
返回解析：剥掉 ` ```json ` 包裹后取 `rows` 数组。

#### 已知陷阱（全部必须实现）

⚠️ **1. LLM 不守规矩是预设，本地必须强制校正。**
`post_process_row` 要在 AI 返回之后再跑一遍：
- `enforce_title_format` —— 强制前后缀 + 49 字截断
- `strip_link_wrappers` —— 剥掉链接外的【】[]()（）""「」等包裹符号
- `unwrap_anchor_tags` —— 把 `<a href=...>...</a>` 还原成裸链接
- 确认第二段是裸链接，第三段不含任何链接

⚠️ **2. 绝不丢行。** `ai_generate_batch` 中任何异常（网络、解析、rows 长度不匹配）都必须整批回退到 `fallback_qa`，保证输出行数 == 输入行数。

`fallback_qa` 的简介模板（原样）：
```
《{名称}》是一份网络分享的资源，本资源由百度网盘分享，点击上方链接即可转存获取。
下载后即可使用，如有疑问欢迎在评论区留言交流。
```

⚠️ **3. `rows` 数组长度必须与输入一致且顺序一致**，不一致即判定整批失败走兜底。

#### 验收标准
- [ ] index 0–11 各生成一次，前后缀严格按表轮询，第 6 条回到第 1 组
- [ ] 构造一个 60 字的资源名，验证标题被截断到 ≤49 且前后缀完整
- [ ] 模拟 AI 返回用 `<a href>` 包裹的链接，验证被还原成裸链接
- [ ] 模拟 AI 返回用【】包裹的链接，验证包裹被剥掉
- [ ] 模拟 AI 超时 / 返回非法 JSON / rows 长度不符，三种情况下输出行数均等于输入行数
- [ ] 模拟 AI 返回的标题不带前缀，验证被强制补上

---

### M07 `websearch` — 百度网页搜索取资料

**工期：0.5 人日**

#### 职责
给定资源名，返回一段网络搜索摘要，供 M06 补全资源信息；同时供 M14 做采集补量。

#### 对外接口
```python
def robust_search_snippets(name: str, max_chars: int = 500) -> str
def site_queries(term: str) -> list[str]

class BaiduWebCollector:
    def __init__(self, fetcher, stop_event): ...
    def search(self, keyword: str, on_log) -> list[dict]

class BaiduSiteSearchCollector:
    def __init__(self, fetcher, stop_event, max_variants: int = 3): ...
    def search(self, term: str, on_log) -> list[dict]
```

#### 关键实现
- 百度网页搜索结果页解析，抽取标题与摘要文本
- `site_queries` 生成 `site:pan.baidu.com <term>` 一类的站内检索变体
- 风控页识别：短页面 + 安全验证关键词 → 抛 `BaiduWebError`

#### 验收标准
- [ ] 输入一个常见资源名，返回非空摘要（联网测试，可标记为 `@pytest.mark.network`）
- [ ] 喂入安全验证页 HTML 样本，正确识别为风控

---

### M08 `pan_auth` — 网盘登录态

**工期：0.5 人日**

#### 职责
百度网盘 Cookie 体检、bdstoken 获取、目录列取。

#### 对外接口
```python
class PanError(Exception): ...
class PanTransientError(PanError): ...   # 可重试
class PanQuotaError(PanError): ...       # 空间不足，必须立即停

class PanClient:
    def __init__(self, cookie: str, timeout: int = 30): ...
    def check_cookie(self) -> tuple[str, str]   # (status, message)
    def bdstoken(self) -> str
    def list_dir(self, path: str) -> list[dict]
    def ensure_target_dir(self, path: str) -> None
```

#### 关键实现
```
身份：  GET https://pan.baidu.com/rest/2.0/xpan/nas?method=uinfo&clienttype=0&web=1
配额：  GET https://pan.baidu.com/api/quota
token： GET https://pan.baidu.com/api/gettemplatevariable?fields=%5B%22bdstoken%22%5D&clienttype=0&web=1
        兜底：GET https://pan.baidu.com/disk/home 后正则 bdstoken["\s:]+["\']?([0-9A-Za-z]+)
列目录：GET https://pan.baidu.com/api/list?dir={}&num=1000&order=name&desc=0&showempty=0&web=1
```

**`check_cookie` 返回 status ∈ `ok` / `expired` / `risk` / `incomplete` / `network`**

判据（原系统注明为 2026-09 实测结论）：

| 现象 | 结论 | 文案 |
|---|---|---|
| uinfo errno == 0 | 正常 | — |
| uinfo errno == -6 | 真失效 | `登录态已失效（errno={}）。请重新登录 pan.baidu.com，复制完整 Cookie 后再粘贴` |
| uinfo 正常但 quota errno == -6 | Cookie 缺 STOKEN，**不是失效** | `登录态有效，但 Cookie 缺少 STOKEN：部分接口可能失败，建议重新复制完整 Cookie` |
| errno ∈ {2, -9, 132} | 安全验证/风控，**不是失效** | `触发百度安全验证（errno={}）。请先在浏览器打开一次 pan.baidu.com 通过验证，再回来重试` |

#### 已知陷阱

⚠️ **`ensure_target_dir` 刻意不创建目录。**
原系统 docstring 原话：「目标不存在说明它被删了或改了名，该让用户重新选，而不是替他凭空造一个空文件夹（那正是用户看到"网盘里多了个空文件夹"的来源）」。
目标不存在时抛错：`目标文件夹不存在或读不到：{}。请重新选择目标文件夹`

⚠️ 每个 `PanClient` 实例对 `ensure_target_dir` 只查一次，结果缓存。

#### 验收标准
- [ ] 四种 status 各有单测（mock 响应）
- [ ] `ensure_target_dir` 在目录不存在时抛错，且**不发出任何 create 请求**（断言请求记录）

---

### M09 `pan_transfer` — 转存（独立模块）

**工期：1 人日**

#### 职责
把一条外部分享链接的全部文件，转存到自己网盘的指定目录。

#### 对外接口
```python
def extract_surl(url: str) -> str
def extract_pwd(url: str) -> str
def cookie_fields(cookie: str) -> set[str]

class PanClient:   # 续 M08
    def verify_share(self, url, surl, pwd) -> tuple[str, str, str]  # (shareid, uk, randsk)
    def file_list(self, shareid, uk, url) -> list[dict]
    def transfer_files(self, shareid, uk, fsids, target_path,
                       share_url, bdstoken) -> dict
    def transferred_fsids(result, expect) -> list[int]
    def fsids_by_names(self, target_path, names) -> list[int]
```

#### 关键实现

**链路顺序（不可调换）：**
```
1. extract_surl / extract_pwd
2. GET  /s/{surl}                          拿分享页 HTML
3. POST /share/verify?surl={}&t={}&...     body: pwd={}&vcode=&vcode_str=
   → 取 randsk，追加到 Cookie： "; BDCLND=" + randsk
4. GET  /share/list?shareid={}&uk={}&root=1&page=1&num=100&order=name&desc=0&web=1&folder_path=%2F
5. POST /share/transfer?shareid={}&from={uk}&bdstoken={}&channel=chunlei&web=1&app_id=250528&clienttype=0
   body: fsidlist=[{}]&path={}
```

**surl 提取的两种形式：**
```
https://pan.baidu.com/s/1AbCdEf            → surl = AbCdEf   （去掉开头的 1）
https://pan.baidu.com/share/init?surl=AbC  → surl = AbC      （参数原值）
正则： [?&]surl=([0-9A-Za-z_-]+)  和  /s/1?([0-9A-Za-z_-]+)
```

#### 已知陷阱（全部必须实现）

⚠️ **1. `share_uk` 优先于 `uk`。**
分享页 HTML 里同时存在登录者自己的 `uk`（未登录时为 0）和分享者的 `share_uk`。**必须先认 `share_uk`**，否则会把 `uk=0` 发给接口，白挨一个"链接出错"。

匹配顺序（严格按此顺序）：
```
1. shareid["\']?\s*[:=]\s*["\']?(\d+)
2. share_uk["\']?\s*[:=]\s*["\']?(\d+)      ← 先试这个
3. \buk["\']?\s*[:=]\s*["\']?(\d+)          ← 兜底
```

⚠️ **2. 用返回里的 `to_fs_id`，不要回头列目录。**
转存接口返回中 `extra.list[].to_fs_id` 直接带着新文件的 fs_id。
原系统 docstring 原话：「多线程并发转存同一个目录时，按"最新文件"去找会抓到别的线程刚转进去的文件，分享就指错了」。
`fsids_by_names`（按文件名在目标目录找）只作为 `to_fs_id` 缺失时的兜底，**不要用"取最新 N 个"**。

⚠️ **3. `errno 12` 有三种含义，必须分开。** （这是 C# 侧当前的 bug，见 §7.2）

| 判据 | 含义 | 处理 |
|---|---|---|
| 返回含 `duplicated.list` | 文件已存在 | **成功跳过**，状态 `重复跳过`，从 `duplicated.list[].path` 取真实路径 |
| 返回含 `target_file_nums_limit` / `non_vip_limit` / `target_file_nums` | 转存文件数超限 | **终态失败，不重试**，文案：`百度网盘限制：转存文件数超限，（本次分享约 {} 个文件，上限 {} 个）；请开通会员或改用文件更少的分享链接` |
| 以上都不是 | 瞬时故障 | 可重试 |

⚠️ **4. 空间不足必须立即停止整批**，抛 `PanQuotaError`，不要继续后面的条目。

#### 失败归类（`fail_kind`，与状态列共用）

把任意失败文案压成最短状态词：
```
空间不足 / 文件数超限 / 网盘限制 / 转存数量上限 / 登录态失效 / 缺少提取码 /
提取码错误 / 已失效 / 已被取消 / 链接失效 / 链接格式错误 / 分享为空 /
目标目录不存在 / 文件名非法 / 风控限流 / 网络异常
```
完整原话保留在该行的 tooltip / 备注字段里。

#### 验收标准
- [ ] 喂入同时含 `uk=0` 和 `share_uk=12345` 的分享页样本，断言用的是 12345
- [ ] 转存返回含 `extra.list[].to_fs_id` 时，断言未发出列目录请求
- [ ] errno 12 + `duplicated.list` → 判为「重复跳过」且 `retryable=False`
- [ ] errno 12 + `target_file_nums_limit` → 判为「文件数超限」且 `retryable=False`
- [ ] errno 12 + 以上都无 → 判为可重试
- [ ] 空间不足 → 抛 `PanQuotaError`

---

### M10 `pan_share` — 分享（独立模块）

**工期：0.5 人日**

#### 职责
对已在自己网盘中的文件创建分享链接。

#### 对外接口
```python
def generate_pwd(length: int = 4) -> str
def random_ua() -> str

class PanClient:   # 续 M08
    def share_files(self, fsids, bdstoken, pwd) -> dict
    def transfer_link(self, url, target_path, do_share: bool,
                      pwd: str = None) -> dict
```

#### 关键实现
```
POST https://pan.baidu.com/share/set?channel=chunlei&web=1&app_id=250528&bdstoken={}&clienttype=0
body: schannel=0&channel_list=[]&period=0&pwd={}&fid_list={}

返回取 link 或 shorturl：
  有 shorturl → https://pan.baidu.com/s/{shorturl}
  最终链接拼上 ?pwd={pwd}
```

提取码字符集：`abcdefghijklmnopqrstuvwxyz0123456789`（4 位）

**`transfer_link` 是 M09+M10 的组合入口**，返回：
```python
{
  "status": "转存成功" | "转存成功，分享失败" | "重复跳过" | "失败",
  "share_url": "...", "share_pwd": "...",
  "dup_paths": [...], "retryable": bool, "message": "..."
}
```

#### 已知陷阱
⚠️ 分享失败但转存已成功时，状态必须是 `转存成功，分享失败` 而不是 `失败` —— 文件已经在网盘里了，重跑会产生重复。

⚠️ 错误映射：
```
分享失败：无权限
分享失败：提取码格式错误
分享被风控/请求过于频繁（errno={}），请稍后重试
```

#### 验收标准
- [ ] `generate_pwd` 输出 4 位，字符集正确，1000 次不重复率合理
- [ ] 转存成功 + 分享失败 → status 为 `转存成功，分享失败`
- [ ] 最终链接格式为 `https://pan.baidu.com/s/xxx?pwd=yyyy`

---

### M11 `zhidao_parse` — 百度知道页面解析（纯函数，无网络）

**工期：1.5 人日**

#### 职责
解析百度知道搜索页和详情页，抽取网盘链接、提取码、资源名。**本模块不发任何请求**，输入是 HTML 字符串。

#### 对外接口
```python
def parse_search_page(html: str) -> tuple[list[dict], int | None]
def classify_search_html(html: str, items: list) -> str   # normal/empty/unknown
def normalize_pan_url(url: str) -> str
def link_key(url: str) -> str
def extract_pan_entries(text: str) -> list[dict]          # [{link, pwd}]
def extract_pan_links(text: str) -> list[str]
def extract_pwd(text: str, link: str) -> str
def strip_spam_letters(name: str) -> str
def clean_title_for_name(title: str) -> str
def extract_resource_name(title: str) -> str
def has_concrete_name(title: str) -> bool
def guess_resource_name(question_title: str, text: str, link: str) -> str
def within_range(item_date: str, days: int) -> bool
```

#### 关键正则（原样照抄）

```python
# 搜索结果条目
r'<a[^>]+href="([^"]*zhidao\.baidu\.com/question/(\d+)\.html\?fr=(?:iks|search)[^"]*)"[^>]*>(.*?)</a>'

# 日期
r'(20\d{2}-\d{2}-\d{2})'

# 网盘链接
r'https?://pan\.baidu\.com/s/[0-9A-Za-z_-]+(?:\?[^\s<>"\'，。；、）】｝」》\u3000]*)?'

# 提取码
r'(?:提取码|提取密码|访问码|密码)\s*[:：]?\s*([0-9A-Za-z]{4})\b'
r'(?:^|[?&])pwd=([0-9A-Za-z]{4})'

# 书名号内容
r'[《]([^》]{2,40})[》]'

# 带扩展名的资源名
r'([\u4e00-\u9fffA-Za-z0-9_\-《》:：&（）()]{2,40})\.(?:txt|epub|mobi|pdf|docx?|xlsx?|pptx?|zip|rar|7z|mp4|mp3|flac|apk|exe|iso)(?![A-Za-z0-9_])'

# 标题前缀剥离
r'^(?:求|有一个|谁有|哪里|哪里有|谁能|我要|找|有没有)[:：]?\s*'

# 类型词前缀剥离
r'^(?:小说|电影|电视剧|动漫|动画|番剧|综艺|短剧|游戏|单机游戏|软件|资料|学习资料|教程|课程|素材|写真|资源|纪录片)[:：]?\s*'

# 泛指词（判定为无具体名称）
r'^(这个|那个|外部|这部|这本|那个|那部|一本|一部|它|这游戏|这个游戏|这资源|这个资源)'

# 分页
r'[?&]pn=(\d+)'
r'href="([^"]+)"[^>]*class="[^"]*pager-next'
r'class="[^"]*pager-next[^>]*href="([^"]+)"'

# 详情页标题
r'<title>([\s\S]*?)_百度知道</title>'

# 正文清理
r'^(收起|展开全部)\s*'
r'\s+by\s+[\u4e00-\u9fffA-Za-z0-9_－]{1,20}$'
```

#### 已知陷阱

⚠️ **1. `strip_spam_letters` —— 引流字符穿插清洗。**
原系统 docstring 原话（重要，逻辑容易写错）：

> 判定标准：**同一个字母在汉字之间插入 ≥2 次**才算干扰。
> - `凡I人I修I仙` → `I` 出现 3 次 → `凡人修仙`
> - `斗l破l苍l穹ltlxlt` → `l` 出现多次 → `斗破苍穹`
> 只出现一次的字母**一律不动**：`战Q神` / `大l陆` 这类保持原样。
> 宁可漏掉偶发一次的，也不要误伤真实的 `战Q神` 变成 `战神`。
> 英文名、数字前缀（`9_`）、版本号（`IPX-580`）同样不受影响。

匹配用：`(?<=[\u4e00-\u9fff])([A-Za-z])(?=[\u4e00-\u9fff])`，统计同一字母出现次数，≥2 才剔除。

⚠️ **2. 这个清洗规则必须在采集端和模板端共用一套。** 否则同一个资源在两处的名称会不一致。

⚠️ **3. 详情页四态判定：**

| 状态 | 判据 | 处理 |
|---|---|---|
| `ok` | 命中正文容器 | 正常 |
| `dead` | 问题已被百度删除 | 跳过，**实测占详情页 1/4 以上，不是异常** |
| `fallback` | 容器都没命中，退回整页 | 可用但要通过 `on_warn` 上报（百度改版信号） |
| `empty` | 什么都没拿到 | 跳过 |

⚠️ **4. 搜索页三态：** `normal`（有结果）/ `empty`（正常的"没有结果"页）/ `unknown`（结构异常或风控）。
原系统 docstring：「有时页面是豆腐块的安全验证页，已被上游拦截；这里只区分"正常空结果页"和"结构异常页"，作用是不把"没有资源"和"被限制"混为一谈」。

#### 验收标准
- [ ] `凡I人I修I仙` → `凡人修仙`
- [ ] `战Q神` → `战Q神`（不变）
- [ ] `IPX-580` → `IPX-580`（不变）
- [ ] `9_斗破苍穹.txt` → `斗破苍穹`
- [ ] 给出 dead / fallback / empty / ok 四份详情页样本，各自分类正确
- [ ] 给出 normal / empty / unknown 三份搜索页样本，各自分类正确
- [ ] `求XXX百度网盘链接` → 资源名 `XXX`
- [ ] `这个游戏谁有` → `has_concrete_name` 为 False

---

### M12 `behavior` — 人类行为模拟

**工期：0.5 人日**

#### 职责
浏览器指纹、账号级请求节奏、常规问题穿插。**只负责"像人"，不负责风控决策**（那是 M13）。

#### 对外接口
```python
def pick_profile() -> dict          # {ua, sec_ch_ua, platform}
def pick_common_question(used: set) -> str
def shuffle_blocks(items: list, size: int) -> list
def pick_every(rng_range: tuple) -> int

class HumanPacer:
    def __init__(self, gap_range=(6,10), break_after_range=..., break_range=...): ...
    def wait_time(self, now: float) -> float
    def note_request(self, read_seconds: float) -> tuple[bool, float]
    def cool_down(self, seconds: float) -> None
    def stagger(self, seconds: float) -> None
    def reset(self) -> None
```

#### 指纹表（8 套，原样照抄）

| UA | sec-ch-ua | platform |
|---|---|---|
| Chrome/124 Win | `"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"` | `"Windows"` |
| Chrome/126 Win | `"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="99"` | `"Windows"` |
| Chrome/128 Win | `"Chromium";v="128", "Google Chrome";v="128", "Not-A.Brand";v="99"` | `"Windows"` |
| Chrome/130 Win | `"Chromium";v="130", "Google Chrome";v="130", "Not-A.Brand";v="99"` | `"Windows"` |
| Edge/126 Win | `"Chromium";v="126", "Microsoft Edge";v="126", "Not-A.Brand";v="99"` | `"Windows"` |
| Edge/129 Win | `"Chromium";v="129", "Microsoft Edge";v="129", "Not-A.Brand";v="99"` | `"Windows"` |
| Chrome/127 macOS | `"Chromium";v="127", "Google Chrome";v="127", "Not-A.Brand";v="99"` | `"macOS"` |
| Firefox/128 Win | （Firefox 不发 sec-ch-ua） | `"Windows"` |

完整 UA 串见原系统提取结果，例：
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36
Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0
```

#### 节奏参数
- 账号内请求间隔：**6–10 秒**
- 周期性长休息：按 `break_after_range` 次请求后休息 `break_range` 秒
- `shuffle_blocks`：块内洗牌，保留整体顺序但打散相邻同类关键词

#### 验收标准
- [ ] `pick_profile` 返回的三个字段互相匹配（Firefox 的 profile 不带 sec-ch-ua）
- [ ] `HumanPacer` 连续 note_request 后，wait_time 落在 6–10 秒区间
- [ ] `cool_down` 能打断正常节奏
- [ ] `shuffle_blocks(list(range(20)), 5)` 的结果每 5 个一组内部被打乱，组间顺序不变

---

### M13 `pool` — 账号池与风控编排

**工期：2 人日 | ⚠️ 全项目最精密的模块**

#### 职责
双账号 × 双出口的统一请求入口 + 风控分级响应。

#### 对外接口
```python
class PoolError(Exception): ...
class CollectCancelled(Exception): ...

def is_risk_html(html: str) -> bool

class AccountSlot:
    def __init__(self, name, cookie, exit_kind): ...
    def reroll_profile(self) -> None
    def proxies(self, pool) -> dict

class SlotPool:
    def __init__(self, accounts, pause_ask, on_log, stop_event, on_status): ...
    def start(self) -> None
    def acquire(self) -> AccountSlot
    def note_request(self, slot, read_seconds) -> None
    def probe_slot(self, slot) -> bool
    def on_risk(self, slot, reason) -> bool
    def on_silent_risk(self, keywords, page) -> bool

class PooledFetcher:
    def get(self, url, referer=None, timeout=None, purpose="search") -> tuple[str, AccountSlot]

class PinnedExitFetcher(PooledFetcher):
    """固定走某个出口（默认直连槽），用于补量"""
```

#### 核心设计（原系统 docstring，必须完整实现）

```
账号1 走直连、账号2 走 Clash 代理；两个账号交替请求，各自保持 6–10 秒间隔。

风控编排（偶发验证页静默处理，只有"全部账号都不能用"才打扰用户）：

  命中「安全验证页」 → 只让那个账号歇 10–20 秒、另一个继续，不弹窗

  同一个号连续命中 3 次 → 只给这个号做一次常规问题的健康探针
      探针正常  → 偶发，继续
      探针异常  → 这个号先被静默停用（冷却 60–90 秒），继续用其它正常账号，
                  冷却结束自动放回来重试（还是不行就再停用）

  只有所有账号都探针异常、一个能用的都不剩 → 才提示用户换节点 / 开 Clash
      换完只清状态、重随机指纹与节奏，不把两个账号塞进同一个出口

单号（只配了一个采集账号）没有"另一个号顶上"，用同一套思路的静默版：
  偶发命中照样静默降速；探针复核也异常时，先静默冷却若干轮
  （60–90 → 90–150 → 120–180 秒，每轮结束自动接着重试、不弹窗），
  只有轮次用完还是被限制，才提示用户开 Clash / 换节点。
```

#### 关键常量

| 参数 | 值 |
|---|---|
| 账号内请求间隔 | 6–10 秒 |
| 偶发命中冷却 | 10–20 秒 |
| 连续命中触发探针阈值 | 3 次 |
| 探针异常后停用冷却 | 60–90 秒 |
| 单号静默冷却三轮 | 60–90 → 90–150 → 120–180 秒 |
| 健康探针 URL | `https://zhidao.baidu.com/search?lm=0&rn=10&pn=0&fr=search&dyTabStr=null&word={常规问题}` |

#### 请求头（固定，原样）
```
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8
Accept-Language: zh-CN,zh;q=0.9
Connection: keep-alive
Referer: https://zhidao.baidu.com/
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: same-origin
sec-ch-ua: <来自 profile>
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: <来自 profile>
Cookie: <账号槽的 cookie>
```

#### 已知陷阱

⚠️ **1. 健康探针用的是"与采集无关的常规问题"**，不能用当前正在采的关键词 —— 否则分不清是"被限制"还是"真没有这个资源"。

⚠️ **2. 换节点之后只清风控标记与连续计数、重随机指纹和节奏，不改出口类型。** 不要把两个账号都塞进代理。

⚠️ **3. `on_silent_risk`（连续多页/多词无内容）必须先探针复核再决定要不要打扰用户。** 探针正常 = 确实没有资源，继续；探针异常 = 真被限制。这个区分是整个采集不误报的关键。

⚠️ **4. 所有 sleep 必须可被 `stop_event` 打断**（分块 sleep，每块检查一次），否则用户点停止要等一分钟。

#### 验收标准
- [ ] 双账号场景：账号1 命中风控 2 次，断言账号2 持续工作、无弹窗、无探针
- [ ] 双账号场景：账号1 连续命中 3 次且探针异常 → 断言它被停用、账号2 继续、仍无弹窗
- [ ] 双账号场景：两个账号都探针异常 → 断言触发 `pause_ask` 弹窗回调
- [ ] 单号场景：探针异常 → 断言进入静默冷却，冷却时长依次为 60–90 / 90–150 / 120–180
- [ ] 单号场景：三轮用完仍异常 → 断言触发 `pause_ask`
- [ ] 冷却期间 `set` stop_event → 断言 1 秒内退出
- [ ] `PinnedExitFetcher` 在指定出口槽不存在时，退回池默认分配而不是卡死

---

### M14 `collect` — 采集调度（原主线①）

**工期：2.5 人日**

#### 职责
把 M11/M13/M15 组装成完整采集任务。两种模式：精准、模糊。

#### 对外接口
```python
class CollectWorker:
    def __init__(self, *, keyword=None, txt_paths=None, count=0,
                 time_range="auto", accounts=None, detail_mode=True,
                 dedupe_names=True, mode="precise", resume=False,
                 checkpoint_path=None,
                 on_item=None, on_progress=None, on_status=None,
                 on_log=None, pause_ask=None): ...
    def run(self) -> dict
    def stop(self) -> None
    def resume_after_risk(self, do_continue: bool) -> None
```

> ⚠️ 注意：原系统这里是 `QThread` + Qt Signal。**本次重建用普通 callback，不引入 Qt。**
> `pause_ask(payload) -> bool` 同步阻塞回调，返回 True=已换节点继续，False=停止任务。

#### 两种模式

| | 精准 | 模糊 |
|---|---|---|
| 输入 | TXT 关键词表 | 领域 + 目标条数 |
| 每词产出 | 最多 1 条 | 不限 |
| 时间范围 | 固定 | 自动放宽：最近一月 → 一年 → 全部 |
| 终止条件 | 关键词跑完 | 够数 / 源枯竭 |
| 额外过滤 | — | 跳过没有具体资源名的标题 |

#### 搜索 URL
```
https://zhidao.baidu.com/search?lm=0&rn=10&pn={pn}&fr=search&dyTabStr=null&word={keyword}
模糊模式的关键词模板：求{kw}百度网盘链接
```

#### 关键阈值（原样）

| 参数 | 值 | 触发行为 |
|---|---|---|
| 连续无结果关键词数 | 5 | 做一次风控复核（探针） |
| 连续空页数 | 5 | 做一次风控复核 |
| 拟人穿插频率 | 每 3–6 次真实搜索 | 插一条常规问题搜索 / 点开一条回答页（结果不入表） |
| 页面正常但无网盘链接的连续词数 | 达阈值 | **判定为确实没有资源，不重搜直接继续** |
| 重搜次数上限 | 见原文案 | `连续 {} 个关键词被限制，重搜 {} 次仍无结果，跳过继续后面的关键词` |

#### 统计口径（结束汇总用）
```
found / skipped_generic（模糊过滤掉的无具体名标题）/ no_link（无网盘链接）/
no_pwd（有链接缺提取码）/ dead（问题已删）/ detail_empty / parse_warn /
barren_pages / abnormal_pages / idle_pages
```

#### 补量
站内采不够时，用 M07 走百度网页搜索补量。
⚠️ **补量必须固定走直连出口**（`PinnedExitFetcher`），不要落到代理账号上。
⚠️ 补量遇到风控提前结束补量，**已采结果保留**。

#### 已知陷阱

⚠️ **1. 去重用两套键**：`link_key`（链接归一化后）和 `name`（资源名）。日志分别输出 `跳过重复链接：{}` / `跳过重复名称：{}`。

⚠️ **2. 分页 pn 未前进时必须停止该查询翻页**，否则死循环。文案：`分页 pn={} 未继续前进，停止该查询翻页`。

⚠️ **3. 时间范围自动放宽只在模糊模式生效**，文案：`时间范围自动放宽到「{}」继续采集…`。

⚠️ **4. 长时间未收到处理结果要自动停止**：`长时间未收到处理结果，已自动停止采集并保留已采结果。`

#### 验收标准
- [ ] 精准模式：10 个关键词，每词最多产出 1 条
- [ ] 模糊模式：目标 20 条，时间范围依次放宽三档
- [ ] 连续 5 个关键词无结果 → 断言调用了探针
- [ ] 拟人穿插：跑 20 次真实搜索，断言插入了 3–7 次常规问题且这些结果未进入结果表
- [ ] 中途 `stop()` → 已采结果完整保留，断点已落盘
- [ ] 分页 pn 不前进的 mock → 断言退出该关键词而非死循环

---

### M15 `checkpoint` — 断点续跑

**工期：0.5 人日**

#### 职责
采集/转存/模板生成三类任务的进度落盘与恢复。

#### 对外接口
```python
def checkpoint_path(source: str, kind: str) -> str
def operation_path(source: str, kind: str) -> str
def find_operations(kind: str) -> list[dict]
def load(path: str) -> dict
def save(path: str, payload: dict) -> None
def clear(path: str) -> None
def clear_collect() -> None
def clear_operations(kind: str) -> None
def clear_all() -> None
def prune(max_age_days: int = 7, keep: int = 50) -> None
```

#### 采集断点 payload 字段
```
精准：items, seen_keys, seen_names, done_keywords, keywords, found
模糊：items, seen_keys, seen_names, done_queries, found
```

#### 验收标准
- [ ] 保存 → 读取，字段完整
- [ ] `prune` 删除超过 7 天的文件，保留最近 50 个
- [ ] 断点文件损坏（非法 JSON）时，`load` 返回空 dict 而非抛异常

---

### M16 `miner_parsers` — 挖词站点解析器（20+ 站点）

**工期：3 人日 | 体量最大**

#### 职责
从 20+ 个公开榜单站点抓取热门资源名称。**全部免登录、免 Cookie，服务端直出页面或 JSON。**

#### 站点清单（按分类）

| 分类 | 数据源 |
|---|---|
| 小说 | 七猫大热榜(男频/女频)、七猫最新上架(男/女)、纵横人气榜、飞卢热门总榜、17K首页榜单 |
| 电影 | 豆瓣电影·热门、豆瓣电影·最新、豆瓣华语电影·最新、豆瓣·动漫电影、猫眼当年票房榜 |
| 电视剧 | 豆瓣剧集·热门/国产剧/日剧/韩剧/美剧/英剧/最新 |
| 动漫 | 豆瓣·日本动画、豆瓣动漫电影、红果漫剧热播榜 |
| 短剧 | 红果热播榜/真人榜/AI榜、豆瓣短剧 |
| 游戏 | TapTap 热门/新品/预约、Steam 热销/最多在线、应用宝、3DM、游民星空热门/榜单、阿里榜 |
| 软件 | 华军(onlinedown) 热门/最新、宝库、非凡(crsky) 热门/最新、423down |

#### 对外接口
```python
def clean_name(raw: str) -> str
def canonical_key(name: str) -> str
def is_mass_software(name: str) -> bool
def is_mass_game(name: str) -> bool
def strip_trailing_version(name: str) -> str
def looks_like_body_text(name: str) -> bool

# 每个站点一对：
def parse_<site>(body: str) -> list[str]
def fetch_<site>(sess, need: int, stop_event, on_log) -> list[str]
```

#### 全局参数（原样）
```python
PACE_RANGE = (2.5, 4.5)          # 每请求随机停顿秒数
HONG_GUO_MAX_PAGE = 5
HISTORY_KEEP_DAYS = 7
HISTORY_MAX_ENTRIES = 20000
HISTORY_FILE_NAME = "挖词历史.json"
FRESH_SOURCE_SHARE = 0.3         # 配额中留给"最新"类源的比例
UA_LIST = [Chrome/126 Win, Chrome/125 Win, Firefox/126 Win, Edge/124 Win]
```

#### 过滤规则

**① 大众软件黑名单**（这些名字没有拉新价值，必须剔除，共 60+ 条）：
```
微信, 企业微信, QQ, TIM, 钉钉, 飞书, 微博, 小红书, 抖音, 抖音极速版, 快手, 快手极速版,
虎牙, 斗鱼, 哔哩哔哩, B站, 爱奇艺, 优酷, 腾讯视频, 芒果TV, 搜狐视频, 西瓜视频, 乐视,
网易云音乐, 酷狗音乐, QQ音乐, 酷我音乐, 汽水音乐, 百度网盘, 阿里云盘, 夸克网盘, 115网盘,
迅雷网盘, 百度云管家, 迅雷, 豆包, 人人视频, 飞球直播, 360安全卫士, 360安全浏览器,
360极速浏览器, 360压缩, 360驱动大师, 360软件管家, 360安全桌面, 360游戏保险箱, 鲁大师,
金山毒霸, 2345安全卫士, 谷歌浏览器, Google Chrome, Microsoft Edge, 搜狗输入法,
百度输入法, QQ输入法, 2345浏览器, WPS Office, Office365, 腾讯电脑管家, 人人网, 多邻国,
高途, 剪映
```

**② 大众游戏黑名单**（40+ 条）：
```
王者荣耀, 王者万象棋, 和平精英, 原神, 崩坏：星穹铁道, 崩坏星穹铁道, 崩坏3, 蛋仔派对,
金铲铲之战, 第五人格, 阴阳师, 梦幻西游, 大话西游, 问道, 倩女幽魂, 明日方舟, 部落冲突,
开心消消乐, 欢乐斗地主, 欢乐麻将, 天天爱消除, 元梦之星, 光·遇, 光遇, 我的世界,
火影忍者, 三国志·战略版, 率土之滨, 皇室战争, 荒野乱斗, 使命召唤手游, 穿越火线,
地下城与勇士, DNF, 英雄联盟手游, 超自然行动组, 红果免费短剧, 番茄免费小说, 元宝
```

**③ 版本号剥离**（仅对 软件/游戏 分类生效）：
```regex
(?:[第]?[一二三四五六七八九十百千万\d]+[季部册集]|S\d{1,3}|Season\s*\d+|\s+[vV]\d[\d.]*\w*|
\s+\d+(?:\.\d+)+\w*|\s*\d+位|x64|x86|win\d[\d\- ]*64位|win\d+|正式版|绿色版|便携版|
中文版|汉化版|破解版|免安装版|官方版|纯净版|远程控制软件|远程控制|下载工具|下载器|播放器)$
```
```regex
[（(]\s*v?[\d.]+[^）)]*[）)]|\s+[vV]\d[\d.]*.*$|
(中文版|直装版|绿色版|便携版|正式版|破解版|汉化版|官方版|纯净版|免安装版|解锁.*|
豪华版|企业版|专业版|旗舰版|增强版|标准版).*$
```

**④ 季/部/卷后缀归一（内容类分类）**：
```regex
(?:第[一二三四五六七八九十百千万零〇\d]+[季部卷集版]|Part\s*\.?\s*\d+|OVA|重制版|重置版|
导演剪辑版|加长版|剧场版|完整版)
```

**⑤ 正文误抓判断**：`looks_like_body_text` —— 名称超长（`_MAX_NAME_LEN=30`）或含句子特征时丢弃。

#### HTML 清洗正则
```regex
_SCRIPT_RE = <script[\s\S]*?</script>|<style[\s\S]*?</style>
_TAG_RE    = <[^>]+>
_ANCHOR_RE = <a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>
_HEADING_RE= <h([1-4])\b[^>]*>([\s\S]*?)</h\1>
```

#### 已知陷阱
⚠️ **1. Steam 需要代理**（`_steam_proxy()` / `_use_proxy()` contextmanager）。其他站点不需要。
⚠️ **2. 响应编码要强制 UTF-8**（`_force_utf8`），部分站点 header 声明错误。
⚠️ **3. 每个请求之间随机停顿 2.5–4.5 秒**，等待期间可被 stop_event 打断。
⚠️ **4. 任何单站失败不影响整体**，记录日志后继续下一个源。

#### 验收标准
- [ ] 每个 `parse_<site>` 都有一份离线 HTML/JSON 样本 + 对应的期望输出（**这是本模块的主要测试量**）
- [ ] 黑名单过滤：输入含 `微信` / `王者荣耀` 的列表，断言被剔除
- [ ] 版本号剥离：`Photoshop 2024 v25.0 绿色版` → `Photoshop`
- [ ] 季数归一：`鬼灭之刃 第三季` → `鬼灭之刃`
- [ ] `looks_like_body_text`：超过 30 字的句子被判为正文

---

### M17 `miner` — 挖词调度

**工期：1 人日**

#### 职责
按「领域 + 数量」编排 M16 的各个源，产出关键词 TXT。

#### 对外接口
```python
CATEGORIES = ("小说", "电影", "电视剧", "动漫", "短剧", "游戏", "软件")

def collect_hot_names(category: str, target: int, save_path: str,
                      stop_event, on_log,
                      add_prefix: bool = True,
                      history_path: str = None,
                      history_days: int = 7,
                      shuffle: bool = True) -> dict
def prune_history(history_path: str, keep_days: int = 7) -> None
```

#### 关键实现

**① 配额规划（`_plan_quotas`）**：按分类对应的源列表分配 target 名额，其中「最新」类源占 `FRESH_SOURCE_SHARE = 0.3`。

**② 历史去重**：按 `canonical_key(name)` 记录，保留 7 天 / 最多 20000 条，落盘为 `挖词历史.json`。

**③ 搜索补量**：站点源不够时，用搜索引擎抓榜单文章补量。搜索模板（原样）：

| 分类 | 查询模板 |
|---|---|
| 小说 | `2026年热门小说排行榜`、`2026年{月}月小说人气榜`、`2025年热门小说排行榜` |
| 电影 | `2026年热门电影排行榜`、`2026年{月}月电影票房榜`、`2025年热门电影排行榜` |
| 电视剧 | `2026年热门电视剧排行榜`、`2026年{月}月电视剧热播榜`、`2026年国产剧排行榜` |
| 动漫 | `2026年热门动漫排行榜`、`2026年{月}月新番推荐`、`2026年日本动画热门榜` |
| 短剧 | `2026年热门短剧排行榜`、`2026年{月}月短剧热播榜`、`2026年{月}月红果短剧热播榜`、`2026年红果短剧热播榜`、`2026最火短剧TOP10`、`2026年爆款短剧名单`、`2026年短剧百强榜`、`2026年真人短剧热播榜`、`2026年短剧播放量排行榜`、`2025年热门短剧排行榜` |
| 游戏 | `2026年热门手游排行榜`、`2026年{月}月手游下载榜`、`2026年热门单机游戏`、`2025年热门单机游戏`、`2026年PC游戏热门榜`、`2026年Steam热销游戏`、`2026年TapTap热门游戏` |
| 软件 | `2026年热门电脑软件`、`2026年常用电脑工具软件` |

⚠️ **年份是硬编码的 2026/2025。** 重建时保持，但在代码中提取为常量并加注释，便于跨年时修改。

**④ 搜索结果停用词**（判断候选是否为榜单标题而非资源名）：
```
排行榜, 榜单, 盘点, 推荐, 名单, 排名, 前十, TOP, No., 2026, 2025, 年, 月, 日,
短剧, 手游, 游戏, 单机, 电影, 电视剧, 动漫, 小说, 软件, 动画, 新番, 热播, 红果,
Steam, TapTap, PC, 第, 第一, 第二, 第三
```

**⑤ 输出**：每行一个关键词的 TXT。`add_prefix=True` 时给名称加上采集用前缀。

#### 返回值
```python
{"count": int, "saved_path": str, "stopped": bool, "reason": str}
```

#### 验收标准
- [ ] 7 个分类各能跑通（可用 mock 源）
- [ ] 中途 stop → 返回 `stopped=True` 且已挖部分已保存
- [ ] 同一名称第二次挖词被历史去重过滤
- [ ] 历史超过 7 天被 prune 清理
- [ ] 配额规划：target=100 时，「最新」类源分到约 30 个名额

---

### M18 `pipeline` — CLI 与端到端编排

**工期：1 人日**

#### 职责
把全部模块串成可执行命令。**这是交付给用户主程序调用的入口。**

#### CLI 设计
```bash
lxds mine     --category 小说 --count 200 --out keywords.txt
lxds collect  --mode precise --keywords keywords.txt --out collected.xlsx
lxds collect  --mode fuzzy   --category 小说 --count 100 --out collected.xlsx
lxds transfer --in collected.xlsx --target /我的资源 --share --out transferred.xlsx
lxds template --in transferred.xlsx --out qa.xlsx
lxds publish  --in qa.xlsx --account <账号名>
lxds answer   --question "..." --style first_person
lxds run      --config pipeline.yaml       # 全流程
```

#### 全流程编排（`lxds run`）
```
mine → collect → [转存：本地 M09/M10 或 交给 C#] → template → publish
```

**转存环节二选一，配置决定：**
```yaml
transfer:
  mode: local          # local = 用 M09/M10；external = 导出文件交给 C#
  external_inbox: "D:/exchange/to_csharp"
  external_outbox: "D:/exchange/from_csharp"
```
`external` 模式下：导出 xlsx 到 inbox，然后轮询 outbox 等待结果文件出现。

#### 已知陷阱
⚠️ 每一步的输出都必须落盘（不要只在内存里传递），这样任一步失败后可以从中间文件接着跑。

#### 验收标准
- [ ] 每个子命令可独立运行
- [ ] `lxds run` 全流程跑通（可用 mock）
- [ ] 中间文件全部落盘且格式符合 §3.1
- [ ] `external` 模式能正确等待并读取 C# 产出的结果文件

---

## 5. C# 侧改动（4 项）

> 目标项目：`C:\Users\45203\Documents\dakazhandian`
> ⚠️ **注意：真实代码在 `.worktrees/transfer-share-link-replacement` 工作树，不是仓库根目录。** 根目录的 src 停在 8 月且转存方法全是桩。

### C01 首次真实端到端验证（前提，必须最先做）

**工期：0.5 人日**

#### 背景
该项目至今**没有任何一次成功的真实百度端到端运行记录**，输出目录 `转存分享结果/` 为空。后续三项改动都建立在"真实返回结构"之上，不先跑通就是盲改。

#### 任务
1. 用**一次性测试账号**（绝不能用生产账号）
2. 手工跑通 1 条真实转存 + 分享
3. 抓取并存档以下真实响应的完整 JSON：
   - `/share/verify` 成功响应
   - `/share/list` 成功响应
   - `/share/transfer` 成功响应（含 `extra.list[].to_fs_id`）
   - `/share/transfer` **重复文件**响应（含 `duplicated.list`）
   - `/share/transfer` **文件数超限**响应（含 `target_file_nums_limit`）
   - `/share/set` 成功响应
4. 存档路径：`tests/fixtures/live-baidu-responses/`

#### 验收标准
- [ ] 6 份真实响应 JSON 已存档
- [ ] `转存分享结果/` 目录产出了第一个真实结果文件

---

### C02 `errno 12` 拆分

**工期：2.5 人日 | 穿透 5 层**

#### 问题
`src/BaiduBatchTransfer.BaiduAdapter/Http/BaiduWebApiClient.cs` 第 733 行附近：
```csharp
-8 or 12 or 31034 => BaiduErrorKind.TransientService,
```
`errno 12` 被一律当成瞬时故障并重试。但它实际有三种含义（见 M09 已知陷阱 3），其中两种重试是无效的。

#### 后果
- 「文件已存在」被当作失败并无谓重试直到耗尽
- 「转存文件数超限」被当作失败并无谓重试，最终报一个无用的错误

#### 改动清单（五层）

| 层 | 文件 | 改动 |
|---|---|---|
| 1. Core | `Core/Domain/BaiduErrorKind.cs` | 新增 `DuplicateSkipped`、`FileCountLimitExceeded` 两个枚举值 |
| 2. Adapter | `BaiduAdapter/Http/BaiduWebApiClient.cs` | `EnsureSuccess` 中对 errno 12 细分：检查 `duplicated.list` → `DuplicateSkipped`；检查 `target_file_nums_limit` / `non_vip_limit` / `target_file_nums` → `FileCountLimitExceeded`；否则 `TransientService`。同时解析出 `duplicated.list[].path` 与上限数字 |
| 3. Application | `Application/Scheduling/OperationExecutor.cs` | 两个新 Kind 标记为**不可重试**；`DuplicateSkipped` 计入成功而非失败 |
| 4. Infrastructure | SQLite 状态枚举与投影仓储 | 新增两种状态的持久化与读回 |
| 5. App | 结果列表状态显示 | 新增两种状态的文案与配色（对齐 Python：`重复跳过` 用橙色，`文件数超限` 用红色） |

#### 测试影响面（已统计）
- `TransientService` 在测试中有 **60 处**断言，需逐一检查是否涉及 errno 12
- 新增枚举值会波及所有 `switch` 表达式

#### 验收标准
- [ ] 用 C01 存档的真实「重复文件」响应，断言判为 `DuplicateSkipped` 且 `retryable == false`
- [ ] 用 C01 存档的真实「文件数超限」响应，断言判为 `FileCountLimitExceeded` 且 `retryable == false`
- [ ] 其他 errno 12 响应仍判为 `TransientService` 且可重试
- [ ] 全量测试通过
- [ ] **交叉验证**：同一批链接用 Python M09 和 C# 各跑一次，errno 12 的三种分支判定结果一致

---

### C03 结果表改为超集

**工期：1.5 人日**

#### 问题
C# 结果表表头：
```
源行号 | 分享链接 | 状态 | 账号 | 目标目录 | 备注 | 错误
```
缺少名称列，Python 侧 M02 无法识别资源名。

#### ⚠️ 明确不要做的事
**不要把结果表"对齐"成 Python 的三列。** 「状态/账号/目标目录/错误」是批量作业的排错命脉，删掉等于把批量转存变成黑盒。

#### 正确改法：超集
```
资源名称 | 分享链接 | 提取码 | 状态 | 账号 | 目标目录 | 备注 | 错误
└─ Python 自动读这三列 ─┘└──── 保留给人看，Python 自动忽略 ────┘
```

#### 为什么只加两列
- 「分享链接」已包含"链接"二字，Python 的模糊匹配天然识别 → **不用改列名**
- Python 模板生成不读提取码（链接自带 `?pwd=`），但加上对人有用 → **加**
- 真正缺的只有「资源名称」→ **必须加**

#### 改动
- `Infrastructure/Excel/OpenXmlResultWriter.cs`：表头数组加两列，行写入补两个值
- 相关测试：表头断言有 **63 处**，需修订受影响部分

#### 验收标准
- [ ] 导出的结果表前三列为 `资源名称 / 分享链接 / 提取码`
- [ ] 后五列保持原样
- [ ] **用 Python M02 的 `read_resource_table` 直接读这个文件，能正确取到 name 和 link**（这是本项验收的硬指标）

---

### C04 导入侧补列名

**工期：0.5 人日**

#### 问题
`Infrastructure/Excel/ExcelColumnSuggestionEngine.cs` 的链接列候选名中**没有「资源链接」**，而这正是 Python 导出的列名。

现有候选：
```csharp
"分享链接", "原分享链接", "链接", "share url", "share link", "url", "link",
```

#### 改动
加入 `"资源链接"`。同时建议加入 `"网盘链接"`。

名称列候选已含「资源名称」✅，提取码列候选已含「提取码」✅，无需改动。

#### 验收标准
- [ ] 用 Python M02 的 `write_resource_table` 导出一个文件，C# 导入时自动识别三列，无需人工映射

---

## 6. 里程碑与工期

### 6.1 模块工期汇总

| 批次 | 模块 | 人日 |
|---|---|---:|
| A（可并行） | M01 config, M02 excelio, M03 deepseek, M11 zhidao_parse, M12 behavior, M16 miner_parsers | 6.5 |
| B（可并行） | M04 qa, M05 zhidao_bulk, M07 websearch, M08 pan_auth, M15 checkpoint | 2.5 |
| C（可并行） | M06 template_engine, M09 pan_transfer, M10 pan_share, M13 pool, M17 miner | 6.0 |
| D | M14 collect | 2.5 |
| E | M18 pipeline | 1.0 |
| **Python 小计** | | **18.5** |
| C# | C01 验证, C02 errno12, C03 结果表, C04 列名 | 5.0 |
| **合计** | | **23.5 人日** |

### 6.2 关于工期的说明

此前给出的粗估是 16–21 人日。细拆到 18 个模块后上浮到 23.5，原因：

1. **模块化本身有成本** —— 每个模块要独立可测、独立交付、独立 demo，这是用户明确要求的交付方式，换来的是可并行、可验证、出问题好定位
2. M16（20+ 站点解析器）的测试样本准备被单独计入，此前被低估
3. C02 的五层穿透改动此前按"改一行 switch"估算，实际要过 60 处断言

### 6.3 推荐执行顺序

```
第 1 步  C01  真实跑通验证             ← 必须最先，它决定 C02/C03 怎么改
第 2 步  批次 A（6 个模块可并行）
第 3 步  批次 B
第 4 步  批次 C
第 5 步  C02 + C03 + C04（此时 M09/M10 已完成，可做交叉验证）
第 6 步  批次 D（M14 采集）
第 7 步  批次 E（M18 编排）+ 端到端联调
```

⚠️ **C01 必须排在最前面。** 它只要 0.5 天，但能挡掉 C02/C03 共 4 天的返工风险。

---

## 7. 验收

### 7.1 模块级
每个模块的「验收标准」清单全部勾选，单测通过，demo 可运行。

### 7.2 集成级

| 编号 | 场景 | 通过标准 |
|---|---|---|
| I1 | 挖词 → 采集 | 挖 50 个关键词，精准采集产出 xlsx，格式符合 §3.1 |
| I2 | 采集 → 本地转存 | 用 M09/M10 转存 10 条，产出含新链接的 xlsx |
| I3 | 采集 → C# 转存 | Python 导出的 xlsx 被 C# 直接导入，无需人工映射列 |
| I4 | C# 转存 → 模板生成 | C# 导出的 xlsx 被 M02 直接读取，name/link 正确 |
| I5 | 模板生成 → 发布 | 生成 20 条问答，上传获得 taskId |
| I6 | **交叉验证** | 同一批 20 条链接，Python M09/M10 与 C# 各跑一次，成功/失败/重复跳过的判定**逐条一致** |
| I7 | 全流程 | `lxds run` 从挖词跑到发布，中间文件齐全 |

**I6 是本项目最重要的验收项** —— 它同时验证了 Python 实现的正确性和 C# errno 12 修复的正确性。

### 7.3 风控验收（必须真机真账号）

| 场景 | 通过标准 |
|---|---|
| 双账号连续采集 300 条 | 全程无弹窗，中途单账号风控被静默处理 |
| 单账号连续采集 100 条 | 触发静默冷却三轮后才弹窗 |
| 采集中途点停止 | 1 秒内退出，已采结果完整 |
| 断点续采 | 重启后能接着跑，不重复采已有条目 |

---

## 8. 风险登记

| # | 风险 | 影响 | 应对 |
|---|---|---|---|
| R1 | 百度知道页面改版导致解析失效 | 采集全线中断 | M11 保留 `fallback` 状态 + `parse_warn` 上报；解析正则集中在一个模块，便于热修 |
| R2 | 挖词站点改版 | 单个源失效 | 单站失败不影响整体；每站解析器独立，可单独修 |
| R3 | C# 首次真实运行发现返回结构与假设不符 | C02/C03 返工 | **C01 排在最前面**，就是为了消除这个风险 |
| R4 | DeepSeek 接口变更或模型下线 | 模板/问答生成中断 | M03 是独立模块，换模型只改一处 |
| R5 | 风控策略升级，现有编排失效 | 采集效率下降 | M13 的阈值全部提取为常量，便于调参 |
| R6 | 2026/2025 硬编码年份跨年失效 | 挖词搜索补量质量下降 | M17 中年份提取为常量并注释 |

---

## 9. 附录：本文档事实来源

本 PRD 中所有技术细节提取自 `百度知道拉新大师 v1.0.4`（PyInstaller onedir，Python 3.12，未加密）的字节码，以及 `dakazhandian` 仓库 `.worktrees/transfer-share-link-replacement` 工作树的 C# 源码。

原系统模块规模（供工期参照）：

| 原模块 | 行数 | 对应本 PRD |
|---|---:|---|
| hot_names_collector | 1639 | M16 |
| collect_page | 1282 | （UI，不重建） |
| pan_manage_page | 1168 | （UI，不重建） |
| template_page | 782 | （UI，不重建） |
| collect_worker | 775 | M14 |
| pan_client | 645 | M08+M09+M10 |
| profile_config_widget | 615 | （UI，不重建） |
| collect_pool | 513 | M13 |
| zhidao_scraper | 500 | M11 |
| template_engine | 359 | M06 |
| keyword_mine_dialog | 311 | M17 |
| baidu_web_scraper | 302 | M07 |
| local_config | 198 | M01 |
| collect_behavior | 190 | M12 |
| qa_page | 190 | M04 |
| collect_checkpoint | 136 | M15 |
| template_worker | 110 | M06 |
| deepseek_client | 67 | M03 |
| zhidao_bulk | 65 | M05 |

原系统全项目 12,446 行，其中 UI 层 3,262 行不在重建范围内。

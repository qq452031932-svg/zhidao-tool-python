# 采集结果右键「打开链接」与「检测链接有效性」

日期：2026-10-15（Asia/Shanghai）。用户确认 10-14 第三轮三项复测通过并同意提交（C# `f77e2a82`、外层 `6805a78`），随后要求开始后续功能。本项按交接说明第四节（已确认方案 B）实现，没有重新询问已确认的交互。

## 行为

右键菜单（采集结果表）
- 「打开链接（第 N 条）」：只打开右键指向的那一条，即使已多选也不批量打开。用系统默认浏览器。
  - 原链接是 `https://pan.baidu.com/s/...` 时保留原样（含其他参数），记录有提取码且链接没有 `pwd` 时补上 `pwd=`；已有 `pwd` 不重复添加。
  - 链接自带的提取码与提取码列不一致：按链接原样打开，不覆盖，并提示「打不开时请改用提取码列的值」。
  - `http://`、`share/init?surl=`、`yun.baidu.com` 形式换成等价的 `https://pan.baidu.com/s/1...`；其他网址（非百度、非分享页）不打开，提示原因。最终仍经过原有 `SystemShareLinkLauncher` 的白名单（只放行 https pan.baidu.com/s/）。
- 「检测链接有效性」/「检测选中的 N 条链接」：检测选中的行；没有选中时菜单项不可用，不会悄悄检测全表，要检测全部先「全选」。
- 「停止检测」：检测进行中可用；结果区按钮行同时出现「停止检测」按钮。
- 选择规则：右键落在未选中的行 → 改为只选这一行（不会检测到旧选择）；落在已选中的行 → 保留多选；落在空白处 → 不改选择，「打开链接」不可用。
- 原有「全选 / 反选 / 取消选择」保留。

「链接状态」列（提取码列之后）
- 未检测、检测中、可访问、已失效、提取码问题、暂无法判断。鼠标停留显示原因（含百度返回码）和检测时间，并注明「只代表当时的结果」。
- 可访问 / 已失效 / 提取码问题分别用现有的成功 / 失败 / 警告底色。

检测过程
- 逐条串行，条与条之间间隔 1 秒；结果区显示「正在检测链接 i/N…」。
- 检测期间锁住开始采集、继续、复制、导出、送入转存（沿用结果操作的忙碌标记），新任务不会把结果写到错误的行；结果按行对象写回，与排序、选择变化无关。
- 停止：已检测完的保留；正在检测的那一条恢复原状态（不会标成失效）；没轮到的保持原状态。摘要「已检测 i/N 条：可访问 …，已失效 …，提取码问题 …，暂无法判断 …」。
- 连续 3 条遇到百度验证 / 请求受限（HTTP 403/429/3xx、验证码类返回码、返回 HTML 页面）自动停止，提示过一段时间再测。
- 可重复检测，新结果覆盖旧结果。
- 运行日志每条记「链接检测 第 N 条：状态。原因」，不写链接和提取码。
- 不转存、不下载、不删记录、不随采集自动检测。

## 检测方法（不登录、只读）

1. `GET /api/shorturlinfo?shorturl=1xxx`：errno 0 = 不需要提取码；-9 = 需要提取码；
2. 需要提取码时 `POST /share/verify?surl=xxx`（表单 pwd）：errno 0 返回 `randsk`；-9 = 提取码错误。记录和链接里的提取码不同时两个都试；
3. `GET /share/list?shorturl=xxx`（带 `BDCLND=randsk`）：errno 0 且文件列表非空 → 可访问。

判定：
- 可访问：只有真正读到非空文件列表。
- 已失效：errno 140（实测「啊哦，链接出错了」），或百度提示文字含「链接出错 / 不存在 / 已失效 / 已过期 / 已取消 / 已被删除 / 来晚了 / 违规 / 侵权」。
- 提取码问题：需要提取码而记录和链接都没有；或校验返回 -9。
- 暂无法判断：超时、网络失败、HTTP 非 200、返回 HTML、验证码类返回码（-62/-63/-64/9019）、缺少状态码、列表为空、其他认不出的返回码（原因里带返回码，方便以后补规则）。

不使用网盘账号或采集 Cookie，不影响已登录的转存账号。

## 实测（2026-10-15，匿名，用户同意后进行）

用 09-29 采集备份里的 5 条公开链接和 1 条编造的链接：
- curl 探测：shorturlinfo 对 5 条真实链接都返回 -9（需要提取码，附分享者信息）；编造链接返回 140「啊哦，链接出错了」；verify 用正确提取码返回 errno 0 + randsk，错误提取码返回 -9；带 BDCLND 的 share/list 返回 errno 0 和文件列表。
- 用构建出的 `ShareLinkChecker` 实际检测：链接内带提取码 → 可访问；提取码列有值 → 可访问；给错提取码 → 提取码问题（-9）；需要提取码但记录没有 → 提取码问题；编造链接 → 已失效（140）。
- 没有遇到真实的「已过期 / 已取消」分享，这两类的返回码未实测，目前只靠提示文字识别；认不出时归「暂无法判断」，不会误判失效。

## 实现

- 新增 `Features/Collect/ShareLinkChecker.cs`：`CollectLinkStatus`、`ShareLinkCheckResult`、`IShareLinkChecker`、`BaiduShareLink`（链接识别 `TryParse`、打开地址 `BuildOpenUri`）、`ShareLinkChecker`（独立 HttpClient，不自动跳转、不用 Cookie 容器、直连，20 秒超时，响应上限 512 KB）。
- `CollectedRow` 由不可变 record 改为可通知的类（按引用区分记录），新增 `LinkStatus`、`LinkStatusText`、`LinkStatusDetail`。原有构造参数不变。
- `CollectViewModel`：可选参数 `linkChecker`、`linkLauncher`、`linkCheckDelay`；`CheckSelectedLinksCommand`、`StopLinkCheckCommand`、`OpenLink`、`SelectedResultCount`、`IsCheckingLinks`。
- `CollectResultSelectionMenu`：新增三项菜单与右键目标行（`PointAt`、`RowAt`）。
- `CollectView.xaml`：「链接状态」列、「停止检测」按钮。
- `AppBootstrap`：传入 `new ShareLinkChecker()` 和已有的 `IShareLinkLauncher`。
- 未改助手 Python、两份 lxds 核心、数据库、OTA/授权、版本号，未打包。

## 验证

- 新增 56 项测试全部通过：`ShareLinkCheckerTests`（三步流程、提取码来源与冲突、四类结论、验证码与 HTTP/网络失败不判失效、用户取消向上抛、非百度链接不发请求、链接识别、打开地址拼接与白名单）；`CollectLinkCheckTests`（只检测选中行并写回原行、停止保留已完成并恢复进行中、重复检测覆盖、连续受限自动停止、异常归暂无法判断、打开只开指定行、运行日志不含链接和提取码、右键保留/替换选择、未提供服务时菜单隐藏）。
- 采集 / 检测 / Cookie 验证 / 监控反馈相关 280 项：279 通过，1 项为 Updates 命名空间的 OTA 发布脚本测试（本机没有 pwsh，历史同类失败）。
- 解决方案构建 0 警告 0 错误；Debug 入口已按最新源码构建。
- App 全量：3588 项，3489 通过、89 失败、10 跳过（16 分 56 秒）。88 项在 Updates 命名空间（授权/OTA 脚本，本机缺工具链），与上轮相同；另 1 项 `AppBootstrapTests.RejectedLicensePreparesFreshAndOlderDatabasesAndCreatesLocalShellWithoutAuthorizedRecovery`（09-28 历史名单内）。这项这次单独跑也失败（第 167 行 `LocalUiMayOpen` 为假，发生在创建主窗口之前）；在临时 worktree 检出改动前的 `f77e2a82` 跑同一组测试同样失败，确认与本次改动无关。没有新增失败项。
- 本次只改 App 项目，Application / Infrastructure 未重跑。

## 未验证与限制

- 没有真实的过期 / 取消分享样本；遇到后看「链接状态」提示里的返回码补规则。
- 百度对匿名请求的频率限制未知；间隔 1 秒和「连续 3 条受限即停」是保守取值，大批量（上千条）检测耗时较长（每条约 1–3 秒）。
- 界面上的鼠标操作（右键、悬停提示、停止按钮）以用户实测为准。

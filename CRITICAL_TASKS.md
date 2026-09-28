# 立即待办事项清单（2026-09-28）

> **执行结果（2026-09-28 12:27）：六项任务已按顺序完成。** C# 独立开发仓库已重建并修复干净克隆时缺失的 `HasExited` 属性，全方案构建通过，相关 33 项测试通过；Python 在 hong-2、hong-1 均为 225 passed。`miner.py` 提交为 `5aa67dc`，README 路径已修正，Python 稳定标签 `v1.1-release` 指向 `ab8c8cf`。旧 C# 副本已保存在 `.recovery/20260928-environment-rebuild/`。以下命令是历史计划，不要重复删除当前已重建的仓库。完整说明见 `HANDOFF.md` 的“最新执行结果”。

## 🔴 高优先级（必须立即执行）

### 1. 重建 C# 开发环境

**当前状态**：`D:\hong-2\dakazhandian` Git 配置损坏，指向 hong-1 的 worktree

**执行步骤**：
```powershell
# 1. 删除损坏的副本
cd D:\hong-2
Remove-Item -Recurse -Force dakazhandian

# 2. 从 hong-1 重新 clone
git clone D:\hong-1\dakazhandian dakazhandian

# 3. 切换到开发分支
cd dakazhandian
git checkout codex/collect-on-release

# 4. 验证 Git 配置
git remote -v
git worktree list
git log --oneline -5

# 5. 测试编译
dotnet build
```

**验收标准**：
- `git remote -v` 显示指向 `D:\hong-1\dakazhandian`
- `git worktree list` 不报错
- `dotnet build` 编译成功

---

## 🟡 中优先级（阻塞测试通过）

### 2. 修复时间敏感测试

**文件**：`tests/test_zhidao_parse.py:82`

**当前代码**（错误）：
```python
assert within_range("2026-09-18", 7) is True  # 已过期
```

**修改为**：
```python
from datetime import date, timedelta

recent = (date.today() - timedelta(days=3)).isoformat()
old = (date.today() - timedelta(days=365)).isoformat()
assert within_range(recent, 7) is True
assert within_range(old, 7) is False
```

**验收标准**：
```bash
pytest tests/test_zhidao_parse.py::test_within_range_uses_iso_dates -v
# 输出：PASSED
```

---

### 3. 提交 miner.py 年份参数化改动

**执行步骤**：
```bash
cd D:\hong-2
git add lxds/miner.py
git commit -m "refactor(miner): 参数化搜索模板年份以便跨年维护

将硬编码的 2026/2025 替换为 SEARCH_YEAR 和 PREVIOUS_SEARCH_YEAR 常量。
避免每年需要修改十几处字符串字面量。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**验收标准**：
```bash
git status
# 输出：working tree clean
```

---

## 🟢 低优先级（文档清理）

### 4. 修正 README.md 示例路径

**执行步骤**：
```bash
# 全局替换
sed -i 's|D:/hong/output|D:/hong-2/output|g' README.md
```

**验收标准**：`README.md` 中所有示例路径指向 `D:/hong-2`

---

### 5. 运行完整测试套件

**执行步骤**：
```bash
cd D:\hong-2
pytest tests/ -v --tb=short
```

**期望输出**：
```
======================== 225 passed in X.XXs ========================
```

---

## 📦 发版准备（等上述全部完成后）

### 6. 在 hong-1 打稳定版标签

**执行步骤**：
```bash
# 1. 从 hong-2 推送到 hong-1
cd D:\hong-2
git push D:\hong-1 HEAD:main

# 2. 在 hong-1 打标签
cd D:\hong-1
git tag -a v1.1-release -m "第二次发版：修复 UI 上下文、年份参数化、时间敏感测试"
git log --oneline --decorate -5

# 3. 同步 C# 代码（如果有改动）
cd D:\hong-1\dakazhandian
git fetch D:\hong-2\dakazhandian codex/collect-on-release
git merge FETCH_HEAD
```

**验收标准**：
- `git tag -l` 显示 `v1.1-release`
- `git show v1.1-release` 显示标签信息

---

## 执行顺序

**必须按顺序执行**（前一步失败则停止）：

1. ✅ 重建 C# 开发环境（任务 1）
2. ✅ 修复时间敏感测试（任务 2）
3. ✅ 提交 miner.py 改动（任务 3）
4. ✅ 运行完整测试套件（任务 5）
5. ✅ 修正 README.md 路径（任务 4）
6. ✅ 发版打标签（任务 6）

---

## 预计耗时

- 任务 1：5 分钟（取决于 git clone 速度）
- 任务 2：2 分钟
- 任务 3：1 分钟
- 任务 4：1 分钟
- 任务 5：2 分钟（取决于测试执行速度）
- 任务 6：3 分钟

**总计**：约 15 分钟

---

## 检查点

执行完每个任务后，在这里打勾：

- [x] 任务 1：C# 开发环境重建完成
- [x] 任务 2：时间敏感测试修复并通过
- [x] 任务 3：miner.py 改动已提交
- [x] 任务 4：README.md 路径已修正
- [x] 任务 5：完整 Python 测试套件通过（225 passed）
- [x] 任务 6：Python v1.1-release 标签已创建

**全部完成后，可以开始新功能开发。**

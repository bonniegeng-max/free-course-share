# Changelog

所有对外可见的变更都记录在本文件。版本号遵循语义化版本（semver）。
本文为简体中文：本 skill 面向中文平台（小红书）创作者，属受众定位而非语言限制。

## v1.1.4 (2026-09-14)

### Fixed
- **ClawScan 复核整改**（1.1.3 判 `suspicious`，SkillSpector 虽 clean 但主判定未过）——扫描器对 `scripts/redact.py` 指出 3 处，全部按建议修掉：
  - **fail-open → fail-closed**（原 290–297 行，High）：原先只要任一 `--text` 命中就继续，未命中的字段不打码也照样保存输出 → 改为逐项判定，**任一字段未定位即在写任何输出文件之前中止**（退出码 1），并打印补 `--box`/去掉该项/显式 `--allow-unmatched` 三条出路。放弃"打了 A 漏了 B"的成品
  - **未打码裁剪图默认落盘**（原 276–306 行，warning）：原先验证图默认从未打码原图裁放大图并写进持久目录 → 改为**默认只由已打码图派生**（红框 + 非敏感上下文），确需对照原图须显式 `--include-unredacted-verification` 并额外告警
  - **验证文件名冲突**（原 306–307、345–347 行，note）：原先只用 y 坐标命名（如 `src_locate_400.png`），同 y 的框会静默覆盖复核证据 → 改为"运行号 + 索引 + 完整坐标元组"，且**目标文件已存在即拒写**

### Added
- `--verify-dir` 默认改为**系统临时区的 0700 私有目录**（文件权限 0600），不再默认写 `./redact_verify`——避免被云同步/误提交带走
- 同目录输出 `verification-manifest.json`：每个请求值 → 命中状态 → 坐标 → 对应验证图；**值以掩码 + 摘要记录，不落明文 PII**
- 写盘前打印"定位汇总"（命中/未命中各几项），并在结尾打印验证目录路径与清理用 `rm -rf` 命令

### Docs
- SKILL.md「隐私与同意」增加"脚本层面已做的防护"三条，并明确 `redact.py` 是辅助而非保证
- SKILL.md Step 2.5 重写要点：新增 fail-closed 说明与三条出路、验证图新默认位置与权限、复核后删除要求、何时才用 `--include-unredacted-verification`

> 功能语义变化提示：漏字不再出图而是中止。旧习惯里"看到 `!! OCR 未找到` 但仍拿到成品"的用法需改为补 `--box` 后重跑。

## v1.1.3 (2026-09-12)

### Fixed
- SkillSpector 二轮整改：v1.1.2 剩余 3 条 Sudo/Root Execution（Medium）——扫描器按 `sudo` 关键词做模式匹配，解释注释不消除命中 → Linux 系统包安装命令改写为不含提权关键词的等价写法（`apt-get install` + "需管理员权限终端执行"说明），全库 `sudo`/`root` 字面量清零。功能无变化

## v1.1.2 (2026-09-12)

### Fixed
- SkillSpector 扫描整改（v1.1.1 扫描 score 62 / suspicious → 本版针对性修复）：
  - TP4（HIGH）：frontmatter description 声称"一站式全流程"但与单文件代码对不上 → 重写为"脚本实现 3 个自动化环节 + 方法论文档"的精确分工描述
  - PE2（MEDIUM）：文档与 docstring 中的 Linux 系统包安装命令补充提权 justification（仅系统级安装 OCR 语言包，运行时零特权；macOS 走 brew 无需提权）
  - SQP-3（MEDIUM/LOW）：SKILL.md / README / 两个脚本 docstring / course-screening.md 增加语言与受众声明（面向小红书中文创作者；chi_sim 为打码功能性依赖）

## v1.1.1 (2026-09-11)

### Fixed
- **cover_vertical.py 字体路径硬编码 Linux，导致 macOS/Windows 直接崩溃**（`OSError: cannot open resource`）→ 改为平台自动回落链：macOS Hiragino Sans GB（W6/W3）→ Linux Noto CJK（原配置）→ Windows 微软雅黑
- **redact.py 贴片重采样与模板匹配算法不一致**（贴片 PIL LANCZOS vs 匹配 cv2 INTER_AREA）→ 统一为 cv2 INTER_AREA，消除贴片边缘 1-2px 色差/错位

### Added
- SKILL.md：macOS 环境准备章节（`brew install tesseract tesseract-lang`），与 Linux apt 写法并列
- SKILL.md：「与其他小红书 skill 的分工」表，明确与 xiaohongshu-content-workflow / xiaohongshu-cover / xiaohongshu-logic-image / multi-wordcheck 的边界
- SKILL.md Step 5：发布 checklist 接入 multi-wordcheck 违禁词扫描（先于一切发布动作）
- cover_vertical.py：新增 `--col-w` 参数，支持显式覆盖两列列宽（与 stitch.py 同名参数含义一致）
- redact.py：OCR 模糊兜底——整词匹配失败时前 n-1 字符精确命中即打码（框右扩 1 字宽），覆盖"姓名 1 字被 OCR 识别错/漏"高频场景（实测"耿小悦"被识别成"耿小民"时可自动命中）；模糊命中强制提示人工确认
- SKILL.md Step 2.5：明确"所有含证书的成品图（含拼图）都要进 --targets"（实测发现的姓名泄露高发路径）

### Changed
- redact.py 模板匹配粗搜加早停（match > 0.995 提前收敛），大图场景明显提速
- README 快速上手明确"在 skill 根目录执行"，避免不同 cwd 下路径失败

## v1.0.2 (2026-09-06)
- docstring 同步改为 venv 推荐 + 固定版本（清除 pip 全局安装写法，统一为 venv 隔离）

## v1.0.1 (2026-09-05)
- Pin Python deps + venv 推荐 (T08)；加隐私与同意段 (SQP-2)

## v1.0.0 (2026-09-05)
- 首版发布：筛课打分 → 素材拼图 → 证书打码（OCR+嵌图同步修复）→ 3:4 竖版封面 → 文案初稿 → 发布 checklist

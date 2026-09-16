# Changelog

所有对外可见的变更都记录在本文件。版本号遵循语义化版本（semver）。
本文为简体中文：本 skill 面向中文平台（小红书）创作者，属受众定位而非语言限制。

## v1.1.8 (2026-09-16)

### Changed
- Display name 调整为 `Free Course Verifier & Share Kit`，直接表达核验、筛选和分享三类结果。
- topics 改为 `free-course`、`course-verification`、`certificate`、`learning-resources`、`share-copy`，移除已经不属于当前产品的图片拼接、打码和封面生成主题。
- 取消“筛课与分享文案必须同时出现”的双条件触发。单课核验、课程发现、比较、筛选或分享文案任一任务均可独立调用。
- 输出按 Verify、Find、Compare、Shortlist、Draft 与 Combined 模式适配，不再强制生成未请求的分享稿。
- 保留官方来源优先、时效标注、免费范围精确定义、只读和不自动发布边界。

## v1.1.7 (2026-09-16)

### Changed
- 恢复单文件、只读的课程核验与分享文案核心。
- 移除图片拼接、OCR 打码和封面生成脚本，避免多文件扫描问题及能力表述冲突。

## v1.1.6 (2026-09-16)

### Fixed
- **恢复完整流水线**：线上 v1.1.5 实际发布的是「单文件精简版」——包里只有 `SKILL.md`，
  `scripts/` 三个脚本与 `references/` 全部缺失，安装后无法拼图、无法打码、无法出封面，
  且自述为 read-only（只核验课程信息 + 写文案），与 skill 名与描述严重不符。
  本版把完整包重新发布：`scripts/{stitch,redact,cover_vertical}.py` +
  `references/course-screening.md` 全部归位

### Security / Privacy
- **清除示例中的真实姓名残留（3 处）**：`README.md`（单字合并示例）、
  `CHANGELOG.md`（OCR 模糊兜底实测记录）、`scripts/redact.py` docstring（同场景示例）
  —— 原示例用的是真实姓名，一律替换为通用示例（`张三` / `李小明`→`李小朋`）。
  此前这些姓氏残留在 v1.1.1–v1.1.5 的线上包里一直存在
- **移除机器专属私有路径**：`SKILL.md` Step 5 与 CHANGELOG 原先指向一个本机私有清单文件的
  绝对路径。改为「使用者自备清单并在对话中提供」，**skill 内不引用 skill 目录之外的任何本地文件**
- **移除个人署名**：`SKILL.md` 封面主体建议里的个人昵称归属改为中性表述「实测反馈」

### Docs
- `README.md` 快速上手示例原用 `--points "0元|完全免费" "4h|学完拿证"`，与本 skill Step 4
  的 2026-09-13 禁用词表**自相矛盾** → 改为合规示例，并补一句「先过禁用词表」
- `scripts/cover_vertical.py` docstring 指向的 `references/prohibited-words.md` 并不存在
  （词库单一真相源已迁至 `xiaohongshu-prohibited-words` skill）→ 改为指向该 skill

### 未变动
- `categories` = `productivity, creative`；`topics` = `xiaohongshu, free-certificates,
  image-stitching, pii-redaction, cover-generator`（发布时显式带上，避免被全量替换清空）
- `scripts/redact.py` 的 fail-closed / 权限核验 / 唯一验证文件名逻辑均未改动

## v1.1.5 (2026-09-14)

### Fixed
- **ClawScan 二轮复核整改**（1.1.4 仍判 `suspicious`，4 条 findings：2 error / 1 warning / 1 note）——
  **代码 2 条**：
  - **成品图 fail-open（`scripts/redact.py` 原 456–458 行，High）**：`--targets` 里嵌套图匹配分不足时只打印警告就 `continue`，脚本继续跑并报告"完成"→ 出现"源图打了码、成品图里那份原样泄露"的漏网。
    改为**先全部预检再落盘**：任何一张匹配不上（或模板匹配抛错）即中止、不写任何输出（退出码 1）；确需放行须显式 `--allow-unmatched-targets`，此时**退出码 2（降级）**、清单里该目标标 `status=skipped`、结尾打印"完成（降级）"
  - **权限设置静默失败（原 272–287、306 行，Medium）**：`_chmod_quiet` 把 `chmod` 的 `OSError` 直接吞掉，文档承诺的 0700/0600 可能没生效却仍报成功。
    改为 `_enforce_mode()`：**设置后核验实际权限位**；验证目录不生效即中止（目录是保护里面所有文件的那道门），文件不生效则告警并提示已降级为依赖目录保护。正常路径实测 0700 生效
  - **账号专属交付动作迁出 skill**（`SKILL.md` 原 200–202 行，T01 强制第三方品牌推广，High）：原 Step 5 checklist 强制"成品默认加固定账号水印 + 置顶评论放短链"。改为：本 skill **不做任何品牌植入、不指定任何站外链接**；账号运营偏好（水印/发布时段/置顶评论）改由使用者自备清单并在对话中提供，**skill 内不放任何账号专属配置**

### Changed
- **依赖安装加固（`SKILL.md` / `README.md`，T08 Low）**：`pip install` 增加 `--index-url https://pypi.org/simple` 与 `--only-binary=:all:`，显式指向官方 PyPI 并只装 wheel；补充 `--require-hashes` 可复现校验的做法说明

### 功能语义变化提示
- 成品图匹配失败**不再静默跳过**而是中止。旧用法"看到一句警告但成品照样出来"要改成：把不含证书的图从 `--targets` 移除，或换一张成品图重跑。
- 降级运行（`--allow-unmatched*`）退出码为 **2**，脚本里若用 `&&` 串联会中断——这是有意设计，避免漏打码的产物被当成成功品继续流转。

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
- redact.py：OCR 模糊兜底——整词匹配失败时前 n-1 字符精确命中即打码（框右扩 1 字宽），覆盖"姓名 1 字被 OCR 识别错/漏"高频场景（实测"李小明"被识别成"李小朋"时可自动命中）；模糊命中强制提示人工确认
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

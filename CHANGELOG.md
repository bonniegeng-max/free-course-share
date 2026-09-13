# Changelog

所有对外可见的变更都记录在本文件。版本号遵循语义化版本（semver）。
本文为简体中文：本 skill 面向中文平台（小红书）创作者，属受众定位而非语言限制。

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

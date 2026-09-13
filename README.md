# free-course-share

小红书「免费课程 / 0元拿证」赛道笔记生产工作流，面向 AI Agent 的 skill（兼容 AgentSkills / openclaw 规范）。

> **Language note**: This skill targets Chinese-platform (Xiaohongshu) creators, so docs and CLI output are in Simplified Chinese by design — audience scoping, not a language restriction. The `chi_sim` OCR pack in `redact.py` is a functional dependency for detecting Chinese names on certificates. English docs available on request (open an issue).

一条流水线跑完：**筛课打分 → 素材拼图 → 证书敏感信息打码 → 3:4 竖版封面 → 文案初稿 → 发布 checklist**。

## 包含内容

| 文件 | 作用 |
|------|------|
| `SKILL.md` | 完整工作流（6 步）+ 踩坑原则 |
| `scripts/stitch.py` | 多图**两列拼图**（手机可读，自动适配深/浅底色） |
| `scripts/redact.py` | 证书姓名等敏感信息**打码一条龙**（见下） |
| `scripts/cover_vertical.py` | 3:4 竖版封面（1080×1440，深/浅双主题，徽章/卖点/警示条参数化） |
| `references/course-screening.md` | 课程筛选 8 项验证清单 + 品牌分级 + /8 打分表 |

## 亮点：redact.py，打码不再返工

针对"证书姓名打码打不准、反复返工"的经典痛点：

- **chi_sim 中文 OCR** 词级定位（英文 OCR 识别中文只会输出乱码坐标，是打偏的最常见根因）
- 自动合并被 OCR 拆开的单字（"耿"+"悦" → 一个框），框自动外扩防露边
- **封面/配图里嵌的证书缩略图同步修复**：模板匹配粗定位 + MSE 网格精搜（scale 与 offset 都精调）自动求出嵌入变换，局部贴片修复，不重做整图
- 每一步自动输出**放大验证裁剪图**，人工确认后再发布
- `--clean-box` 从干净源图取贴片，一键清除历史打错的内容

```bash
python3 scripts/redact.py --src 证书原图.png --text "张三" \
    --targets 封面.png 配图-证书实拍页.png \
    --out /workspace/证书-打码.png --target-out /workspace/ \
    --verify-dir /tmp/redact_verify
```

## 安装

**推荐 venv 隔离安装**：

```bash
git clone https://github.com/bonniegeng-max/free-course-share.git
cd free-course-share

python3 -m venv .venv && source .venv/bin/activate
pip install \
    pillow==12.1.0 \
    numpy==2.3.5 \
    opencv-python-headless==4.13.0.92 \
    pytesseract==0.3.13

# OCR 中文包（系统级）：数据装在系统目录，Linux 需在管理员权限的终端执行一次
# （唯一的管理员动作，仅装 OCR 系统包，skill 运行时零特权；macOS 用 brew 无需管理员权限）
apt-get install -y tesseract-ocr tesseract-ocr-chi-sim
```

## 快速上手

> 以下命令均在 **skill 根目录**（本 README 所在目录）执行；在其他目录调用时，把 `scripts/` 替换为 skill 的实际安装路径（如 `~/.workbuddy/skills/free-course-share/scripts/`）。

```bash
# 1) 两列拼图（3张→左2右1；5张→左3右2）
python3 scripts/stitch.py two-col 图1.png 图2.png 图3.png -o 拼图.png

# 2) 证书打码（OCR 定位 + 嵌入图同步修复 + 验证图）
python3 scripts/redact.py --src 证书.png --text "姓名" --out 证书-打码.png

# 3) 3:4 竖版封面
python3 scripts/cover_vertical.py --out 封面.png --theme dark \
    --title "标题" --sub "副标题" --body 拼图.png \
    --points "0元|完全免费" "4h|学完拿证"
```

工作流的完整方法论（筛课清单、标题公式、正文结构、发布 checklist、踩坑原则）见 [SKILL.md](SKILL.md)。

## 适用人群

- 运营"免费课程 / 证书"赛道小红书账号的创作者
- 需要 agent 自动化笔记素材生产（拼图/封面/打码）的 openclaw / Claude skills 用户

## 隐私与免责声明

`redact.py` 是**辅助工具**，不保证完全隐私保护。OCR 对艺术字/低清字可能识别失败，缩略图经缩放后边缘可能漏字。请在发布前**逐张**用脚本输出的验证裁剪图人眼确认打码到位；不确定时优先使用裁剪版或脱敏示例替代真证书。公司/机构证书常有保密条款，发布前请确认自己有发布权限。本项目作者不对隐私泄露后果承担责任。

## License

[MIT](LICENSE)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书 3:4 竖版封面/轮播图生成器 (1080x1440) — free-course-share skill
基于已验证模板（微软×LinkedIn 证书笔记大纲页）参数化，dark/light 双主题。

用法:
  python3 cover_vertical.py \
    --out /workspace/封面.png \
    --theme dark \
    --top-badge "微软出品|blue" \
    --badges "中文界面" "26分钟" \
    --title "微软AI课 26分钟拿证书" \
    --sub "生成式AI · 智能化在线搜索" \
    --body 图1.png 图2.png 图3.png \
    --points "12题|两章测验" "26分钟|中文课" "1张|完成证书" \
    --warn "改版提醒：官方公告该路径 10月1日 更新改版" "此前完成可按当前要求发证，建议尽早学完" \
    --cta "收藏备用 · 完整领取攻略看主页"

说明:
  - ⚠️ 示例文案已按 2026-09-13 新规：禁用「0元/免费/白嫖/LinkedIn/拿证」，见 SKILL.md Step 4 与 references/prohibited-words.md
  - --body 传 1 张图 = 全宽铺开（等比）；传多张 = 自动两列排布（左 ceil(n/2) 张）
  - --points 可重复传多个 "大字|小字"
  - --top-badge 与 --badges 徽章色: blue|yellow|orange|red|gray
  - 纵向布局动态计算：body 高时自动压缩列宽，保证不溢出 1440
"""
import argparse
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440

THEMES = {
    'dark': {
        'bg': (23, 27, 34), 'card': (30, 36, 47), 'line': (52, 60, 76),
        'txt': (255, 255, 255), 'gray': (168, 176, 192),
        'yellow': (255, 201, 60), 'blue': (79, 140, 255),
        'orange': (255, 159, 69), 'warnbg': (51, 38, 20),
        'warn_txt': (226, 205, 176), 'warn_icon': (35, 28, 18),
    },
    'light': {
        'bg': (255, 255, 255), 'card': (242, 244, 248), 'line': (217, 222, 232),
        'txt': (26, 34, 51), 'gray': (107, 118, 136),
        'yellow': (228, 148, 10), 'blue': (47, 107, 255),
        'orange': (219, 84, 12), 'warnbg': (255, 244, 229),
        'warn_txt': (166, 92, 33), 'warn_icon': (255, 255, 255),
    },
}
BADGE_FILL = {'blue': 'blue', 'yellow': 'yellow', 'orange': 'orange',
              'red': (231, 76, 60), 'gray': None}

# 中文字体回落链：按平台自动探测（macOS → Linux → Windows），首个全部存在的字体组生效
# (bold_path, bold_index, regular_path, regular_index)
FONT_SETS = [
    # macOS 冬青黑体简体：W6(粗)=index 2，W3(常规)=index 0
    ('/System/Library/Fonts/Hiragino Sans GB.ttc', 2,
     '/System/Library/Fonts/Hiragino Sans GB.ttc', 0),
    # Linux (Debian/Ubuntu fonts-noto-cjk)，沿用原验证过的 index=2
    ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 2,
     '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 2),
    # Linux 其他发行版常见路径
    ('/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc', 2,
     '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc', 2),
    # Windows 微软雅黑
    ('C:/Windows/Fonts/msyhbd.ttc', 0,
     'C:/Windows/Fonts/msyh.ttc', 0),
]


def _pick_fonts():
    for bp, bi, rp, ri in FONT_SETS:
        if os.path.exists(bp) and os.path.exists(rp):
            return bp, bi, rp, ri
    raise SystemExit(
        '未找到可用中文字体：macOS 需 Hiragino Sans GB（系统自带）；'
        'Linux 请安装 fonts-noto-cjk；Windows 需微软雅黑（系统自带）'
    )


_BPATH, _BIDX, _RPATH, _RIDX = _pick_fonts()


def f_bold(s): return ImageFont.truetype(_BPATH, s, index=_BIDX)
def f_reg(s): return ImageFont.truetype(_RPATH, s, index=_RIDX)


def tw(d, t, fnt):
    b = d.textbbox((0, 0), t, font=fnt)
    return b[2] - b[0]


def center(d, y, t, fnt, fill, cx=W // 2):
    b = d.textbbox((0, 0), t, font=fnt)
    d.text((cx - (b[2] - b[0]) / 2 - b[0], y), t, font=fnt, fill=fill)


def pill(d, cx, cy, t, fnt, padx, fill_txt, bgc, ol=None):
    b = d.textbbox((0, 0), t, font=fnt)
    tw_, th_ = b[2] - b[0], b[3] - b[1]
    pw, ph = tw_ + padx * 2, th_ + 16
    x0, y0 = cx - pw / 2, cy - ph / 2
    if bgc:
        d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=bgc)
    if ol:
        d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, outline=ol, width=2)
    d.text((x0 + padx - b[0], cy - th_ / 2 - b[1] - 2), t, font=fnt, fill=fill_txt)
    return pw


def parse_badge(s, c):
    """'文字|色' -> (text, color_key)"""
    parts = s.split('|')
    return parts[0], (parts[1] if len(parts) > 1 else c)


def load_body(args):
    imgs = [Image.open(p).convert('RGB') for p in args.body]
    if len(imgs) == 1:
        return imgs, 'single'
    return imgs, 'multi'


def compute_body_layout(imgs, mode, col_w, pad_x, gap):
    """返回贴图所需 (scaled列表[列][图], 总高)"""
    avail_w = W - pad_x * 2
    if mode == 'single':
        im = imgs[0]
        w = avail_w
        h = round(im.height * w / im.width)
        return [[im.resize((w, h), Image.LANCZOS)]], h
    n = len(imgs)
    n_left = (n + 1) // 2
    if col_w is None:
        col_w = (avail_w - gap) // 2
    cols = [imgs[:n_left], imgs[n_left:]]
    scaled = []
    for col in cols:
        sc = []
        for im in col:
            h = round(im.height * col_w / im.width)
            sc.append(im.resize((col_w, h), Image.LANCZOS))
        scaled.append(sc)
    bh = max(sum(im.height for im in c) + gap * (len(c) - 1) for c in scaled if c)
    return scaled, bh


def main():
    ap = argparse.ArgumentParser(description='3:4 竖版封面生成器 (1080x1440)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--theme', default='dark', choices=['dark', 'light'])
    ap.add_argument('--top-badge', help='首个胶囊: "文字|颜色"(blue/yellow/orange/red/gray)')
    ap.add_argument('--badges', nargs='*', default=[], help='其余胶囊, 可多个')
    ap.add_argument('--title', default='')
    ap.add_argument('--sub', default='')
    ap.add_argument('--body', nargs='*', default=[], help='主体图(1张全宽/多张两列)')
    ap.add_argument('--points', nargs='+', default=[], help='要点卡 "大字|小字", 一次可给多个')
    ap.add_argument('--warn', nargs='*', default=[], help='警示条文字(最多两行)')
    ap.add_argument('--cta', default='', help='底部引导语')
    ap.add_argument('--pad-x', type=int, default=28)
    ap.add_argument('--gap', type=int, default=14)
    ap.add_argument('--col-w', type=int, default=None,
                    help='两列模式列宽（默认按高度预算动态压缩；与 stitch.py 同名参数含义一致）')
    args = ap.parse_args()

    T = THEMES[args.theme]
    img = Image.new('RGB', (W, H), T['bg'])
    d = ImageDraw.Draw(img)
    pad_x, gap = args.pad_x, args.gap

    # ---------- 徽章行(自适应居中) ----------
    y = 56
    badge_items = []
    if args.top_badge:
        badge_items.append(parse_badge(args.top_badge, 'blue'))
    for b in args.badges:
        badge_items.append(parse_badge(b, 'gray'))
    if badge_items:
        f_badge = f_bold(26)
        widths = [tw(d, t, f_badge) + 44 for t, _ in badge_items]
        total = sum(widths) + 14 * (len(widths) - 1)
        cx = (W - total) / 2
        for (t, ckey), w_ in zip(badge_items, widths):
            key = BADGE_FILL.get(ckey)
            fill = T.get(key) if isinstance(key, str) else key
            if ckey == 'gray':
                text_c = T['gray'] if args.theme == 'dark' else T['txt']
                pill(d, cx + w_ / 2, y + 26, t, f_badge, 22, text_c, T['card'], ol=T['line'])
            else:
                pill(d, cx + w_ / 2, y + 26, t, f_badge, 22, (255, 255, 255), fill)
            cx += w_ + 14
        y += 84

    # ---------- 标题 / 副标题 ----------
    if args.title:
        center(d, y, args.title, f_bold(62), T['txt'])
        y += 108
    if args.sub:
        center(d, y, args.sub, f_reg(30), T['gray'])
        y += 62

    # ---------- 估算非body高度, 压缩body列宽防溢出 ----------
    avail_w = W - pad_x * 2
    non_body = y + 60  # 底部margin余量
    if args.points:
        non_body += 128 + 30
    if args.warn:
        non_body += 108 + 30
    if args.cta:
        non_body += 46
    body_budget = H - non_body

    body_imgs, mode = load_body(args)
    if body_imgs:
        if mode == 'single':
            col_w = None
        else:
            col_w = args.col_w if args.col_w else (avail_w - gap) // 2
        scaled, bh = compute_body_layout(body_imgs, mode, col_w, pad_x, gap)
        if bh > body_budget and mode == 'multi':
            ratio = body_budget / bh
            scaled, bh = compute_body_layout(body_imgs, mode, max(200, int(col_w * ratio)), pad_x, gap)
        elif bh > body_budget and mode == 'single':
            w = max(200, int(avail_w * body_budget / bh))
            scaled, bh = compute_body_layout(body_imgs, mode, w, pad_x, gap)
        # 贴图
        if mode == 'single':
            img.paste(scaled[0][0], (pad_x, y))
        else:
            x = pad_x
            for col in scaled:
                yy = y
                for im in col:
                    img.paste(im, (x, yy))
                    yy += im.height + gap
                x += col[0].width + gap
        y += bh + 34

    # ---------- 要点卡 ----------
    if args.points:
        pts = [(p.split('|')[0], p.split('|')[1] if '|' in p else '') for p in args.points]
        n = len(pts)
        card_w = (avail_w - gap * (n - 1)) // n
        f_big, f_small = f_bold(46), f_reg(24)
        for i, (big, small) in enumerate(pts):
            x0 = pad_x + i * (card_w + gap)
            d.rounded_rectangle([x0, y, x0 + card_w, y + 128], radius=18, fill=T['card'], outline=T['line'])
            cx_ = x0 + card_w // 2
            center(d, y + 14, big, f_big, T['yellow'], cx=cx_)
            if small:
                center(d, y + 84, small, f_small, T['gray'], cx=cx_)
        y += 128 + 30

    # ---------- 警示条 ----------
    if args.warn:
        warn_lines = args.warn[:2]
        d.rounded_rectangle([pad_x, y, W - pad_x, y + 108], radius=18, fill=T['warnbg'], outline=T['orange'])
        ccy = y + 54
        d.ellipse([pad_x + 32, ccy - 20, pad_x + 72, ccy + 20], fill=T['orange'])
        fb = d.textbbox((0, 0), '!', font=f_bold(34))
        center(d, ccy - (fb[3] - fb[1]) / 2 - fb[1] - 2, '!', f_bold(34), T['warn_icon'], cx=pad_x + 52)
        tx = pad_x + 96
        d.text((tx, y + 18), warn_lines[0], font=f_bold(28), fill=T['orange'])
        if len(warn_lines) > 1 and warn_lines[1]:
            d.text((tx, y + 60), warn_lines[1], font=f_reg(26), fill=T['warn_txt'])
        y += 108 + 30

    # ---------- CTA ----------
    if args.cta:
        center(d, y, args.cta, f_reg(27), T['gray'])

    img.save(args.out, optimize=True)
    print(f'OK {args.out}: {img.size} theme={args.theme} title="{args.title}"')


if __name__ == '__main__':
    main()

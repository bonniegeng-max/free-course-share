#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
截图拼图通用脚本
注：CLI 帮助与输出为简体中文——本 skill 面向中文平台（小红书）创作者，
属受众定位而非语言限制。
用法:
  python3 stitch.py two-col <图1> [图2...] -o out.png [--col-w 880] [--gap 14] [--margin 30] [--bg auto|white|dark]
  python3 stitch.py one-row <图1> [图2...] -o out.png [--gap 14] [--margin 30] [--bg auto|white|dark]
规则:
  - two-col: 左列 ceil(n/2) 张按序, 其余放右列, 顶部对齐, 统一列宽
  - one-row: 统一到最小高度, 横向并列
  - bg auto: 取第一张图左上角像素亮度判断深浅
"""
import argparse
import sys
from PIL import Image

BG_DARK = (23, 27, 34)
BG_LIGHT = (255, 255, 255)


def detect_bg(first_img):
    px = first_img.convert('RGB').getpixel((5, 5))
    return BG_DARK if sum(px) / 3 < 128 else BG_LIGHT


def two_col(paths, out, col_w, gap_v, gap_h, margin, bg):
    imgs = [Image.open(p).convert('RGB') for p in paths]
    n = len(imgs)
    n_left = (n + 1) // 2
    cols = [imgs[:n_left], imgs[n_left:]]
    scaled = []
    for col in cols:
        sc = []
        for im in col:
            h = round(im.height * col_w / im.width)
            sc.append(im.resize((col_w, h), Image.LANCZOS))
        scaled.append(sc)
    h_total = max((sum(im.height for im in c) + gap_v * (len(c) - 1)) for c in scaled if c)
    W = col_w * 2 + gap_h + margin * 2
    H = h_total + margin * 2
    canvas = Image.new('RGB', (W, H), bg)
    x = margin
    for col in scaled:
        y = margin
        for im in col:
            canvas.paste(im, (x, y))
            y += im.height + gap_v
        x += col_w + gap_h
    canvas.save(out, optimize=True)
    print(f'OK {out}: {canvas.size[0]}x{canvas.size[1]} (左{n_left} 右{n - n_left}, 背景{"深" if bg == BG_DARK else "浅"})')


def one_row(paths, out, gap, margin, bg):
    imgs = [Image.open(p).convert('RGB') for p in paths]
    h = min(im.height for im in imgs)
    resized = []
    for im in imgs:
        w = round(im.width * h / im.height)
        resized.append(im.resize((w, h), Image.LANCZOS))
    total_w = sum(im.width for im in resized) + gap * (len(resized) - 1) + margin * 2
    total_h = h + margin * 2
    canvas = Image.new('RGB', (total_w, total_h), bg)
    x = margin
    for im in resized:
        canvas.paste(im, (x, margin))
        x += im.width + gap
    canvas.save(out, optimize=True)
    print(f'OK {out}: {canvas.size[0]}x{canvas.size[1]} (单行横排, 背景{"深" if bg == BG_DARK else "浅"})')


def main():
    ap = argparse.ArgumentParser(description='截图拼图')
    ap.add_argument('mode', choices=['two-col', 'one-row'])
    ap.add_argument('images', nargs='+', help='图片路径, 顺序即排列顺序')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--col-w', type=int, default=880)
    ap.add_argument('--gap', type=int, default=14)
    ap.add_argument('--margin', type=int, default=30)
    ap.add_argument('--bg', default='auto', choices=['auto', 'white', 'dark'])
    args = ap.parse_args()

    if len(args.images) == 1:
        print('只有一张图, 无需拼接, 直接拷贝即可')
        sys.exit(1)

    probe = Image.open(args.images[0]).convert('RGB')
    if args.bg == 'auto':
        bg = detect_bg(probe)
    elif args.bg == 'white':
        bg = BG_LIGHT
    else:
        bg = BG_DARK

    if args.mode == 'two-col':
        two_col(args.images, args.out, args.col_w, args.gap, args.gap, args.margin, bg)
    else:
        one_row(args.images, args.out, args.gap, args.margin, bg)


if __name__ == '__main__':
    main()

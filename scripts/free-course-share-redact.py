#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""敏感信息打码一条龙：中文OCR定位 → 自适应马赛克 → 嵌套图同步修复 → 验证图输出

固化自多次打码返工案例的教训：
1. 中文定位必须用 chi_sim（eng 对中文输出乱码坐标，是多次打偏的根因）
2. 定位框先输出"验证裁剪图"人工确认，再应用到成品
3. 成品图（封面/配图里的缩略图）用"局部贴片"修复，不重做整图
4. 嵌套映射 = 多尺度模板匹配(粗) + MSE窗口搜索(精)，禁止手工估算坐标

依赖：
  # 推荐 venv 隔离：
  python3 -m venv .venv && source .venv/bin/activate
  pip install opencv-python-headless==4.13.0.92 pytesseract==0.3.13
  # OCR 中文包（系统级）：
  sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim

用法：
  # 一条龙：源图定位打码 + 封面/配图里嵌的缩略图同步修复
  python3 redact.py --src 证书原图.png --text "张三" \
      --targets 封面.png 配图.png \
      --out /workspace/证书-打码.png --target-out /workspace/

  # 手动坐标兜底（OCR 识别不出时）
  python3 redact.py --src 图.png --box 913,464,1002,514 --out out.png

  # 清除成品图里历史错误打码（src坐标系框，从干净src取贴片还原）
  python3 redact.py ... --clean-box 810,320,960,445

跑完后必须：Read 查看 --verify-dir 里的验证裁剪图，确认后才算完成。
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    sys.exit("缺少 opencv-python-headless==4.13.0.92: 建议 venv 隔离后 pip install opencv-python-headless==4.13.0.92")
try:
    import pytesseract
except ImportError:
    sys.exit("缺少 pytesseract==0.3.13: 建议 venv 隔离后 pip install pytesseract==0.3.13 "
             "(并 apt-get install tesseract-ocr tesseract-ocr-chi-sim)")


# ---------------- OCR 定位 ----------------

def ocr_words(img_pil):
    """chi_sim 词级识别，返回词框列表"""
    data = pytesseract.image_to_data(img_pil, lang='chi_sim',
                                     output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(data['text'])):
        t = (data['text'][i] or '').strip()
        try:
            conf = float(data['conf'][i])
        except (TypeError, ValueError):
            conf = -1
        if t and conf > 20:
            words.append(dict(t=t, x=data['left'][i], y=data['top'][i],
                              w=data['width'][i], h=data['height'][i]))
    return words


def group_lines(words):
    """按 y 中心聚类成行"""
    if not words:
        return []
    med_h = float(np.median([w['h'] for w in words]))
    words = sorted(words, key=lambda w: w['y'] + w['h'] / 2)
    lines, cur, cy0 = [], [], None
    for w in words:
        cy = w['y'] + w['h'] / 2
        if cy0 is None or abs(cy - cy0) <= med_h * 0.7:
            cur.append(w)
            cy0 = cy if cy0 is None else cy0 * 0.6 + cy * 0.4
        else:
            lines.append(cur)
            cur, cy0 = [w], cy
    if cur:
        lines.append(cur)
    return lines


def merge_boxes(boxes):
    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes)
    y2 = max(b[3] for b in boxes)
    return (int(x1), int(y1), int(np.ceil(x2)), int(np.ceil(y2)))


def find_text_boxes(img_pil, target):
    """在整图中查找目标文本，返回命中框列表（支持词被拆分、词间有空格）"""
    lines = group_lines(ocr_words(img_pil))
    hits = []
    for line in lines:
        line = sorted(line, key=lambda w: w['x'])
        chars = []  # (字符, 框 or None)
        for j, w in enumerate(line):
            cw = w['w'] / max(1, len(w['t']))
            for k, ch in enumerate(w['t']):
                x1 = w['x'] + k * cw
                chars.append((ch, (x1, w['y'], x1 + cw, w['y'] + w['h'])))
            if j < len(line) - 1 and line[j + 1]['x'] - (w['x'] + w['w']) > 2:
                chars.append((' ', None))
        s = ''.join(c for c, _ in chars)
        idx = s.find(target)
        if idx >= 0:
            boxes = [b for _, b in chars[idx:idx + len(target)] if b is not None]
            if boxes:
                hits.append(merge_boxes(boxes))
            continue
        # 去空格再匹配一次
        ns = [(c, b) for c, b in chars if c != ' ']
        s2 = ''.join(c for c, _ in ns)
        idx = s2.find(target)
        if idx >= 0:
            boxes = [b for _, b in ns[idx:idx + len(target)] if b is not None]
            if boxes:
                hits.append(merge_boxes(boxes))
    return hits


# ---------------- 打码 ----------------

def pixelate(img, box, block=None):
    """区域马赛克。block 自适应：约 字高/3，保证不可辨认"""
    x1, y1, x2, y2 = box
    if block is None:
        block = max(10, (y2 - y1) // 3)
    region = img.crop(box)
    w, h = region.size
    small = region.resize((max(1, w // block), max(1, h // block)), Image.BILINEAR)
    img.paste(small.resize((w, h), Image.NEAREST), box)
    return img


def expand(box, pad, size):
    W, H = size
    x1, y1, x2, y2 = box
    return (max(0, int(x1 - pad)), max(0, int(y1 - pad)),
            min(W, int(np.ceil(x2 + pad))), min(H, int(np.ceil(y2 + pad))))


# ---------------- 嵌套映射（粗匹配 + 精搜） ----------------

def match_transform(src_gray, tgt_gray, roi, s_lo=0.25, s_hi=0.9):
    """求 target = src * scale + offset 的变换。
    roi: src 坐标系内的模板区 (x1,y1,x2,y2)，选敏感词所在行+上下文。
    返回 (scale, ox, oy, score)
    """
    x1, y1, x2, y2 = roi
    tmpl_full = src_gray[y1:y2, x1:x2]
    best = None
    for s in np.arange(s_lo, s_hi, 0.005):
        tw, th = int(tmpl_full.shape[1] * s), int(tmpl_full.shape[0] * s)
        if tw < 24 or th < 16 or tw >= tgt_gray.shape[1] or th >= tgt_gray.shape[0]:
            continue
        t = cv2.resize(tmpl_full, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(tgt_gray, t, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if best is None or maxv > best[0]:
            best = (maxv, float(s), maxloc[0] - int(x1 * s), maxloc[1] - int(y1 * s))
    if best is None:
        raise RuntimeError("模板匹配失败：尺度范围内找不到嵌入图")
    score, s, ox, oy = best
    # MSE 网格精搜：scale ±0.01 × offset ±8px（scale 必须一起精调，
    # 否则缩略图边缘会出现 5-10px 贴片错位）
    g1 = src_gray.astype(np.float32)
    best_mse, best = None, (s, ox, oy)
    H_t, W_t = tgt_gray.shape
    for ds in np.arange(-0.010, 0.0105, 0.0025):
        s2 = round(s + float(ds), 4)
        sw, sh = int(g1.shape[1] * s2), int(g1.shape[0] * s2)
        if sw < 10 or sh < 10:
            continue
        src_r = cv2.resize(g1, (sw, sh), interpolation=cv2.INTER_AREA)
        rx1, ry1, rx2, ry2 = int(x1 * s2), int(y1 * s2), int(x2 * s2), int(y2 * s2)
        ref = src_r[ry1:ry2, rx1:rx2]
        if ref.size == 0:
            continue
        for dy in range(-8, 9, 2):
            for dx in range(-8, 9, 2):
                nx, ny = ox + dx, oy + dy
                px1, py1 = rx1 + nx, ry1 + ny
                if px1 < 0 or py1 < 0 or py1 + ref.shape[0] > H_t \
                   or px1 + ref.shape[1] > W_t:
                    continue
                patch = tgt_gray[py1:py1 + ref.shape[0], px1:px1 + ref.shape[1]].astype(np.float32)
                mse = float(((patch - ref) ** 2).mean())
                if best_mse is None or mse < best_mse:
                    best_mse, best = mse, (s2, nx, ny)
    # 最优 scale 下 offset 再细扫 1px
    s, ox, oy = best
    sw, sh = int(g1.shape[1] * s), int(g1.shape[0] * s)
    src_r = cv2.resize(g1, (sw, sh), interpolation=cv2.INTER_AREA)
    rx1, ry1, rx2, ry2 = int(x1 * s), int(y1 * s), int(x2 * s), int(y2 * s)
    ref = src_r[ry1:ry2, rx1:rx2]
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = ox + dx, oy + dy
            px1, py1 = rx1 + nx, ry1 + ny
            if px1 < 0 or py1 < 0 or py1 + ref.shape[0] > H_t \
               or px1 + ref.shape[1] > W_t:
                continue
            patch = tgt_gray[py1:py1 + ref.shape[0], px1:px1 + ref.shape[1]].astype(np.float32)
            mse = float(((patch - ref) ** 2).mean())
            if best_mse is None or mse < best_mse:
                best_mse, best = mse, (s, nx, ny)
    s, ox, oy = best
    return s, ox, oy, score


# ---------------- 验证图 ----------------

def save_verify(img_pil, box, path, ctx=90, zoom=3):
    """裁剪敏感框上下文并画框放大，供人工确认"""
    from PIL import ImageDraw
    W, H = img_pil.size
    x1, y1, x2, y2 = expand(box, ctx, (W, H))
    crop = img_pil.crop((x1, y1, x2, y2))
    crop = crop.resize((crop.width * zoom, crop.height * zoom), Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    bx1, by1 = (box[0] - x1) * zoom, (box[1] - y1) * zoom
    bx2, by2 = (box[2] - x1) * zoom, (box[3] - y1) * zoom
    d.rectangle([bx1, by1, bx2, by2], outline=(255, 0, 0), width=max(2, zoom))
    crop.save(path)


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser(description="敏感信息打码一条龙")
    ap.add_argument('--src', required=True, help='含敏感信息的原始截图')
    ap.add_argument('--text', action='append', default=[], help='要打码的文字，可多次')
    ap.add_argument('--box', action='append', default=[],
                    help='手动框 x1,y1,x2,y2（src坐标系，OCR兜底），可多次')
    ap.add_argument('--pad', type=int, default=8, help='框外扩像素（默认8）')
    ap.add_argument('--block', type=int, default=None, help='马赛克块大小（默认自适应）')
    ap.add_argument('--targets', nargs='*', default=[], help='嵌套该图的成品图，同步修复')
    ap.add_argument('--out', default=None, help='打码后源图输出路径')
    ap.add_argument('--inplace', action='store_true', help='targets 原地覆盖（默认输出到 --target-out）')
    ap.add_argument('--target-out', default=None, help='targets 修复后输出目录')
    ap.add_argument('--verify-dir', default='./redact_verify', help='验证图输出目录')
    ap.add_argument('--clean-box', action='append', default=[],
                    help='src坐标系框：从干净src取贴片，清除targets中该区域的历史错误内容，可多次')
    args = ap.parse_args()

    os.makedirs(args.verify_dir, exist_ok=True)
    src = Image.open(args.src).convert('RGB')
    W, H = src.size
    src_gray = cv2.cvtColor(np.array(src), cv2.COLOR_RGB2GRAY)

    # 1) 定位
    boxes = [tuple(int(v) for v in b.split(',')) for b in args.box]
    for text in args.text:
        hits = find_text_boxes(src, text)
        if not hits:
            print(f"!! OCR 未找到 '{text}'，请人工给 --box 兜底")
        for hb in hits:
            print(f"✓ OCR 定位 '{text}': {hb}")
            boxes.append(hb)
    if not boxes:
        sys.exit("没有任何打码框，退出")

    # 2) 源图打码
    src_mos = src.copy()
    for b in boxes:
        eb = expand(b, args.pad, (W, H))
        pixelate(src_mos, eb, args.block)
        save_verify(src, b, os.path.join(args.verify_dir, f'src_locate_{b[1]}.png'))
        save_verify(src_mos, b, os.path.join(args.verify_dir, f'src_done_{b[1]}.png'))
    if args.out:
        src_mos.save(args.out)
        print(f"✓ 打码源图 → {args.out}")

    # 3) 嵌套成品图同步修复
    for tpath in args.targets:
        tgt = Image.open(tpath).convert('RGB')
        tg = cv2.cvtColor(np.array(tgt), cv2.COLOR_RGB2GRAY)
        tw, th = tgt.size
        # 模板区：所有框的联合包围盒 + 上下文
        ux1 = min(b[0] for b in boxes); uy1 = min(b[1] for b in boxes)
        ux2 = max(b[2] for b in boxes); uy2 = max(b[3] for b in boxes)
        ctx = max(60, (uy2 - uy1) * 3)
        roi = expand((ux1, uy1, ux2, uy2), ctx, (W, H))
        s, ox, oy, score = match_transform(src_gray, tg, roi)
        print(f"→ {os.path.basename(tpath)}: scale={s:.4f} offset=({ox},{oy}) match={score:.3f}")
        if score < 0.85:
            print(f"!! 匹配分过低，跳过 {tpath}（嵌套图可能不存在或变形），请人工处理")
            continue
        # 贴片源：干净版（清历史错误）与打码版
        src_r = src.resize((int(W * s), int(H * s)), Image.LANCZOS)
        mos_r = src_mos.resize((int(W * s), int(H * s)), Image.LANCZOS)
        # 3a) 清历史错误内容（如旧打错马赛克）
        for cb in args.clean_box:
            c1 = expand(tuple(int(v) for v in cb.split(',')), 4, (W, H))
            px1, py1 = int(c1[0] * s) + ox, int(c1[1] * s) + oy
            px2, py2 = int(c1[2] * s) + ox, int(c1[3] * s) + oy
            patch = src_r.crop((int(c1[0] * s), int(c1[1] * s), int(c1[2] * s), int(c1[3] * s)))
            tgt.paste(patch, (px1, py1))
            print(f"  ✓ 已清除历史区域 {cb}")
        # 3b) 贴打码贴片
        for b in boxes:
            eb = expand(b, args.pad, (W, H))
            bx1, by1 = int(eb[0] * s) + ox, int(eb[1] * s) + oy
            bx2, by2 = int(eb[2] * s) + ox, int(eb[3] * s) + oy
            patch = mos_r.crop((int(eb[0] * s), int(eb[1] * s), int(eb[2] * s), int(eb[3] * s)))
            tgt.paste(patch, (bx1, by1))
            save_verify(tgt, (bx1, by1, bx2, by2),
                        os.path.join(args.verify_dir,
                                     f'target_{os.path.splitext(os.path.basename(tpath))[0]}_{by1}.png'))
        if args.inplace:
            tgt.save(tpath)
            print(f"  ✓ 已就地更新 {tpath}")
        elif args.target_out:
            os.makedirs(args.target_out, exist_ok=True)
            op = os.path.join(args.target_out, os.path.basename(tpath))
            tgt.save(op)
            print(f"  ✓ 修复版 → {op}")

    print("\n== 完成。必做：Read 查看", os.path.abspath(args.verify_dir), "里的验证图，确认打码位置后才能交付 ==")


if __name__ == '__main__':
    main()

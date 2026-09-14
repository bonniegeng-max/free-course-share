#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""敏感信息打码一条龙：中文OCR定位 → 自适应马赛克 → 嵌套图同步修复 → 验证图输出

固化自多次打码返工案例的教训：
1. 中文定位必须用 chi_sim——chi_sim 是打码功能的功能性依赖（识别证书上的中文
   姓名），非界面语言约束；eng 对中文输出乱码坐标，是多次打偏的根因
2. 定位框先输出"验证裁剪图"人工确认，再应用到成品
3. 成品图（封面/配图里的缩略图）用"局部贴片"修复，不重做整图
4. 嵌套映射 = 多尺度模板匹配(粗) + MSE窗口搜索(精)，禁止手工估算坐标

安全设计（v1.1.4 起）——下面三条是硬约束，改代码时请勿回退：
A. fail-closed：每个 --text 独立判定命中结果。只要有一项没定位到，就在
   **写任何输出文件之前**中止（退出码非 0），不会产出"漏打一处"的成品。
   确需放行必须显式加 --allow-unmatched，届时打印醒目警告。
B. 验证图默认只由已打码图派生：不把"未打码原图"的放大裁剪写进磁盘。
   确需与原图对照时加 --include-unredacted-verification（会额外告警）。
C. 验证图落私有目录：默认建在系统临时区的 0700 私有目录，文件权限 0600；
   --verify-dir 可指定位置（同样强制 0700）。文件名含"运行号 + 索引 + 完整
   坐标元组"，已存在即拒写、绝不静默覆盖——"人工复核"这道防线不能被自己
   覆盖掉。同目录另出 verification-manifest.json（值做掩码，不落明文 PII）。

依赖（本 skill 文档与 CLI 输出为简体中文：面向中文平台小红书创作者，受众定位）：
  # 推荐 venv 隔离：
  python3 -m venv .venv && source .venv/bin/activate
  pip install opencv-python-headless==4.13.0.92 pytesseract==0.3.13
  # OCR 中文包（系统级）：仅 Linux 需在管理员权限的终端执行一次装系统包，
  # 本脚本运行时不需要任何特权（macOS 用 brew 无需管理员权限）
  apt-get install -y tesseract-ocr tesseract-ocr-chi-sim

用法：
  # 一条龙：源图定位打码 + 封面/配图里嵌的缩略图同步修复
  python3 redact.py --src 证书原图.png --text "张三" \
      --targets 封面.png 配图.png \
      --out /workspace/证书-打码.png --target-out /workspace/

  # 手动坐标兜底（OCR 识别不出时；也是 fail-closed 中止后的推荐补法）
  python3 redact.py --src 图.png --text "张三" --box 913,464,1002,514 --out out.png

  # 清除成品图里历史错误打码（src坐标系框，从干净src取贴片还原）
  python3 redact.py ... --clean-box 810,320,960,445

  # 需要"未打码对照图"时（默认不生成）
  python3 redact.py ... --include-unredacted-verification

  # 明知有漏仍要出图（不推荐）
  python3 redact.py ... --allow-unmatched

跑完后必须：Read 查看结尾打印的验证目录里的图，确认打码位置后才算完成。
验证目录含个人信息，复核完成后请整目录删除。
"""
import argparse
import hashlib
import os
import sys
import tempfile
import time

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
    """在整图中查找目标文本，返回命中框列表（支持词被拆分、词间有空格）

    模糊兜底：整词匹配失败时，若前 len-1 字符精确命中，框向右补一个字宽。
    覆盖高频场景：姓名 1 个字被 OCR 识别错/漏（如"耿小悦"→"耿小民"）。
    模糊命中必须人工确认验证图后再交付。
    """
    lines = group_lines(ocr_words(img_pil))
    hits, fuzzy_hits = [], []
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
            continue
        # 模糊兜底：前 len-1 字符精确命中，框右扩 1 字宽
        if len(target) >= 2:
            idx = s2.find(target[:-1])
            if idx >= 0:
                boxes = [b for _, b in ns[idx:idx + len(target) - 1] if b is not None]
                if boxes:
                    mb = merge_boxes(boxes)
                    avg_w = (mb[2] - mb[0]) / (len(target) - 1)
                    fuzzy_hits.append((mb[0], mb[1], int(mb[2] + avg_w), mb[3]))
    if fuzzy_hits:
        print(f"?? 模糊命中 {len(fuzzy_hits)} 处（允许 1 字 OCR 误差，框右扩 1 字宽）"
              f"——务必人工确认验证图后再交付")
    return hits + fuzzy_hits


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

def resize_rgb(img_pil, s):
    """按 scale 缩放 PIL 图，用与模板匹配一致的 cv2.INTER_AREA，
    避免贴片与匹配阶段重采样算法不同导致的边缘色差/错位"""
    arr = np.array(img_pil)
    h, w = arr.shape[:2]
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    return Image.fromarray(cv2.resize(arr, (nw, nh), interpolation=cv2.INTER_AREA))

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
            if maxv > 0.995:  # 早停：匹配分接近满分，无需继续扫尺度（大图提速）
                break
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


# ---------------- 验证图（私有目录 + 唯一文件名 + 拒绝覆盖） ----------------

def _chmod_quiet(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def make_verify_dir(explicit):
    """建验证目录。一律 0700。返回 (绝对路径, 是否临时目录)"""
    if explicit:
        os.makedirs(explicit, exist_ok=True)
        d = os.path.abspath(explicit)
        _chmod_quiet(d, 0o700)
        return d, False
    d = tempfile.mkdtemp(prefix='redact-verify-')
    _chmod_quiet(d, 0o700)
    return d, True


def save_verify(img_pil, box, path, ctx=90, zoom=3):
    """裁剪敏感框上下文并画框放大，供人工确认。文件权限 0600，已存在则拒写"""
    from PIL import ImageDraw
    if os.path.exists(path):
        sys.exit(f"验证图路径已存在，拒绝覆盖（避免复核证据被静默吃掉）：{path}\n"
                 f"  换个 --verify-dir，或先清掉旧目录后重跑。")
    W, H = img_pil.size
    x1, y1, x2, y2 = expand(box, ctx, (W, H))
    crop = img_pil.crop((x1, y1, x2, y2))
    crop = crop.resize((crop.width * zoom, crop.height * zoom), Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    bx1, by1 = (box[0] - x1) * zoom, (box[1] - y1) * zoom
    bx2, by2 = (box[2] - x1) * zoom, (box[3] - y1) * zoom
    d.rectangle([bx1, by1, bx2, by2], outline=(255, 0, 0), width=max(2, zoom))
    crop.save(path)
    _chmod_quiet(path, 0o600)
    return path


def _mask(text):
    """掩码显示，用于 manifesto——不把明文 PII 再写一份到磁盘"""
    t = text.strip()
    if len(t) <= 1:
        return '*' * max(1, len(t))
    return t[0] + '*' * (len(t) - 1)


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]


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
    ap.add_argument('--verify-dir', default=None,
                    help='验证图输出目录（默认：系统临时区下的 0700 私有目录）')
    ap.add_argument('--clean-box', action='append', default=[],
                    help='src坐标系框：从干净src取贴片，清除targets中该区域的历史错误内容，可多次')
    ap.add_argument('--allow-unmatched', action='store_true',
                    help='危险：允许部分 --text 未定位到时仍然输出。默认 fail-closed 中止，'
                         '不产出漏打码的成品')
    ap.add_argument('--include-unredacted-verification', action='store_true',
                    help='危险：额外输出"未打码原图"的放大裁剪图。默认只输出已打码图')
    args = ap.parse_args()

    src = Image.open(args.src).convert('RGB')
    W, H = src.size
    src_gray = cv2.cvtColor(np.array(src), cv2.COLOR_RGB2GRAY)

    # ---- 1) 定位：先把所有结果判完，写任何文件之前决定是否中止 ----
    boxes = [tuple(int(v) for v in b.split(',')) for b in args.box]
    matched, unmatched = [], []
    for text in args.text:
        hits = find_text_boxes(src, text)
        if not hits:
            unmatched.append(text)
            print(f"✗ OCR 未找到 '{text}'")
            continue
        for hb in hits:
            print(f"✓ OCR 定位 '{text}': {hb}")
            boxes.append(hb)
        matched.append((text, len(hits)))

    print("\n—— 定位汇总（写盘前）——")
    print(f"  待打码文本 {len(args.text)} 项：命中 {len(matched)} 项，未命中 {len(unmatched)} 项")
    print(f"  手动 --box {len(args.box)} 个")
    if unmatched:
        print("  未命中：" + "、".join(f"'{t}'" for t in unmatched))

    if not boxes:
        sys.exit("没有任何打码框，退出（未写入任何输出文件）")
    if unmatched and not args.allow_unmatched:
        sys.exit(
            "\n打码中止：以下文本未能定位。为避免产出漏打码的成品，未写入任何输出。\n"
            "  " + "、".join(f"'{t}'" for t in unmatched) + "\n\n"
            "  处理方式（任选其一）：\n"
            "    1) 为每项补 --box x1,y1,x2,y2 后重跑（推荐，坐标以原图为准）\n"
            "    2) 确认这些字确实不在图上、无需打码 → 把它们从 --text 里去掉\n"
            "    3) 明知有漏仍要出图 → 加 --allow-unmatched"
            "（输出会包含未打码的敏感信息，风险自负）\n")
    if unmatched:
        print("\n" + "!" * 66)
        print("!! --allow-unmatched 已开启：本次输出可能含未打码的敏感信息")
        print("!! 未命中：" + "、".join(unmatched))
        print("!" * 66 + "\n")

    # ---- 2) 建验证目录（到这里才允许落盘）----
    verify_dir, is_temp = make_verify_dir(args.verify_dir)
    run_id = time.strftime('%m%d-%H%M%S')
    manifest = dict(
        generatedAt=time.strftime('%Y-%m-%dT%H:%M:%S'),
        runId=run_id,
        source=os.path.abspath(args.src),
        sourceSize=[W, H],
        allowUnmatched=bool(args.allow_unmatched),
        unredactedVerification=bool(args.include_unredacted_verification),
        verifyDir=verify_dir,
        verifyDirIsTemporary=is_temp,
        verifyDirMode='0700',
        requestedTexts=[dict(label=_mask(t), digest=_digest(t), matched=True, hits=n)
                        for t, n in matched]
                       + [dict(label=_mask(t), digest=_digest(t), matched=False, hits=0)
                          for t in unmatched],
        manualBoxes=[list(b) for b in (tuple(int(v) for v in s.split(',')) for s in args.box)],
        boxes=[],
        verificationFiles=[],
        note='验证图含未打码/已打码的个人信息，人工复核完成后请整目录删除。'
             'requestedTexts 中的值以掩码+摘要形式记录，不落明文。',
    )

    def vpath(kind, idx, box, extra=''):
        """唯一文件名：运行号 + 类型 + 索引 + 完整坐标元组"""
        x1, y1, x2, y2 = box
        return os.path.join(verify_dir,
                            f"{run_id}_{kind}_{idx:03d}_{x1}-{y1}-{x2}-{y2}{extra}.png")

    # ---- 3) 源图打码 ----
    src_mos = src.copy()
    for i, b in enumerate(boxes):
        eb = expand(b, args.pad, (W, H))
        pixelate(src_mos, eb, args.block)
        entry = dict(index=i, box=list(b), expandedBox=list(eb), source=['--box']
                     if b in [tuple(int(v) for v in s.split(',')) for s in args.box] else ['--text'])
        if args.include_unredacted_verification:
            p = vpath('src-UNREDACTED', i, b)
            entry['unredactedVerification'] = save_verify(src, b, p)
            manifest['verificationFiles'].append(p)
        p = vpath('src-redacted', i, b)
        entry['redactedVerification'] = save_verify(src_mos, b, p)
        manifest['verificationFiles'].append(p)
        manifest['boxes'].append(entry)

    if args.include_unredacted_verification:
        print("\n" + "!" * 66)
        print("!! 已输出未打码对照图（src-UNREDACTED_*）——目录里含明文个人信息")
        print("!! 复核完成后请立即整目录删除")
        print("!" * 66)

    if args.out:
        src_mos.save(args.out)
        print(f"✓ 打码源图 → {args.out}")

    # ---- 4) 嵌套成品图同步修复 ----
    for ti, tpath in enumerate(args.targets):
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
        # 贴片源：干净版（清历史错误）与打码版（重采样算法与匹配阶段一致）
        src_r = resize_rgb(src, s)
        mos_r = resize_rgb(src_mos, s)
        # 4a) 清历史错误内容（如旧打错马赛克）
        for cb in args.clean_box:
            c1 = expand(tuple(int(v) for v in cb.split(',')), 4, (W, H))
            px1, py1 = int(c1[0] * s) + ox, int(c1[1] * s) + oy
            px2, py2 = int(c1[2] * s) + ox, int(c1[3] * s) + oy
            patch = src_r.crop((int(c1[0] * s), int(c1[1] * s), int(c1[2] * s), int(c1[3] * s)))
            tgt.paste(patch, (px1, py1))
            print(f"  ✓ 已清除历史区域 {cb}")
        # 4b) 贴打码贴片
        for bi, b in enumerate(boxes):
            eb = expand(b, args.pad, (W, H))
            bx1, by1 = int(eb[0] * s) + ox, int(eb[1] * s) + oy
            bx2, by2 = int(eb[2] * s) + ox, int(eb[3] * s) + oy
            patch = mos_r.crop((int(eb[0] * s), int(eb[1] * s), int(eb[2] * s), int(eb[3] * s)))
            tgt.paste(patch, (bx1, by1))
            p = vpath('target', ti * 1000 + bi, b, extra=f"_{os.path.splitext(os.path.basename(tpath))[0]}")
            save_verify(tgt, (bx1, by1, bx2, by2), p)
            manifest['verificationFiles'].append(p)
        if args.inplace:
            tgt.save(tpath)
            print(f"  ✓ 已就地更新 {tpath}")
        elif args.target_out:
            os.makedirs(args.target_out, exist_ok=True)
            op = os.path.join(args.target_out, os.path.basename(tpath))
            tgt.save(op)
            print(f"  ✓ 修复版 → {op}")

    # ---- 5) 验证清单 ----
    mp = os.path.join(verify_dir, f'{run_id}_verification-manifest.json')
    with open(mp, 'w', encoding='utf-8') as f:
        import json as _json
        _json.dump(manifest, f, ensure_ascii=False, indent=2)
    _chmod_quiet(mp, 0o600)

    print("\n== 完成 ==")
    print(f"验证目录：{verify_dir}" + ("（系统临时目录，重启后可能被清理）" if is_temp else ""))
    print("必做：Read 逐张查看验证图，确认打码位置后才能交付。")
    print("验证目录含个人信息，复核完成后请整目录删除：")
    print(f"  rm -rf '{verify_dir}'")


if __name__ == '__main__':
    main()

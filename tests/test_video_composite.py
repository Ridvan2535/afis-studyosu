# -*- coding: utf-8 -*-
"""İnsanlı sahne video hattı (yapay zekâ videosu + kodla baskı + kodla el kamerası) — sentetik videoyla.

Sentetik "yapay zekâ videosu": sabit sahne + yavaş kamera kayması + arka planda yürüyen insanlar + gren;
bir bölümde afişin önünden el geçer. Beklenen: kayma giderilir, baskı afişe sabit kalır, el geçen pikselde baskı
bastırılır, kalite özeti geçer. Kötü durum: kamera çok oynarsa kalite kontrol REDDEDER."""
import math
import os
import sys
import tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import banner_detect as bd  # noqa: E402
import compositor as cp  # noqa: E402
import cvio  # noqa: E402
import video_composite as vc  # noqa: E402
import video_repair as vr  # noqa: E402

base = cvio.imread(os.path.join(HERE, "scene.jpg"))
base = cv2.resize(base, (720, 1080), interpolation=cv2.INTER_AREA)
design = cp.load_design(os.path.join(HERE, "design_candy.jpg"))
det = bd.detect(base)
assert det.ok, det.reject
ys, xs = np.where(det.mask > 0)
bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
H, W = base.shape[:2]
FPS, N = 24, 72


def make_video(path, drift=1.0, hand=True, seed=5):
    rng = np.random.default_rng(seed)
    sink = vr.make_sink(path, FPS, crf=14)
    try:
        for i in range(N):
            t = i / FPS
            fr = base.copy()
            # arka plandaki insanlar (afişin sağ ve sol dışında), yavaş yürür
            for k, (x0, y0, sp) in enumerate([(0.03 * W, 0.50 * H, 0.25), (0.90 * W, 0.46 * H, -0.2)]):
                x = int(x0 + sp * i)
                x = int(np.clip(x, 12, W - 12))
                if bx0 - 14 < x < bx1 + 14:
                    continue
                cv2.ellipse(fr, (x, int(y0)), (13, 34), 0, 0, 360, (60 + 30 * k, 50, 90), -1, cv2.LINE_AA)
                cv2.circle(fr, (x, int(y0) - 44), 10, (120, 150, 200), -1, cv2.LINE_AA)
            if hand and 30 <= i < 40:                               # afişin önünden el geçer
                cx = int(bx0 + (bx1 - bx0) * (0.2 + 0.06 * (i - 30)))
                cy = int(by0 + (by1 - by0) * 0.45)
                cv2.ellipse(fr, (cx, cy), (26, 40), 20, 0, 360, (110, 140, 200), -1, cv2.LINE_AA)
            # kamera kayması
            tx = drift * (5 * math.sin(2 * math.pi * 0.17 * t) + 2 * math.sin(2 * math.pi * 0.43 * t + 1))
            ty = drift * (4 * math.sin(2 * math.pi * 0.11 * t + 1) + 1.5 * math.sin(2 * math.pi * 0.37 * t))
            sc = 1 + drift * 0.004 * math.sin(2 * math.pi * 0.13 * t)
            rot = drift * 0.15 * math.sin(2 * math.pi * 0.2 * t)
            M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, sc)
            M[:, 2] += [tx, ty]
            fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
            fr = np.clip(fr.astype(np.float32) * (1 + 0.012 * math.sin(2 * math.pi * 0.5 * t)) + rng.normal(0, 1.2, fr.shape), 0, 255).astype(np.uint8)
            sink.write(fr)
        sink.close()
    except BaseException:
        sink.abort()
        raise


with tempfile.TemporaryDirectory() as d:
    src = os.path.join(d, "ai.mp4")
    make_video(src)

    # --- kamera kayması tahmini ---
    grays, s, Ms, st, (vh, vw) = vc.analyse(src)
    assert (vh, vw) == (H, W)
    assert st["inliers"].min() >= 14, st["inliers"].min()
    # --- stabilize + baskı ---
    out = os.path.join(d, "out.mp4")
    summary, infos = vc.compose_video(src, out, design, move="yakinlas", handheld="sabit")
    print("özet:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in summary.items()})
    assert summary["ok"], summary["reasons"]
    assert summary["occl_max"] > 0.005, "geçen el algılanmadı"
    # yay çizerek yaklaşma (orbit) da aynı akıştan geçer; yaklaşma güçlü olduğu için strength otomatik kısılır
    out_o = os.path.join(d, "out_orbit.mp4")
    s_o, _ = vc.compose_video(src, out_o, design, move="yakinlas_saga", handheld="sakin")
    assert s_o["ok"], s_o["reasons"]
    assert os.path.getsize(out_o) > 10_000
    assert os.path.getsize(out) > 20000
    info = vr.video_info(out)
    assert info["frames"] in (N - 1, N, N + 1), info

    # baskı afişe sabit: baskısız kareleri doğrudan üret ve kenar görüntüsünün kaymasını ölç
    gen = vc.frame_stream(src, design, motion=vc.analyse(src))
    frames = [f for f, _ in gen]
    ex = vc.frame_stream.last
    ref = frames[0]
    # arka plan kare kare sabit mi? (yoğun optik akışın medyanı, stabilize öncesi ve sonrası)
    raw_frames = list(vr.iter_video(src))
    gr = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    fH, fW = ref.shape[:2]

    def med_flow(a, b, box):
        fl = cv2.calcOpticalFlowFarneback(gr(a), gr(b), None, 0.5, 4, 25, 5, 7, 1.5, 0)
        y0_, y1_, x0_, x1_ = box
        st_ = fl[int(y0_ * fH):int(y1_ * fH), int(x0_ * fW):int(x1_ * fW)]
        return np.median(st_[..., 0]), np.median(st_[..., 1])

    boxes = [(0.02, 0.22, 0.05, 0.95), (0.75, 0.97, 0.05, 0.20)]
    r0 = cv2.resize(raw_frames[0], (fW, fH), interpolation=cv2.INTER_CUBIC)
    after = max(abs(v) for i in range(3, N, 6) for bx in boxes for v in med_flow(ref, frames[i], bx))
    before = max(abs(v) for i in range(3, N, 6) for bx in boxes
                 for v in med_flow(r0, cv2.resize(raw_frames[i], (fW, fH), interpolation=cv2.INTER_CUBIC), bx))
    print("arka plan kayması (px, çalışma boyutu): stabilize öncesi maks %.2f, sonrası maks %.2f" % (before, after))
    assert before > 4.0, "sentetik kayma beklenenden küçük"
    assert after < 0.6, "stabilizasyon yetersiz"
    x0, y0 = int(bx0 + 0.15 * (bx1 - bx0)), int(by0 + 0.25 * (by1 - by0))
    sz = int(0.55 * (bx1 - bx0))
    # tasarım baskısı belirgin olan bölgede kayma
    def hp(img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return cv2.GaussianBlur(g, (0, 0), 1.2) - cv2.GaussianBlur(g, (0, 0), 7)
    sc = ex["f_up"]
    rx0, ry0, rx1, ry1 = [int(v * sc) for v in (bx0, by0, bx1, by1)]
    sub = lambda im: hp(im)[ry0 + 40:ry1 - 40, rx0 + 30:rx1 - 30]
    h0 = sub(ref)
    win = cv2.createHanningWindow((h0.shape[1], h0.shape[0]), cv2.CV_32F)
    shifts = []
    for i in range(0, N, 4):
        if 28 <= i <= 42:
            continue                                            # el geçen kareler
        (dx, dy), r = cv2.phaseCorrelate(h0, sub(frames[i]), win)
        shifts.append((dx, dy))
    shifts = np.abs(np.array(shifts))
    print("baskı kayması (px, çalışma boyutunda): ort %.2f maks %.2f" % (shifts.mean(), shifts.max()))
    assert shifts.max() < 1.6, "baskı afiş üzerinde sabit kalmıyor"

    # el geçen karede el pikselleri baskısız (kare girdisiyle aynı), baskı el çevresinde duruyor
    i = 34
    raw_f = next(x for j, x in enumerate(vr.iter_video(src)) if j == i)
    tm = np.diag([1, 1, 1.0])
    assert infos[i]["occl"] > 0.01
    assert max(r["occl"] for k, r in enumerate(infos) if k < 25 or k > 45) < 0.02, "el yokken yanlış alarm"

    # --- kötü durum: kamera çok oynamış ---
    bad = os.path.join(d, "bad.mp4")
    make_video(bad, drift=9.0)
    try:
        s2, _ = vc.compose_video(bad, os.path.join(d, "bad_out.mp4"), design, handheld="sabit")
        assert not s2["ok"], "çok oynayan kamera kabul edildi"
        print("kötü video reddedildi:", s2["reasons"])
    except vc.CompositeError as e:
        print("kötü video reddedildi (hata):", e)
print("test_video_composite: TAMAM")

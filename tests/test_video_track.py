# -*- coding: utf-8 -*-
"""Hareketli kameralı video + izlenen baskı. Sentetik 'AI videosu': boş sahneye kamera yaklaşma+yay hareketi (camera_move) uygulanır.
Gerçek referans: aynı kamerayı TASARIMLI fotoğrafa uygulamak. İzlenen baskı bununla karşılaştırılır."""
import os
import sys
import tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import banner_detect as bd  # noqa: E402
import camera_move as cm  # noqa: E402
import compositor as cp  # noqa: E402
import cvio  # noqa: E402
import video_repair as vr  # noqa: E402
import video_track as vt  # noqa: E402

base = cvio.imread(os.path.join(HERE, "scene.jpg"))
base = cv2.resize(base, (720, 1280), interpolation=cv2.INTER_AREA)
design = cp.load_design(os.path.join(HERE, "design_candy.jpg"))
det = bd.detect(base)
assert det.ok, det.reject
withd, _ = cp.composite(base, design, det)

with tempfile.TemporaryDirectory() as d:
    a, b, o = os.path.join(d, "blank.mp4"), os.path.join(d, "truth.mp4"), os.path.join(d, "out.mp4")
    for src, p in ((base, a), (withd, b)):
        cm.render(src, p, move="yakinlas_saga", seconds=4.0, fps=24, long_side=1280, handheld="sakin", strength=0.8, seed=7)
    summ = vt.compose_tracked(a, o, design)
    print({k: v for k, v in summ.items()})
    assert summ["ok"], summ["reasons"]
    fo, ft = list(vr.iter_video(o)), list(vr.iter_video(b))
    n = min(len(fo), len(ft))
    errs = []
    for i in range(0, n, 8):
        x, y = fo[i], ft[i]
        if x.shape != y.shape:
            y = cv2.resize(y, (x.shape[1], x.shape[0]))
        g1, g2 = [cv2.GaussianBlur(cv2.cvtColor(t, cv2.COLOR_BGR2GRAY), (0, 0), 1.5).astype(np.float32) for t in (x, y)]
        errs.append(float(np.mean(np.abs(g1 - g2))))
    print("kare başına ortalama gri fark:", [round(e, 1) for e in errs])
    assert max(errs) < 14, errs
    strip = np.hstack([cv2.resize(fo[i], (240, 427)) for i in (0, n // 4, n // 2, 3 * n // 4, n - 1)])
    cv2.imwrite(os.environ.get("STRIP", os.path.join(d, "strip.jpg")), strip)
print("test_video_track: TAMAM")

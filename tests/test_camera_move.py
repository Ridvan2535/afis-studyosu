# -*- coding: utf-8 -*-
"""Sanal kamera: yürüme ritmi, kadraj payı, şiddet sıralaması, bulanıklık, boyut ve yeniden üretilebilirlik."""
import os
import sys
import tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import camera_move as cm  # noqa: E402
import cvio  # noqa: E402

img = cvio.imread(os.path.join(HERE, "scene.jpg"))
H, W = img.shape[:2]


def rig(level, move="yakinlas", seed=11, **kw):
    return cm.CameraRig(W, H, W, H, 6, 30, move, intensity=cm.level_value(level), seed=seed, **kw)


# 1) yürüme ritmi: dikey sallantının baskın frekansı adım sıklığı (1.7-2.0 Hz) ya da yanal için yarısı
r = rig("yuruyus")
tr = r.trajectory()
p = tr["pitch"] - tr["pitch"].mean()
sp = np.abs(np.fft.rfft(p * np.hanning(len(p))))
fr = np.fft.rfftfreq(len(p), 1 / 30)
peak = fr[1:][np.argmax(sp[1:])]
assert 1.2 <= peak <= 1.85, f"pitch baskın frekans adım sıklığı değil: {peak}"
y = tr["yaw"] - tr["yaw"].mean()
sy = np.abs(np.fft.rfft(y * np.hanning(len(y))))
peak_y = fr[1:][np.argmax(sy[1:])]
assert peak_y < 1.2, f"yaw (yanal sallanma) yavaş olmalı: {peak_y}"

# 2) şiddet sıralaması
def spread(level):
    t = rig(level).trajectory()
    return float(np.std(t["pitch"]) + np.std(t["yaw"]) + np.std(t["roll"]))
s0, s1, s2, s3 = (spread(k) for k in ("sabit", "sakin", "yuruyus", "belirgin"))
assert s0 < 1e-9 < s1 < s2 < s3, (s0, s1, s2, s3)
assert 0.07 < np.std(rig("yuruyus").trajectory()["pitch"]) < 0.5          # doğal aralık (derece): hafif el sallantısı

# 3) kadraj payı: hiçbir karede (alt-örnekler dahil) kenar boşluğu görünmez
for level in ("yuruyus", "belirgin"):
    for mv in cm.MOVES:
        rr = rig(level, mv)
        assert rr._inside(margin=0.0), f"kenar boşluğu: {level}/{mv}"
        assert rr.z_extra <= 1.16, (level, mv, rr.z_extra)

# 4) yeniden üretilebilirlik ve tohum
a = rig("yuruyus").render_frame(img, 40)
b = rig("yuruyus").render_frame(img, 40)
c = rig("yuruyus", seed=12).render_frame(img, 40)
assert a.shape == img.shape and a.dtype == np.uint8
# gren rastgele ama tohumdan türetilir: aynı tohum aynı sonucu verir
assert np.array_equal(a, b)
assert not np.array_equal(a, c)

# 5) hareket bulanıklığı: hızlı karede keskinlik düşer, sakin karede yüksek kalır
rr = rig("belirgin", "saga")          # sabit yakınlaşmalı hareket: keskinlik farkı yalnızca sallantıdan gelsin
tr = rr.trajectory()
v = np.abs(np.gradient(tr["pitch"])) + np.abs(np.gradient(tr["yaw"]))
fast, slow = int(np.argmax(v)), int(np.argmin(v[5:-5])) + 5
def sharp(fi):
    g = cv2.cvtColor(rr.render_frame(img, fi, finish=False), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())
assert sharp(fast) < sharp(slow), "hareket bulanıklığı uygulanmıyor"

# 5b) yay (orbit): hedef çıktı merkezinde kalır, yaklaşılan (sağ) kenar daha az kaynak yüksekliği kaplar
for mv, sign in (("yakinlas_saga", 1), ("yakinlas_sola", -1)):
    rs = rig("sabit", mv)
    tr_ = rs.trajectory()
    assert abs(tr_["orbit"][-1]) > 20 and np.sign(tr_["orbit"][-1]) == sign, (mv, tr_["orbit"][-1])
    M = rs.hmap(rs.seconds)
    ctr = M @ np.array([rs.ow / 2, rs.oh / 2, 1.0])
    ctr = ctr[:2] / ctr[2]
    assert abs(ctr[0] - W / 2) < 0.02 * W and abs(ctr[1] - H / 2) < 0.02 * H, (mv, ctr)
    def span(xo):
        a = M @ np.array([xo, 0.0, 1.0]); b = M @ np.array([xo, rs.oh, 1.0])
        return abs(b[1] / b[2] - a[1] / a[2])
    sl, sr = span(0.0), span(rs.ow)
    assert (sr < sl) if sign > 0 else (sl < sr), (mv, sl, sr)          # kamera sağdaysa sağ kenar yakındır
    assert rs._inside(margin=0.0), mv

# 6) tam video: boyut, kare sayısı, codec
import video_repair as vr  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "ğüş", "k.mp4")                   # Türkçe karakterli yol
    n = cm.render(img, out, "saga", seconds=2, fps=30, handheld="yuruyus")
    assert n == 60 and os.path.getsize(out) > 20000
    info = vr.video_info(out)
    assert info["frames"] in (59, 60, 61), info
    assert abs(info["width"] / info["height"] - W / H) < 0.01, info
print("test_camera_move: TAMAM")

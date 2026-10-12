# -*- coding: utf-8 -*-
"""
Düzlem (tek homografi) yerleşim kuralı — YEREL test (K-23, 2026-10-13).

Kural: tasarım kumaşın her dalga/kıvrımını izlemez; BÜTÜN olarak tek perspektif dönüşümüyle yerleşir. Satır satır
değişen kenarlar ve ışık gradyanı tasarımın iç geometrisini bozmaz. Güçlü kıvrım/katlanma nedeniyle tasarım sığmıyorsa
tasarım zorla deforme edilmez; sahne "sahne_kivrim" ile uygunsuz sayılır.

Doğrulananlar:
  1. Dalgalı kenarlı (hafif) sahnede: tasarımdaki düz dikey ve yatay çizgiler çıktıda DÜZ (doğruya uyum artığı <= 0,6 px),
     önden görünümde yatay ve dikey ölçek eşit (oran korunur, fark <= %1,5), dönüşüm her yerde tek homografi.
  2. Tasarımın sol-üst köşesi kumaşın (uydurulan) sol-üst köşesinde: kırpma/kenar boşluğu yok.
  3. Güçlü katlanmada (kenar sapması büyük) sahne_kivrim; tasarımın baskılı kısmı kumaş dışına düşüyorsa sahne_kivrim.
  4. Perspektifli (açılı) dörtgende tasarımın tamamına tek perspektif uygulanır (düz çizgiler düz kalır).
Çalıştır: python tests/test_duzlem_yerlesim.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2                      # noqa: E402
import numpy as np              # noqa: E402

import banner_detect as bd      # noqa: E402
import compositor as cp         # noqa: E402
import mock_provider as mp      # noqa: E402
import product                  # noqa: E402

PROF = product.profil_olustur("75x200")
DW, DH = 750, 2000


def design_grid():
    rgba = np.zeros((DH, DW, 4), np.uint8)
    for x in (150, 375, 600):
        rgba[200:1800, x - 1:x + 2] = (20, 20, 20, 255)             # dikey çizgiler
    for y in (400, 1000, 1600):
        rgba[y - 1:y + 2, 100:650] = (20, 20, 20, 255)              # yatay çizgiler
    f = rgba.astype(np.float32) / 255.0
    return np.clip(f[..., :3] * f[..., 3:4] + (1 - f[..., 3:4]), 0, 1).astype(np.float32)


def wavy_scene(amp_frac, seed=21, narrow_mid=0.0):
    sc, t = mp.square_scene(1536, PROF.oran, "dokunan", seed=seed)
    sc = sc.astype(np.float32)
    x0, x1, top, bot = int(round(t["x0"])), int(round(t["x1"])), int(round(t["top"])), int(round(t["contact"]))
    wall = sc[top:bot, max(0, x0 - 40):x0 - 10].mean((0, 1))
    w = x1 - x0
    for y in range(top + 5, bot - 5):
        k = (y - top) / max(bot - top, 1)
        d = int(round(amp_frac * w * (0.5 + 0.5 * np.sin(k * np.pi * 6))))           # kenarı dalgalı "yiyen" döküm
        d += int(round(narrow_mid * w * np.exp(-((k - 0.5) / 0.08) ** 2)))           # ortada içeri katlanma
        if d > 0:
            sc[y, x0:x0 + d] = wall
            sc[y, x1 - d:x1] = wall
    return np.clip(sc, 0, 255).astype(np.uint8), t


def line_residual(pts):
    pts = np.asarray(pts, np.float64)
    if len(pts) < 10:
        return 99.0
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c)
    n = vt[1]
    return float(np.abs((pts - c) @ n).max())


design = design_grid()

# ---------------------------------------------------------------- 1-2: hafif dalgalı kenar
sc, t = wavy_scene(0.012)
det = bd.detect(sc, hint={"kind": "fabric"})
assert det.ok, det.reject
out, info, model = cp.composite(sc, design, det, mode="tam_kumas", profile=PROF, return_model=True)
assert info["yerlesim_donusumu"] == "homografi" and info["sorunlar"] == [], info["sorunlar"]
# dönüşüm modelinden: tasarımdaki dikey çizgiler (u=0,2 ve 0,8) sahnede DÜZ doğru (satır izleyen eski yolda 1,7 px bükülür)
uu_, vv_ = model["u"], model["v"]
bx_, by_ = model["bbox"][:2]
for target in (0.2, 0.8):
    pts_ = []
    for r in range(uu_.shape[0]):
        if not (0.15 < np.nanmedian(vv_[r]) < 0.85):
            continue
        row = uu_[r]
        j = np.flatnonzero((row[:-1] < target) & (row[1:] >= target))
        if len(j):
            k = j[0]
            pts_.append((bx_ + k + (target - row[k]) / (row[k + 1] - row[k]), by_ + r))
    bend = line_residual(pts_)
    print(f"model: u={target} çizgisinin sahnedeki doğrudan sapması {bend:.3f} px")
    assert bend < 0.1, f"tasarımın iç geometrisi kenar dalgasıyla bükülüyor: {bend:.2f} px"
ratio = out.astype(np.float32).mean(2) / np.maximum(sc.astype(np.float32).mean(2), 1.0)
ink = ratio < 0.6
q = np.array(info["dortgen"])
Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), q.astype(np.float32))
def to_scene(u, v):
    p = Hm @ np.array([u, v, 1.0]); return p[:2] / p[2]
worst = 0.0
for xd in (150, 375, 600):                                             # dikey çizgiler: her satırda mürekkep merkezi
    pts = []
    for vv in np.linspace(0.12, 0.88, 120):
        xs, ys = to_scene((xd + 0.5) / DW, vv)
        yi = int(round(ys)); xi = int(round(xs))
        seg = np.flatnonzero(ink[yi, xi - 8:xi + 9])
        if len(seg) and not np.any(np.diff(seg) > 1):
            pts.append((xi - 8 + seg.mean(), yi))
    worst = max(worst, line_residual(pts))
for yd in (400, 1000, 1600):                                           # yatay çizgiler
    pts = []
    for uu in np.linspace(0.16, 0.84, 120):
        xs, ys = to_scene(uu, (yd + 0.5) / DH)
        yi = int(round(ys)); xi = int(round(xs))
        seg = np.flatnonzero(ink[yi - 8:yi + 9, xi])
        if len(seg) and not np.any(np.diff(seg) > 1):
            pts.append((xi, yi - 8 + seg.mean()))
    worst = max(worst, line_residual(pts))
print(f"dalgalı kenarda düz çizgilerin doğruya uyum artığı: maks {worst:.2f} px; kenar sapması %{info['kenar_sapmasi'] * 100:.1f}")
assert worst <= 0.6, f"tasarımdaki düz çizgi çıktıda bükülmüş: {worst:.2f} px"
# önden: yatay ve dikey ölçek (px/cm) eşit -> oran korunur
sx = np.linalg.norm(q[1] - q[0]) / PROF.en_cm
sy = np.linalg.norm(q[3] - q[0]) / PROF.boy_cm
print(f"ölçek: yatay {sx:.3f} px/cm, dikey {sy:.3f} px/cm")
assert abs(sx / sy - 1) <= 0.015, (sx, sy)
# sol-üst köşe: uydurulan kumaş köşesinde (kenar boşluğu yok)
assert abs(q[0][0] - t["x0"]) <= 3 and abs(q[0][1] - t["top"]) <= 3, (q[0], t["x0"], t["top"])

# ---------------------------------------------------------------- 3: güçlü katlanma -> uygunsuz
sc2, _ = wavy_scene(0.0, narrow_mid=0.22)                               # ortada kumaş içeri katlanmış: çizgiler kumaş dışına düşer
det2 = bd.detect(sc2, hint={"kind": "fabric"})
if det2.ok:
    _, info2 = cp.composite(sc2, design, det2, mode="tam_kumas", profile=PROF)
    print("ortada katlanma:", [s["tur"] for s in info2["sorunlar"]], "kumaş dışı baskı", info2["kumas_disi_baski"])
    assert any(s["tur"] == "sahne_kivrim" for s in info2["sorunlar"]), info2["sorunlar"]
else:
    print("ortada katlanma: algılama zaten reddetti", det2.reject)
sc3, _ = wavy_scene(0.14)                                               # kenarlarda güçlü dalga
det3 = bd.detect(sc3, hint={"kind": "fabric"})
if det3.ok:
    _, info3 = cp.composite(sc3, design, det3, mode="tam_kumas", profile=PROF)
    print("güçlü kenar dalgası:", [s["tur"] for s in info3["sorunlar"]], "kenar sapması", info3["kenar_sapmasi"])
    assert any(s["tur"] == "sahne_kivrim" for s in info3["sorunlar"]), info3
else:
    print("güçlü kenar dalgası: algılama zaten reddetti", det3.reject)

# ---------------------------------------------------------------- 4: açılı dörtgen -> tek perspektif, düz çizgiler düz
sc4, t4 = mp.square_scene(1536, PROF.oran, "dokunan", seed=5)
W = sc4.shape[1]
src = np.float32([[0, 0], [W, 0], [W, W], [0, W]])
dst = np.float32([[0, 30], [W, 0], [W, W], [0, W - 30]])                # hafif yandan bakış (sol kenar daha kısa)
P = cv2.getPerspectiveTransform(src, dst)
sc4 = cv2.warpPerspective(sc4, P, (W, W), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
det4 = bd.detect(sc4, hint={"kind": "fabric"})
assert det4.ok, det4.reject
out4, info4, m4 = cp.composite(sc4, design, det4, mode="tam_kumas", profile=PROF, return_model=True)
u4, a4 = m4["u"], m4["alpha"] > 0.95
q4 = np.array(info4["dortgen"])
H4 = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), q4.astype(np.float32))
# dönüşümün tek homografi olduğunu doğrula: modelin u,v'si H4^-1 ile birebir
bx0, by0 = m4["bbox"][:2]
ys, xs = np.nonzero(a4)
sel = np.random.default_rng(0).choice(len(xs), 2000, replace=False)
pts = np.stack([xs[sel] + bx0 + 0.5, ys[sel] + by0 + 0.5, np.ones(2000)])
Hi = np.linalg.inv(H4)
uv = Hi @ pts; uv = uv[:2] / uv[2]
err = np.abs(uv[0] - u4[ys[sel], xs[sel]]).max()
print(f"açılı sahne: dönüşüm tek homografiden sapma maks {err:.4f} (u birimi), sorunlar {[s['tur'] for s in info4['sorunlar']]}")
assert err < 0.004, err
print("test_duzlem_yerlesim: TAMAM")

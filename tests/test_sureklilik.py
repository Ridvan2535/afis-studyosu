# -*- coding: utf-8 -*-
"""
Tam kumaş dönüşümünün SÜREKLİLİK testi (2026-10-12, kopma düzeltmesi) — YEREL, ağsız.

İşaret merkezlerini ölçmek yetmez: gerçek sahnede (iş 20261012-224824) harfler satır satır kopuyordu. Bu test
  * kumaş kenarı satır satır pürüzlü (gerçek algılama maskesi gibi) ve üzerinde sert ışık bantları olan bir sahnede,
  * kesintisiz ince dikey/çapraz çizgiler ve harf benzeri şekillerden oluşan tam oranlı bir tasarımı yerleştirir ve
  1. dönüşümde satırdan satıra ani yatay sıçrama olmadığını (u·genişlik'in ikinci farkı <= 1 px),
  2. katlanma olmadığını (du/dx > 0, hiç piksel <= 0 değil),
  3. ince dikey çizgilerin çıktıda satır satır izlendiğinde merkezinin hiçbir satırda 1.5 px'ten fazla sıçramadığını,
  4. harf benzeri şeklin (ince çizgili "E" ve "y" kuyruğu benzeri çapraz çizgi) kopmadığını (her satırda mürekkep var),
  5. ışık bantlarının (çarpma baskı modeli) korunduğunu, yani çıktının ışığı sahneden aldığını
doğrular. Eski kod (satır bazlı ham kenarlar + ışık gradyanından kıvrım kayması) bu testte BAŞARISIZ olur.
Çalıştır: python tests/test_sureklilik.py
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
rng = np.random.default_rng(7)

# ---------------------------------------------------------------- sahne: pürüzlü kenar + sert ışık bantları
scene, t = mp.square_scene(1536, PROF.oran, "dokunan", seed=11)
scene = scene.astype(np.float32)
x0, x1, top, bot = int(round(t["x0"])), int(round(t["x1"])), int(round(t["top"])), int(round(t["contact"]))
wall = scene[top:bot, max(0, x0 - 40):x0 - 10].mean((0, 1))
# kenarı rastgele satırlarda 2-6 px içeri "yiyen" basamaklar (gerçek maskelerdeki gibi satır gürültüsü)
for _ in range(60):
    y = int(rng.integers(top + 40, bot - 40)); h = int(rng.integers(2, 9)); dpx = int(rng.integers(2, 7))
    side = rng.integers(0, 2)
    if side == 0:
        scene[y:y + h, x0:x0 + dpx] = wall
    else:
        scene[y:y + h, x1 - dpx:x1] = wall
# kumaşın üzerinde sert dikey ışık bantları (kıvrım gölgesi taklidi): ışık gradyanı geometri DEĞİLDİR
xx = np.arange(scene.shape[1])
shade = 1.0 - 0.08 * (np.sin((xx - x0) / max(x1 - x0, 1) * np.pi * 7) > 0.6)
shade = cv2.GaussianBlur(shade.astype(np.float32)[None, :], (0, 0), 4.0)[0]
scene[top:bot, x0:x1] *= shade[None, x0:x1, None]
scene = np.clip(scene, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- tasarım: ince çizgiler + harf benzeri şekiller
rgba = np.zeros((DH, DW, 4), np.uint8)
LINES_U = [0.12, 0.31, 0.55, 0.83]
for u in LINES_U:                                            # 3 px kalınlığında kesintisiz dikey çizgiler
    xc = int(round(u * DW))
    rgba[150:1850, xc - 1:xc + 2] = (20, 20, 20, 255)
cv2.line(rgba, (80, 300), (680, 1700), (20, 20, 20, 255), 3, cv2.LINE_AA)        # uzun çapraz çizgi ("y" kuyruğu benzeri)
for k, y in enumerate((500, 900, 1300)):                                           # ince çizgili "E" benzeri harfler
    xL = 400
    rgba[y:y + 160, xL:xL + 4] = (20, 20, 20, 255)
    for dy in (0, 78, 156):
        rgba[y + dy:y + dy + 4, xL:xL + 90] = (20, 20, 20, 255)
f = rgba.astype(np.float32) / 255.0
design = np.clip(f[..., :3] * f[..., 3:4] + (1 - f[..., 3:4]), 0, 1).astype(np.float32)

det = bd.detect(scene, hint={"kind": "fabric"})
assert det.ok, det.reject
out, info, model = cp.composite(scene, design, det, mode="tam_kumas", profile=PROF, return_model=True)
assert info["sorunlar"] == [], info["sorunlar"]

# 1-2) dönüşüm sürekliliği ve katlanma
u, a = model["u"], model["alpha"]
ins = a > 0.95
W0 = info["genislik_px"]
d2 = np.abs(np.diff(u * W0, n=2, axis=0)); m2 = ins[2:] & ins[1:-1] & ins[:-2]
fold = int(((np.diff(u, axis=1) <= 0) & ins[:, 1:] & ins[:, :-1]).sum())
print(f"dönüşüm: satır ikinci farkı maks {d2[m2].max():.3f} px, katlanan piksel {fold}")
assert d2[m2].max() <= 1.0, f"dönüşümde satırdan satıra ani yatay sıçrama: {d2[m2].max():.2f} px"
assert fold == 0, f"dönüşüm {fold} pikselde katlanıyor"

# 3) ince dikey çizgileri satır satır izle: merkez hiçbir satırda 1.5 px'ten fazla sıçramasın
bx0, by0 = model["bbox"][:2]
ratio = out.astype(np.float32).mean(2) / np.maximum(scene.astype(np.float32).mean(2), 1.0)
ink = ratio < 0.55
y_a = int(t["top"] + 0.10 * t["total_px"]); y_b = int(t["top"] + 0.90 * t["total_px"])
worst = 0.0
for uu in LINES_U:
    prev = None
    for y in range(y_a, y_b):
        r = y - by0
        if not (0 <= r < u.shape[0]):
            continue
        row_u = u[r]
        c = int(np.argmin(np.abs(row_u - uu))) + bx0          # bu satırda çizginin beklenen yaklaşık yeri
        seg = ink[y, c - 12:c + 13]
        xs = np.flatnonzero(seg)
        assert len(xs), f"u={uu} çizgisi y={y} satırında KOPUK (mürekkep yok)"
        if len(xs) > 7 or np.any(np.diff(xs) > 1):           # çapraz çizgi / "E" kolu pencereye girdi: merkez ölçülemez, atla
            prev = None
            continue
        xcen = c - 12 + xs.mean()
        if prev is not None:
            worst = max(worst, abs(xcen - prev))
        prev = xcen
print(f"ince dikey çizgiler: satırdan satıra en büyük merkez sıçraması {worst:.2f} px")
assert worst <= 1.5, f"ince çizgi bir satırda {worst:.2f} px sıçradı (kopma/kayma)"

# 4) çapraz çizgi ve "E" şekilleri: her satırda mürekkep sürekli (kopma yok)
def rows_with_ink(v0, v1, u0, u1):
    miss = 0
    for v in np.linspace(v0, v1, 200):
        y = int(round(t["top"] + v * t["total_px"])) - by0
        if not (0 <= y < u.shape[0]):
            continue
        cols = np.flatnonzero((u[y] >= u0) & (u[y] <= u1))
        if len(cols) and not ink[y + by0, cols + bx0].any():
            miss += 1
    return miss
miss_diag = rows_with_ink(0.16, 0.84, 0.08, 0.93)
miss_E = sum(rows_with_ink((y + 3) / DH, (y + 157) / DH, 0.52, 0.55) for y in (500, 900, 1300))
print(f"çapraz çizgi kopuk satır: {miss_diag}, E dikeyi kopuk satır: {miss_E}")
assert miss_diag == 0 and miss_E == 0

# 5) ışık korunur: tasarımın boş (şeffaf) yerinde çıktı = sahne (ışık bantları dahil)
blank = (ratio > 0.97) & (a[..., ] is not None)
yb = int(t["top"] + 0.05 * t["total_px"])
strip = slice(x0 + 5, x1 - 5)
assert np.abs(out[yb, strip].astype(int) - scene[yb, strip].astype(int)).max() <= 2, "boş alanda sahne ışığı değişmiş"
assert info["kivrim_kaymasi"] == 0.0
print("test_sureklilik: TAMAM")

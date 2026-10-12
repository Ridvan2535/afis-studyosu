# -*- coding: utf-8 -*-
"""
Oran düzeltme: yapay zekânın çizdiği afiş tasarımdan daha İNCE çıktıysa (tipik: 0.30-0.40, tasarım 0.51) sahne atılmaz;
afişin bulunduğu yatay şerit orantılı olarak genişletilir (çubuk/asma çubuğu ve kumaş birlikte). Kumaş dokusu düz olduğu için
yatayda %20-45 uzatma gözle fark edilmez; kenarlara doğru yumuşak geçiş olduğu için duvar ve eşyalarda kayma görünmez.
Yalnızca DAR afiş düzeltilir (geniş afiş için duvarı yeniden çizmek gerekirdi).
Sonuçta afişin en-boy oranı tasarımla birebir aynı olur; tasarım afişi tam doldurur ve çarpılmaz.
"""
from __future__ import annotations

import cv2
import numpy as np

MAX_STRETCH = 1.60        # bundan fazla uzatma kumaş dokusunu belli eder: sahne atılır (oran 0.32 ve üstü düzeltilir)
MIN_STRETCH = 1.04        # bundan az fark: dokunma
MAX_FRAME_ASPECT = 0.80   # düzeltme sonrası görsel bu en/boy oranından genişse kenarlardan kırpılır


def _smoother(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


def banner_extent(mask) -> tuple | None:
    """Afişin (x_sol, x_sag, y_ust, y_alt) ölçüsü: satır ortancaları, çubuk/ip çıkıntılarına dayanıklı."""
    m = mask > 0
    ys, xs = np.where(m)
    if len(xs) == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max())
    h = y1 - y0 + 1
    rows = np.arange(int(y0 + 0.12 * h), int(y0 + 0.92 * h))
    xl, xr = [], []
    for r in rows:
        idx = np.flatnonzero(m[r])
        if len(idx):
            xl.append(idx[0]); xr.append(idx[-1])
    if len(xl) < 20:
        return None
    return float(np.median(xl)), float(np.median(xr)), y0, y1


def stretch_factor(cur_aspect: float, target_aspect: float) -> float:
    return target_aspect / max(cur_aspect, 1e-6)


def fixable(cur_aspect: float, target_aspect: float) -> bool:
    f = stretch_factor(cur_aspect, target_aspect)
    return MIN_STRETCH <= f <= MAX_STRETCH


def widen(img, mask, cur_aspect: float, target_aspect: float, ramp=0.28):
    """(yeni_görsel, f, bilgi) döner. mask: algılanan afiş maskesi. Çağıran fixable() ile uygunluğu denetlemiş olmalı."""
    ext = banner_extent(mask)
    if ext is None:
        raise ValueError("afiş ölçülemedi")
    xl, xr, _, _ = ext
    H, W = img.shape[:2]
    bw = xr - xl + 1
    f = stretch_factor(cur_aspect, target_aspect)
    ra = ramp * bw
    xa, xb = max(0.0, xl - ra), min(W - 1.0, xr + ra)
    x = np.arange(W, dtype=np.float64)
    w = np.ones(W)
    left = (x - xa) / max(xl - xa, 1.0)
    right = (xb - x) / max(xb - xr, 1.0)
    w = np.where(x < xl, _smoother(left), np.where(x > xr, _smoother(right), 1.0))
    slope = 1.0 + (f - 1.0) * w
    X = np.concatenate([[0.0], np.cumsum(slope)[:-1]])            # kaynak sütun x -> çıktı konumu
    W2 = int(round(X[-1] + slope[-1]))
    u = np.arange(W2, dtype=np.float64)
    src = np.interp(u, X, x)                                      # çıktı sütunu u -> kaynak sütun
    map_x = np.tile(src.astype(np.float32), (H, 1))
    map_y = np.tile(np.arange(H, dtype=np.float32)[:, None], (1, W2))
    out = cv2.remap(img, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # çok genişlediyse kenarlardan kırp (afiş ortada kalsın, kenarına 4%'ten fazla yaklaşmasın)
    crop = (0, W2)
    if W2 / H > MAX_FRAME_ASPECT:
        keep = int(round(MAX_FRAME_ASPECT * H))
        nl, nr = float(np.interp(xl, x, X)), float(np.interp(xr, x, X)) + 1
        c = (nl + nr) / 2
        a0 = int(np.clip(round(c - keep / 2), 0, W2 - keep))
        pad = 0.04 * keep
        a0 = int(np.clip(a0, max(0, nr + pad - keep), min(W2 - keep, nl - pad))) if nl - pad >= nr + pad - keep else a0
        crop = (a0, a0 + keep)
        out = out[:, crop[0]:crop[1]]
    return out, float(f), {"f": round(float(f), 3), "genislik": [W, int(out.shape[1])], "kirpma": list(crop)}

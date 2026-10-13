# -*- coding: utf-8 -*-
"""
Eski kayıtlardaki algılama katmanlı (yeşil) elenen görselden YAKLAŞIK sahne görüntüsü hesaplar (2026-10-13).

Bu bir HAM GÖRSEL DEĞİLDİR. Eski sürüm elenen sahnenin yalnız algılama katmanlı halini saklıyordu
(banner_detect.overlay: maske içinde 0,6 x sahne + 0,4 x yeşil; üstünde 3 px mavi kenar çizgileri; JPEG %80).
Orijinal sahne kaydedilmediği için KURTARILAMAZ; bu fonksiyon yalnız gözle inceleme için yaklaşık bir görüntü verir:
maske içinde katman cebirsel olarak geri alınır (JPEG kaybı ~1,7 kat büyür), mavi çizgiler komşu piksellerle doldurulur.
Ölçüm/kalite kararı için kullanılmaz; yalnız inceleme ve kalıcı kontrol örnekleri içindir. Dosyaya yazmaz.
"""
from __future__ import annotations

import cv2
import numpy as np

RENKLER = {"yesil": np.array([0, 200, 0], np.float32),       # banner_detect.overlay: det.ok=True (BGR)
           "kirmizi": np.array([0, 0, 220], np.float32)}    # det.ok=False (algılama reddi)
ANA_KANAL = {"yesil": 1, "kirmizi": 2}


def _dene(v, renk):
    c = RENKLER[renk]
    inv = (v - 0.4 * c) / 0.6
    k = ANA_KANAL[renk]
    diger = [i for i in range(3) if i != k]
    d = v[..., k] - (v[..., diger[0]] + v[..., diger[1]]) / 2
    chi = inv.max(2) - inv.min(2)
    cand = (d > 40) & (chi < 70) & (inv.min(2) > -12) & (inv.max(2) < 268)
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand, 8)
    if n <= 1:
        return None, None, 0
    k2 = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    m = (lab == k2).astype(np.uint8)
    ff = m.copy()
    fm = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, fm, (0, 0), 1)
    m = m | (1 - ff)
    return inv, m, int(st[k2, cv2.CC_STAT_AREA])


def yaklasik_sahne(vis_bgr: np.ndarray, en_az_alan: float = 0.01) -> tuple[np.ndarray, np.ndarray, str]:
    """(yaklaşık sahne, kurtarılan maske 0/1, katman: "yesil" | "kirmizi" | "yok").
    Katman bulunamazsa ("yok") kaydedilen dosya zaten işaretsiz sahnedir (eski sürüm maske boşken sahneyi aynen yazardı);
    yine de JPEG %80 kayıplıdır ve büyütülmüş olabilir."""
    v = vis_bgr.astype(np.float32)
    en_iyi = None
    for renk in RENKLER:
        inv, m, alan = _dene(v, renk)
        if m is not None and alan >= en_az_alan * m.size and (en_iyi is None or alan > en_iyi[3]):
            en_iyi = (renk, inv, m, alan)
    if en_iyi is None:
        return vis_bgr.copy(), np.zeros(vis_bgr.shape[:2], np.uint8), "yok"
    renk, inv, m, _ = en_iyi
    blue = (v[..., 0] > 170) & (v[..., 1] < 90) & (v[..., 2] < 90)
    blue = cv2.dilate(blue.astype(np.uint8), np.ones((5, 5), np.uint8))
    yellow = (v[..., 0] < 90) & (v[..., 1] > 200) & (v[..., 2] > 200)          # köşe işaretleri (det.quad varsa)
    blue |= cv2.dilate(yellow.astype(np.uint8), np.ones((5, 5), np.uint8))
    out = np.clip(np.where(m[..., None] > 0, inv, v), 0, 255).astype(np.uint8)
    out = cv2.inpaint(out, blue, 5, cv2.INPAINT_TELEA)
    return out, m, renk

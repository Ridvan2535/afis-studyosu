# -*- coding: utf-8 -*-
"""Kurdele koruması: kurdele kuyrukları afişin dış kenarına binebilir. Baskı çarpma modeliyle yapıldığı için beyaz alanlar
kurdeleyi bozmaz; yine de tasarımın mürekkebi kurdelenin üstüne denk gelirse, kurdele renginde (bilinen renk) olan pikseller
özgün sahneden geri konur. Nötr (krem/siyah/gri) kurdelelerde renkle ayırmak mümkün olmadığı için dokunulmaz."""
from __future__ import annotations

import cv2
import numpy as np


def _lab(rgb):
    px = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
    return cv2.cvtColor(px, cv2.COLOR_BGR2LAB).astype(np.float32)[0, 0]


def mask(scene_bgr, hexv: str):
    """Kurdele renkli pikseller (float 0-1) ya da None (renk nötr, ayrılamaz)."""
    h = hexv.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    t = _lab(rgb)
    ta, tb = t[1] - 128, t[2] - 128
    tc = float(np.hypot(ta, tb))
    if tc < 14:
        return None
    lab = cv2.cvtColor(scene_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    a, b = lab[..., 1] - 128, lab[..., 2] - 128
    c = np.hypot(a, b)
    cosd = (a * ta + b * tb) / np.maximum(c * tc, 1e-6)
    m = (c > max(0.55 * tc, 12.0)) & (cosd > 0.866) & (np.abs(lab[..., 0] - t[0]) < 60)       # renk açısı +-30 derece
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.dilate(m, np.ones((5, 5), np.uint8))
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2)


def restore(scene_bgr, out_bgr, hexv: str | None):
    """Baskılı sahnede kurdele piksellerini özgün sahneden geri koyar."""
    if not hexv:
        return out_bgr
    m = mask(scene_bgr, hexv)
    if m is None:
        return out_bgr
    m = m[..., None]
    return np.clip(scene_bgr.astype(np.float32) * m + out_bgr.astype(np.float32) * (1 - m), 0, 255).astype(np.uint8)

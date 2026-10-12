# -*- coding: utf-8 -*-
"""Kılavuz görsel: afişin kadrajdaki yerini, boyunu ve karşıdan duruşunu gösteren sade bir yerleşim taslağı.
OpenAI/Gemini gibi görsel düzenleyebilen modellere verilir; model bunu gerçekçi bir fotoğrafa çevirir."""
from __future__ import annotations

import cv2
import numpy as np

TOP, BOTTOM = 0.11, 0.885          # afişin kadrajdaki üst/alt kenarı (yükseklik oranı)


def make_guide(frame_aspect: float, banner_aspect: float, long_side: int = 1536, ribbon_hex: str | None = None):
    """(png_bytes, (x0, y0, x1, y1)) döner. frame_aspect = kadraj genişlik/yükseklik."""
    H = int(long_side)
    W = int(round(H * frame_aspect))
    img = np.zeros((H, W, 3), np.float32)
    wall = np.linspace(196, 178, H, dtype=np.float32)[:, None, None]
    img[:] = wall
    fy = int(BOTTOM * H) + 4
    img[fy:] = np.array([128, 140, 150], np.float32)               # zemin (BGR, ılık gri)
    cv2.line(img, (0, fy), (W, fy), (96, 104, 112), 3)
    bh = (BOTTOM - TOP) * H
    bw = min(banner_aspect * bh, 0.80 * W)
    bh = bw / banner_aspect if bw < banner_aspect * bh else bh
    x0, x1 = int(round((W - bw) / 2)), int(round((W + bw) / 2))
    y0, y1 = int(round(TOP * H)), int(round(TOP * H + bh))
    # ahşap çerçeve (stand): iki ince dikme afişin hemen dışında, üstte yuvarlak çubuk, yerde iki ayak; köşelerde kurdele ve uzun kuyruklar
    wood = (92, 140, 190)                                                           # BGR, orta ton doğal ahşap
    pw = max(6, int(0.012 * W))
    gap = int(0.05 * W)
    px0, px1 = x0 - gap - pw, x1 + gap
    rod_y = y0 - int(0.004 * H)
    cv2.rectangle(img, (px0, rod_y - pw // 2), (px1 + pw, rod_y + pw // 2), wood, -1)                       # üst çubuk
    for px in (px0, px1):
        cv2.rectangle(img, (px, rod_y), (px + pw, fy), wood, -1)                                            # dikmeler
        cv2.rectangle(img, (px - int(0.03 * W), fy - pw), (px + pw + int(0.03 * W), fy), wood, -1)          # ayaklar
    cv2.rectangle(img, (x0 + 6, y0 + 8), (x1 + 10, y1 + 10), (140, 140, 140), -1)
    cv2.rectangle(img, (x0, y0), (x1, y1), (210, 229, 236), -1)                                             # afiş (üst çubuğu örter)
    cv2.rectangle(img, (x0, rod_y - pw // 2), (x1, y0 + int(0.004 * H)), wood, -1)
    if ribbon_hex:
        hx = ribbon_hex.lstrip("#")
        rgb = tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)) if len(hx) == 6 else (200, 184, 154)
        bgr = (rgb[2], rgb[1], rgb[0])
        tw = max(5, int(0.012 * W))
        for sgn, cx in ((1, x0 - gap // 2), (-1, x1 + gap // 2)):      # kuyruklar afişin DIŞINDA, dikmeyle afiş arasındaki boşlukta
            cv2.rectangle(img, (cx - tw // 2, rod_y - 6), (cx + tw // 2, rod_y + int(0.40 * (y1 - y0))), bgr, -1)       # kuyruk
            cv2.ellipse(img, (cx, rod_y), (int(tw * 1.8), int(tw * 1.2)), 0, 0, 360, bgr, -1)                                   # fiyonk
    ok, buf = cv2.imencode(".png", np.clip(img, 0, 255).astype(np.uint8))
    return buf.tobytes(), (x0, y0, x1, y1)

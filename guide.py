# -*- coding: utf-8 -*-
"""Kılavuz görsel: afişin kadrajdaki yerini, boyunu ve karşıdan duruşunu gösteren sade bir yerleşim taslağı.
OpenAI/Gemini gibi görsel düzenleyebilen modellere verilir; model bunu gerçekçi bir fotoğrafa çevirir.

Aşama 2A: fotoğraf hattı kare (1:1) kılavuz kullanır: make_guide(1.0, profil.oran). Stand (çubuk, iki dikme, ayaklar) ve kumaş
kadrajda tamamen görünür; kumaşın alt kenarı zemin çizgisine DEĞER (havada bitmez). Köşelerde her zaman görünür kurdele fiyonku
çizilir (renk verilmemişse nötr bir örnek renk). Kuşgözü çizilmez (ürün profilinde opsiyonel; kalite ölçütü değil)."""
from __future__ import annotations

import cv2
import numpy as np

TOP, BOTTOM = 0.11, 0.885          # afişin kadrajdaki üst/alt kenarı (yükseklik oranı)
DEFAULT_BOW_BGR = (170, 160, 200)  # renk seçilmemişse fiyonk için örnek renk (BGR, soluk gül); yalnız yerleşim gösterir


KILAVUZ_SURUMLERI = {
    1: "Aşama 2A kılavuzu (etkin): dikmeler afişten kadraj eninin %5'i kadar uzakta, kuyruklar dikme ile afiş arasında.",
    2: ("ADAY (etkin değil, ücretli denenmedi): dikmeler afişe yakın (%1,2), kuyruklar dikmelerin DIŞINDA; afişin arkası "
        "daha koyu düz zemin (kenar karşıtlığı); etekte ince temas gölgesi. Amaç: stand açıklığının kendisi ürün oranını "
        "taşısın; model açıklığı doldururken kumaşı genişletemesin."),
}


def make_guide(frame_aspect: float, banner_aspect: float, long_side: int = 1536, ribbon_hex: str | None = None,
               surum: int = 1):
    """(png_bytes, (x0, y0, x1, y1)) döner. frame_aspect = kadraj genişlik/yükseklik. surum: KILAVUZ_SURUMLERI."""
    H = int(long_side)
    W = int(round(H * frame_aspect))
    img = np.zeros((H, W, 3), np.float32)
    wall = np.linspace(196, 178, H, dtype=np.float32)[:, None, None]
    img[:] = wall
    fy = int(BOTTOM * H) + 4
    img[fy:] = np.array([128, 140, 150], np.float32)               # zemin (BGR, ılık gri)
    cv2.line(img, (0, fy), (W, fy), (96, 104, 112), 3)
    bh = fy - TOP * H                                               # kumaş üst kenardan zemin çizgisine kadar
    bw = min(banner_aspect * bh, 0.70 * W)                          # dikmeler ve fiyonklar da kadrajda kalsın
    bh = bw / banner_aspect if bw < banner_aspect * bh else bh
    x0, x1 = int(round((W - bw) / 2)), int(round((W + bw) / 2))
    y0 = int(round(fy - bh))                                        # alt kenar zemine değer (kısa afiş kalırsa üstten aşağı iner)
    y1 = fy + max(2, int(0.004 * H))
    # ahşap çerçeve (stand): iki ince dikme afişin hemen dışında, üstte yuvarlak çubuk, yerde iki ayak; köşelerde kurdele ve uzun kuyruklar
    wood = (92, 140, 190)                                                           # BGR, orta ton doğal ahşap
    pw = max(6, int(0.012 * W))
    gap = int(0.05 * W) if surum == 1 else max(4, int(0.012 * W))
    if surum == 2:                                                  # afişin arkasında koyu düz zemin: kenar karşıtlığı
        cv2.rectangle(img, (int(x0 - 0.10 * W), int(y0 - 0.04 * H)), (int(x1 + 0.10 * W), fy), (88, 80, 72), -1)
    px0, px1 = x0 - gap - pw, x1 + gap
    rod_y = y0 - int(0.004 * H)
    cv2.rectangle(img, (px0, rod_y - pw // 2), (px1 + pw, rod_y + pw // 2), wood, -1)                       # üst çubuk
    for px in (px0, px1):
        cv2.rectangle(img, (px, rod_y), (px + pw, fy), wood, -1)                                            # dikmeler
        cv2.rectangle(img, (px - int(0.03 * W), fy - pw), (px + pw + int(0.03 * W), fy), wood, -1)          # ayaklar
    cv2.rectangle(img, (x0 + 6, y0 + 8), (x1 + 10, y1 + 10), (140, 140, 140), -1)
    cv2.rectangle(img, (x0, y0), (x1, y1), (210, 229, 236), -1)                                             # afiş (üst çubuğu örter)
    cv2.rectangle(img, (x0, rod_y - pw // 2), (x1, y0 + int(0.004 * H)), wood, -1)
    if surum == 2:                                                  # etekte ince temas gölgesi (havada bitmez)
        cv2.line(img, (x0 - 4, y1 + 3), (x1 + 4, y1 + 3), (60, 64, 70), 4)
    if True:                                                       # tüm sahneler kurdeleli: fiyonk her zaman görünür
        bgr = DEFAULT_BOW_BGR
        if ribbon_hex:
            hx = ribbon_hex.lstrip("#")
            rgb = tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)) if len(hx) == 6 else (200, 184, 154)
            bgr = (rgb[2], rgb[1], rgb[0])
        tw = max(5, int(0.012 * W))
        kx = ((x0 - gap // 2), (x1 + gap // 2)) if surum == 1 else (px0 - int(0.02 * W), px1 + pw + int(0.02 * W))
        for sgn, cx in ((1, kx[0]), (-1, kx[1])):      # kuyruklar afişin DIŞINDA (v1: dikme ile afiş arası; v2: dikmelerin dışı)
            cv2.rectangle(img, (cx - tw // 2, rod_y - 6), (cx + tw // 2, rod_y + int(0.40 * (y1 - y0))), bgr, -1)       # kuyruk
            for ang, dx in ((25, -1), (-25, 1)):                                                                         # fiyonk: iki ilmek + düğüm
                cv2.ellipse(img, (cx + dx * int(tw * 1.3), rod_y), (int(tw * 1.6), int(tw * 1.0)), ang, 0, 360, bgr, -1)
            cv2.circle(img, (cx, rod_y), max(3, int(tw * 0.7)), bgr, -1)
    ok, buf = cv2.imencode(".png", np.clip(img, 0, 255).astype(np.uint8))
    return buf.tobytes(), (x0, y0, x1, y1)

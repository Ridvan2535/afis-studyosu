# -*- coding: utf-8 -*-
"""
Yerleşim kuralları: afiş DİK, KARŞIDAN (yan açısız) ve YERE KADAR uzanan boyda mı?
Algılanan afiş maskesinden ölçülür; kurallara uymayan sahne elenir (yan açılı afişe düz tasarım koymak yanlış görünür).

Ölçümler:
  oran      : afişin genişlik/yükseklik oranı tasarımın oranına yakın mı (yan açı afişi dar gösterir, yatay afiş de elenir)
  daralma   : üst ile alt genişlik farkı (perspektif/yan bakış)
  dikeylik  : sol/sağ kenarların düşeyden sapma açısı
  üst kenar : üst çubuğun yataylığı
  boy       : afiş kadrajın büyük kısmını kaplıyor ve alt kenarı kadrajın alt bölümünde (yere kadar)
Eşikler gerçek üretilmiş 5 sahneyle ve sentetik sahnelerle ayarlandı; ayrıntı için ölçümler rapora yazılır.
"""
from __future__ import annotations

import numpy as np

ASPECT_RATIO_TOL = (0.72, 1.30)     # (afiş oranı / tasarım oranı) bu aralıkta olmalı
TAPER_RANGE = (0.88, 1.14)          # üst genişlik / alt genişlik
MAX_EDGE_TILT_DEG = 4.0
MAX_TOP_TILT_DEG = 4.5
SIDE_RATIO_RANGE = (0.92, 1.09)     # sol çeyrekteki yükseklik / sağ çeyrekteki yükseklik (yan bakışta yakın taraf daha uzun görünür)
MIN_HEIGHT_FRAC = 0.62              # afiş yüksekliği / kadraj yüksekliği
MIN_BOTTOM_FRAC = 0.78              # afişin alt kenarı kadrajın en az %78'inde (yere yakın)
MAX_TOP_FRAC = 0.40                 # üst kenar kadrajın üst %40'ında


def _largest_component(mask):
    import cv2
    n, lab, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    if n <= 1:
        return None
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return lab == k


def measure(det, shape) -> dict | None:
    H, W = shape[:2]
    m = _largest_component(det.mask)
    if m is None:
        return None
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h = float(y1 - y0 + 1)
    rows = np.arange(int(y0 + 0.12 * h), int(y0 + 0.92 * h))
    if len(rows) < 20:
        return None
    xl = np.array([np.argmax(m[r]) for r in rows], np.float64)
    xr = np.array([W - 1 - np.argmax(m[r][::-1]) for r in rows], np.float64)
    w = xr - xl + 1
    third = max(len(rows) // 3, 1)
    w_top, w_bot, w_med = float(np.median(w[:third])), float(np.median(w[-third:])), float(np.median(w))

    def tilt(v):                       # düşeyden sapma (derece): x'in y'ye göre eğimi
        p = np.polyfit(rows.astype(np.float64), v, 1)
        return float(np.degrees(np.arctan(p[0])))

    # üst kenar eğimi (ip/çubuk gibi ince çıkıntılara dayanıklı: eğimlerin ortancası)
    cols = np.arange(int(x0 + 0.15 * (x1 - x0)), int(x0 + 0.85 * (x1 - x0)))
    top = np.array([np.argmax(m[:, c]) if m[:, c].any() else np.nan for c in cols], np.float64)
    ok = ~np.isnan(top)
    top_tilt = 0.0
    if ok.sum() > 30:
        cc, tt = cols[ok].astype(np.float64), top[ok]
        k = max(len(cc) // 3, 5)
        top_tilt = float(np.degrees(np.arctan(np.median((tt[k:] - tt[:-k]) / (cc[k:] - cc[:-k])))))

    def col_height(frac):
        c = int(x0 + frac * (x1 - x0))
        run = m[:, max(c - 3, 0):c + 4].any(axis=1)
        yy = np.where(run)[0]
        return float(yy.max() - yy.min() + 1) if len(yy) else np.nan

    side = col_height(0.2) / col_height(0.8)
    return {"aspect": w_med / h, "taper": w_top / max(w_bot, 1.0), "tilt_left": tilt(xl), "tilt_right": tilt(xr),
            "top_tilt": top_tilt, "side_ratio": float(side), "h_frac": h / H, "top_frac": y0 / H,
            "bottom_frac": (y1 + 1) / H, "w_frac": w_med / W, "cx_frac": (x0 + x1) / 2 / W}


def check(det, shape, design_aspect: float, ignore_aspect: bool = False) -> tuple[str | None, dict]:
    """(elenme nedeni ya da None, ölçümler). ignore_aspect: en-boy oranını denetleme (oran sonradan düzeltilecekse)."""
    me = measure(det, shape)
    if me is None:
        return "afiş ölçülemedi", {}
    r = me["aspect"] / design_aspect
    bad = []
    if not ignore_aspect and not (ASPECT_RATIO_TOL[0] <= r <= ASPECT_RATIO_TOL[1]):
        if me["aspect"] > design_aspect:
            bad.append(f"afiş çok geniş/yatay (oran {me['aspect']:.2f}, tasarım {design_aspect:.2f})")
        else:
            bad.append(f"afiş çok dar ya da yan açılı görünüyor (oran {me['aspect']:.2f}, tasarım {design_aspect:.2f})")
    if not (TAPER_RANGE[0] <= me["taper"] <= TAPER_RANGE[1]):
        bad.append(f"perspektif/yan açı var (üst/alt genişlik {me['taper']:.2f})")
    if max(abs(me["tilt_left"]), abs(me["tilt_right"])) > MAX_EDGE_TILT_DEG:
        bad.append(f"afiş dik değil (kenar eğimi {max(abs(me['tilt_left']), abs(me['tilt_right'])):.1f}°)")
    if not (SIDE_RATIO_RANGE[0] <= me["side_ratio"] <= SIDE_RATIO_RANGE[1]):
        bad.append(f"afiş yan açıdan çekilmiş (sol/sağ yükseklik oranı {me['side_ratio']:.2f})")
    if abs(me["top_tilt"]) > MAX_TOP_TILT_DEG:
        bad.append(f"üst kenar yatay değil ({abs(me['top_tilt']):.1f}°)")
    if me["h_frac"] < MIN_HEIGHT_FRAC or me["bottom_frac"] < MIN_BOTTOM_FRAC or me["top_frac"] > MAX_TOP_FRAC:
        bad.append(f"afiş yere kadar uzanmıyor (kadrajın %{me['top_frac'] * 100:.0f}-%{me['bottom_frac'] * 100:.0f} aralığında)")
    return ("; ".join(bad) if bad else None), {k: round(v, 3) for k, v in me.items()}


def score(me: dict, design_aspect: float) -> float:
    """Kapıdan geçmiş bir sahnenin kalitesi (0-100): ideale (tam karşıdan, dik, tasarım oranında, yere kadar,
    kadrajı iyi dolduran) ne kadar yakın. Servisleri ve sahneleri karşılaştırmak için kullanılır."""
    if not me:
        return 0.0
    r = me["aspect"] / design_aspect
    pen = 0.0
    pen += min(abs(np.log(max(r, 1e-3))) / np.log(ASPECT_RATIO_TOL[1]), 1.0) * 30       # oran tasarıma ne kadar yakın
    pen += min(abs(me["taper"] - 1.0) / 0.14, 1.0) * 15                                  # perspektif
    pen += min(max(abs(me["tilt_left"]), abs(me["tilt_right"])) / MAX_EDGE_TILT_DEG, 1.0) * 10
    pen += min(abs(me["top_tilt"]) / MAX_TOP_TILT_DEG, 1.0) * 8
    pen += min(abs(me["side_ratio"] - 1.0) / 0.09, 1.0) * 17                             # yan bakış
    pen += min(max(0.0, 0.80 - me["h_frac"]) / 0.18, 1.0) * 10                           # boy kadrajı iyi doldursun
    pen += min(abs(me["cx_frac"] - 0.5) / 0.15, 1.0) * 10                                # ortalı olsun
    return round(max(0.0, 100.0 - pen), 1)

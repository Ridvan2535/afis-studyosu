"""
Otomatik afiş algılama (boş afişli sahne fotoğrafı -> maske + geometri + kalite kapısı).

Çıktı bir `Detection` nesnesidir:
  kind   = "rigid"  -> sert afiş (çerçeve, pano, karton): 4 köşe (quad) bulunur
         = "fabric" -> kumaş/yumuşak afiş: satır satır sol/sağ kenar eğrisi (edges) bulunur
  reject = sahneyi eleten nedenler (boş liste = sahne geçerli)
  warn   = elemeyen ama dikkat edilmesi gereken nedenler

Arkauçlar:
  "classical": OpenCV. Afiş renk/kroma modeli + kenar bariyeriyle tohumdan büyütülür.
               Bu ortamda test edildi. Sınırı: afiş ile arka plan AYNI renkteyse (beyaz afiş / beyaz duvar,
               beyaz çerçeve) ayıramaz; bu durumda sahne kalite kapısında elenir.
  "sam2"     : Meta SAM 2 (nokta istemiyle). SAM2_CKPT ortam değişkeni ile ağırlık dosyası verilirse çalışır.
               DİKKAT: Bu kod bu ortamda çalıştırılıp test EDİLEMEDİ (model ağırlıklarına erişim yoktu).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d, median_filter

WORK_MAX = 1600            # algılama çalışma çözünürlüğü (uzun kenar)
MIN_AREA, MAX_AREA = 0.015, 0.65      # maske / görsel alanı oranı sınırları
BORDER_TOUCH_REJECT = 0.02            # afiş kadrajdan taşıyorsa ele
# Eşikler az sayıda örnekle ayarlandı (temiz afişlerde detay 0.4-0.6, yazı çizilmiş afişte ~5, delik 0 / %5.6).
# Gerçek üretilmiş sahnelerle denedikçe report.json'daki metriklere bakıp yeniden ayarla.
HOLES_WARN, HOLES_REJECT = 0.015, 0.04  # içindeki "boş olmayan" alan oranı
DETAIL_WARN, DETAIL_REJECT = 1.8, 3.5   # afiş içi ortalama ince detay
# Asıl ayırıcı: afiş içinde "güçlü yerel detay" (yüksek geçiren > 14 seviye) taşıyan piksel yüzdesi.
# Temiz sentetik afiş %0, gerçek kumaş %0.023; küçük/soluk yazı %0.37-1.9.
STRONG_LEVEL, STRONG_WARN, STRONG_REJECT = 14.0, 0.08, 0.25


@dataclass
class Detection:
    mask: np.ndarray                     # uint8 0/255, orijinal çözünürlük
    kind: str                            # "rigid" | "fabric"
    quad: np.ndarray | None = None       # (4,2) TL,TR,BR,BL  (rigid)
    edges: np.ndarray | None = None      # (N,3) y, x_sol, x_sag  (fabric)
    backend: str = "classical"
    metrics: dict = field(default_factory=dict)
    reject: list = field(default_factory=list)
    warn: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reject

    def scaled(self, f: float, shape) -> "Detection":
        """Aynı sahnenin f kat büyütülmüş hali için algılama sonucu (yeniden algılamadan; yüksek çözünürlüklü video kaynağı için)."""
        H2, W2 = int(shape[0]), int(shape[1])
        m = cv2.resize(self.mask, (W2, H2), interpolation=cv2.INTER_LINEAR)
        m = ((m > 127) * 255).astype(np.uint8)
        quad = None if self.quad is None else (np.asarray(self.quad, np.float64) + 0.5) * f - 0.5
        edges = None if self.edges is None else ((np.asarray(self.edges, np.float64) + 0.5) * f - 0.5).astype(np.float32)
        return Detection(m, self.kind, quad, edges, backend=self.backend, metrics=dict(self.metrics),
                         reject=list(self.reject), warn=list(self.warn))


# ----------------------------------------------------------------------------
# İpucu (hint) dosyası: sahne.jpg yanında sahne.json
#   {"point":[0.5,0.55]}  | {"box":[x0,y0,x1,y1]} | {"polygon":[[x,y],...]} | {"kind":"fabric"}
# Sayılar 0-1 arasındaysa görsel boyutuna oranlı kabul edilir.
# ----------------------------------------------------------------------------
def load_hint(scene_path: str) -> dict:
    p = os.path.splitext(scene_path)[0] + ".json"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _px(v, W, H):
    x, y = v
    if 0 <= x <= 1 and 0 <= y <= 1:
        return int(x * (W - 1)), int(y * (H - 1))
    return int(x), int(y)


def _seeds(hint, W, H):
    if "point" in hint:
        return [_px(hint["point"], W, H)]
    if "box" in hint:
        x0, y0 = _px(hint["box"][:2], W, H)
        x1, y1 = _px(hint["box"][2:], W, H)
        return [((x0 + x1) // 2, (y0 + y1) // 2)]
    xs = np.linspace(0.28, 0.72, 5)
    ys = np.linspace(0.28, 0.78, 6)
    return [(int(x * W), int(y * H)) for y in ys for x in xs]


# ----------------------------------------------------------------------------
# Klasik algılama
# ----------------------------------------------------------------------------
def _prep(work_bgr):
    H, W = work_bgr.shape[:2]
    blur = cv2.GaussianBlur(work_bgr, (0, 0), max(2.0, 0.002 * max(H, W)))
    lab = cv2.cvtColor(blur, cv2.COLOR_BGR2LAB).astype(np.float32)
    gray = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
    edges = cv2.dilate(cv2.Canny(gray, 10, 30), np.ones((3, 3), np.uint8))
    return lab, edges


def _grow(prep, seed, chroma_tol=5.5):
    lab, edges = prep
    H, W = lab.shape[:2]
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    x, y = seed
    r = max(6, int(0.02 * min(H, W)))
    patch = lab[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].reshape(-1, 3)
    mu = np.median(patch, 0)
    cstd = float(np.hypot(patch[:, 1].std(), patch[:, 2].std()))
    tol = float(np.clip(chroma_tol + 3 * cstd, chroma_tol, 9.0))
    ok = (np.hypot(A - mu[1], B - mu[2]) < tol) & (np.abs(L - mu[0]) < 60)
    cand = (ok & (edges == 0)).astype(np.uint8)
    k = max(3, int(0.008 * min(H, W))) | 1
    cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    _, lbl = cv2.connectedComponents(cand, connectivity=4)
    if lbl[y, x] == 0:
        return None
    return (lbl == lbl[y, x]).astype(np.uint8)


def _fill_holes(m):
    inv = (m == 0).astype(np.uint8)
    _, lbl = cv2.connectedComponents(inv, connectivity=4)
    border = np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))
    holes = (inv == 1) & ~np.isin(lbl, border)
    return (m.astype(bool) | holes).astype(np.uint8), holes


def _finalize(m):
    """Maskeyi kapat, delikleri doldur. (maske, delik_oranı) döner."""
    H, W = m.shape
    k = max(3, int(0.012 * min(H, W))) | 1
    closed = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    filled, holes = _fill_holes(closed)
    area = max(int(filled.sum()), 1)
    return filled, float(holes.sum()) / area


def _contour(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cnts, key=cv2.contourArea)


def _color_stats(lab, m):
    """Maskenin ortalama açıklığı (L, 0-255) ve kroması."""
    er = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8))
    sel = er > 0
    if sel.sum() < 50:
        sel = m > 0
    px = lab[sel].astype(np.float32)
    return float(px[:, 0].mean()), float(np.hypot(px[:, 1] - 128, px[:, 2] - 128).mean())


def _color_factor(L, ch):
    """Baskı modeli çarpmaya dayanır: boş afiş açık renkli ve nötr (beyaz/krem/açık gri) olmalı."""
    fl = np.clip((L - 120) / 50, 0, 1)        # L<=120 -> 0, L>=170 -> 1
    fc = np.clip(1 - (ch - 20) / 25, 0, 1)    # kroma<=20 -> 1, >=45 -> 0
    return float(fl * fc)


def _score(mask):
    H, W = mask.shape
    c = _contour(mask)
    area = cv2.contourArea(c)
    harea = max(cv2.contourArea(cv2.convexHull(c)), 1.0)
    solidity = area / harea
    ar = area / (H * W)
    border = int(mask[0].sum() + mask[-1].sum() + mask[:, 0].sum() + mask[:, -1].sum())
    border_frac = border / (2.0 * (W + H))
    M = cv2.moments(c)
    cx, cy = (M["m10"] / max(M["m00"], 1), M["m01"] / max(M["m00"], 1))
    center_dist = np.hypot(cx / W - 0.5, cy / H - 0.5) / 0.7
    s = solidity * (1 - min(1.0, 4 * border_frac)) * (1 - 0.4 * min(1.0, center_dist))
    if ar < 0.02:
        s *= ar / 0.02
    if ar > 0.55:
        s *= max(0.0, (0.85 - ar) / 0.30)
    return float(s), float(ar), float(solidity), float(border_frac)


# ----------------------------------------------------------------------------
# Geometri: sert afiş mi, kumaş mı?
# ----------------------------------------------------------------------------
def _order_quad(q):
    q = np.asarray(q, np.float32).reshape(4, 2)
    c = q.mean(0)
    ang = np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0])
    q = q[np.argsort(ang)]            # y aşağı eksende: TL, TR, BR, BL (saat yönü)
    i = int(np.argmin(q.sum(1)))
    return np.roll(q, -i, axis=0)


def _seg_dist(P, a, b):
    ab = b - a
    t = ((P - a) @ ab) / max(float(ab @ ab), 1e-9)
    tc = np.clip(t, 0, 1)
    proj = a + tc[:, None] * ab
    return np.linalg.norm(P - proj, axis=1), t


def _intersect(p0, v0, p1, v1):
    A = np.array([[v0[0], -v1[0]], [v0[1], -v1[1]]], np.float64)
    if abs(np.linalg.det(A)) < 1e-9:
        return None
    s, _ = np.linalg.solve(A, np.array([p1[0] - p0[0], p1[1] - p0[1]], np.float64))
    return p0 + s * v0


def _refine_quad(P, quad, area):
    """Her kenar için konturdan doğru uydur, kesişimlerden köşeleri bul (alt-piksel doğruluk)."""
    tol = 0.02 * np.sqrt(area) + 2
    lines = []
    for i in range(4):
        a, b = quad[i].astype(np.float64), quad[(i + 1) % 4].astype(np.float64)
        d, t = _seg_dist(P, a, b)
        sel = P[(d < tol) & (t > 0.08) & (t < 0.92)]
        if len(sel) < 20:
            return quad
        v = cv2.fitLine(sel.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        lines.append((np.array([v[2], v[3]], np.float64), np.array([v[0], v[1]], np.float64)))
    out = []
    diag = np.hypot(*(quad.max(0) - quad.min(0)))
    for i in range(4):
        p = _intersect(*lines[i - 1], *lines[i])
        if p is None or np.linalg.norm(p - quad[i]) > 0.05 * diag:
            return quad
        out.append(p)
    return np.array(out, np.float32)


def _fit_geometry(mask, force_kind=None):
    c = _contour(mask)
    area = cv2.contourArea(c)
    hull = cv2.convexHull(c)
    peri = cv2.arcLength(hull, True)
    quad = None
    for eps in (0.01, 0.02, 0.03, 0.04, 0.05):
        ap = cv2.approxPolyDP(hull, eps * peri, True)
        if len(ap) == 4:
            quad = _order_quad(ap.reshape(4, 2))
            break
    P = c.reshape(-1, 2).astype(np.float64)
    info = {"solidity": float(area / max(cv2.contourArea(hull), 1))}
    rigid = False
    if quad is not None:
        rect_fill = area / max(cv2.contourArea(quad.astype(np.float32)), 1)
        dev = np.min([_seg_dist(P, quad[i].astype(np.float64), quad[(i + 1) % 4].astype(np.float64))[0]
                      for i in range(4)], axis=0)
        straight = float(dev.mean() / np.sqrt(area))
        info.update(rect_fill=float(rect_fill), straightness=straight)
        rigid = rect_fill >= 0.93 and straight <= 0.012 and info["solidity"] >= 0.95
    if force_kind:
        rigid = force_kind == "rigid" and quad is not None
    if rigid:
        q = _order_quad(_refine_quad(P, quad, area))
        return "rigid", q, None, info
    return "fabric", None, _fabric_edges(mask), info


def _fabric_edges(mask):
    H, W = mask.shape
    rows = np.flatnonzero(mask.any(1))
    y0, y1 = int(rows[0]), int(rows[-1])
    ys = np.arange(y0, y1 + 1)
    xl = np.empty(len(ys))
    xr = np.empty(len(ys))
    for i, y in enumerate(ys):
        xs = np.flatnonzero(mask[y])
        xl[i], xr[i] = xs[0], xs[-1]
    n = y1 - y0 + 1
    k = max(5, int(0.04 * n)) | 1
    xl = gaussian_filter1d(median_filter(xl, size=k, mode="nearest"), 0.015 * n, mode="nearest")
    xr = gaussian_filter1d(median_filter(xr, size=k, mode="nearest"), 0.015 * n, mode="nearest")
    step = max(8, n // 60)
    # üst/alt kenarın dalgalı kısmında satırlar eksik kalır; uçlardan %6 kırp
    lo, hi = int(0.06 * n), int(0.94 * n)
    sel = np.arange(lo, hi, step)
    return np.stack([ys[sel], xl[sel], xr[sel]], 1).astype(np.float32)


# ----------------------------------------------------------------------------
# SAM 2 arkauç (OPSİYONEL, bu ortamda test edilemedi)
# ----------------------------------------------------------------------------
_SAM = {}


def _sam2_masks(work_bgr, seeds):
    ckpt = os.environ.get("SAM2_CKPT")
    if not ckpt or not os.path.exists(ckpt):
        return None
    try:
        import torch  # noqa
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except Exception:
        return None
    cfg = os.environ.get("SAM2_CFG", "configs/sam2.1/sam2.1_hiera_l.yaml")
    if "pred" not in _SAM:
        _SAM["pred"] = SAM2ImagePredictor(build_sam2(cfg, ckpt))
    pred = _SAM["pred"]
    pred.set_image(cv2.cvtColor(work_bgr, cv2.COLOR_BGR2RGB))
    out = []
    for (x, y) in seeds:
        masks, scores, _ = pred.predict(point_coords=np.array([[x, y]]), point_labels=np.array([1]),
                                        multimask_output=True)
        for m, s in zip(masks, scores):
            out.append(m.astype(np.uint8))
    return out


# ----------------------------------------------------------------------------
# Ana giriş
# ----------------------------------------------------------------------------
def detect(img_bgr, hint=None, backend="auto") -> Detection:
    hint = hint or {}
    H, W = img_bgr.shape[:2]
    scale = min(1.0, WORK_MAX / max(H, W))
    work = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img_bgr
    wh, ww = work.shape[:2]
    seeds = [(int(x * scale), int(y * scale)) for x, y in _seeds(hint, W, H)]

    lab_work = cv2.cvtColor(work, cv2.COLOR_BGR2LAB)
    cscore = lambda f: _score(f)[0] * _color_factor(*_color_stats(lab_work, f))

    cands, used = [], None          # (skor, maske, delik_oranı)
    if "polygon" in hint:
        poly = np.array([_px(p, W, H) for p in hint["polygon"]], np.float32) * scale
        m = np.zeros((wh, ww), np.uint8)
        cv2.fillPoly(m, [poly.astype(np.int32)], 1)
        cands.append((1.0, m, 0.0))
        used = "hint-polygon"
    if not cands and backend in ("auto", "sam2"):
        ms = _sam2_masks(work, seeds)
        if ms:
            used = "sam2"
            for m in ms:
                f, hf = _finalize(m)
                if f.sum() > 0:
                    cands.append((cscore(f), f, hf))
    if not cands and backend in ("auto", "classical"):
        used = "classical"
        prep = _prep(work)
        covered = np.zeros((wh, ww), bool)
        for sd in seeds:
            if covered[sd[1], sd[0]]:
                continue
            m = _grow(prep, sd)
            if m is None or m.sum() < 50:
                continue
            f, hf = _finalize(m)
            covered |= m.astype(bool)      # doldurulmamış maske: duvar aday ise içindeki afişi "kapsamış" sayma
            cands.append((cscore(f), f, hf))

    if not cands:
        d = Detection(np.zeros((H, W), np.uint8), "fabric", backend=used or backend)
        d.reject.append("afiş bulunamadı")
        return d

    score, wm, holes_frac = max(cands, key=lambda c: c[0])
    mask = cv2.resize(wm, (W, H), interpolation=cv2.INTER_NEAREST) if scale < 1 else wm
    mask = (mask > 0).astype(np.uint8)
    sc, ar, solidity, border_frac = _score(mask)
    lw, cw = _color_stats(lab_work, wm)
    cf = _color_factor(lw, cw)
    sc *= cf
    kind, quad, edges, ginfo = _fit_geometry(mask, hint.get("kind"))

    det = Detection(mask * 255, kind, quad, edges, backend=used or backend)
    det.metrics.update(score=sc, area_ratio=ar, border_touch=border_frac, holes=holes_frac,
                       lightness=lw, chroma=cw, **ginfo)

    # --- kalite kapısı ---
    if cf < 0.3:
        det.reject.append(f"bulunan bölge açık renkli/nötr değil (açıklık {lw:.0f}/255, kroma {cw:.0f}); "
                          "baskı modeli beyaz/krem/açık gri boş afiş ister")
    elif sc < 0.25:
        det.reject.append(f"güvenilir afiş bölgesi bulunamadı (skor {sc:.2f})")
    if ar > MAX_AREA:
        det.reject.append(f"bulunan bölge çok büyük (%{ar * 100:.0f}); duvar/arka plan olabilir")
    if ar < 0.01:
        det.reject.append(f"bulunan bölge çok küçük (%{ar * 100:.1f})")
    elif ar < MIN_AREA:
        det.warn.append(f"afiş küçük kadrajda (%{ar * 100:.1f})")
    if border_frac > BORDER_TOUCH_REJECT:
        det.reject.append("afiş kadraja taşıyor/kesilmiş")
    if holes_frac > HOLES_REJECT:
        det.reject.append(f"afişin içi boş değil (%{holes_frac * 100:.0f} farklı bölge)")
    elif holes_frac > HOLES_WARN:
        det.warn.append(f"afiş içinde farklı bölgeler (%{holes_frac * 100:.0f})")
    if kind == "fabric" and edges is not None:
        mw = float(np.mean(edges[:, 2] - edges[:, 1]))
        det.metrics["mean_width"] = mw
        if mw < 0.06 * W:
            det.reject.append("kumaş afiş çok dar")

    # boşluk (yazı/desen çizilmiş mi) denetimi
    if not det.reject:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        er = cv2.erode(mask, np.ones((max(3, int(0.02 * min(H, W))) | 1,) * 2, np.uint8))
        if er.sum() > 100:
            hp = np.abs(gray - cv2.GaussianBlur(gray, (0, 0), 4))
            vals = hp[er > 0]
            detail = float(vals.mean())
            strong = float((vals > STRONG_LEVEL).mean()) * 100      # güçlü yerel detay (% piksel)
            det.metrics["detail"] = detail
            det.metrics["strong_detail_pct"] = strong
            if strong > STRONG_REJECT or detail > DETAIL_REJECT:
                det.reject.append(f"afiş boş görünmüyor: yazı/desen benzeri detay var "
                                  f"(güçlü detay %{strong:.2f}, ortalama {detail:.1f})")
            elif strong > STRONG_WARN or detail > DETAIL_WARN:
                det.warn.append(f"afişte beklenmedik detay olabilir (güçlü detay %{strong:.2f})")
    return det


def overlay(img_bgr, det: Detection):
    """Hata ayıklama görseli: maske, köşeler/kenar eğrileri."""
    vis = img_bgr.copy()
    m = det.mask > 0
    col = (0, 200, 0) if det.ok else (0, 0, 220)
    vis[m] = (0.6 * vis[m] + 0.4 * np.array(col)).astype(np.uint8)
    if det.quad is not None:
        cv2.polylines(vis, [det.quad.astype(np.int32)], True, (255, 0, 0), 3, cv2.LINE_AA)
        for p in det.quad:
            cv2.circle(vis, tuple(int(v) for v in p), 8, (0, 255, 255), -1)
    if det.edges is not None:
        e = det.edges
        cv2.polylines(vis, [np.stack([e[:, 1], e[:, 0]], 1).astype(np.int32)], False, (255, 0, 0), 3, cv2.LINE_AA)
        cv2.polylines(vis, [np.stack([e[:, 2], e[:, 0]], 1).astype(np.int32)], False, (255, 0, 0), 3, cv2.LINE_AA)
    return vis

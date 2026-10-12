"""
Tasarımı algılanan afişe yerleştirme (statik kompozit).

  sert afiş  -> 4 köşeye perspektif dönüşümü (homografi)
  kumaş afiş -> kumaşın kenar eğrilerini yumuşakça takip eden ağ (mesh) warp + kıvrım kayması

Baskı modeli (ikisinde de aynı): sonuç = sahne pikseli x tasarım rengi (çarpma)
  - kumaşın/kâğıdın kendi ışığı, gölgesi, dokusu ve tonu sahneden gelir
  - açık zeminli tasarımlarda zemin rengi "beyaz" sayılır (zemin afişi hiç değiştirmez)
  - yazılar ve çizimler tasarım dosyasından gelir, yapay zeka çizmez
"""
from __future__ import annotations

import cv2
import numpy as np

import cvio

ASPECT_TOL = 0.15          # sert afişte afiş/tasarım en-boy farkı toleransı (oran, +-%15)


# ----------------------------------------------------------------------------
def load_design(path: str) -> np.ndarray:
    """PNG/JPG -> float32 BGR [0,1]. Şeffaf PNG beyaz zemine oturtulur (şeffaf = baskı yok)."""
    im = cvio.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    im = im.astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0) if im.dtype != np.float32 else im
    if im.shape[2] == 4:
        a = im[..., 3:4]
        im = im[..., :3] * a + (1 - a)
    return np.clip(im, 0, 1).astype(np.float32)


def estimate_paper(design: np.ndarray):
    """Tasarımın zemin rengi açıksa (parlaklık > 0.85) onu döndür; koyu zeminde None (beyaz sayılır)."""
    q = (design * 15).astype(np.int32)
    key = q[..., 0] * 256 + q[..., 1] * 16 + q[..., 2]
    vals, counts = np.unique(key, return_counts=True)
    top = vals[np.argmax(counts)]
    col = design[key == top].mean(0)
    lum = 0.114 * col[0] + 0.587 * col[1] + 0.299 * col[2]
    return col if lum > 0.85 else None


def quad_aspect(quad: np.ndarray) -> float:
    """Sert afişin yaklaşık en/boy oranı (karşılıklı kenar uzunluklarının ortalaması)."""
    tl, tr, br, bl = quad
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    return float(w / max(h, 1e-6))


def check_fit(det, design: np.ndarray):
    """Tasarım bu afişe uyar mı? Uymuyorsa neden metnini döndür, uyuyorsa None."""
    dh, dw = design.shape[:2]
    da = dw / dh
    if det.kind == "rigid":
        qa = quad_aspect(det.quad)
        if abs(np.log(qa / da)) > np.log(1 + ASPECT_TOL):
            return f"en-boy oranı uyumsuz (afiş {qa:.2f}, tasarım {da:.2f})"
    return None


# ----------------------------------------------------------------------------
def _prefit(design, tw, th):
    """Tasarım hedeften çok büyükse önce AREA ile küçült (örtüşme/aliasing olmasın)."""
    dh, dw = design.shape[:2]
    f = max(tw / dw, th / dh)
    if f < 0.75:
        return cv2.resize(design, (max(2, int(dw * f * 1.15)), max(2, int(dh * f * 1.15))),
                          interpolation=cv2.INTER_AREA)
    return design


def _apply_print(region, warped, alpha, ink, paper):
    d = warped
    if paper is not None:
        d = np.clip(d / paper[None, None, :], 0, 1)
    d = 1.0 - ink * (1.0 - d)               # ince kumaşta mürekkep tam kapatmaz
    printed = region * d
    return region * (1 - alpha) + printed * alpha


# ----------------------------------------------------------------------------
def _place_rigid(scene, design, det, ink, paper, ssaa):
    H, W = scene.shape[:2]
    q = det.quad.astype(np.float64)
    c = q.mean(0)
    q = c + (q - c) * 0.997                           # kenar taşmasını önlemek için hafif içeri
    x0, y0 = np.floor(q.min(0)).astype(int) - 3
    x1, y1 = np.ceil(q.max(0)).astype(int) + 3
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    bw, bh = (x1 - x0) * ssaa, (y1 - y0) * ssaa
    design = _prefit(design, bw, bh)
    dh, dw = design.shape[:2]
    src = np.float32([[0, 0], [dw - 1, 0], [dw - 1, dh - 1], [0, dh - 1]])
    dst = ((q - [x0, y0]) * ssaa).astype(np.float32)
    Hm = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(design, Hm, (bw, bh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    cov = cv2.warpPerspective(np.ones((dh, dw), np.float32), Hm, (bw, bh), flags=cv2.INTER_LINEAR, borderValue=0)
    warped = cv2.resize(warped, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(cov, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)[..., None]
    region = scene[y0:y1, x0:x1]
    out = scene.copy()
    out[y0:y1, x0:x1] = _apply_print(region, warped, np.clip(alpha, 0, 1), ink, paper)

    # --- baskı modeli (video onarımı için): sahne pikseli -> tasarım koordinatı (0-1) ---
    gx_r, gy_r = np.meshgrid(np.arange(x1 - x0, dtype=np.float32), np.arange(y1 - y0, dtype=np.float32))
    pts = np.stack([(gx_r + 0.5) * ssaa - 0.5 + 0 * gx_r, (gy_r + 0.5) * ssaa - 0.5], -1).reshape(-1, 1, 2)
    src_pts = cv2.perspectiveTransform(pts.astype(np.float64), np.linalg.inv(Hm)).reshape(y1 - y0, x1 - x0, 2)
    model = {"bbox": [int(x0), int(y0), int(x1), int(y1)],
             "u": (src_pts[..., 0] / (dw - 1)).astype(np.float32),
             "v": (src_pts[..., 1] / (dh - 1)).astype(np.float32),
             "alpha": np.clip(alpha[..., 0], 0, 1).astype(np.float32)}
    return out, {"bbox": [int(x0), int(y0), int(x1), int(y1)]}, model


def _place_fabric(scene, design, det, ink, paper, ssaa, follow, inset_frac, fold_shift, sag_frac):
    H, W = scene.shape[:2]
    mask = (det.mask > 0)
    ys_e, xl_e, xr_e = det.edges[:, 0], det.edges[:, 1], det.edges[:, 2]
    Lf = lambda y: np.interp(y, ys_e, xl_e)
    Rf = lambda y: np.interp(y, ys_e, xr_e)

    # dikey sınırlar: ortadaki sütunların üst/alt kenarının en içeri olanı + pay
    xs_any = np.flatnonzero(mask.any(0))
    cx0 = int(xs_any.min() + 0.2 * (xs_any.max() - xs_any.min()))
    cx1 = int(xs_any.min() + 0.8 * (xs_any.max() - xs_any.min()))
    top = [np.flatnonzero(mask[:, x])[0] for x in range(cx0, cx1) if mask[:, x].any()]
    bot = [np.flatnonzero(mask[:, x])[-1] for x in range(cx0, cx1) if mask[:, x].any()]
    ext_h = float(np.flatnonzero(mask.any(1))[-1] - np.flatnonzero(mask.any(1))[0])
    y_top = float(np.percentile(top, 90) + 0.06 * ext_h)
    y_bot = float(np.percentile(bot, 10) - 0.04 * ext_h)

    yy = np.linspace(y_top, y_bot, 40)
    mean_w = float(np.mean(Rf(yy) - Lf(yy)))
    inset = inset_frac * mean_w
    mean_l, mean_r = float(np.mean(Lf(yy))), float(np.mean(Rf(yy)))
    left = lambda y: (1 - follow) * mean_l + follow * Lf(y) + inset
    right = lambda y: (1 - follow) * mean_r + follow * Rf(y) - inset
    reg_w = float(np.mean(right(yy) - left(yy)))
    reg_h = y_bot - y_top

    # tasarımı bölgeye "contain" ile sığdır (en-boy bozulmaz, ortalanır)
    dh, dw = design.shape[:2]
    da, ra = dw / dh, reg_w / reg_h
    fw, fh = (da / ra, 1.0) if da < ra else (1.0, ra / da)

    ys_m, xs_m = np.flatnonzero(mask.any(1)), xs_any
    x0, x1 = max(0, int(xs_m.min()) - 4), min(W, int(xs_m.max()) + 5)
    y0, y1 = max(0, int(ys_m.min()) - 4), min(H, int(ys_m.max()) + 5)
    gx, gy = np.meshgrid(np.arange(x0 * ssaa, x1 * ssaa) / ssaa, np.arange(y0 * ssaa, y1 * ssaa) / ssaa)

    # kıvrım eğimine göre yatay kayma (baskı kıvrımı izlesin)
    lum = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
    g = cv2.Sobel(cv2.GaussianBlur(lum, (0, 0), 10), cv2.CV_32F, 1, 0, ksize=5)
    p99 = max(float(np.percentile(np.abs(g[mask]), 99)), 1e-6)
    g = np.clip(g / p99, -1, 1)[y0:y1, x0:x1]
    g = cv2.resize(g, (gx.shape[1], gx.shape[0]), interpolation=cv2.INTER_LINEAR)
    gxs = gx - fold_shift * mean_w * g

    L, R = left(gy), right(gy)
    u0 = (gxs - L) / (R - L)
    v0 = (gy - y_top) / reg_h
    sag = sag_frac * reg_w * np.sin(np.pi * np.clip(u0, 0, 1))     # asılı kumaşın üst kenarı hafif sarkar
    v0 = (gy - y_top - sag * (1 - np.clip(v0, 0, 1))) / reg_h
    u = (u0 - (1 - fw) / 2) / fw
    v = (v0 - (1 - fh) / 2) / fh
    inside = ((u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)).astype(np.float32)

    design = _prefit(design, reg_w * fw * ssaa, reg_h * fh * ssaa)
    dh, dw = design.shape[:2]
    warped = cv2.remap(design, (u * (dw - 1)).astype(np.float32), (v * (dh - 1)).astype(np.float32),
                       cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    sz = (x1 - x0, y1 - y0)
    warped = cv2.resize(warped, sz, interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(inside, sz, interpolation=cv2.INTER_AREA)
    # baskı afişin dışına taşmasın
    m_er = cv2.erode(mask[y0:y1, x0:x1].astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha * cv2.GaussianBlur(m_er, (0, 0), 1.5), (0, 0), 1.0)[..., None]

    region = scene[y0:y1, x0:x1]
    out = scene.copy()
    out[y0:y1, x0:x1] = _apply_print(region, warped, np.clip(alpha, 0, 1), ink, paper)

    # --- baskı modeli (video onarımı için): sahne pikseli -> tasarım koordinatı (0-1) ---
    model = {"bbox": [int(x0), int(y0), int(x1), int(y1)],
             "u": cv2.resize(u.astype(np.float32), sz, interpolation=cv2.INTER_AREA),
             "v": cv2.resize(v.astype(np.float32), sz, interpolation=cv2.INTER_AREA),
             "alpha": np.clip(alpha[..., 0], 0, 1).astype(np.float32)}
    return out, {"bbox": [int(x0), int(y0), int(x1), int(y1)],
                 "design_region": [round(y_top), round(y_bot), round(reg_w), round(fw, 2), round(fh, 2)]}, model


# ----------------------------------------------------------------------------
def composite(scene_bgr, design, det, *, paper="auto", ink=None, ssaa=2,
              follow=0.3, inset=0.10, fold_shift=0.01, sag=0.02, return_model=False):
    """scene_bgr uint8, design float32 BGR [0,1]. Sonuç (uint8 BGR, bilgi sözlüğü).

    return_model=True ise üçüncü eleman olarak "baskı modeli" döner: video onarımının ihtiyaç duyduğu
    {bbox, u, v, alpha, paper, ink}. u,v: bölge pikseli -> tasarım koordinatı (0-1), alpha: baskı kapsaması.
    """
    scene = scene_bgr.astype(np.float32) / 255.0
    p = estimate_paper(design) if paper == "auto" else paper
    ink_v = (1.0 if det.kind == "rigid" else 0.93) if ink is None else ink
    if det.kind == "rigid":
        out, info, model = _place_rigid(scene, design, det, ink_v, p, ssaa)
    else:
        out, info, model = _place_fabric(scene, design, det, ink_v, p, ssaa, follow, inset, fold_shift, sag)
    info["paper"] = None if p is None else [round(float(v), 3) for v in p]
    model.update(paper=p, ink=float(ink_v), kind=det.kind)
    img = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
    return (img, info, model) if return_model else (img, info)

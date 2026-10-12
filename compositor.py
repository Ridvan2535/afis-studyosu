"""
Tasarımı algılanan afişe yerleştirme (statik kompozit).

  sert afiş  -> 4 köşeye perspektif dönüşümü (homografi)
  kumaş afiş -> kumaşın kenar eğrilerini yumuşakça takip eden ağ (mesh) warp + kıvrım kayması
  tam kumaş  -> (Aşama 2A, composite(..., mode="tam_kumas", profile=...)) PNG tuvali = kumaşın tamamı; gerçek kenarlar,
                fiziksel dikey ölçek, zemine temas çizgisi, yerde biriken (gizli) kısım. Ayrıntı: _place_full_fabric.
  Eski iki yol (mode=None) eski çağrılar (video modülleri, pipeline.py, kontrol.py) için aynen korunur.

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
# TAM KUMAŞ yolu (Aşama 2A): PNG tuvali kumaşın TAMAMIDIR.
#   * yatay: u, kumaşın GERÇEK sol/sağ kenarlarından (kenar payı / içeri alma yok)
#   * dikey: fiziksel ölçek. px_per_cm = asılı kısmın ortanca genişliği / en_cm; v = (y - üst(x)) / (boy_cm * px_per_cm)
#   * zemine temas çizgisi bulunur; altındaki tasarım (yerde biriken kumaş) GİZLİDİR, oraya baskı yapılmaz.
#     Gizli bölgede mürekkep varsa sonuç "birikme_cozulemedi" işaretlenir (başarılı sayılmamalı).
#   * görünen asılı boy ürün boyuyla uyuşmazsa "sahne_geometri" işaretlenir.
# Tasarım hiçbir zaman kırpılıp küçültülüp ortalanmaz; oranı keyfî değiştirilmez.
# ----------------------------------------------------------------------------
# Aşağıdaki eşiklerin hepsi VARSAYIMDIR (sentetik sahnelerle seçildi; gerçek sahnelerle ayarlanmadı):
TAM_BOY_TOL = 0.03         # VARSAYIM: görünen asılı boy ürün boyundan bu oranı aşacak kadar UZUNSA sahne geometrisi uyuşmuyor
                           # (tolerans içindeki uzunluk farkı tasarımı dikeyde en fazla bu kadar sıkıştırır ve UYARI olarak yazılır)
SPREAD_FRAC = 0.04         # VARSAYIM: alt kenarda genişlik asılı kısma göre bu orandan fazla artıyorsa "birikme yayılması" var
MUREKKEP_ESIK = 0.001      # VARSAYIM: gizli bölgedeki baskılı piksel oranı bunun üstündeyse "gizli bölgede baskı var"
GIZLI_EN_FAZLA = 0.25      # VARSAYIM: yerde kalan (gizli) boy / ürün boyu bunun üstündeyse sergileme yüksekliği ürüne uymuyor
                           # (birikme miktarı uydurulmaz; bu yalnız "200 cm kumaş için stand çok kısa" sınırıdır)
KENAR_YUMUSATMA = 0.02     # VARSAYIM: kenar eğrisi Gauss yumuşatması (kumaş boyunun %2'si); satır gürültüsü kopma yapmasın
KENAR_BANT = (0.10, 0.85)  # kenar doğrularının uydurulduğu bant (asılı boyun oranı; üstteki fiyonk/toplanma ve alttaki birikme dışarıda)
KIVRIM_ESIK = 0.06         # VARSAYIM: kenarın uydurulan doğrudan sapması (p98, kumaş enine oran) bunu aşarsa güçlü kıvrım: sahne uygunsuz
KIVRIM_UYARI = 0.03        # VARSAYIM: bu ile KIVRIM_ESIK arası yalnız uyarı (kenarda yan döküm; baskı kumaşa sığıyorsa kabul)
TASMA_ESIK = 0.003         # VARSAYIM: tasarımın baskılı kısmının bu oranından fazlası kumaşın dışına düşüyorsa sahne uygunsuz
TAM_KUMAS_FOLD_SHIFT = 0.0 # Işık gradyanından kıvrım kayması tam kumaşta KAPALI (K-19): ışık gradyanı geometri değildir;
                           # gerçek sahnede tasarımı kendi üzerine katlayıp çift kontur yaptı. Güvenilir yöntem gelene dek 0.
OLCUM_PAYI = 0.005         # VARSAYIM: asılı boy ölçümünün piksel hassasiyeti (200 cm'de ≈1 cm); bu kadarlık fark sığdırılır
OLCEK_UYARI = 0.01         # dikey ölçek fiziksel ölçekten bu orandan fazla saparsa kullanıcıya uyarı yazılır


def _robust_line(x, y, iters=3):
    """y = a*x + b, aykırı noktalara dayanıklı (MAD ile ayıklayarak yeniden uydurur)."""
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    sel = np.ones(len(x), bool)
    a, b = 0.0, float(np.median(y))
    for _ in range(iters):
        if sel.sum() < 3:
            break
        a, b = np.polyfit(x[sel], y[sel], 1)
        r = y - (a * x + b)
        mad = float(np.median(np.abs(r[sel] - np.median(r[sel])))) + 0.5
        sel = np.abs(r) <= 3.0 * 1.4826 * mad + 1.0
    return float(a), float(b)


def _largest(mask):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return None
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return lab == k


def _refine_edges(prof_line, pos, win):
    """Bir kenar konumunu (piksel sınırı) çevresindeki en güçlü parlaklık basamağına alt-piksel düzeyinde taşır.
    prof_line: (N, L) gradyan büyüklükleri; pos: (N,) başlangıç sınırları. Basamak zayıfsa konum aynen kalır."""
    n, L = prof_line.shape
    out = pos.astype(np.float64).copy()
    for i in range(n):
        c = int(round(pos[i]))
        a, b = max(1, c - win), min(L - 1, c + win + 1)
        if b - a < 3:
            continue
        seg = prof_line[i, a:b]
        j = int(np.argmax(seg))
        if seg[j] < 4.0:                                 # belirgin basamak yok (8 bit gri seviye/px)
            continue
        k = a + j
        y0_, y1_, y2_ = prof_line[i, k - 1], prof_line[i, k], prof_line[i, min(k + 1, L - 1)]
        den = y0_ - 2 * y1_ + y2_
        off = 0.5 * (y0_ - y2_) / den if abs(den) > 1e-6 else 0.0
        out[i] = k + 0.5 + float(np.clip(off, -0.5, 0.5))     # gradyan k ile k+1 arasındaki sınırı ölçer
    return out


def fabric_geometry(mask, en_cm: float, boy_cm: float, tol: float = TAM_BOY_TOL, scene_bgr=None) -> dict:
    """Maskeden tam kumaş geometrisi: kenarlar, üst kenar doğrusu, ölçek, zemine temas çizgisi.
    Koordinatlar piksel SINIRLARIDIR (piksel i, [i, i+1) aralığını kaplar). scene_bgr verilirse sol/sağ/üst/alt kenarlar
    algılama maskesinden sahnedeki gerçek parlaklık basamağına alt-piksel düzeyinde inceltilir (maske kenarı bariyer nedeniyle
    birkaç piksel içeride kalabilir)."""
    m = _largest(mask > 0)
    if m is None:
        raise ValueError("kumaş maskesi boş")
    ys = np.flatnonzero(m.any(1))
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    hgt = y1 - y0
    rows = np.arange(y0, y1)
    sub = m[y0:y1]
    has = sub.any(1)
    xl = np.where(has, np.argmax(sub, 1), np.nan).astype(np.float64)
    xr = np.where(has, sub.shape[1] - np.argmax(sub[:, ::-1], 1), np.nan).astype(np.float64)   # sağ sınır (son piksel + 1)
    good = ~np.isnan(xl)
    xl = np.interp(rows, rows[good], xl[good])
    xr = np.interp(rows, rows[good], xr[good])
    gx_abs = gy_abs = None
    if scene_bgr is not None:
        g = cv2.GaussianBlur(cv2.cvtColor(scene_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
        if g.max() <= 1.0 + 1e-6:
            g = g * 255.0
        gx_abs = np.abs(np.diff(g, axis=1, append=g[:, -1:]))      # [:, k] = |g[k+1] - g[k]|
        gy_abs = np.abs(np.diff(g, axis=0, append=g[-1:, :]))
        win = max(3, int(0.012 * float(np.median(xr - xl))))
        xl = _refine_edges(gx_abs[y0:y1], xl, win)
        xr = _refine_edges(gx_abs[y0:y1], xr, win)
    k = max(5, int(0.01 * hgt)) | 1
    from scipy.ndimage import median_filter
    xl_m = median_filter(xl, size=k, mode="nearest")
    xr_m = median_filter(xr, size=k, mode="nearest")
    w = xr_m - xl_m

    # asılı kısmın referans genişliği (üstteki kurdele/çubuk ve alttaki birikmeden uzak bant)
    ref = slice(int(0.10 * hgt), max(int(0.55 * hgt), int(0.10 * hgt) + 3))
    W0 = float(np.median(w[ref]))
    px_per_cm = W0 / float(en_cm)

    # kenarlar: kumaşın GERÇEK kenarları (follow=1). Düz doğruya zorlanmaz: gerçek kumaş üstte bağla toplanabilir, kenar
    # kıvrılabilir. Bilinen sınır: fiyonk/kuyruk kumaş kenarını örterse o satırlarda tasarım örtülen kenara göre daralır.
    L, R = xl_m, xr_m
    # üst kenar: iç sütunlarda maskenin ilk satırı -> sağlam doğru
    cl, cr = float(np.median(L[ref])), float(np.median(R[ref]))
    cols = np.arange(int(cl + 0.08 * W0), int(cr - 0.08 * W0))
    cols = cols[(cols >= 0) & (cols < m.shape[1])]
    colm = m[:, cols]
    anyc = colm.any(0)
    tops = np.argmax(colm, 0).astype(np.float64)
    bots = (m.shape[0] - np.argmax(colm[::-1], 0)).astype(np.float64)       # alt sınır (son piksel + 1)
    if gy_abs is not None:
        win = max(3, int(0.006 * hgt))
        tops = _refine_edges(gy_abs[:, cols].T, tops, win)
        bots = _refine_edges(gy_abs[:, cols].T, bots, win)
    at, bt = _robust_line(cols[anyc], tops[anyc])

    # zemine temas: alt kısımda genişliğin asılı kısma göre belirgin ve sürekli artması (birikme yayılması)
    contact_row, method, birikme = None, "maske_alti", False
    lo = int(0.55 * hgt)
    hi = max(lo + 1, hgt - max(2, int(0.01 * hgt)))
    big = (w > W0 * (1 + SPREAD_FRAC)) & (w - W0 > 3)
    need = max(4, int(0.012 * hgt))
    for r in range(lo, hi):
        if big[r] and (hi - r) >= need and big[r:hi].mean() >= 0.8:
            r0 = r                                        # yayılmanın BAŞLANGICI: genişlik asılı kısma neredeyse eşit olana dek yukarı
            onset = W0 + max(2.0, 0.005 * W0)
            while r0 > lo and w[r0 - 1] > onset:
                r0 -= 1
            contact_row, method, birikme = r0, "kenar_yayilmasi", True
            break
    xs_all = np.arange(m.shape[1], dtype=np.float64)
    top_x = at * xs_all + bt
    if birikme:
        temas_x = np.full_like(xs_all, float(y0 + contact_row))
    else:
        ab, bb = _robust_line(cols[anyc], bots[anyc])
        temas_x = ab * xs_all + bb
    cxs = cols[anyc]
    asili_px = float(np.median(temas_x[cxs] - top_x[cxs]))
    asili_cm = asili_px / px_per_cm

    # Kenarların satırdan satıra gürültüsünü gider (2026-10-12 kopma düzeltmesi, K-18): her satırın kenarı ayrı ölçüldüğü
    # için birkaç piksellik sıçramalar tasarımı o satırda yatay olarak koparıyordu. Kenar, kumaş boyunca yumuşak bir eğri
    # kabul edilir: temas çizgisinin altındaki (birikme) satırlar temas satırının değeriyle sabitlenir, sonra Gauss ile
    # düzgünleştirilir. Ortalama kenar konumu (yerleşim koordinatı) değişmez; yalnız satır gürültüsü kalkar.
    from scipy.ndimage import gaussian_filter1d
    L_ham, R_ham = L, R
    ci = int(np.clip(round(float(np.median(temas_x[cxs])) - y0), 1, len(L) - 1))
    Lc, Rc = L.copy(), R.copy()
    Lc[ci:], Rc[ci:] = L[ci - 1], R[ci - 1]
    sig = max(3.0, KENAR_YUMUSATMA * hgt)
    L = gaussian_filter1d(Lc, sig, mode="nearest")
    R = gaussian_filter1d(Rc, sig, mode="nearest")
    return {"mask": m, "y0": y0, "y1": y1, "rows": rows, "L": L, "R": R, "L_ham": L_ham, "R_ham": R_ham,
            "kenar_sigma_px": sig, "W0": W0, "px_per_cm": px_per_cm,
            "top_line": (at, bt), "top_x": top_x, "temas_x": temas_x, "temas_y": float(np.median(temas_x[cxs])),
            "birikme": birikme, "temas_yontemi": method, "asili_px": asili_px, "asili_cm": asili_cm,
            "x_range": (int(np.floor(min(L.min(), cl))), int(np.ceil(max(R.max(), cr))))}


def _place_full_fabric(scene, design, det, ink, paper, ssaa, fold_shift, en_cm, boy_cm, tol):
    H, W = scene.shape[:2]
    g = fabric_geometry(det.mask, en_cm, boy_cm, tol, scene_bgr=scene)
    m = g["mask"]
    ppc, asili_cm = g["px_per_cm"], g["asili_cm"]
    boy_px = boy_cm * ppc
    sorunlar, uyarilar = [], []
    olcek_farki = asili_cm / boy_cm - 1.0
    # Dikey ölçek politikası (Aşama 2A, bağımsız inceleme sonrası):
    #   * asılı kısım ürün boyundan KISA ise ölçek FİZİKSELDİR: tasarım sıkıştırılıp yukarı taşınmaz; görünmeyen alt kısım
    #     (yerde kalan kumaş) gizli bölge sayılır ve mürekkep denetimine girer.
    #   * asılı kısım ürün boyundan biraz UZUN ise (<= TAM_BOY_TOL) sahne ölçüm/çizim payı kabul edilir; tasarım temas
    #     çizgisine sığdırılır (dikeyde en fazla TAM_BOY_TOL sıkışma) ve bu UYARI olarak yazılır. Daha uzunsa sahne reddedilir.
    fit_to_contact = False
    if asili_cm > boy_cm * (1 + tol):
        sorunlar.append({"tur": "sahne_geometri",
                         "mesaj": f"Sahnedeki kumaş ürün boyundan uzun görünüyor: asılı kısım ≈{asili_cm:.0f} cm, ürün {boy_cm:g} cm "
                                  f"(en {en_cm:g} cm'ye göre). Sahne ürün geometrisine uymuyor."})
        fit_to_contact = True
    elif asili_cm > boy_cm or abs(olcek_farki) <= OLCUM_PAYI:
        fit_to_contact = True                      # ölçüm payı içindeki fark (≈1 cm) ölçüm hatası sayılır; olcek_farki rapora yazılır
        if olcek_farki > OLCEK_UYARI:
            uyarilar.append(f"Sahnedeki kumaş ürün boyundan ≈%{olcek_farki * 100:.1f} uzun çizilmiş (≈{asili_cm:.0f} cm); tasarım "
                            f"kumaşın görünen boyuna sığdırıldı, dikeyde ≈%{olcek_farki * 100:.1f} sıkıştı. Gözle kontrol edin.")
    if not fit_to_contact and (1.0 - asili_cm / boy_cm) > GIZLI_EN_FAZLA:
        sorunlar.append({"tur": "sahne_geometri",
                         "mesaj": f"Kumaşın görünen asılı boyu (≈{asili_cm:.0f} cm) ürün boyuna ({boy_cm:g} cm) göre çok kısa: "
                                  f"yaklaşık {boy_cm - asili_cm:.0f} cm yerde kalıyor ya da kumaş havada bitiyor. Sergileme yüksekliği ürüne uymuyor."})
    if not fit_to_contact and not g["birikme"] and asili_cm < boy_cm * (1 - tol):
        # zemin algılaması yok: yana yayılan birikme görünmeden kumaş belirgin kısa ise havada bitiyor olabilir -> temkinli ret
        sorunlar.append({"tur": "sahne_geometri",
                         "mesaj": f"Kumaşın görünen boyu ürün boyundan kısa (≈{asili_cm:.0f} cm < {boy_cm:g} cm) ve altta birikme görünmüyor: "
                                  f"kumaş havada bitiyor ya da sahne ürünü kısa çizmiş."})
    elif not fit_to_contact and not g["birikme"] and asili_cm < boy_cm:
        uyarilar.append(f"Kumaşın görünen boyu ürün boyundan ≈{boy_cm - asili_cm:.0f} cm kısa; kalan kısım zemine değen kenarda "
                        f"(görünmeyen) kabul edildi, tasarım sıkıştırılmadı.")
    v_gizli = 1.0 if fit_to_contact else min(1.0, asili_cm / boy_cm)
    gizli_cm = (1.0 - v_gizli) * boy_cm

    x0, x1 = max(0, g["x_range"][0] - 4), min(W, g["x_range"][1] + 5)
    y0, y1 = max(0, g["y0"] - 4), min(H, g["y1"] + 5)
    gx, gy = np.meshgrid((np.arange(x0 * ssaa, x1 * ssaa) + 0.5) / ssaa, (np.arange(y0 * ssaa, y1 * ssaa) + 0.5) / ssaa)

    # kıvrım kayması: yalnız kumaşın İÇİNDEKİ ışık değişiminden (kenar/duvar karşıtlığı kaydırma yaratmasın)
    # --- Tasarım BÜTÜN olarak TEK düzlem dönüşümüyle (homografi) yerleşir (K-23, 2026-10-13) ---
    # Kumaşın satır satır kenarları ve ışık gradyanı tasarımın iç geometrisini DEĞİŞTİRMEZ: kenarlara sağlam düz çizgiler
    # uydurulur, üst kenar ve zemine temas çizgisiyle bir dörtgen kurulur; PNG tuvalinin tamamı bu dörtgene tek
    # perspektif dönüşümüyle oturur. Önden sahnede (paralel kenarlar) bu, oranı koruyan ölçekleme olur; açılı sahnede
    # tasarımın tamamına aynı perspektif uygulanır. Işık, gölge ve doku çarpma baskı modeliyle gelir.
    # fold_shift (ışık gradyanından kayma) tam kumaşta KULLANILMAZ (K-19).
    rows = g["rows"]
    Lh, Rh = np.asarray(g["L_ham"], np.float64), np.asarray(g["R_ham"], np.float64)
    at, bt = g["top_line"]
    xs_all = np.arange(W, dtype=np.float64)
    tem_line = np.polyfit(xs_all, g["temas_x"], 1)                     # temas çizgisi (birikmede yatay)
    ac, bc = float(tem_line[0]), float(tem_line[1])
    top_mid = float(np.median(g["top_x"][int(g["x_range"][0]):int(g["x_range"][1])]))
    hang_px = max(g["temas_y"] - top_mid, 10.0)
    band = (rows >= top_mid + KENAR_BANT[0] * hang_px) & (rows <= top_mid + KENAR_BANT[1] * hang_px)
    if band.sum() < 10:
        band = np.ones(len(rows), bool)
    aL, bL = _robust_line(rows[band], Lh[band])                       # x = aL*y + bL
    aR, bR = _robust_line(rows[band], Rh[band])
    resid = max(float(np.percentile(np.abs(Lh[band] - (aL * rows[band] + bL)), 98)),
                float(np.percentile(np.abs(Rh[band] - (aR * rows[band] + bR)), 98)))

    def side_top(a, b):                                                 # yan çizgi ile üst kenar doğrusunun kesişimi
        y = (at * b + bt) / (1 - at * a)
        return a * y + b, y

    def side_y(a, b, k, c):                                             # yan çizgi ile y = k*x + c doğrusunun kesişimi
        y = (k * b + c) / (1 - k * a)
        return y

    xtl, ytl = side_top(aL, bL)
    xtr, ytr = side_top(aR, bR)
    ycl, ycr = side_y(aL, bL, ac, bc), side_y(aR, bR, ac, bc)          # temas çizgisinde yanlar
    ratio = 1.0 if fit_to_contact else (boy_px / hang_px)             # temasın altı (yerde biriken kısım) fiziksel ölçekle
    ybl, ybr = ytl + (ycl - ytl) * ratio, ytr + (ycr - ytr) * ratio
    quad = np.float64([[xtl, ytl], [xtr, ytr], [aR * ybr + bR, ybr], [aL * ybl + bL, ybl]])
    Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), quad.astype(np.float32))
    Hi = np.linalg.inv(Hm)
    den = Hi[2, 0] * gx + Hi[2, 1] * gy + Hi[2, 2]
    u = (Hi[0, 0] * gx + Hi[0, 1] * gy + Hi[0, 2]) / den
    v = (Hi[1, 0] * gx + Hi[1, 1] * gy + Hi[1, 2]) / den
    temp = ac * gx + bc
    inside = ((u >= 0) & (u <= 1) & (v >= 0) & (v <= 1) & (gy <= temp)).astype(np.float32)
    Lv = float(max(ybl - ytl, ybr - ytr))
    reg_w, reg_h = g["W0"], float(np.max(Lv)) if np.ndim(Lv) else float(Lv)
    design_s = _prefit(design, reg_w * ssaa, reg_h * ssaa)
    dh, dw = design_s.shape[:2]
    warped = cv2.remap(design_s, (u * dw - 0.5).astype(np.float32), (v * dh - 0.5).astype(np.float32),
                       cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    sz = (x1 - x0, y1 - y0)
    warped = np.clip(cv2.resize(warped, sz, interpolation=cv2.INTER_AREA), 0, 1)
    alpha = cv2.resize(inside, sz, interpolation=cv2.INTER_AREA)
    # --- sığma denetimi: güçlü kıvrım/katlanma varsa tasarım ZORLA deforme edilmez, sahne uygunsuz sayılır ---
    lum_d = 0.114 * warped[..., 0] + 0.587 * warped[..., 1] + 0.299 * warped[..., 2]
    ink_w = (lum_d < 0.85) & (alpha > 0.5)                              # tasarımın baskılı (mürekkepli) kısmı, sahnede
    m_tol = cv2.dilate(m[y0:y1, x0:x1].astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    ink_total = int(ink_w.sum())
    ink_out = float((ink_w & ~m_tol).sum()) / max(ink_total, 1)
    kivrim = resid / max(g["W0"], 1.0)
    if KIVRIM_UYARI < kivrim <= KIVRIM_ESIK and ink_out <= TASMA_ESIK:
        uyarilar.append(f"Kumaş kenarında belirgin döküm/kıvrım var (kenar sapması %{kivrim * 100:.1f} en); tasarım düzlem olarak "
                        f"yerleşti ve kumaşa sığıyor. Gözle kontrol edin.")
    if kivrim > KIVRIM_ESIK or ink_out > TASMA_ESIK:
        sorunlar.append({"tur": "sahne_kivrim",
                         "mesaj": f"Kumaş yüzeyi tasarımı bozmadan taşıyacak kadar düz değil (kenar sapması %{kivrim * 100:.1f} en, "
                                  f"kumaş dışına düşen baskı %{ink_out * 100:.2f}). Tasarım zorla deforme edilmedi; sahne uygunsuz."})
    mf = cv2.GaussianBlur(m[y0:y1, x0:x1].astype(np.float32), (0, 0), 0.6)
    alpha = np.clip(alpha * mf, 0, 1)[..., None]

    region = scene[y0:y1, x0:x1]
    out = scene.copy()
    out[y0:y1, x0:x1] = _apply_print(region, warped, alpha, ink, paper)

    # gizli bölgede baskı var mı? (yerde biriken kumaşın altındaki tasarım)
    ink_hidden = 0.0
    if v_gizli < 1.0 and not any(s["tur"] == "sahne_geometri" for s in sorunlar):     # geometri zaten uymuyorsa ikinci neden eklenmez
        import product
        d8 = (np.clip(design, 0, 1) * 255 + 0.5).astype(np.uint8)
        ink_hidden = float(product.murekkep_orani(d8, v_gizli))
        if ink_hidden > MUREKKEP_ESIK:
            sorunlar.append({"tur": "birikme_cozulemedi",
                             "mesaj": f"Tasarımın alt ≈{gizli_cm:.0f} cm'si zeminde biriken kumaşta kalıyor ve bu bölgede baskı var "
                                      f"(%{ink_hidden * 100:.1f}). Birikmedeki kıvrımlar üzerinde baskı doğru çizilemediği için "
                                      f"bu sahne başarılı sayılmadı."})
        else:
            uyarilar.append(f"Tasarımın alt ≈{gizli_cm:.0f} cm'si zeminde birikiyor; bu bölgede baskı yok.")
        if gizli_cm > 0.15 * boy_cm:
            uyarilar.append(f"Zemindeki birikme büyük görünüyor (≈{gizli_cm:.0f} cm); sahneyi gözle kontrol edin.")

    model = {"bbox": [int(x0), int(y0), int(x1), int(y1)],
             "u": cv2.resize(u.astype(np.float32), sz, interpolation=cv2.INTER_AREA),
             "v": cv2.resize(v.astype(np.float32), sz, interpolation=cv2.INTER_AREA),
             "alpha": alpha[..., 0].astype(np.float32)}
    at, bt = g["top_line"]
    info = {"bbox": [int(x0), int(y0), int(x1), int(y1)], "mod": "tam_kumas",
            "kivrim_kaymasi": 0.0, "kenar_sigma_px": round(float(g["kenar_sigma_px"]), 1),
            "yerlesim_donusumu": "homografi", "dortgen": [[round(float(a_), 1) for a_ in q_] for q_ in quad],
            "kenar_sapmasi": round(float(kivrim), 4), "kumas_disi_baski": round(float(ink_out), 5),
            "en_cm": float(en_cm), "boy_cm": float(boy_cm),
            "px_per_cm": round(ppc, 3), "asili_cm": round(asili_cm, 1), "gizli_cm": round(gizli_cm, 1),
            "v_gizli": round(v_gizli, 4), "temas_y": round(g["temas_y"], 1), "birikme": bool(g["birikme"]),
            "temas_yontemi": g["temas_yontemi"], "olcek_farki": round(olcek_farki, 4),
            "dikey_olcek": "temas_cizgisine_kadar" if fit_to_contact else "fiziksel",
            "ust_kenar": [round(at, 5), round(bt, 2)], "genislik_px": round(g["W0"], 1),
            "gizli_murekkep": round(ink_hidden, 5), "sorunlar": sorunlar, "uyarilar": uyarilar}
    return out, info, model


# ----------------------------------------------------------------------------
def composite(scene_bgr, design, det, *, paper="auto", ink=None, ssaa=2,
              follow=0.3, inset=0.10, fold_shift=None, sag=0.02, return_model=False,
              mode=None, profile=None, tol=TAM_BOY_TOL):
    """scene_bgr uint8, design float32 BGR [0,1]. Sonuç (uint8 BGR, bilgi sözlüğü).

    mode=None (eski çağrılar): det.kind'a göre sert (homografi) ya da eski kumaş yolu (inset/pay ile "contain").
    mode="tam_kumas": profile (product.UrunProfili; en_cm/boy_cm) zorunlu. PNG tuvali = kumaşın tamamı; kenar payı, içeri alma,
      kırpma yok; dikey ölçek fiziksel. det.kind yok sayılır (sert görünen sahnede de kumaş yolu). info["sorunlar"] boş değilse
      sonuç başarılı sayılmamalıdır (tur: "sahne_geometri" | "birikme_cozulemedi").

    return_model=True ise üçüncü eleman olarak "baskı modeli" döner: video onarımının ihtiyaç duyduğu
    {bbox, u, v, alpha, paper, ink}. u,v: bölge pikseli -> tasarım koordinatı (0-1), alpha: baskı kapsaması.
    """
    scene = scene_bgr.astype(np.float32) / 255.0
    p = estimate_paper(design) if paper == "auto" else paper
    if mode == "tam_kumas":
        if profile is None:
            raise ValueError("tam_kumas modu ürün profili ister (en_cm, boy_cm)")
        ink_v = 0.93 if ink is None else ink
        fs = TAM_KUMAS_FOLD_SHIFT if fold_shift is None else fold_shift
        out, info, model = _place_full_fabric(scene, design, det, ink_v, p, ssaa, fs,
                                              float(profile.en_cm), float(profile.boy_cm), tol)
        info["paper"] = None if p is None else [round(float(v), 3) for v in p]
        model.update(paper=p, ink=float(ink_v), kind="fabric")
        img = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
        return (img, info, model) if return_model else (img, info)
    if mode not in (None, "eski"):
        raise ValueError(f"bilinmeyen yerleşim modu: {mode!r}")
    ink_v = (1.0 if det.kind == "rigid" else 0.93) if ink is None else ink
    if det.kind == "rigid":
        out, info, model = _place_rigid(scene, design, det, ink_v, p, ssaa)
    else:
        out, info, model = _place_fabric(scene, design, det, ink_v, p, ssaa, follow, inset,
                                         0.01 if fold_shift is None else fold_shift, sag)     # eski yol: davranış aynı
    info["paper"] = None if p is None else [round(float(v), 3) for v in p]
    model.update(paper=p, ink=float(ink_v), kind=det.kind)
    img = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
    return (img, info, model) if return_model else (img, info)

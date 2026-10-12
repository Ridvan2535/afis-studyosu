# -*- coding: utf-8 -*-
"""
İnsanlı sahne videosu: "yapay zekâ videosu + kodla yerleştirilen tasarım + kodla el kamerası".

Neden böyle? Yapay zekâ video modelleri insanları ve ortam hareketini iyi üretir, ama yazıyı bozar ve kamerayı
gerçek bir el kamerası gibi sallayamaz. Bu yüzden iş bölünür:

  1) Yapay zekâya TASARIMSIZ (boş afişli) sahne verilir; "kamera sabit, sadece arka plandaki insanlar yavaş
     hareket eder" istenir.  (Yazı yoktur, bozulacak bir şey de yok.)
  2) Gelen videodaki küçük kamera kayması bulunup kare kare giderilir (stabilizasyon).
  3) Tasarım, ilk karedeki afiş modeline göre HER KAREYE çarpılarak basılır (kumaşın ışığı/kıvrımı o karenin
     kendi piksellerinden geldiği için baskı kumaşın üstünde doğal durur). Afişin kendi hafif kaymasını ve
     önüne geçen bir şey (el, kişi) varsa onu algılar, baskıyı o piksellerde bastırır.
  4) En sonda, fotoğraf videosundaki aynı fiziksel "yürüyen el" kamerası tüm kareye uygulanır.

Her adımın ölçülebilir bir kalite kontrolü var; geçmezse çağıran taraf güvenli kamera videosuna döner.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

import banner_detect as bd
import camera_move as cm
import compositor as cp
import video_repair as vr

GRAY_LONG = 640


# ----------------------------------------------------------------------------
# 1) kamera kayması
# ----------------------------------------------------------------------------
def _gray(f, long_side=GRAY_LONG):
    s = min(1.0, long_side / max(f.shape[:2]))
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    if s < 1:
        g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return g, s


def _fit_sim(p_from, p_to, thr):
    """p_from -> p_to benzerlik dönüşümü (öteleme+ölçek+dönme), RANSAC. (3x3, inlier sayısı)."""
    if len(p_from) < 8:
        return None, 0
    A, inl = cv2.estimateAffinePartial2D(p_from, p_to, method=cv2.RANSAC, ransacReprojThreshold=thr,
                                         maxIters=2000, confidence=0.995)
    if A is None or inl is None:
        return None, 0
    M = np.vstack([A, [0, 0, 1.0]])
    return M, int(inl.sum())


def _track(g_a, g_b, pts, init=None, back_tol=0.8):
    lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    if init is None:
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(g_a, g_b, pts, None, **lk)
    else:
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(g_a, g_b, pts, init.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
    back, st2, _ = cv2.calcOpticalFlowPyrLK(g_b, g_a, nxt, None, **lk)
    ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.linalg.norm(back - pts, axis=2).ravel() < back_tol)
    return pts[ok].reshape(-1, 2), nxt[ok].reshape(-1, 2)


def estimate_motion(grays, thr=1.2, smooth=1.2):
    """Her kare için (kare -> ilk kare) benzerlik dönüşümü (küçük gri görüntü koordinatlarında) ve istatistikler.

    Zincir (t-1 -> t) küçük kaymaları yakalar, ardından ilk kareye doğrudan çapa ile sürüklenme düzeltilir.
    Hareketli insanlar RANSAC'ta aykırı değer sayılır (arka plan çoğunluktaysa)."""
    n = len(grays)
    g0 = grays[0]
    pts0 = cv2.goodFeaturesToTrack(g0, 900, 0.01, 7, blockSize=7)
    Hs = [np.eye(3)]
    inliers = [0]
    anchored = [True]
    for t in range(1, n):
        prev, cur = grays[t - 1], grays[t]
        pts = cv2.goodFeaturesToTrack(prev, 800, 0.01, 7, blockSize=7)
        M_rel, inl = None, 0
        if pts is not None and len(pts) >= 12:
            a, b = _track(prev, cur, pts)
            M_rel, inl = _fit_sim(b, a, thr)                       # cur -> prev
        H_chain = Hs[-1] @ (M_rel if (M_rel is not None and inl >= 10) else np.eye(3))
        H_use, inl_use, anch = H_chain, inl, False
        if pts0 is not None and len(pts0) >= 12:
            init = cv2.perspectiveTransform(pts0.reshape(-1, 1, 2).astype(np.float64), np.linalg.inv(H_chain)).astype(np.float32)
            a, b = _track(g0, cur, pts0, init=init)
            M_d, inl_d = _fit_sim(b, a, thr)                       # cur -> ilk kare
            if M_d is not None and inl_d >= 20:
                H_use, inl_use, anch = M_d, inl_d, True
        Hs.append(H_use)
        inliers.append(inl_use)
        anchored.append(anch)
    P = np.array([[h[0, 0], h[1, 0], h[0, 2], h[1, 2]] for h in Hs])      # a, b, tx, ty (a=s·cosθ, b=s·sinθ)
    if smooth > 0 and n > 3:
        P = gaussian_filter1d(P, smooth, axis=0, mode="nearest")
        P = P - (P[0] - np.array([1.0, 0.0, 0.0, 0.0]))                 # ilk kare tam referans kalsın
    out = []
    for a, b, tx, ty in P:
        out.append(np.array([[a, -b, tx], [b, a, ty], [0, 0, 1.0]]))
    return out, {"inliers": np.array(inliers[1:]) if n > 1 else np.array([0]), "anchored": float(np.mean(anchored)),
                 "tx": P[:, 2], "ty": P[:, 3], "scale": np.hypot(P[:, 0], P[:, 1]),
                 "rot": np.degrees(np.arctan2(P[:, 1], P[:, 0]))}


# ----------------------------------------------------------------------------
# 2) baskı katmanı
# ----------------------------------------------------------------------------
def build_print_layer(model, design, soften=0.0, ss=2):
    """compositor modelinden 'çarpan haritası' üretir: baskılı kare = kare × mul (bbox içinde)."""
    x0, y0, x1, y1 = model["bbox"]
    u, v, alpha = model["u"], model["v"], model["alpha"]
    h, w = alpha.shape
    dh, dw = design.shape[:2]
    core = alpha > 0.5
    if core.sum() > 50:
        sx = np.median(np.abs(np.gradient(u, axis=1))[core]) * (dw - 1) / ss
        sy = np.median(np.abs(np.gradient(v, axis=0))[core]) * (dh - 1) / ss
        s = max(sx, sy)
    else:
        s = 1.0
    if s > 1.25:
        design = cv2.resize(design, (max(2, int(dw / s)), max(2, int(dh / s))), interpolation=cv2.INTER_AREA)
        dh, dw = design.shape[:2]
    uu = cv2.resize(u, None, fx=ss, fy=ss, interpolation=cv2.INTER_LINEAR)
    vv = cv2.resize(v, None, fx=ss, fy=ss, interpolation=cv2.INTER_LINEAR)
    warped = cv2.remap(design, (uu * (dw - 1)).astype(np.float32), (vv * (dh - 1)).astype(np.float32),
                       cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    warped = cv2.resize(warped, (w, h), interpolation=cv2.INTER_AREA)
    paper = model.get("paper")
    d = warped if paper is None else np.clip(warped / np.asarray(paper, np.float32)[None, None, :], 0, 1)
    d = 1.0 - float(model.get("ink", 1.0)) * (1.0 - d)
    mul = 1.0 - alpha[..., None] * (1.0 - d)
    if soften > 0.05:
        mul = cv2.GaussianBlur(mul, (0, 0), soften)
    return np.ascontiguousarray(mul, dtype=np.float32)


def _lum(img):
    return img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299


# ----------------------------------------------------------------------------
# 3) ana akış
# ----------------------------------------------------------------------------
class CompositeError(Exception):
    pass


def analyse(video_path):
    """1. geçiş: küçük gri kareler + kamera kayması. (grays, s, motion, stats, info)"""
    grays, s, n = [], 1.0, 0
    first = None
    for f in vr.iter_video(video_path):
        if first is None:
            first = f.shape[:2]
        g, s = _gray(f)
        grays.append(g)
        n += 1
    if n < 8:
        raise CompositeError("video çok kısa ya da okunamadı")
    Ms, st = estimate_motion(grays)
    return grays, s, Ms, st, first


def frame_stream(video_path, design, *, ref_frames=5, soften_scale=0.45, progress=None, motion=None):
    """Stabilize edilmiş + baskılı kareleri üretir (el kamerası EKLENMEMİŞ). Her adımda (kare, bilgi).
    Sonunda özet için `frame_stream.summary` kullanılmaz; bilgi listesi çağırana verilir (compose_video)."""
    if motion is None:
        motion = analyse(video_path)
    grays, s, Ms, st, (H, W) = motion
    # çalışma boyutu: uzun kenar 1920'ye (küçükse) büyütülür, çift sayı
    f_up = min(2.0, max(1.0, 1920 / max(H, W)))
    ww, wh = int(round(W * f_up)) // 2 * 2, int(round(H * f_up)) // 2 * 2
    # kadraj kırpma: kare kayması yüzünden kenarlarda geçersiz alan kalır; ortak geçerli dikdörtgen
    lo, hi = np.zeros(2), np.array([float(W), float(H)])
    corners = np.array([[0, 0, 1], [W, 0, 1], [W, H, 1], [0, H, 1]], float).T
    for M in Ms:
        Mf = np.diag([1 / s, 1 / s, 1.0]) @ M @ np.diag([s, s, 1.0])
        p = (Mf @ corners)[:2].T
        lo = np.maximum(lo, [p[[0, 3], 0].max(), p[[0, 1], 1].max()])
        hi = np.minimum(hi, [p[[1, 2], 0].min(), p[[2, 3], 1].min()])
    crop = (float(lo[0]), float(lo[1]), float(hi[0] - lo[0]), float(hi[1] - lo[1]))
    crop_frac = 1 - (crop[2] * crop[3]) / (W * H)
    if crop[2] < 0.6 * W or crop[3] < 0.6 * H:
        raise CompositeError("kamera videoda çok oynamış (kadrajın büyük kısmı kaybolur)")
    # kırpma en-boy oranını korur: ortak geçerli dikdörtgenin içinde, aynı oranlı en büyük pencere
    zc = max(W / crop[2], H / crop[3])
    if crop_frac < 0.004:
        cx, cy, cw, ch = 0.0, 0.0, float(W), float(H)
    else:
        cw, ch = W / zc, H / zc
        cx = min(max(crop[0] + crop[2] / 2 - cw / 2, crop[0]), crop[0] + crop[2] - cw)
        cy = min(max(crop[1] + crop[3] / 2 - ch / 2, crop[1]), crop[1] + crop[3] - ch)
    # tek örneklemede: kare -> (ilk kare koordinatı) -> kırp -> çalışma boyutuna ölçekle
    T_crop = np.array([[ww / cw, 0, -cx * ww / cw], [0, wh / ch, -cy * wh / ch], [0, 0, 1.0]])

    def warp_matrix(i):
        Mf = np.diag([1 / s, 1 / s, 1.0]) @ Ms[i] @ np.diag([s, s, 1.0])        # kare px -> ilk kare px
        return (T_crop @ Mf)[:2]

    n = len(Ms)
    stab = lambda f, i: cv2.warpAffine(f, warp_matrix(i), (ww, wh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # --- referans kare: ilk birkaç stabilize karenin medyanı (arkada yürüyen insanlar silinir) ---
    refs = []
    for i, f in enumerate(vr.iter_video(video_path)):
        refs.append(stab(f, i))
        if len(refs) >= ref_frames:
            break
    ref = np.median(np.stack(refs), axis=0).astype(np.uint8) if len(refs) > 2 else refs[0]
    det = bd.detect(ref)
    if not det.ok:
        raise CompositeError("videonun ilk karesinde afiş bulunamadı: " + "; ".join(det.reject))
    why = cp.check_fit(det, design)
    if why:
        raise CompositeError("tasarım videodaki afişe uymadı: " + str(why))
    first_out, info0, model = cp.composite(ref, design, det, return_model=True)
    x0, y0, x1, y1 = model["bbox"]
    soften = soften_scale * max(0.0, f_up - 1.0) + (0.25 if f_up > 1.0 else 0.0)
    mul0 = build_print_layer(model, design, soften=soften)
    bh, bw = mul0.shape[:2]
    core = model["alpha"] > 0.5
    L0 = cv2.GaussianBlur(_lum(ref[y0:y1, x0:x1].astype(np.float32) / 255.0), (0, 0), 2.0)
    pad = 24
    gx0, gy0, gx1, gy1 = max(0, x0 - pad), max(0, y0 - pad), min(ww, x1 + pad), min(wh, y1 + pad)

    def edge_img(img):
        g = cv2.GaussianBlur(cv2.cvtColor(img[gy0:gy1, gx0:gx1], cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.5)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        return cv2.magnitude(gx, gy)

    E0 = edge_img(ref)
    win = cv2.createHanningWindow((E0.shape[1], E0.shape[0]), cv2.CV_32F)
    info_list = []
    shifts = []
    ncore = max(int(core.sum()), 1)

    # --- afişin kendi kayması (kare başına), önce hepsi ölçülür ve yumuşatılır ---
    raw = []
    for i, f in enumerate(vr.iter_video(video_path)):
        fs = stab(f, i)
        (dx, dy), resp = cv2.phaseCorrelate(E0, edge_img(fs), win)
        raw.append((dx, dy, resp))
    raw = np.array(raw)
    ok = raw[:, 2] > 0.05
    sh = raw[:, :2].copy()
    sh[~ok] = 0.0
    sh = gaussian_filter1d(sh, 2.0, axis=0, mode="nearest")
    sh = np.clip(sh, -0.02 * ww, 0.02 * ww)

    for i, f in enumerate(vr.iter_video(video_path)):
        if i >= n:
            break
        fs = stab(f, i)
        dx, dy = float(sh[i, 0]), float(sh[i, 1])
        Ms_ = np.float32([[1, 0, dx], [0, 1, dy]])
        mul = cv2.warpAffine(mul0, Ms_, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1.0)
        region = fs[y0:y1, x0:x1].astype(np.float32) / 255.0
        # önüne giren nesne / ani değişim: kaydırılmış referansla karşılaştır
        L0s = cv2.warpAffine(L0, Ms_, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        Lt = cv2.GaussianBlur(_lum(region), (0, 0), 2.0)
        ratio = Lt[core] / np.maximum(L0s[core], 1e-3) if core.any() else np.array([1.0])
        gain = float(np.clip(np.median(ratio), 0.7, 1.4))
        dev = np.abs(Lt - gain * L0s)
        occl = (dev > 0.075).astype(np.uint8)
        occl = cv2.morphologyEx(occl, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        occl_core = float(occl[core].sum()) / ncore if core.any() else 0.0
        soft = cv2.GaussianBlur(cv2.dilate(occl, np.ones((11, 11), np.uint8)).astype(np.float32), (0, 0), 3.0)
        soft = np.clip(soft * 1.4, 0, 1)[..., None]
        mul_t = 1.0 - (1.0 - mul) * (1.0 - soft)
        out = fs.copy()
        out[y0:y1, x0:x1] = np.clip(region * mul_t * 255.0 + 0.5, 0, 255).astype(np.uint8)
        info_list.append({"frame": i, "dx": dx, "dy": dy, "occl": occl_core, "gain": gain})
        yield out, info_list[-1]
        if progress and i % 8 == 0:
            progress(i + 1, n)
    frame_stream.last = {"motion": st, "crop_frac": crop_frac, "size": (ww, wh), "f_up": f_up,
                         "first_out": first_out, "kind": det.kind, "shift_resp_ok": float(ok.mean())}


def summarize(infos, st, extra, *, inl_min=14, crop_max=0.06, shift_max=0.012, occl_max=0.12, anch_min=0.6):
    inl = st["inliers"]
    reasons = []
    low = float((inl < inl_min).mean())
    if low > 0.05:
        reasons.append(f"kamera kayması güvenilir ölçülemedi (%{low * 100:.0f} karede yeterli sabit nokta yok)")
    if extra["crop_frac"] > crop_max:
        reasons.append(f"yapay zekâ kamerayı oynattı (kadrajın %{extra['crop_frac'] * 100:.0f}'i kayboluyor)")
    dx = np.array([i["dx"] for i in infos]); dy = np.array([i["dy"] for i in infos])
    ww = extra["size"][0]
    mx = float(max(np.abs(dx).max(), np.abs(dy).max()))
    if mx > shift_max * ww:
        reasons.append(f"afiş arka plana göre fazla kaydı (en çok {mx:.0f} px)")
    oc = np.array([i["occl"] for i in infos])
    if oc.max() > occl_max:
        reasons.append(f"afişin önüne bir şey girdi ya da afiş görüntüsü fazla değişti (en çok %{oc.max() * 100:.0f})")
    # kalite puanı (0-100): kapıdan geçen videolar arasında hangisinin daha temiz olduğunu söyler (servis karşılaştırması için)
    pen = (min(mx / max(shift_max * ww, 1e-6), 1.0) * 30 + min(extra["crop_frac"] / max(crop_max, 1e-6), 1.0) * 25
           + min(float(oc.max()) / max(occl_max, 1e-6), 1.0) * 25 + min(low / 0.05, 1.0) * 10
           + min(float(np.abs(st["rot"]).max()) / 2.0, 1.0) * 5 + min(float(np.abs(st["scale"] - 1).max()) / 0.06, 1.0) * 5)
    kalite = round(max(0.0, 100.0 - pen), 1)
    return {"ok": not reasons, "reasons": reasons, "kalite": kalite, "inl_med": float(np.median(inl)) if len(inl) else 0.0,
            "inl_low_frac": low, "crop_frac": float(extra["crop_frac"]), "shift_max_px": mx,
            "occl_max": float(oc.max()), "occl_mean": float(oc.mean()), "frames": len(infos),
            "anchored": float(st["anchored"]), "rot_max_deg": float(np.abs(st["rot"]).max()),
            "scale_dev": float(np.abs(st["scale"] - 1).max())}


def compose_video(video_in, out_path, design, *, move="yakinlas", handheld="yuruyus", seed=11, progress=None,
                  strength=1.0):
    """AI videosu -> stabilize + baskı + el kamerası -> out_path. (özet, bilgi listesi) döner.
    Özet 'ok' False ise çağıran güvenli yedeğe geçmelidir (dosya yine de yazılır, inceleme için)."""
    motion = analyse(video_in)
    fps = vr.video_info(video_in)["fps"] or 24.0
    k = cm.level_value(handheld)
    # yapay zekâ videosunun kareleri düşük çözünürlüklü: yaklaşma en fazla ~1.8 kat (daha fazlası yazıyı bulanıklaştırır)
    zpk = max((cm.MOVES.get(move) or cm.MOVES["yakinlas"])["z"]) - 1.0
    if zpk > 0.8:
        strength = min(strength, 0.8 / zpk)
    rig = None
    sink = None
    infos = []
    try:
        for fr, info in frame_stream(video_in, design, progress=(lambda i, n: progress(i, n * 2)) if progress else None,
                                     motion=motion):
            if rig is None:
                n = len(motion[2])
                H, W = fr.shape[:2]
                rig = cm.CameraRig(W, H, W, H, n / fps, fps, move, intensity=k, strength=strength, seed=seed)
                sink = vr.make_sink(out_path, float(fps), crf=17)
            infos.append(info)
            sink.write(rig.render_frame(fr, len(infos) - 1))
            if progress and len(infos) % 8 == 0:
                progress(len(motion[2]) + len(infos), len(motion[2]) * 2)
        if sink is None:
            raise CompositeError("video kare üretmedi")
        sink.close()
    except BaseException:
        if sink is not None:
            sink.abort()
        raise
    extra = dict(frame_stream.last)
    return summarize(infos, motion[3], extra), infos

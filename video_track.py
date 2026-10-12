# -*- coding: utf-8 -*-
"""
Hareketli kameralı yapay zekâ videosu + kodla yerleştirilen tasarım.

Fark (video_composite.py'den): orada yapay zekâ videosu SABİT kameralıdır ve kamera hareketi sonradan kodla verilir
(düz bir fotoğrafa yaklaşıyormuş gibi görünür). Burada kamerayı yapay zekâ modelinin kendisi hareket ettirir:
yaklaşma, yay çizerek sağa dönme, kurdelelerin uçuşması, koşan çocuklar, değişen arka plan hepsi videonun GERÇEK
içeriğidir. Kod yalnızca tasarımı basar:

  1) İlk karede afiş bulunur, tasarım tek seferde basılır (compositor) ve çarpım (multiply) katmanı çıkarılır.
  2) Afişin bulunduğu düzlem (afiş + çerçeve dikmeleri + üst çubuk) kare kare izlenir (optik akış + RANSAC homografi,
     ilk kareye karşı ECC ile sürüklenme düzeltmesi). Böylece yaklaşma ve yay dönüşündeki perspektif değişimi baskıya geçer.
  3) Baskı her karede o karenin kendi piksellerine çarpılır (kumaşın ışığı ve kıvrımı korunur).
  4) Afişin önüne giren her şey (kurdele ucu, el, kişi) ilk kareyle karşılaştırılarak bulunur; o piksellerde baskı bastırılır.
"""
from __future__ import annotations

import cv2
import numpy as np

import banner_detect as bd
import compositor as cp
import video_repair as vr
from video_composite import CompositeError, build_print_layer, _lum

GRAY_LONG = 960


def _gray_small(f, long_side=GRAY_LONG):
    h, w = f.shape[:2]
    s = long_side / max(h, w)
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    return (cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else g), min(s, 1.0)


def _plane_mask(det_mask, s, pad_x=0.10, pad_top=0.03):
    """Düzlem maskesi (küçük koordinat): afiş + yanındaki dikmeler ve üst çubuk."""
    m = cv2.resize(det_mask, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
    ys, xs = np.where(m > 0)
    if xs.size == 0:
        raise CompositeError("afiş maskesi boş")
    bw, bh = xs.max() - xs.min(), ys.max() - ys.min()
    kx, ky = max(3, int(pad_x * bw)), max(3, int(pad_top * bh))
    return cv2.dilate((m > 0).astype(np.uint8) * 255, np.ones((2 * ky + 1, 2 * kx + 1), np.uint8))


def _lk_pair(prev, cur, pts, lk):
    p1, st1, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, **lk)
    p0b, st2, _ = cv2.calcOpticalFlowPyrLK(cur, prev, p1, None, **lk)
    good = (st1[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(pts[:, 0] - p0b[:, 0], axis=1) < 0.8)
    return p1, good


def _corner_move(Ha, Hb, w, h):
    """İki homografinin dört köşedeki en büyük farkı (px)."""
    c = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], float).T
    pa, pb = Ha @ c, Hb @ c
    return float(np.linalg.norm(pa[:2] / pa[2] - pb[:2] / pb[2], axis=0).max())


def _ecc_refine(g0, cur, Hi, mask0, w, h):
    """Hi (ilk kare -> bu kare) başlangıcını, ilk kareye karşı çok ölçekli ECC ile iyileştir. (H, korelasyon)."""
    Hw = np.linalg.inv(Hi)
    back = cv2.warpPerspective(cur, Hw, (w, h), flags=cv2.INTER_LINEAR)               # bu kare -> ilk kare koordinatı
    diff = cv2.GaussianBlur(cv2.absdiff(back, g0), (0, 0), 2.0)
    bad = (diff > 28).astype(np.uint8)                                                    # öne giren insan/nesne
    bad = cv2.dilate(bad, np.ones((15, 15), np.uint8))
    rel = (mask0 > 0).astype(np.uint8) * (1 - bad)
    rel = (rel * 255).astype(np.uint8)
    if rel.sum() / 255 < 0.15 * (mask0 > 0).sum():
        return Hi, 0.0                                                                    # çok kapalı: güvenme
    cur_ = Hi.astype(np.float32).copy()
    cc = 0.0
    for lv in (4, 2):
        sc = 1.0 / lv
        S = np.diag([sc, sc, 1.0]).astype(np.float32)
        t = cv2.resize(g0, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        c = cv2.resize(cur, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        m = cv2.resize(rel, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST)
        warp = (S @ cur_ @ np.linalg.inv(S)).astype(np.float32)
        cc, warp = cv2.findTransformECC(t, c, warp, cv2.MOTION_HOMOGRAPHY,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 1e-4), m, 5)
        cur_ = (np.linalg.inv(S) @ warp @ S).astype(np.float32)
        cur_ = cur_ / cur_[2, 2]
    return cur_.astype(float), float(cc)


def track(gray_frames, mask0, max_step=0.012):
    """Her kare için ilk kare -> o kare homografisi (küçük koordinatta). (H listesi, istatistik) döner.

    Dayanıklı iki aşama (kadrajda yürüyen insanlar izlemeyi bozmasın diye):
      1) TÜM kareden nokta izlenir, çoğunluğun hareketi (arka plan/çerçeve/balonlar = kamera) RANSAC ile bulunur.
         İnsanlar azınlıktır, dışarıda kalır.
      2) Afiş düzlemi maskesindeki noktalardan, 1. aşamaya uyanlar seçilip düzleme özel homografi iyileştirilir.
    Kare başına kamera hareketi küçüktür; çok büyük sıçrama güvenilmez sayılır ve önceki hareket tutulur."""
    g0 = gray_frames[0]
    H = [np.eye(3)]
    inl_ratio, ecc_cc, lost = [1.0], [1.0], 0
    lk = dict(winSize=(31, 31), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    h, w = g0.shape
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5)
    step_lim = max_step * max(w, h)
    last_rel = np.eye(3)
    for i in range(1, len(gray_frames)):
        prev, cur = gray_frames[i - 1], gray_frames[i]
        Hn, ratio = None, 0.0
        pts = cv2.goodFeaturesToTrack(prev, 900, 0.004, 6, blockSize=5)
        if pts is not None and len(pts) >= 20:
            p1, good = _lk_pair(prev, cur, pts, lk)
            if good.sum() >= 20:
                Hbg, inl = cv2.findHomography(pts[good], p1[good], cv2.RANSAC, 1.5)
                if Hbg is not None and inl is not None and inl.sum() >= 15:
                    Hn, ratio = Hbg, float(inl.sum()) / float(good.sum())
                    # 2. aşama: düzlem noktaları
                    m_prev = cv2.warpPerspective(mask0, H[-1], (w, h), flags=cv2.INTER_NEAREST)
                    xy = np.round(pts[:, 0]).astype(int)
                    inside = (xy[:, 0] >= 0) & (xy[:, 0] < w) & (xy[:, 1] >= 0) & (xy[:, 1] < h)
                    inplane = np.zeros(len(pts), bool)
                    inplane[inside] = m_prev[xy[inside, 1], xy[inside, 0]] > 0
                    pred = cv2.perspectiveTransform(pts, Hbg)
                    agree = np.linalg.norm(pred[:, 0] - p1[:, 0], axis=1) < 4.0
                    sel = good & inplane & agree
                    if sel.sum() >= 10:
                        Hp, inl2 = cv2.findHomography(pts[sel], p1[sel], cv2.RANSAC, 1.2)
                        if Hp is not None and inl2 is not None and inl2.sum() >= 8 and _corner_move(Hp, Hbg, w, h) < 0.02 * max(w, h):
                            Hn = Hp
        if Hn is None or ratio < 0.5:
            # yedek: yalnız düzlem maskesindeki noktalar (dokusuz/gürültülü sahnede tüm kare yöntemi zayıf kalabilir)
            m_prev = cv2.warpPerspective(mask0, H[-1], (w, h), flags=cv2.INTER_NEAREST)
            pl = cv2.goodFeaturesToTrack(prev, 500, 0.005, 5, mask=cv2.erode(m_prev, np.ones((5, 5), np.uint8)), blockSize=5)
            if pl is not None and len(pl) >= 12:
                p1, good = _lk_pair(prev, cur, pl, lk)
                if good.sum() >= 12:
                    Hr, inl = cv2.findHomography(pl[good], p1[good], cv2.RANSAC, 2.5)
                    if Hr is not None and inl is not None and inl.sum() >= 10 and float(inl.sum()) / float(good.sum()) > ratio:
                        Hn, ratio = Hr, float(inl.sum()) / float(good.sum())
        if Hn is not None and _corner_move(Hn, np.eye(3), w, h) > step_lim:
            Hn, ratio = None, 0.0                                     # makul olmayan sıçrama
        if Hn is None:
            lost += 1
            Hn = last_rel                                              # önceki hareketi sürdür (kamera yumuşak gider)
            Hn = np.linalg.matrix_power(np.eye(3) * 0 + Hn, 1) if False else Hn
            # hızı sönümle: tutulan hareketin yarısı
            Hn = np.eye(3) + 0.5 * (Hn - np.eye(3))
        else:
            last_rel = Hn
        Hi = Hn @ H[-1]
        Hi = Hi / Hi[2, 2]
        # ilk kareye karşı çok ölçekli ECC düzeltmesi: yalnız önüne kimsenin girmediği (güvenilir) piksellerde
        cc = 0.0
        try:
            Hi2, cc = _ecc_refine(g0, cur, Hi, mask0, w, h)
            if cc >= 0.65 and _corner_move(Hi2, Hi, w, h) < 0.08 * max(w, h):
                Hi = Hi2
            else:
                cc = 0.0
        except cv2.error:
            cc = 0.0
        H.append(Hi)
        inl_ratio.append(ratio)
        ecc_cc.append(cc)
    stats = {"izlenen_oran": float(np.mean([r > 0 for r in inl_ratio[1:]])) if len(H) > 1 else 1.0,
             "kayip_kare": lost, "ecc_ok_oran": float(np.mean([c > 0 for c in ecc_cc[1:]])) if len(H) > 1 else 1.0,
             "inlier_med": float(np.median(inl_ratio[1:])) if len(H) > 1 else 1.0}
    return H, stats


def _smooth_H(H, sigma=1.2):
    """Homografiyi dört köşe noktası üzerinden zamanda yumuşat (titreşimi alır)."""
    from scipy.ndimage import gaussian_filter1d
    src = np.float32([[0, 0], [1000, 0], [1000, 1000], [0, 1000]])
    P = np.stack([cv2.perspectiveTransform(src[None], h)[0] for h in H])          # n,4,2
    P = gaussian_filter1d(P, sigma, axis=0, mode="nearest")
    return [cv2.getPerspectiveTransform(src, p.astype(np.float32)).astype(float) for p in P]


def compose_tracked(video_in, out_path, design, *, progress=None, work_long=1920, occl_thr=0.09):
    """Hareketli AI videosunun üstüne tasarımı basar. (özet) döner. Özet 'ok' False ise çağıran yedeğe geçmelidir."""
    info = vr.video_info(video_in)
    fps = info["fps"] or 24.0
    frames_small, s = [], 1.0
    first = None
    for f in vr.iter_video(video_in):
        if first is None:
            first = f
        g, s = _gray_small(f)
        frames_small.append(g)
    n = len(frames_small)
    if n < 8:
        raise CompositeError("video çok kısa ya da okunamadı")
    Hh, Ww = first.shape[:2]
    f_up = min(2.0, max(1.0, work_long / max(Hh, Ww)))
    ww, wh = int(round(Ww * f_up)) // 2 * 2, int(round(Hh * f_up)) // 2 * 2
    ref = cv2.resize(first, (ww, wh), interpolation=cv2.INTER_CUBIC) if f_up > 1 else first.copy()
    det = bd.detect(ref)
    if not det.ok:
        raise CompositeError("videonun ilk karesinde afiş bulunamadı: " + "; ".join(det.reject))
    why = cp.check_fit(det, design)
    if why:
        raise CompositeError("tasarım videodaki afişe uymadı: " + str(why))
    _, _, model = cp.composite(ref, design, det, return_model=True)
    x0, y0, x1, y1 = model["bbox"]
    soften = 0.45 * max(0.0, f_up - 1.0) + (0.25 if f_up > 1.0 else 0.0)
    mul0 = build_print_layer(model, design, soften=soften)
    bh, bw = mul0.shape[:2]
    core0 = np.zeros((wh, ww), np.float32)
    core0[y0:y1, x0:x1] = (model["alpha"] > 0.5).astype(np.float32)
    mul_canvas = np.ones((wh, ww, 3), np.float32)
    mul_canvas[y0:y1, x0:x1] = mul0
    ref_lab = cv2.cvtColor(cv2.GaussianBlur(ref, (0, 0), 2.0), cv2.COLOR_BGR2LAB).astype(np.float32)
    ref_L = _lum(cv2.GaussianBlur(ref, (0, 0), 2.0).astype(np.float32) / 255.0)
    dm = det.mask if det.mask.shape[:2] == (wh, ww) else cv2.resize(det.mask, (ww, wh), interpolation=cv2.INTER_NEAREST)
    mask0 = _plane_mask(dm, frames_small[0].shape[1] / ww)
    if progress:
        progress(0, n * 2)
    Hs, st = track(frames_small, mask0)
    Hs = _smooth_H(Hs)
    # izleme kalitesi
    reasons = []
    if st["izlenen_oran"] < 0.8:
        reasons.append(f"afiş düzlemi karelerin %{(1 - st['izlenen_oran']) * 100:.0f}'inde izlenemedi")
    # küçük -> çalışma koordinatı
    k = frames_small[0].shape[1] / ww
    S = np.diag([k, k, 1.0])
    Sinv = np.diag([1 / k, 1 / k, 1.0])
    sink = vr.make_sink(out_path, float(fps), crf=17)
    occl_list = []
    try:
        for i, f in enumerate(vr.iter_video(video_in)):
            if i >= n:
                break
            fr = cv2.resize(f, (ww, wh), interpolation=cv2.INTER_CUBIC) if f_up > 1 else f
            Hf = Sinv @ Hs[i] @ S                       # ilk kare çalışma px -> bu kare çalışma px
            Hf = Hf / Hf[2, 2]
            mul = cv2.warpPerspective(mul_canvas, Hf, (ww, wh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(1, 1, 1))
            core = cv2.warpPerspective(core0, Hf, (ww, wh), flags=cv2.INTER_LINEAR) > 0.5
            core = cv2.erode(core.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            blur = cv2.GaussianBlur(fr, (0, 0), 2.0)
            if core.any():
                Lw = cv2.warpPerspective(ref_L, Hf, (ww, wh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                abw = cv2.warpPerspective(ref_lab[..., 1:], Hf, (ww, wh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                Lt = _lum(blur.astype(np.float32) / 255.0)
                ab = cv2.cvtColor(blur, cv2.COLOR_BGR2LAB).astype(np.float32)[..., 1:]
                ratio = Lt[core] / np.maximum(Lw[core], 1e-3)
                gain = float(np.clip(np.median(ratio), 0.7, 1.4))
                dev = np.abs(Lt - gain * Lw)
                dchroma = np.linalg.norm(ab - abw, axis=2)
                occl = ((dev > occl_thr) | (dchroma > 14.0)).astype(np.uint8)
                occl = cv2.morphologyEx(occl, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
                occl_core = float(occl[core].mean())
                soft = cv2.GaussianBlur(cv2.dilate(occl, np.ones((11, 11), np.uint8)).astype(np.float32), (0, 0), 3.0)
                soft = np.clip(soft * 1.4, 0, 1)[..., None]
                mul = 1.0 - (1.0 - mul) * (1.0 - soft)
            else:
                occl_core = 0.0                           # afiş kadraj dışında: baskı da kadraj dışında
            occl_list.append(occl_core)
            out = np.clip(fr.astype(np.float32) * mul + 0.5, 0, 255).astype(np.uint8)
            sink.write(out)
            if progress and i % 8 == 0:
                progress(n + i, n * 2)
        sink.close()
    except BaseException:
        sink.abort()
        raise
    occl_mean = float(np.mean(occl_list)) if occl_list else 0.0
    if occl_mean > 0.18:
        reasons.append(f"afişin önü ortalama %{occl_mean * 100:.0f} kapalı algılandı (baskı çok bastırıldı)")
    if st["kayip_kare"] > 0.2 * n:
        reasons.append("çok sayıda karede izleme koptu")
    quality = 100.0 * (0.5 * st["izlenen_oran"] + 0.3 * st["ecc_ok_oran"] + 0.2 * max(0.0, 1 - occl_mean / 0.18))
    summary = {"ok": not reasons, "reasons": reasons, "kalite": round(quality, 1), "kare": n, "occl_ort": round(occl_mean, 3), **{k2: round(v, 3) if isinstance(v, float) else v for k2, v in st.items()}}
    return summary

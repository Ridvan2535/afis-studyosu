"""
Video yazı onarımı sınaması: DOĞRUSU BİLİNEN sentetik video.

  gerçek kumaş sahnesi + örnek tasarım -> referans fotoğraf (still)
  GT_t   : still'in kamera hareketi (zoom+pan+hafif dönüş) + kumaş dalgalanması ile bükülmüş hali (doğru cevap)
  AI_t   : GT_t, ama baskı zamanla bozulur (esnek bozulma, bulanıklık, hayalet), ışık oynaması, gürültü
  onarım : AI_t -> repair_frames  ->  GT_t ile karşılaştırılır

Çalıştır:  python tests/test_video_repair.py [kare_sayısı] [bozulma_gücü]
"""
import os
import sys
import time

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import banner_detect as bd          # noqa: E402
import cvio                         # noqa: E402
import compositor as cp             # noqa: E402
import video_repair as vr           # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 72
GARBLE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
FPS = 24.0
OUT = os.path.join(HERE, "video_out")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def garble_design(design, strength):
    """Yapay zekanın bozduğu yazıyı taklit et: esnek bozulma + bulanıklık + hayalet kopya."""
    h, w = design.shape[:2]
    amp, sig = 9.0 * strength, 9.0
    dx = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), sig)
    dy = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), sig)
    norm = max(dx.std(), 1e-6)
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    g = cv2.remap(design, gx + dx / norm * amp, gy + dy / norm * amp, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    g = cv2.GaussianBlur(g, (0, 0), 1.6 * strength + 0.01)
    M = np.float32([[1, 0, 5], [0, 1, 4]])
    ghost = cv2.warpAffine(g, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return np.clip(0.68 * g + 0.32 * ghost, 0, 1).astype(np.float32)


def motion_map(t, shape, maskw):
    """Kare pikseli -> still koordinatı. Kamera (zoom, kayma, dönüş) + yalnız afişte kumaş dalgalanması."""
    H, W = shape
    e = smoothstep(t / (N - 1))
    s = 1 + 0.07 * e
    tx, ty = -26 * e, 10 * e
    rot = np.deg2rad(0.6) * e
    cx, cy = W * 0.52, H * 0.50
    xx, yy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    px, py = xx - cx - tx, yy - cy - ty
    c, sn = np.cos(rot), np.sin(rot)
    qx = (cx + (c * px + sn * py) / s).astype(np.float32)
    qy = (cy + (-sn * px + c * py) / s).astype(np.float32)
    w = cv2.remap(maskw, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    amp = 7.0 * smoothstep(t / 18.0)
    ph = t / FPS
    dx = amp * np.sin(2 * np.pi * (qy / 260.0 - 0.9 * ph)) * w
    dy = 0.35 * amp * np.sin(2 * np.pi * (qx / 180.0 + 0.7 * ph + 1.3)) * w
    return np.stack([qx + dx, qy + dy], -1).astype(np.float32)


def remap(img, M, interp=cv2.INTER_CUBIC):
    return cv2.remap(img, M[..., 0], M[..., 1], interp, borderMode=cv2.BORDER_REPLICATE)


def main():
    t0 = time.time()
    scene = cvio.imread(os.path.join(os.path.dirname(HERE), "scene.jpg"))
    H, W = scene.shape[:2]
    design = cp.load_design(os.path.join(os.path.dirname(HERE), "design_sample.png"))
    det = bd.detect(scene)
    still, _, model = cp.composite(scene, design, det, return_model=True)
    design_g = garble_design(design, GARBLE)
    still_g, _ = cp.composite(scene, design_g, det)
    maskw = cv2.GaussianBlur((det.mask > 0).astype(np.float32), (0, 0), 20)

    gt_frames, ai_frames, maps = [], [], []
    for t in range(N):
        M = motion_map(t, (H, W), maskw)
        g = float(smoothstep((t / (N - 1) - 0.05) / 0.55))                 # ilk kare temiz, sonra bozulur
        light = 1 + 0.015 * np.sin(2 * np.pi * 1.5 * t / N)
        gt = np.clip(remap(still, M).astype(np.float32) * light, 0, 255)
        ai_src = (1 - g) * still.astype(np.float32) + g * still_g.astype(np.float32)
        ai = remap(ai_src.astype(np.float32), M).astype(np.float32) * light + rng.normal(0, 1.2, (H, W, 1))
        gt_frames.append(gt.astype(np.uint8))
        ai_frames.append(np.clip(ai, 0, 255).astype(np.uint8))
        maps.append(M)
    print(f"sentetik video hazır: {N} kare, {W}x{H}, bozulma gücü {GARBLE}, {time.time() - t0:.1f}s")

    # gerçek bir mp4 dosyası olarak yaz ve geri oku (dosya girişi/çıkışı da sınansın)
    ai_path = os.path.join(OUT, "ai_video.mp4")
    vr.write_video(ai_frames, ai_path, FPS)
    ai_read, fps = vr.read_video(ai_path)
    print(f"mp4 yazıldı/okundu: {len(ai_read)} kare, {fps:.0f} fps, {os.path.getsize(ai_path) // 1024} KB")

    t1 = time.time()
    outs, infos, Ps = [], [], []
    for out, info, P in vr.repair_frames(iter(ai_read), still, scene, design, model, (W, H)):
        outs.append(out); infos.append(info); Ps.append(P)
    dt = time.time() - t1
    print(f"onarım: {dt:.1f}s toplam, {dt / N * 1000:.0f} ms/kare (2 çekirdekli CPU)")

    # ---- ölçüm: doğru cevapla karşılaştır ----
    # takip hatası yalnızca tasarımın "mürekkep" olan yerlerinde ölçülür (boş zeminde hata görünmez)
    gray = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ink0 = (gray(still) / np.maximum(gray(scene), 1) < 0.9).astype(np.float32)
    ink0 = cv2.dilate(ink0, np.ones((5, 5), np.uint8))
    rows = []
    for t in range(N):
        a_t = cv2.remap(model_full_alpha(model, (W, H)), maps[t][..., 0], maps[t][..., 1], cv2.INTER_LINEAR)
        core = cv2.erode((a_t > 0.9).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        ink_t = cv2.remap(ink0, maps[t][..., 0], maps[t][..., 1], cv2.INTER_LINEAR) > 0.5
        gt, ai, rp = gt_frames[t], ai_read[t], outs[t]
        mae_ai = float(np.abs(ai.astype(int) - gt.astype(int))[core].mean())
        mae_rp = float(np.abs(rp.astype(int) - gt.astype(int))[core].mean())
        ys, xs = np.where(core)
        sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
        gg = lambda im: cv2.cvtColor(im[sl], cv2.COLOR_BGR2GRAY)
        s_ai, s_rp = ssim(gg(gt), gg(ai)), ssim(gg(gt), gg(rp))
        err = np.linalg.norm(Ps[t] - maps[t], axis=-1)[core & ink_t]
        rows.append((t, mae_ai, mae_rp, s_ai, s_rp, float(err.mean()), float(np.percentile(err, 95))))
    R = np.array(rows)
    print("\nkare   MAE(AI)  MAE(onarım)   SSIM(AI)  SSIM(onarım)   yazı bölgesinde takip hatası ort/p95 (px)")
    for t in sorted(set([0, 1, N // 6, N // 3, N // 2, 2 * N // 3, 5 * N // 6, N - 1])):
        r = R[t]
        print(f"{t:4d}   {r[1]:7.2f}   {r[2]:9.2f}   {r[3]:9.3f}   {r[4]:10.3f}   {r[5]:6.2f} / {r[6]:6.2f}")
    print(f"\nORTALAMA  MAE: AI {R[:, 1].mean():.2f} -> onarım {R[:, 2].mean():.2f}"
          f"   SSIM: AI {R[:, 3].mean():.3f} -> onarım {R[:, 4].mean():.3f}"
          f"   takip hatası: ort {R[:, 5].mean():.2f} px, en kötü kare p95 {R[:, 6].max():.2f} px")
    print("özet:", vr.summarize(infos))

    # ---- görsel kontrol ----
    sel = [0, N // 3, 2 * N // 3, N - 1]
    a0 = cv2.remap(model_full_alpha(model, (W, H)), maps[sel[-1]][..., 0], maps[sel[-1]][..., 1], cv2.INTER_LINEAR)
    ys, xs = np.where(a0 > 0.5)
    y0, y1, x0, x1 = max(0, ys.min() - 20), ys.max() + 20, max(0, xs.min() - 20), xs.max() + 20
    # kare 0 ve son karede aynı kırpma: son karedeki bölge daha geniş
    cols = []
    for t in sel:
        col = [im[t][y0:y1, x0:x1] for im in (ai_read, outs, gt_frames)]
        cols.append(np.vstack([cv2.resize(c, None, fx=0.42, fy=0.42, interpolation=cv2.INTER_AREA) for c in col]))
    cvio.imwrite(os.path.join(OUT, "karsilastirma.jpg"), np.hstack(cols), [cv2.IMWRITE_JPEG_QUALITY, 92])
    # yazı detay kırpığı (son kare): AI | onarım | doğru
    mid_y = (y0 + y1) // 2
    cy0, cy1, cx0, cx1 = mid_y - 330, mid_y - 120, x0 + 20, x1 - 20
    det_crop = np.hstack([im[sel[-1]][cy0:cy1, cx0:cx1] for im in (ai_read, outs, gt_frames)])
    cvio.imwrite(os.path.join(OUT, "yazi_detay_son_kare.jpg"), det_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    vr.write_video(outs, os.path.join(OUT, "onarilmis.mp4"), FPS)
    print("kaydedildi:", OUT)


_ALPHA_CACHE = {}


def model_full_alpha(model, size):
    k = id(model)
    if k not in _ALPHA_CACHE:
        W, H = size
        a = np.zeros((H, W), np.float32)
        x0, y0, x1, y1 = model["bbox"]
        a[y0:y1, x0:x1] = model["alpha"]
        _ALPHA_CACHE[k] = a
    return _ALPHA_CACHE[k]


if __name__ == "__main__":
    main()

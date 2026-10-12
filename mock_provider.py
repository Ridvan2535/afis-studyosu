# -*- coding: utf-8 -*-
"""
SAHTE sağlayıcılar: gerçek servis DEĞİLDİR, yalnızca tüm akışı anahtarsız/ücretsiz sınamak içindir.

MockScenes : sentetik sahneler üretir (iyi sert afişler, gerçek kumaş fotoğrafı, ve kalite kapısının
             elemesi gereken kötü örnekler: yazılı afiş, afişsiz sahne).
MockVideo  : verilen kareden kamera hareketi + giderek bozulan yazı içeren sahte bir "yapay zeka videosu" üretir.
"""
from __future__ import annotations

import os
import re
import tempfile

import cv2
import numpy as np

import make_test_scenes as mts
import video_repair as vr

HERE = os.path.dirname(os.path.abspath(__file__))


def _tall_quad(W, H, aspect, seed, top=0.085, bottom=0.885, yaw=0.0):
    """Yere kadar uzanan dik afiş. yaw>0: yan açı taklidi (sol kenar daha uzun görünür)."""
    rng = np.random.default_rng(1000 + seed)
    h = (bottom - top) * H
    w = min(aspect * h, 0.80 * W)
    h = w / aspect
    cx = W * (0.5 + rng.uniform(-0.02, 0.02))
    y0 = top * H
    k = yaw * h / 2
    return [(cx - w / 2, y0 + k), (cx + w / 2, y0 - k), (cx + w / 2, y0 + h + k * 0.9), (cx - w / 2, y0 + h - k * 0.9)]


_SIZE_RE = re.compile(r"exactly\s+(\d+(?:\.\d+)?)\s*cm\s+wide\s+and\s+(\d+(?:\.\d+)?)\s*cm\s+long", re.I)


def prompt_size(prompt) -> tuple[float, float] | None:
    """Prompttaki "exactly W cm wide and H cm long" ifadesinden (en, boy) cm; yoksa None (eski davranış)."""
    mt = _SIZE_RE.search(str(prompt or ""))
    return (float(mt.group(1)), float(mt.group(2))) if mt else None


# Kare sahne türleri (Aşama 2A). Gerçek sahne gibi: duvar + zemin + ahşap stand + kurdele fiyonkları + krem kumaş.
#   dokunan  : kumaşın alt kenarı tam zemin çizgisinde (asılı boy = ürün boyu)
#   birikmeli: asılı kısım zemine değer, kalan kumaş zeminde hafifçe yayılarak birikir (alt kenar genişler)
#   havada   : kumaş zemine ulaşmadan biter (elenmeli: sahne geometrisi)
#   uzun     : kumaş üründen ince/uzun çizilmiş (asılı boy > ürün boyu; elenmeli: sahne geometrisi)
SQUARE_KINDS = ("dokunan", "birikmeli", "havada", "uzun")
FLOOR_FRAC = 0.89          # zemin çizgisi (kadraj yüksekliği oranı)
TOP_FRAC = 0.11            # kumaşın üst kenarı


def square_scene(size: int, aspect: float, kind: str = "dokunan", seed: int = 0, ribbon_hex: str | None = "#E8B4BC",
                 pool_frac: float = 0.10, wall_rgb=None):
    """Kare sahte sahne. aspect = ürün en/boy (cm oranı). (BGR uint8, gerçek geometri sözlüğü) döner.

    Geometri piksel SINIRLARIYLA verilir: x0/x1 kumaşın sol/sağ kenarı, top üst kenar, contact zemine temas çizgisi,
    total_px kumaşın tam boyu (piksel; ürün boyu), hang_px asılı kısmın boyu."""
    if kind not in SQUARE_KINDS:
        raise ValueError(kind)
    rng = np.random.default_rng(5000 + int(seed))
    mts.rng = np.random.default_rng(int(seed))
    W = H = int(size)
    walls = [(136, 158, 128), (176, 112, 92), (44, 62, 92), (120, 150, 160), (150, 120, 150)]
    img = mts.wall(W, H, wall_rgb or walls[int(seed) % len(walls)])
    fy = int(round(FLOOR_FRAC * H))
    img[fy:] = img[fy:] * 0.55 + np.array([60, 70, 80], np.float32)          # zemin
    top = int(round(TOP_FRAC * H))
    span = fy - top
    if kind == "dokunan":
        total = span; hang = span; bw = aspect * total
    elif kind == "birikmeli":
        hang = span; total = hang / (1 - pool_frac); bw = aspect * total
    elif kind == "havada":
        total = int(0.86 * span); hang = total; bw = aspect * span      # en ürüne göre, ama kumaş zemine ulaşmadan bitiyor
    else:                                    # uzun: en dar, boy tam -> asılı boy ürün boyunun ~1.3 katı
        total = span; hang = span; bw = aspect * total / 1.3
    bw = int(round(bw))
    cx = W // 2 + int(rng.integers(-W // 60, W // 60 + 1))
    x0, x1 = cx - bw // 2, cx - bw // 2 + bw
    bottom = top + int(round(hang))

    # ahşap stand (sahne dekoru): iki dikme, üst çubuk, ayaklar
    wood = np.array((92, 140, 190), np.float32)
    pw = max(6, int(0.011 * W))
    gap = int(0.05 * W)
    px0, px1 = x0 - gap - pw, x1 + gap
    rod_y = top - int(0.006 * H)
    img[rod_y - pw // 2:rod_y + pw // 2 + 1, px0:px1 + pw] = wood
    for px in (px0, px1):
        img[rod_y:fy + 2, px:px + pw] = wood
        img[fy - pw:fy + 2, px - int(0.03 * W):px + pw + int(0.03 * W)] = wood * 0.9
    # kumaş: hafif dikey kıvrım gölgesi, sol-üstten ışık
    fab = np.array((214, 228, 236), np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    shade = 1 + 0.025 * np.sin(2 * np.pi * (xx - x0) / max(bw / 2.7, 1)) - 0.05 * (yy - top) / H - 0.03 * (xx - x0) / max(bw, 1)
    m = np.zeros((H, W), np.float32)
    m[top:bottom, x0:x1] = 1.0
    if kind == "havada":                                                  # duvarda gölge
        sh = cv2.GaussianBlur(np.roll(np.roll(m, 14, 0), 10, 1), (0, 0), 12) * 0.25
        img *= (1 - sh)[..., None]
    pool = None
    if kind == "birikmeli":
        # zeminde biriken kumaş: temas çizgisinden aşağı genişleyen, yumuşak kıvrımlı yayılma
        d = max(8, int(0.045 * H))
        spread = max(6, int(0.10 * bw))
        poly = np.array([[x0, bottom], [x1, bottom], [x1 + spread, bottom + int(0.65 * d)], [x1 + spread // 2, bottom + d],
                         [x0 - spread // 2, bottom + d], [x0 - spread, bottom + int(0.65 * d)]], np.int32)
        pm = np.zeros((H, W), np.uint8)
        cv2.fillPoly(pm, [poly], 1)
        pm = cv2.GaussianBlur(pm.astype(np.float32), (0, 0), 1.0)
        img *= (1 - 0.35 * cv2.GaussianBlur(np.roll(pm, 6, 0), (0, 0), 8))[..., None]           # zemine düşen gölge
        m = np.maximum(m, pm)
        m[top:bottom + 2, x0:x1] = 1.0                                   # asılı kısım ile birikme arasında dikiş çizgisi olmasın
        shade = shade - 0.04 * np.clip((yy - bottom) / d, 0, 1)
        pool = {"depth": d, "spread": spread}
    col = fab[None, None, :] * shade[..., None] + rng.normal(0, 0.8, (H, W, 1)).astype(np.float32)
    ma = cv2.GaussianBlur(m, (0, 0), 0.5)[..., None] if kind != "birikmeli" else m[..., None]
    img = img * (1 - ma) + col * ma
    # çubuğun kumaş üstündeki kısmı (kumaş çubuktan sarkar)
    img[rod_y - pw // 2:top + 1, x0:x1] = wood
    # kurdele fiyonkları ve kuyruklar (kumaşın DIŞINDA, dikme ile kumaş arasında)
    if ribbon_hex:
        hx = ribbon_hex.lstrip("#")
        rgb = tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))
        bgr = (rgb[2], rgb[1], rgb[0])
        tw = max(4, int(0.009 * W))
        for bx in (x0 - gap // 2, x1 + gap // 2):
            cv2.rectangle(img, (bx - tw // 2, rod_y), (bx + tw // 2, rod_y + int(0.33 * span)), bgr, -1, cv2.LINE_AA)
            cv2.rectangle(img, (bx + tw, rod_y), (bx + tw + tw // 2 + 2, rod_y + int(0.26 * span)), bgr, -1, cv2.LINE_AA)
            cv2.ellipse(img, (bx - tw, rod_y), (int(tw * 1.7), int(tw * 1.1)), 25, 0, 360, bgr, -1, cv2.LINE_AA)
            cv2.ellipse(img, (bx + tw, rod_y), (int(tw * 1.7), int(tw * 1.1)), -25, 0, 360, bgr, -1, cv2.LINE_AA)
            cv2.circle(img, (bx, rod_y), max(3, tw // 2 + 1), bgr, -1, cv2.LINE_AA)
    img = np.clip(img, 0, 255).astype(np.uint8)
    truth = {"kind": kind, "x0": float(x0), "x1": float(x1), "top": float(top), "contact": float(bottom),
             "floor": float(fy), "total_px": float(total), "hang_px": float(hang), "width_px": float(bw), "pool": pool}
    return img, truth


class MockScenes:
    """Sahte sahneler: iyi (dik, karşıdan, yere kadar) ve kalite kapısının elemesi gereken kötü örnekler.

    Kare (1:1) istendiğinde (aw≈ah) kare sahne üretir ve afiş oranını prompttaki "exactly W cm wide and H cm long"
    ifadesinden alır (yoksa eski davranış: kadraj oranından türetir). Kare türler: bkz. SQUARE_KINDS.
    Ek sahte servis adları (yalnız kare kipte anlamlı): mock_pool (hep birikmeli), mock_air (hep havada biten),
    mock_long (hep üründen uzun), mock_touch (hep tam zemine değen)."""
    PAPERS = [(238, 235, 229), (240, 238, 230), (236, 234, 228)]
    supports_guide = True
    FORCED = {"mock_pool": "birikmeli", "mock_air": "havada", "mock_long": "uzun", "mock_touch": "dokunan"}

    def __init__(self, variant="mock"):
        self.model = f"mock-{variant}"          # kayıt için model kimliği (gerçek servislerdeki impl.model gibi)
        self.kind = variant                     # mock | mock_bad (hep yan açılı) | mock_err (hep hata) | mock_thin (afiş fazla ince) | FORCED

    def _square(self, prompt, seed, size=1536) -> bytes:
        ps = prompt_size(prompt)
        aspect = (ps[0] / ps[1]) if ps else 0.375
        if self.kind == "mock_thin":
            kind = "uzun"
        elif self.kind in self.FORCED:
            kind = self.FORCED[self.kind]
        else:
            # mock: çoğu iyi (dokunan / birikmeli), arada elenmesi gerekenler (havada, uzun)
            kind = ("dokunan", "birikmeli", "dokunan", "havada", "birikmeli", "uzun")[seed % 6]
        img, _ = square_scene(size, aspect, kind, seed=seed)
        if self.kind == "mock_bad":                       # yan açılı: sağ tarafı daralt (perspektif)
            Hh, Ww = img.shape[:2]
            src = np.float32([[0, 0], [Ww, 0], [Ww, Hh], [0, Hh]])
            dst = np.float32([[0, 0], [Ww, 0.12 * Hh], [Ww, 0.88 * Hh], [0, Hh]])
            img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (Ww, Hh), borderMode=cv2.BORDER_REPLICATE)
        ok, buf = cv2.imencode(".png", img)
        return buf.tobytes()

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        if self.kind == "mock_err":
            from providers import ProviderError
            raise ProviderError("sahte servis hatası (sınama)")
        seed = int(seed or 0)
        if ah and abs(aw / ah - 1.0) < 0.02:                  # kare kadraj istendi (Aşama 2A fotoğraf hattı)
            return self._square(prompt, seed)
        variant = 3 if self.kind == "mock_bad" else (1 if self.kind == "mock_thin" else seed % 6)
        if self.kind == "mock_bad":
            seed = seed - seed % 12                # her zaman 'yan açılı' dalı
        W, H = (1024, 1536) if ah >= aw else (1536, 1024)
        aspect = max(aw / ah / 1.26, 0.2)                     # çağıran kadraj oranını verir; afiş oranı buradan türer
        if self.kind == "mock_thin":
            aspect *= 0.72                                    # gerçek servislerdeki gibi afişi fazla ince çiz
        mts.rng = np.random.default_rng(seed)
        if variant == 2:                                       # gerçek kumaş fotoğrafı (varsa)
            p = os.path.join(HERE, "scene.jpg")
            if os.path.exists(p):
                return open(p, "rb").read()
            variant = 0
        walls = {0: (136, 158, 128), 1: (176, 112, 92), 5: (44, 62, 92), 3: (120, 150, 160), 4: (170, 175, 165)}
        img = mts.wall(W, H, walls.get(variant, (136, 158, 128)))
        img[int(H * 0.905):] = img[int(H * 0.905):] * 0.55 + np.array([60, 70, 80], np.float32)    # zemin
        paper = self.PAPERS[seed % 3]
        if variant in (0, 1, 5):                               # İYİ: dik, karşıdan, yere kadar
            mts.add_poster(img, _tall_quad(W, H, aspect, seed), paper, (150, 110, 70), 5, shadow=0.25)
        elif variant == 3 and (seed // 6) % 2 == 0:            # KÖTÜ: yan açılı
            mts.add_poster(img, _tall_quad(W, H, aspect, seed, yaw=0.14), paper, (150, 110, 70), 5, shadow=0.25)
        elif variant == 3:                                     # KÖTÜ: afişte çizilmiş yazı
            q = _tall_quad(W, H, aspect, seed)
            mts.add_poster(img, q, paper, (150, 110, 70), 5, shadow=0.25)
        elif variant == 4 and (seed // 6) % 2 == 0:            # KÖTÜ: kısa afiş, yere ulaşmıyor
            mts.add_poster(img, _tall_quad(W, H, aspect, seed, top=0.18, bottom=0.55), paper, (150, 110, 70), 5, shadow=0.25)
        # variant 4, ikinci tur: afişsiz sahne
        img = np.clip(img, 0, 255).astype(np.uint8)
        if variant == 3 and (seed // 6) % 2 == 1:
            q = np.array(_tall_quad(W, H, aspect, seed))
            x, y = int(q[:, 0].min() + 30), int((q[:, 1].min() + q[:, 1].max()) / 2)
            cv2.putText(img, "WELCOME", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (40, 40, 40), 4, cv2.LINE_AA)
        ok, buf = cv2.imencode(".png", img)
        return buf.tobytes()


class MockVideo:
    def __init__(self, bad=False):
        self.bad = bad

    def _static(self, img, seconds, seed):
        """Sabit kameralı sahte video (kompozit hat için): hafif kamera kayması + arka planda yürüyen insanlar + gren.
        İstek 'MOCK_VIDEO=bad' ise kamera çok oynar (kalite kontrol reddetmeli)."""
        import math
        import banner_detect as bd
        img = cv2.resize(img, (720, 1280), interpolation=cv2.INTER_AREA)
        H, W = img.shape[:2]
        n = max(14, min(int(seconds * 24), int(os.environ.get("MOCK_FRAMES", "24"))))
        rng = np.random.default_rng(int(seed or 0))
        drift = 9.0 if (self.bad or os.environ.get("MOCK_VIDEO") == "bad") else 1.0
        det = bd.detect(img)
        if det.ok and det.mask.any():
            ys, xs = np.where(det.mask > 0)
            bx0, bx1 = int(xs.min()), int(xs.max())
            outside = cv2.dilate(det.mask, np.ones((25, 25), np.uint8)) == 0
        else:
            bx0, bx1 = int(0.2 * W), int(0.8 * W)
            outside = np.ones((H, W), bool)
        # gerçek sahnelerdeki doku (çim, yaprak, duvar dokusu) taklidi: sabit, afişin dışında. Düz sahnede takip edilecek nokta olmaz.
        tex = cv2.GaussianBlur(np.random.default_rng(99).normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.1) * 22.0
        img = np.clip(img.astype(np.float32) + (tex * outside)[..., None], 0, 255).astype(np.uint8)
        frames = []
        for i in range(n):
            t = i / 24
            fr = img.copy()
            for k, (x0, y0, sp) in enumerate([(0.03 * W, 0.52 * H, 0.3), (0.94 * W, 0.50 * H, -0.25)]):
                x = int(np.clip(x0 + sp * i, 12, W - 12))
                if bx0 - 14 < x < bx1 + 14:
                    continue
                cv2.ellipse(fr, (x, int(y0)), (13, 34), 0, 0, 360, (60 + 30 * k, 50, 90), -1, cv2.LINE_AA)
                cv2.circle(fr, (x, int(y0) - 44), 10, (120, 150, 200), -1, cv2.LINE_AA)
            M = cv2.getRotationMatrix2D((W / 2, H / 2), drift * 0.1 * math.sin(2 * math.pi * 0.2 * t), 1 + drift * 0.003 * math.sin(2 * math.pi * 0.13 * t))
            M[:, 2] += [drift * 4 * math.sin(2 * math.pi * 0.17 * t), drift * 3 * math.sin(2 * math.pi * 0.11 * t + 1)]
            fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
            frames.append(np.clip(fr.astype(np.float32) + rng.normal(0, 1.0, fr.shape), 0, 255).astype(np.uint8))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "mock.mp4")
            vr.write_video(frames, p, 24.0)
            return open(p, "rb").read()

    def video(self, image_jpg: bytes, prompt, seconds=6, seed=None) -> bytes:
        img = cv2.imdecode(np.frombuffer(image_jpg, np.uint8), cv2.IMREAD_COLOR)
        if str(prompt).startswith("Locked-off"):
            return self._static(img, seconds, seed)
        img = cv2.resize(img, (720, 1280), interpolation=cv2.INTER_AREA)
        n = min(int(seconds * 24), int(os.environ.get("MOCK_FRAMES", "24")))
        rng = np.random.default_rng(int(seed or 0))
        H, W = img.shape[:2]
        xx, yy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        nx = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 14)
        ny = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 14)
        nx, ny = nx / nx.std(), ny / ny.std()
        frames = []
        for t in range(n):
            e = t / max(n - 1, 1)
            s = 1 + 0.30 * e
            cx, cy = W * (0.5 - 0.04 * e), H * 0.5
            mx = (cx + (xx - cx) / s).astype(np.float32)
            my = (cy + (yy - cy) / s).astype(np.float32)
            g = min(1.0, max(0.0, (e - 0.05) / 0.5))                     # bozulma giderek artar
            f = cv2.remap(img, mx + 5.0 * g * nx, my + 5.0 * g * ny, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            if g > 0:
                f = cv2.GaussianBlur(f, (0, 0), 1.4 * g)
            frames.append(f)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "mock.mp4")
            vr.write_video(frames, p, 24.0)
            return open(p, "rb").read()

# -*- coding: utf-8 -*-
"""
SAHTE sağlayıcılar: gerçek servis DEĞİLDİR, yalnızca tüm akışı anahtarsız/ücretsiz sınamak içindir.

MockScenes : sentetik sahneler üretir (iyi sert afişler, gerçek kumaş fotoğrafı, ve kalite kapısının
             elemesi gereken kötü örnekler: yazılı afiş, afişsiz sahne).
MockVideo  : verilen kareden kamera hareketi + giderek bozulan yazı içeren sahte bir "yapay zeka videosu" üretir.
"""
from __future__ import annotations

import os
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


class MockScenes:
    """Sahte sahneler: iyi (dik, karşıdan, yere kadar) ve kalite kapısının elemesi gereken kötü örnekler."""
    PAPERS = [(238, 235, 229), (240, 238, 230), (236, 234, 228)]
    supports_guide = True

    def __init__(self, variant="mock"):
        self.kind = variant                     # mock | mock_bad (hep yan açılı) | mock_err (hep hata) | mock_thin (afiş fazla ince)

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        if self.kind == "mock_err":
            from providers import ProviderError
            raise ProviderError("sahte servis hatası (sınama)")
        seed = int(seed or 0)
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

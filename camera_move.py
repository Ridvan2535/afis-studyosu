# -*- coding: utf-8 -*-
"""
Sanal kamera: hazır mockup fotoğrafı SABİT kalır, kamera "elinde yürüyen biri" gibi hareket eder.
Yapay zekâ yoktur: yazı ve tasarım hiçbir karede bozulamaz, ücret çıkmaz, birkaç on saniyede biter.

Gerçekçilik için fiziksel bir model kullanılır (sadece kırp-kaydır değil):
  * Kamera gerçekten DÖNER (yaw/pitch/roll). Dönme, sahnenin derinliğinden bağımsız olduğu için tek bir
    homografiyle (H = K·R·K⁻¹) kusursuz doğru uygulanır; dikey çizgilerde hafif perspektif değişimi görülür.
  * Yürüme ritmi: adım sıklığı ~1.8 Hz'de dikey/pitch zıplaması, adımın yarısı sıklığında (~0.9 Hz) yanal
    sallanma ve roll; üstüne dikkatsizlikten gelen 0.4–6 Hz bant sınırlı rastgele titreme.
  * Kasıtlı hareket (yakınlaşma / sağa-sola kayma) tam pürüzsüz değil: yavaş "dolaşma" ve hız dalgalanması var.
  * Hareket bulanıklığı: her karede deklanşör süresi boyunca alt-örnekler alınıp ortalanır (180° deklanşör).
  * Rolling shutter: kare içinde satırlar farklı anda alındığı için hızlı sallantıda çok hafif eğilme.
  * Hafif film greni ve otomatik pozlama dalgalanması (tam temiz görüntü "yapay" durur).
  * Kadraj dışına taşma olmasın diye gerekli yakınlaştırma payı HESAPLANIR (kenarda boşluk görünmez).

Aynı kamera, sonradan yapay zekâ videosunun karelerine de uygulanabilir (CameraRig.render_frame).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

import video_repair as vr

# z: (başlangıç, bitiş) yakınlaştırma; x: kamera merkezinin yatay kayması (görsel genişliği oranı);
# yaw: kamera kayarken konuya doğru hafif dönme (derece, başlangıç/bitiş)
MOVES = {
    # "dolly": gerçek yürüyüş gibi sabit hızda ilerleme (yakınlaşma sona doğru hızlanır, 1/z doğrusaldır);
    # "lin": ilerleme eğrisinde doğrusal pay (1 = tam sabit hız; küçükse başlangıç/bitiş yumuşar)
    "yakinlas":       {"ad": "Afişe doğru yürü (belirgin yakınlaşma)", "z": (1.00, 2.10), "x": (0.0, 0.0),       "yaw": (0.0, 0.0),
                       "dolly": True, "lin": 0.9},
    # "orbit": kamera afişe yaklaşırken onun etrafında yay çizer (derece, + = sağa); afiş yana dönüyormuş gibi perspektif değişir
    "yakinlas_saga":  {"ad": "Yaklaşırken sağa doğru dön (yay çizerek)", "z": (1.00, 2.00), "x": (0.0, 0.0), "yaw": (0.0, 0.0),
                       "dolly": True, "lin": 0.9, "orbit": 24.0},
    "yakinlas_sola":  {"ad": "Yaklaşırken sola doğru dön (yay çizerek)", "z": (1.00, 2.00), "x": (0.0, 0.0), "yaw": (0.0, 0.0),
                       "dolly": True, "lin": 0.9, "orbit": -24.0},
    "yakinlas_cok":   {"ad": "Çok yakına git (yazıları göster)",       "z": (1.00, 2.70), "x": (0.0, 0.0),       "yaw": (0.0, 0.0),
                       "dolly": True, "lin": 0.9},
    "uzaklas":        {"ad": "Yavaşça uzaklaş (geri çekil)", "z": (1.07, 1.00), "x": (0.0, 0.0),       "yaw": (0.0, 0.0)},
    "saga":           {"ad": "Yan kaydır: sağa (yakınlaşma yok)", "z": (1.05, 1.05), "x": (-0.022, 0.022), "yaw": (0.8, -0.8)},
    "sola":           {"ad": "Yan kaydır: sola (yakınlaşma yok)", "z": (1.05, 1.05), "x": (0.022, -0.022), "yaw": (-0.8, 0.8)},
}
ALL_SET = ["yakinlas", "yakinlas_saga", "yakinlas_sola"]          # "Hepsini üret" seçeneği

# El kamerası şiddeti: kullanıcıya gösterilen ad -> çarpan (1.0 = eski "dikkatsiz yürüyüş"; doğal el artık 0.35)
HANDHELD_LEVELS = {
    "sabit":    {"ad": "Sabit (tripod)",                      "k": 0.0},
    "sakin":    {"ad": "Çok sakin el (neredeyse sabit)",            "k": 0.15},
    "yuruyus":  {"ad": "Doğal el (hafif sallantı)",               "k": 0.35},
    "belirgin": {"ad": "Belirgin el sallantısı",             "k": 0.8},
}
DEFAULT_LEVEL = "yuruyus"


def expand(move: str) -> list[str]:
    if move == "hepsi":
        return list(ALL_SET)
    return [move if move in MOVES else "yakinlas"]


def level_value(level) -> float:
    """'yuruyus' gibi bir ad ya da doğrudan sayı kabul eder."""
    if isinstance(level, (int, float)):
        return max(0.0, float(level))
    return HANDHELD_LEVELS.get(str(level), HANDHELD_LEVELS[DEFAULT_LEVEL])["k"]


def _ease(t, lin=0.35):
    """Yumuşak başlangıç/bitiş (kosinüs) + biraz doğrusal: sabit hız hissini korur."""
    return (1 - lin) * 0.5 * (1 - np.cos(np.pi * t)) + lin * t


def _bandnoise(rng, n, sr, lo, hi):
    """Birim standart sapmalı, [lo, hi] Hz bant sınırlı gürültü."""
    from scipy.signal import butter, sosfiltfilt
    x = rng.standard_normal(n)
    sos = butter(2, [lo, hi], btype="band", fs=sr, output="sos")
    y = sosfiltfilt(sos, x)
    return y / (y.std() + 1e-9)


def _R(yaw, pitch, roll):
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


# ----------------------------------------------------------------------------
class CameraRig:
    """Bir kamera yolu (zamana bağlı yaw/pitch/roll/kayma/yakınlaşma) ve onu kareye uygulayan işleyici.

    sw, sh: kaynak görüntü boyutu    ow, oh: çıktı boyutu (aynı oran)
    """

    SR = 240.0                                   # yol örnekleme sıklığı (Hz)

    def __init__(self, sw, sh, ow, oh, seconds=6.0, fps=30, move="yakinlas", intensity=1.0, strength=1.0,
                 seed=11, vfov=58.0, max_zoom=1.16, shutter=0.33, readout=0.016, grain=1.0, exposure=1.0):
        self.sw, self.sh, self.ow, self.oh = int(sw), int(sh), int(ow), int(oh)
        self.fps, self.seconds = float(fps), float(seconds)
        self.k = max(0.0, float(intensity))
        self.spec = MOVES.get(move) or MOVES["yakinlas"]
        self.strength = float(strength)
        self.shutter, self.readout = float(shutter), float(readout)
        self.grain_sigma = 1.25 * grain
        self.exposure = exposure
        self.f = (sh / 2) / math.tan(math.radians(vfov) / 2)        # kaynak odak uzaklığı (px)
        self.so = ow / sw
        self.seed = seed
        self.n = max(2, int(round(seconds * fps)))
        self._build(seed)
        self.z_extra = 1.0
        self.amp = 1.0
        self._fit(max_zoom)
        self._grain_pool = None

    # -- yol ----------------------------------------------------------------------------------
    def _build(self, seed):
        rng = np.random.default_rng(seed)
        pad = 1.0
        n = int((self.seconds + 2 * pad) * self.SR) + 1
        self._t0 = -pad
        self.fs = float(rng.uniform(1.40, 1.62))                   # adım sıklığı (Hz): sakin, uzun adımlar
        self.ph = rng.uniform(0, 2 * math.pi, 12)
        self.nz = {
            "pitch": _bandnoise(rng, n, self.SR, 0.4, 3.8),
            "yaw":   _bandnoise(rng, n, self.SR, 0.3, 3.2),
            "roll":  _bandnoise(rng, n, self.SR, 0.3, 2.6),
            "zoom":  _bandnoise(rng, n, self.SR, 0.3, 2.5),
            "gain":  _bandnoise(rng, n, self.SR, 0.15, 1.2),
            "spd":   _bandnoise(rng, n, self.SR, 0.1, 0.8),
        }

    def _ns(self, key, t):
        arr = self.nz[key]
        return np.interp((np.asarray(t) - self._t0) * self.SR, np.arange(len(arr)), arr)

    def _shake(self, t):
        """El kamerası açıları (radyan) ve zıplama kayması; şiddet katsayısı uygulanmış."""
        t = np.asarray(t, float)
        fs, ph = self.fs, self.ph
        mod = 1 + 0.25 * np.sin(2 * np.pi * 0.23 * t + ph[0])                    # adım şiddeti dalgalanır
        th = 2 * np.pi * fs * t
        step = np.sin(th + ph[1]) + 0.18 * np.sin(2 * th + ph[2])                # her adımda (topuk vuruşu)
        sway = np.sin(th / 2 + ph[3])                                            # iki adımda bir yanal sallanma
        sway2 = np.sin(th / 2 + ph[4])
        k = self.k * self.amp
        d2r = math.pi / 180
        pitch = k * (0.50 * step * mod + 0.26 * self._ns("pitch", t)) * d2r
        yaw = k * (0.34 * sway * mod + 0.26 * self._ns("yaw", t)) * d2r
        roll = k * (0.22 * sway2 + 0.16 * self._ns("roll", t)) * d2r
        zoom = 1 + k * (0.0016 * np.sin(th / 2 + ph[5]) + 0.0016 * self._ns("zoom", t))
        return yaw, pitch, roll, zoom

    def _progress(self, t):
        """Kasıtlı hareketin ilerleme eğrisi (0-1)."""
        t = np.asarray(t, float)
        u = np.clip(t / self.seconds, 0, 1)
        # hız dalgalanması: ilerleme eğrisi küçük bir zaman bozulmasıyla (insan sabit hızda yürümez)
        warp = u + 0.035 * self._ns("spd", t) * np.sin(np.pi * u)
        return _ease(np.clip(warp, 0, 1), self.spec.get("lin", 0.35))

    def _phi(self, t):
        """Yay (orbit) açısı, radyan: kamera afişin etrafında bu kadar döner (+ = sağa). Yay yoksa 0."""
        deg = float(self.spec.get("orbit", 0.0))
        if not deg:
            return 0.0
        return np.radians(deg * self.strength) * self._progress(t)

    def _base(self, t):
        """Kasıtlı hareket: yakınlaşma, yatay kayma ve konuya doğru hafif dönme (dolaşma + hız dalgalanması ile)."""
        t = np.asarray(t, float)
        e = self._progress(t)
        z0, z1 = self.spec["z"]
        x0, x1 = self.spec["x"]
        y0, y1 = self.spec["yaw"]
        s = self.strength
        if self.spec.get("dolly"):
            # sabit hızla yürüyen kamera: ters ölçek (1/z) zamanla doğrusal değişir
            za, zb = 1 + (z0 - 1) * s, 1 + (z1 - 1) * s
            z = 1.0 / (1.0 / za + (1.0 / zb - 1.0 / za) * e)
        else:
            z = 1 + ((z0 - 1) + ((z1 - 1) - (z0 - 1)) * e) * s
        x = (x0 + (x1 - x0) * e) * s
        yw = (y0 + (y1 - y0) * e) * s
        wander = self.k > 0
        wx = 0.0030 * (np.sin(2 * np.pi * 0.13 * t + self.ph[6]) + 0.6 * np.sin(2 * np.pi * 0.31 * t + self.ph[7])) if wander else 0.0
        wy = 0.0022 * (np.sin(2 * np.pi * 0.11 * t + self.ph[8]) + 0.6 * np.sin(2 * np.pi * 0.27 * t + self.ph[9])) if wander else 0.0
        return z, x + wx * min(self.k, 1.5), wy * min(self.k, 1.5), np.radians(yw)

    # -- homografi ----------------------------------------------------------------------------
    def _core(self, t):
        """Çıktı pikseli -> kaynak pikseli (3x3), satır zamanı farkı olmadan."""
        yaw, pitch, roll, zs = self._shake(t)
        z, x, y, yb = self._base(t)
        orbit = bool(self.spec.get("orbit"))
        phi = float(self._phi(t)) if orbit else 0.0
        if orbit:
            yb = yb - phi                                  # kamera yay üzerinde afişe (hedefe) bakmaya devam eder
        yaw = float(yaw + yb)
        zz = float((1.0 if orbit else z) * zs) * self.z_extra       # yayda yaklaşma zoom ile değil, gerçek konumla yapılır
        f, sw, sh, so = self.f, self.sw, self.sh, self.so
        Ks = np.array([[f, 0, sw / 2], [0, f, sh / 2], [0, 0, 1.0]])
        fo = f * so * zz
        Ko_inv = np.array([[1 / fo, 0, -(self.ow / 2) / fo], [0, 1 / fo, -(self.oh / 2) / fo], [0, 0, 1.0]])
        T = np.array([[1, 0, float(x) * sw], [0, 1, float(y) * sh], [0, 0, 1.0]])
        if orbit:
            # Afiş + duvar tek düzlem (Z=1 birim uzaklık). Kamera, hedef noktasının (afiş merkezi) etrafında r yarıçaplı yayda:
            # C = (r sin(phi), 0, 1 - r cos(phi)). Çıktı -> kaynak: Ks [(1-Cz) I + C n^T] R Ko^-1  (düzlemin ürettiği homografi)
            r = 1.0 / float(z)
            Cx, Cz = r * math.sin(phi), 1.0 - r * math.cos(phi)
            B = np.array([[1 - Cz, 0, Cx], [0, 1 - Cz, 0], [0, 0, 1.0]])
            return T @ Ks @ B @ _R(yaw, float(pitch), float(roll)) @ Ko_inv
        return T @ Ks @ _R(yaw, float(pitch), float(roll)) @ Ko_inv

    def hmap(self, t):
        """Rolling shutter dahil: çıktı -> kaynak homografisi."""
        M = self._core(t)
        if self.readout <= 0 or self.k <= 0:
            return M
        eps = 1.0 / 120
        Mb = self._core(t + eps)
        c = np.array([self.ow / 2, self.oh / 2, 1.0])
        ps = M @ c
        ps /= ps[2]
        pb = np.linalg.inv(Mb) @ ps
        pb /= pb[2]
        vx, vy = (pb[0] - c[0]) / eps, (pb[1] - c[1]) / eps           # içeriğin çıktıdaki hızı (px/sn)
        d, oh = self.readout, self.oh
        A = np.array([[1, -vx * d / oh, vx * d / 2], [0, 1 - vy * d / oh, vy * d / 2], [0, 0, 1.0]])
        return M @ A

    def _corners_src(self, t):
        M = self.hmap(t)
        c = np.array([[0, 0, 1], [self.ow, 0, 1], [self.ow, self.oh, 1], [0, self.oh, 1]], float).T
        p = M @ c
        return (p[:2] / p[2]).T

    # -- kadraj payı --------------------------------------------------------------------------
    def _inside(self, margin=1.5):
        sw, sh = self.sw, self.sh
        for i in range(self.n + 6):
            t = (i - 3) / self.fps
            for dt in (-0.5, 0.0, 0.5):
                p = self._corners_src(t + dt * self.shutter / self.fps)
                if p[:, 0].min() < margin or p[:, 1].min() < margin or p[:, 0].max() > sw - margin or p[:, 1].max() > sh - margin:
                    return False
        return True

    def _fit(self, max_zoom):
        """Kenarlarda boşluk görünmeyecek en küçük yakınlaştırma payını bulur. Pay çok büyüyecekse sallantıyı kısar."""
        # pay, yolun en geniş kadrajında (en küçük yakınlaşma) gerekir; üst sınır max_zoom
        base_low = 1 + (min(self.spec["z"]) - 1) * self.strength
        allowed = max(1.0, max_zoom / max(base_low, 1.0))
        for _ in range(16):
            self.z_extra = allowed
            if self._inside():
                lo, hi = 1.0, allowed                     # hi uygun; en küçük uygun payı ikili aramayla bul
                for _ in range(8):
                    mid = (lo + hi) / 2
                    self.z_extra = mid
                    if self._inside():
                        hi = mid
                    else:
                        lo = mid
                self.z_extra = hi
                return
            self.amp *= 0.85                              # pay sınırı aşılıyor: sallantıyı biraz azalt
        self.z_extra = allowed                            # son çare (kenar boşluğu BORDER_REPLICATE ile kapanır)

    # -- kare çizimi --------------------------------------------------------------------------
    def _grain(self, i):
        if self._grain_pool is None:
            r = np.random.default_rng(self.seed + 1)
            P, H, W = 3, self.oh + 48, self.ow + 48
            pool = []
            for _ in range(P):
                luma = r.standard_normal((H, W, 1)).astype(np.float32)
                luma = cv2.GaussianBlur(luma, (0, 0), 0.7).reshape(H, W, 1) * 1.8      # taneyi biraz yumuşat
                chroma = r.standard_normal((H, W, 3)).astype(np.float32) * 0.35
                pool.append((luma + chroma))
            self._grain_pool = pool
            self._grng = r
        pool = self._grain_pool
        g = pool[(i * 3 + int(self._grng.integers(0, 3))) % len(pool)]
        ox, oy = int(self._grng.integers(0, 48)), int(self._grng.integers(0, 48))
        return g[oy:oy + self.oh, ox:ox + self.ow]

    def render_frame(self, src, i, finish=True):
        """src: uint8 BGR (self.sw x self.sh). i: kare numarası. Hareket bulanıklığı + tane + pozlama uygulanmış kare döner."""
        t = i / self.fps
        shut = self.shutter / self.fps
        flags_hi = cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP
        flags_lo = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP          # alt-örnekler ortalanacağı için doğrusal yeter (2x hızlı)
        if self.k > 0 or self.strength > 0:
            ca = self._corners_src(t - shut / 2)
            cb = self._corners_src(t + shut / 2)
            d = float(np.abs(ca - cb).max())
        else:
            d = 0.0
        K = int(np.clip(math.ceil(d * self.so / 1.1) + 1, 1, 9))
        if K == 1:
            ts = [t]
        else:
            ts = [t + (j / (K - 1) - 0.5) * shut for j in range(K)]
        acc = None
        for tk in ts:
            fr = cv2.warpPerspective(src, self.hmap(tk), (self.ow, self.oh), flags=flags_hi if K == 1 else flags_lo,
                                     borderMode=cv2.BORDER_REPLICATE)
            if acc is None:
                acc = fr.astype(np.float32) if K > 1 else fr
            else:
                acc += fr
        if K > 1:
            out = (acc / K)
        else:
            out = acc.astype(np.float32)
        if finish and self.k > 0:
            g = 1 + 0.010 * self.k * float(self._ns("gain", t)) * self.exposure
            out = out * g
            if self.grain_sigma > 0:
                out = out + self._grain(i) * self.grain_sigma * (0.75 + 0.25 * min(self.k, 1.6))
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)

    def trajectory(self):
        """Test/rapor için: kare başına (yaw, pitch, roll, z, x, y) — derece/oran."""
        ts = np.arange(self.n) / self.fps
        yaw, pitch, roll, zs = self._shake(ts)
        z, x, y, yb = self._base(ts)
        phi = self._phi(ts)
        return {"t": ts, "yaw": np.degrees(yaw + yb - phi), "pitch": np.degrees(pitch), "roll": np.degrees(roll),
                "z": z * zs * self.z_extra, "x": x, "y": y, "orbit": np.degrees(phi) * np.ones_like(ts)}


# ----------------------------------------------------------------------------
def render(photo_bgr, out_path, move="yakinlas", seconds=6.0, fps=30, long_side=1920, handheld=DEFAULT_LEVEL,
           strength=1.0, progress=None, seed=11):
    """photo_bgr (uint8) -> out_path (mp4, H.264). Çıktı oranı fotoğrafla aynıdır. Kare sayısını döndürür.

    handheld: 'sabit' | 'sakin' | 'yuruyus' | 'belirgin' ya da doğrudan sayı (1.0 = yürüyen el).
    """
    H, W = photo_bgr.shape[:2]
    spec = MOVES.get(move) or MOVES["yakinlas"]
    zmax = (1 + (max(spec["z"]) - 1) * strength) * 1.12
    # çok yaklaşan hareketlerde en yakın karede görüntü en fazla ~1.3 kat büyütülsün (yazı bulanıklaşmasın)
    oh_cap = max(1280, int(H * 1.3 / zmax))
    oh = int(min(long_side, H, oh_cap)) // 2 * 2
    ow = int(round(oh * W / H)) // 2 * 2
    k = level_value(handheld)
    # kaynağı, en yakın planda yaklaşık 1:1 örnekleme olacak boyuta getir (bulanıklık ve takılma olmasın)
    f = min(1.0, ow * zmax / W)
    src = cv2.resize(photo_bgr, (max(2, int(round(W * f))), max(2, int(round(H * f)))), interpolation=cv2.INTER_AREA) if f < 1 else photo_bgr
    sh, sw = src.shape[:2]
    rig = CameraRig(sw, sh, ow, oh, seconds, fps, move, intensity=k, strength=strength, seed=seed)
    sink = vr.make_sink(out_path, float(fps), crf=17)
    try:
        for i in range(rig.n):
            sink.write(rig.render_frame(src, i))
            if progress and i % 6 == 0:
                progress(i + 1, rig.n)
        sink.close()
    except BaseException:
        sink.abort()
        raise
    return rig.n

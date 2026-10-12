"""
Video yazı onarımı: yapay zeka videosundaki bozulmuş/kaymış baskıyı, ORİJİNAL yüksek çözünürlüklü
tasarımla kare kare yeniden yerleştirir.

Fikir:
  1) Video modeline, tasarımın yerleştirildiği fotoğrafı (referans kare) başlangıç karesi olarak veririz.
  2) Her video karesi için, "bu karedeki her piksel referans karenin neresine denk geliyor?" haritası (P_t)
     yoğun optik akışla bulunur. Sadece art arda kareler arasındaki akışı toplamak zamanla sürüklenir;
     bu yüzden her karede referans kareye karşı küçük bir düzeltme akışı daha hesaplanır (çapa).
  3) Referanstaki baskı modeli (piksel -> tasarım koordinatı) P_t ile bu kareye taşınır, orijinal tasarım
     2x süper-örneklemeyle çizilir. Zemin = referansın boş (baskısız) afişi, aynı P_t ile taşınmış.
  4) Baskı çevresindeki baskısız kumaştan ışık farkı ölçülüp (yumuşak kazanç) uygulanır.

Bilinen sınırlar:
  - Afişin önünden geçen nesneler (el, balon) maskelenmez; baskının üstüne biner.
  - Kumaş kıvrım gölgeleri, referans karedeki halleriyle taşınır; video süresince çok değişirse
    kıvrım ışığı eski kalabilir. Dalgalanma hafifken sorun olmaz.
  - Afiş kadrajdan çıkar ya da kapanırsa takip güvenilmez olur; kalite metrikleri bunu işaretler.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import cv2
import numpy as np

import cvio


# ----------------------------------------------------------------------------
class Flow:
    """a(p) ≈ b(p + f(p)) olacak şekilde f(p) döndürür (a'dan b'ye geri akış)."""

    def __init__(self, long_side=960):
        self.long = long_side
        self.dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

    @staticmethod
    def _g(img, s):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if s < 1:
            g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        return cv2.GaussianBlur(g, (0, 0), 1.0)

    def __call__(self, a, b):
        H, W = a.shape[:2]
        s = min(1.0, self.long / max(H, W))
        f = self.dis.calc(self._g(a, s), self._g(b, s), None)
        if s < 1:
            f = cv2.resize(f, (W, H), interpolation=cv2.INTER_LINEAR) / s
        return f.astype(np.float32)


class Tracker:
    """Her video karesi için P_t: kare pikseli -> referans görsel koordinatı (H,W,2 float32).

    TASARIM KARARLARI (iki başarısız denemeden sonra, sentetik testle doğrulandı):
      * Yapay zeka yazıyı bozar. Yazıyı dar ölçekte izleyen akış, temiz tasarımı da bozuk şekle uydurur
        (ilk deneme: yazı bozuk çıktı). Bu yüzden akış ÇOK GENİŞ ölçekte (sigma ~40 px) yumuşatılır:
        harf boyutundaki bozulmalar ortalamada kaybolur, kumaşın yavaş dalgalanması ve kamera hareketi kalır.
      * Kumaşın düz bölgelerinde akış gürültülüdür ve rastgele sürüklenir (ikinci deneme: dağıldı).
        Bu yüzden yumuşatma güven ağırlıklıdır: yalnızca kenarı/deseni olan piksellerden ortalama alınır.
      * Her karede referans kareye karşı çapa atılır (kareler arası akış biriktirilmez), sürüklenme birikmez.
    Sınır: sigma büyük olduğu için çok yüksek frekanslı kumaş kıpırtısı (kırışıklık titremesi) takip edilmez.
    """

    def __init__(self, ref_bgr, sigma=40.0, iters=3, flow_long=960):
        self.ref = ref_bgr
        self.H, self.W = ref_bgr.shape[:2]
        self.flow = Flow(flow_long)
        self.sigma = sigma
        self.iters = iters
        gx, gy = np.meshgrid(np.arange(self.W, dtype=np.float32), np.arange(self.H, dtype=np.float32))
        self.grid = np.stack([gx, gy], -1)
        self.P = None

    @staticmethod
    def _sample(arr, coords):
        return cv2.remap(arr, coords[..., 0], coords[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def update(self, frame_u8):
        P = self.grid.copy() if self.P is None else self.P
        for _ in range(self.iters):
            wref = self._sample(self.ref, P)                       # referansın bu karedeki beklenen görünümü
            r = self.flow(frame_u8, wref)                          # frame(p) ≈ wref(p + r)
            g = cv2.GaussianBlur(cv2.cvtColor(wref, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2)
            gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
            e = gx * gx + gy * gy
            w = np.minimum(e, np.percentile(e, 95)) + 1e-3 * (e.mean() + 1e-6)     # güven: yerel kenar enerjisi
            num = cv2.GaussianBlur(r * w[..., None], (0, 0), self.sigma)
            den = cv2.GaussianBlur(w, (0, 0), self.sigma)[..., None]
            P = self._sample(P, self.grid + num / np.maximum(den, 1e-9))
        self.P = P
        return P


# ----------------------------------------------------------------------------
class Renderer:
    def __init__(self, ref_bgr, blank_bgr, design, model, scene_size, ss=2):
        """
        ref_bgr   : başlangıç karesi olarak videoya verilen, tasarımlı fotoğraf (video boyutuna getirilmiş)
        blank_bgr : aynı sahnenin BOŞ afişli hali (aynı boyut)
        design    : float32 BGR [0,1] orijinal tasarım (yüksek çözünürlük)
        model     : compositor.composite(return_model=True) çıktısı
        scene_size: modelin hesaplandığı sahne boyutu (W,H)
        """
        self.H, self.W = ref_bgr.shape[:2]
        self.ss = ss
        # Tasarım 8000 px gibi çok büyükse her karede yeniden küçültmek yavaştır: bir kez, kare boyutunun
        # ~2.5 katına (süper-örnekleme için yeterli) küçült.
        cap = 2.5 * max(self.H, self.W)
        dl = max(design.shape[:2])
        if dl > cap:
            design = cv2.resize(design, None, fx=cap / dl, fy=cap / dl, interpolation=cv2.INTER_AREA)
        self.design = design
        self.paper = model.get("paper")
        self.ink = float(model.get("ink", 1.0))
        Ws, Hs = scene_size
        u0 = np.full((Hs, Ws), -5.0, np.float32)
        v0 = np.full((Hs, Ws), -5.0, np.float32)
        a0 = np.zeros((Hs, Ws), np.float32)
        x0, y0, x1, y1 = model["bbox"]
        u0[y0:y1, x0:x1], v0[y0:y1, x0:x1], a0[y0:y1, x0:x1] = model["u"], model["v"], model["alpha"]
        if (Ws, Hs) != (self.W, self.H):
            u0 = cv2.resize(u0, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
            v0 = cv2.resize(v0, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
            a0 = cv2.resize(a0, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        self.u0, self.v0, self.a0 = u0, v0, a0
        self.blank = blank_bgr.astype(np.float32) / 255.0

    @staticmethod
    def _sample(arr, P, interp=cv2.INTER_LINEAR):
        return cv2.remap(arr, P[..., 0], P[..., 1], interp, borderMode=cv2.BORDER_REPLICATE)

    def render(self, frame_bgr, P):
        a = self._sample(self.a0, P)
        ys, xs = np.where(a > 0.003)
        if len(ys) == 0:
            return frame_bgr, {"print_px": 0}
        pad = 40
        y0, y1 = max(0, ys.min() - pad), min(self.H, ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(self.W, xs.max() + pad + 1)
        Pc = np.ascontiguousarray(P[y0:y1, x0:x1])
        a = a[y0:y1, x0:x1]
        frame = frame_bgr[y0:y1, x0:x1].astype(np.float32) / 255.0
        blank_t = self._sample(self.blank, P)[y0:y1, x0:x1]
        u = self._sample(self.u0, P)[y0:y1, x0:x1]
        v = self._sample(self.v0, P)[y0:y1, x0:x1]

        # --- ışık kazancı: baskı dışındaki kumaş halkasından ---
        core = (a > 0.5).astype(np.uint8)
        ring = ((a < 0.02) & (cv2.dilate(core, np.ones((41, 41), np.uint8)) > 0)
                & (cv2.dilate((a > 0.02).astype(np.uint8), np.ones((9, 9), np.uint8)) == 0)).astype(np.float32)
        # Kazanç yalnızca parlaklıktan hesaplanır (renk tonu kaymasın) ve yalnızca halkadaki KUMAŞ/KÂĞIT benzeri
        # piksellerden (çerçeve, duvar, arka plan ışık ölçümünü bozar: ilk denemede baskı üstünde parlak lekeler çıktı).
        lum = lambda x: x[..., 0] * 0.114 + x[..., 1] * 0.587 + x[..., 2] * 0.299
        fl, bl = lum(cv2.GaussianBlur(frame, (0, 0), 3)), lum(cv2.GaussianBlur(blank_t, (0, 0), 3))
        core_m = core.astype(bool)
        paper_l = float(np.median(bl[core_m])) if core_m.any() else 1.0
        sel = ring * (np.abs(bl - paper_l) < 0.10)
        ratio = np.clip(fl / np.maximum(bl, 1e-3), 0.6, 1.6)
        wsum = cv2.GaussianBlur(sel, (0, 0), 25)
        gain = cv2.GaussianBlur(ratio * sel, (0, 0), 25) / np.maximum(wsum, 1e-4)
        conf = np.clip(wsum / 0.02, 0, 1)                                 # uygun halka yoksa kazanç 1
        gain = np.clip(1 + (gain - 1) * conf, 0.85, 1.18)[..., None]

        # --- süper-örnekli tasarım çizimi ---
        ss = self.ss
        uu = cv2.resize(u, None, fx=ss, fy=ss, interpolation=cv2.INTER_LINEAR)
        vv = cv2.resize(v, None, fx=ss, fy=ss, interpolation=cv2.INTER_LINEAR)
        dh, dw = self.design.shape[:2]
        core_b = core.astype(bool)
        if core_b.sum() > 50:
            sx = np.median(np.abs(np.gradient(u, axis=1))[core_b]) * (dw - 1) / ss
            sy = np.median(np.abs(np.gradient(v, axis=0))[core_b]) * (dh - 1) / ss
            s = max(sx, sy)
        else:
            s = 1.0
        design = self.design
        if s > 1.25:                                                       # tasarım hedeften çok büyük: ön küçült
            design = cv2.resize(design, (max(2, int(dw / s)), max(2, int(dh / s))), interpolation=cv2.INTER_AREA)
        dh2, dw2 = design.shape[:2]
        warped = cv2.remap(design, (uu * (dw2 - 1)).astype(np.float32), (vv * (dh2 - 1)).astype(np.float32),
                           cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        warped = cv2.resize(warped, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)

        d = warped if self.paper is None else np.clip(warped / np.asarray(self.paper, np.float32)[None, None, :], 0, 1)
        d = 1.0 - self.ink * (1.0 - d)
        printed = np.clip(blank_t * gain * d, 0, 1)
        al = a[..., None]
        out_c = frame * (1 - al) + printed * al

        out = frame_bgr.copy()
        out[y0:y1, x0:x1] = np.clip(out_c * 255 + 0.5, 0, 255).astype(np.uint8)
        return out, {"print_px": int(core_b.sum()), "gain": float(np.mean(gain[core_b])) if core_b.any() else 1.0,
                     "design_shrink": float(s), "crop": [int(x0), int(y0), int(x1), int(y1)]}


# ----------------------------------------------------------------------------
def _ncc(frame, warped_ref, mask):
    """Baskı bölgesinde yüksek frekanslı yapı korelasyonu (takip hizası göstergesi, -1..1)."""
    def hp(img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return cv2.GaussianBlur(g, (0, 0), 1.5) - cv2.GaussianBlur(g, (0, 0), 6)
    a, b = hp(frame)[mask], hp(warped_ref)[mask]
    if a.size < 100 or a.std() < 1e-6 or b.std() < 1e-6:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def repair_frames(frames, ref_bgr, blank_bgr, design, model, scene_size, *, sigma=40.0, ss=2, flow_long=960):
    """frames: BGR uint8 kare üreteci. (onarılmış_kare, metrik_sözlüğü, P_t) üretir."""
    tr = rd = None
    hist = []                                  # baskı alanı ortalama koordinatı geçmişi (sıçrama ölçümü için)
    for i, fr in enumerate(frames):
        if tr is None:
            H, W = fr.shape[:2]
            ref = cv2.resize(ref_bgr, (W, H), interpolation=cv2.INTER_AREA) if ref_bgr.shape[:2] != (H, W) else ref_bgr
            blank = cv2.resize(blank_bgr, (W, H), interpolation=cv2.INTER_AREA) if blank_bgr.shape[:2] != (H, W) else blank_bgr
            rd = Renderer(ref, blank, design, model, scene_size, ss=ss)
            tr = Tracker(ref, sigma=sigma, flow_long=flow_long)
        P = tr.update(fr)
        out, info = rd.render(fr, P)
        a = cv2.remap(rd.a0, P[..., 0], P[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mask = a > 0.5
        info["ncc"] = _ncc(fr, cv2.remap(ref, P[..., 0], P[..., 1], cv2.INTER_LINEAR), mask) if mask.any() else 0.0
        info["visible"] = float(mask.sum()) / max(float((rd.a0 > 0.5).sum()), 1.0)
        # zamansal düzgünlük: baskı alanındaki ortalama P'nin ikinci farkı (piksel)
        if mask.any():
            hist.append(P[mask].mean(0))
            if len(hist) >= 3:
                info["jitter"] = float(np.linalg.norm(hist[-1] - 2 * hist[-2] + hist[-3]))
        info["frame"] = i
        yield out, info, P


def summarize(infos, *, ncc_min=0.35, visible_min=0.85, jitter_max=2.5):
    """Video takip kalitesi özeti. Eşikler başlangıç değeri, gerçek videolarla ayarlanmalı."""
    ncc = np.array([i["ncc"] for i in infos])
    vis = np.array([i["visible"] for i in infos])
    jit = np.array([i.get("jitter", 0.0) for i in infos])
    reasons = []
    if (ncc < ncc_min).mean() > 0.1:
        reasons.append(f"takip hizası zayıf (kare başına korelasyon düşük: %{(ncc < ncc_min).mean() * 100:.0f} kare)")
    if vis.min() < visible_min:
        reasons.append(f"afiş kadraja taşıyor/kapanıyor (en düşük görünürlük %{vis.min() * 100:.0f})")
    if jit.max() > jitter_max:
        reasons.append(f"takipte sıçrama (en büyük {jit.max():.1f} px)")
    return {"ok": not reasons, "reasons": reasons, "ncc_min": float(ncc.min()), "ncc_mean": float(ncc.mean()),
            "visible_min": float(vis.min()), "jitter_max": float(jit.max()), "frames": len(infos)}


# ----------------------------------------------------------------------------
def find_ffmpeg():
    """Sistemdeki ffmpeg'i ya da imageio-ffmpeg paketinin getirdiği ffmpeg'i bulur (Windows'ta ayrı kurulum gerekmez)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def iter_video(path):
    """Videoyu kare kare okur. (Yolda Türkçe karakter varsa dosya ASCII geçici klasöre kopyalanır.)"""
    with cvio.AsciiCopy(path) as p:
        cap = cv2.VideoCapture(p)
        try:
            while True:
                ok, f = cap.read()
                if not ok:
                    break
                yield f
        finally:
            cap.release()


def video_info(path):
    with cvio.AsciiCopy(path) as p:
        cap = cv2.VideoCapture(p)
        info = {"fps": cap.get(cv2.CAP_PROP_FPS) or 24.0, "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
        cap.release()
    return info


def read_video(path):
    frames = list(iter_video(path))
    return frames, video_info(path)["fps"]


class VideoSink:
    """Kareleri diske akıtarak yazar (hepsini belleğe yığmaz). ffmpeg varsa H.264 olarak sıkıştırır.
    Tüm ara dosyalar ASCII bir geçici klasörde tutulur (Windows'ta Türkçe karakterli yollar sorun çıkarır);
    bitince nihai dosya yerine taşınır."""

    def __init__(self, path, fps=24.0, crf=14, audio_from=None):
        self.path, self.fps, self.crf, self.audio_from = path, fps, crf, audio_from
        self.dir = cvio.ascii_tempdir()
        self.tmp = os.path.join(self.dir, "ham.mp4")
        self.vw = None
        self.n = 0

    def write(self, frame):
        if self.vw is None:
            H, W = frame.shape[:2]
            self.vw = cv2.VideoWriter(self.tmp, cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (W, H))
        self.vw.write(frame)
        self.n += 1

    def abort(self):
        try:
            if self.vw is not None:
                self.vw.release()
        finally:
            shutil.rmtree(self.dir, ignore_errors=True)

    def close(self):
        try:
            if self.vw is None:
                raise ValueError("kare yok")
            self.vw.release()
            out = os.path.join(self.dir, "son.mp4")
            ff = find_ffmpeg()
            done = False
            if ff:
                with cvio.AsciiCopy(self.audio_from) if self.audio_from else _Null() as audio:
                    cmd = [ff, "-y", "-loglevel", "error", "-i", self.tmp]
                    if audio:
                        cmd += ["-i", audio, "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "aac", "-shortest"]
                    cmd += ["-c:v", "libx264", "-crf", str(self.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
                    r = subprocess.run(cmd, capture_output=True, text=True)
                    done = r.returncode == 0 and os.path.exists(out)
            src = out if done else self.tmp          # ffmpeg yoksa: mp4v (bazı oynatıcılar/tarayıcılar açmayabilir)
            if not os.path.exists(src) or os.path.getsize(src) == 0:
                raise RuntimeError("video dosyası yazılamadı")
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            shutil.move(src, self.path)
            return self.path
        finally:
            shutil.rmtree(self.dir, ignore_errors=True)


class PipeSink:
    """Kareleri doğrudan ffmpeg'e (libx264) akıtır: ara 'mp4v' sıkıştırması olmadığı için kalite kaybı olmaz,
    film greni gibi ince ayrıntılar da korunur. Arayüzü VideoSink ile aynıdır (write / close / abort)."""

    def __init__(self, path, fps=30.0, crf=17):
        ff = find_ffmpeg()
        if not ff:
            raise RuntimeError("ffmpeg bulunamadı")
        self.ff, self.path, self.fps, self.crf = ff, path, float(fps), int(crf)
        self.dir = cvio.ascii_tempdir()
        self.out = os.path.join(self.dir, "son.mp4")
        self.errf = os.path.join(self.dir, "ffmpeg.log")
        self.proc = None
        self._err = None
        self.n = 0

    def _start(self, frame):
        H, W = frame.shape[:2]
        if W % 2 or H % 2:
            raise ValueError("video boyutları çift sayı olmalı")
        cmd = [self.ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
               "-r", f"{self.fps:g}", "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(self.crf),
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", self.out]
        self._err = open(self.errf, "wb")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._err)

    def write(self, frame):
        if self.proc is None:
            self._start(frame)
        try:
            self.proc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        except (BrokenPipeError, OSError):
            raise RuntimeError("ffmpeg videoyu yazamadı: " + self._tail())
        self.n += 1

    def _tail(self):
        try:
            self._err.flush()
            with open(self.errf, "rb") as f:
                return f.read()[-400:].decode("utf-8", "replace")
        except Exception:
            return ""

    def abort(self):
        try:
            if self.proc is not None:
                try:
                    self.proc.stdin.close()
                except Exception:
                    pass
                self.proc.kill()
                self.proc.wait()
            if self._err:
                self._err.close()
        finally:
            shutil.rmtree(self.dir, ignore_errors=True)

    def close(self):
        try:
            if self.proc is None:
                raise ValueError("kare yok")
            self.proc.stdin.close()
            rc = self.proc.wait()
            self._err.close()
            if rc != 0 or not os.path.exists(self.out) or os.path.getsize(self.out) == 0:
                raise RuntimeError("video dosyası yazılamadı: " + self._tail())
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            shutil.move(self.out, self.path)
            return self.path
        finally:
            shutil.rmtree(self.dir, ignore_errors=True)


def make_sink(path, fps=30.0, crf=17):
    """ffmpeg varsa doğrudan H.264 hattı, yoksa eski yöntem."""
    try:
        return PipeSink(path, fps, crf)
    except RuntimeError:
        return VideoSink(path, fps, crf)


class _Null:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def write_video(frames, path, fps=24.0, crf=14, audio_from=None):
    if not frames:
        raise ValueError("kare yok")
    sink = VideoSink(path, fps, crf, audio_from)
    try:
        for f in frames:
            sink.write(f)
        return sink.close()
    except BaseException:
        sink.abort()
        raise


def repair_video(video_in, video_out, ref_bgr, blank_bgr, design, model, scene_size, keep_audio=False, progress=None, **kw):
    """Akışlı onarım: kareler tek tek okunur, onarılır, yazılır. (özet, kare metrikleri) döner."""
    vi = video_info(video_in)
    sink = VideoSink(video_out, vi["fps"], audio_from=video_in if keep_audio else None)
    infos = []
    try:
        for out, info, _ in repair_frames(iter_video(video_in), ref_bgr, blank_bgr, design, model, scene_size, **kw):
            sink.write(out)
            infos.append(info)
            if progress:
                progress(len(infos), vi["frames"])
        sink.close()
    except BaseException:
        sink.abort()
        raise
    return summarize(infos), infos

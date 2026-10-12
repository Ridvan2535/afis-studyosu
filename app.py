# -*- coding: utf-8 -*-
"""
Yerel arayüz sunucusu (ek paket gerektirmez). Çift tıklayınca tarayıcıda açılır; yalnızca bu bilgisayardan erişilir.

  python app.py            -> sunucuyu başlatır ve tarayıcıyı açar
  python app.py --no-browser

Güvenlik: sadece 127.0.0.1'e bağlanır; yalnızca localhost Host başlıklarını kabul eder; POST istekleri özel bir
başlık ister (başka web sitelerinin gizlice istek yollamasını engeller). API anahtarları ayarlar.json'da, bu bilgisayarda durur.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import refstore                                              # noqa: E402
import camera_move                                            # noqa: E402
import cvio                                                   # noqa: E402
import orchestrator as orch                                   # noqa: E402
import product                                                # noqa: E402
from orchestrator import Cancelled, Orchestrator              # noqa: E402
from providers import AuthError, ProviderError, Settings, check_key, scene_arms, video_arms   # noqa: E402
from selector import nice, overview   # noqa: E402

UPLOAD_DIR = os.path.join(HERE, "yuklemeler")
MAX_DESIGN = 250 * 1024 * 1024
MAX_REF = 40 * 1024 * 1024
PORT_RANGE = range(7860, 7890)
CATEGORIES = list(__import__("prompts").CATEGORIES.keys())
SETTING_FIELDS = ["auto_video_move", "auto_video_kind", "scene_provider", "video_provider", "video_mode", "camera_move", "handheld", "openai_model", "gemini_model", "video_resolution",
                  "max_scene_calls", "max_video_tries", "photo_long_side", "seconds"]
FIXED_TYPES = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp", ".zip": "application/zip", ".json": "application/json"}   # Windows kayıt defterine güvenme
INT_FIELDS = {"max_scene_calls", "max_video_tries", "photo_long_side", "seconds"}


class Runner:
    """Tek seferde tek iş: ilerleme, kayıt satırları ve sonuç burada tutulur."""

    def __init__(self):
        self.lock = threading.Lock()
        self.s = {"running": False, "kind": None, "frac": 0.0, "text": "", "logs": [], "error": None,
                  "job": None, "result": None, "finished": 0}
        self.cancel_flag = False
        self.design = None
        self.refs: list[str] = []

    def snapshot(self):
        with self.lock:
            d = dict(self.s)
            d["logs"] = list(d["logs"][-120:])
            d["design"] = os.path.basename(self.design) if self.design else None
            d["refs"] = len(self.refs)
            return d

    def _set(self, **kw):
        with self.lock:
            self.s.update(kw)

    def _log(self, msg):
        with self.lock:
            self.s["logs"].append(f"{time.strftime('%H:%M:%S')}  {msg}")
            self.s["logs"] = self.s["logs"][-300:]

    def start(self, kind, work):
        with self.lock:
            if self.s["running"]:
                return False
            self.cancel_flag = False
            self.s.update(running=True, kind=kind, frac=0.0, text="Başlıyor…", error=None, result=None)
        threading.Thread(target=self._run, args=(work,), daemon=True).start()
        return True

    def _run(self, work):
        settings = Settings.load()
        o = Orchestrator(settings, log=self._log, progress=lambda f, t: self._set(frac=f, text=t),
                         cancel=lambda: self.cancel_flag)
        try:
            res = work(o, settings)
            self._set(result=res)
        except Cancelled:
            self._log("Kullanıcı durdurdu.")
            self._set(error="Durduruldu.")
        except AuthError as e:
            self._log(f"HATA: {e}")
            self._set(error=str(e))
        except ProviderError as e:
            self._log(f"HATA: {e}")
            self._set(error=str(e))
        except Exception as e:     # beklenmeyen: ayrıntı kayıt dosyasına, arayüze kısa mesaj
            tb = traceback.format_exc()
            o.log("BEKLENMEYEN HATA:\n" + tb)
            self._set(error=f"Beklenmeyen hata: {e.__class__.__name__}: {e}  ('Hata raporu' düğmesiyle bana gönder)")
        finally:
            self._set(running=False, finished=self.s["finished"] + 1)


RUN = Runner()


def safe_join(base, *parts):
    p = os.path.realpath(os.path.join(base, *parts))
    if p != os.path.realpath(base) and not p.startswith(os.path.realpath(base) + os.sep):
        return None
    return p


class Handler(BaseHTTPRequestHandler):
    server_version = "AfisStudyo"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # -- yardımcılar ----------------------------------------------------------------
    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("localhost", "127.0.0.1", "[::1]")

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if code >= 400 and self.command == "POST":
            # istek gövdesi okunmamış olabilir: bağlantıyı kapat ki artık veri sonraki istek sanılmasın
            self.send_header("Connection", "close")
            self.close_connection = True
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("istek çok büyük")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            raise ValueError("istek okunamadı")

    def _guard_post(self):
        if not self._host_ok() or self.headers.get("X-Afis") != "1":
            self._send(403, {"hata": "izin yok"})
            return False
        return True

    # -- GET ----------------------------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"hata": "izin yok"})
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/":
                with open(os.path.join(HERE, "ui.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._send(200, RUN.snapshot())
            if u.path == "/api/config":
                s = Settings.load()
                d = s.public()
                d["categories"] = CATEGORIES
                d["moves"] = [[k, v["ad"]] for k, v in camera_move.MOVES.items()]
                d["handheld_levels"] = [[k, v["ad"]] for k, v in camera_move.HANDHELD_LEVELS.items()]
                d["ffmpeg"] = bool(__import__("video_repair").find_ffmpeg())
                d["surum"] = orch.VERSION
                d["olculer"] = [[k, product.olcu_etiketi(k), round(w / h, 4)] for k, (w, h) in product.OLCULER.items()]
                d["ornek_olcu"] = s.ornek_olcu if s.ornek_olcu in product.OLCULER else product.VARSAYILAN_ORNEK_OLCU
                d["servisler"] = {"sahne": [[n, nice(n)] for n in scene_arms(s)], "video": [[n, nice(n)] for n in video_arms(s)]}
                return self._send(200, d)
            if u.path == "/api/refs":
                return self._send(200, {"liste": refstore.list_refs(q.get("category", [CATEGORIES[0]])[0])})
            if u.path.startswith("/refs/"):
                return self._file(safe_join(refstore.ROOT, urllib.parse.unquote(u.path[len("/refs/"):])))
            if u.path == "/api/tasarim_kontrol":
                return self._send(*self._design_check(q.get("olcu", [""])[0]))
            if u.path == "/api/tasarim_onizleme":
                return self._design_preview(q.get("olcu", [""])[0])
            if u.path == "/api/karne":
                return self._send(200, overview(orch.STATS_PATH))
            if u.path == "/api/jobs":
                return self._send(200, Orchestrator.list_jobs())
            if u.path == "/api/job":
                return self._send(200, self._job_info(q.get("name", [""])[0]))
            if u.path == "/api/report":
                if RUN.s["running"]:
                    return self._send(409, {"hata": "bir iş çalışıyor, bitince tekrar dene"})
                job = q.get("job", [""])[0]
                jp = safe_join(orch.JOBS_DIR, job) if job else None
                path = Orchestrator(Settings.load()).make_report(jp if jp and os.path.isdir(jp) else None)
                return self._send(200, {"dosya": os.path.basename(path), "klasor": orch.REPORT_DIR})
            if u.path.startswith("/files/"):
                rel = urllib.parse.unquote(u.path[len("/files/"):])
                p = safe_join(orch.JOBS_DIR, rel)
                return self._file(p)
            if u.path.startswith("/rapor/"):
                p = safe_join(orch.REPORT_DIR, urllib.parse.unquote(u.path[len("/rapor/"):]))
                return self._file(p, download=True)
            return self._send(404, {"hata": "yok"})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self._send(500, {"hata": f"{e.__class__.__name__}: {e}"})

    do_HEAD = do_GET

    def _file(self, p, download=False):
        if not p or not os.path.isfile(p):
            return self._send(404, {"hata": "dosya yok"})
        size = os.path.getsize(p)
        ctype = (FIXED_TYPES.get(os.path.splitext(p)[1].lower()) or mimetypes.guess_type(p)[0]
                 or "application/octet-stream")
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                if start > end:
                    return self._send(416, b"", extra={"Content-Range": f"bytes */{size}"})
                code = 206
        extra = {"Accept-Ranges": "bytes"}
        if code == 206:
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        if download:
            extra["Content-Disposition"] = f'attachment; filename="{os.path.basename(p)}"'
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(p, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _job_info(self, name):
        jp = safe_join(orch.JOBS_DIR, name) if name else None
        if not jp or not os.path.isdir(jp):
            return {"hata": "iş bulunamadı"}
        rap = Orchestrator.report_of(jp)
        base = f"/files/{urllib.parse.quote(name)}/"
        photos = [dict(p, url=base + "foto/" + p["ad"],
                       gizli_url=(base + urllib.parse.quote(p["gizli_onizleme"]) if p.get("gizli_onizleme") else None))
                  for p in rap.get("fotograflar", [])]
        oran_url = base + "onizleme_oran.png" if os.path.exists(os.path.join(jp, "onizleme_oran.png")) else None
        videos = [dict(v, url=base + v["dosya"]) for v in rap.get("videolar", [])]
        ov = os.path.exists(os.path.join(jp, "foto", "_ozet.jpg"))
        return {"name": name, "kategori": rap.get("kategori"), "fotograflar": photos, "elenenler": rap.get("elenenler", []),
                "videolar": videos, "son_uretim": rap.get("son_uretim"), "ozet": base + "foto/_ozet.jpg" if ov else None,
                "servis_karnesi": rap.get("servis_karnesi", []), "insanli": bool(rap.get("insanli")),
                "urun_profili": rap.get("urun_profili"), "tasarim_kontrol": rap.get("tasarim_kontrol"), "durum": rap.get("durum"),
                "bekleme_nedeni": rap.get("bekleme_nedeni"), "oran_onizleme": oran_url,
                "islem": rap.get("islem"), "kaynak_is": rap.get("kaynak_is"), "saglayici_cagrisi": rap.get("saglayici_cagrisi"),
                "yeniden_birlestirilebilir": any(p.get("stem") and os.path.exists(os.path.join(jp, "sahneler_bos", p["stem"] + ".png"))
                                                 for p in rap.get("fotograflar", []))}

    # -- tasarım kontrolü (ürün profili) -------------------------------------------------
    @staticmethod
    def _olcu(raw):
        return raw if raw in product.OLCULER else (Settings.load().ornek_olcu if Settings.load().ornek_olcu in product.OLCULER
                                                    else product.VARSAYILAN_ORNEK_OLCU)

    def _design_check(self, olcu):
        if not RUN.design or not os.path.exists(RUN.design):
            return 400, {"hata": "Önce bir tasarım dosyası yükle."}
        prof = product.profil_olustur(self._olcu(olcu))
        k = product.tasarim_kontrol(RUN.design, prof)
        k["olcu_etiketi"] = product.olcu_etiketi(prof.olcu_id)
        k["uyan_olculer"] = product.uyan_olculer(k["png_oran"])
        return 200, k

    def _design_preview(self, olcu):
        if not RUN.design or not os.path.exists(RUN.design):
            return self._send(404, {"hata": "tasarım yok"})
        import cv2
        img = product.oran_onizleme(RUN.design, product.profil_olustur(self._olcu(olcu)), height=700)
        ok, buf = cv2.imencode(".png", img)
        return self._send(200, buf.tobytes(), "image/png")

    # -- POST ---------------------------------------------------------------------------
    def do_POST(self):
        if not self._guard_post():
            return
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/api/upload":
                return self._upload(q)
            if u.path == "/api/ref_upload":
                return self._ref_upload(q)
            body = self._json_body()
            if u.path == "/api/settings":
                return self._settings(body)
            if u.path == "/api/check_key":
                return self._send(200, {"sonuc": check_key(body.get("name", ""), Settings.load())})
            if u.path == "/api/ref_delete":
                return self._send(200, {"tamam": refstore.delete(body.get("category", ""), body.get("name", ""))})
            if u.path == "/api/ref_desc":
                return self._send(200, {"tamam": refstore.set_desc(body.get("category", ""), body.get("name", ""), body.get("desc", ""))})
            if u.path == "/api/start_photos":
                return self._start_photos(body)
            if u.path == "/api/start_video":
                return self._start_video(body)
            if u.path == "/api/yeniden_birlestir":
                return self._recompose(body)
            if u.path == "/api/cancel":
                RUN.cancel_flag = True
                return self._send(200, {"tamam": True})
            return self._send(404, {"hata": "yok"})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self._send(500, {"hata": f"{e.__class__.__name__}: {e}"})

    def _upload(self, q):
        kind = q.get("kind", ["design"])[0]
        name = os.path.basename(urllib.parse.unquote(q.get("name", ["dosya"])[0])) or "dosya"
        ext = os.path.splitext(name)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            return self._send(400, {"hata": "Yalnızca PNG, JPG ya da WEBP yükleyebilirsin."})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > (MAX_DESIGN if kind == "design" else MAX_REF):
            return self._send(400, {"hata": "Dosya boş ya da çok büyük."})
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(UPLOAD_DIR, f"{stamp}_{kind}{ext}")
        left = n
        with open(path, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        import cv2
        im = cvio.imread(path, cv2.IMREAD_UNCHANGED)
        if im is None:
            os.remove(path)
            return self._send(400, {"hata": "Görsel okunamadı."})
        h, w = im.shape[:2]
        if kind == "design":
            RUN.design = path
        else:
            RUN.refs = (RUN.refs + [path])[-4:]
        res = {"genislik": w, "yukseklik": h, "oran": round(w / h, 3), "ad": os.path.basename(path)}
        if kind == "design":
            code, k = self._design_check(q.get("olcu", [""])[0])
            if code == 200:
                res["kontrol"] = k
        return self._send(200, res)

    def _ref_upload(self, q):
        cat = q.get("category", [CATEGORIES[0]])[0]
        name = urllib.parse.unquote(q.get("name", ["referans.jpg"])[0])
        if os.path.splitext(name)[1].lower() not in refstore.EXTS:
            return self._send(400, {"hata": "Yalnızca PNG, JPG ya da WEBP yükleyebilirsin."})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_REF:
            return self._send(400, {"hata": "Dosya boş ya da çok büyük."})
        data = self.rfile.read(n)
        try:
            info = refstore.add(cat, name, data)
        except ValueError as e:
            return self._send(400, {"hata": str(e)})
        return self._send(200, info)

    def _settings(self, body):
        s = Settings.load()
        for k in body.get("clear", []):
            if k in ("magnific_key", "openai_key", "gemini_key", "topview_key", "topview_uid"):
                setattr(s, k, "")
        for k in ("magnific_key", "openai_key", "gemini_key", "topview_key", "topview_uid"):
            v = (body.get(k) or "").strip()
            if v and "…" not in v and "•" not in v:
                setattr(s, k, v)
        if "strict_layout" in body:
            s.strict_layout = bool(body["strict_layout"])
        if isinstance(body.get("ribbon_colors"), list):
            cols = []
            for c in body["ribbon_colors"][:40]:
                ad, hx = str((c or {}).get("ad", "")).strip()[:30], str((c or {}).get("hex", "")).strip()
                if ad and re.fullmatch(r"#[0-9a-fA-F]{6}", hx) and all(ad != x["ad"] for x in cols):
                    cols.append({"ad": ad, "hex": hx.upper()})
            s.ribbon_colors = cols
        if isinstance(body.get("ribbon_default"), str):
            s.ribbon_default = body["ribbon_default"]
        if "auto_video" in body:
            s.auto_video = bool(body["auto_video"])
        if body.get("ornek_olcu") in product.OLCULER:
            s.ornek_olcu = body["ornek_olcu"]
        for k in SETTING_FIELDS:
            if k in body and body[k] not in (None, ""):
                v = body[k]
                if k in INT_FIELDS:
                    v = max(0, int(v))
                setattr(s, k, v)
        s.max_scene_calls = min(s.max_scene_calls, 60)
        s.max_video_tries = max(1, min(s.max_video_tries, 4))
        s.save()
        return self._send(200, {"tamam": True, "ayarlar": s.public()})

    def _start_photos(self, body):
        if not RUN.design or not os.path.exists(RUN.design):
            return self._send(400, {"hata": "Önce bir tasarım dosyası yükle."})
        category = body.get("category") or CATEGORIES[0]
        n = max(1, min(int(body.get("n", 6)), 12))
        refs = [open(p, "rb").read() for p in RUN.refs if os.path.exists(p)]
        depot = refstore.items(category) if body.get("use_refs", True) else []
        design = RUN.design
        people = bool(body.get("people"))
        rname = body.get("ribbon")
        ribbon = Settings.load().ribbon(rname if isinstance(rname, str) else None)
        olcu = body.get("olcu")
        if olcu is not None and olcu not in product.OLCULER:
            return self._send(400, {"hata": f"Bilinmeyen ölçü: {olcu}"})
        prof = product.profil_olustur(self._olcu(olcu), (ribbon or {}).get("hex"))
        kontrol = product.tasarim_kontrol(design, prof)
        if not kontrol["uyumlu"]:                      # uyuşmazlık sessizce düzeltilmez: ücretli üretim hiç başlamaz
            return self._send(400, {"hata": kontrol["uyarilar"][0], "kontrol": kontrol, "beklemede": True})

        def work(o, settings):
            job = o.new_job(design, category, body.get("name"), profile=prof)
            RUN._set(job=os.path.basename(job))
            res = o.generate_photos(job, n, refs, people=people, ribbon=ribbon, ref_items=depot, profile=prof)
            res["job"] = os.path.basename(job)
            return res

        if not RUN.start("fotograf", work):
            return self._send(409, {"hata": "Başka bir iş çalışıyor."})
        return self._send(200, {"basladi": True})

    def _recompose(self, body):
        """Kayıtlı boş sahnelerden yeniden birleştirme: yeni iş açar, kaynak işe dokunmaz, sağlayıcıya istek göndermez."""
        job = body.get("job", "")
        jp = safe_join(orch.JOBS_DIR, job) if job else None
        if not jp or not os.path.isdir(jp):
            return self._send(400, {"hata": "İş bulunamadı."})
        if not any(p.get("stem") for p in Orchestrator.report_of(jp).get("fotograflar", [])):
            return self._send(400, {"hata": "Bu işte kayıtlı sahne yok."})

        def work(o, settings):
            res = o.recompose_from_scenes(jp)
            RUN._set(job=res["job"])
            return res

        if not RUN.start("fotograf", work):
            return self._send(409, {"hata": "Başka bir iş çalışıyor."})
        return self._send(200, {"basladi": True})

    def _start_video(self, body):
        job, photo = body.get("job", ""), body.get("photo", "")
        jp = safe_join(orch.JOBS_DIR, job) if job else None
        if not jp or not os.path.isdir(jp):
            return self._send(400, {"hata": "İş bulunamadı."})

        mode = body.get("mode") or Settings.load().video_mode
        move = body.get("move") or Settings.load().camera_move

        def work(o, settings):
            RUN._set(job=job)
            if mode == "yapay_zeka":
                res = o.generate_video(jp, photo)
            elif mode == "canli":
                res = o.generate_live_video(jp, photo)
            elif mode == "kompozit":
                res = o.generate_composite_video(jp, photo)
            else:
                res = o.generate_camera_videos(jp, photo, camera_move.expand(move))
            res["job"] = job
            return res

        if not RUN.start("video", work):
            return self._send(409, {"hata": "Başka bir iş çalışıyor."})
        return self._send(200, {"basladi": True})


def make_server():
    for port in PORT_RANGE:
        try:
            return ThreadingHTTPServer(("127.0.0.1", port), Handler), port
        except OSError:
            continue
    raise SystemExit("Boş bir port bulunamadı (7860-7889). Açık olan başka bir pencereyi kapatıp tekrar dene.")


def main():
    for st in (sys.stdout, sys.stderr):                      # Windows konsolunda Türkçe karakter yüzünden çökmesin
        try:
            st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    httpd, port = make_server()
    url = f"http://127.0.0.1:{port}/"
    print(f"Afiş Stüdyosu çalışıyor: {url}")
    print("Kapatmak için bu pencereyi kapat (ya da Ctrl+C).")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

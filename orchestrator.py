# -*- coding: utf-8 -*-
"""
Orkestratör: tüm akışı tek yerden yürütür.

  fotoğraflar : sahne üret -> afişi bul -> kalite kapısı -> tasarımı yerleştir (6 geçerli sahneye kadar)
  video       : seçilen fotoğraf -> 9:16 kadraj -> görselden videoya -> yazıyı orijinal tasarımla onar -> kalite kontrol

Her iş "isler/<tarih>_<ad>/" klasöründe saklanır; hiçbir şey sessizce silinmez, yeniden deneme ve elenme nedenleri
rapor.json'a yazılır. Maliyet tavanı: tek seferde en fazla `max_scene_calls` sahne çağrısı ve
`max_video_tries` video çağrısı yapılır (ücret çağrı başına servis tarafında kesilir).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime

import cv2
import numpy as np

import banner_detect as bd
import camera_move as cm
import compositor as cp
import cvio
import guide as guide_mod
import layout
import pipeline
import product
import prompts
import proportion
import ribbon as ribbon_mod
import video_composite as vc
import video_repair as vr
import video_track as vt
from providers import (AuthError, Magnific, ProviderError, Settings, make_scene_provider, make_video_provider, redact,
                       scene_arms, video_arms)
from selector import Selector, nice

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(HERE, "isler")
REPORT_DIR = os.path.join(HERE, "raporlar")
LOG_PATH = os.path.join(HERE, "kayit.log")
STATS_PATH = os.path.join(HERE, "servis_karnesi.json")      # servislerin başarı geçmişi (otomatik seçim bunu kullanır)
VERSION = "0.7-test"
GOOD_VIDEO = 60.0          # kalite kontrolden geçen video bu puanın üstündeyse başka servis denenmez (ücret tasarrufu)
DESIGN_CAP = 4096          # tasarım belleğe bu uzun kenara küçültülerek alınır (4116x8000 -> 2107x4096)


def slug(s: str) -> str:
    s = s.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", s.strip()).strip("-")
    return (s or "is")[:40]


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Cancelled(Exception):
    pass


class Orchestrator:
    def __init__(self, settings: Settings, log=None, progress=None, cancel=None):
        self.s = settings
        self._log_cb, self._progress_cb = log, progress
        self._cancel = cancel or (lambda: False)
        self.arms_override: dict = {}        # sınama kancası: {"scene": [...], "video": [...]} servis listesini zorla
        self.rng_seed = None                 # sınama kancası: seçimi tekrarlanabilir yapar

    # -- otomatik servis seçimi ---------------------------------------------------
    def _arms(self, kind: str) -> list:
        if kind in self.arms_override:
            return list(self.arms_override[kind])
        return scene_arms(self.s) if kind == "scene" else video_arms(self.s)

    def _rng(self):
        import random
        return random.Random(self.rng_seed)

    def _selector(self, kind: str):
        names = self._arms(kind)
        persist = not all(str(n).startswith("mock") for n in names)
        return Selector(kind, names, STATS_PATH, rng=self._rng(), log=self.log, persist=persist,
                        explore=0.08 if kind == "scene" else 0.0)       # video pahalı: keşif yok, ikinci denemede zaten başka servis denenir

    def _record_karne(self, job: str, kind: str, sel):
        """Servis karnesini işin raporuna yazar ve günlüğe tek satır özet bırakır."""
        sel.save()
        if not any(r["cagri"] for r in sel.table()):
            return
        rap = self.report_of(job)
        rap.setdefault("servis_karnesi", []).append({"tur": kind, "zaman": datetime.now().strftime("%Y%m%d-%H%M%S"),
                                                     "tablo": sel.table(), "kazanan": sel.winner()})
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.log("Servis karnesi (" + ("sahne" if kind == "scene" else "video") + "): " + sel.summary_line()
                 + (f" -> en iyisi: {nice(sel.winner())}" if sel.winner() else ""))

    # -- kayıt ----------------------------------------------------------------
    def log(self, msg: str):
        msg = redact(str(msg), self.s.keys())
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
        try:
            if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 2_000_000:
                os.replace(LOG_PATH, LOG_PATH + ".eski")
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        if self._log_cb:
            self._log_cb(msg)

    def progress(self, frac, text):
        if self._cancel():
            raise Cancelled()
        if self._progress_cb:
            self._progress_cb(float(frac), text)

    # -- iş klasörü ---------------------------------------------------------------
    def new_job(self, design_path: str, category: str, name: str | None = None, profile=None) -> str:
        """Yeni iş klasörü. Rapor: eski alanlar + "urun_profili" ve "tasarim_kontrol" (Aşama 2A).
        profile verilmezse Settings.ornek_olcu ile profil oluşturulur. Oran uyuşmazsa iş yine açılır (kayıt için) ama
        durum "beklemede" yazılır ve onizleme_oran.png üretilir; generate_photos sahne çağrısı yapmaz."""
        os.makedirs(JOBS_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = slug(name or os.path.splitext(os.path.basename(design_path))[0])
        job = os.path.join(JOBS_DIR, f"{stamp}_{base}")
        for sub in ("foto", "sahneler_bos", "video"):
            os.makedirs(os.path.join(job, sub), exist_ok=True)
        ext = os.path.splitext(design_path)[1].lower() or ".png"
        shutil.copy(design_path, os.path.join(job, "tasarim" + ext))
        prof = self._profile(None, profile)
        rap = {"surum": VERSION, "kategori": category, "olusturuldu": stamp,
               "fotograflar": [], "elenenler": [], "videolar": [], "urun_profili": prof.to_dict()}
        self._check_design(job, rap, prof)
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.log(f"Yeni iş: {os.path.basename(job)} ({category}, ölçü {product.olcu_etiketi(prof.olcu_id)})")
        return job

    # -- ürün profili ve tasarım kontrolü (Aşama 2A) ------------------------------------
    def _profile(self, rap: dict | None, profile=None):
        """Öncelik: açık verilen profil > rapordaki profil > ayarlardaki örnek ölçü."""
        if profile is not None:
            return product.UrunProfili.from_dict(profile, strict=True) if isinstance(profile, dict) else profile.dogrula()
        if rap and rap.get("urun_profili"):
            return product.UrunProfili.from_dict(rap["urun_profili"])
        return product.profil_olustur(getattr(self.s, "ornek_olcu", None) or product.VARSAYILAN_ORNEK_OLCU)

    def _check_design(self, job: str, rap: dict, prof) -> dict:
        """Tasarım kontrolünü rapora yazar; uyumsuzsa onizleme_oran.png üretir ve durumu "beklemede" yapar."""
        files = glob.glob(os.path.join(job, "tasarim.*"))
        if not files:
            raise ProviderError("İş klasöründe tasarım dosyası yok.")
        tk = product.tasarim_kontrol(files[0], prof)
        rap["tasarim_kontrol"] = tk
        if not tk["uyumlu"]:
            cvio.imwrite(os.path.join(job, "onizleme_oran.png"), product.oran_onizleme(files[0], prof))
            rap["durum"] = "beklemede"
            rap["bekleme_nedeni"] = "tasarim_oran_uyusmazligi"
            rap["beklemede_neden"] = " ".join(tk["uyarilar"])
            rap["oran_onizleme"] = "onizleme_oran.png"
        elif rap.get("bekleme_nedeni") == "tasarim_oran_uyusmazligi":      # profil/ölçü değişti, artık uyumlu
            rap.pop("durum", None)
            rap.pop("bekleme_nedeni", None)
            rap.pop("beklemede_neden", None)
        return tk

    @staticmethod
    def list_jobs():
        if not os.path.isdir(JOBS_DIR):
            return []
        return sorted((d for d in os.listdir(JOBS_DIR) if os.path.isdir(os.path.join(JOBS_DIR, d))), reverse=True)

    @staticmethod
    def report_of(job):
        return _read_json(os.path.join(job, "rapor.json"), {})

    def _design(self, job):
        files = glob.glob(os.path.join(job, "tasarim.*"))
        if not files:
            raise ProviderError("İş klasöründe tasarım dosyası yok.")
        d = cp.load_design(files[0])
        long_side = max(d.shape[:2])
        if long_side > DESIGN_CAP:
            f = DESIGN_CAP / long_side
            d = cv2.resize(d, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        return d

    # -- fotoğraflar --------------------------------------------------------------------
    def generate_photos(self, job: str, n: int = 6, ref_images: list[bytes] | None = None, people: bool = False, ribbon: dict | None = None,
                        ref_items: list | None = None, profile=None) -> dict:
        """Aşama 2A fotoğraf hattı: kare (1:1) sahne, ürün profili ölçüsü, tam kumaş yerleşimi.

        Profil: verilen > rapordaki > Settings.ornek_olcu. Tasarım oranı profil ile uyuşmazsa HİÇ sahne çağrısı yapılmaz;
        onizleme_oran.png yazılır, rapor durumu "beklemede" olur ve son_uretim["beklemede"]=True döner."""
        rap = self.report_of(job)
        prof = self._profile(rap, profile)
        rap["urun_profili"] = prof.to_dict()                 # yeni üretim çağrısı: profil rapora yazılır
        tk = self._check_design(job, rap, prof)
        if not tk["uyumlu"]:
            for u in tk["uyarilar"]:
                self.log("UYARI: " + u)
            self.log("Önizleme: onizleme_oran.png (kırmızı: kumaşa sığmayan kısım, turuncu: tasarımın kaplamadığı kumaş). "
                     "Sahne üretimi yapılmadı.")
            rap["son_uretim"] = {"hedef": n, "uretilen": 0, "eksik": n, "cagri": 0, "beklemede": True,
                                 "bekleme_nedeni": "tasarim_oran_uyusmazligi", "neden": " ".join(tk["uyarilar"])}
            _write_json(os.path.join(job, "rapor.json"), rap)
            self.progress(1.0, "Beklemede: tasarım oranı kumaşla uyuşmuyor")
            return rap["son_uretim"]
        rap.setdefault("fotograflar", [])
        rap.setdefault("elenenler", [])
        category = prompts.canon(rap.get("kategori", "Düğün"))
        if people or rap.get("insanli") or prompts.default_people(category):
            people = True
            rap["insanli"] = True            # insanlı sahne: video için arka planda misafirler
        import random
        start = rap.setdefault("sahne_baslangic", random.randrange(100))   # her iş farklı sahneden başlar
        psize = prompts.pool_size(category)
        design = self._design(job)
        design_file = glob.glob(os.path.join(job, "tasarim.*"))[0]
        refs = [self._small_png(b) for b in (ref_images or [])][:4]
        depot = [(self._small_png(b), d) for b, d in (ref_items or [])]      # referans deposu: [(görsel, sahne tarifi)]
        if depot:
            self.log(f"Referans deposu: {len(depot)} görsel kullanılacak (her sahne sırayla birinden ilham alır; "
                     f"{sum(1 for _, d in depot if d)} tanesinin hazır sahne tarifi var).")
        pa = prof.oran                                         # yerleşim/kalite ölçütleri PNG oranına değil ÜRÜN oranına göre
        frame = 1.0                                            # ilan fotoğrafı her zaman kare; video ayarı (auto_video_kind) kadrajı DEĞİŞTİRMEZ
        guide_png, _ = guide_mod.make_guide(frame, pa, ribbon_hex=(ribbon or {}).get("hex"))         # kılavuz görseli destekleyen servislere verilir
        # --- servisler: "Otomatik" modda anahtarı girilmiş hepsi yarışır, sonuçlara göre en iyisi daha sık seçilir ---
        names = self._arms("scene")
        if not names:
            raise AuthError("Hiçbir sahne servisi için anahtar girilmemiş (Ayarlar sekmesi).")
        sel = self._selector("scene")
        provs: dict = {}
        auto = len(names) > 1
        have = len(rap.get("fotograflar", []))
        accepted_now, calls, seen = 0, 0, set()
        new_photos: list[str] = []
        self.log(f"Fotoğraf üretimi başladı: hedef {n}, ölçü {product.olcu_etiketi(prof.olcu_id)}, kare kadraj, "
                 f"en fazla {self.s.max_scene_calls} sahne çağrısı, servis: "
                 + (", ".join(nice(x) for x in names) + " (otomatik seçim)" if auto else nice(names[0])))

        def reject(tur, reason, img=None, det=None, lay=None, extra=None):
            rec = {"cagri": calls, "servis": name, "neden": reason, "tur": tur}
            if lay is not None:
                rec["olcum"] = lay
            if extra:
                rec.update(extra)
            if img is not None:
                fn = f"elenen_{have + 1:02d}_{calls:02d}.jpg"                # eski "elenen_NN" üzerine yazmasın
                cvio.imwrite(os.path.join(job, "sahneler_bos", fn),
                             bd.overlay(img, det) if (det is not None and det.mask.any()) else img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                rec["dosya"] = f"sahneler_bos/{fn}"
            rap["elenenler"].append(rec)
            _write_json(os.path.join(job, "rapor.json"), rap)

        while accepted_now < n and calls < self.s.max_scene_calls:
            name = sel.pick()
            if name is None:
                self.log("Kullanılabilir servis kalmadı: üretim durduruluyor (kredi harcamamak için).")
                break
            if name not in provs:
                try:
                    provs[name] = make_scene_provider(self.s, self.log, name=name)
                except AuthError as e:
                    if not auto:
                        raise
                    sel.disable(name, str(e))
                    continue
            provider = provs[name]
            guided = bool(provider.supports_guide)
            idx = calls
            calls += 1
            self.progress(0.05 + 0.9 * min(calls / max(self.s.max_scene_calls, 1), 1.0) * 0.5 + 0.45 * accepted_now / n,
                          f"Sahne {calls} üretiliyor ({nice(name)}; geçerli {accepted_now}/{n})")
            call_refs, sdesc = refs, None
            if depot:
                k = (idx + start + have) % len(depot)
                call_refs, sdesc = [depot[k][0]], (depot[k][1] or None)
            prompt = prompts.build_scene_prompt(category, idx + start + have, prof.en_cm, prof.boy_cm, bool(call_refs), (idx + have) // psize,
                                                guided=guided, people=people, ribbon=ribbon, scene_desc=sdesc, profile=prof)
            try:
                raw = provider.scene(prompt, frame, 1.0, call_refs, seed=idx + 1 + have * 7, guide=guide_png if guided else None)
            except AuthError as e:
                if not auto:
                    raise
                self.log(f"Sahne {calls} ({nice(name)}): {e}")
                reject("servis_hatasi", f"servis hatası: {e}")
                sel.record(name, False, error=True)
                sel.disable(name, "anahtar reddedildi")
                continue
            except ProviderError as e:
                self.log(f"Sahne {calls} ({nice(name)}): hata: {e}")
                reject("servis_hatasi", f"servis hatası: {e}")
                sel.record(name, False, error=True)
                continue
            h = hashlib.md5(raw).hexdigest()
            if h in seen:
                reject("kalite_kapisi", "aynı görsel tekrar geldi")
                sel.record(name, False)
                continue
            seen.add(h)
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                reject("servis_hatasi", "görsel okunamadı")
                sel.record(name, False, error=True)
                continue
            img = self._upscale(img)
            ev = self._evaluate_scene(img, design, prof, f"Sahne {calls} ({nice(name)})")
            if not ev["ok"]:
                reject(ev["tur"], ev["neden"], img, ev["det"], ev["lay"], ev.get("extra"))
                sel.record(name, False)
                continue
            sel.record(name, True, ev["kalite"])
            num = have + accepted_now + 1
            rec = self._save_accepted(job, rap, img, ev, prof, ribbon, num, name, design_file)
            new_photos.append(rec["ad"])
            accepted_now += 1
            self.log(f"Sahne {calls} ({nice(name)}) kabul edildi -> {rec['ad']}, kalite {ev['kalite']:.0f}/100, "
                     f"asılı ≈{ev['info']['asili_cm']:.0f} cm" + (f", zeminde ≈{ev['info']['gizli_cm']:.0f} cm birikme" if ev['info']["v_gizli"] < 0.995 else "")
                     + (f" (uyarı: {'; '.join(rec['uyari'])})" if rec["uyari"] else ""))
            _write_json(os.path.join(job, "rapor.json"), rap)
        sel.save()
        rap.setdefault("servis_karnesi", []).append({"tur": "scene", "zaman": datetime.now().strftime("%Y%m%d-%H%M%S"),
                                                     "tablo": sel.table(), "kazanan": sel.winner()})
        if any(r["cagri"] for r in sel.table()):
            self.log("Servis karnesi: " + sel.summary_line() + (f" -> en iyisi: {nice(sel.winner())}" if sel.winner() else ""))
        best = max(rap.get("fotograflar", []), key=lambda p: p.get("kalite", 0), default=None)
        for p_ in rap.get("fotograflar", []):
            p_["en_iyi"] = bool(best) and p_ is best
        self._overview(job, rap)
        rap["son_uretim"] = {"hedef": n, "uretilen": accepted_now, "eksik": max(0, n - accepted_now), "cagri": calls, "beklemede": False}
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.progress(1.0, f"Bitti: {accepted_now}/{n} geçerli fotoğraf")
        if self.s.auto_video and new_photos:
            self._auto_videos(job, new_photos)
        if accepted_now < n:
            self.log(f"{n - accepted_now} fotoğraf eksik kaldı (çağrı tavanı ya da hata). Tekrar çalıştırırsan eksikler tamamlanır.")
        return rap["son_uretim"]

    # -- ortak sahne değerlendirme ve kayıt (sağlayıcıdan bağımsız) -----------------------------------
    def _evaluate_scene(self, img, design, prof, label: str) -> dict:
        """Bir boş sahneyi değerlendirir ve tasarımı tam kumaş moduyla yerleştirir. AĞ/SAĞLAYICI KULLANMAZ.
        Hem yeni üretimde (generate_photos) hem kayıtlı sahnelerden yeniden birleştirmede aynı kurallar uygulanır:
        kumaş zorunlu algılama -> layout kalite kapısı (ürün oranı) -> tam kumaş yerleşimi -> geometri/birikme sorunları.
        Dönüş: {"ok", "tur", "neden", "det", "lay", "info", "out", "kalite", "extra"}."""
        pa = prof.oran
        det = bd.detect(img, hint={"kind": "fabric"})      # ürün kumaş: otomatik sert/kumaş sınıflandırması yerleşimi değiştirmez
        reason, lay, tur_ = None, {}, "kalite_kapisi"
        if not det.ok:
            reason = "; ".join(det.reject)
        elif det.mask.any():
            why, lay = layout.check(det, img.shape, pa)       # oran düzeltme (sahneyi germe) KAPALI; oran ürün profilinden
            if lay:
                self.log(f"{label} ölçüm: oran {lay['aspect']:.2f} (ürün {pa:.2f}), üst/alt genişlik {lay['taper']:.2f}, "
                         f"sol/sağ yükseklik {lay['side_ratio']:.2f}, boy %{lay['top_frac'] * 100:.0f}-%{lay['bottom_frac'] * 100:.0f}")
            if why and self.s.strict_layout:
                reason = why
                if any(k in why for k in ("çok geniş", "çok dar", "yere kadar uzanmıyor")):
                    tur_ = "sahne_geometri"           # afiş oranı/boyu ürüne uymuyor: sahne geometrisi hatası (kalite değil)
        else:
            reason = "afiş bulunamadı"
        if reason:
            self.log(f"{label} elendi: {reason}")
            return {"ok": False, "tur": tur_, "neden": reason, "det": det, "lay": lay}
        try:
            out, info = cp.composite(img, design, det, mode="tam_kumas", profile=prof)
        except Exception as e:                           # geometri çıkarılamadı: sahne elenir, iş durmaz
            self.log(f"{label} elendi: kumaş geometrisi çıkarılamadı ({e.__class__.__name__}: {e})")
            return {"ok": False, "tur": "sahne_geometri", "neden": f"kumaş geometrisi çıkarılamadı: {e}", "det": det, "lay": lay}
        tk_info = {k: info[k] for k in ("px_per_cm", "asili_cm", "gizli_cm", "v_gizli", "temas_y", "birikme", "temas_yontemi",
                                        "olcek_farki", "dikey_olcek", "gizli_murekkep", "sorunlar", "uyarilar")}
        tk_info.update({k: info.get(k) for k in ("kivrim_kaymasi", "kenar_sigma_px", "yerlesim_donusumu", "dortgen", "kenar_sapmasi", "kumas_disi_baski")})
        if info["sorunlar"]:
            tur = info["sorunlar"][0]["tur"]
            msg = " ".join(x["mesaj"] for x in info["sorunlar"])
            self.log(f"{label} elendi ({product.HATA_TURLERI.get(tur, tur)}): {msg}")
            return {"ok": False, "tur": tur, "neden": msg, "det": det, "lay": lay, "extra": {"tam_kumas": tk_info}}
        quality = layout.score(lay, pa) if lay else 50.0
        return {"ok": True, "tur": None, "neden": None, "det": det, "lay": lay, "info": info, "tk_info": tk_info,
                "out": out, "kalite": quality}

    def _save_accepted(self, job, rap, img, ev, prof, ribbon, num, servis, design_file) -> dict:
        """Kabul edilen sahneyi ve yerleştirilmiş fotoğrafı kaydeder, rapor kaydını ekler (yazma çağıranda)."""
        stem = f"s{num:02d}"
        cvio.imwrite(os.path.join(job, "sahneler_bos", stem + ".png"), img)
        out, info, det = ev["out"], ev["info"], ev["det"]
        if ribbon:
            out = ribbon_mod.restore(img, out, ribbon["hex"])
        fname = f"{num:02d}_kumas.jpg"
        cvio.imwrite(os.path.join(job, "foto", fname), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        rec = {"ad": fname, "stem": stem, "tur": det.kind, "uyari": det.warn + info["uyarilar"],
               "olcu": [out.shape[1], out.shape[0]], "yerlesim": ev["lay"], "servis": servis, "kalite": ev["kalite"],
               "oran_duzeltme": None, "kurdele": (ribbon or {}).get("hex"),
               "yerlesim_modu": "tam_kumas", "olcu_id": prof.olcu_id, "tam_kumas": ev["tk_info"]}
        if info["v_gizli"] < 0.995:
            os.makedirs(os.path.join(job, "onizleme"), exist_ok=True)
            gname = f"onizleme/{num:02d}_gizli.jpg"
            cvio.imwrite(os.path.join(job, gname), product.gizli_bolge_onizleme(design_file, info["v_gizli"]),
                         [cv2.IMWRITE_JPEG_QUALITY, 90])
            rec["gizli_onizleme"] = gname
        rap["fotograflar"].append(rec)
        _write_json(os.path.join(job, "rapor.json"), rap)
        return rec

    # -- kayıtlı sahnelerden yeniden birleştirme (ÜCRETSİZ: sağlayıcıya hiçbir istek gitmez) ------------------
    def recompose_from_scenes(self, src_job: str, name: str | None = None) -> dict:
        """Var olan bir işin KAYITLI boş sahnelerine (sahneler_bos/sNN.png) aynı tasarımı güncel kodla yeniden yerleştirir.
        Yeni bir iş klasörü açar; kaynak işe ve görsellerine DOKUNMAZ. Sağlayıcı/selector hiç kullanılmaz.
        Kalite kapısı, tam kumaş yerleşimi ve sonuç kaydı generate_photos ile aynı fonksiyonlardan geçer."""
        src = self.report_of(src_job)
        photos = [p for p in src.get("fotograflar", []) if p.get("stem")]
        if not photos:
            raise ProviderError("Kaynak işte kayıtlı sahne yok (fotoğraf kaydı bulunamadı).")
        files = glob.glob(os.path.join(src_job, "tasarim.*"))
        if not files:
            raise ProviderError("Kaynak işte tasarım dosyası yok.")
        prof = self._profile(src)
        src_name = os.path.basename(src_job)
        job = self.new_job(files[0], src.get("kategori", "Düğün"), name or f"yeniden_{src_name.split('_')[0]}", profile=prof)
        rap = self.report_of(job)
        rap.update(islem="kayitli_sahnelerden_yeniden_birlestirme", kaynak_is=src_name, saglayici_cagrisi=0,
                   insanli=bool(src.get("insanli")))
        self.log(f"Kayıtlı sahnelerden yeniden birleştirme: kaynak {src_name}, {len(photos)} sahne. "
                 f"Sağlayıcıya istek GÖNDERİLMEZ (ücretsiz).")
        if not rap["tasarim_kontrol"]["uyumlu"]:
            rap["son_uretim"] = {"hedef": len(photos), "uretilen": 0, "eksik": len(photos), "cagri": 0, "saglayici_cagrisi": 0,
                                 "beklemede": True, "bekleme_nedeni": "tasarim_oran_uyusmazligi"}
            _write_json(os.path.join(job, "rapor.json"), rap)
            return dict(rap["son_uretim"], job=os.path.basename(job))
        design = self._design(job)
        design_file = glob.glob(os.path.join(job, "tasarim.*"))[0]
        done = 0
        for i, p in enumerate(photos):
            self.progress(0.05 + 0.9 * i / len(photos), f"Kayıtlı sahne {i + 1}/{len(photos)} yeniden birleştiriliyor")
            spath = os.path.join(src_job, "sahneler_bos", p["stem"] + ".png")
            img = cvio.imread(spath, cv2.IMREAD_COLOR) if os.path.exists(spath) else None
            kaynak = {"is": src_name, "stem": p["stem"], "foto": p.get("ad"), "servis": p.get("servis")}
            if img is None:
                rap["elenenler"].append({"cagri": 0, "servis": None, "tur": "kalite_kapisi", "neden": f"kayıtlı sahne okunamadı: {p['stem']}",
                                         "kaynak": kaynak})
                continue
            img = self._upscale(img)
            ev = self._evaluate_scene(img, design, prof, f"Kayıtlı sahne {p['stem']}")
            if not ev["ok"]:
                rec = {"cagri": 0, "servis": None, "tur": ev["tur"], "neden": ev["neden"], "kaynak": kaynak}
                if ev.get("lay"):
                    rec["olcum"] = ev["lay"]
                rap["elenenler"].append(rec)
                _write_json(os.path.join(job, "rapor.json"), rap)
                continue
            ribbon = {"hex": p["kurdele"]} if p.get("kurdele") else None
            rec = self._save_accepted(job, rap, img, ev, prof, ribbon, len(rap["fotograflar"]) + 1,
                                      "kayitli_sahne", design_file)
            rec["kaynak"] = kaynak
            done += 1
            self.log(f"Kayıtlı sahne {p['stem']} yeniden birleştirildi -> {rec['ad']} (kaynak: {p.get('ad')})")
        best = max(rap.get("fotograflar", []), key=lambda q: q.get("kalite", 0), default=None)
        for q in rap.get("fotograflar", []):
            q["en_iyi"] = bool(best) and q is best
        self._overview(job, rap)
        rap["son_uretim"] = {"hedef": len(photos), "uretilen": done, "eksik": len(photos) - done, "cagri": 0,
                             "saglayici_cagrisi": 0, "beklemede": False}
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.progress(1.0, f"Bitti: {done}/{len(photos)} kayıtlı sahne yeniden birleştirildi (servis çağrısı yok)")
        return dict(rap["son_uretim"], job=os.path.basename(job))

    def _auto_videos(self, job: str, photos: list[str]):
        """Her yeni fotoğraf için onaylanan kamera videosu (ücretsiz, yapay zekâsız). Bir video hata verirse iş durmaz."""
        move = self.s.auto_video_move if self.s.auto_video_move in cm.MOVES else "yakinlas_saga"
        self.log(f"Otomatik video: {len(photos)} fotoğraf için '{cm.MOVES[move]['ad']}' hazırlanıyor.")
        live = self.s.auto_video_kind == "canli" and bool(video_arms(self.s))
        if live:
            self.log("Otomatik video türü: gerçek hareketli sahne (yapay zekâ videosu + izlenen tasarım); sorun olursa kamera videosuna dönülür.")
        for k, name in enumerate(photos):
            try:
                self.progress(k / len(photos), f"Video {k + 1}/{len(photos)}: {name}")
                if live:
                    self.generate_live_video(job, name, max_tries=1)
                else:
                    self.generate_camera_videos(job, name, [move])
            except Exception as e:
                self.log(f"Otomatik video ({name}) yapılamadı: {e.__class__.__name__}: {e}")
        self.progress(1.0, f"Bitti: {len(photos)} fotoğraf ve videoları")

    def _upscale(self, img):
        t = int(self.s.photo_long_side or 0)
        L = max(img.shape[:2])
        if t and L < t * 0.95:
            f = t / L
            img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
        return img

    @staticmethod
    def _small_png(b: bytes) -> bytes:
        im = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
        if im is None:
            return b
        f = min(1.0, 1024 / max(im.shape[:2]))
        if f < 1:
            im = cv2.resize(im, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        return cv2.imencode(".png", im)[1].tobytes()

    def _overview(self, job, rap):
        items = []
        for p in rap.get("fotograflar", []):
            im = cvio.imread(os.path.join(job, "foto", p["ad"]))
            if im is not None:
                items.append((p["ad"], im))
        if items:
            pipeline.contact_sheet(items, os.path.join(job, "foto", "_ozet.jpg"))

    # -- video ----------------------------------------------------------------------------
    def _entry_profile(self, rap, entry):
        """Tam kumaş yerleşimiyle üretilmiş fotoğrafın profili (videoda aynı yerleşim kullanılsın); eski fotoğraflarda None."""
        if entry.get("yerlesim_modu") != "tam_kumas":
            return None
        prof = self._profile(rap)
        oid = entry.get("olcu_id")
        if oid and prof is not None and oid != prof.olcu_id and oid in product.OLCULER:
            prof = product.profil_olustur(oid)          # fotoğraf hangi ölçüyle basıldıysa video da o ölçüyle
        return prof

    def _composite_for(self, scene, design, det, profile, **kw):
        if profile is None:
            return cp.composite(scene, design, det, **kw)
        return cp.composite(scene, design, det, mode="tam_kumas", profile=profile, **kw)

    def _video_start(self, blank, design, margin=0.03, profile=None):
        H, W = blank.shape[:2]
        hint = {"kind": "fabric"} if profile is not None else None
        det0 = bd.detect(blank, hint=hint)
        if not det0.ok:
            raise ProviderError("Bu sahnede afiş artık bulunamadı: " + "; ".join(det0.reject))
        ys, xs = np.where(det0.mask > 0)
        bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
        tr = 9 / 16
        cw, ch = (int(round(H * tr)), H) if W / H > tr else (W, int(round(W / tr)))
        x0 = int(np.clip((bx0 + bx1) / 2 - cw / 2, 0, W - cw))
        y0 = int(np.clip((by0 + by1) / 2 - ch / 2, 0, H - ch))
        if bx0 < x0 + margin * cw or bx1 > x0 + (1 - margin) * cw or by0 < y0 + margin * ch or by1 > y0 + (1 - margin) * ch:
            raise ProviderError("Afiş 9:16 dikey video kadrajına sığmıyor; bu sahneden video üretilemez.")
        blank_c = blank[y0:y0 + ch, x0:x0 + cw].copy()
        det = bd.detect(blank_c, hint=hint)
        if not det.ok:
            raise ProviderError("Kırpılmış kadrajda afiş bulunamadı: " + "; ".join(det.reject))
        ref, info, model = self._composite_for(blank_c, design, det, profile, return_model=True)
        f = min(1.0, 1080 / cw)
        send = cv2.resize(ref, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else ref
        jpg = cv2.imencode(".jpg", send, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()
        return {"blank": blank_c, "ref": ref, "model": model, "size": (cw, ch), "jpg": jpg, "crop": [x0, y0, cw, ch]}

    def generate_video(self, job: str, photo_name: str) -> dict:
        rap = self.report_of(job)
        entry = next((p for p in rap.get("fotograflar", []) if p["ad"] == photo_name), None)
        if not entry:
            raise ProviderError("Seçilen fotoğraf bu işte bulunamadı.")
        blank = cvio.imread(os.path.join(job, "sahneler_bos", entry["stem"] + ".png"))
        if blank is None:
            raise ProviderError("Boş sahne dosyası bulunamadı.")
        design = self._design(job)
        self.progress(0.02, "Video başlangıç karesi hazırlanıyor")
        st = self._video_start(blank, design, profile=self._entry_profile(rap, entry))
        vdir = os.path.join(job, "video", entry["stem"])
        os.makedirs(vdir, exist_ok=True)
        sel = self._selector("video")
        if not sel.names:
            raise AuthError("Hiçbir video servisi için anahtar girilmemiş (Ayarlar sekmesi).")
        auto = len(sel.names) > 1
        provs, used = {}, []
        tries, best = [], None
        self.log(f"Video başladı: {photo_name}, en fazla {self.s.max_video_tries} deneme, servis: "
                 + (", ".join(nice(x) for x in sel.names) + " (otomatik seçim)" if auto else nice(sel.names[0])))
        attempt = 0
        while attempt < self.s.max_video_tries:
            name = sel.pick(exclude=used) or sel.pick()
            if name is None:
                self.log("Kullanılabilir video servisi kalmadı.")
                break
            attempt += 1
            used.append(name)
            base = 0.05 + 0.9 * (attempt - 1) / self.s.max_video_tries
            span = 0.9 / self.s.max_video_tries
            self.progress(base, f"Deneme {attempt}: {nice(name)} ile video üretiliyor (birkaç dakika sürebilir)")
            try:
                if name not in provs:
                    provs[name] = make_video_provider(self.s, self.log, name=name)
                raw = provs[name].video(st["jpg"], prompts.MOTION, self.s.seconds, seed=attempt * 17)
            except AuthError as e:
                if not auto:
                    raise
                self.log(f"Deneme {attempt} ({nice(name)}): {e}")
                tries.append({"deneme": attempt, "servis": name, "hata": str(e)})
                sel.record(name, False, error=True)
                sel.disable(name, "anahtar reddedildi")
                continue
            except ProviderError as e:
                self.log(f"Deneme {attempt} ({nice(name)}): servis hatası: {e}")
                tries.append({"deneme": attempt, "servis": name, "hata": str(e)})
                sel.record(name, False, error=True)
                continue
            ai = os.path.join(vdir, f"ai_{attempt}.mp4")
            with open(ai, "wb") as f:
                f.write(raw)
            out = os.path.join(vdir, f"onarilmis_{attempt}.mp4")

            def prog(i, n, base=base, span=span, attempt=attempt):
                self.progress(base + span * 0.4 + span * 0.6 * i / max(n, 1), f"Deneme {attempt}: yazı onarılıyor ({i}/{n} kare)")

            summary, infos = vr.repair_video(ai, out, st["ref"], st["blank"], design, st["model"], st["size"], progress=prog)
            kal = round(max(0.0, min(1.0, float(summary["ncc_mean"]))) * 100, 1)
            rec = {"deneme": attempt, "servis": name, "kontrol_gecti": summary["ok"], "nedenler": summary["reasons"],
                   "ncc_ort": round(summary["ncc_mean"], 3), "kalite": kal, "kare": summary["frames"], "dosya": os.path.basename(out)}
            tries.append(rec)
            self.log(f"Deneme {attempt} ({nice(name)}): kalite kontrol {'GEÇTİ' if summary['ok'] else 'GEÇMEDİ: ' + '; '.join(summary['reasons'])}")
            sel.record(name, summary["ok"], kal)
            if best is None or (summary["ok"], summary["ncc_mean"]) > (best[1]["ok"], best[1]["ncc_mean"]):
                best = (out, summary, attempt, name)
            if summary["ok"]:
                break
        self._record_karne(job, "video", sel)
        if best is None:
            raise ProviderError("Hiçbir video denemesi tamamlanamadı: " + "; ".join(t.get("hata", "") for t in tries))
        final = os.path.join(vdir, "final.mp4")
        shutil.copy(best[0], final)
        res = {"foto": photo_name, "kontrol_gecti": best[1]["ok"], "secilen_deneme": best[2], "nedenler": best[1]["reasons"],
               "servis": best[3], "denemeler": tries, "dosya": f"video/{entry['stem']}/final.mp4"}
        rap = self.report_of(job)
        rap.setdefault("videolar", []).append(res)
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.progress(1.0, "Video hazır" + ("" if res["kontrol_gecti"] else " (KALİTE KONTROLÜNDEN GEÇMEDİ, kendin kontrol et)"))
        return res

    def generate_composite_video(self, job: str, photo_name: str) -> dict:
        """İnsanlı/hareketli sahne videosu: yapay zekâ TASARIMSIZ sahneyi sabit kamerayla canlandırır; tasarım ve el kamerası
        kodla eklenir. Kalite kontrolden geçmezse otomatik olarak güvenli kamera videosuna döner."""
        rap = self.report_of(job)
        entry = next((p for p in rap.get("fotograflar", []) if p["ad"] == photo_name), None)
        if not entry:
            raise ProviderError("Seçilen fotoğraf bu işte bulunamadı.")
        blank = cvio.imread(os.path.join(job, "sahneler_bos", entry["stem"] + ".png"))
        if blank is None:
            raise ProviderError("Boş sahne dosyası bulunamadı.")
        design = self._design(job)
        move = cm.expand(self.s.camera_move)[0]
        vdir = os.path.join(job, "video", entry["stem"])
        os.makedirs(vdir, exist_ok=True)
        tries, reasons = [], []
        try:
            self.progress(0.02, "Video başlangıç karesi hazırlanıyor")
            st = self._video_start(blank, design, margin=0.05, profile=self._entry_profile(rap, entry))
        except ProviderError as e:
            self.log(f"Kompozit video başlatılamadı: {e}")
            st = None
            reasons.append(str(e))
        best = None
        if st is not None:
            blank_c = st["blank"]
            f = min(1.0, 1080 / blank_c.shape[1])
            send = cv2.resize(blank_c, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else blank_c
            jpg = cv2.imencode(".jpg", send, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()
            people = bool(rap.get("insanli"))
            prompt = prompts.MOTION_PEOPLE if people else prompts.MOTION_STATIC
            sel = self._selector("video")
            if not sel.names:
                raise AuthError("Hiçbir video servisi için anahtar girilmemiş (Ayarlar sekmesi).")
            auto = len(sel.names) > 1
            provs, used = {}, []
            self.log(f"Kompozit video başladı: {photo_name}, hareket {move}, el sallantısı {self.s.handheld}, "
                     f"en fazla {self.s.max_video_tries} deneme, servis: "
                     + (", ".join(nice(x) for x in sel.names) + " (otomatik seçim)" if auto else nice(sel.names[0])))
            attempt = 0
            while attempt < self.s.max_video_tries:
                name = sel.pick(exclude=used) or sel.pick()          # önce henüz denenmemiş servis; kalmadıysa en iyisi
                if name is None:
                    self.log("Kullanılabilir video servisi kalmadı.")
                    break
                attempt += 1
                used.append(name)
                base = 0.05 + 0.9 * (attempt - 1) / self.s.max_video_tries
                span = 0.9 / self.s.max_video_tries
                self.progress(base, f"Deneme {attempt}: {nice(name)} ile sabit kameralı sahne videosu üretiliyor (birkaç dakika sürebilir)")
                try:
                    if name not in provs:
                        provs[name] = make_video_provider(self.s, self.log, name=name)
                    raw = provs[name].video(jpg, prompt, self.s.seconds, seed=attempt * 17, negative=Magnific.NEG_STATIC)
                except AuthError as e:
                    if not auto:
                        raise
                    self.log(f"Deneme {attempt} ({nice(name)}): {e}")
                    tries.append({"deneme": attempt, "servis": name, "hata": str(e)})
                    reasons.append(f"{nice(name)}: {e}")
                    sel.record(name, False, error=True)
                    sel.disable(name, "anahtar reddedildi")
                    continue
                except ProviderError as e:
                    self.log(f"Deneme {attempt} ({nice(name)}): servis hatası: {e}")
                    tries.append({"deneme": attempt, "servis": name, "hata": str(e)})
                    reasons.append(f"servis hatası: {e}")
                    sel.record(name, False, error=True)
                    continue
                ai = os.path.join(vdir, f"kompozit_ai_{attempt}.mp4")
                with open(ai, "wb") as fh:
                    fh.write(raw)
                out = os.path.join(vdir, f"kompozit_{move}_{attempt}.mp4")

                def prog(i, n, base=base, span=span, attempt=attempt):
                    self.progress(base + span * 0.3 + span * 0.7 * i / max(n, 1), f"Deneme {attempt}: stabilize + baskı + el kamerası ({i}/{n})")

                try:
                    summary, _ = vc.compose_video(ai, out, design, move=move, handheld=self.s.handheld,
                                                  seed=attempt * 5 + 11, progress=prog, strength=1.0)
                except vc.CompositeError as e:
                    self.log(f"Deneme {attempt} ({nice(name)}): kompozit yapılamadı: {e}")
                    tries.append({"deneme": attempt, "servis": name, "kontrol_gecti": False, "nedenler": [str(e)]})
                    reasons.append(str(e))
                    sel.record(name, False)
                    continue
                kal = float(summary.get("kalite", 0.0))
                tries.append({"deneme": attempt, "servis": name, "kontrol_gecti": summary["ok"], "nedenler": summary["reasons"],
                              "kalite": kal,
                              "olcum": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in summary.items()
                                        if k not in ("ok", "reasons")}, "dosya": os.path.basename(out)})
                self.log(f"Deneme {attempt} ({nice(name)}): kalite kontrol "
                         + (f"GEÇTİ, kalite {kal:.0f}/100" if summary["ok"] else "GEÇMEDİ: " + "; ".join(summary["reasons"])))
                sel.record(name, summary["ok"], kal)
                if summary["ok"]:
                    if best is None or kal > best[1].get("kalite", 0):
                        best = (out, summary, attempt, name)
                    if kal >= GOOD_VIDEO:                          # yeterince temiz: daha fazla ücret harcama
                        break
                else:
                    reasons.extend(summary["reasons"])
            self._record_karne(job, "video", sel)
        if best:
            final = os.path.join(vdir, f"kompozit_{move}.mp4")
            shutil.copy(best[0], final)
            res = {"foto": photo_name, "tur": "kompozit", "hareket": move, "ad": f"Hareketli sahne · {cm.MOVES[move]['ad']}",
                   "sallanti": self.s.handheld, "kontrol_gecti": True, "nedenler": [], "secilen_deneme": best[2],
                   "servis": best[3], "kalite": best[1].get("kalite"),
                   "denemeler": tries, "dosya": f"video/{entry['stem']}/kompozit_{move}.mp4"}
            rap = self.report_of(job)
            rap["videolar"] = [v for v in rap.get("videolar", [])
                               if not (v.get("tur") == "kompozit" and v.get("foto") == photo_name and v.get("hareket") == move)] + [res]
            _write_json(os.path.join(job, "rapor.json"), rap)
            self.progress(1.0, "Video hazır")
            return {"videolar": [res]}
        # --- güvenli yedek: sabit fotoğraf + sanal kamera ---
        self.log("Hareketli sahne videosu kalite kontrolünden geçemedi: güvenli kamera videosuna dönülüyor (yazı yine bozulmaz).")
        r = self.generate_camera_videos(job, photo_name, [move])
        rap = self.report_of(job)
        extra = {"yedek": True, "yedek_neden": list(dict.fromkeys(reasons))[:6], "denemeler": tries}
        for v in rap.get("videolar", []) + r.get("videolar", []):
            if v.get("tur") == "kamera" and v.get("foto") == photo_name and v.get("hareket") == move:
                v.update(extra)
        _write_json(os.path.join(job, "rapor.json"), rap)
        return r

    def generate_live_video(self, job: str, photo_name: str, max_tries: int | None = None) -> dict:
        """GERÇEK hareketli video: yapay zekâ modeli TASARIMSIZ sahnede kamerayı kendisi yürütüp yay çizdirir (kurdeleler uçuşur,
        çocuklar koşar, açı değişince arka plan gerçekten değişir). Tasarım kare kare izlenerek kodla basılır, yazı bozulmaz.
        Kalite kontrolden geçmezse güvenli kamera videosuna dönülür."""
        rap = self.report_of(job)
        entry = next((p for p in rap.get("fotograflar", []) if p["ad"] == photo_name), None)
        if not entry:
            raise ProviderError("Seçilen fotoğraf bu işte bulunamadı.")
        blank = cvio.imread(os.path.join(job, "sahneler_bos", entry["stem"] + ".png"))
        if blank is None:
            raise ProviderError("Boş sahne dosyası bulunamadı.")
        design = self._design(job)
        move = "yakinlas_saga"
        vdir = os.path.join(job, "video", entry["stem"])
        os.makedirs(vdir, exist_ok=True)
        tries, reasons, best = [], [], None
        try:
            self.progress(0.02, "Video başlangıç karesi hazırlanıyor")
            st = self._video_start(blank, design, margin=0.06, profile=self._entry_profile(rap, entry))
        except ProviderError as e:
            self.log(f"Hareketli video başlatılamadı: {e}")
            st, _ = None, reasons.append(str(e))
        if st is not None:
            blank_c = st["blank"]
            f = min(1.0, 1080 / blank_c.shape[1])
            send = cv2.resize(blank_c, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else blank_c
            jpg = cv2.imencode(".jpg", send, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()
            prompt = prompts.MOTION_LIVE.format(ribbons=prompts.LIVE_RIBBONS if entry.get("kurdele") else "", life=prompts.LIVE_LIFE)
            sel = self._selector("video")
            if not sel.names:
                raise AuthError("Hiçbir video servisi için anahtar girilmemiş (Ayarlar sekmesi).")
            auto = len(sel.names) > 1
            provs, used = {}, []
            tries_max = max_tries or self.s.max_video_tries
            self.log(f"Hareketli video başladı: {photo_name}, en fazla {tries_max} deneme, servis: "
                     + (", ".join(nice(x) for x in sel.names) + " (otomatik seçim)" if auto else nice(sel.names[0])))
            attempt = 0
            while attempt < tries_max:
                name = sel.pick(exclude=used) or sel.pick()
                if name is None:
                    self.log("Kullanılabilir video servisi kalmadı.")
                    break
                attempt += 1
                used.append(name)
                base = 0.05 + 0.9 * (attempt - 1) / tries_max
                span = 0.9 / tries_max
                self.progress(base, f"Deneme {attempt}: {nice(name)} ile hareketli sahne üretiliyor (birkaç dakika sürebilir)")
                try:
                    if name not in provs:
                        provs[name] = make_video_provider(self.s, self.log, name=name)
                    raw = provs[name].video(jpg, prompt, self.s.seconds, seed=attempt * 17, negative=Magnific.NEG_LIVE)
                except AuthError as e:
                    if not auto:
                        raise
                    self.log(f"Deneme {attempt} ({nice(name)}): {e}")
                    tries.append({"deneme": attempt, "servis": name, "hata": str(e)})
                    reasons.append(f"{nice(name)}: {e}")
                    sel.record(name, False, error=True)
                    sel.disable(name, "anahtar reddedildi")
                    continue
                except ProviderError as e:
                    self.log(f"Deneme {attempt} ({nice(name)}): servis hatası: {e}")
                    tries.append({"deneme": attempt, "servis": name, "hata": str(e)})
                    reasons.append(f"servis hatası: {e}")
                    sel.record(name, False, error=True)
                    continue
                ai = os.path.join(vdir, f"canli_ai_{attempt}.mp4")
                with open(ai, "wb") as fh:
                    fh.write(raw)
                out = os.path.join(vdir, f"canli_{attempt}.mp4")

                def prog(i, n, base=base, span=span, attempt=attempt):
                    self.progress(base + span * 0.3 + span * 0.7 * i / max(n, 1), f"Deneme {attempt}: tasarım izlenip basılıyor ({i}/{n})")

                try:
                    summary = vt.compose_tracked(ai, out, design, progress=prog)
                except vc.CompositeError as e:
                    self.log(f"Deneme {attempt} ({nice(name)}): tasarım basılamadı: {e}")
                    tries.append({"deneme": attempt, "servis": name, "kontrol_gecti": False, "nedenler": [str(e)]})
                    reasons.append(str(e))
                    sel.record(name, False)
                    continue
                kal = float(summary.get("kalite", 0.0))
                tries.append({"deneme": attempt, "servis": name, "kontrol_gecti": summary["ok"], "nedenler": summary["reasons"],
                              "kalite": kal, "olcum": {k: v for k, v in summary.items() if k not in ("ok", "reasons")},
                              "dosya": os.path.basename(out)})
                self.log(f"Deneme {attempt} ({nice(name)}): kalite kontrol "
                         + (f"GEÇTİ, kalite {kal:.0f}/100" if summary["ok"] else "GEÇMEDİ: " + "; ".join(summary["reasons"])))
                sel.record(name, summary["ok"], kal)
                if summary["ok"]:
                    if best is None or kal > best[1].get("kalite", 0):
                        best = (out, summary, attempt, name)
                    if kal >= GOOD_VIDEO:
                        break
                else:
                    reasons.extend(summary["reasons"])
            self._record_karne(job, "video", sel)
        if best:
            final = os.path.join(vdir, "canli_yakinlas_saga.mp4")
            shutil.copy(best[0], final)
            res = {"foto": photo_name, "tur": "kompozit", "canli": True, "hareket": move,
                   "ad": "Gerçek hareketli sahne · yaklaşıp sağa dön", "kontrol_gecti": True, "nedenler": [],
                   "secilen_deneme": best[2], "servis": best[3], "kalite": best[1].get("kalite"),
                   "denemeler": tries, "dosya": f"video/{entry['stem']}/canli_yakinlas_saga.mp4"}
            rap = self.report_of(job)
            rap["videolar"] = [v for v in rap.get("videolar", []) if not (v.get("canli") and v.get("foto") == photo_name)] + [res]
            _write_json(os.path.join(job, "rapor.json"), rap)
            self.progress(1.0, "Video hazır")
            return {"videolar": [res]}
        self.log("Hareketli video kalite kontrolünden geçemedi: güvenli kamera videosuna dönülüyor (yazı yine bozulmaz).")
        r = self.generate_camera_videos(job, photo_name, [move])
        rap = self.report_of(job)
        extra = {"yedek": True, "yedek_neden": list(dict.fromkeys(reasons))[:6], "denemeler": tries}
        for v in rap.get("videolar", []) + r.get("videolar", []):
            if v.get("tur") == "kamera" and v.get("foto") == photo_name and v.get("hareket") == move:
                v.update(extra)
        _write_json(os.path.join(job, "rapor.json"), rap)
        return r

    HIRES_FACTOR = 1.6          # yakın planda yazı net kalsın: sahne büyütülür, tasarım orijinal çözünürlüğünden yeniden basılır
    HIRES_MAX_SIDE = 4200

    def _video_source(self, job: str, entry: dict, photo):
        """Kamera videosunun kaynağı: boş sahne büyütülüp tasarım yeniden basılır (afişe yaklaşırken yazı bulanıklaşmasın).
        Herhangi bir sorunda olduğu gibi kaydedilmiş fotoğraf kullanılır."""
        try:
            blank = cvio.imread(os.path.join(job, "sahneler_bos", entry["stem"] + ".png"))
            if blank is None or blank.shape[:2] != photo.shape[:2]:
                return photo
            f = min(self.HIRES_FACTOR, self.HIRES_MAX_SIDE / max(blank.shape[:2]))
            if f < 1.15:
                return photo
            prof = self._entry_profile(self.report_of(job), entry)
            det = bd.detect(blank, hint={"kind": "fabric"} if prof is not None else None)
            if not det.ok or not det.mask.any():
                return photo
            design = self._design(job)
            up = cv2.resize(blank, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
            out, _ = self._composite_for(up, design, det.scaled(f, up.shape), prof)
            out = ribbon_mod.restore(up, out, entry.get("kurdele"))
            self.log(f"Video kaynağı yüksek çözünürlükte hazırlandı ({photo.shape[1]}x{photo.shape[0]} -> {out.shape[1]}x{out.shape[0]}).")
            return out
        except Exception as e:                      # yalnızca kalite içindir: hata olursa mevcut fotoğrafla devam
            self.log(f"Video kaynağı büyütülemedi ({e.__class__.__name__}: {e}); kayıtlı fotoğraf kullanılacak.")
            return photo

    def generate_camera_videos(self, job: str, photo_name: str, moves: list[str]) -> dict:
        """Sabit mockup fotoğrafı + sanal kamera hareketi. Yapay zekâ yok: yazı değişmez, ücret yok."""
        rap = self.report_of(job)
        entry = next((p for p in rap.get("fotograflar", []) if p["ad"] == photo_name), None)
        if not entry:
            raise ProviderError("Seçilen fotoğraf bu işte bulunamadı.")
        img = cvio.imread(os.path.join(job, "foto", photo_name))
        if img is None:
            raise ProviderError("Fotoğraf dosyası okunamadı.")
        img = self._video_source(job, entry, img)
        vdir = os.path.join(job, "video", entry["stem"])
        os.makedirs(vdir, exist_ok=True)
        made = []
        self.log(f"Kamera hareketi videosu: {photo_name}, hareketler: {', '.join(moves)}, {self.s.seconds} sn")
        for k, mv in enumerate(moves):
            name = cm.MOVES[mv]["ad"]
            base, span = k / len(moves), 1.0 / len(moves)
            self.progress(base, f"{name} hazırlanıyor ({k + 1}/{len(moves)})")
            out = os.path.join(vdir, f"kamera_{mv}.mp4")
            cm.render(img, out, mv, seconds=self.s.seconds, fps=30, handheld=self.s.handheld,
                      progress=lambda i, n, base=base, span=span, name=name:
                      self.progress(base + span * 0.95 * i / max(n, 1), f"{name}: kareler işleniyor ({i}/{n})"))
            rec = {"foto": photo_name, "tur": "kamera", "hareket": mv, "ad": name, "sallanti": self.s.handheld, "kontrol_gecti": True, "nedenler": [],
                   "denemeler": [], "dosya": f"video/{entry['stem']}/kamera_{mv}.mp4"}
            rap["videolar"] = [v for v in rap.get("videolar", [])
                               if not (v.get("tur") == "kamera" and v.get("foto") == photo_name and v.get("hareket") == mv)] + [rec]
            _write_json(os.path.join(job, "rapor.json"), rap)
            made.append(rec)
            self.log(f"{name}: hazır -> {rec['dosya']}")
        self.progress(1.0, "Video hazır")
        return {"videolar": made}

    # -- hata raporu ----------------------------------------------------------------------------
    def make_report(self, job: str | None = None) -> str:
        os.makedirs(REPORT_DIR, exist_ok=True)
        path = os.path.join(REPORT_DIR, f"hata_raporu_{datetime.now():%Y%m%d-%H%M%S}.zip")
        keys = self.s.keys()
        try:
            import cv2 as _cv
            cvv = _cv.__version__
        except Exception:
            cvv = "?"
        sysinfo = (f"surum: {VERSION}\npython: {sys.version}\nplatform: {platform.platform()}\nopencv: {cvv}\n"
                   f"ffmpeg: {vr.find_ffmpeg()}\n")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("sistem.txt", sysinfo)
            z.writestr("ayarlar.json", json.dumps(self.s.public(), ensure_ascii=False, indent=2))
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
                    z.writestr("kayit.log", redact("".join(f.readlines()[-600:]), keys))
            if job and os.path.isdir(job):
                for rel in ("rapor.json", os.path.join("foto", "_ozet.jpg")):
                    p = os.path.join(job, rel)
                    if os.path.exists(p):
                        z.write(p, os.path.join("is", rel))
                for p in sorted(glob.glob(os.path.join(job, "sahneler_bos", "elenen_*.jpg")))[:4]:
                    z.write(p, os.path.join("is", "elenen", os.path.basename(p)))
                for p in glob.glob(os.path.join(job, "video", "*", "*.mp4")):
                    if os.path.getsize(p) < 15_000_000 and os.path.basename(p).startswith("ai_"):
                        z.write(p, os.path.join("is", "video", os.path.basename(os.path.dirname(p)), os.path.basename(p)))
            z.writestr("NOT.txt", "Tasarım dosyan ve API anahtarların bu rapora KONMAZ. Kayıtlardaki anahtarlar *** ile maskelenir.\n")
        return path

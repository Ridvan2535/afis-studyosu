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
import deneme_kayit
import gorsel_kontrol_servisi as gks
import sinir_kaniti
import guide as guide_mod
import layout
import pipeline
import product
import prompt_yapisi
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
SAHNE_GOREVI = "onden_kare"      # şimdilik tek görev (önden, kare). Aşama 2B'de 6 görev gelince görev kimliği buraya yazılır.
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
        # Otomatik görsel kontrol servisi (K-49): varsayılan KAPALI. Geliştirme ajanı visual-inspector ile karıştırılmaz.
        try:
            self.gk_servis = gks.servis_olustur(settings)
        except Exception as e:
            self.gk_servis = gks.KapaliServis()
            self.log(f"Görsel kontrol servisi kapalı: {e}")
        self.gk_butce = gks.Butce(settings, os.path.dirname(STATS_PATH))

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
                        ref_items: list | None = None, profile=None, ref_ids: list | None = None) -> dict:
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
        ref_ids = list(ref_ids or [])[:len(refs)]
        ref_ids += [f"yukleme:{i + 1}" for i in range(len(ref_ids), len(refs))]          # kimliği verilmemiş yüklemeler
        depot = [(self._small_png(it[0]), it[1], it[2] if len(it) > 2 else f"depo:{i + 1}")
                 for i, it in enumerate(ref_items or [])]      # referans deposu: [(görsel, sahne tarifi, kimlik)]
        if depot:
            self.log(f"Referans deposu: {len(depot)} görsel kullanılacak (her sahne sırayla birinden ilham alır; "
                     f"{sum(1 for x in depot if x[1])} tanesinin hazır sahne tarifi var).")
        pa = prof.oran                                         # yerleşim/kalite ölçütleri PNG oranına değil ÜRÜN oranına göre
        frame = 1.0                                            # ilan fotoğrafı her zaman kare; video ayarı (auto_video_kind) kadrajı DEĞİŞTİRMEZ
        kilavuz_surumu = prompt_yapisi.KILAVUZ_SURUMU.get(prompt_yapisi.secili_surum(self.s, category), 1)
        guide_png, _ = guide_mod.make_guide(frame, pa, ribbon_hex=(ribbon or {}).get("hex"), surum=kilavuz_surumu)         # kılavuz görseli destekleyen servislere verilir
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
        rap.setdefault("denemeler", [])                      # K-25: çağrı başına tam kayıt (eski işlerde yok; sonradan doldurulmaz)
        uretim_no = 1 + len(rap.get("uretimler", []))
        siniri = int(getattr(self.s, "ayni_hata_siniri", 5) or 0)          # K-30: art arda AYNI hata
        sonucsuz_siniri = int(getattr(self.s, "sonucsuz_siniri", 8) or 0)   # K-33: son kabulden beri sonuçsuz çağrı (neden fark etmez)
        seri = {"imza": None, "sayi": 0, "sonucsuz": 0}
        supheli_dur = bool(getattr(self.s, "supheli_olcumde_dur", True))       # K-36
        durum = {"durdurma": None}
        # karşılaştırma anahtarı (K-32): ürün ölçüsü, sahne görevi, referans kümesi ve üretim ayarları her çağrıda kaydedilir
        ref_kumesi_ids = sorted(set(ref_ids) | {x[2] for x in depot})
        ref_kumesi = (hashlib.sha256("|".join(ref_kumesi_ids).encode("utf-8")).hexdigest()[:12]
                      if ref_kumesi_ids else "referanssiz")
        cur: dict = {}                                       # o anki çağrının kaydı (reject/kabul tamamlar)
        self.log(f"Fotoğraf üretimi başladı: hedef {n}, ölçü {product.olcu_etiketi(prof.olcu_id)}, kare kadraj, "
                 f"en fazla {self.s.max_scene_calls} sahne çağrısı, servis: "
                 + (", ".join(nice(x) for x in names) + " (otomatik seçim)" if auto else nice(names[0])))

        def reject(tur, reason, img=None, det=None, lay=None, extra=None, tani_out=None, tani_kars=None):
            reason = deneme_kayit.temizle(reason)                        # bağlantı / base64 kayda girmez
            rec = {"cagri": calls, "servis": name, "neden": reason, "tur": tur, "uretim_no": uretim_no}
            if lay is not None:
                rec["olcum"] = lay
            if extra:
                rec.update(extra)
            if img is not None:
                base = f"elenen_{have + 1:02d}_{calls:02d}"                  # eski "elenen_NN" üzerine yazmasın
                if any(os.path.exists(os.path.join(job, "sahneler_bos", base + x)) for x in (".jpg", "_ham.jpg")):
                    base = f"elenen_u{uretim_no:02d}_{calls:02d}"             # aynı işte ikinci üretim: çakışma yok
                ov = bd.overlay(img, det) if (det is not None and det.mask.any()) else None
                cvio.imwrite(os.path.join(job, "sahneler_bos", base + "_ham.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
                rec["ham_dosya"] = f"sahneler_bos/{base}_ham.jpg"            # sağlayıcıdan gelen görsel (işaretsiz)
                if ov is not None:
                    cvio.imwrite(os.path.join(job, "sahneler_bos", base + "_algilama.jpg"), ov, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    rec["algilama_dosya"] = f"sahneler_bos/{base}_algilama.jpg"
                rec["dosya"] = rec.get("algilama_dosya") or rec["ham_dosya"]     # geriye uyum (eski arayüz/rapor)
                if tani_out is not None:
                    rec["tani_dosya"] = self._tani_kaydet(job, base, tani_out, rec, prof, kars=tani_kars)
            rec["sade_neden"] = deneme_kayit.sade_neden(rec, prof.boy_cm)
            rec["siniflama"] = deneme_kayit.kontrol_sonucu(rec, prof.oran, prof.boy_cm)      # K-35 otomatik kontrol
            rec["hata_imzasi"] = deneme_kayit.hata_imzasi(tur, reason)
            rap["elenenler"].append(rec)
            cur.update(sonuc="servis_hatasi" if tur == "servis_hatasi" else "elendi", tur=tur, neden=reason,
                       sade_neden=rec["sade_neden"], siniflama=rec["siniflama"], hata_imzasi=rec["hata_imzasi"],
                       ham_dosya=rec.get("ham_dosya"), algilama_dosya=rec.get("algilama_dosya"))
            _write_json(os.path.join(job, "rapor.json"), rap)

        def finish_call():
            """Çağrı kaydını kapatır; art arda aynı hatayı ve son kabulden beri sonuçsuz çağrıları sayar.
            Bir sınır aşılırsa durum["durdurma"] doldurulur (döngü bir sonraki turda durur). Dönüş: durdurma ya da None."""
            cur["sure_sn"] = round(time.monotonic() - cur.pop("_t0"), 1)
            if cur.get("sonuc") == "elendi":
                sig = cur.get("hata_imzasi")
                seri["sayi"] = seri["sayi"] + 1 if sig == seri["imza"] else 1
                seri["imza"] = sig
            else:
                seri.update(imza=None, sayi=0)             # kabul ve servis hatası aynı-hata serisini keser
            seri["sonucsuz"] = 0 if cur.get("sonuc") == "kabul" else seri["sonucsuz"] + 1
            cur["art_arda"], cur["kabulden_beri"] = seri["sayi"], seri["sonucsuz"]
            rap["denemeler"].append(dict(cur))
            _write_json(os.path.join(job, "rapor.json"), rap)
            d = None
            if seri["sayi"] >= 3 and cur.get("sonuc") == "elendi":
                self.log(f"UYARI: aynı hata art arda {seri['sayi']}. kez: {cur.get('sade_neden')}"
                         + (f" (durma sınırı {siniri})" if siniri else " (durma sınırı kapalı)"))
            sk = cur.get("siniflama") or {}
            if supheli_dur and cur.get("sonuc") == "elendi" and sk.get("guven") == "dusuk":
                d = {"neden": "supheli_olcum", "sayi": 1, "cagri": calls,
                     "aciklama": f"Bu sahnede algılama güveni düşük ({' '.join(sk.get('nedenler') or [])}). Ret kesin değil; "
                                 f"şüpheli ölçüm yüzünden otomatik yeni ücretli çağrı başlatılmadı. Elenen denemeler bölümünden "
                                 f"gözle bak (Ayarlar: şüpheli ölçümde dur)."}
            elif siniri and seri["sayi"] >= siniri:
                d = {"neden": "ayni_hata_tekrari", "imza": seri["imza"], "sayi": seri["sayi"], "cagri": calls,
                     "aciklama": f"Aynı hata art arda {seri['sayi']} kez tekrarlandı: {cur.get('sade_neden')} "
                                 f"Ücretli tekrar sürdürülmedi (Ayarlar: aynı hata sınırı {siniri})."}
            elif sonucsuz_siniri and seri["sonucsuz"] >= sonucsuz_siniri and cur.get("sonuc") != "kabul":
                d = {"neden": "sonucsuz_cagri", "sayi": seri["sonucsuz"], "cagri": calls,
                     "aciklama": f"Son kabulden beri {seri['sonucsuz']} çağrı sonuç vermedi (nedenler farklı olsa da). "
                                 f"Ücretli deneme sürdürülmedi (Ayarlar: sonuçsuz çağrı sınırı {sonucsuz_siniri})."}
            if d:
                durum["durdurma"] = d
                self.log("DURDURULDU: " + d["aciklama"])
            return d

        while accepted_now < n and calls < self.s.max_scene_calls and not durum["durdurma"]:
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
            ayar_ozeti = {"kadraj": "1:1", "kilavuz": guided, "kilavuz_surumu": kilavuz_surumu if guided else None, "insanli": bool(people), "kurdele": bool(ribbon),
                          "kati_yerlesim": bool(self.s.strict_layout), "uzun_kenar": int(self.s.photo_long_side or 0)}
            idx = calls
            calls += 1
            self.progress(0.05 + 0.9 * min(calls / max(self.s.max_scene_calls, 1), 1.0) * 0.5 + 0.45 * accepted_now / n,
                          f"Sahne {calls} üretiliyor ({nice(name)}; geçerli {accepted_now}/{n})")
            call_refs, sdesc, call_ref_ids = refs, None, list(ref_ids)
            if depot:
                k = (idx + start + have) % len(depot)
                call_refs, sdesc, call_ref_ids = [depot[k][0]], (depot[k][1] or None), [depot[k][2]]
            surum = prompt_yapisi.secili_surum(self.s, category)
            try:
                prompt, pinfo = prompt_yapisi.build(surum, category, idx + start + have, prof, ribbon=ribbon, people=people,
                                                    has_refs=bool(call_refs), guided=guided, scene_desc=sdesc,
                                                    round_no=(idx + have) // psize)
            except ValueError as e:                     # aday sürüm sınırı aşıldı: sessiz kesme yok, etkin sürüme dön
                self.log(f"Prompt sürümü {surum} kullanılamadı ({e}); etkin sürüm {prompt_yapisi.ETKIN_VARSAYILAN} kullanılıyor.")
                prompt, pinfo = prompt_yapisi.build(prompt_yapisi.ETKIN_VARSAYILAN, category, idx + start + have, prof,
                                                    ribbon=ribbon, people=people, has_refs=bool(call_refs), guided=guided,
                                                    scene_desc=sdesc, round_no=(idx + have) // psize)
            seed = idx + 1 + have * 7
            cur.clear()
            cur.update({"cagri": calls, "uretim_no": uretim_no, "zaman": datetime.now().isoformat(timespec="seconds"),
                        "servis": name, "model": None, "prompt_surumu": pinfo["prompt_surumu"], "prompt": prompt,
                        "prompt_ozeti": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                        "prompt_kelime": len(prompt.split()), "referanslar": call_ref_ids, "kilavuz": guided,
                        "tohum": seed, "olcu_id": prof.olcu_id, "sahne_gorevi": SAHNE_GOREVI,
                        "referans_kumesi": ref_kumesi, "ayar_ozeti": ayar_ozeti, "_t0": time.monotonic()})
            cur.update({k: v for k, v in pinfo.items() if k != "prompt_surumu"})
            try:
                raw = provider.scene(prompt, frame, 1.0, call_refs, seed=seed, guide=guide_png if guided else None)
            except AuthError as e:
                cur["model"] = self._model_id(provider)
                if not auto:
                    reject("servis_hatasi", f"servis hatası: {e}")
                    finish_call()
                    raise
                self.log(f"Sahne {calls} ({nice(name)}): {e}")
                reject("servis_hatasi", f"servis hatası: {e}")
                finish_call()
                sel.record(name, False, error=True)
                sel.disable(name, "anahtar reddedildi")
                continue
            except ProviderError as e:
                cur["model"] = self._model_id(provider)
                self.log(f"Sahne {calls} ({nice(name)}): hata: {e}")
                reject("servis_hatasi", f"servis hatası: {e}")
                finish_call()
                sel.record(name, False, error=True)
                continue
            cur["model"] = self._model_id(provider)
            h = hashlib.md5(raw).hexdigest()
            if h in seen:
                reject("kalite_kapisi", "aynı görsel tekrar geldi")
                finish_call()
                sel.record(name, False)
                continue
            seen.add(h)
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                reject("servis_hatasi", "görsel okunamadı")
                finish_call()
                sel.record(name, False, error=True)
                continue
            img = self._upscale(img)
            ev = self._degerlendir_kurtar(img, design, prof, f"Sahne {calls} ({nice(name)})")
            if not ev["ok"]:
                reject(ev["tur"], ev["neden"], img, ev["det"], ev["lay"], ev.get("extra"), tani_out=ev.get("tani_out"),
                       tani_kars=ev.get("tani_karsilastirma"))
                finish_call()
                sel.record(name, False)
                continue
            sel.record(name, True, ev["kalite"])
            num = have + accepted_now + 1
            rec = self._save_accepted(job, rap, img, ev, prof, ribbon, num, name, design_file)
            rec["cagri"], rec["uretim_no"] = calls, uretim_no
            cur.update(sonuc="kabul", foto=rec["ad"], kalite=round(float(ev["kalite"]), 1))
            finish_call()
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
        durdurma = durum["durdurma"]
        tekrar = deneme_kayit.tekrar_ozeti([d for d in rap["denemeler"] if d.get("uretim_no") == uretim_no])
        rap["son_uretim"] = {"hedef": n, "uretilen": accepted_now, "eksik": max(0, n - accepted_now), "cagri": calls, "beklemede": False,
                             "uretim_no": uretim_no, "ayni_hata_siniri": siniri,
                             "sonucsuz_siniri": sonucsuz_siniri, "supheli_olcumde_dur": supheli_dur, "tavan": self.s.max_scene_calls, "tekrar": tekrar, "durdurma": durdurma}
        rap.setdefault("uretimler", []).append(dict(rap["son_uretim"], zaman=datetime.now().isoformat(timespec="seconds")))
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.progress(1.0, f"Bitti: {accepted_now}/{n} geçerli fotoğraf" + (" (aynı hata tekrarı nedeniyle durduruldu)" if durdurma else ""))
        if self.s.auto_video and new_photos:
            self._auto_videos(job, new_photos)
        if accepted_now < n:
            self.log(f"{n - accepted_now} fotoğraf eksik kaldı (çağrı tavanı ya da hata). Tekrar çalıştırırsan eksikler tamamlanır.")
        return rap["son_uretim"]

    @staticmethod
    def _model_id(provider):
        """Kayıt için model kimliği (ör. seedream-v5-pro-edit). Anahtar/bağlantı içermez; bilinmiyorsa None."""
        for obj in (getattr(provider, "impl", None), provider):
            for attr in ("model", "model_id", "_model"):
                v = getattr(obj, attr, None) if obj is not None else None
                if isinstance(v, str) and v and len(v) < 120 and "://" not in v:
                    return v
        return None

    # -- ortak sahne değerlendirme ve kayıt (sağlayıcıdan bağımsız) -----------------------------------
    # -- algılama şüpheliyse kurtarma (K-49): yeni sahne ÜRETMEZ; aynı ham görselde alternatif adaylar + isteğe bağlı servis --
    def _supheli_mi(self, ev, prof) -> bool:
        if ev["ok"] or ev["tur"] in ("servis_hatasi", "temas_belirsiz"):   # temas belirsizliği bölge seçimi sorunu değil
            return False
        rec = {"tur": ev["tur"], "neden": ev["neden"], "olcum": ev.get("lay")}
        rec.update(ev.get("extra") or {})
        return ev["tur"] == "kalite_kapisi" or deneme_kayit.kontrol_sonucu(rec, prof.oran, prof.boy_cm).get("guven") == "dusuk"

    def _aday_degerlendir(self, img, design, prof, label, det, hint):
        """Bir kumaş adayını programın bütün kontrollerinden + kararlılık testinden geçirir. Doğrulandı mı?"""
        ev = self._evaluate_scene(img, design, prof, label, kararlilik=True, hint=hint, det=det)
        kr = (ev.get("tk_info") or {}).get("kararlilik") or (ev.get("extra") or {}).get("kararlilik") or {}
        return ev, (not kr.get("karar_degisti")) and (not ev["ok"] or not kr.get("kararsiz"))

    def _kurtar(self, img, design, prof, label, ev):
        """(yeni_ev ya da None, bilgi). Sıra: 1) aynı görseldeki alternatif kumaş adayları (ücretsiz, yerel);
        2) yalnız 1 sonuç vermezse ve servis bağlı + bütçe uygunsa bağımsız görsel kontrol (bölge önerisi);
        öneri yeniden algılamada İPUCU olur, yeni maske bütün kontrollerden geçmeli ve önerilen kutuda kalmalıdır.
        Doğru bölge doğrulanamazsa None: sahne kullanıcı incelemesine kalır (şüpheli ölçümde dur korunur)."""
        bilgi = {"denendi": True, "yerel_adaylar": [], "servis": None, "sonuc": "dogrulanamadi"}
        ilk = ev.get("det")
        adaylar = bd.detect_candidates(img, {"kind": "fabric"}, en_fazla=4)
        for i, d in enumerate(adaylar):
            if ilk is not None and getattr(ilk, "mask", None) is not None and ilk.mask.any() and bd._iou(d.mask, ilk.mask) > 0.7:
                continue
            kayit = {"aday": i + 1, "aciklik": round(float(d.metrics.get("lightness", 0)), 1),
                     "alan": round(float(d.metrics.get("area_ratio", 0)), 3)}
            if not d.ok or not d.mask.any():
                kayit["sonuc"] = "algılama reddi: " + "; ".join(d.reject)[:120]
                bilgi["yerel_adaylar"].append(kayit)
                continue
            ys, xs = np.nonzero(d.mask)
            hint = {"point": [float(xs.mean() / img.shape[1]), float(ys.mean() / img.shape[0])]}
            ev2, dogru = self._aday_degerlendir(img, design, prof, f"{label} (aday {i + 1})", d, hint)
            kayit["sonuc"] = ("kabul" if ev2["ok"] else "ret: " + str(ev2["neden"])[:120]) + ("" if dogru else " (kararsız)")
            bilgi["yerel_adaylar"].append(kayit)
            if dogru:
                bilgi["sonuc"] = "yerel_aday_kabul" if ev2["ok"] else "yerel_aday_dogru_bolge_ret"
                bilgi["secilen"] = {"kaynak": "yerel_aday", "aday": i + 1, "ipucu": hint}
                self.log(f"{label}: kurtarma — {i + 1}. kumaş adayı doğrulandı ({bilgi['sonuc']}).")
                return ev2, bilgi
        # 2) bağımsız görsel kontrol (bağlıysa)
        servis = getattr(self, "gk_servis", None) or gks.KapaliServis()
        if not servis.etkin:
            bilgi["servis"] = {"durum": "kapali"}
            return None, bilgi
        butce = getattr(self, "gk_butce", None)
        if butce is not None:
            ok, neden = butce.izin()
            if not ok:
                bilgi["servis"] = {"durum": "butce", "neden": neden}
                return None, bilgi
        try:
            res = servis.incele(img, adaylar, prof.oran)
        except Exception as e:                      # tek çağrı; kör yeniden deneme yok
            bilgi["servis"] = {"durum": "hata", "neden": deneme_kayit.temizle(str(e), 200)}
            return None, bilgi
        if butce is not None:
            butce.kaydet(getattr(res, "tahmini_usd", 0.0) if res else 0.0)
        if res is None:
            bilgi["servis"] = {"durum": "gecersiz_yanit"}
            return None, bilgi
        bilgi["servis"] = {"durum": res.durum, "model": res.model, "kumas_kutusu": res.kumas_kutusu, "aday_no": res.aday_no,
                           "gerekce": res.gerekce, "belirsizlik": res.belirsizlik, "kullanim": res.kullanim,
                           "tahmini_usd": res.tahmini_usd}
        if not res.kumas_kutusu:
            return None, bilgi                       # bölge önerisi yok: "uygun" demesi tek başına yetmez
        x0, y0, x1, y1 = res.kumas_kutusu
        d3 = bd.detect(img, {"box": [x0, y0, x1, y1], "kind": "fabric"})
        if not d3.ok or not d3.mask.any():
            bilgi["servis"]["yeniden_algilama"] = "kumaş bulunamadı"
            return None, bilgi
        H, W = img.shape[:2]
        kutu = np.zeros((H, W), bool)
        kutu[int(y0 * H):int(y1 * H) + 1, int(x0 * W):int(x1 * W) + 1] = True
        m3 = d3.mask > 0
        icerde = float((m3 & kutu).sum()) / max(m3.sum(), 1)
        kaplama = float((m3 & kutu).sum()) / max(kutu.sum(), 1)
        bilgi["servis"]["maske_kutuda"] = round(icerde, 3)
        bilgi["servis"]["kutu_kaplama"] = round(kaplama, 3)
        if icerde < 0.9 or kaplama < 0.5:            # yeni maske öneriyle tutarlı değil -> baskı yapılmaz
            bilgi["servis"]["yeniden_algilama"] = "maske önerilen bölgeyle tutarsız"
            return None, bilgi
        ev3, dogru = self._aday_degerlendir(img, design, prof, f"{label} (görsel kontrol önerisi)", d3,
                                            {"box": [x0, y0, x1, y1]})
        bilgi["servis"]["yeniden_algilama"] = ("kabul" if ev3["ok"] else "ret: " + str(ev3["neden"])[:120]) + ("" if dogru else " (kararsız)")
        if dogru:
            bilgi["sonuc"] = "servis_onerisi_kabul" if ev3["ok"] else "servis_onerisi_dogru_bolge_ret"
            bilgi["secilen"] = {"kaynak": "gorsel_kontrol_onerisi", "kutu": [x0, y0, x1, y1]}
            return ev3, bilgi
        return None, bilgi

    def _degerlendir_kurtar(self, img, design, prof, label):
        """Üretim ve yeniden birleştirmenin ORTAK yolu: değerlendir; şüpheliyse aynı görselde kurtarmayı dene."""
        ev = self._evaluate_scene(img, design, prof, label)
        if getattr(self.s, "kurtarma_etkin", True) and self._supheli_mi(ev, prof):
            ev2, bilgi = self._kurtar(img, design, prof, label, ev)
            if ev2 is not None:
                ev = ev2
            ev["kurtarma"] = bilgi
            if not ev["ok"]:
                ev.setdefault("extra", {})["kurtarma"] = bilgi
        return ev

    def _evaluate_scene(self, img, design, prof, label: str, kararlilik: bool | None = None, hint: dict | None = None,
                        det=None) -> dict:
        """Sahne değerlendirmesi + ölçüm kararlılığı (K-37). kararlilik None -> Settings.olcum_kararlilik_testi.
        hint/det: kurtarma akışında (K-49) belirli bir kumaş adayıyla değerlendirme; kararlılık da aynı ipucuyla ölçülür."""
        ev = self._evaluate_scene_tek(img, design, prof, label, hint=hint, det=det)
        if kararlilik is None:
            kararlilik = bool(getattr(self.s, "olcum_kararlilik_testi", True))
        if not kararlilik or ev["tur"] == "servis_hatasi":
            return ev
        k = self._kararlilik(img, design, prof, ev, hint=hint)
        if ev["ok"]:
            ev["tk_info"]["kararlilik"] = k
            if k["kararsiz"]:
                ev["tk_info"].setdefault("uyarilar", [])
                ev["kararlilik_uyarisi"] = ("Ölçüm kararsız: kabul kararı görüntüdeki çok küçük farklarla (JPEG / ölçek) "
                                            "değişebiliyor; boy ve birikme gözle kontrol edilmeli.")
        else:
            ev.setdefault("extra", {})["kararlilik"] = k
        return ev

    def _kararlilik(self, img, design, prof, ev, hint: dict | None = None) -> dict:
        """Aynı sahneyi iki küçük bozulmayla (JPEG %92 yeniden kodlama; %80 küçültüp geri büyütme) yeniden ölçer.
        Karar (kabul/ret) değişiyorsa ya da asılı boy %3'ten fazla oynuyorsa ölçüm KARARSIZDIR: ret kesin sayılmaz, kabul
        uyarıyla işaretlenir. Sağlayıcıya istek gitmez. Neden (kontrol örnekleri, 2026-10-13): kabul edilen s01 aynı sahnenin
        JPEG'i ve küçültülmüş hallerinde 199,5 / 208,5 cm arasında; s02 197 / 156 cm arasında ölçülüyordu (birikme temas satırı
        tek satırlık maske çentiğine bağlıydı)."""
        H, W = img.shape[:2]
        ok_, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        varyant = [("jpeg92", cv2.imdecode(buf, cv2.IMREAD_COLOR)),
                   ("olcek80", cv2.resize(cv2.resize(img, (int(W * 0.8), int(H * 0.8)), interpolation=cv2.INTER_AREA), (W, H),
                                          interpolation=cv2.INTER_CUBIC))]
        def ozet(e):
            tk = e.get("tk_info") or (e.get("extra") or {}).get("tam_kumas") or {}
            return {"kabul": bool(e["ok"]), "tur": e["tur"], "asili_cm": round(float(tk["asili_cm"]), 1) if tk.get("asili_cm") else None,
                    "oran": (e.get("lay") or {}).get("aspect")}
        ana = ozet(ev)
        sonuclar = []
        for ad, im in varyant:
            e = self._evaluate_scene_tek(im, design, prof, f"(kararlılık {ad})", sessiz=True, hint=hint)
            sonuclar.append(dict(ozet(e), varyant=ad))
        asl = [x["asili_cm"] for x in [ana] + sonuclar if x["asili_cm"]]
        oynama = (max(asl) - min(asl)) / prof.boy_cm if len(asl) > 1 else 0.0
        karar_degisti = any(x["kabul"] != ana["kabul"] for x in sonuclar)
        return {"kararsiz": bool(karar_degisti or oynama > 0.03), "karar_degisti": karar_degisti,
                "asili_oynama": round(oynama, 3), "varyantlar": sonuclar}

    def _evaluate_scene_tek(self, img, design, prof, label: str, sessiz: bool = False, hint: dict | None = None,
                            det=None, sinir: dict | None = None) -> dict:
        """Bir boş sahneyi değerlendirir ve tasarımı tam kumaş moduyla yerleştirir. AĞ/SAĞLAYICI KULLANMAZ.
        Hem yeni üretimde (generate_photos) hem kayıtlı sahnelerden yeniden birleştirmede aynı kurallar uygulanır:
        kumaş zorunlu algılama -> layout kalite kapısı (ürün oranı) -> tam kumaş yerleşimi -> geometri/birikme sorunları.
        Dönüş: {"ok", "tur", "neden", "det", "lay", "info", "out", "kalite", "extra"}."""
        pa = prof.oran
        _log = (lambda m: None) if sessiz else self.log
        if det is None:                                    # ürün kumaş: otomatik sert/kumaş sınıflandırması yerleşimi değiştirmez
            det = bd.detect(img, hint=dict(hint or {}, kind="fabric"))
        reason, lay, tur_ = None, {}, "kalite_kapisi"
        if not det.ok:
            reason = "; ".join(det.reject)
        elif det.mask.any():
            why, lay = layout.check(det, img.shape, pa)       # oran düzeltme (sahneyi germe) KAPALI; oran ürün profilinden
            if lay:
                _log(f"{label} ölçüm: oran {lay['aspect']:.2f} (ürün {pa:.2f}), üst/alt genişlik {lay['taper']:.2f}, "
                         f"sol/sağ yükseklik {lay['side_ratio']:.2f}, boy %{lay['top_frac'] * 100:.0f}-%{lay['bottom_frac'] * 100:.0f}")
            if why and self.s.strict_layout:
                reason = why
                if any(k in why for k in ("çok geniş", "çok dar", "yere kadar uzanmıyor")):
                    tur_ = "sahne_geometri"           # afiş oranı/boyu ürüne uymuyor: sahne geometrisi hatası (kalite değil)
        else:
            reason = "afiş bulunamadı"
        alg = {k: det.metrics.get(k) for k in ("ust_bant_orani", "yan_tasma_orani", "yan_tasma_orani_ilk", "yan_kirpilan_oran")
               if det.metrics.get(k) is not None}
        if reason:
            _log(f"{label} elendi: {reason}")
            return {"ok": False, "tur": tur_, "neden": reason, "det": det, "lay": lay, "extra": {"algilama": alg}}
        try:
            out, info = cp.composite(img, design, det, mode="tam_kumas", profile=prof, sinir=sinir)
        except Exception as e:                           # geometri çıkarılamadı: sahne elenir, iş durmaz
            _log(f"{label} elendi: kumaş geometrisi çıkarılamadı ({e.__class__.__name__}: {e})")
            return {"ok": False, "tur": "sahne_geometri", "neden": f"kumaş geometrisi çıkarılamadı: {e}", "det": det, "lay": lay,
                    "extra": {"algilama": alg}}
        tk_info = {k: info[k] for k in ("px_per_cm", "asili_cm", "gizli_cm", "v_gizli", "temas_y", "birikme", "temas_yontemi",
                                        "olcek_farki", "dikey_olcek", "gizli_murekkep", "sorunlar", "uyarilar")}
        tk_info.update({k: info.get(k) for k in ("yayilma_supheli", "yayilma_sol_px", "yayilma_sag_px", "kivrim_kaymasi", "kenar_sigma_px", "yerlesim_donusumu", "dortgen", "kenar_sapmasi", "kumas_disi_baski")})
        tk_info.update({k: info.get(k) for k in ("temas_belirsiz", "birikme_bandi", "yayilma_baslangic_y", "yayilma_temas_asili_cm",
                                                 "gorunen_murekkep", "temas_cizgisi")})
        if sinir:
            tk_info["manuel_sinir"] = sinir
        if info["sorunlar"]:
            tur = info["sorunlar"][0]["tur"]
            msg = " ".join(x["mesaj"] for x in info["sorunlar"])
            _log(f"{label} elendi ({product.HATA_TURLERI.get(tur, tur)}): {msg}")
            extra = {"tam_kumas": tk_info, "algilama": alg}
            if tur == "sahne_geometri":
                # Kararlı ölçüm doğru ölçüm demek değildir: farkın sınır seçiminden mi, sahnedeki kumaştan mı geldiğini ayır.
                try:
                    sk = sinir_kaniti.olc(img, prof.en_cm, prof.boy_cm, det=det)
                    extra["sinir_araligi"] = {"asili_min": sk["asili_aralik"][0], "asili_max": sk["asili_aralik"][1],
                                              "kaynak": sk["kaynak"].split(" ")[0]}
                except Exception:
                    pass
            kars = None
            if info.get("temas_belirsiz") and info.get("yayilma_baslangic_y"):
                # TANI karşılaştırması: A) genişlemenin başladığı satır temas (eski davranış), B) kumaşın görünen alt kenarı.
                # İkisi de fiziksel ölçekte; tasarım kırpılmaz, yazı taşınmaz, oran esnetilmez.
                try:
                    yy = float(info["yayilma_baslangic_y"])
                    out_a, info_a = cp.composite(img, design, det, mode="tam_kumas", profile=prof,
                                                 sinir={"alt": [(0.0, yy), (float(img.shape[1]), yy)]})
                    kars = [{"etiket": "A) Genişlemenin başladığı satır = temas (eski davranış)", "out": out_a, "info": info_a},
                            {"etiket": "B) Kumaşın görünen alt kenarı (etek ucu) = temas", "out": out, "info": info}]
                    extra["temas_karsilastirma"] = {
                        "yayilma": {"asili_cm": round(info_a["asili_cm"], 1), "gizli_cm": round(info_a["gizli_cm"], 1),
                                    "gorunen_murekkep": info_a.get("gorunen_murekkep")},
                        "etek_ucu": {"asili_cm": round(info["asili_cm"], 1), "gizli_cm": round(info["gizli_cm"], 1),
                                     "gorunen_murekkep": info.get("gorunen_murekkep")}}
                except Exception:
                    kars = None
            return {"ok": False, "tur": tur, "neden": msg, "det": det, "lay": lay, "extra": extra, "tani_out": out,
                    "tani_karsilastirma": kars}
        quality = layout.score(lay, pa) if lay else 50.0
        tk_info["algilama"] = alg
        return {"ok": True, "tur": None, "neden": None, "det": det, "lay": lay, "info": info, "tk_info": tk_info,
                "out": out, "kalite": quality}

    def _tani_kaydet(self, job, base, out, rec, prof, kars=None) -> str | None:
        """Kabul EDİLMEMİŞ sahnenin tasarımlı tanı önizlemesi: yalnız onizleme/ altına, adı "_TANI_" içerir, üzerinde
        "ürün çıktısı değil" şeridi ve kalan yerleşim sorunları yazılır. foto/ klasörüne ve fotoğraf listesine GİRMEZ."""
        try:
            os.makedirs(os.path.join(job, "onizleme"), exist_ok=True)
            ad = f"onizleme/{base}_TANI_urun_ciktisi_degil.jpg"
            if kars:
                im = sinir_kaniti.tani_karsilastirma(kars, sinir_kaniti.kalan_sorunlar(rec, prof.boy_cm), prof.boy_cm)
            else:
                im = sinir_kaniti.tani_onizlemesi(out, sinir_kaniti.kalan_sorunlar(rec, prof.boy_cm))
            cvio.imwrite(os.path.join(job, ad), im, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return ad
        except Exception as e:                       # tanı görseli yan üründür; iş durmaz
            self.log(f"Tanı önizlemesi yazılamadı: {e.__class__.__name__}")
            return None

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
        if ev.get("kararlilik_uyarisi"):
            rec["uyari"] = list(rec["uyari"]) + [ev["kararlilik_uyarisi"]]
        if (det.metrics.get("yan_kirpilan_oran") or 0) > 0:
            rec["uyari"] = list(rec["uyari"]) + [
                f"Algılama maskesi duvara taşmıştı (satırların %{det.metrics.get('yan_tasma_orani_ilk', 0) * 100:.0f}'i); kumaş "
                "kenarları gövdenin düz kenarlarından kestirildi. Kenarları gözle kontrol edin."]
        if ev.get("kurtarma"):
            rec["kurtarma"] = ev["kurtarma"]
            sec = ev["kurtarma"].get("secilen") or {}
            rec["uyari"] = list(rec["uyari"]) + [
                "Kumaş ilk algılamada yanlış bulundu; aynı görselde " + ("alternatif kumaş adayıyla" if sec.get("kaynak") == "yerel_aday"
                else "görsel kontrolün bölge önerisiyle yeniden algılanarak") + " doğrulandı. Gözle kontrol edin."]
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
    def recompose_from_scenes(self, src_job: str, name: str | None = None, elenen_ham: bool = False) -> dict:
        """Var olan bir işin KAYITLI boş sahnelerine (sahneler_bos/sNN.png) aynı tasarımı güncel kodla yeniden yerleştirir.
        Yeni bir iş klasörü açar; kaynak işe ve görsellerine DOKUNMAZ. Sağlayıcı/selector hiç kullanılmaz.
        Kalite kapısı, tam kumaş yerleşimi ve sonuç kaydı generate_photos ile aynı fonksiyonlardan geçer."""
        src = self.report_of(src_job)
        photos = [dict(p, _yol=os.path.join("sahneler_bos", p["stem"] + ".png")) for p in src.get("fotograflar", []) if p.get("stem")]
        if elenen_ham:            # elenen sahnelerin KAYITLI HAM görüntüleri (algılama katmanlı görüntü kullanılmaz)
            for e in src.get("elenenler", []):
                if e.get("ham_dosya"):
                    photos.append({"stem": f"elenen_c{int(e.get('cagri') or 0):02d}", "_yol": e["ham_dosya"], "ad": None,
                                   "servis": e.get("servis"), "kurdele": None, "_elenen": True})
        if not photos:
            raise ProviderError("Kaynak işte kayıtlı sahne yok (fotoğraf kaydı ya da elenenlerin ham görüntüsü bulunamadı).")
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
            spath = os.path.join(src_job, p["_yol"])
            img = cvio.imread(spath, cv2.IMREAD_COLOR) if os.path.exists(spath) else None
            kaynak = {"is": src_name, "stem": p["stem"], "foto": p.get("ad"), "servis": p.get("servis"), "dosya": p["_yol"],
                      "onceki_karar": "elendi" if p.get("_elenen") else "kabul"}
            if img is None:
                rap["elenenler"].append({"cagri": 0, "servis": None, "tur": "kalite_kapisi", "neden": f"kayıtlı sahne okunamadı: {p['stem']}",
                                         "kaynak": kaynak})
                continue
            img = self._upscale(img)
            ev = self._degerlendir_kurtar(img, design, prof, f"Kayıtlı sahne {p['stem']}")
            if not ev["ok"]:
                rec = {"cagri": 0, "servis": None, "tur": ev["tur"], "neden": ev["neden"], "kaynak": kaynak}
                if ev.get("lay"):
                    rec["olcum"] = ev["lay"]
                rec.update(ev.get("extra") or {})
                rec["sade_neden"] = deneme_kayit.sade_neden(rec, prof.boy_cm)
                rec["siniflama"] = deneme_kayit.kontrol_sonucu(rec, prof.oran, prof.boy_cm)
                if ev.get("tani_out") is not None:
                    rec["tani_dosya"] = self._tani_kaydet(job, p["stem"], ev["tani_out"], rec, prof, kars=ev.get("tani_karsilastirma"))
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

    def manuel_sinir(self, src_job: str, dosya: str, ust=None, alt=None, koseler=None) -> dict:
        """MANUEL KURTARMA (K-55): kayıtlı AYNI sahnede kullanıcının verdiği sınırlarla yeni, ayrı sonuç üretir. Yeni üretim yok,
        sağlayıcı çağrısı yok; kaynak işe dokunulmaz.
          ust / alt : iki nokta [[x, y], [x, y]] (0-1 kadraj oranı) — kumaşın üst kenarı / zemine temas çizgisi.
          koseler   : dört nokta [sol-üst, sağ-üst, sağ-alt, sol-alt] (0-1). Verilirse kumaş bölgesi bu dörtgendir (otomatik
                      maske dörtgenle örtüşüyorsa kesişimi alınır: kurdele gibi önündeki nesneler korunur); üst/alt kenarlar köşelerden.
        Bütün kontroller aynen uygulanır (±%3, gizli bölgede baskı, kıvrım...). Tolerans tasarımı esnetme izni değildir;
        sonuç uymazsa kabul edilmez, tanı önizlemesi yazılır."""
        def pts(v, n):
            if v is None:
                return None
            if not (isinstance(v, (list, tuple)) and len(v) == n and all(isinstance(q, (list, tuple)) and len(q) == 2 for q in v)):
                raise ProviderError("Geçersiz nokta listesi.")
            out = [(float(q[0]), float(q[1])) for q in v]
            if not all(0.0 <= a <= 1.0 and 0.0 <= b <= 1.0 for a, b in out):
                raise ProviderError("Noktalar 0-1 aralığında olmalı.")
            return out
        ust, alt, koseler = pts(ust, 2), pts(alt, 2), pts(koseler, 4)
        if koseler is None and ust is None and alt is None:
            raise ProviderError("Üst/alt çizgisi ya da dört köşe gerekli.")
        src = self.report_of(src_job)
        spath = os.path.normpath(os.path.join(src_job, dosya))
        if not spath.startswith(os.path.normpath(src_job) + os.sep) or not os.path.exists(spath):
            raise ProviderError("Kayıtlı sahne bulunamadı.")
        files = glob.glob(os.path.join(src_job, "tasarim.*"))
        if not files:
            raise ProviderError("Kaynak işte tasarım dosyası yok.")
        prof = self._profile(src)
        src_name = os.path.basename(src_job)
        job = self.new_job(files[0], src.get("kategori", "Düğün"), f"manuel_{src_name.split('_')[0]}", profile=prof)
        rap = self.report_of(job)
        rap.update(islem="manuel_sinir", kaynak_is=src_name, saglayici_cagrisi=0)
        img = self._upscale(cvio.imread(spath, cv2.IMREAD_COLOR))
        H, W = img.shape[:2]
        px = lambda q: (q[0] * W, q[1] * H)
        det = None
        if koseler:
            poly = np.array([px(q) for q in koseler], np.float32)
            pm = np.zeros((H, W), np.uint8)
            cv2.fillPoly(pm, [poly.astype(np.int32)], 1)
            oto = bd.detect(img, {"kind": "fabric"})
            om = cv2.dilate((oto.mask > 0).astype(np.uint8), np.ones((15, 15), np.uint8))
            kes = pm & om
            mask = kes if kes.sum() >= 0.85 * pm.sum() else pm
            det = bd.detect(img, {"kind": "fabric", "polygon": [list(q) for q in koseler]})
            det.mask = (mask * 255).astype(np.uint8)
            ust, alt = [koseler[0], koseler[1]], [koseler[3], koseler[2]]
        sinir = {}
        if ust:
            sinir["ust"] = [px(q) for q in ust]
        if alt:
            sinir["alt"] = [px(q) for q in alt]
        design = self._design(job)
        design_file = glob.glob(os.path.join(job, "tasarim.*"))[0]
        self.log(f"Manuel sınır: kaynak {src_name}/{dosya}; sağlayıcıya istek GÖNDERİLMEZ (ücretsiz).")
        ev = self._evaluate_scene_tek(img, design, prof, "Manuel sınır", det=det, sinir=sinir)
        kayit = {"ust": ust, "alt": alt, "koseler": koseler}
        kaynak = {"is": src_name, "dosya": dosya, "onceki_karar": "elendi"}
        if ev["ok"]:
            rec = self._save_accepted(job, rap, img, ev, prof, None, 1, "kayitli_sahne", design_file)
            rec["kaynak"], rec["manuel_sinir"] = kaynak, kayit
            rec["uyari"] = list(rec["uyari"]) + ["Kumaş sınırları KULLANICI tarafından elle verildi (otomatik ölçüm değil)."]
            sonuc = "kabul"
        else:
            rec = {"cagri": 0, "servis": None, "tur": ev["tur"], "neden": ev["neden"], "kaynak": kaynak, "manuel_sinir": kayit}
            if ev.get("lay"):
                rec["olcum"] = ev["lay"]
            rec.update(ev.get("extra") or {})
            rec["sade_neden"] = deneme_kayit.sade_neden(rec, prof.boy_cm)
            rec["siniflama"] = deneme_kayit.kontrol_sonucu(rec, prof.oran, prof.boy_cm)
            if ev.get("tani_out") is not None:
                rec["tani_dosya"] = self._tani_kaydet(job, "manuel", ev["tani_out"], rec, prof)
            rap["elenenler"].append(rec)
            sonuc = "kabul_edilmedi"
        rap["son_uretim"] = {"hedef": 1, "uretilen": int(ev["ok"]), "eksik": int(not ev["ok"]), "cagri": 0, "saglayici_cagrisi": 0,
                             "beklemede": False}
        self._overview(job, rap)
        _write_json(os.path.join(job, "rapor.json"), rap)
        self.progress(1.0, "Manuel sınırla yerleştirme bitti (servis çağrısı yok)")
        return {"job": os.path.basename(job), "sonuc": sonuc, "tur": ev["tur"], "neden": ev["neden"]}

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

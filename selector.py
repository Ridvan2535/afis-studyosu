# -*- coding: utf-8 -*-
"""
Otomatik servis seçimi ("Otomatik" modu).

Kullanıcı hangi servisin daha iyi olduğunu elle denemek zorunda kalmasın diye: anahtarı girilmiş her servis bir
"kol" sayılır. Her çağrının sonucu (kalite kapısından geçti mi, hata verdi mi, kalite puanı) kaydedilir ve sonraki
çağrılarda daha başarılı olan servise daha sık başvurulur (Thompson örneklemesi: iyi servis çoğunlukla seçilir, ama
az denenmiş servis de zaman zaman şans bulur; böylece bir kez şanssız gelen servis sonsuza dek dışlanmaz).

  * Bir serviste üst üste 3 hata olursa (anahtar reddi dahil) o iş boyunca devre dışı kalır, iş diğerleriyle sürer.
  * Sonuçlar `servis_karnesi.json` dosyasında saklanır; sonraki çalıştırmalar sıfırdan denemez, öğrendiğiyle başlar.
    Sahne istemi/servis kodu değiştiğinde SELECTOR_VERSION artırılır ve karne sıfırlanır (eski bilgi yanıltmasın).
  * Harcama tavanı değişmez: toplam çağrı sayısını çağıran taraf (max_scene_calls / max_video_tries) sınırlar.
"""
from __future__ import annotations

import json
import os
import random

SELECTOR_VERSION = "10"          # istem/servis kodu değişince artır: eski karne geçersiz sayılır
CONSEC_ERR_LIMIT = 3

NICE = {
    "openai": "OpenAI (GPT görsel)", "gemini": "Gemini", "magnific": "Magnific (Seedream, yalnız istem)", "magnific-edit": "Magnific Seedream 4.5 Edit",
    "magnific-edit-pro": "Magnific Seedream 5 Pro Edit",
    "veo-3-1": "Veo 3.1", "veo-3-1-fast": "Veo 3.1 Fast", "kling-pro": "Kling Pro", "runway-4-5": "Runway Gen-4.5",
    "tv-kling": "TopView Kling 3.0 Turbo", "tv-veo": "TopView Veo 3.1", "tv-seedance": "TopView Seedance 2.5",
    "mock": "Deneme modu", "mock_bad": "Deneme (kötü)", "mock_err": "Deneme (hatalı)", "mock_thin": "Deneme (ince afiş)", "mock_vbad": "Deneme video (kötü)",
}


def nice(name: str) -> str:
    return NICE.get(name, name)


def _blank():
    return {"calls": 0, "ok": 0, "err": 0, "qual": 0.0}


class Selector:
    def __init__(self, kind, names, path=None, rng=None, log=print, persist=True, explore=0.0):
        self.kind, self.names, self.path, self.log = kind, list(names), path, log
        self.explore = float(explore)                # 0-1: bu oranda çağrıda en az denenmiş servise şans verilir (sahne için küçük)
        self.persist = bool(persist and path)
        self.rng = rng or random.Random()
        hist = {}
        if self.persist and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("version") == SELECTOR_VERSION:
                    hist = data.get("kinds", {}).get(kind, {})
            except Exception:
                hist = {}
        self.hist = {n: {**_blank(), **hist.get(n, {})} for n in self.names}
        self.run = {n: _blank() for n in self.names}
        self.consec = {n: 0 for n in self.names}
        self.off = {}                                # ad -> neden (bu iş boyunca)

    # -- seçim -------------------------------------------------------------------------------
    def active(self):
        return [n for n in self.names if n not in self.off]

    # Not: record() her sonucu hem hist'e hem run'a yazar; yani hist zaten "kalıcı karne + bu iş" toplamıdır.
    # Seçim hesabı yalnız hist'i kullanır (hist + run bu işin sonuçlarını iki kez sayardı). run yalnız raporlama içindir.
    # SELECTOR_VERSION bilerek artırılmadı: save() yalnız hist yazdığından dosyadaki karnede çift sayım hiç olmadı;
    # sürümü artırmak kullanıcının doğru öğrenilmiş verisini boşa sıfırlardı.
    def _calls(self, n):
        return self.hist[n]["calls"]

    def pick(self, exclude=()):
        cands = [n for n in self.active() if n not in exclude]
        if not cands:
            return None
        fresh = [n for n in cands if self._calls(n) < 1]
        if fresh:                                     # hiç denenmemiş servis önce (listedeki sıra öncelik)
            return fresh[0]
        if self.explore and len(cands) > 1 and self.rng.random() < self.explore:
            return min(cands, key=lambda n: (self._calls(n), self.names.index(n)))     # şanssız bir ilk sonuç servisi sonsuza dek dışlamasın
        best, best_v = None, -1.0
        for n in cands:
            h = self.hist[n]                                                 # hist bu işi zaten içerir (bkz. _calls)
            calls = h["calls"]
            reward = min(h["qual"] / 100.0, calls)          # kabul ve kalite birlikte: %100 kaliteyle kabul = 1 puan
            v = self.rng.betavariate(1 + reward, 1 + max(calls - reward, 0))
            if v > best_v:
                best, best_v = n, v
        return best

    # -- sonuç -------------------------------------------------------------------------------
    def record(self, name, ok, quality=None, error=False):
        if ok and quality is None:
            quality = 80.0                                  # puan verilmediyse kabul edilmiş sonuç "iyi" sayılır
        for d in (self.hist[name], self.run[name]):
            d["calls"] += 1
            d["ok"] += 1 if ok else 0
            d["err"] += 1 if error else 0
            d["qual"] += float(quality or 0.0) if ok else 0.0
        self.consec[name] = self.consec[name] + 1 if error else 0
        if self.consec[name] >= CONSEC_ERR_LIMIT:
            self.disable(name, f"üst üste {CONSEC_ERR_LIMIT} hata")

    def disable(self, name, reason):
        if name not in self.off:
            self.off[name] = reason
            self.log(f"{nice(name)} bu işte devre dışı bırakıldı: {reason}")

    # -- rapor -------------------------------------------------------------------------------
    def table(self):
        rows = []
        for n in self.names:
            r, h = self.run[n], self.hist[n]
            rows.append({"servis": n, "ad": nice(n), "cagri": r["calls"], "kabul": r["ok"], "hata": r["err"],
                         "oran": round(r["ok"] / r["calls"], 3) if r["calls"] else None,
                         "kalite": round(r["qual"] / r["ok"], 1) if r["ok"] else None,
                         "toplam_cagri": h["calls"], "toplam_kabul": h["ok"],
                         "toplam_oran": round(h["ok"] / h["calls"], 3) if h["calls"] else None,
                         "devre_disi": self.off.get(n)})
        return rows

    def winner(self):
        """Bu iş için en iyi servis: kabul oranı x ortalama kalite (en az 1 kabul)."""
        rows = [r for r in self.table() if r["kabul"] > 0]
        if not rows:
            return None
        # çağrı başına ortalama ödül = kabul oranı x ortalama kalite (ör. her çağrı kabul + 90 puan = 0.9)
        rows.sort(key=lambda r: ((r["kabul"] / r["cagri"]) * ((r["kalite"] or 0) / 100.0), r["kabul"]), reverse=True)
        return rows[0]["servis"]

    def summary_line(self):
        parts = []
        for r in self.table():
            if r["cagri"]:
                parts.append(f"{r['ad']}: {r['kabul']}/{r['cagri']} kabul" +
                             (f", kalite {r['kalite']:.0f}" if r["kalite"] is not None else "") +
                             (f", {r['hata']} hata" if r["hata"] else ""))
        return " · ".join(parts)

    def save(self):
        if not self.persist:
            return
        try:
            data = {}
            if os.path.exists(self.path):
                try:
                    with open(self.path, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            if data.get("version") != SELECTOR_VERSION:
                data = {"version": SELECTOR_VERSION, "kinds": {}}
            data.setdefault("kinds", {})[self.kind] = self.hist
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass                                      # karne yazılamıyorsa iş yine de sürer


def overview(path) -> dict:
    """Kalıcı karnenin özeti (arayüzdeki 'Servis karnesi' kartı için): {'scene': [...], 'video': [...]}."""
    out = {"scene": [], "video": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return out
    if data.get("version") != SELECTOR_VERSION:
        return out
    for kind, hist in data.get("kinds", {}).items():
        rows = []
        for n, h in hist.items():
            if str(n).startswith("mock"):
                continue
            c, ok = int(h.get("calls", 0)), int(h.get("ok", 0))
            rows.append({"servis": n, "ad": nice(n), "cagri": c, "kabul": ok, "hata": int(h.get("err", 0)),
                         "oran": round(ok / c, 3) if c else 0.0, "kalite": round(h.get("qual", 0.0) / ok, 1) if ok else None})
        rows.sort(key=lambda r: (r["oran"], r["cagri"]), reverse=True)
        out[kind] = rows
    return out

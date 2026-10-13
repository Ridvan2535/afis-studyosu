# -*- coding: utf-8 -*-
"""
Uygulamanın OTOMATİK görsel kontrol servisi (K-49, 2026-10-13).

Bu, Claude Code'daki geliştirme ajanı `visual-inspector` DEĞİLDİR. Ajan dosyası (.claude/agents) yalnız geliştirme
oturumlarında elle çalıştırılır; uygulama onu çağıramaz. Bu modül uygulamanın üretim akışından çağrılabilen ayrı bir
servistir.

Durumlar (belgelerde ayrı gösterilir):
  * HAZIR     : kod, bütçe sınırı, sahte servis ve testler var.
  * BAĞLI     : Ayarlar'da `gorsel_kontrol_servisi = "claude"` ve bir Anthropic API anahtarı girilmişse. Varsayılan "kapali".
  * GERÇEK ÇAĞRIYLA DOĞRULANDI: HAYIR (2026-10-13 itibarıyla hiç gerçek çağrı yapılmadı).

Ne zaman çağrılır (orchestrator._kurtar): yalnız algılama ŞÜPHELİ ise ve aynı ham görseldeki yerel alternatif kumaş
adayları doğrulanamamışsa; sahne başına en fazla 1, iş başına en fazla `gorsel_kontrol_is_basina_en_fazla`, günlük tahmini
harcama `gorsel_kontrol_gunluk_tavan_usd` altında. Yeni sahne üretmez.

Servisin yanıtı yalnız BÖLGE ÖNERİSİ olarak kullanılır: kumaşın kutusu (0-1 oranlı) yeniden algılamaya ipucu olur; yeni
maske programın bütün kontrollerinden ve kararlılık testinden geçmeli ve önerilen kutunun içinde kalmalıdır. Servis
"uygun" dedi diye maskeye baskı yapılmaz.

Resmî belgelerden DOĞRULANAN (2026-10-13, ağdan okundu; gerçek çağrı DEĞİL):
  * Model kimliği `claude-sonnet-5-5` güncel modeller tablosunda var; görsel (image) girdisi destekli.
    Kaynak: https://platform.claude.com/docs/en/models/overview
  * Fiyat: Sonnet 5.5 girdi 2 $ / milyon jeton, çıktı 10 $ / milyon jeton (Opus 5.5: 4/20, Haiku 5.5: 0,10/0,50 —
    100.000 jeton altı istemler). Kaynak: https://platform.claude.com/docs/en/about-claude/pricing
    Not: yalnız ABD'de çıkarım (inference_geo "us") seçilirse 1,1 kat; bu modül o parametreyi göndermez.
  * Uç nokta POST https://api.anthropic.com/v1/messages; örnekte başlıklar X-Api-Key, anthropic-version: 2023-06-01,
    Content-Type: application/json (belge anthropic-version'ı "isteğe bağlı" diye listeler). Yanıtta usage.input_tokens /
    usage.output_tokens var. Kaynak: https://platform.claude.com/docs/en/api/messages/create
  * Görsel bloğu {"type":"image","source":{"type":"base64","media_type":...,"data":...}}; JPEG/PNG/GIF/WebP; görsel
    jetonu ceil(w/28)*ceil(h/28); görsel başına en fazla 10 MB (base64). Kaynak:
    https://platform.claude.com/docs/en/build-with-claude/vision

DOĞRULANMAMIŞ (gerçek çağrı yapılmadı; kesin bilgi değildir):
  * Çağrı başına maliyet: TAHMİN. 1024 px sahne (ceil(1024/28)^2 = 1.369 jeton) + 512 px aday görseli (361) + istem metni
    (ölçülmedi, ~1.500 varsayıldı) ≈ 3.300 girdi, ≤ 600 çıktı -> ≈ 0,013 $. Bütçe sayacı gerçek çağrıda usage alanından
    hesaplar; tahmin yalnız "izin var mı" ön kontrolünde kullanılır.
  * Modelin bu istemle geçerli JSON döndürdüğü, kutu önerisinin doğruluğu, yanıt süresi: hiç denenmedi.
Anahtar ve base64 görsel hiçbir kayda/rapora yazılmaz.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date

import cv2
import numpy as np

API_URL = "https://api.anthropic.com/v1/messages"
API_SURUM = "2023-06-01"
VARSAYILAN_MODEL = "claude-sonnet-5-5"
FIYAT_USD_M = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50)}
TAHMINI_GIRDI, TAHMINI_CIKTI = 3300, 600
KULLANIM_DOSYASI = "gorsel_kontrol_kullanim.json"      # yalnız sayaçlar; anahtar yok

ISTEM = (
    "Bir etkinlik sahnesi fotoğrafında stand üzerinde asılı BOŞ krem/beyaz kumaş afiş aranıyor. Ürün oranı (en/boy) {oran:.3f}. "
    "Görsel 1: sahnenin tamamı. Görsel 2: aynı sahne üzerinde programın kumaş ADAYLARI numaralı renkli çerçevelerle. "
    "Görevin: sahnede kumaş afiş nerede, kendi gözünle bul. Programın adaylarını doğru kabul etme. Santimetre yazma. "
    "Yalnız şu JSON'u döndür: {{\"kumas_var\": true|false, \"aday_no\": <doğru adayın numarası ya da null>, "
    "\"kumas_kutusu\": [x0, y0, x1, y1] (0-1 oranlı, kumaşın yalnız asılı kısmı) ya da null, "
    "\"durum\": \"uygun\"|\"inceleme_gerekli\"|\"uygun_degil\", \"gerekce\": \"kısa\", \"belirsizlik\": \"kısa\"}}"
)


@dataclass
class Sonuc:
    durum: str
    kumas_kutusu: list | None = None
    aday_no: int | None = None
    gerekce: str = ""
    belirsizlik: str = ""
    model: str | None = None
    kullanim: dict = field(default_factory=dict)
    tahmini_usd: float = 0.0


class KapaliServis:
    ad, etkin = "kapali", False

    def incele(self, img, adaylar, oran):
        return None


class SahteServis:
    """Testler için: önceden verilen yanıtları sırayla döndürür (ağ yok, ücret yok)."""
    ad, etkin = "sahte", True

    def __init__(self, yanitlar):
        self.yanitlar = list(yanitlar)
        self.cagri = 0

    def incele(self, img, adaylar, oran):
        self.cagri += 1
        y = self.yanitlar.pop(0) if self.yanitlar else None
        return Sonuc(**y, model="sahte", tahmini_usd=0.0) if y else None


def aday_gorseli(img, adaylar, uzun=512):
    """Adayların numaralı çerçeveleri (maske dış hatları) — servise gider; yerelde de inceleme için kullanılır."""
    h, w = img.shape[:2]
    f = uzun / max(h, w)
    vis = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    renk = [(0, 0, 255), (255, 0, 0), (0, 200, 0), (0, 200, 255), (255, 0, 255)]
    for i, d in enumerate(adaylar):
        m = cv2.resize((d.mask > 0).astype(np.uint8), (vis.shape[1], vis.shape[0]), interpolation=cv2.INTER_NEAREST)
        cn, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(vis, cn, -1, renk[i % len(renk)], 2)
        ys, xs = np.nonzero(m)
        if len(xs):
            cv2.putText(vis, str(i + 1), (int(xs.mean()) - 8, int(ys.mean())), cv2.FONT_HERSHEY_SIMPLEX, 0.9, renk[i % len(renk)], 3)
    return vis


def _jpeg_b64(img, uzun):
    h, w = img.shape[:2]
    f = min(1.0, uzun / max(h, w))
    if f < 1:
        img = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(buf.tobytes()).decode("ascii")


class ClaudeServis:
    """Anthropic Messages API ile görsel kontrol. HAZIR ama gerçek çağrıyla DOĞRULANMADI. Tek POST, kör yeniden deneme yok."""
    ad, etkin = "claude", True

    def __init__(self, api_key: str, model: str = VARSAYILAN_MODEL, zaman_asimi: int = 60):
        if not api_key:
            raise ValueError("görsel kontrol için Anthropic API anahtarı girilmemiş")
        self._key, self.model, self.zaman_asimi = api_key, model, zaman_asimi

    def incele(self, img, adaylar, oran):
        import requests
        govde = {"model": self.model, "max_tokens": 600, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _jpeg_b64(img, 1024)}},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                          "data": _jpeg_b64(aday_gorseli(img, adaylar), 512)}},
            {"type": "text", "text": ISTEM.format(oran=oran)}]}]}
        r = requests.post(API_URL, json=govde, timeout=self.zaman_asimi,
                          headers={"x-api-key": self._key, "anthropic-version": API_SURUM, "content-type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"görsel kontrol servisi HTTP {r.status_code}")          # gövde (olası anahtar yankısı) yazılmaz
        j = r.json()
        metin = "".join(c.get("text", "") for c in j.get("content", []) if c.get("type") == "text")
        u = j.get("usage") or {}
        gi, ci = FIYAT_USD_M.get(self.model, (4.0, 20.0))
        usd = (u.get("input_tokens", 0) * gi + u.get("output_tokens", 0) * ci) / 1e6
        return yanit_coz(metin, model=self.model, kullanim={k: u.get(k) for k in ("input_tokens", "output_tokens")}, usd=usd)


def yanit_coz(metin: str, model=None, kullanim=None, usd=0.0) -> Sonuc | None:
    """Model metninden JSON'u çıkarır ve DOĞRULAR; bozuksa None (tahminle doldurulmaz)."""
    m = re.search(r"\{.*\}", metin or "", re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except ValueError:
        return None
    durum = j.get("durum")
    if durum not in ("uygun", "inceleme_gerekli", "uygun_degil"):
        return None
    kutu = j.get("kumas_kutusu")
    if kutu is not None:
        if not (isinstance(kutu, list) and len(kutu) == 4 and all(isinstance(v, (int, float)) for v in kutu)):
            kutu = None
        else:
            x0, y0, x1, y1 = [float(min(1, max(0, v))) for v in kutu]
            kutu = [x0, y0, x1, y1] if (x1 - x0) > 0.03 and (y1 - y0) > 0.1 else None
    an = j.get("aday_no")
    return Sonuc(durum=durum, kumas_kutusu=kutu, aday_no=an if isinstance(an, int) else None,
                 gerekce=str(j.get("gerekce", ""))[:400], belirsizlik=str(j.get("belirsizlik", ""))[:400],
                 model=model, kullanim=kullanim or {}, tahmini_usd=round(usd, 5))


def servis_olustur(settings):
    tur = getattr(settings, "gorsel_kontrol_servisi", "kapali")
    if tur == "claude":
        return ClaudeServis(getattr(settings, "anthropic_key", ""), getattr(settings, "gorsel_kontrol_modeli", VARSAYILAN_MODEL))
    return KapaliServis()


class Butce:
    """Sahne / iş / gün sınırları. Gerçek kullanım (usage) varsa onunla, yoksa tahminle sayar."""

    def __init__(self, settings, klasor: str):
        self.s, self.yol = settings, os.path.join(klasor, KULLANIM_DOSYASI)
        self.is_cagri = 0

    def _oku(self):
        try:
            with open(self.yol, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def izin(self) -> tuple[bool, str]:
        en_fazla = int(getattr(self.s, "gorsel_kontrol_is_basina_en_fazla", 3) or 0)
        if self.is_cagri >= en_fazla:
            return False, f"iş başına görsel kontrol sınırı ({en_fazla}) doldu"
        tavan = float(getattr(self.s, "gorsel_kontrol_gunluk_tavan_usd", 0.5) or 0)
        model = getattr(self.s, "gorsel_kontrol_modeli", VARSAYILAN_MODEL)
        gi, ci = FIYAT_USD_M.get(model, (4.0, 20.0))
        tahmin = (TAHMINI_GIRDI * gi + TAHMINI_CIKTI * ci) / 1e6
        bugun = self._oku().get(date.today().isoformat(), {"usd": 0.0})
        if bugun["usd"] + tahmin > tavan:
            return False, f"günlük görsel kontrol tavanı ({tavan:.2f} $) aşılacaktı"
        return True, ""

    def kaydet(self, usd: float):
        self.is_cagri += 1
        d = self._oku()
        g = d.setdefault(date.today().isoformat(), {"usd": 0.0, "cagri": 0})
        g["usd"] = round(g["usd"] + float(usd or 0), 5)
        g["cagri"] = g.get("cagri", 0) + 1
        tmp = self.yol + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, self.yol)

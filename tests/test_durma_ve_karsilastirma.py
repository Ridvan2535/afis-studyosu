# -*- coding: utf-8 -*-
"""
Durma sınırları ve prompt sürümü karşılaştırma kuralları — SAHTE SERVİS / yerel test (ağ yok, ücretsiz).

A. Durma (K-30, K-33):
   1. Farklı nedenlerle art arda elenen çağrılar aynı-hata sınırına takılmaz ama SONUÇSUZ çağrı sınırında durur.
   2. Kabul gelince sonuçsuz sayacı sıfırlanır (durma, kabulden sonraki N. sonuçsuz çağrıda olur).
   3. Servis hataları da sonuçsuz sayılır. 4. Sınırlar kapalıyken toplam çağrı tavanı geçerlidir.
   5. Geriye dönük simülasyon, orkestratörün gerçek durduğu çağrıyla AYNI sonucu verir.
   6. 2026-10-13 işinin (14 çağrı) kayıtlı sırasıyla sınır tablosu beklenen çağrılarda durur.
B. Karşılaştırma (K-28, K-32):
   1. Referans kümesi / ölçü / ayar farklıysa "karşılaştırılamaz". 2. Anahtar alanı eksik eski kayıt "karşılaştırılamaz".
   3. Etkin sürümde tek başarısız deneme varken aday ÖNERİLMEZ. 4. Beğeni verisi yoksa sıfır beğeni sayılmaz (yetersiz veri).
   5. Yeterli ve eşleşen veride aday önerilir ya da etkin kalır; öneri ayarı DEĞİŞTİRMEZ.
   6. Deney türleri (K-44): yalnız prompt (kılavuz aynı) ile prompt + kılavuz paketi ayrılır; kılavuz farkı paket
      karşılaştırmasını geçersiz kılmaz, değişen iki bileşen kayıtlı, paketten promptun tek etkisi iddia edilmez.
Çalıştır: python tests/test_durma_ve_karsilastirma.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import deneme_kayit as dk      # noqa: E402
import mock_provider as mp     # noqa: E402
import orchestrator as orch    # noqa: E402
import providers               # noqa: E402
from providers import ProviderError, SceneProvider, Settings   # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_durma_")
orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.REPORT_DIR = os.path.join(tmp, "raporlar")
orch.LOG_PATH = os.path.join(tmp, "kayit.log")
orch.STATS_PATH = os.path.join(tmp, "servis_karnesi.json")
design = os.path.join(tmp, "tasarim.png")
can = np.zeros((2000, 750, 4), np.uint8); can[200:600, 100:650] = (40, 40, 160, 255)
cv2.imwrite(design, can)


class Desen:
    """Çağrı sırasına göre sahne türü veren sahte servis: h=havada (kısa), u=uzun, k=kabul edilir (dokunan), e=servis hatası."""
    supports_guide = True

    def __init__(self, desen):
        self.desen, self.i, self.model = desen, 0, "mock-desen"

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None):
        c = self.desen[self.i % len(self.desen)]; self.i += 1
        if c == "e":
            raise ProviderError("sahte servis hatası")
        img, _ = mp.square_scene(1024, 0.375, {"h": "havada", "u": "uzun", "k": "dokunan"}[c], seed=self.i)
        return cv2.imencode(".png", img)[1].tobytes()


def run(desen, n, ayni, sonucsuz, tavan, supheli=False):
    impl = Desen(desen)
    orch.make_scene_provider = lambda s, log, name=None: SceneProvider(impl)
    s = Settings(scene_provider="mock", max_scene_calls=tavan, photo_long_side=0, auto_video=False,
                 ayni_hata_siniri=ayni, sonucsuz_siniri=sonucsuz, supheli_olcumde_dur=supheli)
    o = orch.Orchestrator(s, log=lambda m: None, progress=lambda f, t: None)
    job = o.new_job(design, "Düğün", "durma")
    res = o.generate_photos(job, n)
    return res, o.report_of(job)


# ---------------------------------------------------------------- A1: farklı nedenler, kabul yok -> sonuçsuz sınırında durur
res, rap = run("hu", 3, 3, 4, 10)
sig = [d["hata_imzasi"] for d in rap["denemeler"]]
print("A1:", res["cagri"], (res["durdurma"] or {}).get("neden"), sig)
assert len(set(sig)) == 2, f"desen iki farklı hata üretmeli: {sig}"
assert max(d["art_arda"] for d in rap["denemeler"]) == 1, "farklı nedenler aynı-hata serisi sayıldı"
assert res["cagri"] == 4 and res["durdurma"]["neden"] == "sonucsuz_cagri" and res["eksik"] == 3, res
# aynı koşulda sonuçsuz sınırı kapalıyken tavan kadar gider (aynı-hata sınırı tek başına yakalamaz)
res0, _ = run("hu", 3, 3, 0, 7)
assert res0["cagri"] == 7 and res0["durdurma"] is None, res0

# ---------------------------------------------------------------- A2: kabul sayacı sıfırlar
res, rap = run("hhhkhuhuhu", 3, 0, 4, 20)
kb = [d["kabulden_beri"] for d in rap["denemeler"]]
print("A2:", res["cagri"], res["uretilen"], kb)
assert kb[:5] == [1, 2, 3, 0, 1], kb
assert res["uretilen"] == 1 and res["cagri"] == 8 and res["durdurma"]["neden"] == "sonucsuz_cagri", res
assert rap["fotograflar"] and res["eksik"] == 2, "kabul edilen fotoğraf saklanmalı, eksik gösterilmeli"

# ---------------------------------------------------------------- A3: servis hatası da sonuçsuz sayılır
res, rap = run("e", 2, 5, 3, 10)
assert res["cagri"] == 3 and res["durdurma"]["neden"] == "sonucsuz_cagri", res
assert all(d["sonuc"] == "servis_hatasi" for d in rap["denemeler"])

# ---------------------------------------------------------------- A4: sınırlar kapalı -> toplam çağrı tavanı
res, _ = run("hu", 2, 0, 0, 5)
assert res["cagri"] == 5 and res["durdurma"] is None, res

# ---------------------------------------------------------------- A5: simülasyon = gerçek davranış
for desen, ayni, sonucsuz, tavan in (("hhhkhuhuhu", 0, 4, 20), ("hhuhhhh", 3, 6, 12), ("huk", 2, 3, 9), ("hhhhh", 4, 8, 14)):
    res, rap = run(desen, 3, ayni, sonucsuz, tavan)
    dizi = dk.cagri_dizisi(rap)
    sim = dk.durma_simulasyonu(dizi, ayni, sonucsuz, tavan, 3)
    assert sim["dur_cagri"] == res["cagri"] and sim["kabul"] == res["uretilen"], (desen, sim, res)
print("A5: simülasyon orkestratörle aynı noktada duruyor")

# ---------------------------------------------------------------- A6: 2026-10-13 işinin kayıtlı sırası (14 çağrı, 7 ve 11 kabul)
K, G, U, B = "sahne_geometri:kisa", "sahne_geometri:genis", "sahne_geometri:uzun", "birikme_cozulemedi:birikme"
seq = [K, K, K, B, K, K, None, K, K, U, None, K, G, K]
dizi = [{"cagri": i + 1, "sonuc": "kabul" if s is None else "elendi", "hata_imzasi": s, "turetildi": True} for i, s in enumerate(seq)]
beklenen = {(3, 0): (3, "ayni_hata", 2), (5, 0): (14, "tavan", 0), (5, 6): (6, "sonucsuz", 2),
            (5, 7): (14, "tavan", 0), (5, 8): (14, "tavan", 0), (0, 4): (4, "sonucsuz", 2)}
for (a, k), (dur, ned, kac) in beklenen.items():
    r = dk.durma_simulasyonu(dizi, a, k, 14, 3)
    assert (r["dur_cagri"], r["neden"], r["kacan_kabul"]) == (dur, ned, kac), ((a, k), r)
# eski rapordan türetme: elenen listesi + son_uretim ile aynı dizi çıkar; tutarsız kayıtta türetilmez
eski = {"son_uretim": {"cagri": 14, "uretilen": 2},
        "elenenler": [{"cagri": i + 1, "tur": s.split(":")[0], "neden": {"kisa": "kısa", "genis": "geniş", "uzun": "uzun",
                                                                          "birikme": "birik"}[s.split(":")[1]]}
                      for i, s in enumerate(seq) if s]}
assert [(x["sonuc"], x["hata_imzasi"]) for x in dk.cagri_dizisi(eski)] == [(x["sonuc"], x["hata_imzasi"]) for x in dizi]
assert dk.cagri_dizisi(dict(eski, son_uretim={"cagri": 15, "uretilen": 2})) == []
print("A6: 14 çağrılık iş sınır tablosu doğru")

# ---------------------------------------------------------------- A7: şüpheli ölçümde dur (K-36)
gercek = dk.kontrol_sonucu
dk.kontrol_sonucu = lambda rec, oran, boy=None: dict(gercek(rec, oran, boy), guven="dusuk", nedenler=["sınama: düşük güven"])
try:
    res, rap = run("hk", 2, 0, 0, 6, supheli=True)
    assert res["cagri"] == 1 and res["durdurma"]["neden"] == "supheli_olcum", res
    assert "otomatik yeni ücretli çağrı başlatılmadı" in res["durdurma"]["aciklama"]
    res, _ = run("hk", 2, 0, 0, 6, supheli=False)          # ayar kapalıysa devam eder
    assert res["cagri"] > 1, res
finally:
    dk.kontrol_sonucu = gercek
print("A7: şüpheli ölçümde otomatik yeni çağrı yok")

# ---------------------------------------------------------------- B: karşılaştırma
J = os.path.join(tmp, "karsilastirma")
AYAR = {"kadraj": "1:1", "kilavuz": True, "insanli": True, "kurdele": True, "kati_yerlesim": True, "uzun_kenar": 2400}


def is_yaz(ad, surum, sonuclar, begeni=(), kil=1, **fark):
    jp = os.path.join(J, ad); os.makedirs(jp, exist_ok=True)
    den = []
    for i, s in enumerate(sonuclar):
        d = {"cagri": i + 1, "uretim_no": 1, "prompt_surumu": surum, "model": "seedream-v5-pro-edit", "olcu_id": "75x200",
             "sahne_gorevi": "onden_kare", "referans_kumesi": "r1", "ayar_ozeti": dict(AYAR, kilavuz_surumu=kil), "sure_sn": 120,
             "sonuc": "kabul" if s == "k" else "elendi",
             "siniflama": {"kaynak": "olasi_algilama" if s == "a" else "uretim"}}
        if s == "k":
            d["foto"] = f"{i + 1:02d}_kumas.jpg"
        d.update(fark)
        den.append({k: v for k, v in d.items() if v is not None})
    json.dump({"kategori": "Düğün", "denemeler": den}, open(os.path.join(jp, "rapor.json"), "w", encoding="utf-8"))
    for foto, karar in begeni:
        dk.insan_yaz(jp, foto, karar)


def karar(aday_surum="3A-aday"):
    gr = dk.ozet(J)
    return [r for r in dk.oneriler(gr, "2A") if r["aday"] == aday_surum], gr


IYI_ADAY = "kkkkkuuuuuuu"                                     # 12 çağrı, 5 kabul
ADAY_BEGENI = [("01_kumas.jpg", "begendim"), ("02_kumas.jpg", "begendim"), ("03_kumas.jpg", "begendim")]

# B3: etkin sürümde tek başarısız deneme -> aday önerilemez
is_yaz("e1", "2A", "u")
is_yaz("a1", "3A-aday", IYI_ADAY, ADAY_BEGENI)
r, _ = karar()
assert len(r) == 1 and r[0]["karar"] == "yetersiz_veri", r
assert any("Etkin" in n and "12 çağrı" in n for n in r[0]["nedenler"]), r

# B4: etkin yeterli çağrı ama insan değerlendirmesi YOK -> sıfır beğeni sayılmaz, yetersiz veri
is_yaz("e1", "2A", "kuuuuuuuuuuuk")                         # 13 çağrı, 2 kabul, değerlendirme yok
r, gr = karar()
e = next(g for g in gr if g["prompt_surumu"] == "2A")
assert e["begeni_orani"] is None and e["insan_degerlendirmesi"] == 0, e
assert r[0]["karar"] == "yetersiz_veri" and any("insan değerlendirmesi" in n for n in r[0]["nedenler"]), r

# B5a: eşleşen ve yeterli veri -> aday önerilir
is_yaz("e1", "2A", "kuuuuuukuuuuk", [("01_kumas.jpg", "begendim"), ("08_kumas.jpg", "uygun_degil"), ("13_kumas.jpg", "begendim")])
r, _ = karar()
assert r[0]["karar"] == "aday_onerilir", r
# B5b: aday beğenisi düşükse etkin kalır
is_yaz("a1", "3A-aday", IYI_ADAY, [("01_kumas.jpg", "uygun_degil"), ("02_kumas.jpg", "uygun_degil"), ("03_kumas.jpg", "begendim")])
r, _ = karar()
assert r[0]["karar"] == "etkin_kalsin" and any("beğeni" in n for n in r[0]["nedenler"]), r
is_yaz("a1", "3A-aday", IYI_ADAY, ADAY_BEGENI)
# olası algılama retleri paydadan çıkar: 12 çağrı, 5 kabul, 4 algılama -> oran 5/8
is_yaz("a2", "3A-aday", "kkkkkaaaauuu", ADAY_BEGENI, referans_kumesi="r9")
g = next(x for x in dk.ozet(J) if x["referans_kumesi"] == "r9")
assert g["kabul_orani"] == round(5 / 8, 3), g

# B1: referans kümesi farklı -> karşılaştırılamaz (r9 için etkin grup yok)
r, _ = karar()
r9 = [x for x in dk.oneriler(dk.ozet(J), "2A") if x["olcu_id"] == "75x200" and x["karar"] == "karsilastirilamaz"]
assert r9, "farklı referans kümesi karşılaştırılamaz olmalı"
ea = {"kategori": "Düğün", "model": "m", "olcu_id": "75x200", "sahne_gorevi": "onden_kare", "referans_kumesi": "r1",
      "ayar_ozeti": AYAR, "eksik_alanlar": []}
for alan, deger in (("olcu_id", "150x400"), ("referans_kumesi", "r2"), ("ayar_ozeti", dict(AYAR, insanli=False)),
                    ("sahne_gorevi", "yandan_kare"), ("model", "baska")):
    assert dk.karsilastirilabilir(ea, dict(ea, **{alan: deger})), alan
assert dk.aday_karari(dict(ea, cagri=50), dict(ea, olcu_id="150x400", cagri=50))["karar"] == "karsilastirilamaz"

# B2: eksik alanlı (eski biçim) kayıt -> karşılaştırılamaz
is_yaz("a3", "3C-eski", IYI_ADAY, ADAY_BEGENI, olcu_id=None, ayar_ozeti=None)
r, _ = karar("3C-eski")
assert r and r[0]["karar"] == "karsilastirilamaz" and "eksik alan" in r[0]["nedenler"][0], r

# B6 (K-44): deney türleri. 3A-aday + kılavuz 1 vs 2A + kılavuz 1 -> yalnız prompt
r, _ = karar("3A-aday")
assert all(x["deney_turu"] == "yalniz_prompt" for x in r if x["karar"] != "karsilastirilamaz"), r
# 3B-aday + kılavuz 2 vs 2A + kılavuz 1 -> PAKET: kılavuz farkı karşılaştırmayı geçersiz KILMAZ, iki bileşen kayıtlı
is_yaz("a4", "3B-aday", IYI_ADAY, ADAY_BEGENI, kil=2)
r, _ = karar("3B-aday")
assert len(r) == 1 and r[0]["karar"] != "karsilastirilamaz", r
assert r[0]["deney_turu"] == "prompt_kilavuz_paketi", r[0]
assert any("prompt" in d for d in r[0]["degisen_bilesenler"]) and any("kılavuz: 1 -> 2" in d for d in r[0]["degisen_bilesenler"])
if r[0]["karar"] == "aday_onerilir":                              # paket önerisi promptun tek etkisini iddia etmez
    assert any("çıkarılamaz" in n for n in r[0]["nedenler"]), r[0]
assert "çıkarılamaz" in r[0]["not"]
# kılavuz kullanılmış ama sürümü kayıtlı değil -> eksik alan (tahminle doldurulmaz)
is_yaz("a5", "3D-eksik", IYI_ADAY, ADAY_BEGENI, kil=None)
r, _ = karar("3D-eksik")
assert r[0]["karar"] == "karsilastirilamaz" and "kilavuz_surumu" in r[0]["nedenler"][0], r

# öneri hiçbir ayarı değiştirmez
s = Settings()
assert s.prompt_surumleri == {} and not hasattr(dk, "uygula")
print("test_durma_ve_karsilastirma: TAMAM")

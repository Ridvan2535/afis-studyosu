# -*- coding: utf-8 -*-
"""
Çağrı kaydı, tekrar durdurma, insan değerlendirmesi ve prompt sürümleri — SAHTE SERVİS testi (ağ yok, ücretsiz).

Doğrulananlar:
  1. Her çağrı için rapor["denemeler"]: son prompt, prompt sürümü, model kimliği, referans kimlikleri, süre, sonuç,
     elenme nedeni; anahtar / base64 / bağlantı YOK.
  2. Elenen sahnede ham görsel ve algılama görseli AYRI kaydedilir.
  3. Aynı hata art arda `ayni_hata_siniri` kez olursa üretim durur; durdurma nedeni ve eksik sayısı raporda; 0 = kapalı.
  4. İnsan değerlendirmesi ayrı dosyada; rapor.json'u (otomatik kalite kaydını) değiştirmez.
  5. Prompt sürümü kategori bazlı seçilir; aday sürüm bölüm sınırlarına uyar; değiştirilemez ürün kuralları özeti sabit.
  6. Ret sınıflandırması (üretim / olası algılama / belirsiz) ölçümlere göre.
Çalıştır: python tests/test_deneme_kayit.py
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import deneme_kayit as dk      # noqa: E402
import orchestrator as orch    # noqa: E402
import product                 # noqa: E402
import prompt_yapisi as py_    # noqa: E402
import prompts                 # noqa: E402
from providers import Settings  # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_deneme_")
orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.REPORT_DIR = os.path.join(tmp, "raporlar")
orch.LOG_PATH = os.path.join(tmp, "kayit.log")
orch.STATS_PATH = os.path.join(tmp, "servis_karnesi.json")
KEY = "SECRET-KEY-ABCDEFGH-123456"

design = os.path.join(tmp, "tasarim.png")
can = np.zeros((2000, 750, 4), np.uint8)
can[200:600, 100:650] = (40, 40, 160, 255)
cv2.imwrite(design, can)


def run(provider, n, siniri, calls, surumler=None, ref_items=None, cat="Düğün"):
    s = Settings(scene_provider=provider, video_provider="mock", max_scene_calls=calls, photo_long_side=0,
                 auto_video=False, magnific_key=KEY, ayni_hata_siniri=siniri, prompt_surumleri=surumler or {})
    logs = []
    o = orch.Orchestrator(s, log=logs.append, progress=lambda f, t: None)
    job = o.new_job(design, cat, provider)
    res = o.generate_photos(job, n, ref_items=ref_items)
    return job, res, o.report_of(job), logs


def no_secrets(job):
    txt = open(os.path.join(job, "rapor.json"), encoding="utf-8").read()
    assert KEY not in txt, "anahtar rapora yazıldı"
    assert "base64" not in txt and not re.search(r"[A-Za-z0-9+/]{200,}", txt), "base64 benzeri veri rapora yazıldı"
    assert "http://" not in txt and "https://" not in txt, "bağlantı rapora yazıldı"


# ---------------------------------------------------------------- 1-3: hep havada biten sahne -> 3. tekrarda durur
fake_ref = cv2.imencode(".png", np.full((64, 64, 3), 128, np.uint8))[1].tobytes()
job, res, rap, logs = run("mock_air", 2, 3, 10, ref_items=[(fake_ref, "", "depo:dugun/ornek.jpg")])
print("havada:", {k: res[k] for k in ("uretilen", "eksik", "cagri")}, "durdurma:", (res.get("durdurma") or {}).get("neden"))
assert res["cagri"] == 3 and res["uretilen"] == 0 and res["eksik"] == 2, res
assert res["durdurma"] and res["durdurma"]["neden"] == "ayni_hata_tekrari" and res["durdurma"]["sayi"] == 3, res
assert any("DURDURULDU" in m for m in logs) and any("art arda 3" in m for m in logs)
d = rap["denemeler"]
assert len(d) == 3
for x in d:
    for k in ("cagri", "zaman", "servis", "model", "prompt_surumu", "prompt", "prompt_ozeti", "referanslar", "sure_sn",
              "sonuc", "tur", "neden", "sade_neden", "hata_imzasi", "siniflama"):
        assert k in x, (k, x.keys())
    assert x["model"] == "mock-mock_air" and x["prompt_surumu"] == "2A" and x["sonuc"] == "elendi"
    assert x["referanslar"] == ["depo:dugun/ornek.jpg"] and len(x["prompt"].split()) > 200
assert [x["art_arda"] for x in d] == [1, 2, 3]
for e in rap["elenenler"]:
    assert e["ham_dosya"].endswith("_ham.jpg") and os.path.exists(os.path.join(job, e["ham_dosya"]))
    assert e["algilama_dosya"].endswith("_algilama.jpg") and os.path.exists(os.path.join(job, e["algilama_dosya"]))
    ham = cv2.imread(os.path.join(job, e["ham_dosya"])); alg = cv2.imread(os.path.join(job, e["algilama_dosya"]))
    assert ham.shape == alg.shape and np.abs(ham.astype(int) - alg.astype(int)).mean() > 1.0, "ham ve algılama aynı görsel"
    assert e["sade_neden"] and "kadrajın" not in e["sade_neden"], e["sade_neden"]     # sade Türkçe, teknik ölçü değil
no_secrets(job)

# sınır 0 = kapalı: tavan kadar dener
job0, res0, rap0, _ = run("mock_air", 2, 0, 4)
assert res0["cagri"] == 4 and res0["durdurma"] is None, res0
assert dk.tekrar_ozeti(rap0["denemeler"])["en_uzun_seri"] == 4

# ---------------------------------------------------------------- kabul + insan değerlendirmesi (ayrı dosya)
jobk, resk, rapk, _ = run("mock_touch", 2, 5, 6)
assert resk["uretilen"] == 2 and resk["cagri"] == 2, resk
ok = [x for x in rapk["denemeler"] if x["sonuc"] == "kabul"]
assert len(ok) == 2 and all(x["foto"] and x["sure_sn"] >= 0 for x in ok)
before = open(os.path.join(jobk, "rapor.json"), "rb").read()
dk.insan_yaz(jobk, ok[0]["foto"], "begendim", "ışık güzel")
dk.insan_yaz(jobk, ok[1]["foto"], "uygun_degil", "")
assert open(os.path.join(jobk, "rapor.json"), "rb").read() == before, "insan değerlendirmesi otomatik kaydı değiştirdi"
h = dk.insan_oku(jobk)["fotograflar"]
assert h[ok[0]["foto"]]["karar"] == "begendim" and h[ok[0]["foto"]]["not"] == "ışık güzel"
try:
    dk.insan_yaz(jobk, ok[0]["foto"], "harika")
    raise AssertionError("geçersiz karar kabul edildi")
except ValueError:
    pass
dk.insan_yaz(jobk, ok[1]["foto"], None)
dk.insan_elenen_yaz(jobk, "1:3", "kullanilabilir", "iyi görünüyor")
assert open(os.path.join(jobk, "rapor.json"), "rb").read() == before, "elenen etiketi rapor.json'u değiştirdi"
assert dk.insan_oku(jobk)["elenenler"]["1:3"]["karar"] == "kullanilabilir"
for bad in (("1:3", "harika"), ("x", "kullanilabilir")):
    try:
        dk.insan_elenen_yaz(jobk, *bad)
        raise AssertionError(f"geçersiz etiket kabul edildi: {bad}")
    except ValueError:
        pass
assert ok[1]["foto"] not in dk.insan_oku(jobk)["fotograflar"]
no_secrets(jobk)

# ---------------------------------------------------------------- 5: kategori bazlı sürüm, aday sınırları
jobc, resc, rapc, _ = run("mock_touch", 1, 5, 2, surumler={prompts.canon("Düğün"): "3A-aday"})
x = rapc["denemeler"][0]
assert x["prompt_surumu"] == "3A-aday" and x["prompt_kelime"] <= py_.TOPLAM_LIMIT, x["prompt_kelime"]
assert x["urun_kurallari_ozeti"] == py_.URUN_KURALLARI_OZET
st = Settings(prompt_surumleri={prompts.canon("Düğün"): "3A-aday"})
others = [c for c in prompts.CATEGORIES if prompts.canon(c) != prompts.canon("Düğün")]
assert others and all(py_.secili_surum(st, c) == "2A" for c in others), "bir kategorinin sürümü diğerini etkiledi"
assert py_.secili_surum(Settings(prompt_surumleri={"Düğün": "yok-boyle"}), "Düğün") == "2A"
# değiştirilemez ürün kuralları: metin değişirse bu test bilerek başarısız olur (kullanıcı onayı gerekir)
assert py_.URUN_KURALLARI_OZET == "a3fdb2051e51277e", py_.URUN_KURALLARI_OZET
prof = product.profil_olustur("75x200")
for c in prompts.CATEGORIES:
    for i in range(prompts.pool_size(c) * 2):
        for g, r_ in ((True, True), (False, False)):
            t, info = py_.build("3A-aday", c, i, prof, ribbon={"hex": "#F2C230"}, people=True, has_refs=r_, guided=g,
                                round_no=i // prompts.pool_size(c))
            assert all(info["bolum_kelime"][k] <= py_.LIMITLER[k] for k in py_.LIMITLER), (c, i, info)
            assert "75 cm wide and 200 cm tall" in t
print("aday sürüm: tüm kategorilerde bölüm sınırları içinde")

# ---------------------------------------------------------------- 6: sınıflandırma (2026-10-13 işindeki ölçümlerle aynı biçim)
U = 0.375
uretim = {"tur": "sahne_geometri", "neden": "Kumaşın görünen boyu ürün boyundan kısa (≈157 cm < 200 cm)", "olcum": {"aspect": 0.463},
          "tam_kumas": {"asili_cm": 157.1, "birikme": False}}
algi = {"tur": "birikme_cozulemedi", "neden": "Tasarımın alt ≈48 cm'si zeminde ... kıvrımlar", "olcum": {"aspect": 0.384},
        "tam_kumas": {"asili_cm": 152.5, "gizli_cm": 47.5, "birikme": True}}
belirsiz = {"tur": "sahne_geometri", "neden": "asılı boyu (≈145 cm) ... çok kısa", "olcum": {"aspect": 0.401},
            "tam_kumas": {"asili_cm": 145.0, "birikme": True, "temas_yontemi": "kenar_yayilmasi"}}
# K-35: aynı maske ölçümü hem reddi hem teşhisi veriyor -> ±%3 kuralına takılan ama kaba sınır (±%30) içindeki ret
# "İnceleme gerekli"; kesin hata yalnız güven düşük değilken ve sapma ±%30 dışındayken
assert dk.kontrol_sonucu(uretim, U)["durum"] == "inceleme"
assert dk.kontrol_sonucu(dict(uretim, olcum={"aspect": 0.53}), U)["durum"] == "kesin_hata"
k_alg = dk.kontrol_sonucu(algi, U)
assert k_alg["durum"] == "inceleme" and k_alg["guven"] == "dusuk", k_alg
b = dk.kontrol_sonucu(belirsiz, U)
assert b["durum"] == "inceleme" and b["guven"] == "dusuk", b
# düşük güvenle kesin hata yazılmaz (sapma büyük olsa bile)
kk = dk.kontrol_sonucu(dict(uretim, olcum={"aspect": 0.53}, kararlilik={"kararsiz": True, "karar_degisti": True, "varyantlar": []}), U)
assert kk["durum"] == "inceleme" and kk["guven"] == "dusuk", kk
# insan etiketi: gösterimi etkiler, otomatik sonucu değiştirmez
oto = dk.kontrol_sonucu(dict(uretim, olcum={"aspect": 0.53}), U)
assert dk.birlesik_durum(oto, {"karar": "kullanilabilir"})["durum"] == "inceleme" and oto["durum"] == "kesin_hata"
assert dk.birlesik_durum(dk.kontrol_sonucu(uretim, U), {"karar": "gercekten_hatali"})["durum"] == "kesin_hata"
assert dk.kontrol_sonucu({"tur": "servis_hatasi", "neden": "x"}, U)["durum"] == "servis"
assert dk.hata_imzasi("birikme_cozulemedi", algi["neden"]) == "birikme_cozulemedi:birikme"
assert "tahmini 157 cm, ürün 200 cm" in dk.sade_neden(uretim, 200)
assert "[gizlendi]" in dk.temizle("hata https://x.example/a?sig=abc ve data:image/png;base64,QUJD")
assert "https" not in dk.temizle("hata https://x.example/a?sig=abc")

# ---------------------------------------------------------------- karşılaştırma yalnız öneri üretir
oz = dk.ozet(orch.JOBS_DIR)
g2a = next(g for g in oz if g["prompt_surumu"] == "2A" and g["model"] == "mock-mock_touch")
assert g2a["begendim"] == 1 and g2a["kabul"] == 2
k = dk.aday_karari(g2a, next(g for g in oz if g["prompt_surumu"] == "3A-aday"))
assert k["karar"] in ("yetersiz_veri", "karsilastirilamaz"), k
print("test_deneme_kayit: TAMAM")

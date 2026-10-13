# -*- coding: utf-8 -*-
"""
Görsel Kontrol değerlendirme düzeni — YEREL test (model çağrısı YOK, ağ yok).

  1. Paket ajana program kararını/gerekçesini SIZDIRMAZ (bilgi.json ve dosya adları); cevaplar ayrı klasörde.
  2. Ham görüntüsü olmayan eski kayıt "yaklasik" işaretlenir ve değerlendirme sınırı yazılır.
  3. Rehber ve değerlendirme örnekleri ÇAKIŞMAZ (aynı örnek hem öğretim hem başarı kanıtı olamaz).
  4. Karşılaştırma: program/insan ile çelişen, "inceleme gerekli" diyen ve kural dışı (santimetre iddiası, eksik alan)
     çıktılar kullanıcı incelemesine ayrılır; tablo doğruluk yüzdesi iddia etmez.
  4b. Programın ret gerekçesini tekrar eden ya da programın kararına atıf yapan çıktı 'bağımsız değil' işaretlenir.
  5. Ajan tanımı salt okunur ve yetkisiz (yazma/kabuk aracı yok; gizli klasör okuma yasağı yazılı).
Çalıştır: python tests/test_gorsel_kontrol.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "gorsel_kontrol"))

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import orchestrator as orch    # noqa: E402
from providers import Settings  # noqa: E402
import hazirla                 # noqa: E402
import karsilastir             # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_gk_")
orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.LOG_PATH = os.path.join(tmp, "k.log")
orch.STATS_PATH = os.path.join(tmp, "s.json")
design = os.path.join(tmp, "t.png")
can = np.zeros((2000, 750, 4), np.uint8); can[300:700, 100:650] = (40, 40, 160, 255)
cv2.imwrite(design, can)
o = orch.Orchestrator(Settings(scene_provider="mock_air", max_scene_calls=2, photo_long_side=0, supheli_olcumde_dur=False,
                               ayni_hata_siniri=0), log=lambda m: None, progress=lambda f, t: None)
job = o.new_job(design, "Düğün", "gk")
o.generate_photos(job, 1)
orch.Orchestrator(Settings(scene_provider="mock_touch", max_scene_calls=1, photo_long_side=0), log=lambda m: None,
                  progress=lambda f, t: None).generate_photos(job, 1)
rp = os.path.join(job, "rapor.json")
rap = json.load(open(rp, encoding="utf-8"))
# eski biçim kaydı taklidi: 2. elenen yalnız algılama katmanlı görseli taşısın
e = rap["elenenler"][1]
e["dosya"] = e.pop("algilama_dosya"); e.pop("ham_dosya")
json.dump(rap, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
jn = os.path.basename(job)
plan = {"urun": {"olcu": "75x200", "en_cm": 75, "boy_cm": 200},
        "rehber": [{"ad": "sentetik_dokunan", "kaynak": "sentetik", "tur": "dokunan", "oran": 0.375}],
        "degerlendirme": [{"is": jn, "grup": "farkli_is", "ornekler": ["c1", "c2", "s01"]}]}
pp = os.path.join(tmp, "plan.json"); json.dump(plan, open(pp, "w"))
cikti = os.path.join(tmp, "gk")
anahtar = hazirla.main([orch.JOBS_DIR, "--cikti", cikti, "--plan", pp])

# 1: sızıntı yok
YASAK = ("sahne_geometri", "elendi", "kabul", "ret", "neden", "kalite", "havada", "kısa", "program_karar")
for kod in anahtar:
    d = os.path.join(cikti, "paket", kod)
    assert sorted(os.listdir(d)) == ["alt.jpg", "bilgi.json", "maske.png", "sahne.jpg", "ust.jpg"], os.listdir(d)
    b = open(os.path.join(d, "bilgi.json"), encoding="utf-8").read().lower()
    assert not any(w in b.replace("kesin santimetre", "") for w in ("sahne_geometri", "elendi", "\"karar\"", "havada", "neden")), b
assert not os.path.exists(os.path.join(cikti, "paket", "anahtar.json"))
assert os.path.exists(os.path.join(cikti, "cevaplar_GIZLI", "anahtar.json"))
# 2: eski kayıt yaklaşık
tur = {v["ornek"]: v["goruntu_turu"] for v in anahtar.values()}
assert tur == {"c1": "ham", "c2": "yaklasik", "s01": "ham"}, tur
kod_c2 = next(k for k, v in anahtar.items() if v["ornek"] == "c2")
bi = json.load(open(os.path.join(cikti, "paket", kod_c2, "bilgi.json"), encoding="utf-8"))
assert "ham değildir" in bi["degerlendirme_siniri"].lower() and "kurtarılamaz" in bi["degerlendirme_siniri"]
# 3: gerçek plan dosyasında rehber/değerlendirme çakışmaz
gp = json.load(open(os.path.join(ROOT, "gorsel_kontrol", "ornek_plani.json"), encoding="utf-8"))
reh = {(r["is"], "c%d" % r["cagri"] if "cagri" in r else r["dosya"].split("/")[-1].split(".")[0]) for r in gp["rehber"] if r["kaynak"] == "is"}
deg = {(b["is"], x) for b in gp["degerlendirme"] for x in b["ornekler"]}
har = {(h["is"], x) for h in gp["haric"] for x in h["ornek"].split(",")}
assert not (reh & deg), reh & deg
assert not (deg & har), deg & har
print(f"plan: rehber {len(gp['rehber'])} (gerçek {len(reh)}), değerlendirme {len(deg)}, hariç {len(har)}")

# 4: karşılaştırma
def cikti_yaz(kod, durum, estetik="kullanilabilir", yer="evet", ek=""):
    c = {"kod": kod, "goruntu_turu": anahtar[kod]["goruntu_turu"], "kontroller": {}, "oran_gozlemi": "uyumlu",
         "estetik": {"karar": estetik, "gerekce": "x"}, "yerlestirilebilir": {"karar": yer, "gerekce": "x"},
         "durum": durum, "gerekce": "örnek" + ek, "belirsizlik": "düşük"}
    os.makedirs(os.path.join(cikti, "ajan_ciktilari"), exist_ok=True)
    json.dump(c, open(os.path.join(cikti, "ajan_ciktilari", kod + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
k = {v["ornek"]: kk for kk, v in anahtar.items()}
cikti_yaz(k["c1"], "uygun")                                  # program reddetti -> çelişki
cikti_yaz(k["c2"], "uygun_degil", "kullanilamaz", "hayir", ek=" etek 187 cm")   # santimetre iddiası
cikti_yaz(k["s01"], "uygun")                                 # program kabul -> uyuşma
satir, inc, ozet = karsilastir.main(["--klasor", cikti])
r = {x["ornek"]: x for x in satir}
assert "Program reddetti" in r["c1"]["celiski"] and r["c1"]["kullanici_incelemesi"] == "evet"
assert "santimetre" in r["c2"]["cikti_hatasi"] and r["c2"]["kullanici_incelemesi"] == "evet"
assert not r["s01"]["celiski"] and r["s01"]["kullanici_incelemesi"] == ""
md = open(os.path.join(cikti, "kullanici_incelemesi.md"), encoding="utf-8").read()
assert "doğruluk değil" in md and "%" not in md.split("Grup özeti")[1].split("\n")[0]

# 4b: programın gerekçesini tekrar eden çıktı bağımsız inceleme sayılmaz
neden_c1 = anahtar[k["c1"]]["program"]["neden"]
cikti_yaz(k["c1"], "uygun_degil", "kullanilabilir", "hayir", ek=" " + neden_c1)
satir, inc, ozet = karsilastir.main(["--klasor", cikti])
r = {x["ornek"]: x for x in satir}
assert "tekrar" in r["c1"]["bagimsizlik"] and r["c1"]["kullanici_incelemesi"] == "evet", r["c1"]
cikti_yaz(k["c1"], "uygun_degil", "kullanilabilir", "hayir", ek=" program reddetmiş olmalı")
r = {x["ornek"]: x for x in karsilastir.main(["--klasor", cikti])[0]}
assert "atıf" in r["c1"]["bagimsizlik"], r["c1"]
assert r["s01"]["bagimsizlik"] == "tamam"

# 5: ajan tanımı
ad = open(os.path.join(ROOT, ".claude", "agents", "visual-inspector.md"), encoding="utf-8").read()
tools = [t.strip() for t in ad.split("tools:")[1].split("\n")[0].split(",")]
assert set(tools) <= {"Read", "Glob"}, tools
assert "cevaplar_GIZLI" in ad and "Santimetre YAZMA" in ad and "reddetmez" in ad
print("test_gorsel_kontrol: TAMAM")

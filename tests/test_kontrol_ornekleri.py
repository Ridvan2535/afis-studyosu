# -*- coding: utf-8 -*-
"""
Kalıcı kontrol örnekleri — iş 20261013-005509 (YEREL test; servis çağrısı yok).

Örnekler: tests/kontrol_ornekleri/is_005509/kontrol.json
  * 12 elenen sahne: eski kayıtta yalnız algılama katmanlı görsel vardı; dosyalar ondan hesaplanan YAKLAŞIK görüntülerdir
    (ham değil). İnsan etiketi: 1, 6, 13 "gerçekten hatalı" (fazla geniş), diğer 9 "kullanılabilir" (görsel kabul;
    fiziksel ölçü doğrulaması DEĞİL).
  * 2 kabul edilen sahne (ham, küçültülmüş).
Doğrulananlar:
  1. Kabul edilen sahneler hâlâ kabul (Uygun).                    2. Fazla geniş 1, 6, 13 hâlâ elenir (kontrol korunur).
  3. 13 otomatik "Kesin hata" (kaba sınır ±%30 dışında).          4. Kullanılabilir etiketli 9 örnekten hiçbiri otomatik
     "Kesin hata" değil; insan etiketiyle birleşince "İnceleme gerekli".
  5. #4: alt kenardaki belirgin TEK taraflı yayılma (maske zemine taşmış) artık birikme sayılmaz; sahte "birikme
     çözülemedi" reddi kalkar. #2, #4, #5: birikme yalnız kenar yayılmasından çıkarıldığı için algılama güveni düşük.
  8. Kararlılık: kabul edilen s01 JPEG/ölçek varyantında farklı karar verir -> "kararsız" işaretlenir (kabul kalır, uyarı).
  6. Yaklaşık görüntüden yeniden ölçülen oran, eski kayıttaki orana yakın (geri çevirme sadakati; #8 bilinen istisna).
  7. Eşikler gevşetilmedi (layout ve compositor sabitleri sabit).
Çalıştır: python tests/test_kontrol_ornekleri.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2                     # noqa: E402

import compositor as cp        # noqa: E402
import deneme_kayit as dk      # noqa: E402
import layout                  # noqa: E402
import orchestrator as orch    # noqa: E402
import product                 # noqa: E402
from providers import Settings  # noqa: E402

D = os.path.join(HERE, "kontrol_ornekleri", "is_005509")
man = json.load(open(os.path.join(D, "kontrol.json"), encoding="utf-8"))
prof = product.profil_olustur("75x200")
o = orch.Orchestrator(Settings(photo_long_side=2400, strict_layout=True), log=lambda m: None, progress=lambda f, t: None)
import numpy as np             # noqa: E402
design = np.ones((2000, 750, 3), np.float32)          # örnek tasarım: tuvalin ortasında baskı, kenarlar baskısız (tam kumaş)
design[300:1700, 150:600] = 0.25

# 7: eşikler değişmedi
assert layout.ASPECT_RATIO_TOL == (0.72, 1.30) and cp.TAM_BOY_TOL == 0.03, "eşikler değişmiş"

sonuc = {}
print(f"{'örnek':<24}{'insan':<17}{'kayıt':<34}{'yeniden':<44}{'otomatik':<34}gösterim")
for it in man["ornekler"]:
    img = o._upscale(cv2.imread(os.path.join(D, it["dosya"])))
    ev = o._evaluate_scene(img, design, prof, it["dosya"])
    rec = {"tur": ev["tur"], "neden": ev["neden"], "olcum": ev["lay"]}
    rec.update(ev.get("extra") or {})
    oto = dk.kontrol_sonucu(rec, prof.oran, prof.boy_cm) if not ev["ok"] else {"durum": "uygun", "guven": None}
    insan = {"karar": it["insan"]} if it["insan"] else None
    gos = dk.birlesik_durum(oto, insan)["durum"] if not ev["ok"] else "uygun"
    tk = rec.get("tam_kumas") or (ev.get("tk_info") or {})
    sonuc[it["dosya"]] = dict(ok=ev["ok"], tur=ev["tur"], aspect=(ev["lay"] or {}).get("aspect"), oto=oto, gos=gos, tk=tk, it=it)
    k = it["kayit"]
    kr = (ev.get("tk_info") or {}).get("kararlilik") or (ev.get("extra") or {}).get("kararlilik") or {}
    sonuc[it["dosya"]]["kararlilik"] = kr
    print(f"{it['dosya'][:23]:<24}{str(it['insan']):<17}"
          f"{(str(k['tur'])[:16] + ' ' + str(k['aspect']) + ' ' + str(k.get('asili_cm'))):<34}"
          f"{(('KABUL' if ev['ok'] else str(ev['tur'])[:16]) + ' ' + str((ev['lay'] or {}).get('aspect')) + ' ' + str(tk.get('asili_cm')) + (' yayılma-şüpheli' if tk.get('yayilma_supheli') else '')):<44}"
          f"{(oto['durum'] + '/' + str(oto.get('guven'))):<34}{gos:<12}"
          f"kararlılık: {'KARARSIZ' if kr.get('kararsiz') else 'kararlı'} "
          + ", ".join(f"{v['varyant']}={'K' if v['kabul'] else 'R'}/{v['asili_cm']}" for v in kr.get("varyantlar", [])))

# 1: kabul edilenler kabul
for f in ("kabul_s01_ham.png", "kabul_s02_ham.png"):
    assert sonuc[f]["ok"], (f, sonuc[f]["tur"])
# kabul edilen s01'in kabulü kararsız (JPEG/ölçek varyantında karar değişiyor): kabul edilir ama uyarı alır (K-37)
assert sonuc["kabul_s01_ham.png"]["kararlilik"].get("kararsiz") is True
print("s01 kararlılık:", sonuc["kabul_s01_ham.png"]["kararlilik"].get("kararsiz"), "s02:", sonuc["kabul_s02_ham.png"]["kararlilik"].get("kararsiz"))
# 2-3: fazla geniş örnekler elenmeye devam eder; 13 otomatik kesin
for c in (1, 6, 13):
    s = sonuc[f"elenen_{c:02d}_yaklasik.jpg"]
    assert not s["ok"] and s["gos"] == "kesin_hata", (c, s["tur"], s["gos"])
assert sonuc["elenen_13_yaklasik.jpg"]["oto"]["durum"] == "kesin_hata"
# 4: kullanılabilir etiketlilerden hiçbiri otomatik kesin hata değil
for f, s in sonuc.items():
    if s["it"]["insan"] == "kullanilabilir":
        assert s["oto"]["durum"] != "kesin_hata", (f, s["oto"])
        assert s["ok"] or s["gos"] == "inceleme", (f, s["gos"])
# 5: tek taraflı yayılma
s4 = sonuc["elenen_04_yaklasik.jpg"]
assert s4["tk"].get("yayilma_supheli") and not s4["tk"].get("birikme"), s4["tk"]
for c in (2, 4, 5):          # birikme yalnız kenar yayılmasından ya da tek taraflı yayılma: algılama güveni düşük
    s = sonuc[f"elenen_{c:02d}_yaklasik.jpg"]
    assert s["oto"]["guven"] == "dusuk", (c, s["oto"])
assert sonuc["elenen_04_yaklasik.jpg"]["tur"] != "birikme_cozulemedi"
# 6: geri çevirme sadakati (oran ±0,02)
for f, s in sonuc.items():
    k = s["it"]["kayit"]
    if k.get("aspect") and s["aspect"] and "08" not in f:
        assert abs(s["aspect"] - k["aspect"]) <= 0.02, (f, s["aspect"], k["aspect"])
print("test_kontrol_ornekleri: TAMAM")

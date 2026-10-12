# -*- coding: utf-8 -*-
"""
"Elenen denemeler" ve insan değerlendirmesi uç noktaları — YEREL HTTP testi (sağlayıcı yok, ağ yok, ücretsiz).

  - /api/job: elenen kayıtlarına sade neden, kaynak sınıfı, ham / algılama görsel adresleri eklenir.
    Eski kayıtlarda (ham görsel saklanmamış) ham_url None ve eski_kayit True olur; eksik bilgi uydurulmaz.
  - /api/degerlendir: Beğendim / Uygun değil + not ayrı dosyaya yazılır; rapor.json değişmez; olmayan fotoğraf reddedilir.
  - /api/prompt_ozet: sürüm karşılaştırması döner; sürüm kendiliğinden değişmez.
  - /api/settings: aynı hata sınırı ve kategori prompt sürümü kaydedilir (geçici ayar dosyasında).
Gerçek bir iş klasörüyle de çalıştırılabilir:  python tests/test_elenen_arayuz.py <iş_klasörü>  (klasör KOPYALANIR).
Çalıştır: python tests/test_elenen_arayuz.py
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import providers               # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_elenen_ui_")
providers.SETTINGS_PATH = os.path.join(tmp, "ayarlar.json")          # gerçek ayar dosyasına dokunulmaz
import app                     # noqa: E402
import orchestrator as orch    # noqa: E402
import refstore                # noqa: E402

orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.REPORT_DIR = os.path.join(tmp, "raporlar")
orch.LOG_PATH = os.path.join(tmp, "kayit.log")
orch.STATS_PATH = os.path.join(tmp, "servis_karnesi.json")
refstore.ROOT = os.path.join(tmp, "referanslar")
os.makedirs(orch.JOBS_DIR)

real = sys.argv[1] if len(sys.argv) > 1 else None
if real:
    name = os.path.basename(os.path.normpath(real))
    shutil.copytree(real, os.path.join(orch.JOBS_DIR, name))
else:
    design = os.path.join(tmp, "tasarim.png")
    can = np.zeros((2000, 750, 4), np.uint8); can[200:600, 100:650] = (40, 40, 160, 255)
    cv2.imwrite(design, can)
    s = providers.Settings(scene_provider="mock_air", max_scene_calls=3, photo_long_side=0, ayni_hata_siniri=0)
    o = orch.Orchestrator(s, log=lambda m: None, progress=lambda f, t: None)
    jp = o.new_job(design, "Düğün", "ui")
    o.generate_photos(jp, 1)
    s2 = providers.Settings(scene_provider="mock_touch", max_scene_calls=1, photo_long_side=0)
    orch.Orchestrator(s2, log=lambda m: None, progress=lambda f, t: None).generate_photos(jp, 1)
    rp = os.path.join(jp, "rapor.json")
    rap = json.load(open(rp, encoding="utf-8"))
    old = dict(rap["elenenler"][0])                                     # eski biçim kaydı taklidi: yalnız işaretli görsel
    old["dosya"] = old.pop("algilama_dosya"); old.pop("ham_dosya")
    for k in ("sade_neden", "siniflama", "hata_imzasi", "uretim_no"):
        old.pop(k, None)
    rap["elenenler"][0] = old
    json.dump(rap, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
    name = os.path.basename(jp)

srv, port = app.make_server()
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = f"http://127.0.0.1:{port}"


def get(p):
    return json.loads(urllib.request.urlopen(B + p).read())


def post(p, body):
    rq = urllib.request.Request(B + p, json.dumps(body).encode(), {"Content-Type": "application/json", "X-Afis": "1"})
    try:
        return 200, json.loads(urllib.request.urlopen(rq).read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


info = get("/api/job?name=" + urllib.parse.quote(name))
el = info["elenenler"]
assert el, "elenen yok"
for e in el:
    assert e["sade_neden"] and e["siniflama"]["kaynak"] in ("uretim", "olasi_algilama", "belirsiz", "servis")
    for u in (e.get("ham_url"), e.get("algilama_url"), e.get("diger_url")):
        if u:
            assert urllib.request.urlopen(B + urllib.parse.quote(u, safe="/%")).status == 200, u
olds = [e for e in el if e["eski_kayit"]]
for e in olds:
    assert e["ham_url"] is None, "eski kayıtta ham görsel uyduruldu"
say = {}
for e in el:
    say[e["siniflama"]["kaynak"]] = say.get(e["siniflama"]["kaynak"], 0) + 1
print(f"{len(el)} elenen; eski kayıt {len(olds)}; sınıflar {say}; deneme kaydı var: {info['deneme_kaydi_var']}")
if not real:
    assert len(olds) == 1 and olds[0]["algilama_url"] and info["deneme_kaydi_var"]
    assert all(e["ham_url"] and e["algilama_url"] for e in el if not e["eski_kayit"])
else:
    for e in el:
        print(f"  #{e['cagri']:>2} {e['siniflama']['kaynak']:<15} {e['sade_neden']}")

ds = info["durma_simulasyonu"]
assert ds and ds["cagri_dizisi"] and ds["simdiki_ayar"]["dur_cagri"] >= 1, ds
print(f"durma simülasyonu ({'türetilmiş' if ds['turetildi'] else 'kayıtlı'} sıra, tavan {ds['tavan']}): şimdiki ayarla "
      f"{ds['simdiki_ayar']['dur_cagri']}. çağrı ({ds['simdiki_ayar']['neden']})")
if real:
    for r in ds["tablo"]:
        print(f"  aynı={r['ayni_hata_siniri']} sonuçsuz={r['sonucsuz_siniri']} -> {r['dur_cagri']}. çağrı {r['neden']}, "
              f"kabul {r['kabul']}, kaçan {r['kacan_kabul']}")
foto = info["fotograflar"][0]["ad"]
rp = os.path.join(orch.JOBS_DIR, name, "rapor.json")
before = open(rp, "rb").read()
c, r = post("/api/degerlendir", {"job": name, "foto": foto, "karar": "begendim", "not": "renkler doğal"})
assert c == 200 and r["insan"]["karar"] == "begendim", r
assert open(rp, "rb").read() == before, "değerlendirme rapor.json'u değiştirdi"
assert get("/api/job?name=" + urllib.parse.quote(name))["fotograflar"][0]["insan"]["not"] == "renkler doğal"
c, r = post("/api/degerlendir", {"job": name, "foto": "yok.jpg", "karar": "begendim"})
assert c == 400, (c, r)
c, r = post("/api/degerlendir", {"job": name, "foto": foto, "karar": "harika"})
assert c == 400, (c, r)

oz = get("/api/prompt_ozet")
assert oz["etkin_varsayilan"] == "2A" and all(v == "2A" for v in oz["kategori_surumleri"].values())
c, r = post("/api/settings", {"ayni_hata_siniri": 4, "prompt_surumleri": {"Düğün": "3A-aday", "Doğum günü": "uydurma"}})
assert c == 200 and r["ayarlar"]["ayni_hata_siniri"] == 4, r
oz = get("/api/prompt_ozet")
ks = oz["kategori_surumleri"]
import prompts                 # noqa: E402
assert ks[prompts.canon("Düğün")] == "3A-aday" and sum(v == "3A-aday" for v in ks.values()) == 1, ks
post("/api/settings", {"prompt_surumleri": {"Düğün": "2A"}})
assert get("/api/prompt_ozet")["kategori_surumleri"][prompts.canon("Düğün")] == "2A"
srv.shutdown()
print("BASE", B, "İŞ", name) if os.environ.get("AFIS_BEKLE") else None
print("test_elenen_arayuz: TAMAM")

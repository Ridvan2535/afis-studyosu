"""Ürün profili ve tasarım kontrolü (product.py) — yerel, ağsız. Çalıştır: python tests/test_product.py"""
import os
import sys
import tempfile

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import product as P          # noqa: E402
import prompts               # noqa: E402
import cvio                  # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_prod_")

# 1) satış ölçüleri ayrı kimliklerle; aynı oranlı ölçüler ayrı profiller
assert P.SATIS_OLCULERI == ["50x100", "50x150", "75x200", "150x300", "150x400"]
a, b = P.profil_olustur("50x100"), P.profil_olustur("150x300")
assert abs(a.oran - b.oran) < 1e-9 and a.olcu_id != b.olcu_id and (a.en_cm, b.en_cm) == (50, 150)
c, d = P.profil_olustur("75x200"), P.profil_olustur("150x400")
assert abs(c.oran - d.oran) < 1e-9 and (c.boy_cm, d.boy_cm) == (200, 400)
# prompt ölçüyü PNG oranından değil profilden alır: aynı oranlı iki ölçü farklı metin üretir
pa = prompts.build_scene_prompt("Düğün", 0, 1, 2, profile=a)
pb = prompts.build_scene_prompt("Düğün", 0, 1, 2, profile=b)
assert "exactly 50 cm wide and 100 cm long" in pa and "exactly 150 cm wide and 300 cm long" in pb, (pa[:0])
assert "20-30 cm" not in pa and "grommet" not in pa.lower() and "SQUARE photograph" in pa
assert "RIBBONS" in pa                                          # kurdele rengi seçilmese de sahne kurdeleli
# örnek ölçü varsayılanı ve satış ölçülerinden ayrı alan
assert P.UrunProfili().olcu_id == "75x200" and P.UrunProfili().satis_olculeri == P.SATIS_OLCULERI
try:
    P.profil_olustur("80x200")
    raise SystemExit("bilinmeyen ölçü kabul edildi")
except ValueError:
    pass
# görünür fiyonk ile fiziksel bağlantı ayrı; bilinmeyenler None
pr = P.profil_olustur("75x200", "#E8B4BC")
dd = pr.to_dict()
assert dd["gorunur_fiyonk"]["var"] is True and dd["gorunur_fiyonk"]["renk"] == "#E8B4BC" and dd["fiziksel_baglanti"]["kusgozu"] is None
assert dd["malzeme"]["gramaj_gsm"] is None and dd["sergileme"]["stand_paket_icerigi"] is False
assert P.UrunProfili.from_dict(dd).olcu_id == "75x200"                   # rapordan geri okunur (türetilmiş alanlar yok sayılır)
assert P.UrunProfili.from_dict(dict(dd, gelecekte_eklenen_alan=1)).en_cm == 75
# kayıtlı cm değerleri korunur; iç içe sözlükler varsayılanla birleşir; eski/gelecek rapor gevşek okunur
eski = {"olcu_id": "75x200", "en_cm": 75, "boy_cm": 200, "malzeme": {"tur": "pamuk-keten"}, "gorunur_fiyonk": None}
r = P.UrunProfili.from_dict(eski)
assert r.malzeme["gramaj_gsm"] is None and r.gorunur_fiyonk["var"] is True and r.surum == 1
assert P.UrunProfili.from_dict({"urun_turu": "tisort", "olcu_id": "M"}).urun_turu == "tisort"     # okunur, çökmez
try:
    P.UrunProfili.from_dict({"urun_turu": "tisort", "olcu_id": "M"}, strict=True)
    raise SystemExit("strict doğrulama çalışmadı")
except ValueError:
    pass
assert dd["gorunur_fiyonk"]["baglanti_gorunur_zorunlu"] is False and set(P.HATA_TURLERI) >= {"tasarim_oran_uyusmazligi", "sahne_geometri", "birikme_cozulemedi"}


# 2) tasarım kontrolü: tam oranlı şeffaf PNG uyumlu; uyuşmazlık uyarı verir, dosya değişmez
def png(w, h, alpha=True, name="t.png"):
    im = np.zeros((h, w, 4 if alpha else 3), np.uint8)
    if alpha:
        im[..., :3] = 255
        im[h // 4:h // 2, w // 4:3 * w // 4] = (30, 30, 30, 255)          # yalnız ortada baskı, gerisi şeffaf
    else:
        im[:] = 240
    p = os.path.join(tmp, name)
    cvio.imwrite(p, im)
    return p


ok_path = png(750, 2000)
k = P.tasarim_kontrol(ok_path, pr)
assert k["uyumlu"] and not k["uyarilar"] and k["hata_turu"] is None, k
assert k["seffaflik"]["var"] and 0.8 < k["seffaflik"]["tam_seffaf_oran"] < 0.9, k["seffaflik"]
assert k["px"] == [750, 2000] and abs(k["dpi"] - 750 / (75 / 2.54)) < 0.2

# kullanıcı numunesi: ~0.515 oranlı dosya 75x200'e (0.375) uymaz -> bekletilir, düzeltilmez
num = png(4116, 8000, alpha=False, name="numune.png")
before = open(num, "rb").read()
k2 = P.tasarim_kontrol(num, pr)
assert not k2["uyumlu"] and k2["hata_turu"] == "tasarim_oran_uyusmazligi" and "bekletiliyor" in k2["uyarilar"][0], k2
assert open(num, "rb").read() == before                             # dosyaya dokunulmadı
assert not k2["seffaflik"]["var"] and any("şeffaflık yok" in t for t in k2["bilgiler"])
assert k2["yon"] == "genis" and k2["karsilik_boy_cm"] == round(75 / (4116 / 8000), 1) and k2["fark_cm"] < 0
# tamamen opak RGBA: alfa kanalı var ama şeffaflık yok
op = np.full((2000, 750, 4), 255, np.uint8)
kop = P.tasarim_kontrol(op, pr)
assert kop["seffaflik"]["alfa_kanali"] and not kop["seffaflik"]["var"] and any("şeffaflık yok" in t for t in kop["bilgiler"])
# tolerans içi küçük fark raporlanır (sessiz değil)
kt = P.tasarim_kontrol(np.zeros((2000, 753, 3), np.uint8), pr)
assert kt["uyumlu"] and kt["tolerans_ici_esneme"] is not None and any("tolerans içinde" in t for t in kt["bilgiler"])
# 50x100'e de (%3 fark) uymaz: tolerans %1
assert not P.tasarim_kontrol(num, P.profil_olustur("50x100"))["uyumlu"]
# design_sample benzeri 900x2300 (0.391) 75x200'e uymaz
assert not P.tasarim_kontrol(png(900, 2300, name="s.png"), pr)["uyumlu"]
# uyan ölçüler bilgisi birden fazla olabilir ve seçim yapmaz
assert P.uyan_olculer(0.5) == ["50x100", "150x300"] and P.uyan_olculer(0.375) == ["75x200", "150x400"]

# 3) önizlemeler: oran önizlemesi kumaş oranında çerçeve çizer; tasarımı kırpmaz (tamamı görünür)
pv = P.oran_onizleme(num, pr, height=700)
assert pv.ndim == 3 and pv.shape[0] == int(700 * 0.8) + 80                # tasarım (0.515) kumaştan kısa -> kumaş boyu, turuncu alan
pv2 = P.oran_onizleme(png(600, 2000, name="dar.png"), pr, height=700)   # tasarım dar (0.30) -> kumaştan uzun -> kırmızı taşma
assert pv2.shape[0] > pv.shape[0]
g = P.gizli_bolge_onizleme(ok_path, 0.9, height=400)
assert g.shape[0] == 400 and P.gizli_bolge_onizleme(ok_path, None, height=400).shape[0] == 400
# mürekkep oranı: alt yarıda baskı yok, üst yarıda var
assert P.murekkep_orani(ok_path, 0.6) == 0.0 and P.murekkep_orani(ok_path, 0.0) > 0.1
# float (0-1) girdi de doğru ölçülür (yeniden 255'e bölünmez)
fl = np.zeros((100, 40, 3), np.float32); fl[:] = 1.0; fl[80:] = 0.1
assert abs(P.murekkep_orani(fl, 0.8) - 1.0) < 1e-6 and P.murekkep_orani(fl, 0.0) > 0.19

out_dir = os.environ.get("AFIS_ORNEK_DIR")
if out_dir:
    os.makedirs(out_dir, exist_ok=True)
    cvio.imwrite(os.path.join(out_dir, "oran_onizleme_numune_75x200.png"), pv)
    cvio.imwrite(os.path.join(out_dir, "oran_onizleme_dar_75x200.png"), pv2)
print("test_product: TAMAM")

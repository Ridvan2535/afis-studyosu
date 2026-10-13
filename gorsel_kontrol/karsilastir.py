# -*- coding: utf-8 -*-
"""Ajan çıktılarını gizli anahtarla karşılaştırır; uyuşmayanları kullanıcı incelemesine ayırır (AĞ YOK).
  python gorsel_kontrol/karsilastir.py [--klasor gorsel_kontrol]
Girdi: ajan_ciktilari/<kod>.json (visual-inspector çıktısı), cevaplar_GIZLI/anahtar.json
Çıktı: degerlendirme_tablosu.csv, kullanici_incelemesi.md
Program kararı ve insan etiketi DOĞRU CEVAP sayılmaz: tablo uyuşma/çelişki gösterir, başarı yüzdesi iddia etmez.
Ajanın hiçbir sonucu otomatik ret, yeni üretim ya da prompt değişikliği tetiklemez."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DURUMLAR = ("uygun", "inceleme_gerekli", "uygun_degil")
ZORUNLU = ("kod", "goruntu_turu", "kontroller", "oran_gozlemi", "estetik", "yerlestirilebilir", "durum", "gerekce",
           "belirsizlik")
CM_IDDIASI = re.compile(r"\d+([.,]\d+)?\s*(cm|santim)", re.I)


def dogrula(c: dict) -> list[str]:
    s = [f"eksik alan: {k}" for k in ZORUNLU if k not in c]
    if c.get("durum") not in DURUMLAR:
        s.append(f"geçersiz durum: {c.get('durum')}")
    if (c.get("estetik") or {}).get("karar") not in ("kullanilabilir", "sinirda", "kullanilamaz"):
        s.append("geçersiz estetik kararı")
    if (c.get("yerlestirilebilir") or {}).get("karar") not in ("evet", "belirsiz", "hayir"):
        s.append("geçersiz yerleştirilebilir kararı")
    if CM_IDDIASI.search(json.dumps(c, ensure_ascii=False)):
        s.append("fotoğraftan santimetre iddiası (yasak)")
    return s


PROGRAM_TERIMLERI = ("sahne_geometri", "birikme_cozulemedi", "sahne_kivrim", "kenar_yayilmasi", "kalite kapısı",
                     "program reddet", "program kabul", "elenmiş", "elendi", "ret gerekçe", "asılı kısım")


def _kelimeler(t: str) -> list[str]:
    return [w for w in re.findall(r"[a-zçğıöşü0-9]+", (t or "").lower()) if len(w) > 2]


def yanki(c: dict, k: dict) -> list[str]:
    """Bağımsızlık denetimi: ajan programın ret gerekçesini tekrar ediyorsa bu bağımsız inceleme SAYILMAZ.
    (a) program gerekçesiyle 4 kelimelik ortak dizi, (b) programın iç terimleri / karar atıfları."""
    metin = " ".join([c.get("gerekce", ""), c.get("belirsizlik", ""), (c.get("estetik") or {}).get("gerekce", ""),
                      (c.get("yerlestirilebilir") or {}).get("gerekce", "")]
                     + [(v or {}).get("not", "") for v in (c.get("kontroller") or {}).values()])
    out = []
    pw = _kelimeler(k["program"].get("neden") or "")
    aw = " ".join(_kelimeler(metin))
    ortak = {" ".join(pw[i:i + 4]) for i in range(len(pw) - 3)} if len(pw) >= 4 else set()
    if any(g in aw for g in ortak):
        out.append("Ajan programın ret gerekçesini kelimesi kelimesine tekrar ediyor.")
    if any(t in metin.lower() for t in PROGRAM_TERIMLERI):
        out.append("Ajan programın iç terimlerine/kararına atıf yapıyor (bağımsız gözlem değil).")
    return out


def celiskiler(c: dict, k: dict) -> list[str]:
    out = []
    p = k["program"]
    if p["karar"] == "kabul" and c["durum"] == "uygun_degil":
        out.append("Program kabul etti, ajan uygun değil diyor.")
    if p["karar"] == "ret" and c["durum"] == "uygun":
        out.append("Program reddetti, ajan uygun diyor.")
    if p.get("kontrol") == "kesin_hata" and c["durum"] != "uygun_degil":
        out.append("Program kesin hata diyor, ajan katılmıyor.")
    ins = (k.get("insan") or {}).get("karar")
    if ins in ("kullanilabilir", "begendim") and c["estetik"]["karar"] == "kullanilamaz":
        out.append("Kullanıcı görsel olarak kullanılabilir dedi, ajan estetik olarak kullanılamaz diyor.")
    if ins in ("gercekten_hatali", "uygun_degil") and c["durum"] == "uygun":
        out.append("Kullanıcı hatalı dedi, ajan uygun diyor.")
    if c["goruntu_turu"] != k["goruntu_turu"]:
        out.append(f"Görüntü türü yanlış bildirildi ({c['goruntu_turu']} / gerçek {k['goruntu_turu']}).")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--klasor", default=HERE)
    a = ap.parse_args(argv)
    anahtar = json.load(open(os.path.join(a.klasor, "cevaplar_GIZLI", "anahtar.json"), encoding="utf-8"))["ornekler"]
    d = os.path.join(a.klasor, "ajan_ciktilari")
    satirlar, inceleme, eksik = [], [], []
    for kod, k in sorted(anahtar.items(), key=lambda x: (x[1]["grup"], x[1]["is"], x[1]["ornek"])):
        p = os.path.join(d, kod + ".json")
        if not os.path.exists(p):
            eksik.append(kod)
            continue
        c = json.load(open(p, encoding="utf-8"))
        hatalar = dogrula(c)
        cel = [] if hatalar else celiskiler(c, k)
        bag = [] if hatalar else yanki(c, k)
        ins = (k.get("insan") or {}).get("karar") or ""
        row = {"kod": kod, "grup": k["grup"], "is": k["is"][:15], "ornek": k["ornek"], "goruntu": k["goruntu_turu"],
               "program": k["program"]["karar"] + "/" + str(k["program"].get("kontrol")), "insan": ins,
               "ajan_estetik": c.get("estetik", {}).get("karar"), "ajan_yerlestirilebilir": c.get("yerlestirilebilir", {}).get("karar"),
               "ajan_durum": c.get("durum"), "ajan_belirsizlik": c.get("belirsizlik", ""),
               "cikti_hatasi": "; ".join(hatalar), "celiski": "; ".join(cel), "bagimsizlik": "; ".join(bag) or "tamam",
               "kullanici_incelemesi": "evet" if (cel or hatalar or bag or c.get("durum") == "inceleme_gerekli") else ""}
        satirlar.append(row)
        if row["kullanici_incelemesi"]:
            inceleme.append((row, c))
    if satirlar:
        with open(os.path.join(a.klasor, "degerlendirme_tablosu.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
            w.writeheader()
            w.writerows(satirlar)
    ozet = {}
    for r in satirlar:
        g = ozet.setdefault(r["grup"], {"ornek": 0, "celiski": 0, "inceleme": 0, "bagimsiz_degil": 0})
        g["ornek"] += 1
        g["bagimsiz_degil"] += r["bagimsizlik"] != "tamam"
        g["celiski"] += bool(r["celiski"])
        g["inceleme"] += r["kullanici_incelemesi"] == "evet"
    with open(os.path.join(a.klasor, "kullanici_incelemesi.md"), "w", encoding="utf-8") as f:
        f.write("# Kullanıcı incelemesine ayrılanlar\n\nAjan ile program/insan etiketi uyuşmayanlar, ajanın "
                "'inceleme gerekli' dediği ve çıktısı kurala uymayanlar. Ajan hiçbir sahneyi reddetmez.\n\n")
        f.write("Grup özeti (doğruluk değil, uyuşma): " + json.dumps(ozet, ensure_ascii=False) + "\n\n")
        if eksik:
            f.write(f"Ajan çıktısı olmayan örnekler: {', '.join(eksik)}\n\n")
        for r, c in inceleme:
            f.write(f"## {r['kod']} ({r['is']} {r['ornek']}, {r['goruntu']})\n- program: {r['program']} · insan: {r['insan'] or '—'}\n"
                    f"- ajan: {r['ajan_durum']} · estetik {r['ajan_estetik']} · yerleştirilebilir {r['ajan_yerlestirilebilir']}\n"
                    f"- gerekçe: {c.get('gerekce', '')}\n- belirsizlik: {c.get('belirsizlik', '')}\n"
                    + (f"- **çelişki:** {r['celiski']}\n" if r["celiski"] else "")
                    + (f"- **çıktı hatası:** {r['cikti_hatasi']}\n" if r["cikti_hatasi"] else "")
                    + (f"- **bağımsızlık:** {r['bagimsizlik']}\n" if r["bagimsizlik"] != "tamam" else "") + "\n")
    print(f"{len(satirlar)} örnek karşılaştırıldı, {len(inceleme)} kullanıcı incelemesine; eksik {len(eksik)}; özet {ozet}")
    return satirlar, inceleme, ozet


if __name__ == "__main__":
    main()

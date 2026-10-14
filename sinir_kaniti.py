# -*- coding: utf-8 -*-
"""Kumaş sınırı kanıtı (TANI aracı; kabul/ret kararı VERMEZ, ayar/kayıt değiştirmez, ağ yok, ücret yok).

Bir ham sahnede programın kumaş maskesinden çıkardığı dört sınırı (üst, sol, sağ, alt/zemine temas) çizer, her sınırın
yakın görünümünü verir ve oran farkının KAYNAĞINI ayırır:
  * "geometri": makul bütün sınır seçimlerinde asılı boy ürün boyunun ±%3'ü dışında kalıyorsa fark sahnedeki kumaştan gelir;
  * "sınır seçimi": bazı makul seçimler ±%3 içine düşüyor, bazıları düşmüyorsa sonuç sınırın nereden alındığına bağlıdır
    -> kesinleşmez, "İnceleme gerekli".
Kararlı ölçüm doğru ölçüm DEMEK DEĞİLDİR: kararlılık testi aynı sınırı tekrar bulur; burada sınırın kendisi sorgulanır.

Makul sınır seçimleri (hepsi aynı maske ve sahneden; sabit koordinat yok):
  genişlik (ölçek): asılı kısmın %10-55 bandı (program) | %10-85 bandı | yalnız %55-85 bandı
  üst: maskenin üst doğrusu (program) | çubuk kılıfı/üst bant dahil (algılamanın ölçtüğü ust_bant_orani kadar yukarı)
  alt: programın temas çizgisi | maskenin alt kenarı (etek ucu)
Kullanım: python sinir_kaniti.py ham.jpg cikti.jpg [--en 75 --boy 200] [--tol 0.03]
"""
import argparse
import itertools
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import banner_detect as bd   # noqa: E402
import compositor as cp      # noqa: E402


def olc(img, en_cm=75.0, boy_cm=200.0, tol=None, det=None):
    tol = cp.TAM_BOY_TOL if tol is None else tol
    det = det or bd.detect(img, {"kind": "fabric"})
    if not det.mask.any():
        return {"hata": "maske yok", "det": det}
    g = cp.fabric_geometry(det.mask, en_cm, boy_cm, tol, scene_bgr=img)
    hgt = g["y1"] - g["y0"]
    w = g["R_ham"] - g["L_ham"]
    bant = lambda a, b: float(np.median(w[int(a * hgt):max(int(b * hgt), int(a * hgt) + 3)]))
    genislik = {"%10-55 (program)": bant(0.10, 0.55), "%10-85": bant(0.10, 0.85), "%55-85": bant(0.55, 0.85)}
    ust_prog = float(np.median(g["top_x"][g["mask"].any(0)]))
    ust_bant = float(det.metrics.get("ust_bant_orani") or 0.0) * hgt
    ustler = {"maske üstü (program)": ust_prog, "üst bant dahil": ust_prog - ust_bant}
    m = g["mask"]
    cl, cr = float(np.median(g["L_ham"][int(.1 * hgt):int(.55 * hgt)])), float(np.median(g["R_ham"][int(.1 * hgt):int(.55 * hgt)]))
    cols = np.arange(int(cl + 0.08 * g["W0"]), int(cr - 0.08 * g["W0"]))
    cols = cols[m[:, cols].any(0)]
    alt_maske = float(np.median(m.shape[0] - np.argmax(m[::-1, cols], 0)))
    altlar = {"temas çizgisi (program)": float(g["temas_y"]), "etek ucu (maske altı)": alt_maske}
    secimler = []
    for (gk, gv), (uk, uv), (ak, av) in itertools.product(genislik.items(), ustler.items(), altlar.items()):
        asili = (av - uv) / (gv / en_cm)
        secimler.append({"genislik": gk, "ust": uk, "alt": ak, "asili_cm": round(asili, 1),
                         "oran": round(gv / max(av - uv, 1), 4), "icinde": abs(asili / boy_cm - 1) <= tol})
    icinde = [s["icinde"] for s in secimler]
    # kaynak: insan için metin (değişmedi); kaynak_kodu: makine için sabit kod (G5b) -> "uygun" | "geometri" | "sinir"
    if all(icinde):
        kaynak, kaynak_kodu = "uygun (bütün makul sınırlarda ±%{:.0f} içinde)".format(tol * 100), "uygun"
    elif not any(icinde):
        kaynak, kaynak_kodu = "geometri (bütün makul sınırlarda ±%{:.0f} dışında)".format(tol * 100), "geometri"
    else:
        kaynak, kaynak_kodu = "sınır seçimi (bazı makul sınırlarda içinde, bazılarında dışında) -> İnceleme gerekli", "sinir"
    a = [s["asili_cm"] for s in secimler]
    return {"det": det, "g": g, "genislik": genislik, "ustler": ustler, "altlar": altlar, "secimler": secimler,
            "asili_aralik": [min(a), max(a)], "kaynak": kaynak, "kaynak_kodu": kaynak_kodu,
            "program_asili_cm": round(g["asili_cm"], 1),
            "birikme": g["birikme"], "temas_yontemi": g["temas_yontemi"], "hgt": hgt}


def ciz(img, r, yol, baslik=""):
    g, H, W = r["g"], img.shape[0], img.shape[1]
    v = img.copy()
    cn, _ = cv2.findContours((g["mask"] > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(v, cn, -1, (0, 255, 0), 3)
    rows = g["rows"]
    t = max(2, W // 600)
    for xx, col in ((g["L_ham"], (0, 220, 255)), (g["R_ham"], (0, 220, 255))):
        pts = np.stack([xx, rows], 1).astype(np.int32)
        cv2.polylines(v, [pts], False, col, t)
    x0, x1 = int(r["genislik"] and min(g["L_ham"])) - 40, int(max(g["R_ham"])) + 40
    renk = {"maske üstü (program)": (255, 80, 0), "üst bant dahil": (255, 200, 120),
            "temas çizgisi (program)": (0, 0, 255), "etek ucu (maske altı)": (255, 0, 255)}
    for k, y in list(r["ustler"].items()) + list(r["altlar"].items()):
        cv2.line(v, (max(0, x0), int(y)), (min(W, x1), int(y)), renk[k], t)
    # yakın görünümler: üst, alt (zemin), sol orta, sağ orta
    hg, y0 = r["hgt"], g["y0"]
    cx = int((np.median(g["L_ham"]) + np.median(g["R_ham"])) / 2)
    yt, yb = int(min(r["ustler"].values())), int(max(r["altlar"].values()))
    ym = int(y0 + 0.65 * hg)
    def kes(xa, ya, xb, yb_):
        xa, ya, xb, yb_ = max(0, xa), max(0, ya), min(W, xb), min(H, yb_)
        return cv2.resize(v[ya:yb_, xa:xb], (400, 400))
    s = int(0.12 * hg)
    parcalar = [kes(cx - s * 2, yt - s // 2, cx + s * 2, yt + s * 2), kes(cx - s * 2, yb - s * 2, cx + s * 2, yb + s // 2),
                kes(int(np.median(g["L_ham"])) - s, ym - s, int(np.median(g["L_ham"])) + s, ym + s),
                kes(int(np.median(g["R_ham"])) - s, ym - s, int(np.median(g["R_ham"])) + s, ym + s)]
    adlar = ["ust sinir", "alt / zemin", "sol kenar (%65)", "sag kenar (%65)"]
    for p, a in zip(parcalar, adlar):
        cv2.rectangle(p, (0, 0), (399, 26), (0, 0, 0), -1)
        cv2.putText(p, a, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    ana = cv2.resize(v, (800, 800))
    sag = np.vstack([np.hstack(parcalar[:2]), np.hstack(parcalar[2:])])
    tuval = np.hstack([ana, sag])
    alt = np.full((150, tuval.shape[1], 3), 255, np.uint8)
    satirlar = [baslik,
                f"program: asili {r['program_asili_cm']} cm, temas: {r['temas_yontemi']}, birikme: {r['birikme']}",
                f"makul sinir secimlerinde asili boy: {r['asili_aralik'][0]}-{r['asili_aralik'][1]} cm (urun 200, kabul 194-206)",
                "kaynak: " + r["kaynak"].replace("ı", "i").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("İ", "I"),
                "yesil: maske | sari: sol/sag kenar | mavi: ust (program) | acik mavi: ust bant dahil | kirmizi: temas (program) | mor: etek ucu"]
    for i, s_ in enumerate(satirlar):
        cv2.putText(alt, s_, (10, 26 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(yol, np.vstack([tuval, alt]), [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ham")
    ap.add_argument("cikti")
    ap.add_argument("--en", type=float, default=75)
    ap.add_argument("--boy", type=float, default=200)
    ap.add_argument("--baslik", default="")
    a = ap.parse_args()
    im = cv2.imread(a.ham)
    r = olc(im, a.en, a.boy)
    ciz(im, r, a.cikti, a.baslik)
    print(json.dumps({k: r[k] for k in ("program_asili_cm", "asili_aralik", "kaynak", "genislik", "ustler", "altlar",
                                        "temas_yontemi", "birikme")}, ensure_ascii=False, indent=1))
    for s in r["secimler"]:
        print(s)


# ----------------------------------------------------------------------------
# Tasarımlı TANI önizlemesi (kabul edilmemiş sahne). Ürün çıktısıyla karışmasın diye: kırmızı çerçeve, üstte ve altta
# "TANI ÖNİZLEMESİ — ÜRÜN ÇIKTISI DEĞİL" şeridi, çapraz filigran ve sağda kalan yerleşim sorunlarının sade listesi.
# Dosya adı her zaman "_TANI_" içerir ve yalnız onizleme/ klasörüne yazılır (foto/ klasörüne asla).
_FONTLAR = ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "arial.ttf", "C:/Windows/Fonts/arial.ttf",
            "segoeui.ttf")


def _font(boy):
    from PIL import ImageFont
    for f in _FONTLAR:
        try:
            return ImageFont.truetype(f, boy)
        except Exception:
            continue
    return ImageFont.load_default()


def kalan_sorunlar(rec: dict, boy_cm: float = 200.0) -> list:
    """Kayıttan, yerleştirmeyi engelleyen sorunların SADE listesi (görsel güzel görünse bile neden kabul edilmediği)."""
    out = []
    tk = rec.get("tam_kumas") or {}
    a = tk.get("asili_cm")
    if a:
        fark = a / boy_cm - 1
        out.append(("Programın ölçümüne göre (kesin değil, aşağıya bakın) " if (rec.get("sinir_araligi") or {}).get("kaynak") in ("sınır", "sinir") else "")
                   + f"Kumaşın görünen asılı boyu ≈{a:.0f} cm; ürün {boy_cm:g} cm (kabul ±%3: {boy_cm * .97:.0f}–{boy_cm * 1.03:.0f} cm). "
                   f"Fark %{fark * 100:+.0f}.")
        if fark < -0.03:
            out.append("Tasarım fiziksel ölçekle yerleşir: alttaki ≈%.0f cm'lik kısım zemine/görünmeyen bölgeye düşer; "
                       "o kısımdaki yazı/desen görünmez ya da kumaş havada bitiyor görünür." % (boy_cm - a))
        elif fark > 0.03:
            out.append("Tasarımı kumaşa sığdırmak için dikeyde %%%.0f sıkıştırmak gerekir; tasarım oranı bozulur (izin yok)." % (fark * 100))
    sa = rec.get("sinir_araligi") or {}
    if sa:
        if sa.get("kaynak") == "geometri":
            out.append(f"Bütün makul sınır seçimlerinde {sa['asili_min']:.0f}–{sa['asili_max']:.0f} cm: fark sahnedeki kumaştan geliyor.")
        elif sa.get("kaynak") in ("sınır", "sinir"):        # eski kayıt: metnin ilk kelimesi; yeni: kaynak_kodu
            out.append(f"Sınır seçimine göre {sa['asili_min']:.0f}–{sa['asili_max']:.0f} cm: sonuç sınırın nereden alındığına bağlı; "
                       "gözle inceleme gerekli.")
    if tk.get("temas_belirsiz"):
        tk_k = rec.get("temas_karsilastirma") or {}
        out.insert(0, "Zemine temas belirsiz: kumaşın yavaş genişlemesi yerde birikme kanıtı sayılmadı. "
                   + (f"Genişlemenin başladığı satır temas alınırsa asılı ≈{tk_k['yayilma']['asili_cm']:.0f} cm ve tasarımın "
                      f"%{(1 - (1.0 if tk_k['yayilma']['gorunen_murekkep'] is None else tk_k['yayilma']['gorunen_murekkep'])) * 100:.0f}'i gizlenir; etek ucu alınırsa ≈"
                      f"{tk_k['etek_ucu']['asili_cm']:.0f} cm. " if tk_k else "")
                   + "Otomatik gizleme yapılmadı; manuel sınırla düzeltilebilir.")
    if tk.get("birikme") and tk.get("temas_yontemi") == "kenar_yayilmasi":
        out.append(f"Zemine temas çizgisi yalnız kenar genişlemesinden kestirildi (temas y≈{tk.get('temas_y', 0):.0f} px); güvenilir değil.")
    for u in tk.get("uyarilar") or []:
        out.append(u)
    alg = rec.get("algilama") or {}
    if alg.get("yan_kirpilan_oran"):
        out.append("Algılama maskesi duvara taşmıştı; kumaş kenarları gövdenin düz kenarlarından kestirildi.")
    if not out:
        out.append(str(rec.get("neden") or "Ret nedeni kayıtta yok."))
    return out


def tani_onizlemesi(out_bgr, sorunlar: list, baslik: str = "") -> np.ndarray:
    from PIL import Image, ImageDraw
    H, W = out_bgr.shape[:2]
    f = 900 / max(H, W)
    sah = cv2.resize(out_bgr, (int(W * f), int(H * f)), interpolation=cv2.INTER_AREA)
    sh, sw = sah.shape[:2]
    # çapraz filigran
    wm = np.zeros_like(sah)
    cv2.putText(wm, "TANI - URUN CIKTISI DEGIL", (int(sw * .02), int(sh * .58)), cv2.FONT_HERSHEY_DUPLEX, sw / 520, (255, 255, 255), 3, cv2.LINE_AA)
    M = cv2.getRotationMatrix2D((sw / 2, sh / 2), 35, 1.0)
    wm = cv2.warpAffine(wm, M, (sw, sh))
    sah = np.where(wm > 0, (0.55 * sah + 0.45 * np.array([40, 40, 220])).astype(np.uint8), sah)
    cv2.rectangle(sah, (0, 0), (sw - 1, sh - 1), (0, 0, 220), 10)
    panel_w = 520
    tuval = Image.new("RGB", (sw + panel_w, sh + 120), (255, 255, 255))
    tuval.paste(Image.fromarray(cv2.cvtColor(sah, cv2.COLOR_BGR2RGB)), (0, 60))
    d = ImageDraw.Draw(tuval)
    for y in (0, sh + 60):
        d.rectangle([0, y, sw + panel_w, y + 59], fill=(200, 30, 30))
        d.text((16, y + 14), "TANI ÖNİZLEMESİ — KABUL EDİLMEDİ — ÜRÜN ÇIKTISI DEĞİL (satışa/ilana konmaz)", fill=(255, 255, 255), font=_font(26))
    x, y = sw + 18, 76
    d.text((x, y), baslik or "Kalan yerleşim sorunları", fill=(0, 0, 0), font=_font(24))
    y += 40
    fn = _font(19)
    for s in sorunlar:
        satir, kel = "", s.split()
        parca = []
        for k in kel:
            if d.textlength(satir + " " + k, font=fn) > panel_w - 40:
                parca.append(satir)
                satir = k
            else:
                satir = (satir + " " + k).strip()
        parca.append(satir)
        d.text((x, y), "•", fill=(200, 30, 30), font=fn)
        for p in parca:
            d.text((x + 16, y), p, fill=(20, 20, 20), font=fn)
            y += 25
        y += 10
    return cv2.cvtColor(np.array(tuval), cv2.COLOR_RGB2BGR)


def tani_karsilastirma(kars: list, sorunlar: list, boy_cm: float = 200.0) -> np.ndarray:
    """Temas belirsizken iki temas seçimini yan yana gösterir (TANI; ürün çıktısı değil). Her panelde üst kenar (mavi),
    temas çizgisi (kırmızı), asılı boy, zeminde kalan kısım ve tasarımın baskılı kısmının görünen oranı yazılır."""
    from PIL import Image, ImageDraw
    paneller = []
    for k in kars:
        o, inf = k["out"].copy(), k["info"]
        H, W = o.shape[:2]
        t = max(3, W // 400)
        x0, x1 = inf["bbox"][0], inf["bbox"][2]
        a, b = inf["temas_cizgisi"]
        cv2.line(o, (x0 - 60, int(a * (x0 - 60) + b)), (x1 + 60, int(a * (x1 + 60) + b)), (0, 0, 255), t)
        ua, ub = inf["ust_kenar"]
        cv2.line(o, (x0 - 60, int(ua * (x0 - 60) + ub)), (x1 + 60, int(ua * (x1 + 60) + ub)), (255, 120, 0), t)
        f = 640 / max(H, W)
        o = cv2.resize(o, (int(W * f), int(H * f)), interpolation=cv2.INTER_AREA)
        cv2.rectangle(o, (0, 0), (o.shape[1] - 1, o.shape[0] - 1), (0, 0, 220), 6)
        paneller.append((k["etiket"], o, inf))
    pw, ph = paneller[0][1].shape[1], paneller[0][1].shape[0]
    tuval = Image.new("RGB", (pw * len(paneller) + 20 * (len(paneller) - 1), 60 + 70 + ph + 150 + 60 + 22 * 4 * len(sorunlar)), (255, 255, 255))
    d = ImageDraw.Draw(tuval)
    d.rectangle([0, 0, tuval.width, 59], fill=(200, 30, 30))
    d.text((16, 14), "TANI — TEMAS ÇİZGİSİ KARŞILAŞTIRMASI — KABUL EDİLMEDİ — ÜRÜN ÇIKTISI DEĞİL", fill=(255, 255, 255), font=_font(24))
    for i, (et, o, inf) in enumerate(paneller):
        x = i * (pw + 20)
        d.text((x + 6, 70), et, fill=(0, 0, 0), font=_font(19))
        tuval.paste(Image.fromarray(cv2.cvtColor(o, cv2.COLOR_BGR2RGB)), (x, 130))
        gm = inf.get("gorunen_murekkep")
        satir = [f"Asılı boy ≈{inf['asili_cm']:.0f} cm (ürün {boy_cm:g}; kabul {boy_cm * .97:.0f}–{boy_cm * 1.03:.0f})",
                 f"Zeminde/görünmeyen kısım ≈{inf['gizli_cm']:.0f} cm",
                 f"Tasarımın baskılı kısmının görünen oranı: %{(gm if gm is not None else 1) * 100:.1f}",
                 "Tasarımın TAMAMI görünüyor" if (gm or 0) >= 0.999 else "Tasarımın alt kısmı (yazı dahil) GÖRÜNMÜYOR"]
        for j, sa in enumerate(satir):
            d.text((x + 6, 130 + ph + 10 + j * 30), sa, fill=(20, 20, 20) if j < 3 else ((0, 120, 0) if (gm or 0) >= 0.999 else (200, 30, 30)), font=_font(19))
    y = 130 + ph + 140
    d.text((10, y), "Mavi: üst kenar   Kırmızı: temas çizgisi (altı zemine düşer, basılmaz). Tasarım kırpılmadı, esnetilmedi, yazı taşınmadı.",
           fill=(60, 60, 60), font=_font(17))
    y += 34
    fn = _font(16)
    for s in sorunlar:
        satir = "• "
        for k in s.split():
            if d.textlength(satir + " " + k, font=fn) > tuval.width - 30:
                d.text((10, y), satir, fill=(20, 20, 20), font=fn)
                y += 22
                satir = "   " + k
            else:
                satir = (satir + " " + k) if satir.strip() else satir + k
        d.text((10, y), satir, fill=(20, 20, 20), font=fn)
        y += 26
    return cv2.cvtColor(np.array(tuval.crop((0, 0, tuval.width, min(tuval.height, y + 20)))), cv2.COLOR_RGB2BGR)

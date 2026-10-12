# -*- coding: utf-8 -*-
"""
Deneme kayıtları, ret sınıflandırması, tekrar imzası, insan değerlendirmesi ve sürüm karşılaştırması (2026-10-13).

Ağ yok, sağlayıcı yok. Anahtar, gizli bağlantı ve base64 KAYDEDİLMEZ (yalnız prompt metni, kimlikler ve ölçümler).

Ret kaynağı sınıfları (öğrenme verisinden ayırmak için):
  "uretim"          : ölçümler sahnenin ürüne gerçekten uymadığını tutarlı biçimde gösteriyor (ör. afiş oranı ürünle %8+ farklı)
  "olasi_algilama"  : ölçümler kendi içinde çelişiyor (ör. oran ürünle uyumlu ama birikme/temas ölçümü boyu kısa gösteriyor)
  "belirsiz"        : ikisi de güvenle söylenemiyor
  "servis"          : servis hatası (prompt öğrenmesine girmez)
Fotoğraftan hesaplanan santimetreler TAHMİNİDİR; birikme/temas yöntemine göre güvenilirliği işaretlenir.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

URETIM_ORAN_SAPMA = 0.08        # VARSAYIM: ölçülen afiş oranı ürün oranından bu kadar farklıysa üretim hatası sayılır
ALGILAMA_ORAN_UYUM = 0.05       # VARSAYIM: oran bu kadar yakınken "kısa/birikme" denmesi çelişkidir -> olası algılama
INSAN_DOSYASI = "insan_degerlendirme.json"     # otomatik kalite kontrolünden AYRI


_URL = re.compile(r"https?://\S+|data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+|[A-Za-z0-9+/]{120,}={0,2}")


def temizle(text: str | None, limit: int = 600) -> str:
    """Kayda yazılacak serbest metinden bağlantıları, data/base64 bloklarını ve aşırı uzunluğu temizler."""
    return _URL.sub("[gizlendi]", str(text or ""))[:limit]


def hata_imzasi(tur: str | None, neden: str | None) -> str:
    """Art arda tekrar sayımı için kaba hata imzası (tür + alt neden)."""
    n = (neden or "").lower()
    sabit = {"birikme_cozulemedi": "birikme", "sahne_kivrim": "kivrim", "servis_hatasi": "servis"}
    if tur in sabit:
        return f"{tur}:{sabit[tur]}"
    alt = "diger"
    for key, words in (("kisa", ("kısa", "havada")), ("uzun", ("uzun",)), ("genis", ("geniş", "yatay")),
                       ("dar", ("dar ",)), ("bos_degil", ("boş değil", "boş görünmüyor", "yazı/desen")),
                       ("bulunamadi", ("bulunamadı", "çok küçük", "kadraja taşıyor")), ("kivrim", ("düz değil", "kıvrım")),
                       ("birikme", ("birik",))):
        if any(w in n for w in words):
            alt = key
            break
    return f"{tur or 'bilinmiyor'}:{alt}"


def siniflandir(rec: dict, urun_orani: float) -> dict:
    """Ret kaydını kaynağına göre sınıflar. Yalnız kayıttaki ölçümleri kullanır; eksik ölçüm varsa 'belirsiz'."""
    tur = rec.get("tur")
    if tur == "servis_hatasi":
        return {"kaynak": "servis", "aciklama": "Servis hatası; görsel değerlendirilmedi."}
    olcum = rec.get("olcum") or {}
    tk = rec.get("tam_kumas") or {}
    asp = olcum.get("aspect")
    if not asp:
        return {"kaynak": "belirsiz", "aciklama": "Afiş ölçülemedi ya da algılanamadı; üretim mi algılama mı ayırt edilemiyor."}
    sapma = asp / urun_orani - 1.0
    cm_guvenilir = not (tk.get("birikme") and tk.get("temas_yontemi") == "kenar_yayilmasi")
    if tur in ("sahne_geometri", "birikme_cozulemedi") and abs(sapma) <= ALGILAMA_ORAN_UYUM and tk.get("birikme"):
        return {"kaynak": "olasi_algilama", "oran_sapmasi": round(sapma, 3), "cm_guvenilir": False,
                "aciklama": f"Ölçülen afiş oranı ürünle uyumlu (%{sapma * 100:+.0f}) ama zemin birikmesi algılanıp boy kısa "
                            f"hesaplandı; algılama maskesi zemine taşmış olabilir."}
    if abs(sapma) >= URETIM_ORAN_SAPMA:
        yon = "geniş/kısa" if sapma > 0 else "dar/uzun"
        return {"kaynak": "uretim", "oran_sapmasi": round(sapma, 3), "cm_guvenilir": cm_guvenilir,
                "aciklama": f"Afiş ürüne göre {yon} çizilmiş: ölçülen en/boy {asp:.3f}, ürün {urun_orani:.3f} "
                            f"(%{sapma * 100:+.0f})." + ("" if cm_guvenilir else " Santimetre tahmini güvenilir değil (birikme ölçümü).")}
    return {"kaynak": "belirsiz", "oran_sapmasi": round(sapma, 3), "cm_guvenilir": cm_guvenilir,
            "aciklama": f"Oran farkı küçük (%{sapma * 100:+.0f}); ret ölçüm payına yakın, kaynak kesin değil."
                        + ("" if cm_guvenilir else " Santimetre tahmini güvenilir değil (birikme ölçümü).")}


def sade_neden(rec: dict, boy_cm: float | None = None) -> str:
    """Arayüz için sade Türkçe tek cümle. Santimetreler 'tahmini' olarak gösterilir."""
    tur, n = rec.get("tur"), (rec.get("neden") or "")
    tk = rec.get("tam_kumas") or {}
    urun = f", ürün {boy_cm:.0f} cm" if boy_cm else ""
    if tur == "servis_hatasi":
        return "Servis hata verdi; görsel alınamadı."
    if tur == "sahne_geometri" and tk.get("asili_cm"):
        a = tk["asili_cm"]
        if "uzun" in n:
            return f"Kumaş ürün boyundan uzun çizilmiş (tahmini {a:.0f} cm{urun})."
        return f"Kumaş ürün boyundan kısa görünüyor (tahmini {a:.0f} cm{urun})."
    if tur == "sahne_geometri" and ("geniş" in n or "yatay" in n):
        return "Afiş ürüne göre fazla geniş çizilmiş."
    if "yere kadar uzanmıyor" in n or "havada" in n:
        return "Afişin alt kenarı zemine ulaşmıyor; kumaş havada bitiyor."
    if "çok dar" in n:
        return "Afiş ürüne göre fazla dar/uzun çizilmiş."
    if tur == "birikme_cozulemedi":
        return f"Kumaşın alt kısmı yerde birikmiş görünüyor (tahmini {tk.get('gizli_cm', 0):.0f} cm) ve tasarımın o bölgesinde yazı var."
    if tur == "sahne_kivrim":
        return "Kumaş fazla kıvrımlı; tasarım bozulmadan sığmıyor."
    if "boş" in n:
        return "Afişin üzerinde yazı ya da desen var (boş değil)."
    if "bulunamadı" in n or "küçük" in n or "taşıyor" in n:
        return "Afiş sahnede bulunamadı ya da kadraja taşıyor."
    return re.sub(r"\s+", " ", n)[:160]


def tekrar_ozeti(denemeler: list[dict]) -> dict:
    """Art arda aynı hata imzası: en uzun seri ve son seri."""
    best, cur, cur_sig, best_sig = 0, 0, None, None
    for d in denemeler:
        sig = d.get("hata_imzasi") if d.get("sonuc") == "elendi" else None
        if sig and sig == cur_sig:
            cur += 1
        else:
            cur, cur_sig = (1, sig) if sig else (0, None)
        if cur > best:
            best, best_sig = cur, cur_sig
    return {"en_uzun_seri": best, "imza": best_sig, "son_seri": cur, "son_imza": cur_sig}


# ---------------------------------------------------------------------------- insan değerlendirmesi (ayrı dosya)
def insan_oku(job: str) -> dict:
    try:
        with open(os.path.join(job, INSAN_DOSYASI), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"fotograflar": {}}


def insan_yaz(job: str, foto: str, karar: str | None, not_: str = "") -> dict:
    if karar not in ("begendim", "uygun_degil", None):
        raise ValueError("karar 'begendim', 'uygun_degil' ya da boş olmalı")
    d = insan_oku(job)
    fs = d.setdefault("fotograflar", {})
    if karar is None:
        fs.pop(foto, None)
    else:
        fs[foto] = {"karar": karar, "not": (not_ or "").strip()[:300], "zaman": datetime.now().isoformat(timespec="seconds")}
    tmp = os.path.join(job, INSAN_DOSYASI + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(job, INSAN_DOSYASI))
    return d


# ---------------------------------------------------------------------------- sürüm karşılaştırması (yalnız rapor)
ADAY_KURALLARI = {
    "en_az_cagri": 12,          # tek başarılı görsel yetmez: aday için en az bu kadar çağrı
    "en_az_kabul": 3,
    "en_az_insan_degerlendirmesi": 3,
    "kabul_orani_farki": 0.10,  # aday kabul oranı etkinden en az bu kadar yüksek olmalı (algılama şüphelileri hariç)
    "begeni_orani_dusmesin": True,
    "sure_artisi_en_fazla": 0.25,
}


def ozet(jobs_dir: str) -> list[dict]:
    """Tüm işlerin deneme kayıtlarından (kategori, prompt sürümü, model) grupları. Eski işlerde kayıt yoksa sayılmaz
    (sonradan tahminle doldurulmaz). Olası algılama hatası olan retler kabul oranı hesabından ÇIKARILIR."""
    grup: dict = {}
    if not os.path.isdir(jobs_dir):
        return []
    for j in sorted(os.listdir(jobs_dir)):
        jp = os.path.join(jobs_dir, j)
        try:
            with open(os.path.join(jp, "rapor.json"), encoding="utf-8") as f:
                rap = json.load(f)
        except Exception:
            continue
        insan = insan_oku(jp).get("fotograflar", {})
        for d in rap.get("denemeler", []):
            key = (rap.get("kategori"), d.get("prompt_surumu"), d.get("model") or d.get("servis"))
            g = grup.setdefault(key, {"kategori": key[0], "prompt_surumu": key[1], "model": key[2], "cagri": 0, "kabul": 0,
                                      "elendi_uretim": 0, "elendi_algilama": 0, "elendi_belirsiz": 0, "servis_hatasi": 0,
                                      "sure_toplam": 0.0, "begendim": 0, "uygun_degil": 0, "isler": set()})
            g["cagri"] += 1
            g["isler"].add(j)
            g["sure_toplam"] += float(d.get("sure_sn") or 0)
            if d.get("sonuc") == "kabul":
                g["kabul"] += 1
                h = insan.get(d.get("foto") or "", {}).get("karar")
                if h:
                    g[h] += 1
            elif d.get("sonuc") == "servis_hatasi":
                g["servis_hatasi"] += 1
            else:
                k = (d.get("siniflama") or {}).get("kaynak", "belirsiz")
                g["elendi_" + ("algilama" if k == "olasi_algilama" else ("uretim" if k == "uretim" else "belirsiz"))] += 1
    out = []
    for g in grup.values():
        etkili = g["cagri"] - g["elendi_algilama"] - g["servis_hatasi"]
        g["kabul_orani"] = round(g["kabul"] / etkili, 3) if etkili > 0 else None
        g["ort_sure_sn"] = round(g["sure_toplam"] / g["cagri"], 1) if g["cagri"] else None
        hd = g["begendim"] + g["uygun_degil"]
        g["begeni_orani"] = round(g["begendim"] / hd, 3) if hd else None
        g["is_sayisi"] = len(g.pop("isler"))
        g.pop("sure_toplam")
        out.append(g)
    return sorted(out, key=lambda x: (str(x["kategori"]), str(x["model"]), str(x["prompt_surumu"])))


def aday_karari(etkin: dict | None, aday: dict | None, kurallar: dict = ADAY_KURALLARI) -> dict:
    """Yalnız ÖNERİ üretir; sürümü değiştirmez. Aynı kategori ve aynı modelin iki grubu karşılaştırılmalıdır."""
    if not etkin or not aday:
        return {"karar": "yetersiz_veri", "nedenler": ["Karşılaştırılacak iki grup yok."]}
    if etkin["kategori"] != aday["kategori"] or etkin["model"] != aday["model"]:
        return {"karar": "karsilastirilamaz", "nedenler": ["Kategori ya da model farklı; karşılaştırma geçersiz."]}
    ned = []
    if aday["cagri"] < kurallar["en_az_cagri"]:
        ned.append(f"Aday için en az {kurallar['en_az_cagri']} çağrı gerekir ({aday['cagri']}).")
    if aday["kabul"] < kurallar["en_az_kabul"]:
        ned.append(f"Aday için en az {kurallar['en_az_kabul']} kabul gerekir ({aday['kabul']}).")
    if (aday["begendim"] + aday["uygun_degil"]) < kurallar["en_az_insan_degerlendirmesi"]:
        ned.append("Yeterli insan değerlendirmesi yok.")
    if ned:
        return {"karar": "yetersiz_veri", "nedenler": ned}
    ok = []
    if (aday["kabul_orani"] or 0) - (etkin["kabul_orani"] or 0) < kurallar["kabul_orani_farki"]:
        ok.append("Kabul oranı yeterince yükselmedi.")
    if kurallar["begeni_orani_dusmesin"] and (aday["begeni_orani"] or 0) < (etkin["begeni_orani"] or 0):
        ok.append("İnsan beğenisi düştü.")
    if etkin.get("ort_sure_sn") and aday.get("ort_sure_sn") and \
            aday["ort_sure_sn"] > etkin["ort_sure_sn"] * (1 + kurallar["sure_artisi_en_fazla"]):
        ok.append("Çağrı süresi belirgin arttı.")
    if ok:
        return {"karar": "etkin_kalsin", "nedenler": ok}
    return {"karar": "aday_onerilir", "nedenler": ["Ölçütler sağlandı; geçiş kullanıcı onayıyla yapılır, önceki sürüme dönülebilir."]}

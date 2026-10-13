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


KESIN_ORAN_SAPMA = 0.30        # layout.ASPECT_RATIO_TOL ile aynı: afiş biçimi bu kadar farklıysa "çok geniş/dar" (bağımsız kaba sınır)
YAN_TASMA_DUSUK_GUVEN = 0.04   # VARSAYIM: kenar satırlarının %4'ünden fazlası doğrudan taşıyorsa maske güvenilir değil
BOY_TOL = 0.03                 # compositor TAM_BOY_TOL ile aynı (±%3)
INSAN_ELENEN_KARARLARI = ("kullanilabilir", "gercekten_hatali")


def kontrol_sonucu(rec: dict, urun_orani: float, boy_cm: float | None = None) -> dict:
    """Elenen sahnenin OTOMATİK kontrol sonucu (K-35): "inceleme" (İnceleme gerekli) | "kesin_hata" | "servis".
    Kesin hata yalnız algılama güveni düşük DEĞİLKEN ve afiş biçimi ürün oranından %30+ farklıyken yazılır; ±%3 boy
    kuralına takılan ama kaba sınırın içinde kalan retler "İnceleme gerekli"dir (sahne yine kullanılmaz, ama kesin
    üretim hatası denmez). Aynı maske ölçümü hem reddi hem teşhisi verdiği için güven ayrıca değerlendirilir."""
    tur = rec.get("tur")
    if tur == "servis_hatasi":
        return {"durum": "servis", "guven": None, "kaynak": "servis", "nedenler": [], "aciklama": "Servis hatası; görsel değerlendirilmedi."}
    olcum, tk, alg = rec.get("olcum") or {}, rec.get("tam_kumas") or {}, rec.get("algilama")
    n = (rec.get("neden") or "").lower()
    dusuk = []
    asp = olcum.get("aspect")
    sapma = (asp / urun_orani - 1.0) if asp else None
    if sapma is None:
        dusuk.append("Afiş ölçülemedi ya da bulunamadı.")
    if tk.get("yayilma_supheli"):
        dusuk.append(f"Alt kenarda yalnız bir yana yayılma var (sol {tk.get('yayilma_sol_px')} px / sağ {tk.get('yayilma_sag_px')} px): "
                     "maske zemine ya da arka plana taşmış olabilir.")
    if tk.get("birikme") and tk.get("temas_yontemi") == "kenar_yayilmasi":
        dusuk.append("Zemindeki birikme yalnız kenar yayılmasından çıkarıldı; boy tahmini güvenilir değil.")
    if tur == "birikme_cozulemedi" and sapma is not None and abs(sapma) <= ALGILAMA_ORAN_UYUM:
        dusuk.append(f"Afiş oranı ürünle uyumlu (%{sapma * 100:+.0f}) ama birikme ölçüldü; çelişkili.")
    kr = rec.get("kararlilik") or {}
    if kr.get("kararsiz"):
        vs = ", ".join(f"{v.get('varyant')}: {'kabul' if v.get('kabul') else 'ret'}"
                       + (f" {v['asili_cm']:.0f} cm" if v.get("asili_cm") else "") for v in kr.get("varyantlar", []))
        dusuk.append(f"Ölçüm kararsız: aynı sahne küçük görüntü farklarıyla yeniden ölçülünce "
                     + ("karar değişiyor" if kr.get("karar_degisti") else f"asılı boy %{kr.get('asili_oynama', 0) * 100:.0f} oynuyor")
                     + (f" ({vs})." if vs else "."))
    if alg:
        if (alg.get("yan_tasma_orani") or 0) > YAN_TASMA_DUSUK_GUVEN:
            dusuk.append(f"Maske kenarı satırların %{alg['yan_tasma_orani'] * 100:.0f}'inde düz kenardan dışarı taşıyor.")
        ub = alg.get("ust_bant_orani") or 0
        a = tk.get("asili_cm")
        boy = boy_cm or 200.0
        if ub >= 0.01 and a and abs(a / boy - 1) - ub < BOY_TOL:
            dusuk.append(f"Üstte maskeye girmemiş kumaş bandı var (boyun %{ub * 100:.0f}'i); dahil edilirse karar değişebilir.")
    guven = "dusuk" if dusuk else ("bilinmiyor" if alg is None and not kr else "yuksek")
    if guven != "dusuk" and sapma is not None and abs(sapma) >= KESIN_ORAN_SAPMA:
        yon = "geniş/kısa" if sapma > 0 else "dar/uzun"
        return {"durum": "kesin_hata", "guven": guven, "kaynak": "uretim", "oran_sapmasi": round(sapma, 3), "nedenler": [],
                "aciklama": f"Afiş ürüne göre belirgin {yon} çizilmiş (en/boy %{sapma * 100:+.0f}; kaba sınır ±%30)."}
    if dusuk:
        acik = "Algılama güveni düşük: " + " ".join(dusuk) + " Kesin hata denmez; gözle bakılmalı."
    elif sapma is not None:
        acik = (f"Ölçülen en/boy ürünle %{sapma * 100:+.0f} farklı; ±%3 boy kuralına takıldı ama kaba sınırın (±%30) içinde. "
                "Sahne bu ürün için kullanılmadı; gözle bakılmalı.")
    else:
        acik = "Ret nedeni gözle doğrulanmalı."
    if guven == "bilinmiyor":
        acik += " (Eski kayıt: algılama güveni ölçümleri yok.)"
    return {"durum": "inceleme", "guven": guven, "kaynak": "olasi_algilama" if dusuk else "belirsiz",
            "oran_sapmasi": round(sapma, 3) if sapma is not None else None, "nedenler": dusuk, "aciklama": acik}


def birlesik_durum(oto: dict, insan: dict | None) -> dict:
    """Otomatik sonuç + insan etiketi -> gösterilecek durum. İnsan etiketi otomatik kaydı DEĞİŞTİRMEZ; yalnız gösterimi
    etkiler. 'Kullanılabilir' görsel kabuldür, fiziksel ölçü doğrulaması sayılmaz."""
    k = (insan or {}).get("karar")
    if oto.get("durum") == "servis":
        return {"durum": "servis", "not": ""}
    if k == "gercekten_hatali":
        return {"durum": "kesin_hata", "not": "İnsan etiketi: gerçekten hatalı."}
    if k == "kullanilabilir":
        cel = oto.get("durum") == "kesin_hata"
        return {"durum": "inceleme", "not": ("Çelişki: otomatik kontrol kesin hata diyor, sen kullanılabilir dedin. " if cel else "")
                + "İnsan etiketi: kullanılabilir (görsel kabul; ölçü doğrulaması değil)."}
    return {"durum": oto.get("durum"), "not": ""}


def siniflandir(rec: dict, urun_orani: float, boy_cm: float | None = None) -> dict:
    """Geriye uyum: kontrol_sonucu ile aynı (eski 'kaynak' alanı da döner)."""
    return kontrol_sonucu(rec, urun_orani, boy_cm)


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
    # ALGILAMA başarısızlıkları baskı/desen hatasından AYRI gösterilir (2026-10-13, iş 054333: "açık renkli/nötr değil"
    # mesajındaki "boş afiş ister" ifadesi yanlışlıkla "yazı/desen var" diye çevriliyordu)
    if "açık renkli/nötr değil" in n:
        return "Program kumaşı bulamadı: seçtiği bölge koyu (arka plan olabilir). Algılama hatası; afişte desen olduğu anlamına gelmez."
    if "güvenilir afiş bölgesi bulunamadı" in n or "afiş bulunamadı" in n or "afiş ölçülemedi" in n:
        return "Program kumaşı güvenle bulamadı (algılama hatası; afişte desen olduğu anlamına gelmez)."
    if "çok büyük" in n:
        return "Program kumaş yerine çok büyük bir bölge seçti (duvar/zemin olabilir); algılama hatası."
    if "çok küçük" in n:
        return "Program kumaş olarak çok küçük bir bölge buldu; algılama hatası olabilir."
    if "taşıyor" in n or "kesilmiş" in n:
        return "Bulunan bölge kadraj kenarına taşıyor; afiş kesilmiş ya da algılama zemine/duvara yayılmış olabilir."
    if "boş görünmüyor" in n or "boş değil" in n or "yazı/desen" in n:
        return "Afişin üzerinde yazı ya da desen var gibi görünüyor (boş değil)."
    if "yere kadar uzanmıyor" in n or "havada" in n:
        return "Afişin alt kenarı zemine ulaşmıyor; kumaş havada bitiyor."
    if "çok dar" in n:
        return "Afiş ürüne göre fazla dar/uzun çizilmiş."
    if tur == "birikme_cozulemedi":
        return f"Kumaşın alt kısmı yerde birikmiş görünüyor (tahmini {tk.get('gizli_cm', 0):.0f} cm) ve tasarımın o bölgesinde yazı var."
    if tur == "sahne_kivrim":
        return "Kumaş fazla kıvrımlı; tasarım bozulmadan sığmıyor."
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
        return {"fotograflar": {}, "elenenler": {}}


def elenen_anahtari(rec: dict) -> str:
    """Elenen kaydının insan etiketi anahtarı: '<üretim no ya da 0>:<çağrı>'."""
    return f"{int(rec.get('uretim_no') or 0)}:{int(rec.get('cagri') or 0)}"


def insan_elenen_yaz(job: str, anahtar: str, karar: str | None, not_: str = "", kaynak: str = "kullanici") -> dict:
    """Elenen deneme için insan etiketi: 'kullanilabilir' | 'gercekten_hatali' | None (sil). rapor.json'a DOKUNMAZ."""
    if karar not in INSAN_ELENEN_KARARLARI + (None,):
        raise ValueError("karar 'kullanilabilir', 'gercekten_hatali' ya da boş olmalı")
    if not re.fullmatch(r"\d+:\d+", anahtar or ""):
        raise ValueError("geçersiz elenen anahtarı")
    d = insan_oku(job)
    es = d.setdefault("elenenler", {})
    if karar is None:
        es.pop(anahtar, None)
    else:
        es[anahtar] = {"karar": karar, "not": (not_ or "").strip()[:300], "kaynak": kaynak,
                       "zaman": datetime.now().isoformat(timespec="seconds")}
    _insan_kaydet(job, d)
    return d


def _insan_kaydet(job: str, d: dict):
    tmp = os.path.join(job, INSAN_DOSYASI + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(job, INSAN_DOSYASI))


def insan_yaz(job: str, foto: str, karar: str | None, not_: str = "") -> dict:
    if karar not in ("begendim", "uygun_degil", None):
        raise ValueError("karar 'begendim', 'uygun_degil' ya da boş olmalı")
    d = insan_oku(job)
    fs = d.setdefault("fotograflar", {})
    if karar is None:
        fs.pop(foto, None)
    else:
        fs[foto] = {"karar": karar, "not": (not_ or "").strip()[:300], "zaman": datetime.now().isoformat(timespec="seconds")}
    _insan_kaydet(job, d)
    return d


# ---------------------------------------------------------------------------- sürüm karşılaştırması (yalnız rapor)
ADAY_KURALLARI = {
    "en_az_cagri": 12,          # HER İKİ sürüm için: tek (başarısız) eski denemeye karşı aday önerilmez
    "en_az_kabul": 3,           # aday için
    "en_az_insan_degerlendirmesi": 3,   # HER İKİ sürüm için; eksik beğeni verisi sıfır beğeni SAYILMAZ
    "kabul_orani_farki": 0.10,  # aday kabul oranı etkinden en az bu kadar yüksek olmalı (algılama şüphelileri hariç)
    "begeni_orani_dusmesin": True,
    "sure_artisi_en_fazla": 0.25,
}
# Karşılaştırılabilirlik anahtarı: prompt sürümü DIŞINDAKİ her şey aynı olmalı (K-32)
KARSILASTIRMA_ALANLARI = ("kategori", "model", "olcu_id", "sahne_gorevi", "referans_kumesi", "ayar_ozeti")


def _anahtar_degeri(v):
    if isinstance(v, dict):
        return json.dumps(v, sort_keys=True, ensure_ascii=False)
    return v


def ozet(jobs_dir: str) -> list[dict]:
    """Tüm işlerin deneme kayıtlarından gruplar: (kategori, model, ölçü, sahne görevi, referans kümesi, üretim ayarları,
    prompt sürümü). Eski işlerde kayıt yoksa sayılmaz (sonradan tahminle doldurulmaz). Anahtar alanlarından biri eksik
    olan kayıtlar ayrı grupta toplanır ve 'eksik_alanlar' ile işaretlenir (karşılaştırılamaz).
    Olası algılama hatası ve servis hatası olan çağrılar kabul oranı paydasından ÇIKARILIR."""
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
            ayar = dict(d.get("ayar_ozeti") or {})
            kil = ayar.pop("kilavuz_surumu", None)          # kılavuz sürümü deney BİLEŞENİDİR; ayar karşılaştırmasından ayrı (K-44)
            alan = {"kategori": rap.get("kategori"), "model": d.get("model"), "olcu_id": d.get("olcu_id"),
                    "sahne_gorevi": d.get("sahne_gorevi"), "referans_kumesi": d.get("referans_kumesi"),
                    "ayar_ozeti": ayar or None}
            eksik = [k for k in KARSILASTIRMA_ALANLARI if alan[k] in (None, "", {})]
            if ayar.get("kilavuz") and kil is None:
                eksik.append("kilavuz_surumu")                # kılavuz kullanılmış ama sürümü kayıtlı değil
            key = tuple(_anahtar_degeri(alan[k]) for k in KARSILASTIRMA_ALANLARI) + (d.get("prompt_surumu"), kil)
            g = grup.setdefault(key, dict(alan, prompt_surumu=d.get("prompt_surumu"), kilavuz_surumu=kil, eksik_alanlar=eksik,
                                          cagri=0, kabul=0, elendi_uretim=0, elendi_algilama=0, elendi_belirsiz=0,
                                          servis_hatasi=0, sure_toplam=0.0, begendim=0, uygun_degil=0, isler=set()))
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
        g["insan_degerlendirmesi"] = hd
        g["begeni_orani"] = round(g["begendim"] / hd, 3) if hd else None      # veri yoksa None (0 DEĞİL)
        g["is_sayisi"] = len(g.pop("isler"))
        g.pop("sure_toplam")
        out.append(g)
    return sorted(out, key=lambda x: tuple(str(x[k]) for k in KARSILASTIRMA_ALANLARI)
                  + (str(x["prompt_surumu"]), str(x.get("kilavuz_surumu"))))


def deney_turu(etkin: dict, aday: dict) -> dict:
    """K-44: hangi bileşenler değişti? Prompt dışındaki koşullar (karsilastirilabilir) zaten aynıdır.
    yalniz_prompt          : kılavuz aynı (ya da ikisi de kılavuzsuz) -> fark prompta bağlanabilir.
    prompt_kilavuz_paketi  : prompt VE kılavuz birlikte değişti -> paket olarak değerlendirilir; promptun tek başına
                             etkisi bu deneyden ÇIKARILAMAZ.
    yalniz_kilavuz         : prompt aynı, kılavuz farklı."""
    dp = etkin.get("prompt_surumu") != aday.get("prompt_surumu")
    dk_ = etkin.get("kilavuz_surumu") != aday.get("kilavuz_surumu")
    tur = "prompt_kilavuz_paketi" if (dp and dk_) else ("yalniz_kilavuz" if dk_ else "yalniz_prompt")
    deg = [f"prompt: {etkin.get('prompt_surumu')} -> {aday.get('prompt_surumu')}"] if dp else []
    if dk_:
        deg.append(f"kılavuz: {etkin.get('kilavuz_surumu')} -> {aday.get('kilavuz_surumu')}")
    notu = {"yalniz_prompt": "Yalnız prompt değişti; fark prompta bağlanabilir.",
            "prompt_kilavuz_paketi": "Prompt ve kılavuz birlikte değişti: sonuç PAKETİN etkisidir; promptun tek başına etkisi "
                                     "bu deneyden çıkarılamaz.",
            "yalniz_kilavuz": "Yalnız kılavuz değişti; fark kılavuza bağlanabilir."}[tur]
    return {"deney_turu": tur, "degisen_bilesenler": deg, "not": notu}


def karsilastirilabilir(a: dict, b: dict) -> list[str]:
    """Boş liste = karşılaştırılabilir; değilse nedenler."""
    ned = []
    for g, ad in ((a, "etkin"), (b, "aday")):
        if g.get("eksik_alanlar"):
            ned.append(f"{ad} sürüm kayıtlarında eksik alan: {', '.join(g['eksik_alanlar'])}.")
    if ned:
        return ned
    adlar = {"kategori": "kategori", "model": "model", "olcu_id": "ürün ölçüsü", "sahne_gorevi": "sahne görevi",
             "referans_kumesi": "referans kümesi", "ayar_ozeti": "üretim ayarları"}
    for k in KARSILASTIRMA_ALANLARI:
        if _anahtar_degeri(a.get(k)) != _anahtar_degeri(b.get(k)):
            ned.append(f"{adlar[k]} farklı.")
    return ned


def aday_karari(etkin: dict | None, aday: dict | None, kurallar: dict = ADAY_KURALLARI) -> dict:
    """Yalnız ÖNERİ üretir; sürümü değiştirmez. Karar sırası: karşılaştırılamaz -> yetersiz veri -> etkin kalsın / öneri."""
    if not aday:
        return {"karar": "yetersiz_veri", "nedenler": ["Aday sürüm için kayıt yok."]}
    if not etkin:
        return {"karar": "karsilastirilamaz", "nedenler": ["Aynı koşullarda (kategori, model, ölçü, sahne görevi, "
                                                           "referans kümesi, üretim ayarları) etkin sürüm kaydı yok."]}
    ned = karsilastirilabilir(etkin, aday)
    if ned:
        return {"karar": "karsilastirilamaz", "nedenler": ned}
    ned = []
    for g, ad in ((etkin, "Etkin"), (aday, "Aday")):
        if g["cagri"] < kurallar["en_az_cagri"]:
            ned.append(f"{ad} sürüm için en az {kurallar['en_az_cagri']} çağrı gerekir ({g['cagri']}).")
        if g["insan_degerlendirmesi"] < kurallar["en_az_insan_degerlendirmesi"]:
            ned.append(f"{ad} sürüm için en az {kurallar['en_az_insan_degerlendirmesi']} insan değerlendirmesi gerekir "
                       f"({g['insan_degerlendirmesi']}).")
        if g["kabul_orani"] is None:
            ned.append(f"{ad} sürümün kabul oranı hesaplanamıyor.")
    if aday["kabul"] < kurallar["en_az_kabul"]:
        ned.append(f"Aday için en az {kurallar['en_az_kabul']} kabul gerekir ({aday['kabul']}).")
    if ned:
        return {"karar": "yetersiz_veri", "nedenler": ned}
    ok = []
    if aday["kabul_orani"] - etkin["kabul_orani"] < kurallar["kabul_orani_farki"]:
        ok.append("Kabul oranı yeterince yükselmedi.")
    if kurallar["begeni_orani_dusmesin"] and aday["begeni_orani"] < etkin["begeni_orani"]:   # ikisi de None değil (yukarıda)
        ok.append("İnsan beğenisi düştü.")
    if etkin.get("ort_sure_sn") and aday.get("ort_sure_sn") and \
            aday["ort_sure_sn"] > etkin["ort_sure_sn"] * (1 + kurallar["sure_artisi_en_fazla"]):
        ok.append("Çağrı süresi belirgin arttı.")
    if ok:
        return {"karar": "etkin_kalsin", "nedenler": ok}
    return {"karar": "aday_onerilir", "nedenler": ["Ölçütler sağlandı; geçiş kullanıcı onayıyla yapılır, önceki sürüme dönülebilir."]}


def oneriler(gruplar: list[dict], etkin_surum: str) -> list[dict]:
    """Her aday grup için, prompt sürümü dışında BİREBİR aynı koşullardaki etkin grupla karşılaştırma önerisi."""
    out = []
    for g in gruplar:
        if g["prompt_surumu"] == etkin_surum:
            continue
        adaylar = [] if g["eksik_alanlar"] else [x for x in gruplar if x["prompt_surumu"] == etkin_surum
                                                 and not x["eksik_alanlar"] and not karsilastirilabilir(x, g)]
        # önce aynı kılavuzlu etkin grup (yalnız prompt deneyi); yoksa paket deneyi
        etkin = next((x for x in adaylar if x.get("kilavuz_surumu") == g.get("kilavuz_surumu")), None) or \
            (adaylar[0] if adaylar else None)
        r = aday_karari(etkin, g) if not g["eksik_alanlar"] else \
            {"karar": "karsilastirilamaz", "nedenler": [f"Aday kayıtlarında eksik alan: {', '.join(g['eksik_alanlar'])}."]}
        dt = deney_turu(etkin, g) if etkin else {"deney_turu": None, "degisen_bilesenler": [], "not": ""}
        if dt["deney_turu"] == "prompt_kilavuz_paketi" and r["karar"] == "aday_onerilir":
            r = dict(r, nedenler=r["nedenler"] + [dt["not"]])
        out.append(dict(r, **dt, kategori=g["kategori"], model=g["model"], olcu_id=g["olcu_id"], aday=g["prompt_surumu"],
                        aday_kilavuz=g.get("kilavuz_surumu"), etkin_kilavuz=(etkin or {}).get("kilavuz_surumu")))
    return out


# ---------------------------------------------------------------------------- durma sınırları simülasyonu
def cagri_dizisi(rap: dict) -> list[dict]:
    """Bir işin çağrı sırası: [{cagri, sonuc, hata_imzasi, turetildi}]. Yeni işlerde 'denemeler' kaydından alınır.
    Eski işlerde kayıttan TÜRETİLİR (yeni bilgi uydurulmaz): son üretimin çağrı sayısı ve elenen listesi bilinir; elenen
    listesinde olmayan çağrı numaraları kabul edilen çağrılardır. Birden çok üretimli eski işte türetme yapılmaz."""
    den = rap.get("denemeler")
    if den:
        son = max(d.get("uretim_no", 1) for d in den)
        return [{"cagri": d["cagri"], "sonuc": d.get("sonuc"), "hata_imzasi": d.get("hata_imzasi"), "turetildi": False,
                 "supheli": (d.get("siniflama") or {}).get("guven") == "dusuk"}
                for d in den if d.get("uretim_no", 1) == son]
    su = rap.get("son_uretim") or {}
    n = int(su.get("cagri") or 0)
    el = {e.get("cagri"): e for e in rap.get("elenenler", []) if e.get("cagri")}
    if not n or len(el) + int(su.get("uretilen") or 0) != n:
        return []                                          # tutarsız/çok üretimli eski kayıt: türetilmez
    oran = (rap.get("urun_profili") or {}).get("oran") or 0.375
    out = []
    for c in range(1, n + 1):
        e = el.get(c)
        if e:
            son = "servis_hatasi" if e.get("tur") == "servis_hatasi" else "elendi"
            out.append({"cagri": c, "sonuc": son, "hata_imzasi": e.get("hata_imzasi") or hata_imzasi(e.get("tur"), e.get("neden")),
                        "turetildi": True, "supheli": kontrol_sonucu(e, oran).get("guven") == "dusuk"})
        else:
            out.append({"cagri": c, "sonuc": "kabul", "hata_imzasi": None, "turetildi": True, "supheli": False})
    return out


def durma_simulasyonu(dizi: list[dict], ayni: int, sonucsuz: int, tavan: int, hedef: int | None = None,
                      supheli_dur: bool = False) -> dict:
    """Kayıtlı çağrı dizisinde verilen sınırlarla üretimin hangi çağrıda duracağını hesaplar (sağlayıcı çağrısı yok).
    Orkestratördeki kuralın aynısı: kabul iki sayacı da sıfırlar; servis hatası aynı-hata serisini keser ama sonuçsuz
    sayacını artırır. Dönüş: {dur_cagri, neden, kabul, harcanan, kacan_kabul}."""
    seri_imza, seri, kuru, kabul = None, 0, 0, 0
    for i, d in enumerate(dizi):
        c = d["cagri"]
        if tavan and c > tavan:
            return _sim(c - 1, "tavan", kabul, dizi, i)
        if d["sonuc"] == "kabul":
            kabul += 1
            seri_imza, seri, kuru = None, 0, 0
            if hedef and kabul >= hedef:
                return _sim(c, "hedef", kabul, dizi, i + 1)
            continue
        if d["sonuc"] == "elendi":
            seri = seri + 1 if d["hata_imzasi"] == seri_imza else 1
            seri_imza = d["hata_imzasi"]
        else:
            seri_imza, seri = None, 0
        kuru += 1
        if supheli_dur and d.get("supheli"):
            return _sim(c, "supheli_olcum", kabul, dizi, i + 1)
        if ayni and seri >= ayni:
            return _sim(c, "ayni_hata", kabul, dizi, i + 1)
        if sonucsuz and kuru >= sonucsuz:
            return _sim(c, "sonucsuz", kabul, dizi, i + 1)
    son = dizi[-1]["cagri"] if dizi else 0
    return _sim(son, "tavan" if tavan and son >= tavan else "kayit_bitti", kabul, dizi, len(dizi))


def _sim(dur, neden, kabul, dizi, kalan_bas):
    kacan = sum(1 for d in dizi[kalan_bas:] if d["sonuc"] == "kabul")
    return {"dur_cagri": dur, "neden": neden, "kabul": kabul, "harcanan": dur, "kacan_kabul": kacan}


def sinir_tablosu(dizi: list[dict], tavan: int, hedef: int | None = None,
                  ayni_degerleri=(0, 3, 4, 5), sonucsuz_degerleri=(0, 4, 5, 6, 7, 8), supheli=(False, True)) -> list[dict]:
    """Farklı sınır çiftleri için durma noktası tablosu (yalnız kayıtlı veriyle)."""
    return [dict(durma_simulasyonu(dizi, a, k, tavan, hedef, sp), ayni_hata_siniri=a, sonucsuz_siniri=k, supheli_dur=sp)
            for sp in supheli for a in ayni_degerleri for k in sonucsuz_degerleri]

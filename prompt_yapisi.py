# -*- coding: utf-8 -*-
"""
Prompt sürümleri ve kısa, gelişebilen prompt yapısı (2026-10-13).

ETKİN sürüm "2A": prompts.build_scene_prompt (değişmedi; ~1150 kelime).
ADAY sürüm "3A-aday": dört bölümlü kısa yapı. Varsayılan olarak HİÇBİR kategoride etkin DEĞİLDİR; yalnız kullanıcı
Ayarlar'dan bir kategori için elle seçebilir. Otomatik terfi ya da otomatik ücretli iyileştirme döngüsü YOKTUR.

Bölümler ve gerekçeli uzunluk sınırları (kelime):
  1. urun   (≤ 120): DEĞİŞTİRİLEMEZ ürün kuralları (kullanıcının kesin kuralları). Sabit metin + profil değerleri
                     (ölçü, kurdele rengi). Kod bu metni otomatik değiştirmez; test özet (hash) ile korur.
                     Gerekçe: 5 kural + ölçü + renk tek cümlelerle ~100 kelimeye sığar; daha uzunu tekrar demektir.
  2. kamera (≤ 60) : kare, önden, orta yükseklik; afişin kadrajdaki boyu/eni SAYIYLA (profil oranından hesaplanır).
                     Gerekçe: en sık ret "afiş fazla geniş/kısa"; bunu oran cümlesini çoğaltarak değil, kadrajdaki
                     payı açıkça vererek çözmeyi deniyor. Daha uzun kamera tarifinin etkisi ölçülmedi.
  3. ortam  (≤ 115): kategori sahne tarifi (havuzdan ya da referans tarifinden) + ışık + kısa gerçekçilik + misafir.
                     Gerekçe: mevcut havuz tarifleri ortanca 33, en uzun 69 kelime; ışık en çok 16; sabit kısım ~20; ölçülen en uzun ortam bölümü 111 kelime.
                     (En uzun tarifler ileride kısaltılabilir; bu sürümde kategori içerikleri değiştirilmedi.)
  4. model  (≤ 45) : modele/girdiye özel kısa uyarlama (kılavuz görsel, referans görsel). Gerekçe: iki kısa cümle.
Toplam ≤ 330 kelime (etkin 2A: ~1150).

Kurallar: Her başarısızlıkta yeni cümle EKLENMEZ. Tekrarlayan hata için önce nedeni (üretim mi, algılama mı)
docs/kararlar.md'de araştırılır; gerekiyorsa mevcut cümle DEĞİŞTİRİLİR ya da gereksiz cümle ÇIKARILIR ve sürüm
numarası artırılır. Bir kategorinin sürümünü değiştirmek diğer kategorileri ETKİLEMEZ (kategori bazlı seçim).
"""
from __future__ import annotations

import hashlib

import prompts

ETKIN_VARSAYILAN = "2A"
SURUMLER = {
    "2A": {"durum": "etkin", "aciklama": "Aşama 2A promptu (prompts.build_scene_prompt), ~1150 kelime."},
    "3A-aday": {"durum": "aday", "aciklama": "Dört bölümlü kısa yapı (~250 kelime); değerlendirilmedi."},
}
LIMITLER = {"urun": 120, "kamera": 60, "ortam": 115, "model": 45}
TOPLAM_LIMIT = 330

# ---- 1. DEĞİŞTİRİLEMEZ ürün kuralları (kullanıcının kesin kuralları; CLAUDE.md §1) ------------------------------
URUN_KURALLARI = (
    "PRODUCT (fixed): one blank off-white cotton-linen banner, completely empty: no print, text, pattern, border or fringe. "
    "It hangs from the top rod of a slim free-standing light pine stand (two thin posts, two small feet); the posts stay "
    "visible beside it. A soft {ribbon} ribbon bow is tied at each top corner; the tails hang outside the banner, never on it. "
    "The bottom hem reaches the floor and may rest on it slightly, never ending in the air. Nothing covers the banner. "
    "SIZE (fixed): {w} cm wide and {h} cm tall, a tall narrow strip {r:.2f} times taller than wide."
)
URUN_KURALLARI_OZET = hashlib.sha256(URUN_KURALLARI.encode("utf-8")).hexdigest()[:16]


def kural_metni(profile, ribbon_hex: str | None) -> str:
    rib = f"{prompts.color_en(ribbon_hex)} ({ribbon_hex})" if ribbon_hex else "satin, in a colour that suits the scene,"
    return URUN_KURALLARI.format(ribbon=rib, w=profile.en_cm, h=profile.boy_cm, r=profile.boy_cm / profile.en_cm)


# ---- 2. kamera ve yerleşim ----------------------------------------------------------------------------------
def kamera_metni(profile) -> str:
    h_frac = 0.75                                        # kılavuzla uyumlu: afiş kadraj yüksekliğinin ~%75'i
    w_frac = h_frac * profile.oran                        # kare kadrajda genişlik payı (75x200 için ≈%28)
    return (f"CAMERA: square 1:1 photo, straight-on front view from mid-height; the banner faces the camera squarely, "
            f"its edges vertical. The banner fills about {round(h_frac * 100)}% of the image height but only about "
            f"{round(w_frac * 100)}% of its width. The whole stand, both feet and the floor are inside the frame.")


# ---- 3. ortam ----------------------------------------------------------------------------------------------
def ortam_metni(category: str, index: int, round_no: int, people: bool, scene_desc: str | None) -> str:
    pool = prompts.CATEGORIES[prompts.canon(category)]
    desc = (scene_desc or "").strip() or pool[index % len(pool)]
    outdoor = not desc.startswith("IN:")
    if desc[:3] in ("OUT", "IN:"):
        desc = desc.split(":", 1)[1].strip()
    desc = desc.replace("SCENE:", "").strip()
    lights = prompts.LIGHTS_OUT if outdoor else prompts.LIGHTS_IN
    light = lights[(index * 3 + index // len(pool) * 2 + round_no) % len(lights)]
    who = " Guests far behind it, small and out of focus." if people else ""
    return (f"SCENE: {desc} A darker, textured backdrop right behind the banner. {light}"
            f"{who} Candid real-event photo, not a render; no text or signs.")


# ---- 4. modele / girdiye özel kısa uyarlama -----------------------------------------------------------------
def model_metni(guided: bool, has_refs: bool, model_id: str | None = None) -> str:
    parts = []
    if guided:
        parts.append("Image 1 is a layout guide: keep the banner's position, size and proportion exactly; replace only "
                     "the grey placeholder background with the scene.")
    if has_refs:
        parts.append("The other image shows mood and venue only; ignore any artwork, size or shape of banners in it.")
    return " ".join(parts)


def _kelime(s: str) -> int:
    return len(s.split())


def build_candidate(category, index, profile, ribbon=None, people=False, has_refs=False, guided=False,
                    scene_desc=None, round_no=0, model_id=None) -> tuple[str, dict]:
    """Aday sürüm "3A-aday": (prompt, bölümler) döner. Bölüm sınırları aşılırsa ValueError (sessiz kesme yok)."""
    b = {"model": model_metni(guided, has_refs, model_id),
         "urun": kural_metni(profile, (ribbon or {}).get("hex")),
         "kamera": kamera_metni(profile),
         "ortam": ortam_metni(category, index, round_no, people, scene_desc)}
    for k, lim in LIMITLER.items():
        if _kelime(b[k]) > lim:
            raise ValueError(f"prompt bölümü '{k}' {_kelime(b[k])} kelime > sınır {lim}")
    text = " ".join(x for x in (b["model"], b["urun"], b["kamera"], b["ortam"]) if x)
    if _kelime(text) > TOPLAM_LIMIT:
        raise ValueError(f"prompt toplamı {_kelime(text)} kelime > {TOPLAM_LIMIT}")
    return text, b


def secili_surum(settings, category: str) -> str:
    """Kategori bazlı seçim: bir kategorinin sürümü diğerlerini etkilemez. Bilinmeyen değer -> etkin varsayılan."""
    m = getattr(settings, "prompt_surumleri", None) or {}
    v = m.get(prompts.canon(category), ETKIN_VARSAYILAN)
    return v if v in SURUMLER else ETKIN_VARSAYILAN


def build(version: str, category, index, profile, *, ribbon=None, people=False, has_refs=False, guided=False,
          scene_desc=None, round_no=0, model_id=None) -> tuple[str, dict]:
    """Seçili sürümle prompt üretir. (prompt, bilgi) — bilgi rapora kaydedilir (prompt sürümü, bölüm uzunlukları)."""
    if version == "3A-aday":
        text, b = build_candidate(category, index, profile, ribbon, people, has_refs, guided, scene_desc, round_no, model_id)
        return text, {"prompt_surumu": version, "urun_kurallari_ozeti": URUN_KURALLARI_OZET,
                      "bolum_kelime": {k: _kelime(v) for k, v in b.items()}}
    text = prompts.build_scene_prompt(category, index, profile.en_cm, profile.boy_cm, has_refs, round_no, guided=guided,
                                      people=people, ribbon=ribbon, scene_desc=scene_desc, profile=profile)
    return text, {"prompt_surumu": "2A"}

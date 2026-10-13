# -*- coding: utf-8 -*-
"""
Ürün profili ve tasarım girdisi kontrolü (Aşama 2A).

Üç kavram birbirinden AYRIDIR (CLAUDE.md):
  * fiziksel ürün ölçüsü  -> kullanıcı seçer (ölçü kimliğiyle: "75x200"); PNG oranından ASLA tahmin edilmez
  * PNG oranı             -> tasarım dosyasının piksel en/boy oranı
  * baskı alanı           -> "tam_kumas" modunda PNG tuvali kumaşın TAMAMIDIR (iç boşluklar tasarımın parçasıdır)

Oran uyuşmazlığı sessizce düzeltilmez: tasarım kırpılmaz, esnetilmez, küçültülüp ortalanmaz. Kontrol sonucu uyarı ve
önizleme verir; uyuşmayan tasarımla nihai üretim BEKLETİLİR.

Bilinmeyen fiziksel bilgiler (gramaj, karışım oranı, kuşgözü çapı...) None kalır; uydurulmaz.
Bu modül ağ ve sağlayıcı kullanmaz.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

import cvio

# Satış ölçüleri: kimlik -> (en_cm, boy_cm). Aynı oranlı ölçüler (50x100 ile 150x300; 75x200 ile 150x400) AYRI kimliktir.
OLCULER: dict[str, tuple[int, int]] = {
    "50x100": (50, 100),
    "50x150": (50, 150),
    "75x200": (75, 200),
    "150x300": (150, 300),
    "150x400": (150, 400),
}
SATIS_OLCULERI = list(OLCULER)            # ilanda satılan ölçüler (değişmez)
VARSAYILAN_ORNEK_OLCU = "75x200"         # ilan görsellerinde gösterilen örnek ölçü (satış ölçülerinden ayrı alan)

ORAN_TOLERANSI = 0.01                    # VARSAYIM: |log(PNG oranı / kumaş oranı)| bunun üstündeyse "uyuşmuyor" (yaklaşık %1).
                                         # Tolerans içindeki fark tam kumaş yerleşiminde dikeyde en fazla bu kadar esnemeye
                                         # karşılık gelir ve tasarım kontrolünde "tolerans_ici_esneme" olarak raporlanır.
DPI_BILGI_ESIGI = 100                    # VARSAYIM: altı "düşük olabilir" diye bilgi verilir; baskı firmasıyla doğrulanmadı

KUMAS_RENGI_BGR = (214, 228, 236)        # önizlemede baskısız kumaş (krem) — yalnız gösterim içindir
PROFIL_SURUMU = 1

# Hata türleri (tasarım düzeyi ve fotoğraf/sahne düzeyi) — rapor ve arayüz aynı adları kullanır
HATA_TURLERI = {
    "tasarim_oran_uyusmazligi": "Tasarım oranı seçilen ölçüyle uyuşmuyor",
    "sahne_geometri": "Sahnedeki afiş ürün ölçüsüne uymuyor",
    "kalite_kapisi": "Sahne kalite kapısından geçmedi",
    "servis_hatasi": "Servis hatası",
    "birikme_cozulemedi": "Zemindeki birikme doğru çizilemedi",
    "sahne_kivrim": "Kumaş yüzeyi tasarımı bozmadan taşıyacak kadar düz değil",
    "temas_belirsiz": "Kumaşın zemine temas çizgisi belirsiz (incelemeye bırakıldı)",
}


@dataclass
class UrunProfili:
    urun_turu: str = "kumas_afis"                 # ürün türü (etkinlik kategorisinden AYRI)
    olcu_id: str = VARSAYILAN_ORNEK_OLCU          # bu işte/sahnede gösterilen fiziksel ölçü
    en_cm: int | None = None                      # olcu_id'den doldurulur ve rapora KAYDEDİLİR (tablo ileride değişse de iş anlamını korur)
    boy_cm: int | None = None
    tasarim_modu: str = "tam_kumas"               # PNG tuvali = kumaşın tamamı
    satis_olculeri: list = field(default_factory=lambda: list(SATIS_OLCULERI))
    malzeme: dict = field(default_factory=lambda: {"tur": "pamuk-keten", "karisim": None, "gramaj_gsm": None})
    sergileme: dict = field(default_factory=lambda: {
        "bicim": "standa_asili",                  # sahnede ahşap stand dekoru; stand paket içeriği değildir
        "stand_paket_icerigi": False,
        "alt_kenar": "zemine_deger_ya_da_hafif_birikir",   # havada bitmez; birikme miktarı sabitlenmez
    })
    gorunur_fiyonk: dict = field(default_factory=lambda: {   # görsel öğe (tüm sahneler kurdeleli)
        "var": True, "renk": None, "konum": "ust_koseler_cubuk",
        "baglanti_gorunur_zorunlu": False,        # kurdelenin kuşgözünden geçişi görünmek zorunda değil; ret nedeni değil
    })
    fiziksel_baglanti: dict = field(default_factory=lambda: {"kusgozu": None, "kusgozu_cap_mm": None})  # opsiyonel ürün özelliği; bilinmiyorsa None
    surum: int = PROFIL_SURUMU

    def __post_init__(self):
        if self.olcu_id in OLCULER:
            w, h = OLCULER[self.olcu_id]
            self.en_cm = w if self.en_cm is None else self.en_cm
            self.boy_cm = h if self.boy_cm is None else self.boy_cm

    # ---- türetilen değerler ----
    @property
    def oran(self) -> float:
        return self.en_cm / self.boy_cm

    def to_dict(self) -> dict:
        d = asdict(self)
        d["oran"] = round(self.oran, 4)
        return d

    @classmethod
    def from_dict(cls, d: dict | None, strict: bool = False) -> "UrunProfili":
        """Rapordan okur. strict=False (varsayılan): eski/gelecekteki raporlar okunabilsin diye doğrulama yapılmaz ve
        bilinmeyen alanlar yok sayılır; iç içe sözlükler varsayılanlarla birleştirilir. Yeni iş başlatırken strict=True."""
        d = dict(d or {})
        d.pop("oran", None)
        base = cls(olcu_id=d.get("olcu_id", VARSAYILAN_ORNEK_OLCU)) if d.get("olcu_id") in OLCULER else cls()
        known = {f for f in cls.__dataclass_fields__}
        kw = {}
        for k, v in d.items():
            if k not in known:
                continue
            dv = getattr(base, k)
            kw[k] = {**dv, **(v or {})} if isinstance(dv, dict) else v
        p = cls(**kw)
        if strict:
            p.dogrula()
        return p

    def dogrula(self):
        if self.olcu_id not in OLCULER:
            raise ValueError(f"Bilinmeyen ölçü: {self.olcu_id!r}. Seçenekler: {', '.join(OLCULER)}")
        if self.tasarim_modu != "tam_kumas":
            raise ValueError(f"Desteklenmeyen tasarım modu: {self.tasarim_modu!r}")
        if self.urun_turu != "kumas_afis":
            raise ValueError(f"Bu sürüm yalnız kumaş afiş destekler: {self.urun_turu!r}")
        if (self.en_cm, self.boy_cm) != OLCULER[self.olcu_id]:
            raise ValueError(f"Ölçü kimliği ile cm değerleri çelişiyor: {self.olcu_id} / {self.en_cm}x{self.boy_cm}")
        return self


def profil_olustur(olcu_id: str = VARSAYILAN_ORNEK_OLCU, fiyonk_renk: str | None = None) -> UrunProfili:
    if olcu_id not in OLCULER:
        raise ValueError(f"Bilinmeyen ölçü: {olcu_id!r}. Seçenekler: {', '.join(OLCULER)}")
    p = UrunProfili(olcu_id=olcu_id)
    p.gorunur_fiyonk["renk"] = fiyonk_renk
    return p.dogrula()


def olcu_etiketi(olcu_id: str) -> str:
    w, h = OLCULER[olcu_id]
    return f"{w}×{h} cm"


# ----------------------------------------------------------------------------
# Tasarım girdisi kontrolü
# ----------------------------------------------------------------------------
def _read_unchanged(path_or_img):
    if isinstance(path_or_img, np.ndarray):
        return path_or_img
    im = cvio.imread(path_or_img, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path_or_img)
    return im


def oran_sapmasi(png_oran: float, kumas_oran: float) -> float:
    """İşaretli göreli sapma: >0 PNG kumaştan geniş, <0 dar (log oranı)."""
    return math.log(png_oran / kumas_oran)


def tasarim_kontrol(path_or_img, profil: UrunProfili) -> dict:
    """PNG boyutu, oranı, şeffaflığı ve çözünürlüğünü kontrol eder. Tasarıma DOKUNMAZ.

    Dönen sözlük rapora/arayüze yazılır. "uyumlu" False ise nihai üretim bekletilmelidir."""
    im = _read_unchanged(path_or_img)
    h, w = im.shape[:2]
    ch = 1 if im.ndim == 2 else im.shape[2]
    png_oran = w / h
    sap = oran_sapmasi(png_oran, profil.oran)
    uyumlu = abs(sap) <= ORAN_TOLERANSI
    seffaf = None
    if ch == 4:
        a = im[..., 3].astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0)
        tam, yari = float((a <= 0.02).mean()), float(((a > 0.02) & (a < 0.98)).mean())
        seffaf = {"alfa_kanali": True, "var": (tam + yari) > 0, "tam_seffaf_oran": round(tam, 4), "yari_seffaf_oran": round(yari, 4)}
    else:
        seffaf = {"alfa_kanali": False, "var": False, "tam_seffaf_oran": 0.0, "yari_seffaf_oran": 0.0}
    dpi = w / (profil.en_cm / 2.54)
    dpi_boy = h / (profil.boy_cm / 2.54)
    uyarilar, bilgiler = [], []
    yon = None if uyumlu else ("genis" if sap > 0 else "dar")
    karsilik_boy = profil.en_cm / png_oran              # aynı ende tasarımın karşılık geldiği boy (cm)
    if not uyumlu:
        yon_tr = "geniş" if sap > 0 else "dar"
        uyarilar.append(
            f"Tasarım oranı kumaşla uyuşmuyor: tasarım {w}×{h} px (en/boy {png_oran:.3f}), kumaş {olcu_etiketi(profil.olcu_id)} "
            f"(en/boy {profil.oran:.3f}). Tasarım kumaştan %{abs(math.exp(sap) - 1) * 100:.1f} daha {yon_tr}; "
            f"{profil.en_cm} cm ene göre {karsilik_boy:.0f} cm boya karşılık geliyor. Tasarım kırpılmadı ve esnetilmedi; "
            f"bu ürünün nihai üretimi bekletiliyor. Doğru oranlı bir dosya yükleyin ya da ölçüyü kontrol edin.")
    if not seffaf["var"]:
        bilgiler.append("Dosyada şeffaflık yok: tuvalin tamamı baskı sayılır. Açık renkli zemin, kumaş rengine yakınsa "
                        "baskısız gibi görünür (mevcut baskı modeli).")
    if dpi < DPI_BILGI_ESIGI:
        bilgiler.append(f"Çözünürlük {profil.en_cm} cm ene göre yaklaşık {dpi:.0f} dpi; baskı için düşük olabilir "
                        f"(eşik {DPI_BILGI_ESIGI} dpi bir varsayımdır, baskı firmasıyla doğrulanmalı).")
    if uyumlu and abs(sap) > 1e-4:
        bilgiler.append(f"Tasarım oranı kumaştan %{abs(math.exp(sap) - 1) * 100:.2f} farklı (tolerans içinde); "
                        f"yerleşimde boyda bu kadar esneme olur.")
    return {"px": [int(w), int(h)], "png_oran": round(png_oran, 4), "kumas_oran": round(profil.oran, 4),
            "olcu_id": profil.olcu_id, "en_cm": profil.en_cm, "boy_cm": profil.boy_cm,
            "sapma": round(sap, 4), "tolerans": ORAN_TOLERANSI, "uyumlu": bool(uyumlu),
            "yon": yon, "karsilik_boy_cm": round(karsilik_boy, 1), "fark_cm": round(karsilik_boy - profil.boy_cm, 1),
            "tolerans_ici_esneme": round(math.exp(-sap) - 1, 4) if uyumlu else None,
            "uyan_olculer": uyan_olculer(png_oran),
            "seffaflik": seffaf, "dpi": round(dpi, 1), "dpi_boy": round(dpi_boy, 1), "dpi_not": "dpi kumaş enine göre",
            "uyarilar": uyarilar, "bilgiler": bilgiler,
            "hata_turu": None if uyumlu else "tasarim_oran_uyusmazligi"}


def uyan_olculer(png_oran: float) -> list[str]:
    """Bilgi amaçlı: PNG oranına tolerans içinde uyan ölçü kimlikleri (birden fazla olabilir; SEÇİM YAPMAZ)."""
    return [k for k, (w, h) in OLCULER.items() if abs(oran_sapmasi(png_oran, w / h)) <= ORAN_TOLERANSI]


# ----------------------------------------------------------------------------
# Önizlemeler (yalnız gösterim; tasarım dosyası değişmez)
# ----------------------------------------------------------------------------
def _to_bgr_on_fabric(im, fabric=KUMAS_RENGI_BGR):
    """Şeffaf alanları kumaş rengiyle gösterir (çarpma baskı modeli: tasarım rengi x kumaş)."""
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    f = im.astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0)
    fab = np.array(fabric, np.float32) / 255.0
    if f.shape[2] == 4:
        a = f[..., 3:4]
        rgb = f[..., :3]
        return np.clip((rgb * fab) * a + fab * (1 - a), 0, 1)
    return np.clip(f[..., :3] * fab, 0, 1)


def _hatch(img, x0, y0, x1, y1, color, step=14):
    sub = img[y0:y1, x0:x1]
    if sub.size == 0:
        return
    over = sub.copy()
    over[:] = color
    for k in range(-(y1 - y0), (x1 - x0), step):
        cv2.line(sub, (k, 0), (k + (y1 - y0), y1 - y0), color, 2, cv2.LINE_AA)
    img[y0:y1, x0:x1] = (0.75 * sub + 0.25 * over).astype(img.dtype)


def oran_onizleme(path_or_img, profil: UrunProfili, height: int = 900) -> np.ndarray:
    """Kumaş (seçilen ölçünün oranı) ile tasarımın gerçek oranını yan yana gösterir.

    Tasarım kumaş enine ölçeklenir (en hizalı, üstten başlar). Kumaşın dışına taşan tasarım kısmı KIRMIZI taralı,
    tasarımın kaplamadığı kumaş kısmı TURUNCU taralı gösterilir. Hiçbir şey kırpılmaz/esnetilmez; bu bir uyarı görselidir."""
    im = _read_unchanged(path_or_img)
    dh, dw = im.shape[:2]
    pad = 40
    fab_h = int(height * 0.8)
    fab_w = int(round(fab_h * profil.oran))
    des_w = fab_w
    des_h = int(round(des_w * dh / dw))
    canvas_h = max(fab_h, des_h) + 2 * pad
    canvas_w = fab_w + 2 * pad
    out = np.full((canvas_h, canvas_w, 3), 245, np.uint8)
    x0, y0 = pad, pad
    small = cv2.resize(im, (des_w, des_h), interpolation=cv2.INTER_AREA)
    vis = (_to_bgr_on_fabric(small) * 255).astype(np.uint8)
    out[y0:y0 + des_h, x0:x0 + des_w] = vis
    if des_h > fab_h:                                   # tasarım kumaştan uzun: alt kısım kumaşa sığmıyor
        _hatch(out, x0, y0 + fab_h, x0 + des_w, y0 + des_h, (40, 40, 220))
    elif des_h < fab_h:                                 # tasarım kumaştan kısa: kumaşın altı kaplanmıyor
        out[y0 + des_h:y0 + fab_h, x0:x0 + fab_w] = KUMAS_RENGI_BGR
        _hatch(out, x0, y0 + des_h, x0 + fab_w, y0 + fab_h, (30, 140, 240))
    cv2.rectangle(out, (x0 - 1, y0 - 1), (x0 + fab_w, y0 + fab_h), (60, 60, 60), 2)   # kumaşın sınırı
    return out


def gizli_bolge_onizleme(path_or_img, v_gizli: float | None, height: int = 900) -> np.ndarray:
    """Tasarımın sahnede yerde biriken (görünmeyen) alt kısmını gösterir. v_gizli: tasarım boyunun bu oranından
    aşağısı gizli (0-1). None ya da >=1 ise gizli bölge yoktur. Yazı yapay olarak yukarı taşınmaz; yalnız işaretlenir."""
    im = _read_unchanged(path_or_img)
    dh, dw = im.shape[:2]
    h = int(height)
    w = max(2, int(round(h * dw / dh)))
    vis = (_to_bgr_on_fabric(cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)) * 255).astype(np.uint8)
    if v_gizli is not None and v_gizli < 1.0:
        y = int(round(max(0.0, v_gizli) * h))
        _hatch(vis, 0, y, w, h, (60, 60, 200))
        cv2.line(vis, (0, y), (w, y), (0, 0, 200), 2, cv2.LINE_AA)
    return vis


def murekkep_orani(path_or_img, v_from: float) -> float:
    """Tasarımın v_from'dan aşağısındaki "baskılı" piksel oranı (şeffaf ya da kumaş/beyaz zemin sayılmaz).
    Yerde biriken kısımda baskı var mı sorusuna kaba yanıt verir. Bilinen sınır: parlaklığı 0.85'in üstündeki çok açık
    renkli baskı "baskısız" sayılır. uint8/uint16 ya da 0-1 float girdi kabul eder."""
    im = _read_unchanged(path_or_img)
    h = im.shape[0]
    y = int(round(min(max(v_from, 0.0), 1.0) * h))
    part = im[y:]
    if part.size == 0:
        return 0.0
    if np.issubdtype(part.dtype, np.floating):       # 0-1 aralığında float girdi (ör. compositor.load_design) yeniden bölünmez
        f = part.astype(np.float32)
    else:
        f = part.astype(np.float32) / (65535.0 if part.dtype == np.uint16 else 255.0)
    if f.ndim == 2:
        f = f[..., None].repeat(3, 2)
    a = f[..., 3] if f.shape[2] == 4 else np.ones(f.shape[:2], np.float32)
    lum = 0.114 * f[..., 0] + 0.587 * f[..., 1] + 0.299 * f[..., 2]
    ink = (a > 0.1) & (lum < 0.85)
    return float(ink.mean())

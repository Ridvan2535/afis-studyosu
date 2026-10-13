# -*- coding: utf-8 -*-
"""
Dış servis bağlantıları: sahne görseli üretimi ve görselden videoya çevirme.

DURUM (dürüst özet):
  * Magnific uç noktaları (adres, anahtar başlığı, istek alanları, durum değerleri) Magnific'in kendi
    dokümanından okunarak yazıldı. Gerçek anahtarla HİÇ çalıştırılmadı.
  * OpenAI ve Gemini çağrıları, bu servislerin bilinen REST arayüzüne göre yazıldı; bu oturumda
    dokümanları okunmadı ve çalıştırılmadı. Model adları ayarlardan değiştirilebilir.
  * "mock" (sahte) sağlayıcı gerçek servis değildir; sadece akışı anahtarsız sınamak içindir.
  * Magnific'te görev sorgulama adresi, istek adresi + "/" + görev numarası olarak varsayıldı
    (Veo için doküman bunu doğruluyor, görsel uç noktası için doğrulanmadı).
İlk gerçek çalıştırmada bir hata çıkarsa "Hata raporu" düğmesiyle bana gönder.
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field, fields

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(HERE, "ayarlar.json")


class ProviderError(Exception):
    pass


class AuthError(ProviderError):
    """Anahtar reddedildi: tekrar denemenin anlamı yok."""


class QuotaError(AuthError):
    """Hesapta bakiye/kota yok ya da bu modele erişim kapalı: tekrar denemek boşuna (ama anahtar geçerli olabilir).
    account=True: sorun tüm hesapta (kredi bitti); başka modeli denemek de boşuna."""
    def __init__(self, msg, account=False):
        super().__init__(msg)
        self.account = account


_ACCOUNT_WIDE = ("credit_balance_exhausted", "no credits remaining", "insufficient_quota", "billing_hard_limit")


# ----------------------------------------------------------------------------
# Ayarlar (anahtarlar yalnızca bu bilgisayarda, ayarlar.json dosyasında durur)
# ----------------------------------------------------------------------------
@dataclass
class Settings:
    magnific_key: str = ""
    topview_key: str = ""
    topview_uid: str = ""
    openai_key: str = ""
    gemini_key: str = ""
    scene_provider: str = "auto"          # auto (anahtarı olanları dener, en iyisini seçer) | magnific | openai | gemini | mock
    video_provider: str = "auto"          # auto | veo-3-1 | veo-3-1-fast | kling-pro | runway-4-5 | mock
    openai_model: str = "auto"            # auto = servisten en yeni görsel modeli bulur
    gemini_model: str = "auto"
    video_resolution: str = "720p"        # veo: 720p | 1080p | 4k
    max_scene_calls: int = 14             # tek seferde en fazla kaç sahne üretimi çağrısı (maliyet tavanı)
    max_video_tries: int = 2              # video kalite kontrolünden geçmezse en fazla kaç deneme
    photo_long_side: int = 2400           # sahne bu uzun kenara büyütülür (0 = kapalı)
    seconds: int = 6
    video_mode: str = "kamera"            # kamera (sabit sahne + sanal kamera) | kompozit (YZ videosu + kodla baskı) | yapay_zeka (ham)
    camera_move: str = "yakinlas_saga"    # yakinlas | yakinlas_saga | yakinlas_sola | yakinlas_cok | saga | sola | uzaklas | hepsi
    handheld: str = "yuruyus"             # sabit | sakin | yuruyus | belirgin (kamera hareketi videosundaki el sallantısı)
    servis_surumu: int = 3                # 1: otomatik servis seçimi, 2: onaylanan video ayarı (yaklaşırken sağa dön)
    auto_video: bool = False              # her fotoğraf üretildiğinde onun için kamera videosu da otomatik üretilir (ücretsiz)
    auto_video_move: str = "yakinlas_saga"
    auto_video_kind: str = "canli"        # canli (YZ kamerayı yürütür, ücretli) | kamera (düz fotoğraf + sanal kamera, ücretsiz)
    ribbon_colors: list = field(default_factory=lambda: [
        {"ad": "Sarı", "hex": "#F2C230"}, {"ad": "Krem", "hex": "#F1E6D2"}, {"ad": "Pudra pembe", "hex": "#E8B4BC"},
        {"ad": "Adaçayı yeşili", "hex": "#9CAF88"}, {"ad": "Bebek mavisi", "hex": "#A9C7E8"}, {"ad": "Bordo", "hex": "#722F37"},
        {"ad": "Siyah", "hex": "#1E1E1E"}])      # kullanıcı Ayarlar'dan kendi renklerini ekler
    ribbon_default: str = "Sarı"          # fotoğraf ekranında varsayılan seçili kurdele rengi ("" = kurdelesiz)
    strict_layout: bool = True            # sahne: dik, karşıdan (yan açısız) ve yere kadar uzanan afiş şartı
    ornek_olcu: str = "75x200"            # ilan görsellerinde gösterilen örnek ölçü kimliği (product.OLCULER); satış ölçülerinden ayrı
    prompt_surumleri: dict = field(default_factory=dict)   # kategori -> prompt sürümü (prompt_yapisi.SURUMLER); boş = etkin "2A"
    ayni_hata_siniri: int = 5             # aynı hata art arda bu kadar tekrarlanırsa üretim durur (0 = kapalı); K-30
    olcum_kararlilik_testi: bool = True   # her sahne iki küçük bozulmayla yeniden ölçülür (ücretsiz); kararsız ret kesin sayılmaz; K-37
    kurtarma_etkin: bool = True           # şüpheli algılamada aynı ham görselde alternatif kumaş adayları (ücretsiz, yerel); K-49
    gorsel_kontrol_servisi: str = "kapali"   # kapali | claude — uygulamanın otomatik görsel kontrolü (ücretli; varsayılan kapalı)
    anthropic_key: str = ""               # yalnız gorsel_kontrol_servisi=claude iken kullanılır; arayüzde maskelenir
    gorsel_kontrol_modeli: str = "claude-sonnet-5-5"
    gorsel_kontrol_is_basina_en_fazla: int = 3
    gorsel_kontrol_gunluk_tavan_usd: float = 0.5
    supheli_olcumde_dur: bool = True      # algılama güveni düşük bir retten sonra otomatik yeni ücretli çağrı yapılmaz; K-36
    sonucsuz_siniri: int = 8              # son kabulden beri bu kadar çağrı sonuç vermezse (neden fark etmez) üretim durur (0 = kapalı); K-33

    @classmethod
    def load(cls) -> "Settings":
        data = {}
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        names = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in data.items() if k in names})
        if data and int(data.get("servis_surumu", 0)) < 1:             # eski ayar dosyası: otomatik seçime geç (sahte mod korunur)
            if s.scene_provider != "mock":
                s.scene_provider = "auto"
            if s.video_provider != "mock":
                s.video_provider = "auto"
            if s.openai_model == "gpt-image-1":
                s.openai_model = "auto"
            if s.gemini_model == "gemini-2.5-flash-image":
                s.gemini_model = "auto"
            s.servis_surumu = 1
        if data and int(data.get("servis_surumu", 0)) < 2:             # onaylanan video ayarı: yaklaşırken sağa dön, doğal el
            s.camera_move = "yakinlas_saga"
            s.handheld = "yuruyus"
            s.auto_video, s.auto_video_move = True, "yakinlas_saga"
            s.servis_surumu = 2
        if s.ornek_olcu not in ("50x100", "50x150", "75x200", "150x300", "150x400"):   # product.OLCULER ile aynı (döngüsel içe aktarma olmasın)
            s.ornek_olcu = "75x200"
        try:
            s.ayni_hata_siniri = max(0, min(int(s.ayni_hata_siniri), 50))
        except (TypeError, ValueError):
            s.ayni_hata_siniri = 5
        try:
            s.sonucsuz_siniri = max(0, min(int(s.sonucsuz_siniri), 60))
        except (TypeError, ValueError):
            s.sonucsuz_siniri = 8
        if not isinstance(s.prompt_surumleri, dict):
            s.prompt_surumleri = {}
        if data and int(data.get("servis_surumu", 0)) < 3:             # kullanıcı isteği: video ben "üret" demeden üretilmesin
            s.auto_video = False
            s.servis_surumu = 3
        for attr, env in (("magnific_key", "MAGNIFIC_API_KEY"), ("openai_key", "OPENAI_API_KEY"),
                          ("gemini_key", "GEMINI_API_KEY"),
                          ("topview_key", "TOPVIEW_API_KEY"), ("topview_uid", "TOPVIEW_UID")):
            if not getattr(s, attr) and os.environ.get(env):
                setattr(s, attr, os.environ[env])
        return s

    def save(self):
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_PATH)

    def keys(self):
        return [k for k in (self.magnific_key, self.openai_key, self.gemini_key, self.topview_key, self.anthropic_key) if k]

    def ribbon(self, name: str | None = None):
        """Seçili kurdele rengi -> {"ad","hex"} ya da None (kurdelesiz)."""
        name = self.ribbon_default if name is None else name
        for c in self.ribbon_colors or []:
            if c.get("ad") == name:
                return {"ad": c["ad"], "hex": c["hex"]}
        return None

    def public(self) -> dict:
        """Arayüze/rapora giden hali: anahtarlar maskelenir."""
        d = asdict(self)
        for k in ("magnific_key", "openai_key", "gemini_key", "topview_key", "anthropic_key"):
            d[k] = mask(d[k])
        return d


def mask(key: str) -> str:
    if not key:
        return ""
    return key[:3] + "…" + key[-3:] if len(key) > 10 else "••••"


def redact(text: str, keys) -> str:
    for k in keys:
        if k:
            text = text.replace(k, "***")
    return text


# ----------------------------------------------------------------------------
# HTTP yardımcıları
# ----------------------------------------------------------------------------
def _body_msg(r) -> str:
    """Servisin hata gövdesinden kısa, okunur bir ileti çıkarır (anahtarlar zaten gövdede olmaz)."""
    try:
        j = r.json()
        err = j.get("error", j)
        if isinstance(err, dict):
            msg = err.get("message") or err.get("detail") or err.get("status") or json.dumps(err, ensure_ascii=False)
            code = err.get("code") or err.get("type") or ""
            return (f"{code}: " if code and str(code) not in str(msg) else "") + str(msg)
        return str(err)
    except ValueError:
        return (r.text or "").strip().replace("\n", " ")


_QUOTA_STRONG = ("insufficient_quota", "limit: 0", "billing_hard_limit", "must be verified", "verify organization",
                 "free tier", "payment required")
_QUOTA_WEAK = ("exceeded your current quota", "check your plan", "billing", "credit", "not enough", "insufficient")
_RATE_MARKERS = ("retry in", "retrydelay", "try again in", "rate limit", "too many requests", "requests per", "per minute")
_QUOTA_HINTS = _QUOTA_STRONG + _QUOTA_WEAK


def _is_quota(body: str) -> bool:
    b = body.lower()
    if any(h in b for h in _QUOTA_STRONG):
        return True
    if any(h in b for h in _RATE_MARKERS):             # kısa süreli hız sınırı: beklenir
        return False
    return any(h in b for h in _QUOTA_WEAK)


def _http(method, url, *, headers=None, tries=3, timeout=60, **kw):
    last = None
    for i in range(tries):
        try:
            r = requests.request(method, url, headers=headers, timeout=timeout, **kw)
        except requests.RequestException as e:
            last = ProviderError(f"Bağlantı hatası ({e.__class__.__name__}). İnternet bağlantını kontrol et.")
            time.sleep(2 * (i + 1))
            continue
        if r.status_code in (401, 403):
            body = _body_msg(r)
            if r.status_code == 403 and any(h in body.lower() for h in _QUOTA_HINTS):
                raise QuotaError(f"Bu modele erişim kapalı (HTTP 403): {body[:240]}")
            raise AuthError(f"Anahtar reddedildi (HTTP {r.status_code}). Anahtarı ve hesap bakiyesini kontrol et. {body[:200]}".strip())
        if r.status_code in (402,):
            raise QuotaError(f"Bakiye yetersiz (HTTP 402): {_body_msg(r)[:240]}")
        if r.status_code == 429:
            body = _body_msg(r)
            if _is_quota(body):                                           # kota/bakiye bitmiş: beklemek işe yaramaz
                raise QuotaError(f"Kota ya da bakiye yok (HTTP 429): {body[:240]}",
                                 account=any(h in body.lower() for h in _ACCOUNT_WIDE))
            last = ProviderError(f"Servis meşgul ya da hız sınırında (HTTP 429): {body[:240]}")
            time.sleep(min(30, 3 * (2 ** i)))
            continue
        if r.status_code in (500, 502, 503, 504):
            last = ProviderError(f"Servis hata verdi (HTTP {r.status_code}): {_body_msg(r)[:200]}")
            time.sleep(min(30, 3 * (2 ** i)))
            continue
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}: {_body_msg(r)[:300]}")
        return r
    raise last or ProviderError("Bilinmeyen bağlantı hatası")


def _nearest(ratio, table):
    return min(table, key=lambda kv: abs(math.log(ratio / kv[1])))[0]


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _data_uri(data: bytes) -> str:
    mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ("image/webp" if data[:4] == b"RIFF" else "image/jpeg")
    return f"data:{mime};base64,{_b64(data)}"


def _download(url: str) -> bytes:
    return _http("GET", url, timeout=300).content


# ----------------------------------------------------------------------------
# Model keşfi: "auto" seçiliyse servisin kendi model listesinden en yeni görsel modeli bul (yeni model çıkınca kod
# değişmesin). Liste alınamazsa bilinen varsayılan kullanılır. Sonuç süreç boyunca saklanır.
# ----------------------------------------------------------------------------
_MODEL_CACHE: dict = {}
OPENAI_DEFAULT, GEMINI_DEFAULT = "gpt-image-1", "gemini-2.5-flash-image"


def rank_openai_models(ids) -> list:
    """gpt-image-N modelleri, en yeni önce (-mini ve tarihli sürümler dışarıda)."""
    found = []
    for i in ids:
        m = re.fullmatch(r"gpt-image-(\d+(?:\.\d+)?)", str(i))
        if m:
            found.append((float(m.group(1)), str(i)))
    out = [n for _, n in sorted(set(found), reverse=True)]
    return out or [OPENAI_DEFAULT]


def pick_openai_model(ids) -> str:
    return rank_openai_models(ids)[0]


def rank_gemini_models(models) -> list:
    """models: [{'name': 'models/...', 'supportedGenerationMethods': [...]}]. Sıra: pro > flash > lite, sonra en yeni sürüm,
    sonra kararlı > önizleme. İlk model çalışmazsa (kota/erişim) sıradaki denenir."""
    cands = []
    for m in models:
        name = str(m.get("name", "")).split("/")[-1]
        if "image" not in name or "imagen" in name or "generateContent" not in (m.get("supportedGenerationMethods") or ["generateContent"]):
            continue
        v = re.search(r"(\d+(?:\.\d+)?)", name)
        tier = 2 if "pro" in name else (0 if "lite" in name else 1)
        cands.append((tier, float(v.group(1)) if v else 0.0, 0 if re.search(r"preview|exp", name) else 1, name))
    out = [c[3] for c in sorted(set(cands), reverse=True)]
    return out or [GEMINI_DEFAULT]


def pick_gemini_model(models) -> str:
    return rank_gemini_models(models)[0]


def resolve_models(kind, key, configured, log=print) -> list:
    """Kullanılacak model sırası. Elle yazılmışsa yalnızca o; 'auto' ise servisin model listesinden en iyiden başlayarak."""
    if configured and configured != "auto":
        return [configured]
    ck = (kind, key[-6:] if key else "")
    if ck in _MODEL_CACHE:
        return list(_MODEL_CACHE[ck])
    chosen = [OPENAI_DEFAULT] if kind == "openai" else [GEMINI_DEFAULT]
    try:
        if kind == "openai":
            r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
            if r.status_code == 200:
                chosen = rank_openai_models([m.get("id") for m in r.json().get("data", [])])
        else:
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key},
                             params={"pageSize": 200}, timeout=30)
            if r.status_code == 200:
                chosen = rank_gemini_models(r.json().get("models", []))
    except (requests.RequestException, ValueError):
        pass
    _MODEL_CACHE[ck] = chosen
    log(f"{'OpenAI' if kind == 'openai' else 'Gemini'} görsel modelleri otomatik seçildi (sırayla denenir): {', '.join(chosen[:3])}")
    return list(chosen)


def resolve_model(kind, key, configured, log=print) -> str:
    return resolve_models(kind, key, configured, log)[0]


def _try_models(models, call, log, label):
    """Modelleri sırayla dener: kota/erişim/bulunamadı hatasında sıradakine geçer, başka hatada durur."""
    last = None
    for i, m in enumerate(models[:3]):
        try:
            return call(m)
        except QuotaError as e:
            if e.account:                                   # kredi bitmiş: başka model de çalışmaz
                raise
            last = e
        except AuthError:
            raise
        except ProviderError as e:
            if not re.search(r"HTTP (400|404)", str(e)):
                raise
            last = e
        if i + 1 < len(models[:3]):
            log(f"{label} {m} kullanılamadı ({str(last)[:120]}); sıradaki model deneniyor.")
    raise last


# ----------------------------------------------------------------------------
# Magnific (eski adıyla Freepik) API
# ----------------------------------------------------------------------------
class Magnific:
    BASE = "https://api.magnific.com"
    ASPECTS = [("social_story_9_16", 9 / 16), ("portrait_2_3", 2 / 3), ("traditional_3_4", 3 / 4),
               ("square_1_1", 1.0), ("classic_4_3", 4 / 3), ("standard_3_2", 3 / 2), ("widescreen_16_9", 16 / 9)]
    NEG = ("distorted or warped letters, extra text, morphing, flicker, fast motion, sudden cuts, "
           "blur, deformed fabric, people, hands")
    NEG_LIVE = ("text, letters, logo, print or pattern on the banner, banner changing shape or size, morphing, flicker, sudden cuts, "
                "fast zoom, slow motion, warped frame posts, duplicated objects, person in front of the banner, hands on the banner, "
                "close-up faces, distorted faces, extra limbs, cartoon, CGI look")
    NEG_STATIC = ("camera movement, camera shake, zoom, pan, tilt, handheld, text, letters, logo, print on the banner, "
                  "morphing, flicker, sudden cuts, warping fabric, person in front of the banner, people touching the banner, "
                  "hands on the banner, close-up faces, distorted faces, extra limbs")

    def __init__(self, key, log=print, poll_every=4.0, max_wait=900):
        if not key:
            raise AuthError("Magnific anahtarı girilmemiş (Ayarlar sekmesi).")
        self.key, self.log, self.poll_every, self.max_wait = key, log, poll_every, max_wait

    def _h(self):
        return {"x-magnific-api-key": self.key, "Content-Type": "application/json", "Accept": "application/json"}

    def _run(self, path, body):
        r = _http("POST", self.BASE + path, headers=self._h(), json=body, timeout=180)
        j = r.json()
        data = j.get("data", j)
        tid = data.get("task_id")
        if not tid:
            raise ProviderError(f"Magnific beklenmeyen yanıt verdi: {str(j)[:200]}")
        self.log(f"Magnific görevi başladı ({path.split('/')[-1]}), bekleniyor…")
        t0 = time.time()
        spath = path
        while True:
            if time.time() - t0 > self.max_wait:
                raise ProviderError("Magnific görevi zaman aşımına uğradı.")
            time.sleep(self.poll_every)
            try:
                g = _http("GET", f"{self.BASE}{spath}/{tid}", headers=self._h(), timeout=60).json()
            except ProviderError as e:
                alt = spath[:-4] if spath.endswith("-pro") else None     # örn. kling-v2-6-pro -> kling-v2-6 (sorgu adresi dokümanda yok)
                if "404" in str(e) and alt:
                    self.log(f"Sorgu adresi {spath} bulunamadı, {alt} deneniyor.")
                    spath = alt
                    continue
                raise
            d = g.get("data", g)
            st = str(d.get("status", "")).upper()
            if st == "COMPLETED":
                urls = d.get("generated") or []
                if not urls:
                    raise ProviderError("Görev tamamlandı ama çıktı adresi yok.")
                return urls
            if st == "FAILED":
                detail = d.get("error") or d.get("message") or d.get("detail") or d.get("reason") or ""
                if not detail:
                    extra = {k: v for k, v in d.items() if k not in ("generated", "task_id", "status")}
                    detail = json.dumps(extra, ensure_ascii=False)[:200] if extra else ""
                raise ProviderError("Magnific görevi başarısız oldu (içerik filtresi ya da servis hatası olabilir)."
                                    + (f" Servisin mesajı: {str(detail)[:300]}" if detail else ""))

    # -- sahne ---------------------------------------------------------------
    supports_guide = False

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        if refs and not getattr(self, "_warned_refs", False):
            self._warned_refs = True
            self.log("Uyarı: Seedream uç noktası referans görsel almıyor; referanslar bu sağlayıcıda kullanılmadı.")
        body = {"prompt": prompt[:4000], "aspect_ratio": _nearest(aw / ah, self.ASPECTS)}
        if seed is not None:
            body["seed"] = int(seed)
        urls = self._run("/v1/ai/text-to-image/seedream-v4-5", body)
        return _download(urls[0])

    # -- video ---------------------------------------------------------------
    def video(self, image_jpg: bytes, prompt, seconds=6, seed=None, model="veo-3-1", resolution="720p",
              negative=None) -> bytes:
        neg = negative or self.NEG
        if model.startswith("veo"):
            dur = min((4, 6, 8), key=lambda d: abs(d - seconds))
            body = {"image": _b64(image_jpg), "prompt": prompt[:19000], "negative_prompt": neg,
                    "duration": dur, "resolution": resolution, "aspect_ratio": "9:16", "generate_audio": False}
        elif model == "kling-pro":
            dur = "5" if seconds <= 7 else "10"
            body = {"image": _b64(image_jpg), "prompt": prompt[:2400], "negative_prompt": neg[:2400],
                    "duration": dur, "cfg_scale": 0.6, "aspect_ratio": "social_story_9_16"}
            model = "kling-v2-6-pro"                       # eski "kling-pro" adresi 404 verdi; resmi dokümandaki ad
        elif model == "runway-4-5":                       # resmi dokümandan; henüz gerçek anahtarla denenmedi
            dur = min((5, 8, 10), key=lambda d: abs(d - seconds))
            body = {"image": _b64(image_jpg), "prompt": prompt[:2000], "ratio": "720:1280", "duration": dur}
            if seed is not None:
                body["seed"] = int(seed) % 4294967295
            urls = self._run("/v1/ai/image-to-video/runway-4-5", body)
            return _download(urls[0])
        else:
            raise ProviderError(f"Bilinmeyen video modeli: {model}")
        if seed is not None and model.startswith("veo"):
            body["seed"] = int(seed)
        urls = self._run(f"/v1/ai/image-to-video/{model}", body)
        return _download(urls[0])

    def check(self):
        r = requests.get(self.BASE + "/v1/resources", headers=self._h(), params={"limit": 1}, timeout=30)
        return r.status_code


# ----------------------------------------------------------------------------
# Magnific "Seedream Edit": referans görselli sahne üretimi (kılavuz görsel + isteğe bağlı sahne referansları).
# Resmi dokümandan: POST /v1/ai/text-to-image/seedream-v4-5-edit  (reference_images 1-5, aspect_ratio, seed).
# Görev sorgulama adresi diğer Magnific uç noktalarındaki gibi "<uç nokta>/<görev no>" varsayıldı; gerçek anahtarla denenmedi.
# ----------------------------------------------------------------------------
class MagnificEdit(Magnific):
    supports_guide = True
    ENDPOINTS = {"magnific-edit": ("seedream-v4-5-edit", 5), "magnific-edit-pro": ("seedream-v5-pro-edit", 10)}

    def __init__(self, key, log=print, variant="magnific-edit", **kw):
        super().__init__(key, log, **kw)
        self.model, self.max_refs = self.ENDPOINTS[variant]

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        imgs = ([guide] if guide else []) + list(refs or [])
        imgs = imgs[:min(self.max_refs, 5)]
        if not imgs:
            raise ProviderError("Seedream Edit en az bir referans görsel ister (iç hata: kılavuz görsel yok).")
        if self.model.startswith("seedream-v5"):          # 5 Pro: "invalid url" hatası verdi -> data URI biçimi (gerçek anahtarla denenecek)
            enc = [_data_uri(b) for b in imgs]
        else:
            enc = [_b64(b) for b in imgs]
        body = {"prompt": prompt[:4000], "reference_images": enc,
                "aspect_ratio": _nearest(aw / ah, self.ASPECTS)}
        if seed is not None:
            body["seed"] = int(seed) % 4294967295
        urls = self._run(f"/v1/ai/text-to-image/{self.model}", body)
        return _download(urls[0])


# ----------------------------------------------------------------------------
# OpenAI görseller
# ----------------------------------------------------------------------------
class OpenAIImages:
    BASE = "https://api.openai.com/v1"

    def __init__(self, key, model="gpt-image-1", log=print):
        if not key:
            raise AuthError("OpenAI anahtarı girilmemiş (Ayarlar sekmesi).")
        self.key, self.log = key, log
        self.models = resolve_models("openai", key, model, log)
        self.model = self.models[0]

    supports_guide = True

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        size = "1024x1536" if ah > aw * 1.1 else ("1536x1024" if aw > ah * 1.1 else "1024x1024")
        auth = {"Authorization": f"Bearer {self.key}"}
        images = ([guide] if guide else []) + list(refs or [])[:4]

        def call(model):
            if images:
                files = [("image[]", (f"gorsel{i}.png", b, "image/png")) for i, b in enumerate(images)]
                return _http("POST", f"{self.BASE}/images/edits", headers=auth, timeout=400,
                             data={"model": model, "prompt": prompt, "size": size, "quality": "high"}, files=files)
            return _http("POST", f"{self.BASE}/images/generations", headers={**auth, "Content-Type": "application/json"},
                         timeout=400, json={"model": model, "prompt": prompt, "size": size, "quality": "high", "n": 1})

        r = _try_models(self.models, call, self.log, "OpenAI")
        d = r.json()["data"][0]
        if d.get("b64_json"):
            return base64.b64decode(d["b64_json"])
        if d.get("url"):
            return _download(d["url"])
        raise ProviderError("OpenAI yanıtında görsel yok.")

    def check(self):
        return requests.get(f"{self.BASE}/models", headers={"Authorization": f"Bearer {self.key}"}, timeout=30).status_code


# ----------------------------------------------------------------------------
# Gemini görseller
# ----------------------------------------------------------------------------
class GeminiImages:
    BASE = "https://generativelanguage.googleapis.com/v1beta"
    ASPECTS = [("9:16", 9 / 16), ("2:3", 2 / 3), ("3:4", 3 / 4), ("4:5", 4 / 5), ("1:1", 1.0),
               ("5:4", 5 / 4), ("4:3", 4 / 3), ("3:2", 3 / 2), ("16:9", 16 / 9)]

    def __init__(self, key, model="gemini-2.5-flash-image", log=print):
        if not key:
            raise AuthError("Gemini anahtarı girilmemiş (Ayarlar sekmesi).")
        self.key, self.log = key, log
        self.models = resolve_models("gemini", key, model, log)
        self.model = self.models[0]

    supports_guide = True

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        parts = [{"text": prompt}]
        if guide:
            parts.append({"inline_data": {"mime_type": "image/png", "data": _b64(guide)}})
        for b in (refs or [])[:3]:
            parts.append({"inline_data": {"mime_type": "image/png", "data": _b64(b)}})
        cfg = {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": _nearest(aw / ah, self.ASPECTS)}}
        h = {"x-goog-api-key": self.key, "Content-Type": "application/json"}

        def call(model):
            url = f"{self.BASE}/models/{model}:generateContent"
            try:
                return _http("POST", url, headers=h, timeout=300, json={"contents": [{"parts": parts}], "generationConfig": cfg})
            except QuotaError:
                raise
            except ProviderError as e:
                if "HTTP 400" not in str(e) or "imageConfig" not in cfg:
                    raise
                cfg2 = {k: v for k, v in cfg.items() if k != "imageConfig"}     # model en-boy ayarını tanımıyorsa onsuz dene
                return _http("POST", url, headers=h, timeout=300, json={"contents": [{"parts": parts}], "generationConfig": cfg2})

        r = _try_models(self.models, call, self.log, "Gemini")
        for cand in r.json().get("candidates", []):
            for p in cand.get("content", {}).get("parts", []):
                inl = p.get("inlineData") or p.get("inline_data")
                if inl and inl.get("data"):
                    return base64.b64decode(inl["data"])
        raise ProviderError("Gemini yanıtında görsel yok (içerik filtresi olabilir).")

    def check(self):
        return requests.get(f"{self.BASE}/models", headers={"x-goog-api-key": self.key}, timeout=30).status_code


# ----------------------------------------------------------------------------
# Fabrika
# ----------------------------------------------------------------------------
class SceneProvider:
    def __init__(self, impl):
        self.impl = impl

    @property
    def supports_guide(self) -> bool:
        return bool(getattr(self.impl, "supports_guide", False))

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None) -> bytes:
        if self.supports_guide:
            return self.impl.scene(prompt, aw, ah, refs or [], seed, guide)
        return self.impl.scene(prompt, aw, ah, refs or [], seed)


# ----------------------------------------------------------------------------
# TopView: tek hesaptan birçok video modeli (Kling, Veo, Seedance ...). Resmi dokümandan yazıldı
# (docs.topview.ai): başlıklar "Authorization: Bearer <anahtar>" + "Topview-Uid: <kullanıcı no>".
# Akış: GET /v1/upload/credential -> PUT dosya -> GET /v1/upload/check -> POST /v2/common_task/image2video/task/submit
# -> GET .../query?taskId=... (status: init/running/success/fail, result.videos[0].filePath). Gerçek anahtarla DENENMEDİ.
# ----------------------------------------------------------------------------
class TopViewVideo:
    BASE = "https://api.topview.ai"
    MODELS = {                                   # arm adı -> (TopView model adı, geçerli süreler, çözünürlük)
        "tv-kling": ("Kling 3.0 Turbo", (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), 720),
        "tv-veo": ("Veo 3.1", (4, 6, 8), 720),
        "tv-seedance": ("Seedance 2.5", tuple(range(4, 31)), 720),
    }
    NEG = Magnific.NEG_STATIC

    def __init__(self, key, uid, log=print, poll_every=5.0, max_wait=900):
        if not key or not uid:
            raise AuthError("TopView anahtarı ya da kullanıcı numarası girilmemiş (Ayarlar sekmesi).")
        self.key, self.uid, self.log, self.poll_every, self.max_wait = key, uid, log, poll_every, max_wait

    def _h(self):
        return {"Authorization": f"Bearer {self.key}", "Topview-Uid": self.uid, "Accept": "application/json"}

    def _json(self, r):
        j = r.json()
        if str(j.get("code")) != "200":
            raise ProviderError(f"TopView hata verdi: {str(j.get('message') or j)[:240]}")
        return j.get("result") or {}

    def _upload(self, jpg: bytes) -> str:
        res = self._json(_http("GET", self.BASE + "/v1/upload/credential", headers=self._h(), params={"format": "jpg"}, timeout=60))
        put = requests.put(res["uploadUrl"], data=jpg, timeout=300)
        if put.status_code >= 300:
            raise ProviderError(f"TopView görsel yüklemesi başarısız (HTTP {put.status_code}).")
        chk = self._json(_http("GET", self.BASE + "/v1/upload/check", headers=self._h(), params={"fileId": res["fileId"]}, timeout=60))
        if str(chk).lower() not in ("true", "{}") and chk not in (True,):
            self.log(f"TopView yükleme denetimi: {chk}")
        return res["fileId"]

    def video(self, image_jpg: bytes, prompt, seconds=6, seed=None, arm="tv-kling", negative=None) -> bytes:
        name, durs, res = self.MODELS[arm]
        dur = min(durs, key=lambda d: abs(d - seconds))
        fid = self._upload(image_jpg)
        body = {"model": name, "firstFrameFileId": fid, "prompt": (prompt + " Avoid: " + (negative or self.NEG))[:2000],
                "resolution": res, "duration": dur, "generatingCount": 1}
        r = self._json(_http("POST", self.BASE + "/v2/common_task/image2video/task/submit", headers=self._h(), json=body, timeout=120))
        tid = r.get("taskId")
        if not tid:
            raise ProviderError(f"TopView beklenmeyen yanıt verdi: {str(r)[:200]}")
        self.log(f"TopView görevi başladı ({name}), bekleniyor…")
        t0 = time.time()
        while True:
            if time.time() - t0 > self.max_wait:
                raise ProviderError("TopView görevi zaman aşımına uğradı.")
            time.sleep(self.poll_every)
            q = self._json(_http("GET", self.BASE + "/v2/common_task/image2video/task/query", headers=self._h(), params={"taskId": tid}, timeout=60))
            st = q.get("status")
            if st == "success":
                vids = q.get("videos") or []
                url = (vids[0] or {}).get("filePath") if vids else None
                if not url:
                    raise ProviderError("TopView video adresi vermedi.")
                return _download(url)
            if st == "fail":
                raise ProviderError(f"TopView üretemedi: {q.get('errorMsg') or 'bilinmeyen neden'}")


class VideoProvider:
    def __init__(self, impl, model, resolution="720p"):
        self.impl, self.model, self.resolution = impl, model, resolution

    def video(self, image_jpg: bytes, prompt, seconds=6, seed=None, negative=None) -> bytes:
        if isinstance(self.impl, Magnific):
            return self.impl.video(image_jpg, prompt, seconds, seed, self.model, self.resolution, negative=negative)
        if isinstance(self.impl, TopViewVideo):
            return self.impl.video(image_jpg, prompt, seconds, seed, arm=self.model, negative=negative)
        return self.impl.video(image_jpg, prompt, seconds, seed)


SCENE_ORDER = ("openai", "gemini", "magnific-edit", "magnific-edit-pro", "magnific")   # kılavuz görsel alanlar önce denenir
VIDEO_ORDER = ("veo-3-1", "kling-pro")          # Runway: "400 Validation error" verdi, doğrulanana kadar otomatik listede yok
TOPVIEW_ORDER = ("tv-kling", "tv-veo", "tv-seedance")


def available_scene(s: Settings) -> list:
    """Otomatik modda denenecek sahne servisleri (anahtarı girilmiş olanlar)."""
    have = {"openai": s.openai_key, "gemini": s.gemini_key, "magnific": s.magnific_key,
            "magnific-edit": s.magnific_key, "magnific-edit-pro": s.magnific_key}
    return [n for n in SCENE_ORDER if have[n]]


def available_video(s: Settings) -> list:
    return (list(VIDEO_ORDER) if s.magnific_key else []) + (list(TOPVIEW_ORDER) if (s.topview_key and s.topview_uid) else [])


def scene_arms(s: Settings) -> list:
    """Bu çalıştırmada yarışacak sahne servisleri. Elle seçildiyse yalnızca o."""
    if s.scene_provider == "auto":
        return available_scene(s)
    return [s.scene_provider]


def video_arms(s: Settings) -> list:
    if s.video_provider == "auto":
        return available_video(s)
    return [s.video_provider]


def make_scene_provider(s: Settings, log=print, name=None) -> SceneProvider:
    p = name or s.scene_provider
    if p == "auto":
        raise ProviderError("Otomatik modda servis adı verilmeli (iç hata).")
    if p == "magnific":
        return SceneProvider(Magnific(s.magnific_key, log))
    if p in MagnificEdit.ENDPOINTS:
        return SceneProvider(MagnificEdit(s.magnific_key, log, variant=p))
    if p == "openai":
        return SceneProvider(OpenAIImages(s.openai_key, s.openai_model, log))
    if p == "gemini":
        return SceneProvider(GeminiImages(s.gemini_key, s.gemini_model, log))
    if p in ("mock", "mock_bad", "mock_err", "mock_thin", "mock_pool", "mock_air", "mock_long", "mock_touch"):
        from mock_provider import MockScenes
        return SceneProvider(MockScenes(variant=p))
    raise ProviderError(f"Bilinmeyen sahne sağlayıcısı: {p}")


def make_video_provider(s: Settings, log=print, name=None) -> VideoProvider:
    p = name or s.video_provider
    if p == "auto":
        raise ProviderError("Otomatik modda servis adı verilmeli (iç hata).")
    if p in ("veo-3-1", "veo-3-1-fast", "kling-pro", "runway-4-5"):
        return VideoProvider(Magnific(s.magnific_key, log), p, s.video_resolution)
    if p in TopViewVideo.MODELS:
        return VideoProvider(TopViewVideo(s.topview_key, s.topview_uid, log), p)
    if p in ("mock", "mock_vbad"):
        from mock_provider import MockVideo
        return VideoProvider(MockVideo(bad=(p == "mock_vbad")), "mock")
    raise ProviderError(f"Bilinmeyen video sağlayıcısı: {p}")


def check_key(name: str, s: Settings) -> str:
    """Kredi harcamadan anahtarı denemek için en ucuz çağrı. Sonucu Türkçe cümle olarak döndürür."""
    try:
        if name in ("magnific", "magnific-edit", "magnific-edit-pro"):
            code = Magnific(s.magnific_key).check()
        elif name in ("topview", "topview_uid"):
            tv = TopViewVideo(s.topview_key, s.topview_uid)
            r = requests.get(tv.BASE + "/v1/upload/credential", headers=tv._h(), params={"format": "jpg"}, timeout=30)
            code = r.status_code if r.status_code != 200 else (200 if str(r.json().get("code")) == "200" else 403)
        elif name == "openai":
            code = OpenAIImages(s.openai_key).check()
        elif name == "gemini":
            code = GeminiImages(s.gemini_key).check()
        else:
            return "Bilinmeyen servis"
    except AuthError as e:
        return str(e)
    except requests.RequestException as e:
        return f"Bağlantı kurulamadı ({e.__class__.__name__})"
    if code == 200:
        return "Anahtar çalışıyor."
    if code in (401, 403):
        return f"Anahtar reddedildi (HTTP {code})."
    return f"Belirsiz yanıt (HTTP {code}); gerçek üretimde denenmeli."

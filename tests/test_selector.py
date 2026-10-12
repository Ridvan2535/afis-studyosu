"""Servis seçicisi (Selector) birim sınaması: tohumlu, ağsız, hızlı. Çalıştır: python tests/test_selector.py"""
import json
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import selector as S                      # noqa: E402
import providers as P                     # noqa: E402

logs = []
tmp = tempfile.mkdtemp(prefix="afis_sel_")
path = os.path.join(tmp, "karne.json")

# 1) hiç denenmemiş servis önce, listedeki sıra öncelik
sel = S.Selector("scene", ["a", "b", "c"], path, rng=random.Random(1), log=logs.append)
assert sel.pick() == "a"
sel.record("a", True, 80)
assert sel.pick() == "b"
sel.record("b", False)
assert sel.pick() == "c"
sel.record("c", False, error=True)

# 2) başarılı servis zamanla çoğunlukla seçilir; kötüler tamamen dışlanmaz
for _ in range(10):
    sel.record("a", True, 85)
cnt = {"a": 0, "b": 0, "c": 0}
for _ in range(400):
    cnt[sel.pick()] += 1
print("seçim sayıları:", cnt)
assert cnt["a"] > 330                              # iyi servis baskın (tek sayımla P(a)~0.90 -> ~358/400; eski 380 eşiği çift sayımın ~0.98'ine dayanıyordu)
# keşif payı: şanssız ilk sonucu olan servis tamamen unutulmaz
sel.explore = 0.1
cnt = {"a": 0, "b": 0, "c": 0}
for _ in range(400):
    cnt[sel.pick()] += 1
print("keşifli seçim sayıları:", cnt)
assert cnt["b"] + cnt["c"] > 10 and cnt["a"] > 300
sel.explore = 0.0

# 3) exclude
assert sel.pick(exclude=["a", "b"]) == "c"
assert sel.pick(exclude=["a", "b", "c"]) is None

# 4) üst üste 3 hata -> devre dışı; iş sürer
sel2 = S.Selector("scene", ["x", "y"], None, rng=random.Random(2), log=logs.append)
for _ in range(3):
    sel2.record("x", False, error=True)
assert "x" in sel2.off and sel2.active() == ["y"]
assert all(sel2.pick() == "y" for _ in range(20))
# araya başarı girerse sayaç sıfırlanır
sel3 = S.Selector("scene", ["x"], None, rng=random.Random(3), log=logs.append)
sel3.record("x", False, error=True); sel3.record("x", False, error=True); sel3.record("x", True, 70); sel3.record("x", False, error=True)
assert not sel3.off

# 5) kalıcılık: kaydet -> yeni Selector geçmişi okur; sürüm değişince sıfırlanır
sel.save()
again = S.Selector("scene", ["a", "b", "c"], path, rng=random.Random(4), log=logs.append)
assert again.hist["a"]["ok"] == 11 and again.hist["c"]["err"] == 1
assert again.pick() == "a" or again.pick() in ("a", "b", "c")          # tümü denenmiş: Thompson
# video türü ayrı tutulur
v = S.Selector("video", ["veo-3-1", "kling-pro"], path, rng=random.Random(5), log=logs.append)
v.record("veo-3-1", True, 90)
v.save()
data = json.load(open(path, encoding="utf-8"))
assert set(data["kinds"]) == {"scene", "video"}, data.keys()
ov = S.overview(path)
assert ov["scene"][0]["servis"] == "a" and ov["video"][0]["servis"] == "veo-3-1"
data["version"] = "eski"
json.dump(data, open(path, "w", encoding="utf-8"))
fresh = S.Selector("scene", ["a"], path, rng=random.Random(6), log=logs.append)
assert fresh.hist["a"]["calls"] == 0 and S.overview(path) == {"scene": [], "video": []}
# bozuk dosya sorun çıkarmaz
open(path, "w").write("{bozuk")
S.Selector("scene", ["a"], path, log=logs.append).save()

# 6) kazanan: önce kabul oranı, sonra kalite
w = S.Selector("scene", ["p", "q"], None, rng=random.Random(7), log=logs.append)
for _ in range(4): w.record("p", True, 70)
for _ in range(4): w.record("q", True, 90)
assert w.winner() == "q"
w.record("q", False)
assert w.winner() == "q"          # q: 4/5 kabul x 90 = 0.72 > p: 1.0 x 70 = 0.70
w.record("q", False)
assert w.winner() == "p"          # q: 4/6 x 90 = 0.60 < 0.70
assert S.Selector("scene", ["p"], None).winner() is None

# 6b) regresyon: bu işteki sonuçlar seçim hesabında iki kez sayılmamalı (hist zaten "kalıcı + bu iş" toplamı)
class _SpyRng(random.Random):
    """betavariate'e geçen (alpha, beta) parametrelerini kaydeder; değer olarak sabit 0.5 döner."""
    def __init__(self):
        super().__init__(0)
        self.beta_args = []

    def betavariate(self, alpha, beta):
        self.beta_args.append((alpha, beta))
        return 0.5


def _close(p, q):
    return all(abs(x - y) < 1e-9 for x, y in zip(p, q))


# kalıcı geçmişi olmayan iş: bir kayıttan sonra parametreler hist sayımına eşit
spy = _SpyRng()
r1 = S.Selector("scene", ["a"], None, rng=spy, log=logs.append, persist=False)
r1.record("a", True, 80)
assert r1._calls("a") == 1 == r1.hist["a"]["calls"], r1._calls("a")
assert r1.pick() == "a" and len(spy.beta_args) == 1
assert _close(spy.beta_args[0], (1 + 0.8, 1 + 0.2)), spy.beta_args          # çift sayımla (1+1.6, 1+0.4) olurdu

# kalıcı karnede 2 çağrı + bu işte 1 çağrı -> toplam 3 (4 değil)
path2 = os.path.join(tmp, "karne2.json")
json.dump({"version": S.SELECTOR_VERSION,
           "kinds": {"scene": {"a": {"calls": 2, "ok": 2, "err": 0, "qual": 160.0},
                               "b": {"calls": 1, "ok": 0, "err": 0, "qual": 0.0}}}},
          open(path2, "w", encoding="utf-8"))
spy = _SpyRng()
r2 = S.Selector("scene", ["a", "b"], path2, rng=spy, log=logs.append)
r2.record("a", True, 90)
assert r2._calls("a") == 3 and r2._calls("b") == 1, (r2._calls("a"), r2._calls("b"))
assert r2.run["a"]["calls"] == 1 and r2.hist["a"]["calls"] == 3              # rapor için run ayrı kalır
r2.pick()
pa, pb = spy.beta_args                                                        # isim sırası: a, b
# a: calls=3, ödül=min(250/100, 3)=2.5 -> (1+2.5, 1+0.5); çift sayımla calls=4, ödül=3.4 -> (4.4, 1.6) olurdu
assert _close(pa, (3.5, 1.5)), pa
assert _close(pb, (1.0, 2.0)), pb                                             # b bu işte kayıtsız: yalnız kalıcı geçmiş
r2.save()
assert json.load(open(path2, encoding="utf-8"))["kinds"]["scene"]["a"]["calls"] == 3   # dosyada da 3

# keşif dalı da tek sayımla karar vermeli: a kalıcı 5 / bu iş 0, b kalıcı 2 / bu iş 2 -> en az denenen b (4 < 5)
# (çift sayımla b = 2 + 2*2 = 6 > 5 olur ve a seçilirdi)
path3 = os.path.join(tmp, "karne3.json")
json.dump({"version": S.SELECTOR_VERSION,
           "kinds": {"scene": {"a": {"calls": 5, "ok": 5, "err": 0, "qual": 400.0},
                               "b": {"calls": 2, "ok": 1, "err": 0, "qual": 70.0}}}},
          open(path3, "w", encoding="utf-8"))
r3 = S.Selector("scene", ["a", "b"], path3, rng=random.Random(8), log=logs.append, explore=1.0)
r3.record("b", False); r3.record("b", True, 75)
assert r3._calls("a") == 5 and r3._calls("b") == 4, (r3._calls("a"), r3._calls("b"))
assert r3.pick() == "b"

# 7) model keşfi ayrıştırma
assert P.pick_openai_model(["gpt-4o", "gpt-image-1", "gpt-image-1-mini", "gpt-image-2", "dall-e-3", "gpt-image-1.5"]) == "gpt-image-2"
assert P.pick_openai_model(["gpt-4o"]) == P.OPENAI_DEFAULT
models = [{"name": "models/gemini-2.5-flash-image", "supportedGenerationMethods": ["generateContent"]},
          {"name": "models/gemini-3-pro-image-preview", "supportedGenerationMethods": ["generateContent"]},
          {"name": "models/imagen-4.0-generate-001", "supportedGenerationMethods": ["predict"]},
          {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]}]
assert P.pick_gemini_model(models) == "gemini-3-pro-image-preview"
assert P.pick_gemini_model([]) == P.GEMINI_DEFAULT
lite = [{"name": "models/gemini-3.1-flash-lite-image"}, {"name": "models/gemini-2.5-flash-image"}]
assert P.rank_gemini_models(lite) == ["gemini-2.5-flash-image", "gemini-3.1-flash-lite-image"]      # lite en sona
assert P.rank_gemini_models(models)[:2] == ["gemini-3-pro-image-preview", "gemini-2.5-flash-image"]
assert P.rank_openai_models(["gpt-image-1", "gpt-image-2", "gpt-image-1-mini"]) == ["gpt-image-2", "gpt-image-1"]

# 8) ayarlar göçü ve servis listeleri
st = P.Settings(magnific_key="k1", openai_key="", gemini_key="g1")
assert P.scene_arms(st) == ["gemini", "magnific-edit", "magnific-edit-pro", "magnific"]
assert P.video_arms(st) == ["veo-3-1", "kling-pro"]
st.scene_provider = "openai"; st.video_provider = "kling-pro"
assert P.scene_arms(st) == ["openai"] and P.video_arms(st) == ["kling-pro"]
assert P.video_arms(P.Settings()) == [] and P.scene_arms(P.Settings()) == []

# 8b) HTTP hata sınıflandırması (ağ yok: requests.request taklit edilir)
class _R:
    def __init__(self, code, body):
        self.status_code, self._b = code, body
        self.text = json.dumps(body)

    def json(self):
        return self._b


def with_response(code, body):
    calls = []
    def fake(method, url, **kw):
        calls.append(1)
        return _R(code, body)
    P.requests.request = fake
    P.time.sleep = lambda s_: None
    try:
        P._http("GET", "http://x", tries=3)
    except P.ProviderError as e:
        return e, len(calls)
    return None, len(calls)


real_request, real_sleep = P.requests.request, P.time.sleep
e, n = with_response(429, {"error": {"message": "You exceeded your current quota, please check your plan and billing details.", "type": "insufficient_quota"}})
assert isinstance(e, P.QuotaError) and n == 1, (e, n)            # kota bitti: beklemeden dur
e, n = with_response(429, {"error": {"message": "Rate limit reached for images per minute. Please try again in 6s.", "type": "rate_limit"}})
assert type(e) is P.ProviderError and n == 3 and "429" in str(e) and "try again" in str(e), (e, n)     # hız sınırı: bekle, 3 deneme, neden görünür
e, n = with_response(429, {"error": {"code": 429, "message": "Quota exceeded for metric ... limit: 0, model: gemini-3-pro-image", "status": "RESOURCE_EXHAUSTED"}})
assert isinstance(e, P.QuotaError) and n == 1, (e, n)
e, n = with_response(403, {"error": {"message": "Your organization must be verified to use the model `gpt-image-2`."}})
assert isinstance(e, P.QuotaError) and "verified" in str(e), e
e, n = with_response(401, {"error": {"message": "Incorrect API key provided"}})
assert type(e) is P.AuthError and "Incorrect API key" in str(e), e
e, n = with_response(400, {"error": {"message": "bad size"}})
assert type(e) is P.ProviderError and "bad size" in str(e) and n == 1, e
P.requests.request, P.time.sleep = real_request, real_sleep

# model sırası: kota/erişim hatasında sıradaki model denenir
tried = []
def call(m):
    tried.append(m)
    if m == "m1":
        raise P.QuotaError("limit: 0")
    if m == "m2":
        raise P.ProviderError("HTTP 404: model not found")
    return "ok"
assert P._try_models(["m1", "m2", "m3"], call, lambda *_: None, "T") == "ok" and tried == ["m1", "m2", "m3"]
tried2 = []
def call_acct(m):
    tried2.append(m)
    raise P.QuotaError("credit_balance_exhausted", account=True)
try:
    P._try_models(["a1", "a2", "a3"], call_acct, lambda *_: None, "T")
    raise SystemExit("hesap geneli kota yutuldu")
except P.QuotaError:
    assert tried2 == ["a1"], tried2                          # kredi bitmişse diğer modelleri denemez
e, n = with_response(429, {"error": {"code": "credit_balance_exhausted", "message": "You have no credits remaining."}})
assert isinstance(e, P.QuotaError) and e.account and n == 1, (e, n)
P.requests.request, P.time.sleep = real_request, real_sleep
try:
    P._try_models(["m1"], call, lambda *_: None, "T")
    raise SystemExit("QuotaError yutuldu")
except P.QuotaError:
    pass

# 8c) Magnific Seedream Edit isteği
sent = {}
class _Fake(P.MagnificEdit):
    def _run(self, path, body):
        sent["path"], sent["body"] = path, body
        return ["http://img"]
P._download = lambda url: b"IMG"
me = _Fake("k", variant="magnific-edit")
assert me.scene("prompt", 0.667, 1.0, refs=[b"r1", b"r2", b"r3", b"r4", b"r5"], seed=7, guide=b"G") == b"IMG"
assert sent["path"] == "/v1/ai/text-to-image/seedream-v4-5-edit"
assert sent["body"]["aspect_ratio"] == "portrait_2_3" and len(sent["body"]["reference_images"]) == 5
assert sent["body"]["reference_images"][0] == P._b64(b"G") and sent["body"]["seed"] == 7
assert _Fake("k", variant="magnific-edit-pro").model == "seedream-v5-pro-edit"
assert P.make_scene_provider(P.Settings(magnific_key="k"), name="magnific-edit").supports_guide

# 9) kalite puanı: ideal sahne yüksek, bozuk sahne düşük
import layout                              # noqa: E402
good = {"aspect": 0.514, "taper": 1.0, "tilt_left": 0.0, "tilt_right": 0.0, "top_tilt": 0.0, "side_ratio": 1.0,
        "h_frac": 0.85, "cx_frac": 0.5}
bad = dict(good, aspect=0.42, taper=1.1, side_ratio=0.93, h_frac=0.6, cx_frac=0.38)
sg, sb = layout.score(good, 0.514), layout.score(bad, 0.514)
print("kalite puanları:", sg, sb)
assert sg > 95 and sb < sg - 20 and layout.score({}, 0.5) == 0.0
print("test_selector: TAMAM")

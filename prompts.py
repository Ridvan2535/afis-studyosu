# -*- coding: utf-8 -*-
"""Sahne ve video istemleri (görsel modelleri İngilizce istemlerle daha iyi çalışır).

Ürün: yere kadar uzanan, DİK, boş (baskısız) hambez afiş; kamera tam KARŞIDAN bakar (yan açı yok).
Tasarım düz açıda yerleştirildiği için sahnedeki afişin de düz açıda olması şarttır (layout.py bunu denetler).
"""
import math

SUBJECT = (
    "SUBJECT: one single tall vertical BLANK banner made of natural off-white unbleached raw cotton-and-linen canvas "
    "(light cream, matte, visible fine weave, clean, neatly hemmed straight edges with no fringe, no tassels and no frayed threads anywhere, and no coloured border or edge strip). The banner is completely empty: no text, no letters, "
    "no pattern, no border, no logo, no print. {stand} {hem} Only very gentle natural vertical folds and a soft natural drape, otherwise flat and smooth. "
    "{ribbon} {proportion}"
)
# Eski sabit "20-30 cm daha uzun" ifadesi uydurulmuş bir ölçüydü (Aşama 2A'da kaldırıldı). Profil yoksa eski metin korunur.
HEM_LEGACY = ("It is FLOOR-LENGTH: the fabric is about 20-30 cm longer than the frame's clearance, so its straight plain hem reaches down TO the floor "
              "and rests ON the ground, lying there with a soft slight curve and a few gentle folds (no fringe, no tassels).")
HEM_PROFILE = ("It is FLOOR-LENGTH: the fabric hangs straight down from the rod and its straight plain bottom hem reaches the floor and touches it, "
               "ideally resting softly on the ground with only a little gentle pooling; the hem NEVER ends in the air above the floor "
               "(no fringe, no tassels).")

STAND = (
    "CONSTRUCTION (copy exactly): a slim free-standing rectangular frame of plain light natural pine wood stands on the floor by itself: two thin "
    "square vertical posts, a pair of small flat feet, and a thin round top rod. The banner HANGS FREELY from the top rod between the two posts: its "
    "top edge is folded over the rod and the banner hangs straight down in front of the rod, NOT attached, sewn, nailed or stapled to the posts. "
    "The banner is narrower than the frame, so a clear gap of several centimetres shows between each banner edge and the posts; the posts stay "
    "completely visible on both sides and never overlap the banner. The frame is NOT hung from the ceiling, NOT tied to a tree or beam, no ropes."
)

_NAMED = {"mustard yellow": (242, 194, 48), "lemon yellow": (250, 230, 90), "cream white": (241, 230, 210), "white": (250, 250, 250),
          "blush pink": (232, 180, 188), "hot pink": (230, 70, 140), "dusty rose": (200, 140, 150), "sage green": (156, 175, 136),
          "forest green": (40, 100, 60), "emerald green": (30, 150, 100), "baby blue": (169, 199, 232), "royal blue": (50, 80, 190),
          "navy blue": (30, 40, 90), "teal": (40, 140, 140), "burgundy": (114, 47, 55), "red": (200, 30, 40), "orange": (240, 140, 40),
          "terracotta": (190, 100, 70), "lavender": (190, 170, 220), "purple": (110, 60, 150), "brown": (110, 75, 50), "tan beige": (205, 185, 150),
          "grey": (140, 140, 140), "black": (30, 30, 30), "gold": (200, 160, 60), "champagne": (230, 210, 170)}


def color_en(hexv: str) -> str:
    """#RRGGBB -> en yakın İngilizce renk adı (model Türkçe renk adından çok bunu iyi anlar)."""
    h = hexv.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return min(_NAMED, key=lambda k: sum((a - b) ** 2 for a, b in zip(_NAMED[k], rgb)))


RIBBON_ON = (
    "RIBBONS: at each of the two top corners a soft {name} ribbon (hex {hex}), about 3 cm wide, soft matte satin, is tied around the top rod "
    "right at the banner's corner in a relaxed, slightly imperfect bow. From each bow two long, thin ribbon tails of slightly different lengths "
    "hang down freely OUTSIDE the banner's side edge, in the gap beside the posts, reaching about 35-45% of the banner's height, gently curling "
    "and moving in the air. The tails do NOT lie on the banner and are never glued or sewn to its edge: the banner's side edges are plain cream "
    "fabric with NO ribbon stripe or coloured edging on them. The ribbon colour is exactly {name} ({hex}), the same on both sides."
)
RIBBON_OFF = "No ribbons: the banner is simply draped over the rod, clean and unadorned."
# Ürün profiliyle her sahne kurdelelidir; renk seçilmemişse ortama uygun nötr bir renk modele bırakılır.
RIBBON_ANY = (
    "RIBBONS: at each of the two top corners a soft ribbon, about 3 cm wide, soft matte satin or chiffon in a colour that suits the scene, "
    "is tied around the top rod right at the banner's corner in a relaxed, slightly imperfect bow, as in a real event decoration. From each bow "
    "two long, thin ribbon tails of slightly different lengths hang down freely OUTSIDE the banner's side edge, in the gap beside the posts. "
    "The tails do NOT lie on the banner: the banner's side edges are plain cream fabric with NO ribbon stripe or coloured edging on them."
)

CAMERA = (
    "CAMERA: perfectly FRONTAL straight-on view, like a catalogue product photo or architectural front elevation. The lens "
    "is at the banner's mid-height, the camera axis is exactly perpendicular to the banner, and the banner faces the camera "
    "squarely and is horizontally centred. The banner is NOT turned, NOT angled, NOT seen from the side, NOT in perspective: "
    "its left and right edges are perfectly vertical and parallel, and its top edge is perfectly horizontal. "
    "Portrait photograph; the banner is the main subject and fills about 80% of the image height and about 60-70% of the image width, "
    "from about 11% below the top of the frame down to the floor, fully visible, not cropped; the whole wooden frame is visible."
)
CAMERA_SQUARE = (
    "CAMERA: perfectly FRONTAL straight-on view, like a catalogue product photo or architectural front elevation. The lens "
    "is at the banner's mid-height, the camera axis is exactly perpendicular to the banner, and the banner faces the camera "
    "squarely and is horizontally centred. The banner is NOT turned, NOT angled, NOT seen from the side, NOT in perspective: "
    "its left and right edges are perfectly vertical and parallel, and its top edge is perfectly horizontal. "
    "SQUARE photograph (1:1). The banner and the ENTIRE wooden stand - top rod, both posts and both feet - and the floor where the hem "
    "touches it are fully visible inside the square with a little space around them; nothing is cropped at the top, bottom or sides."
)

SURROUND = (
    "Directly behind the banner there is something dark, saturated or richly textured (clipped green hedge, dense foliage, a deep-coloured wall, "
    "heavy drapery, timber, a stone wall) so the cream banner stands out with strong tonal contrast; never a white or cream surface right behind it. "
    "Around and beyond it the place is rich, lived-in and full of the celebration's atmosphere, not an empty room. "
    "The ground or floor is visible below the banner. Nothing hides or overlaps the banner or its frame except the ribbon tails{clear}. "
    "Decorations, balloons, flowers and guests stay beside or behind it, never in front of it. "
    "REALISM (most important): it must look like a candid, unretouched photo that a guest or the host took with a good phone or a mirrorless camera "
    "at a real event, NOT a render or an AI picture: true-to-life colours, natural uneven light with real shadows and highlights, a hint of film grain, "
    "real fabric, grass, skin and wood texture, slightly imperfect everyday details, a natural depth of field. No text, letters, logos or signs anywhere. "
    "{light}"
)

CLEAR_NO_PEOPLE = ""
CLEAR_PEOPLE = ""
PEOPLE = (
    " PEOPLE: real-looking guests in festive clothes are present in the background, several metres behind the banner, small in the frame and slightly out "
    "of focus, seen from behind, in profile or at a distance, naturally spread out, chatting or celebrating. "
    "Nobody stands in front of the banner or touches it, nobody overlaps it, and nobody is in the foreground; no close-up faces."
)

REFERENCE_NOTE = (
    " Use the attached reference photo(s) for the mood, wall colours, lighting and type of venue, and ALSO copy the physical construction shown: "
    "the slim light-wood frame and rod, the soft fabric drape, and how the ribbons are tied in relaxed bows at the top corners and fall as long tails. "
    "The references may show banners with printed artwork, text, characters or colours: IGNORE all of that completely. "
    "Do not copy any artwork, lettering, characters, banner colour or layout from the banners in the references, and do not copy "
    "their banner shape, size or angle. In the new image the banner is blank cream canvas with absolutely nothing printed on it. "
    "Create a NEW, different scene."
)

REF_ORDER = " (Image 1 is the layout guide; the other attached image is the reference photo.)"
RIBBON_REF = " The ribbon colour is FIXED as stated above: ignore the colours of any ribbons in the references, copy only their soft, natural, slightly frayed look and how they are tied."
GUIDE_NOTE = (
    "Image 1 is a LAYOUT GUIDE, not a style reference. Turn it into a realistic photograph with EXACTLY this composition: "
    "the cream rectangle is the blank fabric banner. Keep its exact position, size, tall proportions and perfectly frontal, flat "
    "orientation (edges perfectly vertical, no rotation, no perspective, no side view). The small coloured shapes at the rod ends are ribbon bows "
    "and the two thin coloured strips beside the banner (outside its edges, in the gap next to the posts) are their ribbon tails: keep them outside the banner, never on it. "
    "The lower band is the floor and the banner's bottom hem reaches it and touches it. "
    "Replace the plain grey wall and flat floor with the scene described below, but do not move, resize, rotate or reshape the banner, "
    "and do not put any print or text on it. "
)

# Her sahnenin başındaki "OUT:" açık hava, "IN:" iç mekan demektir (ışık listesi ona göre seçilir).
CATEGORIES = {
    "Düğün": [
        "OUT: SCENE: open-air wedding on a big green lawn. A tall dark clipped hedge directly behind the banner; beyond and beside it a wide meadow with white chairs, a flower arch far away and a crowd of guests in light summer outfits gathering in the distance. A bride in a white dress stands calmly beside the banner, a metre to its right, not touching it.",
        "OUT: SCENE: vineyard wedding reception in the countryside. Rows of grapevines and rolling green hills behind, long banquet tables with greenery and candles far to the side, guests laughing in the background; the banner stands on a dirt-and-grass path in front of a dense dark vine wall.",
        "OUT: SCENE: lakeside wedding. Tall dark pine trees directly behind the banner, a calm lake and wooden jetty in the distance with a small crowd of guests, soft haze over the water, wildflowers in the grass beside the banner.",
        "OUT: SCENE: rustic farm wedding in a wheat-and-green-field landscape. A dark weathered barn wall directly behind the banner, string lights hanging in the background, hay bales and a cheerful crowd of guests with a groom in a suit standing far behind.",
        "OUT: SCENE: Mediterranean olive-grove wedding. Old olive trees and a dry-stone wall behind the banner, terracotta pots with lavender beside it, long tables and guests in linen outfits in the distance, warm countryside feeling.",
        "OUT: SCENE: forest-clearing wedding at dusk. Dark leafy trees directly behind the banner, hundreds of warm fairy lights glowing in the branches, rows of chairs and guests in the soft blurred distance, petals scattered on the grass.",
        "OUT: SCENE: city-garden wedding celebration. A lush climbing-ivy wall directly behind the banner, a blooming rose bed, a gazebo and a lively crowd of guests with champagne glasses in the background.",
        "OUT: SCENE: botanical-garden wedding reception. Large dark green tropical leaves and a stone balustrade behind the banner, a flowering magnolia, guests strolling on the garden path far away, a bride and groom in the blurred distance.",
        "IN: SCENE: elegant wedding hall entrance. Heavy deep burgundy velvet drapes directly behind the banner, a dark marble floor, tall floral arrangements and candle lanterns well to the sides, a glowing chandelier and guests mingling in the room beyond.",
    ],
    "Nişan / Kına": [
        "IN: SCENE: traditional henna (kına) night. Deep red and gold drapery directly behind the banner, a decorated tray with candles and henna dishes on a side table, women in colourful festive dresses gathering far behind, warm lamps.",
        "OUT: SCENE: engagement party on a vine-covered terrace. Dense dark green vines directly behind the banner, lanterns hanging, rose bouquets in pots to the side, guests with drinks chatting in the distance at sunset.",
        "OUT: SCENE: garden engagement celebration. A dark clipped hedge behind the banner, white and pink flower arrangements beside it, a long table with fruit and sweets, family and friends celebrating in the background.",
        "IN: SCENE: engagement dinner in a restaurant hall. Dark teal wall with gold sconces directly behind the banner, round tables with roses, guests seated in the blurred background, a soft warm glow.",
        "OUT: SCENE: seaside engagement party. A dark stone wall behind the banner, the sea and a pier in the background, white flowers and lanterns on the ground at the sides, a happy couple and guests far away.",
        "IN: SCENE: cosy family living-room engagement. A deep green wall directly behind the banner, a sofa, flowers and sweets on a table to the side, relatives chatting in the background.",
        "OUT: SCENE: courtyard of a stone house with potted geraniums. Rough dark stone wall behind the banner, rugs and cushions on the ground, evening lights, guests in festive clothes in the distance.",
        "OUT: SCENE: rooftop engagement party at golden hour. A dark green plant wall behind the banner, city skyline far behind, string lights, a small group of guests with glasses at the far side.",
    ],
    "Bekarlığa veda": [
        "IN: SCENE: bridal shower in a bright living room. A deep green plant wall directly behind the banner, pink and white balloons and a prosecco table beside it, friends in matching outfits laughing in the background.",
        "OUT: SCENE: bachelorette brunch in a garden. A dark hedge directly behind the banner, a long brunch table with flowers, pink balloons at the sides, girlfriends chatting in the distance.",
        "IN: SCENE: boho bridal party. Dark terracotta wall behind the banner, pampas grass and macrame beside it, a floor-cushion lounge area and friends in the soft blurred background.",
        "OUT: SCENE: pool-side bachelorette party. Dark tropical palm foliage behind the banner, inflatable swans and pastel balloons at the sides, friends in sunglasses far behind in the sun.",
        "IN: SCENE: rooftop evening party. Dark navy wall with neon-warm string lights, a bar with champagne to the side, friends dancing in the distance.",
        "OUT: SCENE: countryside villa lawn party. A tall dark cypress hedge behind the banner, white sheets and rose petals on picnic tables, friends relaxing in the background.",
    ],
    "Baby shower": [
        "IN: SCENE: lively baby shower in a party room. Bunches of red, pink and blue balloons and a big balloon garland arch around and behind the banner but never covering it, a dark teal wall directly behind it, two small wrapped gift boxes on the floor beside the banner and one right at its foot, a dessert table with cupcakes in the background, relatives with smiles in the distance.",
        "OUT: SCENE: baby shower garden party. A dark green hedge behind the banner, colourful red, pink and blue balloons tied to the garden fence and trees around, a few small gift packages in the grass beside the banner, a picnic table with cake and lemonade, guests and kids in the background.",
        "IN: SCENE: cosy family living-room baby shower. A deep navy wall directly behind the banner, pastel and primary-colour balloons floating along the ceiling, a heap of small gift boxes with ribbons beside it, a sofa with relatives and a snack table in the background.",
        "OUT: SCENE: baby shower on a sunny terrace. Dark climbing plants behind the banner, bunting flags and balloon clusters in red, pink and blue, a wicker basket with gifts at its foot, a table with sweets and guests chatting far behind.",
        "IN: SCENE: baby shower in a community hall. Rich-coloured drapes directly behind the banner, a long balloon garland along the side wall, tables with cakes and little gift bags, a crowd of cheerful guests in the blurred background.",
        "OUT: SCENE: baby shower picnic in a park. Big old trees behind the banner, pink and blue balloons tied to the trees, blankets and cushions on the grass, small gift boxes beside the banner and families in the distance.",
        "IN: SCENE: pastel baby shower with a dark wall. A deep forest-green wall directly behind the banner, clusters of red, pink and blue balloons on both sides, a cake table, two little gift boxes beside the banner, guests mingling far behind.",
        "OUT: SCENE: backyard baby shower at golden hour. A dark wooden fence behind the banner, strings of lights, colourful balloons on the fence and the floor, small presents beside the banner, relatives and kids playing in the background.",
    ],
    "Cinsiyet partisi": [
        "OUT: SCENE: gender reveal party in a garden. A dark green hedge directly behind the banner, pink and blue balloons everywhere around it and on the grass, small gift boxes beside the banner, smoke-free confetti on the lawn, family and friends gathering in the distance.",
        "IN: SCENE: gender reveal at home. A deep navy wall behind the banner, big pink and blue balloon clusters on both sides, a cake table and gift boxes beside the banner, guests with cameras in the background.",
        "OUT: SCENE: gender reveal on a sunny terrace. Dark climbing plants behind the banner, pink and blue bunting and balloons, relatives chatting far behind.",
        "IN: SCENE: party hall reveal. Dark drapery behind the banner, a balloon arch of pink and blue to the side, dessert table and excited guests in the distance.",
        "OUT: SCENE: countryside reveal picnic. A line of trees behind the banner, pink and blue balloons tied to a wooden fence, blankets and baskets, friends and family in the field far behind.",
        "OUT: SCENE: backyard reveal at golden hour. A dark fence behind the banner, string lights, pastel pink and blue balloons, a few small gifts beside the banner, guests laughing in the background.",
    ],
    "Çocuk doğum günü": [
        "IN: SCENE: kids' birthday party in a decorated living room. A dark teal wall directly behind the banner, red, yellow, blue and pink balloons all around and floating on the ceiling, a birthday cake table and small wrapped gifts beside the banner, children running and playing far behind.",
        "OUT: SCENE: birthday party in a garden. A dark green hedge behind the banner, colourful balloon bunches tied to the fence and trees, a table with cake and snacks, kids and parents in the background, small gift boxes beside the banner.",
        "IN: SCENE: birthday party in a play-cafe. A deep blue wall behind the banner, colourful balloons, ball pit and slides in the blurred background, children and parents.",
        "OUT: SCENE: park birthday picnic. Large dark trees behind the banner, balloons tied to the branches, tablecloth with cupcakes, families and kids playing far away.",
        "IN: SCENE: party hall birthday. Dark curtains behind the banner, balloon arch to the side, a table with a big cake, party hats, small gifts beside the banner, kids dancing in the background.",
        "OUT: SCENE: birthday on a sunny terrace. Dark climbing plants behind the banner, bunting flags and balloons, gift boxes beside the banner, kids and parents around a table far behind.",
        "OUT: SCENE: backyard birthday at golden hour. A dark wooden fence behind the banner, string lights and balloons, a trampoline and kids in the background, small presents beside the banner.",
        "IN: SCENE: cosy home birthday in the evening. A deep green wall behind the banner, warm lamps, balloons on the floor, a cake with candles on the table in the distance and family around it.",
    ],
    "Yetişkin doğum günü": [
        "IN: SCENE: elegant birthday dinner party. A dark navy wall behind the banner, gold and black balloons, candles and flowers on tables to the side, guests with glasses laughing in the blurred background.",
        "OUT: SCENE: garden birthday party at dusk. A dark hedge behind the banner, string lights across the garden, a long table with food, friends chatting in the distance.",
        "IN: SCENE: rooftop terrace birthday. A dark green plant wall behind the banner, city lights far behind, balloons in rose gold, friends with drinks in the background.",
        "OUT: SCENE: seaside birthday party at sunset. A dark stone wall behind the banner, beach and sea in the background, lanterns and balloons at the sides, friends gathering far away.",
        "IN: SCENE: restaurant private room birthday. A deep burgundy wall behind the banner, round tables, flowers and a cake in the distance, friends seated and cheering.",
        "OUT: SCENE: villa pool party birthday. Dark palm foliage behind the banner, balloons and floats at the sides, guests in swimwear and summer clothes far in the background.",
    ],
    "Mezuniyet": [
        "OUT: SCENE: graduation celebration on a university campus lawn. Large dark green trees behind the banner, graduates in gowns and caps with families taking photos in the distance, balloons and flowers beside the banner.",
        "IN: SCENE: graduation party at home. A deep navy wall behind the banner, gold and black balloons, a table with cake and diplomas, family and friends in the background.",
        "OUT: SCENE: graduation garden party. A dark hedge behind the banner, bunting and balloons in school colours, friends in gowns tossing caps far behind.",
        "IN: SCENE: banquet hall graduation dinner. Dark drapery behind the banner, round tables, gold balloons, graduates and parents in the blurred hall.",
        "OUT: SCENE: stone university building courtyard. A dark old brick wall behind the banner, flowers in pots, crowds of graduates and families far behind at golden hour.",
        "OUT: SCENE: seaside graduation picnic. A dark rock wall behind the banner, balloons and blankets on the sand, friends celebrating far away.",
    ],
    "Yılbaşı": [
        "IN: SCENE: cosy New Year's Eve living room. A big decorated Christmas tree with warm lights and gold-and-red ornaments directly behind the banner's side, a dark green wall behind the banner itself, a fireplace with stockings to one side, wrapped presents beside the banner, family with glasses in the background.",
        "OUT: SCENE: snowy garden at night. Snow-covered dark pine trees behind the banner, warm fairy lights wrapped around the trees, soft falling snow, lanterns in the snow, a wooden cabin with glowing windows far behind, a few people in winter coats in the distance.",
        "IN: SCENE: New Year's Eve party hall. A deep navy curtain behind the banner, gold and silver balloons, a sparkling table with champagne, guests in elegant clothes in the blurred background.",
        "OUT: SCENE: winter wonderland market square. A dark timber chalet wall behind the banner, garlands and lights, snow on the ground, crowds with hot drinks far behind.",
        "IN: SCENE: festive dining room. A deep red wall behind the banner, a Christmas tree beside it, a laden dinner table with candles and gifts at its foot, family members in the background.",
        "OUT: SCENE: snowy mountain chalet terrace. A dark wood-plank wall behind the banner, snow-covered peaks far behind, string lights and fir garlands, friends in knitwear far in the distance.",
        "IN: SCENE: countdown party at home. A dark green wall behind the banner, gold number balloons and confetti, a table with party hats, friends dancing in the background.",
        "IN: SCENE: cosy cabin with fireplace. Dark pine-log wall behind the banner, a warm crackling fire and a decorated tree to the side, presents beside the banner, family on a sofa in the background.",
    ],
}
# Eski kayıtlı işler için takma adlar
ALIASES = {"Doğum günü / Baby shower": "Baby shower"}
# Arka planda misafir/kalabalık olması doğal olan kutlamalar (insanlı sahne varsayılan)
PEOPLE_DEFAULT = {"Düğün", "Nişan / Kına", "Bekarlığa veda", "Mezuniyet", "Yetişkin doğum günü", "Yılbaşı"}

LIGHTS_OUT = [
    "Light: golden hour, low warm sun, long soft shadows.",
    "Light: soft overcast daylight, gentle and even, slightly cool.",
    "Light: bright late-morning sun with some dappled shade, fresh and airy.",
    "Light: blue hour just after sunset, warm string lights glowing against the deep blue sky.",
    "Light: early afternoon sun, clear sky, crisp light and natural contrast.",
    "Light: late-evening twilight with warm lamp light mixing into the cool ambient light.",
    "Light: hazy warm morning light with a gentle mist in the air.",
]
LIGHTS_IN = [
    "Light: warm evening lamps and candlelight with a soft glow.",
    "Light: bright daylight from large windows, airy and soft.",
    "Light: mixed warm ceiling lights and a little flash-like fill, as in a real party snapshot.",
    "Light: cosy low light with fairy lights and soft shadows.",
    "Light: soft late-afternoon window light with warm highlights.",
    "Light: festive evening light with a few coloured accents, slightly warm white balance.",
]


def canon(category: str) -> str:
    category = ALIASES.get(category, category)
    return category if category in CATEGORIES else "Düğün"


def default_people(category: str) -> bool:
    return canon(category) in PEOPLE_DEFAULT


def pool_size(category: str) -> int:
    return len(CATEGORIES[canon(category)])


# ESKİ YOL (profilsiz işler ve eski testler için korunur): tasarım oranından ölçü tahmini. Yeni üretim hattı bunu KULLANMAZ;
# ölçü ürün profilinden gelir (product.py). Bilinen hata: aynı oranlı ölçüler (50x100/150x300, 75x200/150x400) ayırt edilemez.
STANDARD_SIZES = [(50, 100), (50, 150), (75, 200), (150, 300), (150, 400)]


def size_for(aspect: float, tol: float = 0.10):
    """Tasarım oranına en yakın satılan ölçü (en, boy) ya da yakın değilse None."""
    w, h = min(STANDARD_SIZES, key=lambda s: abs(math.log(aspect / (s[0] / s[1]))))
    return (w, h) if abs(aspect / (w / h) - 1) <= tol else None


def aspect_text(aw: float, ah: float) -> str:
    r = aw / ah
    sz = size_for(r)
    if sz:
        w, h = sz
        return (f"Banner size: exactly {w} cm wide and {h} cm tall (its height is {h / w:.1f} times its width). "
                f"Keep exactly this proportion: do NOT make it wider, narrower, shorter or taller than this.")
    return (f"Banner proportion: its height is exactly {1 / r:.2f} times its width (for example {r * 100:.0f} cm wide and 100 cm tall). "
            f"Keep exactly this proportion: do NOT make it wider or narrower.")


def frame_aspect(banner_aspect: float) -> float:
    """Kadrajın en/boy oranı: afiş yüksekliğin ~%80'ini, genişliğin ~%60'ını kaplasın. Hedef oran, servislerin ortak
    desteklediği en yakın standart orana oturtulur (9:16, 2:3, 3:4); böylece kılavuz görselin oranı çıktının oranıyla birebir
    aynı olur ve afişin en-boy oranı kayıpsız korunur."""
    want = min(max(1.26 * banner_aspect, 0.5625), 0.80)
    return min((9 / 16, 2 / 3, 3 / 4), key=lambda r: abs(math.log(want / r)))


def profile_size_text(profile) -> str:
    """Ürün profilinden ölçü cümlesi (PNG oranından tahmin YOK)."""
    w, h = profile.en_cm, profile.boy_cm
    return (f"Banner size: the fabric is exactly {w} cm wide and {h} cm long (its length is {h / w:.2f} times its width). "
            f"The stand is just tall enough for this fabric to hang from the rod down to the floor. Keep exactly this proportion: "
            f"do NOT make the banner wider, narrower, shorter or longer than this.")


def build_scene_prompt(category: str, index: int, aw: float, ah: float, has_refs=False, round_no=0, guided=False,
                       people=False, ribbon=None, scene_desc: str | None = None, profile=None) -> str:
    """scene_desc: referans deposundaki görsele yazılmış hazır sahne tarifi (varsa genel kategori listesi yerine kullanılır).
    Tarif "OUT:" ya da "IN:" ile başlayabilir (ışık seçimi için); başlamıyorsa dış mekân sayılır."""
    pool = CATEGORIES[canon(category)]
    desc = (scene_desc or "").strip() or pool[index % len(pool)]
    outdoor = not desc.startswith("IN:")
    if desc[:4] in ("OUT:", "IN: ") or desc[:3] == "IN:":
        desc = desc.split(":", 1)[1].strip()
    lights = LIGHTS_OUT if outdoor else LIGHTS_IN
    # sahneden bağımsız adımla ışık seç: aynı sahne tekrar gelse bile başka saat/ışık olur
    light = lights[(index * 3 + index // len(pool) * 2 + round_no) % len(lights)]
    variety = ""
    if round_no > 0:   # liste tükenip başa dönünce aynı sahneyi tekrar etmesin
        variety = f" Variation {round_no + 1}: change the venue details, season of the plants, colour palette and the people, but keep the same banner layout."
    if ribbon:
        rb = RIBBON_ON.format(name=color_en(ribbon["hex"]), hex=ribbon["hex"])
    else:
        rb = RIBBON_ANY if profile is not None else RIBBON_OFF        # ürün profiliyle tüm sahneler kurdeleli
    if profile is not None:                                          # Aşama 2A: ölçü profilden, kare kadraj, uydurulmuş birikme ölçüsü yok
        subject = SUBJECT.format(proportion=profile_size_text(profile), ribbon=rb, stand=STAND, hem=HEM_PROFILE)
        camera = CAMERA_SQUARE
    else:
        subject = SUBJECT.format(proportion=aspect_text(aw, ah), ribbon=rb, stand=STAND, hem=HEM_LEGACY)
        camera = CAMERA
    head = GUIDE_NOTE if guided else ""
    surround = SURROUND.format(clear=", and at most a few small gift boxes at its very foot where the scene mentions them", light=light)
    return (head + subject + " " + camera + " " + desc + variety + " " + surround + (PEOPLE if people else "")
            + (REFERENCE_NOTE if has_refs else "") + (REF_ORDER if (has_refs and guided) else "")
            + (RIBBON_REF if (ribbon and has_refs) else ""))


MOTION = (
    "Slow handheld camera move toward the hanging fabric banner with a slight sideways arc, subtle natural handheld sway. "
    "The fabric moves very gently in a light breeze. The printed text and artwork on the banner stay perfectly unchanged "
    "and sharp. Photorealistic, natural light, stable exposure, one continuous shot, no cuts."
)


# Kompozit video (kamera SABİT, tasarım sonradan kodla basılır): modele yazı yoktur, kameranın oynamaması istenir.
MOTION_STATIC = (
    "Locked-off static shot on a tripod: the camera does not move at all, no zoom, no pan, no tilt, no shake. "
    "The blank cream fabric banner stays perfectly still and unchanged, with no text or print appearing on it. "
    "Only very subtle ambient motion: leaves and light drapery sway gently in a soft breeze, soft light flickers naturally. "
    "Photorealistic, natural light, stable exposure, one continuous shot, no cuts."
)
MOTION_PEOPLE = (
    "Locked-off static shot on a tripod: the camera does not move at all, no zoom, no pan, no tilt, no shake. "
    "The blank cream fabric banner stays perfectly still and unchanged, with no text or print appearing on it, and nobody "
    "walks in front of it or touches it. In the far background the party guests move slowly and naturally: gentle weight shifts, "
    "small relaxed gestures, calm conversation, a slow unhurried walk, never fast or sudden. Leaves and light drapery sway "
    "slightly in a soft breeze. Photorealistic, natural light, stable exposure, one continuous shot, no cuts."
)


# Hareketli kamera videosu: kamera hareketini yapay zekâ modeli YAPAR (gerçek parallax), tasarım sonradan kodla basılır.
MOTION_LIVE = (
    "CAMERA MOVEMENT (the most important instruction, it must clearly happen): a continuous handheld dolly shot. In the first 2 seconds the camera "
    "pushes steadily forward toward the banner, then for the rest of the clip it keeps moving forward while orbiting in a smooth arc to the right "
    "around the banner, so by the end the banner is clearly larger in the frame and is seen from a visibly different angle, and the background "
    "behind it slides and changes with strong parallax (the camera travels about 2-3 metres in total). Natural handheld walking sway, never static. "
    "The banner always stays in the frame and mostly visible. The banner is blank cream fabric and stays blank: no text, print or pattern ever appears "
    "on it; it hangs freely, keeps its shape and sways only very slightly. {ribbons}{life}"
    "Photorealistic, natural light, true-to-life colours, one continuous shot, no cuts, no slow motion."
)
LIVE_RIBBONS = ("The thin satin ribbon tails and bows at the top corners flutter, wave and curl lightly in the breeze, clearly visible "
                "moving, always staying outside the banner's edges. ")
LIVE_LIFE = ("The scene is alive: guests and children behind and beside the banner move naturally, kids run and play, people chat and gesture, "
             "balloons and leaves sway, lights twinkle. Everybody stays beside or behind the banner, nobody ever walks between the camera and "
             "the banner or touches it. ")
LIVE_QUIET = "Leaves and light fabrics in the background sway gently in the breeze. "

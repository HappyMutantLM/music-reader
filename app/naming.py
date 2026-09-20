"""
naming.py — shared composer/category/instrument vocabulary and detection logic.
"""

import re
import unicodedata

# ── Known composers ────────────────────────────────────────────────────────
COMPOSERS = {
    "bach", "bachjs", "jsbach", "bachcpe", "cpebach",
    "beethoven", "brahms", "chopin", "debussy",
    "dvorak", "handel", "haydn", "mahler", "mozart", "prokofiev",
    "ravel", "schubert", "schumann", "shostakovich", "strauss",
    "tchaikovsky", "vivaldi", "wagner",
    "scriabin", "skrjabin", "satie", "rossini", "janacek",
    "gounod", "gershwin", "saint-saens", "saintsaens",
    # Bass repertoire
    "bottesini", "dragonetti", "koussevitzky", "rabbath", "vanhal",
    # Method/etude authors
    "simandl", "czerny", "hanon", "kreutzer", "popper", "kummer",
    "vance", "beringer", "manookian", "bastien",
    # Popular
    "billjoel", "billyjoel", "loureed", "queen", "joplin", "bowie",
    "comeau",
    # Contemporary/local
    "pierce",
    "lpierce", "piercel",

    # ── ABRSM Piano Practical Grades 2027 & 2028 syllabus ──────────────────
    # Auto-derived: bare surname (where it doesn't collide with an existing
    # or another new composer's surname) plus name/surname order-pairs, same
    # convention as "pierce"/"lpierce"/"piercel" above. Review before relying
    # on it for non-Western name order or unusual bylines (flagged inline).

    # Shared surnames -- disambiguated by initials/given name (bare surname
    # NOT added for these; see comment on each):
    "jcfbach", "bachjcf",          # J. C. F. Bach (bare "bach" above = J. S. Bach)
    "lmozart", "mozartl",          # L. (Leopold) Mozart (bare "mozart" above = W. A. Mozart)
    "cschumann", "schumannc",      # C. (Clara) Schumann (bare "schumann" above = Robert Schumann)
    "barthoward", "howardbart",    # Bart Howard ("Fly Me to the Moon")
    "danihoward", "howarddani",    # Dani Howard
    "pamwedgwood", "wedgwoodpam",  # Pam Wedgwood
    "samwedgwood", "wedgwoodsam",  # Sam Wedgwood

    # Family name given first in source (kept as printed) / compound surname:
    "chenpeixun", "peixunchen", "chen",   # Chen Peixun (family name "Chen")
    "nihongjin", "hongjinni", "ni",        # Ni Hongjin (family name "Ni")
    "saintgeorges", "saint-georges",       # Chevalier de Saint-Georges

    "beach", "abeach", "beacha",  # A. Beach
    "muller", "aemuller", "mullerae",  # A. E. Müller
    "hedges", "ahedges", "hedgesa",  # A. Hedges
    "lindeman", "alindeman", "lindemana",  # A. Lindeman
    "reinagle", "areinagle", "reinaglea",  # A. Reinagle
    "agay",  # Agay
    "robertson", "ailierobertson", "robertsonailie",  # Ailie Robertson
    "bullard", "alanbullard", "bullardalan",  # Alan Bullard
    "haughton", "alanhaughton", "haughtonalan",  # Alan Haughton
    "menken", "alanmenken", "menkenalan",  # Alan Menken
    "albeniz",  # Albéniz
    "skevington", "alexandraskevington", "skevingtonalexandra",  # Alexandra Skevington
    "ffrench", "alexisffrench", "ffrenchalexis",  # Alexis Ffrench
    "cook", "aliciaaugellocook", "cookaliciaaugello",  # Alicia Augello Cook
    "savanenkovaite", "alinasavanenkovaite", "savanenkovaitealina",  # Alina Savanenkovaite
    "mathews", "alisonmathews", "mathewsalison",  # Alison Mathews
    "pirio", "alonsomalikpirio", "pirioalonsomalik",  # Alonso Malik Pirio
    "alwyn",  # Alwyn
    "andree",  # Andrée
    "bell", "angelinebell", "bellangeline",  # Angeline Bell
    "arensky",  # Arensky
    "arlen",  # Arlen
    "part", "arvopart", "partarvo",  # Arvo Pärt
    "mayerl", "bjmayerl", "mayerlbj",  # B. J. Mayerl
    "marcello", "bmarcello", "marcellob",  # B. Marcello
    "grondahl", "backergrondahl", "grondahlbacker",  # Backer Grøndahl
    "balutet",  # Balutet
    "arens", "barbaraarens", "arensbarbara",  # Barbara Arens
    "snow", "barbarasnow", "snowbarbara",  # Barbara Snow
    "bartok",  # Bartók
    "crosland", "bencrosland", "croslandben",  # Ben Crosland
    "schattel", "bertramschattel", "schattelbertram",  # Bertram Schattel
    "joel", "joelbilly",  # Billy Joel
    "taylor", "billytaylor", "taylorbilly",  # Billy Taylor
    "dylan", "bobdylan", "dylanbob",  # Bob Dylan
    "bonis",  # Bonis
    "bridge",  # Bridge
    "kelly", "bryankelly", "kellybryan",  # Bryan Kelly
    "burleigh",  # Burleigh
    "buxtehude",  # Buxtehude
    "hartmann", "chartmann", "hartmannc",  # C. Hartmann
    "petzold", "cpetzold", "petzoldc",  # C. Petzold
    "rego", "cairosrego", "regocairos",  # Cairos-Rego
    "vine", "carlvine", "vinecarl",  # Carl Vine
    "klose", "carolklose", "klosecarol",  # Carol Klose
    "calvache", "carolinacalvache", "calvachecarolina",  # Carolina Calvache
    "carse",  # Carse
    "casella",  # Casella
    "rollin", "catherinerollin", "rollincatherine",  # Catherine Rollin
    "coles", "cecilcoles", "colescecil",  # Cecil Coles
    "chaminade",  # Chaminade
    "stier", "charlesstier", "stiercharles",  # Charles Stier
    "tan", "cheehwatan", "tancheehwa",  # Chee-Hwa Tan
    "donkin", "christinedonkin", "donkinchristine",  # Christine Donkin
    "norton", "christophernorton", "nortonchristopher",  # Christopher Norton
    "cimarosa",  # Cimarosa
    "clementi",  # Clementi
    "scarlatti", "dscarlatti", "scarlattid",  # D. Scarlatti
    "fournier", "daniellefournier", "fournierdanielle",  # Danielle Fournier
    "fellows", "darrenfellows", "fellowsdarren",  # Darren Fellows
    "joio", "dellojoio", "joiodello",  # Dello Joio
    "alexander", "dennisalexander", "alexanderdennis",  # Dennis Alexander
    "diabelli",  # Diabelli
    "hidy", "dianehidy", "hidydiane",  # Diane Hidy
    "thomson", "donaldthomson", "thomsondonald",  # Donald Thomson
    "dring",  # Dring
    "duncombe",  # Duncombe
    "dvarionas",  # Dvarionas
    "dyson",  # Dyson
    "farrar", "efarrar", "farrare",  # E. Farrar
    "turner", "eturner", "turnere",  # E. Turner
    "alberga", "eleanoralberga", "albergaeleanor",  # Eleanor Alberga
    "davidsson", "eliasdavidsson", "davidssonelias",  # Elias Davidsson
    "wells", "elsiewells", "wellselsie",  # Elsie Wells
    "john", "eltonjohn", "johnelton",  # Elton John
    "estevez",  # Estévez
    "price", "fprice", "pricef",  # F. Price
    "farrenc",  # Farrenc
    "ruiz", "federicoruiz", "ruizfederico",  # Federico Ruiz
    "field",  # Field
    "mulsant", "florentinemulsant", "mulsantflorentine",  # Florentine Mulsant
    "fly",  # Fly
    "faux", "francisfaux", "fauxfrancis",  # Francis Faux
    "gade",  # Gade
    "gambarini",  # Gambarini
    "martin", "geraldmartin", "martingerald",  # Gerald Martin
    "gillock",  # Gillock
    "ginastera",  # Ginastera
    "gliere",  # Glière
    "goedicke",  # Goedicke
    "gonzaga",  # Gonzaga
    "granados",  # Granados
    "grechaninov",  # Grechaninov
    "grieg",  # Grieg
    "grovlez",  # Grovlez
    "guastavino",  # Guastavino
    "gurlitt",  # Gurlitt
    "simcock", "gwilymsimcock", "simcockgwilym",  # Gwilym Simcock
    "gorres",  # Görres
    "hofmann", "hhofmann", "hofmannh",  # H. Hofmann
    "haslinger",  # Haslinger
    "hammond", "heatherhammond", "hammondheather",  # Heather Hammond
    "madden", "helenmadden", "maddenhelen",  # Helen Madden
    "hensel",  # Hensel
    "hook",  # Hook
    "burgmuller", "jffburgmuller", "burgmullerjff",  # J. F. F. Burgmüller
    "fiocco", "jhfiocco", "fioccojh",  # J. H. Fiocco
    "krebs", "jlkrebs", "krebsjl",  # J. L. Krebs
    "last", "jmlast", "lastjm",  # J. M. Last
    "hummel", "jnhummel", "hummeljn",  # J. N. Hummel
    "metelka", "jakubmetelka", "metelkajakub",  # Jakub Metelka
    "welburn", "jameswelburn", "welburnjames",  # James Welburn
    "sebba", "janesebba", "sebbajane",  # Jane Sebba
    "sifford", "jasonsifford", "siffordjason",  # Jason Sifford
    "bowman", "jenniferbowman", "bowmanjennifer",  # Jennifer Bowman
    "jensen",  # Jensen
    "blake", "jessieblake", "blakejessie",  # Jessie Blake
    "jianer",  # Jian'er
    "kotchie", "jocelynekotchie", "kotchiejocelyne",  # Jocelyn E. Kotchie
    "hisaishi", "joehisaishi", "hisaishijoe",  # Joe Hisaishi
    "rowcroft", "johnrowcroft", "rowcroftjohn",  # John Rowcroft
    "scofield", "johnscofield", "scofieldjohn",  # John Scofield
    "williams", "johnwilliams", "williamsjohn",  # John Williams
    "mitchell", "jonimitchell", "mitchelljoni",  # Joni Mitchell
    "hague", "julieknerrhague", "haguejulieknerr",  # Julie Knerr Hague
    "armstrong", "junearmstrong", "armstrongjune",  # June Armstrong
    "parker", "kparker", "parkerk",  # K. Parker
    "kabalevsky",  # Kabalevsky
    "marshall", "karenmarshall", "marshallkaren",  # Karen Marshall
    "tanaka", "karentanaka", "tanakakaren",  # Karen Tanaka
    "feenstra", "kathleenfeenstra", "feenstrakathleen",  # Kathleen Feenstra
    "kern",  # Kern
    "khachaturian",  # Khachaturian
    "paine", "knowlespaine", "paineknowles",  # Knowles Paine
    "nystedt", "knutnystedt", "nystedtknut",  # Knut Nystedt
    "kuhlau",  # Kuhlau
    "bernstein", "lbernstein", "bernsteinl",  # L. Bernstein
    "kohler", "lkohler", "kohlerl",  # L. Köhler
    "laumenskiene",  # Laumenskienė
    "lennon",  # Lennon
    "liliuokalani",  # Lili'uokalani
    "berwin", "lindseyberwin", "berwinlindsey",  # Lindsey Berwin
    "liszt",  # Liszt
    "chamberlain", "louisechamberlain", "chamberlainlouise",  # Louise Chamberlain
    "drewett", "louisedrewett", "drewettlouise",  # Louise Drewett
    "einaudi", "ludovicoeinaudi", "einaudiludovico",  # Ludovico Einaudi
    "lyadov",  # Lyadov
    "helyer", "mhelyer", "helyerm",  # M. Helyer
    "hill", "mhill", "hillm",  # M. Hill
    "ciurlionis", "mkciurlionis", "ciurlionismk",  # M. K. Čiurlionis
    "mageau",  # Mageau
    "maikapar",  # Maikapar
    "corley", "mariathompsoncorley", "corleymariathompson",  # Maria Thompson Corley
    "goddard", "markgoddard", "goddardmark",  # Mark Goddard
    "tanner", "marktanner", "tannermark",  # Mark Tanner
    "mier", "marthamier", "miermartha",  # Martha Mier
    "martinez",  # Martínez
    "massenet",  # Massenet
    "mchugh",  # McHugh
    "mendelssohn",  # Mendelssohn
    "mercury",  # Mercury
    "messiaen",  # Messiaen
    "cornick", "mikecornick", "cornickmike",  # Mike Cornick
    "gasieniec", "miroslawgasieniec", "gasieniecmiroslaw",  # Mirosław Gąsieniec
    "moszkowski",  # Moszkowski
    "sol", "nahresol", "solnahre",  # Nahre Sol
    "ikeda", "naokoikeda", "ikedanaoko",  # Naoko Ikeda
    "iles", "nikkiiles", "ilesnikki",  # Nikki Iles
    "yeoh", "nikkiyeoh", "yeohnikki",  # Nikki Yeoh
    "okoye", "nkeiruokoye", "okoyenkeiru",  # Nkeiru Okoye
    "russell", "orussell", "russello",  # O. Russell
    "orff",  # Orff
    "wolf", "pewolf", "wolfpe",  # P. E. Wolf
    "hall", "phall", "hallp",  # P. Hall
    "pachulski",  # Pachulski
    "paradies",  # Paradies
    "doyle", "patrickdoyle", "doylepatrick",  # Patrick Doyle
    "harris", "paulharris", "harrispaul",  # Paul Harris
    "harvey", "paulharvey", "harveypaul",  # Paul Harvey
    "peskett", "philpeskett", "peskettphil",  # Phil Peskett
    "lane", "philiplane", "lanephilip",  # Philip Lane
    "piazzolla",  # Piazzolla
    "pinto",  # Pinto
    "purcell",  # Purcell
    "rachmaninoff",  # Rachmaninoff
    "rameau",  # Rameau
    "maxner", "rebekahmaxner", "maxnerrebekah",  # Rebekah Maxner
    "reinecke",  # Reinecke
    "rofe",  # Rofe
    "center", "ronaldcenter", "centerronald",  # Ronald Center
    "rubinstein",  # Rubinstein
    "heller", "sheller", "hellers",  # S. Heller
    "baynes", "santoshbaynes", "baynessantosh",  # Santosh Baynes
    "bareilles", "sarabareilles", "bareillessara",  # Sara Bareilles
    "baker", "sarahbaker", "bakersarah",  # Sarah Baker
    "konecsni", "sarahkonecsni", "konecsnisarah",  # Sarah Konecsni
    "watts", "sarahwatts", "wattssarah",  # Sarah Watts
    "schytte",  # Schytte
    "sculthorpe",  # Sculthorpe
    "chern", "sebastianooiweichern", "chernsebastianooiwei",  # Sebastian Ooi Wei Chern
    "seiber",  # Seiber
    "siegmeister",  # Siegmeister
    "skryabin",  # Skryabin
    "spindler",  # Spindler
    "starer",  # Starer
    "hough", "stephenhough", "houghstephen",  # Stephen Hough
    "schwartz", "stephenschwartz", "schwartzstephen",  # Stephen Schwartz
    "swinstead",  # Swinstead
    "eve", "teve", "evet",  # T. Eve (Ghanaian)
    "kirchner", "tkirchner", "kirchnert",  # T. Kirchner
    "niekludow", "tamaraniekludow", "niekludowtamara",  # Tamara Niekludow
    "swift", "taylorswift", "swifttaylor",  # Taylor Swift
    "telemann",  # Telemann
    "richert", "teresarichert", "richertteresa",  # Teresa Richert
    "garland", "timgarland", "garlandtim",  # Tim Garland
    "turk",  # Türk
    "korn", "uwekorn", "kornuwe",  # Uwe Korn
    "capers", "valeriecapers", "capersvalerie",  # Valerie Capers
    "proudler", "victoriaproudler", "proudlervictoria",  # Victoria Proudler
    "villoldo",  # Villoldo
    "neugasimov", "vitalijneugasimov", "neugasimovvitalij",  # Vitalij Neugasimov
    "carroll", "wcarroll", "carrollw",  # W. Carroll
    "weber",  # Weber
    "withers",  # Withers
    "bowen", "ybowen", "boweny",  # Y. Bowen
    "yamada",  # Yamada
    "dixon", "zoedixon", "dixonzoe",  # Zoe Dixon
}

# --- excluded from COMPOSERS (see naming.py comment block) ---
# Traditional/folk (not personal composer names):
#   African American Spiritual
#   Trad.
#   Trad. Chinese
#   Trad. Chinese (Jiangsu)
#   Trad. Irish
#   Trad. Jamaican
#   Trad. Japanese
#   Trad. Korean
#   Trad. Malay
#   Trad. Moravian
#   Trad. Namibian
#   Trad. Scottish
# Collaborative pop/songwriting credits (pick a representative name per
# song once you know how you'll file it -- not auto-added):
#   Adele Adkins & Greg Kurstin
#   Benny Andersson, Björn Ulvaeus & Anderson
#   Billie Eilish & Finneas O'Connell
#   Ed Sheeran, Samuel Roman, Johnny McDaid, Taylor Swift & Fred Gibson
#   Elton John & Tim Rice
#   George Barnett, Joel Laslett Pott & Fred Gibson
#   Guy Berryman, Jonny Buckland, Will Champion & Chris Martin
#   H. Mancini & J. Mercer
#   Hans Zimmer, Ryan Rubin & Alex Gibson
#   Janet & Alan Bullard
#   John Stephens & Toby Gad
#   Justin Timberlake, Max Martin & Shellback
#   Kristen Anderson-Lopez & Robert Lopez
#   M. David, A. Hoffman & Livingston
#   Melody Bober & Glori Goranson
#   P. Hall & Paul Drayton
#   Smokey Robinson & Ronald White
#   Waller, Razaf & H. Brooks

# ── Known instruments ───────────────────────────────────────────────────────
INSTRUMENTS = {
    "bass", "piano", "violin", "viola", "cello",
    "flute", "oboe", "clarinet", "trumpet", "horn", "organ",
    "satb", "lute",
}

# ── Category vocabulary (canonical) ─────────────────────────────────────────
CATEGORY_PREFIXES = {
    "method":    ["method", "meth"],
    "etude":     ["etude", "étude", "study", "studies"],
    "technique": ["technique", "tech", "exercise", "exercises",
                  "scale", "scales", "arpeggios", "cadences", "fundamentals"],
    "orch":      ["orch", "orchestra", "orchestral", "symphony", "symphonie"],
    "excerpt":   ["excerpt", "excerpts", "audition"],
}

CATEGORY_MAP = {cat.capitalize(): cat.capitalize() for cat in CATEGORY_PREFIXES}

# ── Tokens to preserve exact casing ──────────────────────────────────────────
PRESERVE_CASE = {
    "js": "JS", "cpe": "CPE", "wa": "WA", "jcf": "JCF",
    "bwv": "BWV", "kv": "KV", "op": "Op",
    "vol": "Vol", "book": "Book",
    "i": "I", "ii": "II", "iii": "III", "iv": "IV",
    "v": "V", "vi": "VI", "vii": "VII", "viii": "VIII",
}

OPUS_RE     = re.compile(r"op\.?\s*(\d+)", re.IGNORECASE)
VOLUME_RE   = re.compile(r"(book|vol|volume|part|grade)\s*\.?(\d+)", re.IGNORECASE)
MOVEMENT_RE = re.compile(r"(mvt|mov|movement)\s*\.?(\d+)", re.IGNORECASE)
BWV_RE      = re.compile(r"bwv\s*(\d+)", re.IGNORECASE)
KV_RE       = re.compile(r"k\.?v?\.?\s*(\d+)", re.IGNORECASE)


# Characters unicodedata's NFKD decomposition doesn't split into a base
# letter + combining accent (so a plain "strip combining marks" pass alone
# would leave them untouched).
_ACCENT_TRANSLATE = str.maketrans({
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
})


def normalize_composer(s: str) -> str:
    """Lowercase + strip accents/diacritics + drop non-letters, so composer
    matching is diacritic-insensitive. COMPOSERS stores plain-ASCII tokens
    (e.g. "albeniz", "bartok"), but real scanned filenames keep the accents
    printed on the score ("Albéniz", "Bartók", "Janáček") — without this,
    detect_composer()/is_known_composer() would never match them."""
    s = s.translate(_ACCENT_TRANSLATE)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z]", "", s)
    return s.lower()


def clean(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def to_camel(s: str) -> str:
    words = s.split()
    result = []
    for w in words:
        lower = w.lower()
        if lower in PRESERVE_CASE:
            result.append(PRESERVE_CASE[lower])
        elif not w.isupper() and not w.islower() and w[:1].isupper():
            result.append(w)
        else:
            result.append(w.capitalize())
    return "".join(result)


def detect_category(name_lower: str) -> str:
    words = set(name_lower.split())
    for category, keywords in CATEGORY_PREFIXES.items():
        if words & set(keywords):
            return category
    return "repertoire"


def find_category_keyword(name_lower: str, category: str) -> str | None:
    words = name_lower.split()
    for kw in CATEGORY_PREFIXES.get(category, []):
        if kw in words:
            return kw
    return None


def detect_composer(parts: list) -> tuple:
    max_window = min(3, len(parts))
    for window in range(max_window, 0, -1):
        for i in range(len(parts) - window + 1):
            candidate = parts[i:i + window]
            glued = normalize_composer("".join(candidate))
            if glued in COMPOSERS:
                composer = to_camel(" ".join(candidate))
                remaining = parts[:i] + parts[i + window:]
                return composer, remaining
    return None, parts


def detect_instrument(parts: list) -> tuple:
    for i, part in enumerate(parts):
        if part.lower() in INSTRUMENTS:
            return to_camel(part), parts[:i] + parts[i + 1:]
    return None, parts


def extract_pattern(text: str, pattern: re.Pattern, fmt: str) -> tuple:
    m = pattern.search(text)
    if m:
        value = fmt.format(*m.groups())
        text = text[:m.start()] + text[m.end():]
        return value, text.strip()
    return None, text


def is_known_composer(name: str) -> bool:
    if not name:
        return False
    return normalize_composer(name) in COMPOSERS


def is_known_instrument(name: str) -> bool:
    if not name:
        return False
    return name.lower() in INSTRUMENTS
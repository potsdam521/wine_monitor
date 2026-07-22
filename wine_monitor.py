#!/usr/bin/env python3
"""
Wine Monitor — Costco México + Watchlist + Interactive Dashboard
One script, one run:
  1. Scrapes Costco.com.mx for all wine categories (new wines, price changes).
  2. Checks every product in the WATCHLIST for price changes.
  3. Generates an interactive HTML dashboard (wine_dashboard.html).
  4. Sends a Windows toast notification with a summary.

━━  HOW TO ADD A WATCHLIST PRODUCT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Find the WATCHLIST list below and add a dict:
    { "name": "...", "url": "https://...", "site": "...", "currency": "MXN" }
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import math
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════════════════════════
#  WATCHLIST  ← add / remove products here
# ══════════════════════════════════════════════════════════════════════════════
WATCHLIST = [
    {
        "name"    : "E. Guigal La Landonne Côte Rôtie 750ml",
        "url"     : "https://www.vinoteca.com/vino-tinto-e-guigal-la-landonne-cote-rotie-750-ml/p",
        "site"    : "Vinoteca.com",
        "currency": "MXN",
        "notes"   : "",
    },
    {
        "name"    : "E. Guigal La Turque Côte Rôtie 750ml",
        "url"     : "https://vinosdefrancia.mx/products/cote-rotie-guigal-la-turque",
        "site"    : "VinosdeFrancia.mx",
        "currency": "MXN",
        "notes"   : "",
    },
    {
        "name"    : "E. Guigal La Mouline Côte Rôtie 750ml",
        "url"     : "https://vinosdefrancia.mx/products/cote-rotie-guigal-la-mouline",
        "site"    : "VinosdeFrancia.mx",
        "currency": "MXN",
        "notes"   : "",
    },
    {
        "name"           : "Faustino I Gran Reserva 1995 Tempranillo 750ml",
        "url"            : "https://www.soriana.com/vino-tinto-faustino-i-gran-reserva-1995-tempranillo-750-ml/11714238.html",
        "site"           : "Soriana.com",
        "currency"       : "MXN",
        "notes"          : "",
        "pickup_location": "Pilares",
    },
    {
        "name"           : "Faustino I Gran Reserva 1964 Tempranillo 750ml",
        "url"            : "https://www.soriana.com/vino-tinto-faustino-i-gran-reserva-1964-tempranillo-750-ml/11714226.html",
        "site"           : "Soriana.com",
        "currency"       : "MXN",
        "notes"          : "",
        "pickup_location": "Pilares",
    },
]

# ══════════════════════════════════════════════════════════════════════════════
#  COSTCO CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════
COSTCO_CATEGORIES = [
    ("Vino Tinto",                "https://www.costco.com.mx/Vinos/Vinos/Vino-Tinto/c/cos_21.1.1"),
    ("Vino Blanco",               "https://www.costco.com.mx/Vinos/Vinos/Vino-Blanco/c/cos_21.1.2"),
    ("Vino Espumoso y Champagne", "https://www.costco.com.mx/Vinos/Vinos/Vino-Espumoso-y-Champagne/c/cos_21.1.3"),
    ("Vino Rosado",               "https://www.costco.com.mx/Vinos/Vinos/Vino-Rosado/c/cos_21.1.4"),
    ("Cajas de Vino",             "https://www.costco.com.mx/Vinos/Vinos/Cajas-de-Vino/c/cos_21.1.5"),
    ("Vinos Fortificados",        "https://www.costco.com.mx/Vinos/Vinos/Vinos-Fortificados/c/cos_21.1.6"),
]
COSTCO_PRIORITY = {"Vino Tinto", "Vino Blanco"}

# ══════════════════════════════════════════════════════════════════════════════
#  WINE REGION KEYWORDS  — keyword (lowercase) → (region label, lat, lng, country)
# ══════════════════════════════════════════════════════════════════════════════
REGION_KEYWORDS: dict[str, tuple[str, float, float, str]] = {
    # ── France – Bordeaux ───────────────────────────────────────────────────
    "bordeaux":       ("Bordeaux",      44.838, -0.579, "France"),
    "margaux":        ("Bordeaux",      44.838, -0.579, "France"),
    "pauillac":       ("Bordeaux",      44.838, -0.579, "France"),
    "pomerol":        ("Bordeaux",      44.838, -0.579, "France"),
    "saint-émilion":  ("Bordeaux",      44.838, -0.579, "France"),
    "saint emilion":  ("Bordeaux",      44.838, -0.579, "France"),
    "sauternes":      ("Bordeaux",      44.838, -0.579, "France"),
    "mouton":         ("Bordeaux",      44.838, -0.579, "France"),
    "lafite":         ("Bordeaux",      44.838, -0.579, "France"),
    "petrus":         ("Bordeaux",      44.838, -0.579, "France"),
    "lynch":          ("Bordeaux",      44.838, -0.579, "France"),
    "graves":         ("Bordeaux",      44.838, -0.579, "France"),
    # ── France – Burgundy ───────────────────────────────────────────────────
    "bourgogne":      ("Burgundy",      47.052, 4.385, "France"),
    "burgundy":       ("Burgundy",      47.052, 4.385, "France"),
    "chablis":        ("Burgundy",      47.052, 4.385, "France"),
    "gevrey":         ("Burgundy",      47.052, 4.385, "France"),
    "meursault":      ("Burgundy",      47.052, 4.385, "France"),
    "puligny":        ("Burgundy",      47.052, 4.385, "France"),
    "montrachet":     ("Burgundy",      47.052, 4.385, "France"),
    "romanee":        ("Burgundy",      47.052, 4.385, "France"),
    "nuits":          ("Burgundy",      47.052, 4.385, "France"),
    "beaune":         ("Burgundy",      47.052, 4.385, "France"),
    "pommard":        ("Burgundy",      47.052, 4.385, "France"),
    # ── France – Champagne ─────────────────────────────────────────────────
    "champagne":      ("Champagne",     49.044, 4.023, "France"),
    "moët":           ("Champagne",     49.044, 4.023, "France"),
    "moet":           ("Champagne",     49.044, 4.023, "France"),
    "veuve":          ("Champagne",     49.044, 4.023, "France"),
    "dom pérignon":   ("Champagne",     49.044, 4.023, "France"),
    "krug":           ("Champagne",     49.044, 4.023, "France"),
    "bollinger":      ("Champagne",     49.044, 4.023, "France"),
    "ruinart":        ("Champagne",     49.044, 4.023, "France"),
    "perrier-jouët":  ("Champagne",     49.044, 4.023, "France"),
    # ── France – Rhône ─────────────────────────────────────────────────────
    "rhône":          ("Rhône Valley",  44.143, 4.808, "France"),
    "rhone":          ("Rhône Valley",  44.143, 4.808, "France"),
    "côte rôtie":     ("Rhône Valley",  45.478, 4.791, "France"),
    "cote rotie":     ("Rhône Valley",  45.478, 4.791, "France"),
    "châteauneuf":    ("Rhône Valley",  44.055, 4.834, "France"),
    "chateauneuf":    ("Rhône Valley",  44.055, 4.834, "France"),
    "hermitage":      ("Rhône Valley",  45.073, 4.840, "France"),
    "condrieu":       ("Rhône Valley",  45.462, 4.774, "France"),
    "crozes":         ("Rhône Valley",  45.073, 4.840, "France"),
    "gigondas":       ("Rhône Valley",  44.174, 4.984, "France"),
    "guigal":         ("Rhône Valley",  45.478, 4.791, "France"),
    "jaboulet":       ("Rhône Valley",  45.073, 4.840, "France"),
    "chapoutier":     ("Rhône Valley",  45.073, 4.840, "France"),
    # ── France – Alsace / Loire / Provence ─────────────────────────────────
    "alsace":         ("Alsace",        48.265, 7.444, "France"),
    "gewurztraminer": ("Alsace",        48.265, 7.444, "France"),
    "trimbach":       ("Alsace",        48.265, 7.444, "France"),
    "sancerre":       ("Loire Valley",  47.330, 2.841, "France"),
    "pouilly":        ("Loire Valley",  47.291, 2.963, "France"),
    "muscadet":       ("Loire Valley",  47.227, -1.553, "France"),
    "vouvray":        ("Loire Valley",  47.394, 0.788, "France"),
    "chinon":         ("Loire Valley",  47.167, 0.242, "France"),
    "provence":       ("Provence",      43.528, 5.450, "France"),
    "bandol":         ("Provence",      43.132, 5.753, "France"),
    "languedoc":      ("Languedoc",     43.503, 3.356, "France"),
    "roussillon":     ("Languedoc",     42.694, 2.895, "France"),
    # ── Italy – Tuscany ────────────────────────────────────────────────────
    "toscana":        ("Tuscany",       43.771, 11.249, "Italy"),
    "tuscany":        ("Tuscany",       43.771, 11.249, "Italy"),
    "chianti":        ("Tuscany",       43.546, 11.188, "Italy"),
    "brunello":       ("Tuscany",       43.057, 11.489, "Italy"),
    "montalcino":     ("Tuscany",       43.057, 11.489, "Italy"),
    "bolgheri":       ("Tuscany",       43.231, 10.592, "Italy"),
    "sassicaia":      ("Tuscany",       43.231, 10.592, "Italy"),
    "ornellaia":      ("Tuscany",       43.231, 10.592, "Italy"),
    "tignanello":     ("Tuscany",       43.546, 11.188, "Italy"),
    "antinori":       ("Tuscany",       43.771, 11.249, "Italy"),
    "frescobaldi":    ("Tuscany",       43.771, 11.249, "Italy"),
    # ── Italy – Piedmont ───────────────────────────────────────────────────
    "barolo":         ("Piedmont",      44.609, 7.939, "Italy"),
    "barbaresco":     ("Piedmont",      44.705, 8.044, "Italy"),
    "piemonte":       ("Piedmont",      44.901, 7.860, "Italy"),
    "nebbiolo":       ("Piedmont",      44.901, 7.860, "Italy"),
    "barbera":        ("Piedmont",      44.901, 7.860, "Italy"),
    "dolcetto":       ("Piedmont",      44.901, 7.860, "Italy"),
    "gavi":           ("Piedmont",      44.691, 8.803, "Italy"),
    "gaja":           ("Piedmont",      44.901, 7.860, "Italy"),
    # ── Italy – Veneto / Sicily / Other ────────────────────────────────────
    "amarone":        ("Veneto",        45.526, 10.975, "Italy"),
    "valpolicella":   ("Veneto",        45.526, 10.975, "Italy"),
    "prosecco":       ("Veneto",        45.872, 12.198, "Italy"),
    "soave":          ("Veneto",        45.420, 11.250, "Italy"),
    "veneto":         ("Veneto",        45.465, 11.877, "Italy"),
    "allegrini":      ("Veneto",        45.526, 10.975, "Italy"),
    "sicilia":        ("Sicily",        37.599, 14.015, "Italy"),
    "sicily":         ("Sicily",        37.599, 14.015, "Italy"),
    "etna":           ("Sicily",        37.751, 15.005, "Italy"),
    "nero d'avola":   ("Sicily",        37.599, 14.015, "Italy"),
    "montepulciano":  ("Abruzzo",       42.350, 13.398, "Italy"),
    "abruzzo":        ("Abruzzo",       42.350, 13.398, "Italy"),
    # ── Spain – Rioja ──────────────────────────────────────────────────────
    "rioja":          ("Rioja",         42.467, -2.450, "Spain"),
    "tempranillo":    ("Rioja",         42.467, -2.450, "Spain"),
    "muga":           ("Rioja",         42.467, -2.450, "Spain"),
    "campo viejo":    ("Rioja",         42.467, -2.450, "Spain"),
    "beronia":        ("Rioja",         42.467, -2.450, "Spain"),
    "faustino":       ("Rioja",         42.467, -2.450, "Spain"),
    "cvne":           ("Rioja",         42.467, -2.450, "Spain"),
    "marques de riscal": ("Rioja",      42.467, -2.450, "Spain"),
    "marqués de riscal": ("Rioja",      42.467, -2.450, "Spain"),
    # ── Spain – Ribera / Priorat / Penedès ─────────────────────────────────
    "ribera del duero": ("Ribera del Duero", 41.648, -3.700, "Spain"),
    "vega sicilia":   ("Ribera del Duero", 41.648, -3.700, "Spain"),
    "pesquera":       ("Ribera del Duero", 41.648, -3.700, "Spain"),
    "protos":         ("Ribera del Duero", 41.648, -3.700, "Spain"),
    "priorat":        ("Priorat",       41.200, 0.759, "Spain"),
    "penedès":        ("Penedès",       41.350, 1.723, "Spain"),
    "penedes":        ("Penedès",       41.350, 1.723, "Spain"),
    "torres":         ("Penedès",       41.350, 1.723, "Spain"),
    "rias baixas":    ("Rías Baixas",   42.423, -8.645, "Spain"),
    "albariño":       ("Rías Baixas",   42.423, -8.645, "Spain"),
    "albarino":       ("Rías Baixas",   42.423, -8.645, "Spain"),
    "jerez":          ("Jerez",         36.687, -6.137, "Spain"),
    "sherry":         ("Jerez",         36.687, -6.137, "Spain"),
    # ── Argentina ──────────────────────────────────────────────────────────
    "mendoza":        ("Mendoza",       -32.890, -68.846, "Argentina"),
    "malbec":         ("Mendoza",       -32.890, -68.846, "Argentina"),
    "zuccardi":       ("Mendoza",       -32.890, -68.846, "Argentina"),
    "catena":         ("Mendoza",       -32.890, -68.846, "Argentina"),
    "achaval":        ("Mendoza",       -32.890, -68.846, "Argentina"),
    "norton":         ("Mendoza",       -32.890, -68.846, "Argentina"),
    "rutini":         ("Mendoza",       -32.890, -68.846, "Argentina"),
    "luján de cuyo":  ("Mendoza",       -33.052, -68.878, "Argentina"),
    "lujan de cuyo":  ("Mendoza",       -33.052, -68.878, "Argentina"),
    "valle de uco":   ("Valle de Uco",  -33.679, -69.180, "Argentina"),
    "cafayate":       ("Salta",         -26.072, -65.976, "Argentina"),
    "salta":          ("Salta",         -24.782, -65.423, "Argentina"),
    "torrontés":      ("Salta",         -26.072, -65.976, "Argentina"),
    "torrontes":      ("Salta",         -26.072, -65.976, "Argentina"),
    "patagonia":      ("Patagonia",     -40.091, -71.310, "Argentina"),
    "neuquén":        ("Patagonia",     -38.952, -68.059, "Argentina"),
    # ── Chile ──────────────────────────────────────────────────────────────
    "maipo":          ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "concha y toro":  ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "concha":         ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "don melchor":    ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "almaviva":       ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "santa rita":     ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "undurraga":      ("Valle del Maipo",    -33.624, -70.587, "Chile"),
    "colchagua":      ("Valle de Colchagua", -34.578, -71.077, "Chile"),
    "lapostolle":     ("Valle de Colchagua", -34.578, -71.077, "Chile"),
    "montes":         ("Valle de Colchagua", -34.578, -71.077, "Chile"),
    "casablanca":     ("Valle de Casablanca",-33.329, -71.405, "Chile"),
    "veramonte":      ("Valle de Casablanca",-33.329, -71.405, "Chile"),
    "errázuriz":      ("Aconcagua",     -32.834, -70.598, "Chile"),
    "errazuriz":      ("Aconcagua",     -32.834, -70.598, "Chile"),
    "seña":           ("Aconcagua",     -32.834, -70.598, "Chile"),
    "maule":          ("Valle del Maule", -35.426, -71.670, "Chile"),
    # ── USA ────────────────────────────────────────────────────────────────
    "napa":           ("Napa Valley",   38.503, -122.265, "USA"),
    "opus one":       ("Napa Valley",   38.503, -122.265, "USA"),
    "caymus":         ("Napa Valley",   38.503, -122.265, "USA"),
    "silver oak":     ("Napa Valley",   38.503, -122.265, "USA"),
    "mondavi":        ("Napa Valley",   38.503, -122.265, "USA"),
    "duckhorn":       ("Napa Valley",   38.503, -122.265, "USA"),
    "beringer":       ("Napa Valley",   38.503, -122.265, "USA"),
    "stags leap":     ("Napa Valley",   38.503, -122.265, "USA"),
    "sonoma":         ("Sonoma County", 38.292, -122.458, "USA"),
    "kendall":        ("Sonoma County", 38.292, -122.458, "USA"),
    "california":     ("California",    36.778, -119.418, "USA"),
    "oregon":         ("Oregon",        45.523, -122.677, "USA"),
    "willamette":     ("Oregon",        45.523, -122.677, "USA"),
    "washington":     ("Washington St.",46.885, -120.263, "USA"),
    # ── Mexico ─────────────────────────────────────────────────────────────
    "guadalupe":      ("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "baja california": ("Valle de Guadalupe",31.875, -116.593, "Mexico"),
    "l.a. cetto":     ("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "la cetto":       ("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "monte xanic":    ("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "adobe guadalupe":("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "casa de piedra": ("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "vena cava":      ("Valle de Guadalupe", 31.875, -116.593, "Mexico"),
    "parras":         ("Valle de Parras",    25.444, -102.176, "Mexico"),
    "casa madero":    ("Valle de Parras",    25.444, -102.176, "Mexico"),
    "madero":         ("Valle de Parras",    25.444, -102.176, "Mexico"),
    # ── Australia ──────────────────────────────────────────────────────────
    "barossa":        ("Barossa Valley", -34.531, 138.955, "Australia"),
    "penfolds":       ("Barossa Valley", -34.531, 138.955, "Australia"),
    "wolf blass":     ("Barossa Valley", -34.531, 138.955, "Australia"),
    "jacob's creek":  ("Barossa Valley", -34.531, 138.955, "Australia"),
    "jacobs creek":   ("Barossa Valley", -34.531, 138.955, "Australia"),
    "margaret river": ("Margaret River", -33.952, 115.079, "Australia"),
    "hunter":         ("Hunter Valley",  -32.779, 151.174, "Australia"),
    "mclaren vale":   ("McLaren Vale",   -35.222, 138.555, "Australia"),
    "coonawarra":     ("Coonawarra",     -37.293, 140.824, "Australia"),
    "yarra":          ("Yarra Valley",   -37.790, 145.570, "Australia"),
    # ── South Africa ───────────────────────────────────────────────────────
    "stellenbosch":   ("Stellenbosch",  -33.932, 18.860, "South Africa"),
    "pinotage":       ("Stellenbosch",  -33.932, 18.860, "South Africa"),
    "kanonkop":       ("Stellenbosch",  -33.932, 18.860, "South Africa"),
    "franschhoek":    ("Franschhoek",   -33.912, 19.126, "South Africa"),
    "paarl":          ("Paarl",         -33.734, 18.975, "South Africa"),
    "cape":           ("Western Cape",  -33.925, 18.424, "South Africa"),
    # ── Portugal ───────────────────────────────────────────────────────────
    "douro":          ("Douro Valley",  41.192, -7.699, "Portugal"),
    "porto":          ("Douro Valley",  41.145, -8.612, "Portugal"),
    "quinta":         ("Douro Valley",  41.192, -7.699, "Portugal"),
    "graham":         ("Douro Valley",  41.192, -7.699, "Portugal"),
    "sandeman":       ("Douro Valley",  41.192, -7.699, "Portugal"),
    "taylor":         ("Douro Valley",  41.192, -7.699, "Portugal"),
    "alentejo":       ("Alentejo",      38.478, -8.021, "Portugal"),
    "vinho verde":    ("Vinho Verde",   41.827, -8.545, "Portugal"),
    # ── Germany / NZ / Greece ──────────────────────────────────────────────
    "mosel":          ("Mosel",         49.993, 7.169, "Germany"),
    "rheingau":       ("Rheingau",      50.013, 8.001, "Germany"),
    "riesling":       ("Mosel",         49.993, 7.169, "Germany"),
    "pfalz":          ("Pfalz",         49.380, 8.200, "Germany"),
    "marlborough":    ("Marlborough",   -41.513, 173.961, "New Zealand"),
    "cloudy bay":     ("Marlborough",   -41.513, 173.961, "New Zealand"),
    "kim crawford":   ("Marlborough",   -41.513, 173.961, "New Zealand"),
    "santorini":      ("Santorini",     36.393, 25.462, "Greece"),
    "assyrtiko":      ("Santorini",     36.393, 25.462, "Greece"),
    "xinomavro":      ("Macedonia GR",  40.628, 22.071, "Greece"),
}

# ══════════════════════════════════════════════════════════════════════════════
#  FILE PATHS
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR                = Path(__file__).parent.resolve()

COSTCO_LATEST_FILE      = BASE_DIR / "wine_list_latest.json"
COSTCO_HISTORY_FILE     = BASE_DIR / "wine_price_history.json"
COSTCO_FINDINGS_FILE    = BASE_DIR / "costco_wine_findings.txt"
WATCHLIST_HISTORY_FILE  = BASE_DIR / "watchlist_price_history.json"
WATCHLIST_FINDINGS_FILE = BASE_DIR / "watchlist_findings.txt"
TLWM_LATEST_FILE        = BASE_DIR / "tlwm_list_latest.json"
TLWM_HISTORY_FILE       = BASE_DIR / "tlwm_price_history.json"
TLWM_FINDINGS_FILE      = BASE_DIR / "tlwm_findings.txt"
DASHBOARD_FILE          = BASE_DIR / "wine_dashboard.html"
LOG_FILE                = BASE_DIR / "wine_monitor.log"

TLWM_BASE_URL = "https://www.thelittlewinemarket.com"

PAGE_SLEEP     = 1.5
CATEGORY_SLEEP = 2.0
PRODUCT_SLEEP  = 2.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  SHARED UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
DIVIDER = "═" * 72
THIN    = "─" * 58


def parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(raw).replace(",", "").strip())
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def fmt_price(amount: float | None, currency: str = "MXN") -> str:
    if amount is None:
        return "(precio no disponible)"
    return f"${amount:,.2f} {currency}"


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.warning("Could not load %s: %s", path, exc)
    return {}


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prepend_to_file(path: Path, block: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    with open(path, "w", encoding="utf-8") as f:
        f.write(block)
        if existing:
            f.write(existing)


def send_toast(title: str, message: str) -> None:
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.BalloonTipIcon  = 'Info'
$n.BalloonTipTitle = '{title.replace("'","''")}'
$n.BalloonTipText  = '{message.replace("'","''")}'
$n.Visible = $True
$n.ShowBalloonTip(8000)
Start-Sleep -Milliseconds 9000
$n.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log.warning("Toast failed: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
#  COSTCO MONITOR
# ══════════════════════════════════════════════════════════════════════════════

def _costco_extract_price(item_tag) -> tuple[float | None, str]:
    for sel in [".product-price-amount", ".price", ".product-price", ".js-price",
                ".priceValue", ".productPrice", "[class*='price'] span",
                "[class*='Price']", "span.value", ".item-price"]:
        try:
            el = item_tag.select_one(sel)
        except Exception:
            continue
        if el:
            raw = el.get_text(strip=True)
            val = parse_price(raw)
            if val:
                return val, raw
    for tag in item_tag.find_all(True):
        text = tag.get_text(strip=True)
        if re.match(r"^\$[\d,]+\.\d{2}$", text):
            val = parse_price(text)
            if val:
                return val, text
    return None, ""


def costco_scrape_category(cat_name: str, base_url: str) -> list[dict]:
    products: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)
    page_num = 0
    while True:
        url = base_url if page_num == 0 else f"{base_url}?page={page_num}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("  Costco fetch failed [%s] p%d: %s", cat_name, page_num + 1, exc)
            break
        soup  = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.product-list-item") or \
                soup.select("sip-product-list-item") or \
                soup.select("li[class*='product']")
        if not items:
            break
        for item in items:
            thumb = item.select_one("a.thumb[title]") or item.select_one("a[title]")
            if not thumb:
                continue
            name = thumb.get("title", "").strip()
            if not name:
                continue
            href = thumb.get("href", "")
            url  = ("https://www.costco.com.mx" + href) if href.startswith("/") else href
            price, price_raw = _costco_extract_price(item)
            products.append({"name": name, "price": price, "price_raw": price_raw, "url": url})
        hrefs = [a.get("href", "") for a in soup.select("a.page-link[href*='page=']")]
        if not hrefs:
            break
        max_p = max((int(m.group(1)) for h in hrefs if (m := re.search(r"page=(\d+)", h))), default=0)
        if page_num + 1 > max_p:
            break
        page_num += 1
        time.sleep(PAGE_SLEEP)
    log.info("  %-30s  %d vinos  (%d con precio)",
             cat_name, len(products), sum(1 for p in products if p["price"]))
    return products


def costco_scrape_all() -> dict:
    log.info("── Costco: scraping costco.com.mx …")
    results = {}
    for i, (cat, url) in enumerate(COSTCO_CATEGORIES):
        results[cat] = costco_scrape_category(cat, url)
        if i < len(COSTCO_CATEGORIES) - 1:
            time.sleep(CATEGORY_SLEEP)
    log.info("── Costco: %d vinos en %d categorías",
             sum(len(v) for v in results.values()), len(results))
    return results


def costco_update_history(history: dict, snapshot: dict, today: str) -> dict:
    for cat, products in snapshot.items():
        history.setdefault(cat, {})
        for p in products:
            price = p.get("price")
            if price is None:
                continue
            entries = history[cat].setdefault(p["name"], [])
            if not entries or entries[-1]["price"] != price:
                entries.append({"date": today, "price": price})
    return history


def _name_price_map(products) -> dict:
    return {p["name"]: p.get("price") if isinstance(p, dict) else None
            for p in products
            if (isinstance(p, dict) and p.get("name")) or isinstance(p, str)}


def costco_compare(prev: dict, curr: dict) -> dict:
    new_wines: dict = {}; removed: dict = {}; drops: dict = {}; increases: dict = {}
    for cat in set(list(prev) + list(curr)):
        pm = _name_price_map(prev.get(cat, []))
        cm = _name_price_map([p for p in curr.get(cat, []) if isinstance(p, dict)])
        for name in cm:
            if name not in pm:
                prod = next((p for p in curr.get(cat, []) if isinstance(p, dict) and p["name"] == name), {})
                new_wines.setdefault(cat, []).append(prod)
        for name in pm:
            if name not in cm:
                removed.setdefault(cat, []).append(name)
        for name, np in cm.items():
            op = pm.get(name)
            if name not in pm or op is None or np is None:
                continue
            if np < op:
                pct = (op - np) / op * 100
                drops.setdefault(cat, []).append({"name": name, "old": op, "new": np, "pct": pct, "saving": op - np})
            elif np > op:
                pct = (np - op) / op * 100
                increases.setdefault(cat, []).append({"name": name, "old": op, "new": np, "pct": pct, "extra": np - op})
    for d in [drops, increases]:
        for cat in d:
            d[cat].sort(key=lambda x: x["pct"], reverse=True)
    return {"new_wines": new_wines, "removed_wines": removed,
            "price_drops": drops, "price_increases": increases}


def _ordered_cats(d: dict) -> list:
    return [c for c in d if c in COSTCO_PRIORITY] + [c for c in d if c not in COSTCO_PRIORITY]


def costco_build_baseline(snapshot: dict, today: str) -> str:
    lines = [DIVIDER, f"  COSTCO WINE MONITOR — {today}", DIVIDER,
             "  [BASELINE — PRIMERA CORRIDA]", "", "  Vinos por categoría:", ""]
    total = 0
    for cat, _ in COSTCO_CATEGORIES:
        c = len(snapshot.get(cat, [])); total += c
        lines.append(f"    [{cat}]  {c} vinos")
    lines += ["", f"  TOTAL: {total} vinos", DIVIDER, ""]
    return "\n".join(lines)


def costco_build_report(changes: dict, today: str) -> str:
    nw = changes["new_wines"]; rw = changes["removed_wines"]
    pd = changes["price_drops"]; pi = changes["price_increases"]
    tn = sum(len(v) for v in nw.values()); tr = sum(len(v) for v in rw.values())
    td = sum(len(v) for v in pd.values()); ti = sum(len(v) for v in pi.values())
    lines = [DIVIDER, f"  COSTCO WINE MONITOR — {today}", DIVIDER, ""]
    lines += [f"  🍷 NUEVOS VINOS  ({tn})", f"  {THIN}"]
    if tn == 0:
        lines.append("  (ningún vino nuevo)")
    else:
        pn = {c: v for c, v in nw.items() if c in COSTCO_PRIORITY}
        on = {c: v for c, v in nw.items() if c not in COSTCO_PRIORITY}
        if pn:
            lines += ["", "  ⭐ TINTOS & BLANCOS:"]
            for cat in _ordered_cats(pn):
                lines.append(f"    [{cat}]")
                for p in pn[cat]:
                    ps = fmt_price(p.get("price")) if p.get("price") else "(sin precio)"
                    lines.append(f"      • {p.get('name','?')}   {ps}")
        if on:
            lines += ["", "  OTRAS:"]
            for cat in _ordered_cats(on):
                lines.append(f"    [{cat}]")
                for p in on[cat]:
                    ps = fmt_price(p.get("price")) if p.get("price") else "(sin precio)"
                    lines.append(f"      • {p.get('name','?')}   {ps}")
    lines.append("")
    lines += [f"  📉 DESCUENTOS  ({td})", f"  {THIN}"]
    if td == 0:
        lines.append("  (ninguno)")
    else:
        for cat in _ordered_cats(pd):
            lines.append(f"    [{cat}]")
            for d in pd[cat]:
                lines += [f"      ▼ {d['name']}",
                          f"        Antes: {fmt_price(d['old'])}  →  Ahora: {fmt_price(d['new'])}"
                          f"   (-{d['pct']:.1f}%,  ahorras {fmt_price(d['saving'])})"]
    lines.append("")
    lines += [f"  📈 ALZAS  ({ti})", f"  {THIN}"]
    if ti == 0:
        lines.append("  (ninguna)")
    else:
        for cat in _ordered_cats(pi):
            lines.append(f"    [{cat}]")
            for d in pi[cat]:
                lines += [f"      ▲ {d['name']}",
                          f"        Antes: {fmt_price(d['old'])}  →  Ahora: {fmt_price(d['new'])}"
                          f"   (+{d['pct']:.1f}%,  sube {fmt_price(d['extra'])})"]
    lines.append("")
    if tr > 0:
        lines += [f"  ❌ RETIRADOS  ({tr})", f"  {THIN}"]
        for cat in _ordered_cats(rw):
            lines.append(f"    [{cat}]")
            for name in rw[cat]:
                lines.append(f"      • {name}")
        lines.append("")
    lines += [DIVIDER, ""]
    return "\n".join(lines)


def run_costco(today: str):
    prev     = load_json(COSTCO_LATEST_FILE) or None
    history  = load_json(COSTCO_HISTORY_FILE)
    current  = costco_scrape_all()
    history  = costco_update_history(history, current, today)
    save_json(COSTCO_HISTORY_FILE, history)
    if not prev:
        save_json(COSTCO_LATEST_FILE, current)
        prepend_to_file(COSTCO_FINDINGS_FILE, costco_build_baseline(current, today))
        log.info("Costco baseline guardado — %d vinos", sum(len(v) for v in current.values()))
        return current, None, history
    changes = costco_compare(prev, current)
    prepend_to_file(COSTCO_FINDINGS_FILE, costco_build_report(changes, today))
    save_json(COSTCO_LATEST_FILE, current)
    n_new = sum(len(v) for v in changes["new_wines"].values())
    n_d   = sum(len(v) for v in changes["price_drops"].values())
    n_i   = sum(len(v) for v in changes["price_increases"].values())
    n_r   = sum(len(v) for v in changes["removed_wines"].values())
    log.info("Costco → Nuevos: %d  Descuentos: %d  Alzas: %d  Retirados: %d", n_new, n_d, n_i, n_r)
    return current, changes, history


# ══════════════════════════════════════════════════════════════════════════════
#  WATCHLIST MONITOR
# ══════════════════════════════════════════════════════════════════════════════

def watchlist_extract_price(soup: BeautifulSoup, hint: str | None = None) -> float | None:
    if hint:
        el = soup.select_one(hint)
        if el:
            val = parse_price(el.get_text(strip=True))
            if val:
                return val
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            for obj in (data if isinstance(data, list) else [data]):
                offers = obj.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                pv = offers.get("price") or obj.get("price")
                if pv:
                    val = parse_price(str(pv))
                    if val:
                        return val
        except Exception:
            continue
    for prop in ["product:price:amount", "og:price:amount"]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            val = parse_price(el["content"])
            if val:
                return val
    el = soup.find(attrs={"itemprop": "price"})
    if el:
        val = parse_price(el.get("content") or el.get_text(strip=True))
        if val:
            return val
    for sel in [".skuBestPrice", ".bestPrice", "[class*='sellingPrice']",
                "[class*='bestPrice']", ".price", ".product-price", ".js-price",
                ".priceValue", ".productPrice", "[class*='price'] span",
                "span.value", ".item-price", ".sale-price", ".current-price"]:
        try:
            el = soup.select_one(sel)
        except Exception:
            continue
        if el:
            val = parse_price(el.get_text(strip=True))
            if val:
                return val
    for tag in soup.find_all(["span", "div", "p", "strong", "b"]):
        text = tag.get_text(strip=True)
        if re.match(r"^\$[\d,]+(?:\.\d{1,2})?$", text):
            val = parse_price(text)
            if val:
                return val
    return None


def selenium_fetch_price(url: str, pickup_location: str | None = None) -> float | None:
    """
    Fetch price from a JS-heavy site using headless Chrome.
    If pickup_location is given (e.g. 'Pilares'), attempts to set it before reading the price.
    Requires: pip install selenium webdriver-manager
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        log.error("Selenium not installed. Run: pip install selenium webdriver-manager")
        return None

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-background-networking")   # suppresses GCM/push errors
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-logging")
    opts.add_argument("--log-level=3")                     # FATAL only
    opts.add_argument("--silent")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        service = Service(
            ChromeDriverManager().install(),
            log_path="NUL",                                # suppress chromedriver console output
        )
        driver = webdriver.Chrome(service=service, options=opts)
        driver.set_page_load_timeout(30)          # hard cap: never hang on page load
        driver.set_script_timeout(15)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
        )
        try:
            driver.get(url)
        except Exception as exc:
            log.warning("  selenium page load timeout/error: %s", exc)
            # Continue — partial page may still have price data

        # ── Set pickup location (Soriana / VTEX) ────────────────────────────
        if pickup_location:
            # Wait briefly for the store-picker button to appear
            short_wait = WebDriverWait(driver, 5)
            picker_sels = [
                "[class*='store-selector'] button",
                "[class*='pickup'] button",
                "button[class*='location']",
                "[class*='addressBar'] button",
                "[data-testid*='location']",
                "span[class*='address']",
                ".vtex-store-header button",
            ]
            for sel in picker_sels:
                try:
                    btn = short_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
                    inp_sels = [
                        "input[placeholder*='código postal']",
                        "input[placeholder*='Código Postal']",
                        "input[placeholder*='buscar']",
                        "input[placeholder*='Buscar']",
                        "input[placeholder*='ubicación']",
                        "input[type='search']",
                        "[class*='modal'] input[type='text']",
                    ]
                    for isel in inp_sels:
                        try:
                            inp = driver.find_element(By.CSS_SELECTOR, isel)
                            inp.clear()
                            inp.send_keys(pickup_location)
                            time.sleep(2)
                            for rsel in [
                                "[class*='result']:first-child",
                                "li[class*='item']:first-child",
                                "[class*='store-list'] li:first-child",
                                "[class*='option']:first-child",
                            ]:
                                try:
                                    res = driver.find_element(By.CSS_SELECTOR, rsel)
                                    driver.execute_script("arguments[0].click();", res)
                                    time.sleep(2)
                                    break
                                except Exception:
                                    continue
                            break
                        except Exception:
                            continue
                    break
                except Exception:
                    continue

        # ── Extract price — one single wait, then fast find_elements scan ────
        # Wait up to 10 s for ANY price-like element to appear, then read all candidates
        price_sels = [
            ".vtex-product-price-1-x-sellingPriceValue",
            ".vtex-product-price-1-x-sellingPrice",
            "[class*='sellingPriceValue']",
            "[class*='sellingPrice']",
            "[class*='bestPrice']",
            "[class*='price-best']",
            "[class*='ProductPrice']",
            "[data-testid='price']",
            ".price",
            ".product-price",
        ]
        combined = ", ".join(price_sels)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, combined))
            )
        except Exception:
            pass  # page may still have partial data — try anyway

        for sel in price_sels:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                val = parse_price(
                    el.text.strip() or el.get_attribute("content") or ""
                )
                if val:
                    log.debug("  selenium price via '%s': %s", sel, val)
                    return val

        # Last resort: parse rendered HTML with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        return watchlist_extract_price(soup)

    except Exception as exc:
        log.warning("  selenium_fetch_price error: %s", exc)
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def _needs_browser(product: dict) -> bool:
    return bool(product.get("pickup_location") or product.get("requires_browser"))


def watchlist_fetch_group(browser: bool) -> list[dict]:
    """Fetch the fast (requests) or slow (browser) subset of WATCHLIST."""
    group = [p for p in WATCHLIST if _needs_browser(p) == browser]
    if not group:
        return []
    label = "browser" if browser else "fast"
    log.info("── Watchlist [%s]: %d producto(s) …", label, len(group))
    session = requests.Session()
    session.headers.update(HEADERS)
    results = []
    for i, product in enumerate(group):
        r = {"name": product["name"], "url": product["url"], "site": product["site"],
             "currency": product.get("currency", "MXN"), "price": None, "error": None,
             "pending": False}
        pickup = product.get("pickup_location")
        try:
            if browser:
                log.info("  %-50s  [browser] pickup=%s", product["name"][:50], pickup or "—")
                price = selenium_fetch_price(product["url"], pickup)
            else:
                resp = session.get(product["url"], timeout=30)
                resp.raise_for_status()
                price = watchlist_extract_price(BeautifulSoup(resp.text, "html.parser"),
                                                product.get("price_selector"))
            r["price"] = price
            log.info("  %-50s  %s", product["name"][:50],
                     fmt_price(price, r["currency"]) if price else "⚠️  sin precio")
        except requests.RequestException as exc:
            r["error"] = str(exc)
            log.warning("  %-50s  ERROR: %s", product["name"][:50], exc)
        except Exception as exc:
            r["error"] = str(exc)
            log.warning("  %-50s  ERROR: %s", product["name"][:50], exc)
        results.append(r)
        if i < len(group) - 1:
            time.sleep(PRODUCT_SLEEP)
    return results


def watchlist_pending_placeholders() -> list[dict]:
    """Return placeholder rows for browser-based items (shown while Selenium runs)."""
    return [
        {"name": p["name"], "url": p["url"], "site": p["site"],
         "currency": p.get("currency", "MXN"), "price": None, "error": None, "pending": True}
        for p in WATCHLIST if _needs_browser(p)
    ]


def watchlist_fetch_all() -> list[dict]:
    """Legacy helper — fetches all items sequentially (fast then browser)."""
    return watchlist_fetch_group(browser=False) + watchlist_fetch_group(browser=True)


def watchlist_update_history(history: dict, results: list[dict], today: str) -> dict:
    for r in results:
        if r["price"] is None:
            continue
        entries = history.setdefault(r["url"], [])
        if not entries or entries[-1]["price"] != r["price"]:
            entries.append({"date": today, "price": r["price"]})
    return history


def watchlist_prev_price(history: dict, url: str) -> float | None:
    entries = history.get(url, [])
    return entries[-2]["price"] if len(entries) >= 2 else None


def watchlist_build_report(results: list[dict], history: dict, today: str) -> str:
    drops: list = []; increases: list = []; unchanged: list = []
    no_price: list = []; errors: list = []
    for r in results:
        if r["error"]:       errors.append(r); continue
        if r["price"] is None: no_price.append(r); continue
        prev = watchlist_prev_price(history, r["url"])
        if prev is None:
            unchanged.append({**r, "prev": None, "first_seen": True})
        elif r["price"] < prev:
            pct = (prev - r["price"]) / prev * 100
            drops.append({**r, "prev": prev, "pct": pct, "saving": prev - r["price"]})
        elif r["price"] > prev:
            pct = (r["price"] - prev) / prev * 100
            increases.append({**r, "prev": prev, "pct": pct, "extra": r["price"] - prev})
        else:
            unchanged.append({**r, "prev": prev, "first_seen": False})
    drops.sort(key=lambda x: x["pct"], reverse=True)
    increases.sort(key=lambda x: x["pct"], reverse=True)
    lines = [DIVIDER, f"  WATCHLIST MONITOR — {today}", DIVIDER, ""]
    lines += [f"  📉 PRECIO MÁS BAJO  ({len(drops)})", f"  {THIN}"]
    if not drops:
        lines.append("  (ninguno)")
    else:
        for d in drops:
            lines += [f"    ▼ {d['name']}",
                      f"      {d['site']}  |  Antes: {fmt_price(d['prev'],d['currency'])}  →  "
                      f"Ahora: {fmt_price(d['price'],d['currency'])}  (-{d['pct']:.1f}%)", ""]
    lines.append("")
    lines += [f"  📈 ALZAS  ({len(increases)})", f"  {THIN}"]
    if not increases:
        lines.append("  (ninguna)")
    else:
        for d in increases:
            lines += [f"    ▲ {d['name']}",
                      f"      {d['site']}  |  Antes: {fmt_price(d['prev'],d['currency'])}  →  "
                      f"Ahora: {fmt_price(d['price'],d['currency'])}  (+{d['pct']:.1f}%)", ""]
    lines.append("")
    lines += [f"  ✅ SIN CAMBIO  ({len(unchanged)})", f"  {THIN}"]
    for d in unchanged:
        tag = "  [primera lectura]" if d.get("first_seen") else ""
        lines.append(f"    • {d['name']}  {fmt_price(d['price'],d['currency'])}{tag}")
    if no_price:
        lines += ["", f"  ⚠️  SIN PRECIO  ({len(no_price)})", f"  {THIN}"]
        for d in no_price:
            lines.append(f"    • {d['name']}  ({d['site']})")
    if errors:
        lines += ["", f"  ❌ ERRORES  ({len(errors)})", f"  {THIN}"]
        for d in errors:
            lines.append(f"    • {d['name']}  —  {d['error']}")
    lines += ["", DIVIDER, ""]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  THE LITTLE WINE MARKET  (Shopify JSON API — no HTML scraping needed)
# ══════════════════════════════════════════════════════════════════════════════

def tlwm_scrape_all() -> list[dict]:
    log.info("── TLWM: fetching thelittlewinemarket.com …")
    products: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)
    page = 1
    while True:
        url = f"{TLWM_BASE_URL}/collections/all/products.json?limit=250&page={page}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            batch = resp.json().get("products", [])
        except Exception as exc:
            log.warning("  TLWM fetch error (page %d): %s", page, exc)
            break
        if not batch:
            break
        for p in batch:
            variant     = (p.get("variants") or [{}])[0]
            price       = parse_price(str(variant.get("price") or ""))
            compare_at  = parse_price(str(variant.get("compare_at_price") or ""))
            available   = variant.get("available", True)
            products.append({
                "name":             p.get("title", ""),
                "vendor":           p.get("vendor", ""),
                "product_type":     p.get("product_type", ""),
                "price":            price,
                "compare_at_price": compare_at,
                "url":              f"{TLWM_BASE_URL}/products/{p.get('handle','')}",
                "available":        available,
                "tags":             p.get("tags", []),
            })
        if len(batch) < 250:
            break
        page += 1
        time.sleep(1.0)
    log.info("  TLWM: %d productos (%d con precio, %d agotados)",
             len(products),
             sum(1 for p in products if p["price"]),
             sum(1 for p in products if not p["available"]))
    return products


def tlwm_update_history(history: dict, products: list[dict], today: str) -> dict:
    for p in products:
        if p["price"] is None:
            continue
        entries = history.setdefault(p["name"], [])
        if not entries or entries[-1]["price"] != p["price"]:
            entries.append({"date": today, "price": p["price"]})
    return history


def tlwm_compare(prev: list[dict], curr: list[dict]) -> dict:
    prev_map = {p["name"]: p for p in prev}
    curr_map = {p["name"]: p for p in curr}
    new_wines  = [p for n, p in curr_map.items() if n not in prev_map]
    removed    = [p for n, p in prev_map.items() if n not in curr_map]
    drops: list[dict] = []
    increases: list[dict] = []
    for name, cp in curr_map.items():
        pp = prev_map.get(name)
        if pp is None or pp.get("price") is None or cp.get("price") is None:
            continue
        op, np_ = pp["price"], cp["price"]
        if np_ < op:
            pct = (op - np_) / op * 100
            drops.append({**cp, "old": op, "new": np_, "pct": round(pct,1), "saving": op - np_})
        elif np_ > op:
            pct = (np_ - op) / op * 100
            increases.append({**cp, "old": op, "new": np_, "pct": round(pct,1), "extra": np_ - op})
    drops.sort(key=lambda x: x["pct"], reverse=True)
    increases.sort(key=lambda x: x["pct"], reverse=True)
    return {"new_wines": new_wines, "removed": removed, "drops": drops, "increases": increases}


def run_tlwm(today: str):
    prev = load_json(TLWM_LATEST_FILE) or None
    history = load_json(TLWM_HISTORY_FILE)
    curr = tlwm_scrape_all()
    history = tlwm_update_history(history, curr, today)
    save_json(TLWM_HISTORY_FILE, history)
    if not prev:
        save_json(TLWM_LATEST_FILE, curr)
        log.info("TLWM baseline guardado — %d productos", len(curr))
        return curr, None, history
    changes = tlwm_compare(prev, curr)
    n_new = len(changes["new_wines"])
    n_d   = len(changes["drops"])
    n_i   = len(changes["increases"])
    n_r   = len(changes["removed"])
    lines = [DIVIDER, f"  THE LITTLE WINE MARKET — {today}", DIVIDER, ""]
    lines += [f"  🍷 NUEVOS ({n_new})", f"  {THIN}"]
    lines += ["  (ninguno)"] if not n_new else \
             [f"    • {w['name']}  {fmt_price(w.get('price'))}" for w in changes["new_wines"]]
    lines += ["", f"  📉 DESCUENTOS ({n_d})", f"  {THIN}"]
    lines += ["  (ninguno)"] if not n_d else \
             [f"    ▼ {d['name']}  {fmt_price(d['old'])} → {fmt_price(d['new'])}  (-{d['pct']:.1f}%)"
              for d in changes["drops"]]
    lines += ["", f"  📈 ALZAS ({n_i})", f"  {THIN}"]
    lines += ["  (ninguno)"] if not n_i else \
             [f"    ▲ {d['name']}  {fmt_price(d['old'])} → {fmt_price(d['new'])}  (+{d['pct']:.1f}%)"
              for d in changes["increases"]]
    if n_r:
        lines += ["", f"  ❌ RETIRADOS ({n_r})", f"  {THIN}"]
        lines += [f"    • {w['name']}" for w in changes["removed"]]
    lines += ["", DIVIDER, ""]
    prepend_to_file(TLWM_FINDINGS_FILE, "\n".join(lines))
    save_json(TLWM_LATEST_FILE, curr)
    log.info("TLWM → Nuevos: %d  Descuentos: %d  Alzas: %d  Retirados: %d", n_new, n_d, n_i, n_r)
    return curr, changes, history


def run_watchlist(today: str):
    if not WATCHLIST:
        return [], {}
    history = load_json(WATCHLIST_HISTORY_FILE)
    results = watchlist_fetch_all()
    history = watchlist_update_history(history, results, today)
    prepend_to_file(WATCHLIST_FINDINGS_FILE, watchlist_build_report(results, history, today))
    save_json(WATCHLIST_HISTORY_FILE, history)
    nd = sum(1 for r in results if r["price"] and watchlist_prev_price(history, r["url"])
             and r["price"] < watchlist_prev_price(history, r["url"]))
    ni = sum(1 for r in results if r["price"] and watchlist_prev_price(history, r["url"])
             and r["price"] > watchlist_prev_price(history, r["url"]))
    log.info("── Watchlist → Descuentos: %d  Alzas: %d", nd, ni)
    return results, history


# ══════════════════════════════════════════════════════════════════════════════
#  REGION DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_region(wine_name: str) -> tuple[str, float, float, str] | None:
    nl = wine_name.lower()
    for kw, region in REGION_KEYWORDS.items():
        if kw in nl:
            return region
    return None


def aggregate_regions(snapshot: dict, new_wines_dict: dict) -> list[dict]:
    new_names: set[str] = set()
    for wines in new_wines_dict.values():
        for w in wines:
            new_names.add(w["name"] if isinstance(w, dict) else w)

    regions: dict[str, dict] = {}
    for cat, products in snapshot.items():
        for prod in products:
            name  = prod["name"]  if isinstance(prod, dict) else str(prod)
            price = prod.get("price") if isinstance(prod, dict) else None
            info  = detect_region(name)
            if not info:
                continue
            region_name, lat, lng, country = info
            if region_name not in regions:
                regions[region_name] = {"name": region_name, "lat": lat, "lng": lng,
                                        "country": country, "count": 0, "new_count": 0,
                                        "categories": {}, "wines": []}
            is_new = name in new_names
            url    = prod.get("url", "") if isinstance(prod, dict) else ""
            regions[region_name]["count"] += 1
            if is_new:
                regions[region_name]["new_count"] += 1
            regions[region_name]["categories"][cat] = \
                regions[region_name]["categories"].get(cat, 0) + 1
            regions[region_name]["wines"].append({
                "name": name, "price": price, "url": url,
                "cat": cat, "is_new": is_new,
            })

    # Sort wines inside each region: new first, then alphabetically
    for r in regions.values():
        r["wines"].sort(key=lambda w: (0 if w["is_new"] else 1, w["name"].lower()))

    return sorted(regions.values(), key=lambda x: x["count"], reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE HTML DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def generate_dashboard(today: str, costco_snapshot: dict, costco_changes: dict | None,
                       costco_history: dict, tlwm_snapshot: list, tlwm_changes: dict | None,
                       tlwm_history: dict, watchlist_results: list[dict],
                       watchlist_history: dict) -> None:

    new_wines_dict = costco_changes.get("new_wines", {}) if costco_changes else {}
    regions        = aggregate_regions(costco_snapshot, new_wines_dict)

    total_wines = sum(len(v) for v in costco_snapshot.values())
    new_total   = sum(len(v) for v in new_wines_dict.values())
    n_drops     = sum(len(v) for v in costco_changes.get("price_drops", {}).values()) if costco_changes else 0
    n_increases = sum(len(v) for v in costco_changes.get("price_increases", {}).values()) if costco_changes else 0

    cat_labels  = [c for c, _ in COSTCO_CATEGORIES]
    cat_counts  = [len(costco_snapshot.get(c, [])) for c, _ in COSTCO_CATEGORIES]
    cat_new     = [len(new_wines_dict.get(c, [])) for c, _ in COSTCO_CATEGORIES]

    # Price-drop wines for sparklines (top 5 by drop %)
    drop_sparklines: list[dict] = []
    if costco_changes:
        for cat, items in costco_changes.get("price_drops", {}).items():
            for item in items[:2]:
                hist = costco_history.get(cat, {}).get(item["name"], [])
                drop_sparklines.append({"name": item["name"][:40], "history": hist,
                                        "pct": round(item["pct"], 1)})
            if len(drop_sparklines) >= 5:
                break

    # TLWM data for dashboard
    tlwm_total     = len(tlwm_snapshot)
    tlwm_new_total = len(tlwm_changes["new_wines"])  if tlwm_changes else 0
    tlwm_n_drops   = len(tlwm_changes["drops"])      if tlwm_changes else 0
    tlwm_n_inc     = len(tlwm_changes["increases"])  if tlwm_changes else 0
    tlwm_new_list  = [{"name": w["name"], "price": w.get("price"), "url": w.get("url",""),
                        "vendor": w.get("vendor",""), "type": w.get("product_type","")}
                       for w in (tlwm_changes["new_wines"] if tlwm_changes else [])]
    tlwm_drops_list = [{"name": d["name"], "old": d["old"], "new": d["new"],
                         "pct": d["pct"], "saving": d["saving"], "url": d.get("url","")}
                        for d in (tlwm_changes["drops"] if tlwm_changes else [])]
    tlwm_inc_list   = [{"name": d["name"], "old": d["old"], "new": d["new"],
                         "pct": d["pct"], "extra": d["extra"], "url": d.get("url","")}
                        for d in (tlwm_changes["increases"] if tlwm_changes else [])]

    # Watchlist price histories
    wl_charts: list[dict] = []
    for r in watchlist_results:
        hist = watchlist_history.get(r["url"], [])
        wl_charts.append({"name": r["name"], "site": r["site"],
                           "currency": r.get("currency", "MXN"),
                           "price": r["price"], "history": hist,
                           "pending": r.get("pending", False)})

    # Full wine lists for gauge modals
    new_wines_list: list[dict] = []
    drops_list:     list[dict] = []
    increases_list: list[dict] = []
    if costco_changes:
        # Build URL lookup from current snapshot
        url_lookup: dict[str, str] = {}
        for cat, prods in costco_snapshot.items():
            for p in prods:
                if isinstance(p, dict):
                    url_lookup[p.get("name","")] = p.get("url","")
        for cat, wines in costco_changes.get("new_wines", {}).items():
            for w in wines:
                name = w.get("name","")
                new_wines_list.append({"name": name, "price": w.get("price"),
                                       "cat": cat, "url": url_lookup.get(name,"")})
        for cat, items in costco_changes.get("price_drops", {}).items():
            for d in items:
                drops_list.append({"name": d["name"], "old": d["old"], "new": d["new"],
                                   "pct": round(d["pct"],1), "saving": d["saving"],
                                   "cat": cat, "url": url_lookup.get(d["name"],"")})
        for cat, items in costco_changes.get("price_increases", {}).items():
            for d in items:
                increases_list.append({"name": d["name"], "old": d["old"], "new": d["new"],
                                       "pct": round(d["pct"],1), "extra": d["extra"],
                                       "cat": cat, "url": url_lookup.get(d["name"],"")})
    new_wines_list.sort(key=lambda w: w.get("cat",""))
    drops_list.sort(key=lambda w: -w["pct"])
    increases_list.sort(key=lambda w: -w["pct"])

    # All-time new wines: first entry in history = first seen date
    _snap_idx: dict[str, tuple[str, float | None]] = {}
    for _cat, _prods in costco_snapshot.items():
        for _p in _prods:
            if isinstance(_p, dict) and _p.get("name"):
                _snap_idx[_p["name"]] = (_p.get("url", ""), _p.get("price"))
    all_new_wines: list[dict] = []
    for _cat, _wines in costco_history.items():
        for _wname, _entries in _wines.items():
            if _entries:
                _url, _price = _snap_idx.get(_wname, ("", None))
                all_new_wines.append({
                    "name": _wname, "cat": _cat,
                    "first_seen": _entries[0]["date"],
                    "price": _price, "url": _url,
                })
    all_new_wines.sort(key=lambda w: w["first_seen"], reverse=True)

    dashboard_data = {
        "date": today,
        "is_baseline": costco_changes is None,
        "costco": {
            "total_wines": total_wines, "new_total": new_total,
            "n_drops": n_drops, "n_increases": n_increases,
            "cat_labels": cat_labels, "cat_counts": cat_counts, "cat_new": cat_new,
            "drop_sparklines": drop_sparklines,
            "new_wines_list": new_wines_list,
            "drops_list":     drops_list,
            "increases_list": increases_list,
            "all_new_wines":  all_new_wines,
        },
        "regions": regions,
        "tlwm": {
            "total": tlwm_total, "new_total": tlwm_new_total,
            "n_drops": tlwm_n_drops, "n_increases": tlwm_n_inc,
            "is_baseline": tlwm_changes is None,
            "new_wines_list": tlwm_new_list,
            "drops_list":     tlwm_drops_list,
            "increases_list": tlwm_inc_list,
        },
        "watchlist": wl_charts,
    }

    data_js = json.dumps(dashboard_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wine Monitor — {today}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:     #0d0608; --card:   #1a0c0e; --card2: #221014;
    --border: #3d1a1e; --red:    #c0392b; --red2:  #e74c3c;
    --gold:   #d4a843; --green:  #27ae60; --blue:  #2980b9;
    --text:   #f0e6e8; --muted:  #8a7070;
    --font: 'Segoe UI', system-ui, sans-serif;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:var(--font); min-height:100vh; }}

  header {{
    background: linear-gradient(135deg,#1a0608,#2d0f15,#1a0608);
    border-bottom:1px solid var(--border);
    padding:18px 32px; display:flex; align-items:center; justify-content:space-between;
  }}
  header h1 {{ font-size:1.6rem; color:var(--gold); letter-spacing:1px; }}
  header h1 span {{ color:var(--red2); }}
  .date-badge {{ background:var(--card2); border:1px solid var(--border);
    border-radius:20px; padding:6px 16px; font-size:0.85rem; color:var(--muted); }}

  main {{ max-width:1400px; margin:0 auto; padding:28px 24px; }}
  .section-title {{
    font-size:0.7rem; font-weight:700; letter-spacing:3px; text-transform:uppercase;
    color:var(--muted); margin-bottom:14px; padding-bottom:6px; border-bottom:1px solid var(--border);
  }}

  /* Gauges */
  .gauges {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:28px; }}
  .gauge-card {{
    background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:20px 16px 12px;
    text-align:center; position:relative; overflow:hidden;
    transition: border-color .2s, transform .15s;
  }}
  .gauge-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; }}
  .gauge-card.g-total::before {{ background:var(--gold); }}
  .gauge-card.g-new::before   {{ background:var(--blue); }}
  .gauge-card.g-drops::before {{ background:var(--green); }}
  .gauge-card.g-rises::before {{ background:var(--red2); }}
  .gauge-card.clickable {{ cursor:pointer; }}
  .gauge-card.clickable:hover {{ border-color:#6a3a3e; transform:translateY(-2px);
    box-shadow:0 6px 20px rgba(0,0,0,.4); }}
  .gauge-hint {{ font-size:0.65rem; color:#5a4040; margin-top:2px; letter-spacing:1px; }}
  .gauge-svg {{ width:160px; height:95px; }}
  .gauge-bg   {{ fill:none; stroke:#2a1015; stroke-width:12; stroke-linecap:round; }}
  .gauge-fill {{ fill:none; stroke-width:12; stroke-linecap:round;
    stroke-dasharray:251.33 251.33; stroke-dashoffset:251.33;
    transition:stroke-dashoffset 1.4s cubic-bezier(.4,0,.2,1); }}
  .gauge-num  {{ font-size:1.9rem; font-weight:800; fill:var(--text); }}
  .gauge-label {{ font-size:0.78rem; color:var(--muted); margin-top:4px; letter-spacing:1px; }}

  /* Charts */
  .charts-row {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:28px; }}
  .chart-card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; }}
  .chart-card h3 {{ font-size:0.78rem; color:var(--muted); letter-spacing:2px;
    text-transform:uppercase; margin-bottom:16px; }}
  .chart-wrap {{ position:relative; height:240px; }}

  /* Map */
  .map-card {{ background:var(--card); border:1px solid var(--border);
    border-radius:12px; overflow:hidden; margin-bottom:28px; }}
  .map-header {{ padding:14px 20px; border-bottom:1px solid var(--border); }}
  .map-header-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }}
  .map-header h3 {{ font-size:0.78rem; color:var(--muted); letter-spacing:2px; text-transform:uppercase; }}
  .map-legend {{ display:flex; gap:20px; font-size:0.75rem; color:var(--muted); }}
  .map-legend span {{ display:flex; align-items:center; gap:6px; }}
  .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
  .map-filters {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .map-filter-btn {{
    padding:5px 14px; border-radius:20px; border:1px solid var(--border);
    background:var(--card2); color:var(--muted); font-size:0.75rem; cursor:pointer;
    transition:background .15s, color .15s, border-color .15s;
  }}
  .map-filter-btn.active {{ background:#3d1a1e; color:var(--text); border-color:#6a3a3e; }}
  #wine-map {{ height:480px; position:relative; }}

  /* Watchlist */
  .watchlist-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
    gap:16px; margin-bottom:28px; }}
  .wl-card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; }}
  .wl-name {{ font-size:0.9rem; font-weight:600; color:var(--text); margin-bottom:4px; }}
  .wl-site {{ font-size:0.72rem; color:var(--muted); margin-bottom:12px; }}
  .wl-price {{ font-size:1.4rem; font-weight:800; color:var(--gold); }}
  .wl-change.up   {{ color:var(--red2);  font-size:0.78rem; }}
  .wl-change.down {{ color:var(--green); font-size:0.78rem; }}
  .wl-chart-wrap {{ position:relative; height:100px; margin-top:14px; }}
  .wl-link {{ display:inline-block; margin-top:8px; font-size:0.72rem; color:var(--blue); text-decoration:none; }}
  .wl-link:hover {{ text-decoration:underline; }}
  .no-history {{ color:var(--muted); font-size:0.75rem; margin-top:14px; text-align:center; }}

  /* Drops card */
  .drops-card {{ background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:20px; margin-bottom:28px; }}
  .drops-card h3 {{ font-size:0.78rem; color:var(--muted); letter-spacing:2px;
    text-transform:uppercase; margin-bottom:14px; }}
  .drop-row {{ display:flex; justify-content:space-between; align-items:center;
    padding:10px 0; border-bottom:1px solid var(--border); font-size:0.85rem; }}
  .drop-row:last-child {{ border-bottom:none; }}
  .drop-name {{ flex:1; color:var(--text); }}
  .drop-pct  {{ color:var(--green); font-weight:700; font-size:0.9rem; margin:0 16px; }}
  .drop-prices {{ color:var(--muted); font-size:0.8rem; }}

  /* Baseline */
  .baseline-notice {{
    background:linear-gradient(90deg,#1a0e00,#2a1a00,#1a0e00);
    border:1px solid #4a3000; border-radius:12px;
    padding:20px 24px; text-align:center; margin-bottom:28px;
    color:var(--gold); font-size:0.9rem;
  }}

  footer {{ text-align:center; padding:24px; color:var(--muted); font-size:0.75rem;
    border-top:1px solid var(--border); margin-top:8px; }}

  /* ── Modal ── */
  .modal-overlay {{
    display:none; position:fixed; inset:0; background:rgba(0,0,0,.75);
    z-index:9000; align-items:center; justify-content:center;
  }}
  .modal-overlay.open {{ display:flex; }}
  .modal-box {{
    background:var(--card); border:1px solid var(--border); border-radius:14px;
    width:min(680px,95vw); max-height:85vh; display:flex; flex-direction:column;
    box-shadow:0 20px 60px rgba(0,0,0,.6);
  }}
  .modal-head {{
    padding:18px 22px; background:var(--card2); border-bottom:1px solid var(--border);
    border-radius:14px 14px 0 0; display:flex; justify-content:space-between; align-items:flex-start;
    flex-shrink:0;
  }}
  .modal-title {{ font-size:1.05rem; font-weight:700; color:var(--text); }}
  .modal-sub   {{ font-size:0.75rem; color:var(--muted); margin-top:3px; }}
  .modal-close {{
    background:none; border:none; color:var(--muted); font-size:1.3rem;
    cursor:pointer; padding:0 4px; line-height:1; flex-shrink:0;
  }}
  .modal-close:hover {{ color:var(--text); }}
  .modal-controls {{
    padding:12px 22px; border-bottom:1px solid var(--border); flex-shrink:0;
    display:flex; gap:8px; flex-wrap:wrap; align-items:center;
  }}
  .modal-pill {{
    padding:4px 12px; border-radius:16px; border:1px solid var(--border);
    background:var(--card2); color:var(--muted); font-size:0.72rem; cursor:pointer;
    transition:background .15s, color .15s;
  }}
  .modal-pill.active {{ background:#3d1a1e; color:var(--text); border-color:#6a3a3e; }}
  .modal-search {{
    margin-left:auto; padding:5px 12px;
    background:#0d0608; border:1px solid var(--border); border-radius:8px;
    color:var(--text); font-size:0.8rem; outline:none; width:180px;
  }}
  .modal-body {{ flex:1; overflow-y:auto; }}
  .modal-row {{
    display:flex; align-items:center; padding:10px 22px;
    border-bottom:1px solid #1f0f12; gap:12px;
  }}
  .modal-row:hover {{ background:#1f0f12; }}
  .modal-row.is-new {{ background:#1e0d10; }}
  .modal-row-info {{ flex:1; min-width:0; }}
  .modal-row-name {{
    font-size:0.85rem; color:var(--text); white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis;
  }}
  .modal-row-meta {{ font-size:0.7rem; color:var(--muted); margin-top:2px; }}
  .modal-row-price {{ font-size:0.85rem; font-weight:700; color:var(--gold); white-space:nowrap; }}
  .modal-row-change {{ font-size:0.78rem; font-weight:700; white-space:nowrap; }}
  .modal-row-change.down {{ color:var(--green); }}
  .modal-row-change.up   {{ color:var(--red2); }}
  .new-badge {{ font-size:0.6rem; font-weight:700; letter-spacing:1px;
    color:var(--red2); margin-right:4px; }}
  .modal-link {{
    color:var(--blue); font-size:0.75rem; text-decoration:none;
    padding:3px 8px; border:1px solid #1a3a5c; border-radius:6px;
    white-space:nowrap; flex-shrink:0; transition:background .15s;
  }}
  .modal-link:hover {{ background:#1a2a3c; }}
  .modal-footer {{
    padding:10px 22px; border-top:1px solid var(--border);
    font-size:0.72rem; color:var(--muted); flex-shrink:0;
    display:flex; justify-content:space-between; align-items:center;
  }}
</style>
</head>
<body>

<header>
  <h1>🍷 Wine <span>Monitor</span></h1>
  <div class="date-badge">Última actualización: {today}</div>
</header>

<main>

<div id="baseline-notice" style="display:none" class="baseline-notice">
  📋 Primera corrida — datos de referencia guardados. Los cambios se detectarán a partir de la próxima ejecución.
</div>

<!-- Gauges -->
<p class="section-title">Resumen — Haz clic en un indicador para ver el detalle</p>
<div class="gauges">
  <div class="gauge-card g-total" id="gc-total">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-total" stroke="#d4a843"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-total">0</text>
    </svg>
    <div class="gauge-label">VINOS TOTALES</div>
  </div>
  <div class="gauge-card g-new clickable" id="gc-new" title="Clic para ver la lista">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-new" stroke="#2980b9"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-new">0</text>
    </svg>
    <div class="gauge-label">NUEVOS HOY</div>
    <div class="gauge-hint">↗ VER LISTA</div>
  </div>
  <div class="gauge-card g-drops clickable" id="gc-drops" title="Clic para ver la lista">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-drops" stroke="#27ae60"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-drops">0</text>
    </svg>
    <div class="gauge-label">DESCUENTOS</div>
    <div class="gauge-hint">↗ VER LISTA</div>
  </div>
  <div class="gauge-card g-rises clickable" id="gc-rises" title="Clic para ver la lista">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-rises" stroke="#e74c3c"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-rises">0</text>
    </svg>
    <div class="gauge-label">ALZAS DE PRECIO</div>
    <div class="gauge-hint">↗ VER LISTA</div>
  </div>
</div>

<!-- Charts -->
<p class="section-title">Costco — Vinos por Categoría</p>
<div class="charts-row">
  <div class="chart-card">
    <h3>Cantidad por categoría</h3>
    <div class="chart-wrap"><canvas id="bar-chart"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Distribución</h3>
    <div class="chart-wrap"><canvas id="donut-chart"></canvas></div>
  </div>
</div>

<!-- Price drops sparklines -->
<div id="drops-section" class="drops-card" style="display:none">
  <h3>📉 Descuentos destacados — clic en el indicador para ver todos</h3>
  <div id="drops-list"></div>
</div>

<!-- Map -->
<p class="section-title">Mapa de Regiones Vitivinícolas — Haz clic en una burbuja para ver los vinos</p>
<div class="map-card">
  <div class="map-header">
    <div class="map-header-top">
      <h3>Vinos detectados por región de origen</h3>
      <div class="map-legend">
        <span><span class="dot" style="background:#e74c3c"></span> Con vinos nuevos</span>
        <span><span class="dot" style="background:#5d8aa8"></span> Sin cambios</span>
      </div>
    </div>
    <div class="map-filters">
      <button class="map-filter-btn active" data-filter="all" id="mfb-all">Todas las regiones</button>
      <button class="map-filter-btn" data-filter="new" id="mfb-new">★ Solo con nuevos</button>
      <button class="map-filter-btn" data-filter="existing" id="mfb-existing">Sin cambios</button>
    </div>
  </div>
  <div id="wine-map"></div>
</div>

<!-- Watchlist -->
<!-- The Little Wine Market -->
<p class="section-title">The Little Wine Market — Resumen</p>
<div id="tlwm-baseline-notice" style="display:none" class="baseline-notice">
  📋 Primera corrida TLWM — datos de referencia guardados.
</div>
<div class="gauges" id="tlwm-gauges">
  <div class="gauge-card g-total">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-tlwm-total" stroke="#d4a843"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-tlwm-total">0</text>
    </svg>
    <div class="gauge-label">TLWM TOTAL</div>
  </div>
  <div class="gauge-card g-new clickable" id="tlwm-gc-new" title="Clic para ver nuevos">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-tlwm-new" stroke="#2980b9"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-tlwm-new">0</text>
    </svg>
    <div class="gauge-label">NUEVOS TLWM</div>
    <div class="gauge-hint">↗ VER LISTA</div>
  </div>
  <div class="gauge-card g-drops clickable" id="tlwm-gc-drops" title="Clic para ver descuentos">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-tlwm-drops" stroke="#27ae60"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-tlwm-drops">0</text>
    </svg>
    <div class="gauge-label">DESCUENTOS TLWM</div>
    <div class="gauge-hint">↗ VER LISTA</div>
  </div>
  <div class="gauge-card g-rises clickable" id="tlwm-gc-rises" title="Clic para ver alzas">
    <svg class="gauge-svg" viewBox="0 0 200 95">
      <path class="gauge-bg"   d="M 20 85 A 80 80 0 0 1 180 85"/>
      <path class="gauge-fill" d="M 20 85 A 80 80 0 0 1 180 85" id="gf-tlwm-rises" stroke="#e74c3c"/>
      <text class="gauge-num"  x="100" y="75" text-anchor="middle" id="gv-tlwm-rises">0</text>
    </svg>
    <div class="gauge-label">ALZAS TLWM</div>
    <div class="gauge-hint">↗ VER LISTA</div>
  </div>
</div>

<!-- Watchlist -->
<p class="section-title">Watchlist — Productos Monitoreados</p>
<div class="watchlist-grid" id="watchlist-grid"></div>

</main>
<footer>Wine Monitor · Generado el {today} · costco.com.mx + watchlist</footer>

<!-- Modal overlay -->
<div class="modal-overlay" id="modal">
  <div class="modal-box">
    <div class="modal-head">
      <div>
        <div class="modal-title" id="modal-title"></div>
        <div class="modal-sub"  id="modal-sub"></div>
      </div>
      <button class="modal-close" id="modal-close">✕</button>
    </div>
    <div class="modal-controls" id="modal-controls"></div>
    <div class="modal-body"     id="modal-body"></div>
    <div class="modal-footer">
      <span id="modal-count"></span>
      <a href="https://www.costco.com.mx/Vinos/Vinos/c/cos_21" target="_blank"
         style="color:var(--blue);font-size:0.72rem;text-decoration:none">
        Ir a Costco Vinos ↗
      </a>
    </div>
  </div>
</div>

<script>
const D = {data_js};

// ── Helpers ──────────────────────────────────────────────────────────────────
const fmtP = (p, cur='MXN') =>
  p != null ? '$' + p.toLocaleString('es-MX',{{minimumFractionDigits:2}}) + (cur && cur!=='MXN' ? ' '+cur : '') : '—';

// ── Gauge ────────────────────────────────────────────────────────────────────
function setGauge(id, value, maxVal) {{
  const L = 251.33, p = maxVal > 0 ? Math.min(1, value / maxVal) : 0;
  const el = document.getElementById('gf-' + id);
  if (el) el.style.strokeDashoffset = L * (1 - p);
  const vl = document.getElementById('gv-' + id);
  if (vl) vl.textContent = value;
}}

if (D.is_baseline) document.getElementById('baseline-notice').style.display = 'block';

const C = D.costco;
setTimeout(() => {{
  setGauge('total', C.total_wines, C.total_wines);
  setGauge('new',   C.new_total,   Math.max(C.new_total, 20));
  setGauge('drops', C.n_drops,     Math.max(C.n_drops, 10));
  setGauge('rises', C.n_increases, Math.max(C.n_increases, 10));
}}, 150);

// ── Modal ────────────────────────────────────────────────────────────────────
let modalWines = [], modalFilter = 'all', modalMode = 'new';

function openModal(title, subtitle, wines, mode, keepPeriodBar) {{
  modalWines  = wines;
  modalFilter = 'all';
  modalMode   = mode;
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-sub').textContent   = subtitle;

  // Build category pills
  const cats = [...new Set(wines.map(w => w.cat))].filter(Boolean);
  const ctrl = document.getElementById('modal-controls');
  const savedPbar = keepPeriodBar ? document.getElementById('modal-period-bar') : null;
  ctrl.innerHTML = '';
  if (savedPbar) ctrl.prepend(savedPbar);
  const mkPill = (label, val) => {{
    const b = document.createElement('button');
    b.className = 'modal-pill' + (val === 'all' ? ' active' : '');
    b.textContent = label; b.dataset.val = val;
    b.addEventListener('click', () => {{
      modalFilter = val;
      ctrl.querySelectorAll('.modal-pill').forEach(p =>
        p.classList.toggle('active', p.dataset.val === val));
      renderModal(document.getElementById('msearch').value);
    }});
    ctrl.appendChild(b);
  }};
  mkPill('Todos', 'all');
  cats.forEach(c => mkPill(c.replace('Vino ','').replace('Vinos ',''), c));

  const srch = document.createElement('input');
  srch.id = 'msearch'; srch.className = 'modal-search';
  srch.placeholder = 'Buscar…';
  srch.addEventListener('input', e => renderModal(e.target.value));
  ctrl.appendChild(srch);

  renderModal('');
  document.getElementById('modal').classList.add('open');
}}

function renderModal(search) {{
  const q = (search || '').toLowerCase();
  const shown = modalWines.filter(w =>
    (modalFilter === 'all' || w.cat === modalFilter) &&
    (!q || w.name.toLowerCase().includes(q))
  );
  const body = document.getElementById('modal-body');
  body.innerHTML = '';

  if (!shown.length) {{
    body.innerHTML = '<div style="padding:30px;text-align:center;color:var(--muted)">Sin resultados</div>';
    document.getElementById('modal-count').textContent = '0 vinos';
    return;
  }}

  shown.forEach(w => {{
    const row = document.createElement('div');
    row.className = 'modal-row' + (w.is_new ? ' is-new' : '');
    const catShort = (w.cat||'').replace('Vino ','').replace('Vinos ','');

    let changeHtml = '';
    if (modalMode === 'drops' && w.pct != null)
      changeHtml = `<span class="modal-row-change down">▼ ${{w.pct}}% · ahorra ${{fmtP(w.saving)}}</span>`;
    else if (modalMode === 'rises' && w.pct != null)
      changeHtml = `<span class="modal-row-change up">▲ ${{w.pct}}% · sube ${{fmtP(w.extra)}}</span>`;

    const priceHtml = (modalMode === 'drops' || modalMode === 'rises') && w.old != null
      ? `<div style="font-size:0.7rem;color:var(--muted);text-decoration:line-through">${{fmtP(w.old)}}</div>
         <div class="modal-row-price">${{fmtP(w.new)}}</div>`
      : `<div class="modal-row-price">${{fmtP(w.price)}}</div>`;

    const linkHtml = w.url
      ? `<a class="modal-link" href="${{w.url}}" target="_blank">Ver ↗</a>`
      : '';

    row.innerHTML = `
      <div class="modal-row-info">
        ${{w.is_new ? '<span class="new-badge">★ NUEVO</span>' : ''}}
        <div class="modal-row-name" title="${{w.name}}">${{w.name}}</div>
        <div class="modal-row-meta">${{catShort}}${{changeHtml ? ' · ' : ''}}${{changeHtml}}</div>
      </div>
      ${{priceHtml}}
      ${{linkHtml}}
    `;
    body.appendChild(row);
  }});
  document.getElementById('modal-count').textContent =
    `${{shown.length}} de ${{modalWines.length}} vinos`;
}}

document.getElementById('modal-close').addEventListener('click', () =>
  document.getElementById('modal').classList.remove('open'));
document.getElementById('modal').addEventListener('click', e => {{
  if (e.target === document.getElementById('modal'))
    document.getElementById('modal').classList.remove('open');
}});
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') document.getElementById('modal').classList.remove('open');
}});

// ── Gauge clicks ─────────────────────────────────────────────────────────────
document.getElementById('gc-new').addEventListener('click', () => {{
  const allNew = C.all_new_wines || [];
  if (!C.new_wines_list.length && !allNew.length) return;
  const todayStr = D.date;

  function daysMinus(n) {{
    const d = new Date(todayStr); d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }}

  function winesForPeriod(period, dateVal) {{
    if (period === 'run') return C.new_wines_list;
    if (period === 'date') return allNew.filter(w => w.first_seen === (dateVal || todayStr));
    const cutoff = period === '7d' ? daysMinus(7) : daysMinus(30);
    return allNew.filter(w => w.first_seen >= cutoff);
  }}

  function openPeriod(period, activePillEl, dateVal) {{
    const wines = winesForPeriod(period, dateVal);
    const subs = {{
      run:   `${{C.new_total}} vino(s) nuevo(s) esta corrida`,
      '7d':  `Últimos 7 días — ${{wines.length}} vino(s)`,
      '30d': `Últimos 30 días — ${{wines.length}} vino(s)`,
      date:  `${{dateVal || todayStr}} — ${{wines.length}} vino(s)`,
    }};
    openModal('🍷 Nuevos Vinos', subs[period] || '', wines, 'new', true);
    document.getElementById('modal-period-bar').querySelectorAll('.period-btn')
      .forEach(b => b.classList.toggle('active', b === activePillEl));
    const di = document.getElementById('modal-date-input');
    if (di) di.style.display = period === 'date' ? 'inline-block' : 'none';
  }}

  // Initial open with "this run"
  openModal('🍷 Nuevos Vinos', `${{C.new_total}} vino(s) nuevo(s) esta corrida`,
    C.new_wines_list, 'new', false);

  // Inject period bar at top of modal-controls
  const ctrl = document.getElementById('modal-controls');
  const pbar = document.createElement('div');
  pbar.id = 'modal-period-bar';
  pbar.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;align-items:center;width:100%;padding-bottom:8px;margin-bottom:4px;border-bottom:1px solid var(--border);';

  const pillMap = {{}};
  [['Esta corrida','run'],['7 días','7d'],['30 días','30d'],['Por fecha','date']].forEach(([lbl, val]) => {{
    const btn = document.createElement('button');
    btn.className = 'modal-pill period-btn' + (val === 'run' ? ' active' : '');
    btn.textContent = lbl;
    pillMap[val] = btn;
    btn.addEventListener('click', () => {{
      const di = document.getElementById('modal-date-input');
      if (val === 'date') {{
        if (di) di.style.display = 'inline-block';
        openPeriod('date', btn, di ? di.value : todayStr);
      }} else {{
        if (di) di.style.display = 'none';
        openPeriod(val, btn, null);
      }}
    }});
    pbar.appendChild(btn);
  }});

  const dateInput = document.createElement('input');
  dateInput.id = 'modal-date-input';
  dateInput.type = 'date';
  dateInput.value = todayStr;
  dateInput.style.cssText = 'display:none;padding:4px 8px;background:#0d0608;border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:0.78rem;outline:none;margin-left:4px;';
  dateInput.addEventListener('change', () => openPeriod('date', pillMap['date'], dateInput.value));
  pbar.appendChild(dateInput);
  ctrl.prepend(pbar);
}});
document.getElementById('gc-drops').addEventListener('click', () => {{
  if (!C.drops_list.length) return;
  openModal('📉 Descuentos', `${{C.n_drops}} vino(s) con precio más bajo que la corrida anterior`,
    C.drops_list, 'drops');
}});
document.getElementById('gc-rises').addEventListener('click', () => {{
  if (!C.increases_list.length) return;
  openModal('📈 Alzas de Precio', `${{C.n_increases}} vino(s) con precio más alto que la corrida anterior`,
    C.increases_list, 'rises');
}});

// ── Bar chart ────────────────────────────────────────────────────────────────
new Chart(document.getElementById('bar-chart'), {{
  type: 'bar',
  data: {{
    labels: C.cat_labels.map(l => l.replace('Vino ','').replace('Vinos ','')),
    datasets: [
      {{ label:'Total',  data:C.cat_counts, backgroundColor:'rgba(192,57,43,0.6)', borderColor:'#c0392b', borderWidth:1 }},
      {{ label:'Nuevos', data:C.cat_new,    backgroundColor:'rgba(41,128,185,0.8)', borderColor:'#2980b9', borderWidth:1 }},
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ labels:{{ color:'#f0e6e8', font:{{size:11}} }} }},
               tooltip:{{ callbacks:{{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y}} vinos` }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#8a7070', font:{{size:11}} }}, grid:{{ color:'#2a1015' }} }},
      y:{{ ticks:{{ color:'#8a7070' }},                  grid:{{ color:'#2a1015' }} }},
    }}
  }}
}});

const DONUT_COLORS = ['#c0392b','#2980b9','#f39c12','#8e44ad','#16a085','#d35400'];
new Chart(document.getElementById('donut-chart'), {{
  type:'doughnut',
  data:{{ labels:C.cat_labels.map(l=>l.replace('Vino ','').replace('Vinos ','')),
          datasets:[{{ data:C.cat_counts, backgroundColor:DONUT_COLORS,
                       borderColor:'#0d0608', borderWidth:2 }}] }},
  options:{{
    responsive:true, maintainAspectRatio:false, cutout:'62%',
    plugins:{{
      legend:{{ position:'right', labels:{{ color:'#f0e6e8', font:{{size:11}}, padding:12 }} }},
      tooltip:{{ callbacks:{{ label: ctx => ` ${{ctx.label}}: ${{ctx.parsed}} vinos` }} }},
    }}
  }}
}});

// ── Price drop sparklines ────────────────────────────────────────────────────
if (C.drop_sparklines && C.drop_sparklines.length > 0) {{
  document.getElementById('drops-section').style.display = 'block';
  const list = document.getElementById('drops-list');
  C.drop_sparklines.forEach(sp => {{
    const last2 = sp.history.slice(-2);
    const old_p = last2.length >= 2 ? last2[0].price : null;
    const new_p = last2.length >= 1 ? last2[last2.length-1].price : null;
    const row = document.createElement('div');
    row.className = 'drop-row';
    row.innerHTML = `<span class="drop-name">${{sp.name}}</span>
      <span class="drop-pct">-${{sp.pct}}%</span>
      <span class="drop-prices">${{fmtP(old_p)}} → ${{fmtP(new_p)}}</span>`;
    list.appendChild(row);
  }});
}}

// ── Map ──────────────────────────────────────────────────────────────────────
const map = L.map('wine-map', {{ zoomControl: true }}).setView([20, 10], 2);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '© OpenStreetMap contributors © CARTO',
  subdomains: 'abcd', maxZoom: 18,
}}).addTo(map);

// Side-panel for wine list
const panel = document.createElement('div');
panel.id = 'region-panel';
panel.style.cssText = `
  position:absolute; top:0; right:0; width:340px; height:100%;
  background:#1a0c0e; border-left:1px solid #3d1a1e;
  z-index:1000; display:none; flex-direction:column;
  font-family:'Segoe UI',sans-serif; overflow:hidden;
`;
panel.innerHTML = `
  <div id="rp-header" style="padding:14px 16px;background:#221014;border-bottom:1px solid #3d1a1e;flex-shrink:0">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div id="rp-name"  style="font-size:1.05rem;font-weight:700;color:#f0e6e8"></div>
        <div id="rp-country" style="font-size:0.75rem;color:#8a7070;margin-top:2px"></div>
      </div>
      <button id="rp-close" style="background:none;border:none;color:#8a7070;font-size:1.2rem;cursor:pointer;padding:0 4px;line-height:1">✕</button>
    </div>
    <div id="rp-stats" style="margin-top:10px;display:flex;gap:14px"></div>
    <div id="rp-filter" style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap"></div>
    <input id="rp-search" placeholder="Buscar vino…" style="
      margin-top:8px;width:100%;padding:6px 10px;
      background:#0d0608;border:1px solid #3d1a1e;border-radius:6px;
      color:#f0e6e8;font-size:0.8rem;outline:none;
    "/>
  </div>
  <div id="rp-list" style="flex:1;overflow-y:auto;padding:8px 0"></div>
  <div id="rp-footer" style="padding:8px 16px;background:#221014;border-top:1px solid #3d1a1e;
       font-size:0.72rem;color:#8a7070;flex-shrink:0"></div>
`;
document.getElementById('wine-map').appendChild(panel);
document.getElementById('rp-close').addEventListener('click', () => {{
  panel.style.display = 'none';
  map.invalidateSize();
}});

let activeWines = [];
let activeFilter = 'all';

// fmtP defined above

function renderWineList(wines, search) {{
  const list  = document.getElementById('rp-list');
  const query = (search || '').toLowerCase();
  const shown = wines.filter(w =>
    (activeFilter === 'all' || (activeFilter === 'new' && w.is_new) ||
     w.cat === activeFilter) &&
    (!query || w.name.toLowerCase().includes(query))
  );
  list.innerHTML = '';
  if (!shown.length) {{
    list.innerHTML = '<div style="color:#8a7070;font-size:0.8rem;padding:20px 16px;text-align:center">Sin resultados</div>';
    return;
  }}
  shown.forEach(w => {{
    const row = document.createElement('div');
    row.style.cssText = `
      padding:9px 16px; border-bottom:1px solid #2a1015;
      display:flex; justify-content:space-between; align-items:center;
      ${{w.is_new ? 'background:#1f0d10;' : ''}}
    `;
    const catShort = w.cat.replace('Vino ','').replace('Vinos ','');
    row.innerHTML = `
      <div style="flex:1;min-width:0;padding-right:10px">
        ${{w.is_new ? '<span style="color:#e74c3c;font-size:0.65rem;font-weight:700;letter-spacing:1px;display:block;margin-bottom:2px">★ NUEVO</span>' : ''}}
        <div style="font-size:0.82rem;color:#f0e6e8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
             title="${{w.name}}">${{w.name}}</div>
        <div style="font-size:0.7rem;color:#6a5050;margin-top:2px">${{catShort}}</div>
      </div>
      <div style="font-size:0.82rem;font-weight:600;color:#d4a843;white-space:nowrap">${{fmtP(w.price)}}</div>
    `;
    list.appendChild(row);
  }});
  document.getElementById('rp-footer').textContent =
    `Mostrando ${{shown.length}} de ${{wines.length}} vinos`;
}}

function openPanel(r) {{
  activeWines = r.wines || [];
  activeFilter = 'all';
  document.getElementById('rp-name').textContent    = r.name;
  document.getElementById('rp-country').textContent = r.country;
  document.getElementById('rp-search').value        = '';

  // Stats badges
  const stats = document.getElementById('rp-stats');
  stats.innerHTML = `
    <span style="background:#2a1015;border:1px solid #3d1a1e;border-radius:12px;
          padding:3px 10px;font-size:0.75rem;color:#d4a843">
      ${{r.count}} vinos
    </span>
    ${{r.new_count > 0 ? `<span style="background:#3d0a0a;border:1px solid #7a1a1a;border-radius:12px;
          padding:3px 10px;font-size:0.75rem;color:#e74c3c">★ ${{r.new_count}} nuevos</span>` : ''}}
  `;

  // Category filter pills
  const cats = [...new Set(activeWines.map(w => w.cat))];
  const filterDiv = document.getElementById('rp-filter');
  filterDiv.innerHTML = '';
  const allBtn = document.createElement('button');
  allBtn.textContent = 'Todos';
  allBtn.dataset.cat = 'all';
  allBtn.style.cssText = `background:#c0392b;border:none;border-radius:10px;
    padding:3px 10px;font-size:0.7rem;color:#fff;cursor:pointer;`;
  allBtn.addEventListener('click', () => {{
    activeFilter = 'all';
    filterDiv.querySelectorAll('button').forEach(b =>
      b.style.background = b.dataset.cat === 'all' ? '#c0392b' : '#2a1015');
    renderWineList(activeWines, document.getElementById('rp-search').value);
  }});
  filterDiv.appendChild(allBtn);
  if (r.new_count > 0) {{
    const nb = document.createElement('button');
    nb.textContent = '★ Nuevos';
    nb.dataset.cat = 'new';
    nb.style.cssText = `background:#2a1015;border:1px solid #7a1a1a;border-radius:10px;
      padding:3px 10px;font-size:0.7rem;color:#e74c3c;cursor:pointer;`;
    nb.addEventListener('click', () => {{
      activeFilter = 'new';
      filterDiv.querySelectorAll('button').forEach(b =>
        b.style.background = b.dataset.cat === 'new' ? '#7a1a1a' : '#2a1015');
      renderWineList(activeWines, document.getElementById('rp-search').value);
    }});
    filterDiv.appendChild(nb);
  }}
  cats.forEach(cat => {{
    const btn = document.createElement('button');
    btn.textContent = cat.replace('Vino ','').replace('Vinos ','');
    btn.dataset.cat = cat;
    btn.style.cssText = `background:#2a1015;border:1px solid #3d1a1e;border-radius:10px;
      padding:3px 10px;font-size:0.7rem;color:#8a7070;cursor:pointer;`;
    btn.addEventListener('click', () => {{
      activeFilter = cat;
      filterDiv.querySelectorAll('button').forEach(b =>
        b.style.background = b.dataset.cat === cat ? '#3d1a1e' : '#2a1015');
      renderWineList(activeWines, document.getElementById('rp-search').value);
    }});
    filterDiv.appendChild(btn);
  }});

  document.getElementById('rp-search').addEventListener('input', e =>
    renderWineList(activeWines, e.target.value));

  renderWineList(activeWines, '');
  panel.style.display = 'flex';
  map.invalidateSize();
}}

// ── Layer groups for map filter buttons ─────────────────────────────────────
const layerAll      = L.layerGroup().addTo(map);  // visible by default
const layerNew      = L.layerGroup();
const layerExisting = L.layerGroup();

D.regions.forEach(r => {{
  const radius = Math.max(7, Math.min(38, 7 + r.count * 0.9));
  const hasNew = r.new_count > 0;
  const color  = hasNew ? '#e74c3c' : '#5d8aa8';
  const marker = L.circleMarker([r.lat, r.lng], {{
    radius, fillColor: color, color: '#fff',
    weight: 1.5, opacity: 0.9, fillOpacity: hasNew ? 0.75 : 0.45,
  }})
  .on('click', () => openPanel(r))
  .bindTooltip(`<b>${{r.name}}</b> — ${{r.count}} vinos${{hasNew ? ` · ★ ${{r.new_count}} nuevos` : ''}}`,
               {{ direction:'top', offset:[0,-6] }});

  layerAll.addLayer(marker);
  (hasNew ? layerNew : layerExisting).addLayer(marker);
}});

// ── Update button labels with region counts ──────────────────────────────────
(function updateFilterCounts() {{
  const nAll = D.regions.length;
  const nNew = D.regions.filter(r => r.new_count > 0).length;
  const nEx  = nAll - nNew;
  document.getElementById('mfb-all').textContent      = `Todas las regiones (${{nAll}})`;
  document.getElementById('mfb-new').textContent      = `★ Solo con nuevos (${{nNew}})`;
  document.getElementById('mfb-existing').textContent = `Sin cambios (${{nEx}})`;
}})();

// ── Wire filter buttons ──────────────────────────────────────────────────────
const filterGroups = {{ all: layerAll, new: layerNew, existing: layerExisting }};
document.querySelectorAll('.map-filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const f = btn.dataset.filter;
    // Update active style
    document.querySelectorAll('.map-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    // Swap layer groups
    Object.values(filterGroups).forEach(lg => map.removeLayer(lg));
    filterGroups[f].addTo(map);
    // Update count badge in button if needed
    map.invalidateSize();
  }});
}});

// No-region notice
if (D.regions.length === 0) {{
  document.querySelector('.map-header h3').textContent =
    '⚠️  No se detectaron regiones en los nombres de vinos esta corrida';
}}

// ── TLWM gauges ──────────────────────────────────────────────────────────────
const T = D.tlwm;
if (T.is_baseline) document.getElementById('tlwm-baseline-notice').style.display = 'block';
setTimeout(() => {{
  setGauge('tlwm-total', T.total,       T.total);
  setGauge('tlwm-new',   T.new_total,   Math.max(T.new_total, 10));
  setGauge('tlwm-drops', T.n_drops,     Math.max(T.n_drops, 10));
  setGauge('tlwm-rises', T.n_increases, Math.max(T.n_increases, 10));
}}, 300);
document.getElementById('tlwm-gc-new').addEventListener('click', () => {{
  if (!T.new_wines_list.length) return;
  const wines = T.new_wines_list.map(w => ({{...w, cat: w.type || 'TLWM'}}));
  openModal('🍷 TLWM — Nuevos Vinos', `${{T.new_total}} vino(s) nuevo(s) en The Little Wine Market`, wines, 'new');
}});
document.getElementById('tlwm-gc-drops').addEventListener('click', () => {{
  if (!T.drops_list.length) return;
  const wines = T.drops_list.map(w => ({{...w, cat: 'TLWM'}}));
  openModal('📉 TLWM — Descuentos', `${{T.n_drops}} vino(s) con precio más bajo`, wines, 'drops');
}});
document.getElementById('tlwm-gc-rises').addEventListener('click', () => {{
  if (!T.increases_list.length) return;
  const wines = T.increases_list.map(w => ({{...w, cat: 'TLWM'}}));
  openModal('📈 TLWM — Alzas', `${{T.n_increases}} vino(s) con precio más alto`, wines, 'rises');
}});

// ── Watchlist cards ──────────────────────────────────────────────────────────
const grid = document.getElementById('watchlist-grid');
if (D.watchlist.length === 0) {{
  grid.innerHTML = '<p style="color:var(--muted);grid-column:1/-1">No hay productos en el watchlist.</p>';
}}
D.watchlist.forEach((w, idx) => {{
  const card = document.createElement('div');
  card.className = 'wl-card';

  if (w.pending) {{
    card.innerHTML = `
      <div class="wl-name">${{w.name}}</div>
      <div class="wl-site">${{w.site}}</div>
      <div style="margin-top:12px;color:var(--muted);font-size:0.8rem">
        ⏳ Actualizando precio…
      </div>`;
    grid.appendChild(card);
    return;
  }}

  const hist     = w.history || [];
  const priceStr = w.price != null
    ? '$' + w.price.toLocaleString('es-MX', {{minimumFractionDigits:2}}) + ' ' + w.currency
    : '—';
  const prev     = hist.length >= 2 ? hist[hist.length - 2].price : null;
  let changeHtml = '';
  if (prev && w.price) {{
    const diff = w.price - prev;
    const pct  = (diff / prev * 100).toFixed(1);
    changeHtml = diff < 0
      ? `<span class="wl-change down">▼ ${{Math.abs(pct)}}% vs última lectura</span>`
      : diff > 0
        ? `<span class="wl-change up">▲ ${{pct}}% vs última lectura</span>`
        : `<span style="color:var(--muted);font-size:0.78rem">Sin cambio</span>`;
  }}

  card.innerHTML = `
    <div class="wl-name">${{w.name}}</div>
    <div class="wl-site">${{w.site}}</div>
    <div class="wl-price">${{priceStr}}</div>
    ${{changeHtml}}
    ${{hist.length > 1
      ? `<div class="wl-chart-wrap"><canvas id="wl-chart-${{idx}}"></canvas></div>`
      : `<div class="no-history">Sin historial de precios aún</div>`}}
  `;
  grid.appendChild(card);

  if (hist.length > 1) {{
    const labels = hist.map(h => h.date);
    const prices = hist.map(h => h.price);
    const minP   = Math.min(...prices.filter(p=>p!=null)) * 0.97;
    const maxP   = Math.max(...prices.filter(p=>p!=null)) * 1.03;
    new Chart(document.getElementById(`wl-chart-${{idx}}`), {{
      type: 'line',
      data: {{
        labels,
        datasets: [{{ label: 'Precio', data: prices,
          borderColor: '#d4a843', backgroundColor: 'rgba(212,168,67,0.1)',
          tension: 0.3, fill: true, pointRadius: 4,
          pointBackgroundColor: prices.map((p,i) => {{
            if (i === 0) return '#d4a843';
            return p < prices[i-1] ? '#27ae60' : p > prices[i-1] ? '#e74c3c' : '#d4a843';
          }})
        }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }},
          tooltip: {{ callbacks: {{ label: ctx =>
            ' $' + ctx.parsed.y.toLocaleString('es-MX',{{minimumFractionDigits:2}}) + ' ' + w.currency
          }} }}
        }},
        scales: {{
          x: {{ ticks: {{ color:'#8a7070', font:{{size:9}}, maxRotation:0 }}, grid:{{color:'#2a1015'}} }},
          y: {{ ticks: {{ color:'#8a7070', font:{{size:9}},
                          callback: v => '$'+v.toLocaleString('es-MX') }},
               grid:{{color:'#2a1015'}}, min: minP, max: maxP }},
        }}
      }}
    }});
  }}
}});
</script>
</body>
</html>"""

    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("Dashboard generado: %s", DASHBOARD_FILE.name)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    today = date.today().isoformat()
    log.info("=" * 60)
    log.info("Wine Monitor — %s", today)
    log.info("=" * 60)

    # 1. Costco
    costco_snapshot, costco_changes, costco_history = run_costco(today)

    # 2. The Little Wine Market
    tlwm_snapshot, tlwm_changes, tlwm_history = run_tlwm(today)

    # 3. Fast watchlist (requests-based — no browser needed)
    watchlist_history = load_json(WATCHLIST_HISTORY_FILE)
    fast_results = watchlist_fetch_group(browser=False)

    # 4. Generate initial dashboard immediately with "⏳ Actualizando…" for Soriana
    pending = watchlist_pending_placeholders()
    generate_dashboard(today, costco_snapshot, costco_changes, costco_history,
                       tlwm_snapshot, tlwm_changes, tlwm_history,
                       fast_results + pending, watchlist_history)
    log.info("── Dashboard inicial listo — iniciando Soriana (browser)…")

    # 5. Fetch browser-based items (Soriana / Selenium) and regenerate dashboard
    browser_results = watchlist_fetch_group(browser=True)
    all_results = fast_results + browser_results
    watchlist_history = watchlist_update_history(watchlist_history, all_results, today)
    prepend_to_file(WATCHLIST_FINDINGS_FILE, watchlist_build_report(all_results, watchlist_history, today))
    save_json(WATCHLIST_HISTORY_FILE, watchlist_history)
    generate_dashboard(today, costco_snapshot, costco_changes, costco_history,
                       tlwm_snapshot, tlwm_changes, tlwm_history,
                       all_results, watchlist_history)
    watchlist_results = all_results

    # 6. Toast summary
    parts: list[str] = []
    if costco_changes:
        n_new = sum(len(v) for v in costco_changes.get("new_wines", {}).values())
        n_d   = sum(len(v) for v in costco_changes.get("price_drops", {}).values())
        n_i   = sum(len(v) for v in costco_changes.get("price_increases", {}).values())
        if n_new: parts.append(f"{n_new} nuevo(s) en Costco")
        if n_d:   parts.append(f"{n_d} descuento(s) Costco 📉")
        if n_i:   parts.append(f"{n_i} alza(s) Costco 📈")
    if tlwm_changes:
        if tlwm_changes["new_wines"]: parts.append(f"{len(tlwm_changes['new_wines'])} nuevo(s) TLWM")
        if tlwm_changes["drops"]:     parts.append(f"{len(tlwm_changes['drops'])} descuento(s) TLWM 📉")
    if all_results:
        nd = sum(1 for r in all_results if r["price"] and
                 watchlist_prev_price(watchlist_history, r["url"]) and
                 r["price"] < watchlist_prev_price(watchlist_history, r["url"]))
        ni = sum(1 for r in all_results if r["price"] and
                 watchlist_prev_price(watchlist_history, r["url"]) and
                 r["price"] > watchlist_prev_price(watchlist_history, r["url"]))
        if nd: parts.append(f"{nd} baja watchlist 📉")
        if ni: parts.append(f"{ni} sube watchlist 📈")

    if parts:
        send_toast("🍷 Wine Monitor — Cambios", "  |  ".join(parts))
    else:
        send_toast("🍷 Wine Monitor", "Sin cambios hoy. Dashboard actualizado.")

    log.info("=" * 60)
    log.info("Listo. Dashboard: %s", DASHBOARD_FILE.name)
    log.info("=" * 60)


if __name__ == "__main__":
    main()

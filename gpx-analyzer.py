# B.7.20 – Brevet Simulator (ultrasicher, in Blöcken)


import math
import datetime as dt
import numpy as np
import pandas as pd
import gpxpy
import gpxpy.geo
from fpdf import FPDF
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import branca.colormap as cm
import json
import io
import matplotlib
matplotlib.use("Agg")  # Server-Backend ohne Display -- notwendig auf Streamlit Cloud
import matplotlib.pyplot as plt
import datetime
import streamlit as st

# ---------------------------------------------------------
# Seitenkonfiguration -- MUSS der erste Streamlit-Befehl im Skript sein
# ---------------------------------------------------------
st.set_page_config(
    page_title="Brevet Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Hauptmenü (☰), Deploy-Button, "Manage app"-Statuswidget und Fußzeile
# ausblenden. Bewusst NUR einzelne Elemente per data-testid/#id ansprechen,
# NICHT den gemeinsamen Toolbar-Container (data-testid="stToolbar")
# verstecken -- ein Test hat gezeigt, dass sich der Sidebar-Ein-/Ausklapp-
# Button (der im selben Container sitzt) über eine CSS-Ausnahme dafür nicht
# zuverlässig wieder sichtbar machen lässt. Das würde das Wiederaufklappen
# einer eingeklappten Sidebar verhindern -- deshalb hier verzichtet.
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    /* Hauptmenü (☰), Deploy-Button, Status-Widget einzeln ausblenden */
    #MainMenu,
    [data-testid="stMainMenu"],
    [data-testid="stAppDeployButton"],
    [data-testid="stStatusWidget"] {
        visibility: hidden !important;
        display: none !important;
    }

    /* Standard-Streamlit-Fußzeile ausblenden */
    footer {
        visibility: hidden !important;
        display: none !important;
    }

    /* GitHub-Icon (Link zum Repo, von Streamlit Community Cloud bei
       öffentlichen Repos automatisch eingeblendet) ausblenden. Per
       Browser-Inspektion ermittelter echter Selektor: die SVG-Klasse
       "octicon-mark-github". Mit :has() wird gleich der komplette
       umschließende Link (<a>) mitversteckt, damit keine leere,
       trotzdem anklickbare Fläche übrig bleibt. */
    a:has(.octicon-mark-github),
    .octicon-mark-github {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Session-State sicher initialisieren
# ---------------------------------------------------------

if "params" not in st.session_state:
    st.session_state["params"] = {}

if "control_points" not in st.session_state:
    st.session_state["control_points"] = []

if "pause_points" not in st.session_state:
    st.session_state["pause_points"] = []

if "df_acp" not in st.session_state:
    st.session_state["df_acp"] = None

if "start_dt" not in st.session_state:
    st.session_state["start_dt"] = None

if "df_raw" not in st.session_state:
    st.session_state["df_raw"] = None

if "df" not in st.session_state:
    st.session_state["df"] = None

# ---------------------------------------------------------
# ÜBERSETZUNGEN (i18n)
# ---------------------------------------------------------
if "lang" not in st.session_state:
    st.session_state["lang"] = "de"

TRANSLATIONS = {
    "lang_select_label": {"de": "Sprache", "en": "Language"},

    "settings_load_header": {"de": "🔄 Einstellungen laden", "en": "🔄 Load settings"},
    "settings_load_uploader": {"de": "Gespeicherte Einstellungen laden", "en": "Load saved settings"},
    "settings_load_success": {"de": "Einstellungen erfolgreich geladen!", "en": "Settings loaded successfully!"},

    "start_header": {"de": "Startzeit", "en": "Start time"},
    "start_date_label": {"de": "Datum", "en": "Date"},
    "start_time_label": {"de": "Zeit", "en": "Time"},

    "brevet_length_header": {"de": "Brevet-Länge", "en": "Brevet distance"},
    "brevet_length_label": {"de": "Distanz", "en": "Distance"},
    "brevet_1200plus_label": {"de": "1200+ km", "en": "1200+ km"},
    "max_time_label": {"de": "Maximalzeit (HH:MM)", "en": "Max. time (HH:MM)"},
    "max_time_help": {
        "de": "Offizielle ACP-Regelzeit für die gewählte Distanz, frei editierbar. Werte: 200 km = 13:30, 300 km = 20:00, 400 km = 27:00, 600 km = 40:00, 1000 km = 75:00, 1200 km = 90:00.",
        "en": "Official ACP time limit for the selected distance, freely editable. Values: 200 km = 13:30, 300 km = 20:00, 400 km = 27:00, 600 km = 40:00, 1000 km = 75:00, 1200 km = 90:00.",
    },
    "max_time_invalid": {"de": "Ungültiges Zeitformat. Bitte HH:MM eingeben (z.B. 27:00).", "en": "Invalid time format. Please enter HH:MM (e.g. 27:00)."},
    "max_time_1200plus_note": {
        "de": "Für Strecken über 1200 km gibt es keine feste ACP-Zeit – sie hängt von der tatsächlichen Distanz und den Regeln des Veranstalters ab (LRM-Richtwert: ca. 13,33 km/h Mindesttempo bis 1299 km, danach abnehmend). Bitte manuell anpassen.",
        "en": "For distances beyond 1200 km there is no fixed ACP time – it depends on the actual distance and the organizer's rules (LRM guideline: approx. 13.33 km/h minimum pace up to 1299 km, decreasing beyond that). Please adjust manually.",
    },

    "rider_header": {"de": "Fahrer & Rad", "en": "Rider & bike"},
    "weight_label": {"de": "Gesamtgewicht (kg)", "en": "Total weight (kg)"},

    "power_header": {"de": "Leistung / FTP", "en": "Power / FTP"},
    "ftp_label": {"de": "FTP (Watt)", "en": "FTP (watts)"},
    "power_caption": {"de": "Leistung automatisch aus FTP berechnet:", "en": "Power automatically calculated from FTP:"},
    "power_flat": {"de": "Flach: {w} W", "en": "Flat: {w} W"},
    "power_up": {"de": "Bergauf: {w} W", "en": "Uphill: {w} W"},
    "power_down": {"de": "Bergab: {w} W", "en": "Downhill: {w} W"},

    "speeds_header": {"de": "Zielgeschwindigkeiten (automatisch aus FTP, aber überschreibbar)", "en": "Target speeds (auto from FTP, but overridable)"},
    "spd_down_label": {"de": "Bergab", "en": "Downhill"},
    "spd_ldown_label": {"de": "Leicht bergab", "en": "Slightly downhill"},
    "spd_flat_label": {"de": "Flach", "en": "Flat"},
    "spd_lup_label": {"de": "Leicht bergauf", "en": "Slightly uphill"},
    "spd_mup_label": {"de": "Mittel bergauf", "en": "Moderate uphill"},
    "spd_sup_label": {"de": "Steil bergauf", "en": "Steep uphill"},
    "spd_vsup_label": {"de": "Sehr steil", "en": "Very steep"},

    "physics_header": {"de": "Physik", "en": "Physics"},
    "cda_label": {"de": "CdA", "en": "CdA"},
    "crr_label": {"de": "Crr", "en": "Crr"},
    "wind_label": {"de": "Wind (km/h)", "en": "Wind (km/h)"},
    "wind_ang_label": {"de": "Windrichtung (° Kompass, aus der der Wind kommt)", "en": "Wind direction (° compass, direction wind is coming from)"},
    "wind_ang_short_label": {"de": "Richtung (° Kompass)", "en": "Direction (° compass)"},
    "point_wind_caption": {
        "de": "Wind gilt jeweils für den Abschnitt, der an diesem Punkt endet. Richtung als Kompasskurs (0°=Nord, 90°=Ost, 180°=Süd, 270°=West), unabhängig von der Fahrtrichtung -- sinnvoll v.a. bei Rundkursen.",
        "en": "Wind applies to the segment ending at this point. Direction as a compass bearing (0°=North, 90°=East, 180°=South, 270°=West), independent of travel direction -- especially useful for loop routes.",
    },
    "max_down_label": {"de": "Max. Abfahrt (km/h)", "en": "Max. downhill (km/h)"},
    "min_spd_label": {"de": "Min. Geschwindigkeit (km/h)", "en": "Min. speed (km/h)"},

    "hybrid_label": {"de": "Hybrid-Faktor (Physik ↔ Zieltempo)", "en": "Hybrid factor (physics ↔ target speed)"},
    "hybrid_help": {
        "de": "0 = nur Leistungs-/Physikmodell (FTP, CdA, Crr, Wind). 1 = nur die manuell eingetragenen Zielgeschwindigkeiten je Steigungsklasse.",
        "en": "0 = power/physics model only (FTP, CdA, Crr, wind). 1 = only the manually entered target speeds per gradient class.",
    },

    "fatigue_header": {"de": "Ermüdung", "en": "Fatigue"},
    "fatigue_k_label": {"de": "Max. Geschwindigkeitsverlust durch Ermüdung (%)", "en": "Max. speed loss from fatigue (%)"},
    "fatigue_k_help": {"de": "Wie viel langsamer du bist, wenn die Ermüdung ihr Maximum erreicht hat.", "en": "How much slower you are once fatigue has reached its maximum."},
    "fatigue_hours_label": {"de": "Fahrzeit bis maximale Ermüdung (Stunden)", "en": "Riding time until maximum fatigue (hours)"},
    "fatigue_hours_help": {
        "de": "Nach so vielen Stunden AKTIVER Fahrzeit (ohne Pausen) ist die Ermüdung maximal. Pausen verlangsamen/stoppen diese Uhr (siehe unten).",
        "en": "After this many hours of ACTIVE riding time (excluding breaks), fatigue is at its maximum. Breaks slow down/stop this clock (see below).",
    },
    "pause_recovery_label": {"de": "Erholung pro Pausenminute", "en": "Recovery per break minute"},
    "pause_recovery_help": {
        "de": "Wie viele Minuten 'Ermüdungszeit' eine Minute Pause abbaut. Beispiel: 3.0 → eine 10-minütige Pause an einem Kontroll- oder Pausenpunkt reduziert die aufgelaufene Ermüdung so, als wärst du 30 Minuten weniger gefahren.",
        "en": "How many minutes of 'fatigue time' one minute of break removes. Example: 3.0 → a 10-minute break at a control or pause point reduces accumulated fatigue as if you had ridden 30 minutes less.",
    },

    "cp_header": {"de": "Kontrollpunkte", "en": "Control points"},
    "cp_count_label": {"de": "Anzahl KP", "en": "Number of CPs"},
    "cp_name_label": {"de": "KP {i} Name", "en": "CP {i} Name"},
    "cp_km_label": {"de": "KP {i} km", "en": "CP {i} km"},
    "cp_pause_label": {"de": "KP {i} Pause (min)", "en": "CP {i} Break (min)"},

    "pp_header": {"de": "Pausenpunkte", "en": "Pause points"},
    "pp_count_label": {"de": "Anzahl PP", "en": "Number of PPs"},
    "pp_name_label": {"de": "PP {i} Name", "en": "PP {i} Name"},
    "pp_km_label": {"de": "PP {i} km", "en": "PP {i} km"},
    "pp_pause_label": {"de": "PP {i} Pause (min)", "en": "PP {i} Break (min)"},

    "gpx_uploader_label": {"de": "GPX-Datei hochladen", "en": "Upload GPX file"},
    "error_no_cp": {"de": "Keine gültigen Kontrollpunkte gefunden – df_sum ist leer.", "en": "No valid control points found – summary is empty."},

    "metric_distance": {"de": "Streckenlänge", "en": "Distance"},
    "metric_total_time": {"de": "Gesamtzeit (HH:MM)", "en": "Total time (HH:MM)"},
    "metric_avg_total": {"de": "Ø‑Geschwindigkeit gesamt", "en": "Avg. speed overall"},
    "metric_pause_total": {"de": "Pausen gesamt", "en": "Total breaks"},
    "metric_arrival": {"de": "Ankunft", "en": "Arrival"},
    "metric_moving_time": {"de": "Fahrzeit ohne Pausen (HH:MM)", "en": "Riding time excl. breaks (HH:MM)"},
    "metric_avg_moving": {"de": "Ø‑Geschwindigkeit ohne Pausen", "en": "Avg. speed excl. breaks"},
    "metric_total_time_short": {"de": "Gesamtzeit", "en": "Total time"},

    "subheader_elevation": {"de": "Höhenprofil", "en": "Elevation profile"},
    "subheader_map": {"de": "Karte", "en": "Map"},
    "elevation_click_hint": {
        "de": "Klicke auf eine Stelle im Höhenprofil, um die Position auf der Karte unten zu markieren.",
        "en": "Click a point on the elevation profile to highlight that position on the map below.",
    },
    "subheader_summary": {"de": "Zusammenfassung", "en": "Summary"},
    "subheader_export": {"de": "Export", "en": "Export"},

    "elevation_title": {"de": "Höhenprofil (geglättet)", "en": "Elevation profile (smoothed)"},
    "elevation_xaxis": {"de": "Kilometer", "en": "Kilometers"},
    "elevation_yaxis": {"de": "Höhe (m)", "en": "Elevation (m)"},

    "map_start": {"de": "Start", "en": "Start"},
    "map_finish": {"de": "Ziel", "en": "Finish"},
    "map_pause_prefix": {"de": "Pause", "en": "Break"},

    "type_cp": {"de": "KP", "en": "CP"},
    "type_pp": {"de": "PP", "en": "PP"},

    "col_typ": {"de": "Typ", "en": "Type"},
    "col_name": {"de": "Name", "en": "Name"},
    "col_km": {"de": "Km", "en": "Km"},
    "col_km_seg": {"de": "Km Abschnitt", "en": "Km segment"},
    "col_hm": {"de": "Hm", "en": "Elev (m)"},
    "col_hm_seg": {"de": "Hm Abschnitt", "en": "Elev seg (m)"},
    "col_date": {"de": "Datum", "en": "Date"},
    "col_weekday": {"de": "Tag", "en": "Day"},
    "col_arrival": {"de": "Ankunft", "en": "Arrival"},
    "col_arrival_day": {"de": "Ankunft Tag", "en": "Arrival day"},
    "col_arrival_time": {"de": "Ankunft Uhrzeit", "en": "Arrival time"},
    "col_departure": {"de": "Abfahrt", "en": "Departure"},
    "col_departure_day": {"de": "Abfahrt Tag", "en": "Departure day"},
    "col_departure_time": {"de": "Abfahrt Uhrzeit", "en": "Departure time"},
    "col_time_seg": {"de": "Zeit Abschnitt", "en": "Time segment"},
    "col_avg_kmh": {"de": "Ø‑km/h", "en": "Avg km/h"},
    "col_avg_kmh_seg": {"de": "Ø‑km/h Abschnitt", "en": "Avg km/h seg"},
    "col_pause_min": {"de": "Pause", "en": "Break"},

    "grad_downhill": {"de": "Bergab", "en": "Downhill"},
    "grad_light_downhill": {"de": "Leicht bergab", "en": "Slightly downhill"},
    "grad_flat": {"de": "Flach", "en": "Flat"},
    "grad_light_up": {"de": "Leicht bergauf", "en": "Slightly uphill"},
    "grad_moderate_up": {"de": "Mittel bergauf", "en": "Moderate uphill"},
    "grad_steep_up": {"de": "Steil bergauf", "en": "Steep uphill"},
    "grad_very_steep_up": {"de": "Sehr steil bergauf", "en": "Very steep uphill"},
    "col_name_help": {"de": "Name des Kontroll- oder Pausenpunkts", "en": "Name of the control or pause point"},

    "settings_filename_label": {"de": "Dateiname für die Einstellungen", "en": "Filename for the settings"},
    "settings_filename_help": {"de": "Ohne Dateiendung – .json wird automatisch angehängt.", "en": "Without file extension – .json is appended automatically."},
    "settings_filename_submit": {"de": "Namen übernehmen", "en": "Apply name"},
    "settings_filename_caption": {
        "de": "Der Speicherort (Ordner) wird von deinem Browser bestimmt: Standard-Download-Ordner, oder ein Auswahldialog, falls dein Browser 'Vor jedem Download nach Speicherort fragen' aktiviert hat (Chrome/Edge: Einstellungen → Downloads).",
        "en": "The save location (folder) is determined by your browser: default download folder, or a chooser dialog if your browser has 'Ask where to save each file' enabled (Chrome/Edge: Settings → Downloads).",
    },
    "settings_filename_current": {"de": "Aktueller Dateiname: **{name}**", "en": "Current filename: **{name}**"},

    "save_settings_button": {"de": "💾 Einstellungen speichern", "en": "💾 Save settings"},
    "export_excel_button": {"de": "Excel exportieren", "en": "Export Excel"},

    "gpx_info": {"de": "Bitte eine GPX-Datei hochladen, um die Simulation zu starten.", "en": "Please upload a GPX file to start the simulation."},

    "subheader_elevation_segments": {"de": "Höhenprofil nach Abschnitten", "en": "Elevation profile by segment"},
    "export_elevation_jpeg_button": {"de": "📷 Höhendiagramm als JPEG exportieren", "en": "📷 Export elevation chart as JPEG"},
    "no_segments_info": {
        "de": "Für das Abschnitts-Höhendiagramm wird mindestens ein Kontroll- oder Pausenpunkt benötigt.",
        "en": "The segmented elevation chart requires at least one control or pause point.",
    },
    "label_pause_short": {"de": "Pause", "en": "Break"},

    "pdf_title": {"de": "Brevet Zusammenfassung", "en": "Brevet summary"},
}


def T(key, **kwargs):
    """Übersetzten Text für den aktuell gewählten UI-Sprache zurückgeben."""
    lang = st.session_state.get("lang", "de")
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang, entry.get("de", key))
    if kwargs:
        return text.format(**kwargs)
    return text

def create_acp_dataframe():
    data = {
        "distance": [0, 200, 300, 400, 600, 1000],
        "open":     [0, 5.53, 8.0, 10.0, 15.0, 28.0],
        "close":    [0, 13.5, 20.0, 27.0, 40.0, 75.0]
    }

    df = pd.DataFrame(data)
    df["open_seconds"] = (df["open"] * 3600).astype(int)
    df["close_seconds"] = (df["close"] * 3600).astype(int)
    return df

df_acp = create_acp_dataframe()

G = 9.81
AIR = 1.226

# -----------------------------------------------------
# Zeitformat definieren
# -----------------------------------------------------
def parse_time_to_seconds(tstr):
    """
    Konvertiert jeden möglichen timedelta-String robust in Sekunden.
    Beispiele:
    - '1:23:45'
    - '12:34'
    - '1 day, 2:03:04'
    - '0:03:04.123456'
    """
    tstr = tstr.strip()

    days = 0

    # Fall: "1 day, 2:03:04"
    if "day" in tstr:
        day_part, time_part = tstr.split(",", 1)
        days = int(day_part.split()[0])
        tstr = time_part.strip()

    # Millisekunden entfernen
    if "." in tstr:
        tstr = tstr.split(".")[0]

    parts = tstr.split(":")

    # Fall: MM:SS
    if len(parts) == 2:
        m, s = map(int, parts)
        h = 0

    # Fall: HH:MM:SS
    elif len(parts) == 3:
        h, m, s = map(int, parts)

    else:
        raise ValueError(f"Unbekanntes Zeitformat: {tstr}")

    return days*86400 + h*3600 + m*60 + s


def format_hhmm(seconds):
    """Konvertiert Sekunden in HH:MM (immer zweistellig)."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def format_decimal(value, decimals=1):
    """
    Formatiert eine Zahl mit fester Anzahl Nachkommastellen (immer, auch bei
    glatten Werten wie 20 -> '20,0') und sprachabhängigem Dezimaltrennzeichen:
    Komma für Deutsch, Punkt für Englisch.
    """
    lang = st.session_state.get("lang", "de")
    s = f"{value:.{decimals}f}"
    if lang == "de":
        s = s.replace(".", ",")
    return s


def parse_hhmm_to_seconds(tstr):
    """
    Konvertiert einen 'HH:MM'-String (z.B. ACP-Maximalzeit '13:30' = 13 Std.
    30 Min.) in Sekunden. Bewusst getrennt von parse_time_to_seconds(), das
    einen 2-teiligen String als MM:SS interpretiert (Pandas-Timedelta-Stil) –
    für unsere Zwecke ('HH:MM' als Stunden:Minuten) wäre das falsch.
    """
    tstr = tstr.strip()
    parts = tstr.split(":")
    if len(parts) != 2:
        raise ValueError(f"Erwarte Format HH:MM, erhalten: {tstr}")
    h, m = parts
    h = int(h)
    m = int(m)
    if m < 0 or m > 59 or h < 0:
        raise ValueError(f"Ungültige HH:MM-Werte: {tstr}")
    return h * 3600 + m * 60

# -----------------------------------------------------
# GPX PARSER (ohne Cache)
# -----------------------------------------------------
def parse_gpx(file):
    gpx = gpxpy.parse(file)

    lats, lons, elevs, dists = [], [], [], []
    total = 0.0
    last = None

    for track in gpx.tracks:
        for seg in track.segments:
            for p in seg.points:
                lats.append(p.latitude)
                lons.append(p.longitude)
                elevs.append(p.elevation)

                if last:
                    dx = gpxpy.geo.haversine_distance(
                        last.latitude, last.longitude, p.latitude, p.longitude
                    )
                    if dx is None or math.isnan(dx):
                        dx = 0.0
                    total += dx

                dists.append(total)
                last = p

    df = pd.DataFrame({
        "lat": pd.to_numeric(lats, errors="coerce"),
        "lon": pd.to_numeric(lons, errors="coerce"),
        "elev": pd.to_numeric(elevs, errors="coerce"),
        "distance_m": pd.to_numeric(dists, errors="coerce"),
    })

    df["lat"] = df["lat"].ffill()
    df["lon"] = df["lon"].ffill()
    df["elev"] = df["elev"].ffill().bfill()

    dh = df["elev"].diff().fillna(0)
    dx = df["distance_m"].diff().fillna(1)
    df["gradient"] = (dh / dx) * 100

    return df

# -----------------------------------------------------
# DOWNSAMPLING (10× schneller)
# -----------------------------------------------------
def downsample(df, n=1500):
    if len(df) <= n:
        return df
    idx = np.linspace(0, len(df) - 1, n).astype(int)
    return df.iloc[idx].reset_index(drop=True)

# -----------------------------------------------------
# ACP TIMES (optional, aktuell nicht genutzt)
# -----------------------------------------------------
def compute_acp_times(df):
    max_s = [(200, 34), (400, 32), (600, 30), (1000, 28), (1300, 26)]
    min_s = [(200, 15), (400, 15), (600, 15), (1000, 11.428), (1300, 13.333)]

    def acp(km, table):
        rem = km
        h = 0
        for lim, sp in table:
            if rem <= 0:
                break
            seg = min(rem, lim)
            h += seg / sp
            rem -= seg
        return h * 3600

    rows = []
    for _, r in df.iterrows():
        km = r["distance_m"] / 1000
        rows.append({
            "km": km,
            "open_s": acp(km, max_s),
            "close_s": acp(km, min_s)
        })
    return pd.DataFrame(rows)

# -----------------------------------------------------
# WIND
# -----------------------------------------------------
def wind_component(w, ang):
    """Wind in km/h + Winkel (0° = Gegenwind) -> Gegenwind-Komponente in m/s."""
    return (w / 3.6) * math.cos(math.radians(ang))


def compute_bearing(lat1, lon1, lat2, lon2):
    """Fahrtrichtung (Kompasskurs, 0-360°, 0=Nord) von Punkt 1 nach Punkt 2."""
    lat1r, lon1r, lat2r, lon2r = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2r - lon1r
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360) % 360

# -----------------------------------------------------
# PHYSIK-MODELL: Geschwindigkeit aus Leistung lösen
# -----------------------------------------------------
def required_power(v_ms, grad_percent, weight_kg, cda, crr, wind_ms):
    """
    Leistung (W), die nötig ist, um mit v_ms (m/s über Grund) bei gegebener
    Steigung, Gesamtgewicht, CdA, Crr und Gegenwind-Komponente (wind_ms,
    positiv = Gegenwind) zu fahren.
    """
    if v_ms <= 0:
        return 0.0

    theta = math.atan(grad_percent / 100.0)
    v_air = v_ms + wind_ms  # Anströmgeschwindigkeit der Luft

    # Luftwiderstand behält bei Rückenwind (v_air < 0) das Vorzeichen bei
    drag_force = 0.5 * AIR * cda * v_air * abs(v_air)
    roll_force = crr * weight_kg * G * math.cos(theta)
    grade_force = weight_kg * G * math.sin(theta)

    total_force = drag_force + roll_force + grade_force
    return max(total_force, 0.0) * v_ms


def solve_speed_from_power(power_w, grad_percent, weight_kg, cda, crr, wind_ms):
    """Löst v (km/h) numerisch per Bisektion für eine gegebene Leistung."""
    lo, hi = 0.3, 35.0  # Suchraum in m/s (~1 – 126 km/h)

    # Falls selbst bei minimaler Geschwindigkeit mehr Leistung nötig ist als
    # verfügbar (z.B. extreme Steigung, wenig Watt) -> Minimalgeschwindigkeit
    if required_power(lo, grad_percent, weight_kg, cda, crr, wind_ms) >= power_w:
        return lo * 3.6

    for _ in range(30):
        mid = (lo + hi) / 2
        p = required_power(mid, grad_percent, weight_kg, cda, crr, wind_ms)
        if p < power_w:
            lo = mid
        else:
            hi = mid

    return ((lo + hi) / 2) * 3.6

# -----------------------------------------------------
# HAVERSINE (Meter)
# -----------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# -----------------------------------------------------
# DISTANZ BERECHNEN (Meter)
# -----------------------------------------------------
def compute_distance(df):
    dist = [0.0]
    for i in range(1, len(df)):
        lat1, lon1 = df.loc[i-1, "lat"], df.loc[i-1, "lon"]
        lat2, lon2 = df.loc[i, "lat"], df.loc[i, "lon"]
        d = haversine(lat1, lon1, lat2, lon2)
        dist.append(dist[-1] + d)
    return np.array(dist)

# -----------------------------------------------------
# STEIGUNG / GRADIENT (%)
# -----------------------------------------------------
def compute_gradient(df):
    elev = df["elev"].values
    dist = df["distance_m"].values

    grad = np.zeros(len(df))
    for i in range(1, len(df)):
        dh = elev[i] - elev[i-1]
        dx = dist[i] - dist[i-1]
        grad[i] = (dh / dx) * 100 if dx > 0 else 0
    return grad

# -----------------------------------------------------
# GESCHWINDIGKEIT BERECHNEN (Hybrid: Physik + Zieltempo)
# -----------------------------------------------------
def compute_speed(df, params, pause_events=None):
    """
    pause_events: Liste von {"km": ..., "pause_min": ...} (Kontroll- und
    Pausenpunkte zusammen). Wird für die zeitbasierte Ermüdung gebraucht:
    die Ermüdung wächst mit der bereits gefahrenen Zeit (nicht mit der
    Distanz) und wird durch Pausen anteilig wieder abgebaut.
    """
    pause_events = sorted(pause_events or [], key=lambda e: e["km"])

    # Ermüdungsparameter (zeitbasiert)
    fatigue_k = params.get("fatigue_k", 0.25)            # max. Geschwindigkeitsverlust (Anteil)
    fatigue_hours = params.get("fatigue_hours", 20.0)    # Fahrzeit bis maximale Ermüdung
    fatigue_min_factor = params.get("fatigue_min_factor", 0.5)  # Untergrenze (nie langsamer als 50%)
    pause_recovery = params.get("pause_recovery", 3.0)   # "Ermüdungsminuten"-Abbau pro Pausenminute

    # Geschwindigkeiten aus params (Zieltempo-Modell)
    spd_down   = params["spd_down"]
    spd_ldown  = params["spd_ldown"]
    spd_flat   = params["spd_flat"]
    spd_lup    = params["spd_lup"]
    spd_mup    = params["spd_mup"]
    spd_sup    = params["spd_sup"]
    spd_vs_up  = params["spd_vs_up"]

    min_spd    = params["min_spd"]
    max_down   = params["max_down"]

    # Physik-Parameter
    weight  = params.get("weight", 85.0)
    cda     = params.get("cda", 0.28)
    crr     = params.get("crr", 0.004)

    # Wind je Abschnitt (Kontroll-/Pausenpunkt zu Kontroll-/Pausenpunkt) --
    # sinnvoll v.a. bei Rundkursen, wo sich die Fahrtrichtung über die
    # Strecke hinweg ändert. "wind_ang" ist ein ABSOLUTER Kompasskurs
    # (0°=Nord, 90°=Ost, ...), aus dem der Wind weht -- unabhängig von der
    # Fahrtrichtung. Liste von {"km_start", "km_end", "wind", "wind_ang"},
    # nach km_start sortiert.
    segment_winds = sorted(
        params.get("segment_winds", []) or [],
        key=lambda s: s.get("km_start", 0.0),
    )
    if not segment_winds and (params.get("wind", 0.0) or params.get("wind_ang", 0.0)):
        # Rückwärtskompatibilität: alte Einstellungsdateien ohne
        # segment_winds hatten einen einzigen globalen Windwert
        segment_winds = [{
            "km_start": 0.0, "km_end": float("inf"),
            "wind": params.get("wind", 0.0), "wind_ang": params.get("wind_ang", 0.0),
        }]
    wind_seg_idx = 0

    # Lokale Fahrtrichtung (Kompasskurs) an jedem Streckenpunkt vorab
    # berechnen, um die absolute Windrichtung in einen auf die jeweils
    # AKTUELLE Fahrtrichtung bezogenen Gegenwind-/Rückenwind-Winkel
    # umzurechnen (0° = Gegenwind, siehe wind_component()).
    lat_arr = df["lat"].values if "lat" in df.columns else None
    lon_arr = df["lon"].values if "lon" in df.columns else None

    ftp    = params.get("ftp", 250)
    w_flat = params.get("w_flat", int(ftp * 0.75))
    w_up   = params.get("w_up", int(ftp * 0.90))
    w_down = params.get("w_down", int(ftp * 0.50))

    # 0.0 = Geschwindigkeit rein aus Physik (FTP/CdA/Crr/Wind),
    # 1.0 = Geschwindigkeit rein aus den Zieltempo-Feldern
    hybrid_factor = params.get("hybrid_factor", 0.7)
    hybrid_factor = min(max(hybrid_factor, 0.0), 1.0)

    n = len(df)
    v_kmh = np.zeros(n)

    km_arr = df["km"].values
    grad_arr = df["gradient"].values
    dist_arr = df["distance_m"].values

    # "Ermüdungsuhr": akkumulierte Fahrzeit (Sekunden), abzüglich der durch
    # Pausen erholten Zeit. Wächst nur beim Fahren, wird an Pausenpunkten
    # zurückgesetzt (teilweise).
    fatigue_clock_s = 0.0
    event_idx = 0

    for i in range(n):

        km = km_arr[i]
        grad = grad_arr[i]

        # Windsegment für diesen Punkt bestimmen -- der Wind kann sich von
        # Kontroll-/Pausenpunkt zu Kontroll-/Pausenpunkt ändern (v.a. bei
        # Rundkursen relevant)
        if segment_winds:
            while (
                wind_seg_idx < len(segment_winds) - 1
                and km >= segment_winds[wind_seg_idx]["km_end"]
            ):
                wind_seg_idx += 1

            wind_speed = segment_winds[wind_seg_idx].get("wind", 0.0)
            wind_from_compass = segment_winds[wind_seg_idx].get("wind_ang", 0.0)

            # Lokale Fahrtrichtung an diesem Punkt (aus dem vorherigen zum
            # aktuellen Punkt, bzw. vom aktuellen zum nächsten am Streckenanfang)
            if lat_arr is not None and lon_arr is not None:
                if i == 0:
                    j = min(i + 1, n - 1)
                    local_bearing = compute_bearing(lat_arr[i], lon_arr[i], lat_arr[j], lon_arr[j])
                else:
                    local_bearing = compute_bearing(lat_arr[i - 1], lon_arr[i - 1], lat_arr[i], lon_arr[i])
            else:
                local_bearing = 0.0

            # Kompass-Windrichtung relativ zur lokalen Fahrtrichtung:
            # 0° = Gegenwind, 180° = Rückenwind (siehe wind_component())
            relative_wind_ang = wind_from_compass - local_bearing
            wind_ms = wind_component(wind_speed, relative_wind_ang)
        else:
            wind_ms = 0.0

        # Alle Pausen/Kontrollpunkte, die bis zu diesem Streckenpunkt
        # bereits passiert wurden, als Erholung verrechnen
        while event_idx < len(pause_events) and pause_events[event_idx]["km"] <= km:
            recovery_s = pause_events[event_idx]["pause_min"] * 60.0 * pause_recovery
            fatigue_clock_s = max(0.0, fatigue_clock_s - recovery_s)
            event_idx += 1

        # Ermüdungsfaktor abhängig von der bereits gefahrenen (erholungs-
        # bereinigten) Zeit, nicht von der Distanz
        fatigue_hours_elapsed = fatigue_clock_s / 3600.0
        if fatigue_hours > 0:
            fatigue = 1 - fatigue_k * (fatigue_hours_elapsed / fatigue_hours)
        else:
            fatigue = 1.0
        fatigue = max(fatigue, fatigue_min_factor)

        # --- Zieltempo-Modell: Basisgeschwindigkeit je nach Steigung ---
        # Grenzen: bergab < -6% | leicht bergab -6..0% | flach 0..2% |
        # leicht bergauf 2..4% | mittel bergauf 4..8% | steil bergauf 8..10%
        # | sehr steil bergauf >= 10%
        if grad < -6:
            base = spd_down
        elif grad < 0:
            base = spd_ldown
        elif grad < 2:
            base = spd_flat
        elif grad < 4:
            base = spd_lup
        elif grad < 8:
            base = spd_mup
        elif grad < 10:
            base = spd_sup
        else:
            base = spd_vs_up

        v_target = base * fatigue

        # --- Physik-Modell: Leistung -> Geschwindigkeit ---
        if grad < -2:
            power = w_down
        elif grad < 1:
            power = w_flat
        else:
            power = w_up
        power = power * fatigue

        v_physics = solve_speed_from_power(power, grad, weight, cda, crr, wind_ms)

        # --- Beide Modelle mischen ---
        v = hybrid_factor * v_target + (1 - hybrid_factor) * v_physics

        # Limits
        if grad < 0:
            v = min(v, max_down)

        v = max(v, min_spd)

        v_kmh[i] = v

        # Segmentzeit zu diesem Punkt zur Ermüdungsuhr addieren (gleiche
        # dx/v-Logik wie add_time_profile, damit beide konsistent bleiben)
        if i > 0:
            dx = dist_arr[i] - dist_arr[i - 1]
            v_ms = max(v_kmh[i] / 3.6, 0.1)
            fatigue_clock_s += dx / v_ms

    return v_kmh


# -----------------------------------------------------
# ZEITPROFIL BERECHNEN (Segmentzeit + kumulierte Zeit)
# -----------------------------------------------------
def add_time_profile(df, params):
    # Geschwindigkeit in m/s
    v_ms = df["speed_kmh"].values * (1000 / 3600)

    # Segmentzeiten
    time_s = np.zeros(len(df))
    for i in range(1, len(df)):
        dx = df["distance_m"].iloc[i] - df["distance_m"].iloc[i-1]
        v = max(v_ms[i], 0.1)  # Schutz gegen 0
        time_s[i] = dx / v

    df["time_s"] = time_s
    df["cum_seconds"] = df["time_s"].cumsum()

    return df

# -----------------------------------------------------
# ZUSAMMENFASSUNG ERZEUGEN
# -----------------------------------------------------
# Hinweis: control_points/pause_points werden NICHT hier oben gelesen,
# da die Sidebar-Editoren (Kontroll-/Pausenpunkte) und das Laden
# gespeicherter Einstellungen erst weiter unten laufen und den
# Session State verändern. Die aktuellen Werte werden erst unmittelbar
# vor dem build_summary()-Aufruf aus st.session_state geholt.


def build_summary(df, control_points, pause_points, start_dt, df_acp):

    # Übergebene Punkte verwenden (nicht erneut aus dem Session State lesen –
    # sonst kann build_summary mit anderen Werten aufgerufen werden, als
    # tatsächlich übergeben wurden, z.B. bei einer künftigen Vorschau-Funktion)
    cp_list = control_points
    pp_list = pause_points

    # Wochentags-Abkürzungen sprachabhängig (nicht von strftime()/Locale
    # abhängig machen, da auf Streamlit Cloud i.d.R. keine deutschen
    # Locale-Dateien installiert sind)
    weekday_abbr = {
        "de": ["MO", "DI", "MI", "DO", "FR", "SA", "SO"],
        "en": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"],
    }
    current_lang = st.session_state.get("lang", "de")

    rows = []

    # -------------------------
    # 1. Events sammeln (KP + PP)
    # -------------------------
    events = []

    for cp in cp_list:
        events.append({
            "type": T("type_cp"),
            "name": cp["name"],
            "km": float(cp["km"]),
            "pause": int(cp["pause"])
        })

    for pp in pp_list:
        events.append({
            "type": T("type_pp"),
            "name": pp["name"],
            "km": float(pp["km"]),
            "pause": int(pp["pause"])
        })

    # Wenn keine Events → leere Summary zurückgeben
    if len(events) == 0:
        return pd.DataFrame(), {
            "moving_seconds": 0,
            "total_seconds": 0,
            "arrival_dt": start_dt.strftime("%Y-%m-%d %H:%M")
        }

    # Sortieren nach km
    events = sorted(events, key=lambda x: x["km"])

    # -------------------------
    # 2. Initialwerte
    # -------------------------
    last_km = 0.0
    last_time = 0.0
    last_hm = 0.0
    total_pause_seconds = 0

    # -------------------------
    # 3. Summary berechnen
    # -------------------------
    for ev in events:

        # Index im Track finden
        idx = df.index[df["km"] >= ev["km"]].min()
        if pd.isna(idx):
            idx = df.index[-1]

        km = float(df.loc[idx, "km"])

        # Höhenmeter
        cum_hm = float(df.loc[idx, "hm_cum"])
        seg_hm = cum_hm - last_hm

        # Zeit
        cum_t = float(df.loc[idx, "cum_seconds"])
        seg_t = cum_t - last_time

        # Pause
        pause_min = ev["pause"]
        pause_s = pause_min * 60

        # Ankunftszeit (ohne Pause)
        arrival_dt = start_dt + pd.to_timedelta(cum_t + total_pause_seconds, unit="s")

        # Abfahrt (mit Pause)
        departure_dt = arrival_dt + pd.to_timedelta(pause_s, unit="s")

        # Pause zur Gesamtzeit addieren
        total_pause_seconds += pause_s

        # Gesamtzeit inkl. Pause
        total_seconds = cum_t + total_pause_seconds

        # Geschwindigkeiten
        seg_km = km - last_km
        avg_total = km / (total_seconds / 3600) if total_seconds > 0 else 0
        avg_seg = seg_km / (seg_t / 3600) if seg_t > 0 else 0

        # Zeile erzeugen (Reihenfolge: Name, Typ, Km Abschnitt, Km,
        # Hm Abschnitt, Hm, Ankunft Tag, Ankunft Uhrzeit, Pause,
        # Abfahrt Tag, Abfahrt Uhrzeit, Zeit Abschnitt, Ø-km/h Abschnitt,
        # Ø-km/h)
        rows.append({
            T("col_name"): ev["name"],
            T("col_typ"): ev["type"],

            T("col_km_seg"): round(seg_km),
            T("col_km"): round(km),

            T("col_hm_seg"): int(seg_hm),
            T("col_hm"): int(cum_hm),

            T("col_arrival_day"): weekday_abbr.get(current_lang, weekday_abbr["de"])[arrival_dt.weekday()],
            T("col_arrival_time"): arrival_dt.strftime("%H:%M"),

            T("col_pause_min"): format_hhmm(pause_s),

            T("col_departure_day"): weekday_abbr.get(current_lang, weekday_abbr["de"])[departure_dt.weekday()],
            T("col_departure_time"): departure_dt.strftime("%H:%M"),

            T("col_time_seg"): format_hhmm(seg_t),
            T("col_avg_kmh_seg"): format_decimal(avg_seg, 1),
            T("col_avg_kmh"): format_decimal(avg_total, 1),
        })

        # Update für nächsten Abschnitt
        last_km = km
        last_time = cum_t
        last_hm = cum_hm

    # -------------------------
    # 4. Rückgabe
    # -------------------------
    df_sum = pd.DataFrame(rows)

    raw_times = {
        "moving_seconds": float(last_time),
        "total_seconds": float(last_time + total_pause_seconds),
        "total_pause_seconds": float(total_pause_seconds),
        "arrival_dt": arrival_dt.strftime("%Y-%m-%d %H:%M")
    }

    return df_sum, raw_times




# -----------------------------------------------------
# EXCEL EXPORT
# -----------------------------------------------------
def export_excel(df):
    import io
    buf = io.BytesIO()

    # Spalten, die als echte Excel-Uhrzeit (hh:mm) statt als Text exportiert
    # werden sollen
    time_cols = [T("col_arrival_time"), T("col_departure_time")]
    # Spalten, die als echte Excel-Dauer ([hh]:mm, Stunden >23 möglich)
    # statt als Text exportiert werden sollen
    duration_cols = [T("col_pause_min"), T("col_time_seg")]

    sheet_name = T("subheader_summary")[:31]  # Excel-Limit: max. 31 Zeichen

    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)

        workbook = w.book
        worksheet = w.sheets[sheet_name]
        time_format = workbook.add_format({"num_format": "hh:mm"})
        duration_format = workbook.add_format({"num_format": "[hh]:mm"})

        columns = list(df.columns)
        col_formats = [(c, time_format) for c in time_cols] + \
                      [(c, duration_format) for c in duration_cols]

        for col_name, fmt in col_formats:
            if col_name not in columns:
                continue
            col_idx = columns.index(col_name)
            for row_idx, value in enumerate(df[col_name]):
                try:
                    seconds = parse_hhmm_to_seconds(str(value))
                    day_fraction = seconds / 86400.0
                except (ValueError, AttributeError):
                    continue  # Wert nicht parsbar -> von pandas geschriebenen Text belassen
                worksheet.write_number(row_idx + 1, col_idx, day_fraction, fmt)

    return buf.getvalue()

# -----------------------------------------------------
# PDF EXPORT
# -----------------------------------------------------
def export_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=9)

    pdf.cell(0, 10, T("pdf_title"), ln=True)

    for _, r in df.iterrows():
        line = (
            f"{r[T('col_typ')]} – {r[T('col_name')]} – "
            f"KM {r[T('col_km')]} ({r[T('col_km_seg')]}) – "
            f"{r[T('col_hm')]} ({r[T('col_hm_seg')]}) – "
            f"{T('col_arrival')} {r[T('col_arrival_day')]} {r[T('col_arrival_time')]} – "
            f"{T('col_departure')} {r[T('col_departure_day')]} {r[T('col_departure_time')]} – "
            f"{T('col_time_seg')} {r[T('col_time_seg')]} – "
            f"Ø {r[T('col_avg_kmh')]} km/h – Ø {r[T('col_avg_kmh_seg')]} km/h – "
            f"{T('col_pause_min')} {r[T('col_pause_min')]}"
        )
        pdf.multi_cell(0, 6, line)

    output = pdf.output(dest="S")
    # fpdf2 (aktuelle Bibliotheksversion) liefert bereits bytes/bytearray
    # zurück; das alte PyFPDF lieferte einen str. Beide Fälle abfangen,
    # statt blind .encode("utf-8") auf ein evtl. schon binäres Objekt
    # aufzurufen (führte vorher zu AttributeError).
    if isinstance(output, (bytes, bytearray)):
        return bytes(output)
    return output.encode("latin-1")


# -----------------------------------------------------
# FOLIUM MAP (stabil, B.7.20)
# -----------------------------------------------------
def build_map(df, control_points, pause_points, segment_winds=None, highlight_km=None):
    # Falls Gradient überall gleich ist → Colormap‑Fix
    vmin = float(df["gradient"].min())
    vmax = float(df["gradient"].max())
    if vmin == vmax:
        vmax = vmin + 0.01

    m = folium.Map(
        location=[df["lat"].iloc[0], df["lon"].iloc[0]]
    )

    # Karte automatisch so zoomen/zentrieren, dass die GESAMTE Strecke
    # sichtbar ist, statt eines festen zoom_start um den Startpunkt.
    # fit_bounds erwartet [[lat_min, lon_min], [lat_max, lon_max]].
    lat_min = float(df["lat"].min())
    lat_max = float(df["lat"].max())
    lon_min = float(df["lon"].min())
    lon_max = float(df["lon"].max())
    m.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]])

    colormap = cm.LinearColormap(
        colors=["green", "yellow", "orange", "red"],
        vmin=vmin,
        vmax=vmax
    )

    # Route
    folium.PolyLine(
        df[["lat", "lon"]].values,
        color="blue",
        weight=4,
        opacity=0.8
    ).add_to(m)

    colormap.add_to(m)

    # Start
    folium.Marker(
        [df["lat"].iloc[0], df["lon"].iloc[0]],
        popup=T("map_start"),
        icon=folium.Icon(color="green")
    ).add_to(m)

    # Ziel
    folium.Marker(
        [df["lat"].iloc[-1], df["lon"].iloc[-1]],
        popup=T("map_finish"),
        icon=folium.Icon(color="red")
    ).add_to(m)

    # Kontrollpunkte
    for cp in control_points:
        idx = (df["distance_m"] / 1000 - cp["km"]).abs().idxmin()
        folium.Marker(
            [df["lat"].iloc[idx], df["lon"].iloc[idx]],
            popup=f"{T('type_cp')}: {cp['name']}",
            icon=folium.Icon(color="blue")
        ).add_to(m)

    # Pausenpunkte
    for pp in pause_points:
        idx = (df["distance_m"] / 1000 - pp["km"]).abs().idxmin()
        folium.Marker(
            [df["lat"].iloc[idx], df["lon"].iloc[idx]],
            popup=f"{T('map_pause_prefix')}: {pp['name']}",
            icon=folium.Icon(color="orange")
        ).add_to(m)

    # Windrichtung je Abschnitt: ein gedrehter Pfeil an der Streckenmitte
    # jedes Abschnitts, zeigt die Richtung, AUS der der Wind weht (analog zur
    # Meteorologie-Konvention). "wind_ang" ist ein absoluter Kompasskurs
    # (0°=Nord) -- keine Umrechnung über die Fahrtrichtung mehr nötig.
    for seg in (segment_winds or []):
        wind_speed = seg.get("wind", 0.0)
        if not wind_speed:
            continue  # kein Wind eingetragen -> kein Pfeil, vermeidet Kartenchaos

        seg_start = seg["km_start"]
        seg_end = seg["km_end"]
        idx_mid = (df["km"] - (seg_start + seg_end) / 2).abs().idxmin()

        wind_from_deg = seg.get("wind_ang", 0.0) % 360
        # Pfeil soll in die Richtung zeigen, in die der Wind WEHT (also
        # entgegengesetzt zur "kommt aus"-Richtung) -- Pfeilsymbol ➤ zeigt
        # per Default nach rechts (Osten, 90°), daher -90° Korrektur
        arrow_rotation = (wind_from_deg + 180 - 90) % 360

        tooltip_text = f"{T('wind_label')}: {wind_speed:g} km/h"

        folium.Marker(
            [df["lat"].iloc[idx_mid], df["lon"].iloc[idx_mid]],
            icon=folium.DivIcon(
                html=(
                    f'<div style="font-size:26px; color:#1565c0; '
                    f'width:32px; height:32px; text-align:center; line-height:32px; '
                    f'transform: rotate({arrow_rotation:.0f}deg); '
                    f'text-shadow: 1px 1px 2px white, -1px -1px 2px white, '
                    f'1px -1px 2px white, -1px 1px 2px white;">➤</div>'
                ),
                icon_size=(32, 32),
                icon_anchor=(16, 16),
            ),
            tooltip=tooltip_text,
        ).add_to(m)

    # Angeklickte Position aus dem Höhenprofil hervorheben (falls vorhanden)
    if highlight_km is not None:
        idx_h = (df["km"] - highlight_km).abs().idxmin()
        folium.CircleMarker(
            [df["lat"].iloc[idx_h], df["lon"].iloc[idx_h]],
            radius=10,
            color="#d81b60",
            weight=3,
            fill=True,
            fill_color="#ffeb3b",
            fill_opacity=0.9,
            tooltip=f"{T('elevation_xaxis')}: {df['km'].iloc[idx_h]:.1f} km",
        ).add_to(m)

    return m

# -----------------------------------------------------
# HÖHENPROFIL (Plotly)
# -----------------------------------------------------
def plot_elevation(df):
    fig = go.Figure()

    # Farbskala nach Steigung
    colors = np.where(df["gradient"] > 6, "red",
             np.where(df["gradient"] > 3, "orange",
             np.where(df["gradient"] > 1, "yellow", "green")))

    fig.add_trace(go.Scatter(
        x=df["distance_m"] / 1000,
        y=df["elev_smooth"],
        mode="lines+markers",
        line=dict(width=3),
        marker=dict(color=colors, size=5),
    ))

    fig.update_layout(
        title=T("elevation_title"),
        xaxis_title=T("elevation_xaxis"),
        yaxis_title=T("elevation_yaxis"),
        height=300,
        margin=dict(l=40, r=20, t=40, b=40),
        # Nötig, damit Plotly Klicks auf einzelne Punkte als "Punkt-
        # Auswahl"-Event feuert, das Streamlits on_select="rerun" abfangen
        # kann. Ohne Marker (nur "lines") gibt es sonst oft keinen exakt
        # anklickbaren Trefferpunkt.
        clickmode="event+select",
    )
    return fig


# -----------------------------------------------------
# STEIGUNGS-KATEGORIEN (Farbe je nach Steigung, für Höhenprofile)
# -----------------------------------------------------
# (obere Grenze in %, Farbe, Übersetzungsschlüssel) -- der Reihe nach
# geprüft, lückenlos aneinander anschließend:
#   bergab            < -6 %
#   leicht bergab     -6 % .. 0 %
#   flach              0 % .. 2 %
#   leicht bergauf      2 % .. 4 %
#   mittel bergauf       4 % .. 8 %
#   steil bergauf         8 % .. 10 %
#   sehr steil bergauf   >= 10 %
GRADIENT_CATEGORIES = [
    (-6.0, "#1565c0", "grad_downhill"),
    (0.0, "#64b5f6", "grad_light_downhill"),
    (2.0, "#4caf50", "grad_flat"),
    (4.0, "#cddc39", "grad_light_up"),
    (8.0, "#ff9800", "grad_moderate_up"),
    (10.0, "#e53935", "grad_steep_up"),
    (float("inf"), "#8e0000", "grad_very_steep_up"),
]


def gradient_color_and_key(grad):
    """Ordnet einen Steigungswert (%) einer Farbe + Übersetzungsschlüssel zu."""
    for upper, color, key in GRADIENT_CATEGORIES:
        if grad < upper:
            return color, key
    return GRADIENT_CATEGORIES[-1][1], GRADIENT_CATEGORIES[-1][2]


# -----------------------------------------------------
# GEMEINSAME LEGENDE FÜR DIE STEIGUNGS-FARBCODIERUNG
# -----------------------------------------------------
def plot_gradient_legend():
    """
    Erzeugt eine einzelne, kompakte Legende für die Steigungs-Farbcodierung
    (bergab/flach/leicht/mittel/steil bergauf), inkl. der jeweiligen
    Prozentbereiche. Wird einmal VOR dem ersten Höhenprofil angezeigt,
    statt in jedem einzelnen Abschnitts-Diagramm erneut zu erscheinen.
    """
    lower = float("-inf")
    handles = []
    labels = []
    for upper, color, key in GRADIENT_CATEGORIES:
        if lower == float("-inf"):
            range_str = f"< {upper:g}%"
        elif upper == float("inf"):
            range_str = f"≥ {lower:g}%"
        else:
            range_str = f"{lower:g}–{upper:g}%"

        handles.append(plt.Rectangle((0, 0), 1, 1, facecolor=color, alpha=0.9))
        labels.append(f"{T(key)} ({range_str})")
        lower = upper

    fig, ax = plt.subplots(figsize=(10, 1.1))
    ax.axis("off")
    ax.legend(
        handles, labels, loc="center", ncol=4,
        fontsize=8, frameon=False,
    )
    fig.tight_layout()
    return fig


# -----------------------------------------------------
# HÖHENPROFIL JE EINZELNEM ABSCHNITT (Matplotlib, JPEG-exportierbar)
# -----------------------------------------------------
def plot_segment_profile(df, seg_start_km, seg_end_km, row):
    """
    Erzeugt EIN Höhenprofil-Diagramm für genau einen Abschnitt zwischen zwei
    aufeinanderfolgenden Kontroll-/Pausenpunkten, inklusive einer kleinen
    Tabelle mit den zugehörigen Werten aus der Zusammenfassung (row = die
    entsprechende Zeile aus df_sum). Die Fläche wird punktgenau nach der
    lokalen Steigung eingefärbt (bergab/flach/leicht/mittel/steil bergauf).
    Gibt die Matplotlib-Figure zurück (Anzeige in der App UND JPEG-Export).
    """
    km_arr = df["km"].values
    elev_arr = df["elev_smooth"].values
    grad_arr = df["gradient"].values
    mask = (km_arr >= seg_start_km) & (km_arr <= seg_end_km)

    if not np.any(mask):
        return None

    seg_km = km_arr[mask]
    seg_elev = elev_arr[mask]
    seg_grad = grad_arr[mask]

    if len(seg_km) < 2:
        return None

    y_min = float(np.nanmin(seg_elev))
    y_max = float(np.nanmax(seg_elev))
    y_pad = max((y_max - y_min) * 0.12, 5.0)

    fig, (ax_elev, ax_table) = plt.subplots(
        2, 1,
        figsize=(8, 3.2),
        gridspec_kw={"height_ratios": [3, 1.7]},
    )

    # Höhenprofil: jedes kleine Teilstück in der Farbe seiner lokalen Steigung
    for j in range(1, len(seg_km)):
        g = (seg_grad[j - 1] + seg_grad[j]) / 2.0
        color, _ = gradient_color_and_key(g)
        ax_elev.fill_between(
            seg_km[j - 1:j + 1], seg_elev[j - 1:j + 1], y_min - y_pad,
            color=color, linewidth=0,
        )
    ax_elev.plot(seg_km, seg_elev, color="#333333", linewidth=1.0)

    ax_elev.set_xlim(seg_start_km, seg_end_km)
    ax_elev.set_ylim(y_min - y_pad, y_max + y_pad)
    ax_elev.set_ylabel(T("elevation_yaxis"))
    ax_elev.set_xlabel(T("elevation_xaxis"))
    ax_elev.grid(True, alpha=0.2)

    name = str(row[T("col_name")]).strip() or "-"
    ax_elev.set_title(name, fontsize=12, fontweight="bold")

    # Werte für GENAU diesen Abschnitt -- als Label/Wert-Paare, dann auf
    # 2 Spalten aufgeteilt (Distanz/Höhe/Tempo links, Zeiten/Pause rechts),
    # damit die Tabelle kompakter (breiter statt hoch) wird
    pairs = [
        (T("col_km_seg"), f"{row[T('col_km_seg')]} km"),
        (T("col_hm_seg"), f"{row[T('col_hm_seg')]} m"),
        (T("col_avg_kmh_seg"), f"{row[T('col_avg_kmh_seg')]} km/h"),
        (T("col_arrival"), str(row[T("col_arrival")])),
        (T("col_departure"), str(row[T("col_departure")])),
        (T("col_pause_min"), f"{row[T('col_pause_min')]} min"),
    ]
    half = math.ceil(len(pairs) / 2)
    table_rows = []
    for i in range(half):
        left_label, left_val = pairs[i]
        if i + half < len(pairs):
            right_label, right_val = pairs[i + half]
        else:
            right_label, right_val = "", ""
        table_rows.append([left_label, left_val, right_label, right_val])

    ax_table.axis("off")
    tbl = ax_table.table(
        cellText=table_rows,
        cellLoc="left",
        loc="center",
        colWidths=[0.22, 0.22, 0.22, 0.22],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.6)

    # Label-Spalten (1. und 3.) in der Farbe der durchschnittlichen Steigung
    # dieses Abschnitts hervorheben (zeigt den "Gesamtcharakter" des Abschnitts)
    avg_grad = float(np.nanmean(seg_grad))
    accent_color, _ = gradient_color_and_key(avg_grad)
    for r in range(len(table_rows)):
        tbl[r, 0].set_facecolor(accent_color)
        tbl[r, 0].set_alpha(0.3)
        tbl[r, 2].set_facecolor(accent_color)
        tbl[r, 2].set_alpha(0.3)

    fig.tight_layout()
    return fig



_lang_options = {"Deutsch": "de", "English": "en"}
_lang_labels = list(_lang_options.keys())
_current_lang_label = "Deutsch" if st.session_state.get("lang", "de") == "de" else "English"
_selected_lang_label = st.sidebar.selectbox(
    T("lang_select_label"),
    _lang_labels,
    index=_lang_labels.index(_current_lang_label),
)
st.session_state["lang"] = _lang_options[_selected_lang_label]

# -----------------------------------------------------
# SIDEBAR – Einstellungen laden
# -----------------------------------------------------
st.sidebar.header(T("settings_load_header"))

uploaded_settings = st.sidebar.file_uploader(T("settings_load_uploader"), type="json")

if uploaded_settings is not None:
    data = json.load(uploaded_settings)

    loaded_params = data.get("params", {})
    control_points = data.get("control_points", [])
    pause_points = data.get("pause_points", [])

    # Startdatum laden
    if "start_dt" in loaded_params:
        start_dt_loaded = datetime.datetime.strptime(loaded_params["start_dt"], "%Y-%m-%d %H:%M")
    else:
        start_dt_loaded = datetime.datetime.combine(datetime.date.today(), datetime.time(6, 0))

    # In Session State schreiben, DAMIT die Widgets weiter unten ihre
    # Default-Werte daraus lesen können (vorher wurden diese ignoriert!)
    # Wind hängt jetzt direkt an den einzelnen Kontroll-/Pausenpunkten
    # (cp["wind"]/cp["wind_ang"]) und wird dadurch automatisch mit
    # control_points/pause_points geladen -- keine separate Behandlung mehr
    # nötig.
    st.session_state["control_points"] = control_points
    st.session_state["pause_points"] = pause_points
    st.session_state["params"] = loaded_params
    st.session_state["start_dt"] = start_dt_loaded

    st.sidebar.success(T("settings_load_success"))

# Zuvor gespeicherte Werte (leeres Dict, falls noch nichts geladen wurde) –
# alle Widgets unten verwenden dies als Default statt fester Werte.
saved = st.session_state.get("params", {}) or {}

# -----------------------------------------------------
# SIDEBAR – Brevet-Länge & Maximalzeit (ACP-Regeln)
# -----------------------------------------------------
st.sidebar.header(T("brevet_length_header"))

# Offizielle ACP-Regelzeiten (HH:MM). Für 1200 km gilt laut LRM ebenfalls
# 90:00. Für "1200+" gibt es KEINE feste ACP/LRM-Zeit -- sie hängt von der
# tatsächlichen Distanz und den Organizer-Regeln ab (LRM: ca. 13,33 km/h
# Mindesttempo bis 1299 km, danach abnehmend). 90:00 dient hier nur als
# Startwert, der manuell angepasst werden muss.
ACP_MAX_TIME_STR = {
    "200": "13:30",
    "300": "20:00",
    "400": "27:00",
    "600": "40:00",
    "1000": "75:00",
    "1200": "90:00",
    "1200+": "90:00",
}

brevet_length_options = ["200", "300", "400", "600", "1000", "1200", "1200+"]


def _brevet_length_display(value):
    return T("brevet_1200plus_label") if value == "1200+" else f"{value} km"


_saved_brevet_length = saved.get("brevet_length", st.session_state.get("brevet_length", "200"))
if _saved_brevet_length not in brevet_length_options:
    _saved_brevet_length = "200"

brevet_length = st.sidebar.selectbox(
    T("brevet_length_label"),
    brevet_length_options,
    index=brevet_length_options.index(_saved_brevet_length),
    format_func=_brevet_length_display,
)

# Wenn sich die gewählte Länge geändert hat, Maximalzeit auf den ACP-Wert
# zurücksetzen. Ansonsten den zuletzt (ggf. manuell angepassten) Wert
# behalten -- so bleibt eine eigene Eingabe erhalten, solange die Länge
# nicht erneut gewechselt wird.
if st.session_state.get("brevet_length") != brevet_length:
    st.session_state["brevet_length"] = brevet_length
    st.session_state["max_time_str"] = ACP_MAX_TIME_STR[brevet_length]

_default_max_time_str = st.session_state.get(
    "max_time_str", saved.get("max_time_str", ACP_MAX_TIME_STR[brevet_length])
)

max_time_str_input = st.sidebar.text_input(
    T("max_time_label"),
    value=_default_max_time_str,
    help=T("max_time_help"),
)

try:
    max_time_seconds = parse_hhmm_to_seconds(max_time_str_input)
    st.session_state["max_time_str"] = max_time_str_input
except ValueError:
    st.sidebar.error(T("max_time_invalid"))
    max_time_seconds = parse_hhmm_to_seconds(st.session_state.get("max_time_str", "13:30"))

if brevet_length == "1200+":
    st.sidebar.caption(T("max_time_1200plus_note"))

# -----------------------------------------------------
# SIDEBAR – Startzeit
# -----------------------------------------------------
st.sidebar.header(T("start_header"))

_default_start_dt = st.session_state.get("start_dt") or dt.datetime.combine(dt.date.today(), dt.time(6, 0))
start_date = st.sidebar.date_input(T("start_date_label"), _default_start_dt.date())
start_time = st.sidebar.time_input(T("start_time_label"), _default_start_dt.time())
start_dt = dt.datetime.combine(start_date, start_time)

# -----------------------------------------------------
# SIDEBAR – Fahrer & Rad
# -----------------------------------------------------
st.sidebar.header(T("rider_header"))
weight = st.sidebar.number_input(T("weight_label"), 50.0, 150.0, float(saved.get("weight", 85.0)))

# -----------------------------------------------------
# SIDEBAR – Leistung / FTP
# -----------------------------------------------------
st.sidebar.header(T("power_header"))

ftp = st.sidebar.number_input(T("ftp_label"), 100, 450, int(saved.get("ftp", 250)))

# Auto-Leistung aus FTP
st.sidebar.caption(T("power_caption"))

w_flat = int(ftp * 0.75)
w_up   = int(ftp * 0.90)
w_down = int(ftp * 0.50)

st.sidebar.write(T("power_flat", w=w_flat))
st.sidebar.write(T("power_up", w=w_up))
st.sidebar.write(T("power_down", w=w_down))

# -----------------------------------------------------
# SIDEBAR – Zielgeschwindigkeiten
# -----------------------------------------------------
st.sidebar.header(T("speeds_header"))

# Auto-Vorschläge aus FTP (werden nur als Default genutzt, falls nichts
# gespeichert wurde – gespeicherte/manuell überschriebene Werte haben Vorrang)
auto_flat  = round(ftp * 0.11)   # ~ FTP * 0.11 → 28 km/h bei FTP=250
auto_lup   = round(ftp * 0.09)
auto_mup   = round(ftp * 0.075)
auto_sup   = round(ftp * 0.055)
auto_vs_up = round(ftp * 0.04)
auto_ldown = round(ftp * 0.13)
auto_down  = round(ftp * 0.15)

spd_down  = st.sidebar.number_input(T("spd_down_label"), 10.0, 90.0, float(saved.get("spd_down", auto_down)))
spd_ldown = st.sidebar.number_input(T("spd_ldown_label"), 10.0, 70.0, float(saved.get("spd_ldown", auto_ldown)))
spd_flat  = st.sidebar.number_input(T("spd_flat_label"), 10.0, 50.0, float(saved.get("spd_flat", auto_flat)))
spd_lup   = st.sidebar.number_input(T("spd_lup_label"), 5.0, 40.0, float(saved.get("spd_lup", auto_lup)))
spd_mup   = st.sidebar.number_input(T("spd_mup_label"), 5.0, 35.0, float(saved.get("spd_mup", auto_mup)))
spd_sup   = st.sidebar.number_input(T("spd_sup_label"), 3.0, 30.0, float(saved.get("spd_sup", auto_sup)))
spd_vs_up = st.sidebar.number_input(T("spd_vsup_label"), 2.0, 25.0, float(saved.get("spd_vs_up", auto_vs_up)))

# -----------------------------------------------------
# SIDEBAR – Physik
# -----------------------------------------------------
st.sidebar.header(T("physics_header"))
cda = st.sidebar.number_input(T("cda_label"), 0.15, 0.5, float(saved.get("cda", 0.28)))
crr = st.sidebar.number_input(T("crr_label"), 0.002, 0.01, float(saved.get("crr", 0.004)))
max_down = st.sidebar.number_input(T("max_down_label"), 20.0, 100.0, float(saved.get("max_down", 70.0)))
min_spd = st.sidebar.number_input(T("min_spd_label"), 3.0, 15.0, float(saved.get("min_spd", 6.0)))

# Hybrid-Faktor: Anteil des Zieltempo-Modells an der finalen Geschwindigkeit.
# 0.0 = Geschwindigkeit ausschließlich aus Physik (FTP/CdA/Crr/Wind) berechnet,
# 1.0 = Geschwindigkeit ausschließlich aus den oben eingetragenen Zielwerten.
hybrid_factor = st.sidebar.slider(
    T("hybrid_label"),
    0.0, 1.0, float(saved.get("hybrid_factor", 0.7)), 0.01,
    help=T("hybrid_help")
)

# -----------------------------------------------------
# SIDEBAR – Ermüdung
# -----------------------------------------------------
st.sidebar.header(T("fatigue_header"))

fatigue_k_pct = st.sidebar.slider(
    T("fatigue_k_label"),
    0, 50, int(round(float(saved.get("fatigue_k", 0.25)) * 100)),
    help=T("fatigue_k_help")
)
fatigue_k = fatigue_k_pct / 100.0

fatigue_hours = st.sidebar.number_input(
    T("fatigue_hours_label"),
    2.0, 80.0, float(saved.get("fatigue_hours", 20.0)),
    help=T("fatigue_hours_help")
)

pause_recovery = st.sidebar.slider(
    T("pause_recovery_label"),
    0.0, 10.0, float(saved.get("pause_recovery", 3.0)), 0.5,
    help=T("pause_recovery_help")
)

# -----------------------------------------------------
# PARAMETER-BUNDLE (für compute_speed & Zeitmodell)
# -----------------------------------------------------
params = {
    "ftp": ftp,
    "weight": weight,
    "cda": cda,
    "crr": crr,
    # Nur für Rückwärtskompatibilität sehr alter Einstellungsdateien ganz
    # ohne Kontroll-/Pausenpunkte -- Wind wird jetzt direkt an den
    # jeweiligen Kontroll-/Pausenpunkten eingestellt (siehe cp["wind"]/
    # cp["wind_ang"] weiter unten, daraus wird "segment_winds" abgeleitet)
    "wind": saved.get("wind", 0.0),
    "wind_ang": saved.get("wind_ang", 0.0),
    "max_down": max_down,
    "min_spd": min_spd,

    "spd_down": spd_down,
    "spd_ldown": spd_ldown,
    "spd_flat": spd_flat,
    "spd_lup": spd_lup,
    "spd_mup": spd_mup,
    "spd_sup": spd_sup,
    "spd_vs_up": spd_vs_up,

    "w_flat": w_flat,
    "w_up": w_up,
    "w_down": w_down,

    "hybrid_factor": hybrid_factor,

    "fatigue_k": fatigue_k,
    "fatigue_hours": fatigue_hours,
    "pause_recovery": pause_recovery,

    "brevet_length": brevet_length,
    "max_time_str": st.session_state.get("max_time_str", max_time_str_input),
    "max_time_seconds": max_time_seconds,
}

params["start_dt"] = start_dt.strftime("%Y-%m-%d %H:%M")

# Aktuellen Stand sofort spiegeln, damit der "Einstellungen speichern"-Button
# weiter unten immer den echten aktuellen Stand exportiert (nicht nur den
# zuletzt hochgeladenen).
st.session_state["params"] = params

# -----------------------------------------------------
# SIDEBAR – Kontrollpunkte
# -----------------------------------------------------
st.sidebar.header(T("cp_header"))
st.sidebar.caption(T("point_wind_caption"))

n_cp = st.sidebar.number_input(T("cp_count_label"), 0, 20, len(st.session_state["control_points"]))

# Wenn Anzahl geändert wurde → Liste anpassen
if n_cp != len(st.session_state["control_points"]):
    st.session_state["control_points"] = st.session_state["control_points"][:n_cp]
    while len(st.session_state["control_points"]) < n_cp:
        st.session_state["control_points"].append({"name": "", "km": 0.0, "pause": 0, "wind": 0.0, "wind_ang": 0.0})

# Eingabefelder
for i in range(n_cp):
    cp = st.session_state["control_points"][i]

    cp["name"] = st.sidebar.text_input(T("cp_name_label", i=i+1), value=cp["name"], key=f"cpn{i}")
    cp["km"] = st.sidebar.number_input(T("cp_km_label", i=i+1), 0.0, 2000.0, cp["km"], key=f"cpk{i}")
    cp["pause"] = st.sidebar.number_input(T("cp_pause_label", i=i+1), 0, 900, cp["pause"], key=f"cpp{i}")
    wind_col1, wind_col2 = st.sidebar.columns(2)
    with wind_col1:
        cp["wind"] = st.number_input(
            T("wind_label"), 0.0, 60.0, float(cp.get("wind", 0.0)), key=f"cpw{i}"
        )
    with wind_col2:
        cp["wind_ang"] = st.number_input(
            T("wind_ang_short_label"), 0.0, 360.0, float(cp.get("wind_ang", 0.0)) % 360, key=f"cpwa{i}"
        )

# -----------------------------------------------------
# SIDEBAR – Pausenpunkte
# -----------------------------------------------------
st.sidebar.header(T("pp_header"))
st.sidebar.caption(T("point_wind_caption"))

n_pp = st.sidebar.number_input(T("pp_count_label"), 0, 20, len(st.session_state["pause_points"]))

# Liste anpassen
if n_pp != len(st.session_state["pause_points"]):
    st.session_state["pause_points"] = st.session_state["pause_points"][:n_pp]
    while len(st.session_state["pause_points"]) < n_pp:
        st.session_state["pause_points"].append({"name": "", "km": 0.0, "pause": 0, "wind": 0.0, "wind_ang": 0.0})

# Eingabefelder
for i in range(n_pp):
    pp = st.session_state["pause_points"][i]

    pp["name"] = st.sidebar.text_input(T("pp_name_label", i=i+1), value=pp["name"], key=f"ppn{i}")
    pp["km"] = st.sidebar.number_input(T("pp_km_label", i=i+1), 0.0, 2000.0, pp["km"], key=f"ppk{i}")
    pp["pause"] = st.sidebar.number_input(T("pp_pause_label", i=i+1), 0, 900, pp["pause"], key=f"ppp{i}")
    wind_col1, wind_col2 = st.sidebar.columns(2)
    with wind_col1:
        pp["wind"] = st.number_input(
            T("wind_label"), 0.0, 60.0, float(pp.get("wind", 0.0)), key=f"ppw{i}"
        )
    with wind_col2:
        pp["wind_ang"] = st.number_input(
            T("wind_ang_short_label"), 0.0, 360.0, float(pp.get("wind_ang", 0.0)) % 360, key=f"ppwa{i}"
        )

# -----------------------------------------------------
# Wind je Abschnitt aus den Kontroll-/Pausenpunkten ableiten
# -----------------------------------------------------
# Jeder Punkt trägt seinen eigenen Wind für "den Abschnitt, der an diesem
# Punkt endet". Nach km sortiert ergibt das lückenlose Abschnittsgrenzen
# von 0 bis zum letzten Punkt (i.d.R. das Ziel). Da Wind jetzt direkt am
# jeweiligen Punkt hängt, wird er automatisch mit control_points/
# pause_points gespeichert und geladen -- keine separate Synchronisierung
# mehr nötig.
_wind_events = sorted(
    (
        [{"km": float(cp["km"]), "wind": float(cp.get("wind", 0.0)), "wind_ang": float(cp.get("wind_ang", 0.0))}
         for cp in st.session_state["control_points"]] +
        [{"km": float(pp["km"]), "wind": float(pp.get("wind", 0.0)), "wind_ang": float(pp.get("wind_ang", 0.0))}
         for pp in st.session_state["pause_points"]]
    ),
    key=lambda e: e["km"],
)

segment_winds = []
_prev_km = 0.0
for ev in _wind_events:
    segment_winds.append({
        "km_start": _prev_km, "km_end": ev["km"],
        "wind": ev["wind"], "wind_ang": ev["wind_ang"],
    })
    _prev_km = ev["km"]

# In params spiegeln, damit compute_speed() (weiter unten aufgerufen) und
# das Speichern/Laden der Einstellungen darauf zugreifen können
params["segment_winds"] = segment_winds
st.session_state["params"]["segment_winds"] = segment_winds

# -----------------------------------------------------
# RDP-DOWNSAMPLING
# -----------------------------------------------------
def rdp_indices(points, epsilon):
    """
    Iteratives Ramer-Douglas-Peucker. points: Liste von (lat, lon)-Tupeln.
    Gibt die sortierten Indizes der zu behaltenden Punkte zurück (Start und
    Ende immer enthalten). Iterativ mit explizitem Stack statt Rekursion,
    damit auch sehr lange Tracks (>>1000 km, zehntausende GPX-Punkte) nicht
    an Pythons Rekursionslimit scheitern können.
    """
    n = len(points)
    if n < 3:
        return list(range(n))

    def perpendicular_distance(pt, start, end):
        if start == end:
            return gpxpy.geo.haversine_distance(pt[0], pt[1], start[0], start[1])
        x0, y0 = pt
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj = (x1 + t * dx, y1 + t * dy)
        return gpxpy.geo.haversine_distance(pt[0], pt[1], proj[0], proj[1])

    keep = {0, n - 1}
    stack = [(0, n - 1)]

    while stack:
        start_i, end_i = stack.pop()
        if end_i - start_i < 2:
            continue

        start_pt = points[start_i]
        end_pt = points[end_i]

        max_dist = 0.0
        max_idx = start_i

        for i in range(start_i + 1, end_i):
            dist = perpendicular_distance(points[i], start_pt, end_pt)
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > epsilon:
            keep.add(max_idx)
            stack.append((start_i, max_idx))
            stack.append((max_idx, end_i))
        # sonst: Segment ist bereits nahezu eine Gerade -> keine weitere Unterteilung

    return sorted(keep)


def downsample_rdp(df, epsilon=8):
    """
    Reduziert den Track mit RDP. Arbeitet direkt mit Zeilen-Indizes statt
    die reduzierten Punkte per Koordinatenvergleich im DataFrame zu suchen –
    das ist robust auch bei doppelten Koordinaten (z.B. Kreuzungen,
    Wendepunkte, Start=Ziel), wo der alte Ansatz den falschen Index treffen
    oder Punkte verlieren konnte.
    """
    points = list(zip(df["lat"].values, df["lon"].values))
    idx = rdp_indices(points, epsilon)
    return df.iloc[idx].reset_index(drop=True)

# -----------------------------------------------------
# GPX UPLOAD + ZEITPROFIL + SUMMARY
# -----------------------------------------------------
gpx_file = st.file_uploader(T("gpx_uploader_label"), type=["gpx"])

if gpx_file is not None:
    
        # 1. GPX einlesen
    df_raw = parse_gpx(gpx_file)
    
    # 2. Downsampling
    df = downsample_rdp(df_raw, epsilon=8)

    # Höhen glätten ohne SciPy
    df["elev_med"] = df["elev"].rolling(window=5, center=True, min_periods=1).median()
    df["elev_smooth"] = df["elev_med"].rolling(window=7, center=True, min_periods=1).mean()

        
    # 3. Höhen glätten
    #df["elev"] = df["elev"].rolling(window=5, center=True, min_periods=1).mean()
    
    # 4. Höhenmeter berechnen
    df["elev_diff"] = df["elev_smooth"].diff().fillna(0)
    df["hm_pos"] = df["elev_diff"].apply(lambda x: x if x > 0 else 0)
    df["hm_cum"] = df["hm_pos"].cumsum()

    # 5. Steigung berechnen
    df["gradient"] = df["elev_smooth"].diff().fillna(0) / df["distance_m"].diff().fillna(1)
    df["gradient"] = df["gradient"] * 100


    # 5. km berechnen
    df["km"] = df["distance_m"] / 1000

    # Aktueller Stand der Kontroll-/Pausenpunkte (nach allen Sidebar-Edits
    # und einem eventuellen Settings-Upload) — direkt aus dem Session State.
    # Wird VOR compute_speed() benötigt, da die zeitbasierte Ermüdung durch
    # Pausen an genau diesen Punkten abgebaut wird.
    control_points = st.session_state["control_points"]
    pause_points = st.session_state["pause_points"]

    pause_events = (
        [{"km": float(cp["km"]), "pause_min": int(cp["pause"])} for cp in control_points] +
        [{"km": float(pp["km"]), "pause_min": int(pp["pause"])} for pp in pause_points]
    )

    # 6. Geschwindigkeit berechnen (inkl. zeitbasierter Ermüdung + Pausen-Erholung)
    df["speed_kmh"] = compute_speed(df, params, pause_events)

    # 7. Zeitprofil berechnen (Segment- und kumulierte Zeiten aus Segmentlängen,
    #    NICHT aus der kumulierten distance_m — siehe add_time_profile())
    df = add_time_profile(df, params)

    # 5. Summary berechnen
    df_sum, raw_times = build_summary(df, control_points, pause_points, start_dt, df_acp)

    # Speichern Parameter und Punkte
    def save_settings(params, control_points, pause_points, filename="settings.json"):
        data = {
            "params": params,
            "control_points": control_points,
            "pause_points": pause_points
        }
    
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    
    # 6. Tracklänge
    track_length_km = round(df["km"].iloc[-1], 1)


    # 7. Save-Button
    state = {
        "params": st.session_state["params"],
        "control_points": st.session_state["control_points"],
        "pause_points": st.session_state["pause_points"]
    }

    # Zweistufig, damit der Dateiname garantiert übernommen ist, BEVOR der
    # Download-Button ihn verwendet: st.download_button liest den Dateinamen
    # aus dem Skriptlauf zum Zeitpunkt des Klicks. Wird der Name nur in
    # st.text_input eingetragen, kann es passieren, dass ein Klick auf
    # "Speichern" knapp VOR der Übernahme des neuen Texts erfolgt und
    # dadurch noch der alte/Default-Name verwendet wird. Der explizite
    # "Namen übernehmen"-Button erzwingt einen Rerun, der den Namen sicher
    # in st.session_state["settings_filename"] ablegt.
    with st.form("settings_filename_form"):
        filename_input = st.text_input(
            T("settings_filename_label"),
            value=st.session_state.get("settings_filename", "brevet_settings"),
            help=T("settings_filename_help")
        )
        name_submitted = st.form_submit_button(T("settings_filename_submit"))
        if name_submitted:
            st.session_state["settings_filename"] = filename_input

    st.caption(T("settings_filename_caption"))

    # Bereits übernommenen Namen verwenden (Default, falls noch nie
    # bestätigt wurde)
    current_filename = st.session_state.get("settings_filename", "brevet_settings")

    # Dateinamen bereinigen: keine Pfad-/Sonderzeichen, .json sicherstellen
    safe_filename = "".join(
        c for c in current_filename.strip() if c not in '\\/:*?"<>|'
    ).strip()
    if not safe_filename:
        safe_filename = "brevet_settings"
    if not safe_filename.lower().endswith(".json"):
        safe_filename += ".json"

    st.write(T("settings_filename_current", name=safe_filename))

    st.download_button(
        T("save_settings_button"),
        data=json.dumps(state, indent=2, ensure_ascii=False),
        file_name=safe_filename,
        mime="application/json"
    )


    # Prüfen, ob df_sum leer ist
    if df_sum.empty:
        st.error(T("error_no_cp"))
        st.stop()

    last_row = df_sum.iloc[-1]

    # Sekundenwerte aus raw_times
    total_seconds = raw_times["total_seconds"]
    moving_seconds = raw_times["moving_seconds"]

    # Pausen (aus raw_times, da die Pause-Spalte jetzt als "[hh]:mm"-Text
    # formatiert ist und sich nicht mehr direkt aufsummieren lässt)
    pause_seconds = raw_times.get("total_pause_seconds", 0.0)
    total_pause_min = pause_seconds / 60

    # HH:MM Formate
    total_hhmm = format_hhmm(total_seconds)
    moving_hhmm = format_hhmm(moving_seconds)

    # Geschwindigkeiten
    km_total = last_row[T("col_km")]
    total_hours = total_seconds / 3600 if total_seconds > 0 else 0
    moving_hours = moving_seconds / 3600 if moving_seconds > 0 else 0

    avg_total = round(km_total / total_hours, 1) if total_hours > 0 else 0
    avg_moving = round(km_total / moving_hours, 1) if moving_hours > 0 else 0

    # ACP-Zeit (Schlusszeit des Brevets)
    acp_seconds = df_acp["close_seconds"].iloc[-1]
    acp_hhmm = format_hhmm(acp_seconds)

    # Anzeige KPIs
    col1, col2 = st.columns(2)

    with col1:
        st.metric(T("metric_distance"), f"{km_total:.1f} km")
        st.metric(T("metric_total_time"), total_hhmm)
        st.metric(T("metric_avg_total"), f"{avg_total:.1f} km/h")
        st.metric(T("metric_pause_total"), f"{int(total_pause_min)} min")
       
        
    with col2:
        st.metric(T("metric_arrival"), raw_times["arrival_dt"])
        st.metric(T("metric_moving_time"), moving_hhmm)
        st.metric(T("metric_avg_moving"), f"{avg_moving:.1f} km/h")
        #st.metric("ACP‑Zeit gesamt (HH:MM)", acp_hhmm)

    # -----------------------------------------------------
    # HÖHENPROFIL + KARTE
    # -----------------------------------------------------
    st.subheader(T("subheader_elevation"))
    st.caption(T("elevation_click_hint"))

    elevation_event = st.plotly_chart(
        plot_elevation(df),
        use_container_width=True,
        on_select="rerun",
        key="elevation_chart_event",
    )

    # Angeklickten Punkt auslesen (falls vorhanden) und km-Position merken --
    # bleibt über den Rerun hinweg erhalten, bis erneut geklickt wird
    try:
        _clicked_points = elevation_event["selection"]["points"]
    except Exception:
        _clicked_points = []
    if _clicked_points:
        st.session_state["selected_km"] = _clicked_points[0].get("x")

    st.subheader(T("subheader_map"))
    m = build_map(
        df, control_points, pause_points, segment_winds,
        highlight_km=st.session_state.get("selected_km"),
    )
    st_folium(m, width=900, height=600)

    # -----------------------------------------------------
    # ZUSAMMENFASSUNG
    # -----------------------------------------------------
    st.subheader(T("subheader_summary"))

    # df_sum ist bereits berechnet
    total_time_str = raw_times["arrival_dt"][-5:]
    st.metric(T("metric_total_time_short"), format_hhmm(raw_times["total_seconds"]))

    st.dataframe(
        df_sum,
        hide_index=True,
        column_config={
            T("col_name"): st.column_config.TextColumn(
                T("col_name"),
                width="medium",
                help=T("col_name_help"),
                pinned="left"
            )
        }
    )

    # -----------------------------------------------------
    # EXPORT (Excel + PDF)
    # -----------------------------------------------------
    st.subheader(T("subheader_export"))

    col1, col2 = st.columns(2)

    with col1:
        data_xlsx = export_excel(df_sum)
        st.download_button(
            T("export_excel_button"),
            data=data_xlsx,
            file_name="brevet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    #with col2:
    #    data_pdf = export_pdf(df_sum)
    #    st.download_button(
    #        "PDF exportieren",
    #       data=data_pdf,
    #       file_name="brevet.pdf",
    #        mime="application/pdf"
    #    )

    # -----------------------------------------------------
    # HÖHENPROFIL JE EINZELNEM ABSCHNITT (mit Tabelle, JPEG-exportierbar)
    # -----------------------------------------------------
    st.subheader(T("subheader_elevation_segments"))

    boundaries_km = [0.0] + df_sum[T("col_km")].astype(float).tolist()
    n_segments = len(boundaries_km) - 1

    if n_segments < 1:
        st.info(T("no_segments_info"))
    else:
        fig_legend = plot_gradient_legend()
        st.pyplot(fig_legend)
        plt.close(fig_legend)

        for i in range(n_segments):
            seg_start = boundaries_km[i]
            seg_end = boundaries_km[i + 1]
            row = df_sum.iloc[i]
            name = str(row[T("col_name")]).strip() or f"{row[T('col_typ')]} {i + 1}"

            with st.expander(f"{name}  ({seg_start:.0f}–{seg_end:.0f} km)", expanded=(i == 0)):
                fig_i = plot_segment_profile(df, seg_start, seg_end, row)

                if fig_i is not None:
                    st.pyplot(fig_i)

                    img_buf = io.BytesIO()
                    fig_i.savefig(img_buf, format="jpg", dpi=150, bbox_inches="tight")
                    img_buf.seek(0)

                    safe_name = "".join(
                        c for c in name if c.isalnum() or c in (" ", "_", "-")
                    ).strip().replace(" ", "_") or f"abschnitt_{i + 1}"

                    st.download_button(
                        T("export_elevation_jpeg_button"),
                        data=img_buf.getvalue(),
                        file_name=f"hoehenprofil_{i + 1}_{safe_name}.jpg",
                        mime="image/jpeg",
                        key=f"jpeg_export_segment_{i}",
                    )

                    plt.close(fig_i)

else:
    st.info(T("gpx_info"))

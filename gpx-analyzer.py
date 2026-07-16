import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gpxpy
import io

# ---------------------------------------------------------
# Hilfsfunktionen für GPX-Verarbeitung
# ---------------------------------------------------------

def parse_gpx(file_bytes):
    """Liest eine GPX-Datei und gibt ein DataFrame mit Zeit, Distanz, Höhe und Steigung zurück."""
    gpx = gpxpy.parse(io.StringIO(file_bytes.decode("utf-8")))
    points = []
    total_dist = 0.0

    last_point = None
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                if last_point is not None:
                    d = last_point.distance_3d(p) / 1000.0  # km
                    total_dist += d
                else:
                    d = 0.0
                points.append({
                    "time": p.time.replace(tzinfo=None),
                    "lat": p.latitude,
                    "lon": p.longitude,
                    "ele": p.elevation,
                    "dist_km": total_dist
                })
                last_point = p

    df = pd.DataFrame(points)
    if df.empty:
        return df

    # Steigung (Gradient) berechnen: Höhenänderung pro km
    df["delta_ele"] = df["ele"].diff().fillna(0.0)
    df["delta_dist"] = df["dist_km"].diff().fillna(0.0)
    df["gradient"] = np.where(df["delta_dist"] > 0,
                              df["delta_ele"] / df["delta_dist"],
                              0.0)
    return df


def interpolate_time_at_distance(df, target_km):
    """Interpoliert die Zeit an einer bestimmten Distanz (km)."""
    if target_km <= df["dist_km"].iloc[0]:
        return df["time"].iloc[0]
    if target_km >= df["dist_km"].iloc[-1]:
        return df["time"].iloc[-1]

    before = df[df["dist_km"] <= target_km].iloc[-1]
    after = df[df["dist_km"] >= target_km].iloc[0]

    if after["dist_km"] == before["dist_km"]:
        return before["time"]

    ratio = (target_km - before["dist_km"]) / (after["dist_km"] - before["dist_km"])
    delta_t = after["time"] - before["time"]
    return before["time"] + ratio * delta_t


def stand_time_between(df, km_start, km_end, speed_threshold_kmh=1.0):
    """
    Schätzt Standzeit (Pause) zwischen zwei Distanzen.
    Annahme: Geschwindigkeit < speed_threshold_kmh => Pause.
    """
    mask = (df["dist_km"] >= km_start) & (df["dist_km"] <= km_end)
    sub = df[mask].copy()
    if len(sub) < 2:
        return 0.0

    sub["dt"] = sub["time"].diff().dt.total_seconds().fillna(0.0)
    sub["ddist"] = sub["dist_km"].diff().fillna(0.0)
    sub["speed_kmh"] = np.where(sub["dt"] > 0,
                                (sub["ddist"] / (sub["dt"] / 3600.0)),
                                0.0)
    pause_seconds = sub.loc[sub["speed_kmh"] < speed_threshold_kmh, "dt"].sum()
    return float(pause_seconds)


def speed_by_gradient(df, km_start, km_end):
    """
    Durchschnittsgeschwindigkeiten nach Steigungskategorien zwischen km_start und km_end.
    Kategorien sind grob gewählt.
    """
    mask = (df["dist_km"] >= km_start) & (df["dist_km"] <= km_end)
    sub = df[mask].copy()
    if len(sub) < 2:
        return (None, None, None, None, None, None, None)

    sub["dt"] = sub["time"].diff().dt.total_seconds().fillna(0.0)
    sub["ddist"] = sub["dist_km"].diff().fillna(0.0)
    sub["speed_kmh"] = np.where(sub["dt"] > 0,
                                (sub["ddist"] / (sub["dt"] / 3600.0)),
                                0.0)

    def avg_speed(cond):
        tmp = sub[cond & (sub["dt"] > 0)]
        if tmp.empty:
            return None
        return (tmp["ddist"].sum() / (tmp["dt"].sum() / 3600.0))

    speed_down = avg_speed(sub["gradient"] < -20)              # sehr steil bergab
    speed_light_down = avg_speed((sub["gradient"] >= -20) & (sub["gradient"] < -5))
    speed_flat = avg_speed((sub["gradient"] >= -5) & (sub["gradient"] <= 5))
    speed_light_up = avg_speed((sub["gradient"] > 5) & (sub["gradient"] <= 20))
    speed_medium_up = avg_speed((sub["gradient"] > 20) & (sub["gradient"] <= 40))
    speed_steep_up = avg_speed((sub["gradient"] > 40) & (sub["gradient"] <= 60))
    speed_very_steep_up = avg_speed(sub["gradient"] > 60)

    return (speed_down, speed_light_down, speed_flat,
            speed_light_up, speed_medium_up, speed_steep_up, speed_very_steep_up)


def format_hhmm(hours):
    """Formatiert Stunden als HH:MM."""
    total_minutes = int(round(hours * 60))
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------

st.set_page_config(page_title="GPX-Analyzer", layout="wide")
st.title("GPX-Analyzer")

st.markdown("Lade eine GPX-Datei hoch und definiere Kontrollpunkte (km), "
            "um Ankunftszeiten, Pausen und Geschwindigkeiten zu berechnen.")

uploaded_file = st.file_uploader("GPX-Datei hochladen", type=["gpx"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    df = parse_gpx(file_bytes)

    if df.empty:
        st.error("Die GPX-Datei enthält keine Punkte oder konnte nicht gelesen werden.")
        st.stop()

    st.subheader("Basisdaten")
    start_datetime = df["time"].iloc[0]
    end_datetime = df["time"].iloc[-1]
    total_dist = df["dist_km"].iloc[-1]

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Startzeit", start_datetime.strftime("%Y-%m-%d %H:%M"))
    with col_b:
        st.metric("Endzeit", end_datetime.strftime("%Y-%m-%d %H:%M"))
    with col_c:
        st.metric("Gesamtdistanz (km)", f"{total_dist:.1f}".replace(".", ","))

    st.line_chart(df.set_index("time")[["dist_km"]])

    st.subheader("Kontrollpunkte definieren")
    num_points = st.number_input("Anzahl Kontrollpunkte", min_value=1, max_value=20, value=3, step=1)
    max_dist = total_dist

    controls = []
    for i in range(num_points):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.number_input(
                f"Distanz Punkt {i + 1} (km)",
                min_value=0.0,
                max_value=float(max_dist),
                value=min(float(max_dist), (i + 1) * 5.0),
                key=f"dist_{i}"
            )
        with col2:
            name = st.text_input(
                f"Name Punkt {i + 1}",
                value=f"Punkt {i + 1}",
                key=f"name_{i}"
            )
        controls.append({"km": dist, "name": name})

    if st.button("Berechnen", key="calc_button"):
        # Sortieren nach Distanz
        controls = sorted(controls, key=lambda x: x["km"])
        results = []
        last_km = 0.0
        current_start = start_datetime

        for cp in controls:
            cp_km = cp["km"]
            gps_time_at_cp = interpolate_time_at_distance(df, cp_km)
            gps_time_at_last = interpolate_time_at_distance(df, last_km)

            segment_duration = gps_time_at_cp - gps_time_at_last
            segment_hours = segment_duration.total_seconds() / 3600.0
            segment_dist = cp_km - last_km

            pause_seconds = stand_time_between(df, last_km, cp_km)
            pause_td = timedelta(seconds=pause_seconds)
            netto_hours = (segment_duration.total_seconds() - pause_seconds) / 3600.0

            speed_brutto = segment_dist / segment_hours if segment_hours > 0 else 0
            speed_netto = segment_dist / netto_hours if netto_hours > 0 else 0

            (speed_down,
             speed_light_down,
             speed_flat,
             speed_light_up,
             speed_medium_up,
             speed_steep_up,
             speed_very_steep_up) = speed_by_gradient(df, last_km, cp_km)

            base_offset = gps_time_at_cp - df["time"].iloc[0]
            arrival_time = current_start + base_offset
            departure_time = arrival_time + pause_td

            def fmt_speed(v):
                if v is None:
                    return ""
                return f"{v:.1f}".replace(".", ",")

            results.append({
                "Name": cp["name"],
                "km": cp_km,
                "Ankunft": arrival_time.strftime("%Y-%m-%d %H:%M"),
                "Pause_min": round(pause_seconds / 60.0, 1),
                "Segment_h": format_hhmm(segment_hours),
                "Netto_kmh": f"{speed_netto:.1f}".replace(".", ","),
                "Brutto_kmh": f"{speed_brutto:.1f}".replace(".", ","),
                "Speed_down": fmt_speed(speed_down),
                "Speed_light_down": fmt_speed(speed_light_down),
                "Speed_flat": fmt_speed(speed_flat),
                "Speed_light_up": fmt_speed(speed_light_up),
                "Speed_medium_up": fmt_speed(speed_medium_up),
                "Speed_steep_up": fmt_speed(speed_steep_up),
                "Speed_very_steep_up": fmt_speed(speed_very_steep_up),
                "Abfahrt": departure_time.strftime("%Y-%m-%d %H:%M"),
            })

            last_km = cp_km
            current_start = departure_time

        st.subheader("Ergebnisse")
        res_df = pd.DataFrame(results)
        st.dataframe(res_df, use_container_width=True)

        csv = res_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Ergebnisse als CSV herunterladen",
            data=csv,
            file_name="gpx_analyzer_results.csv",
            mime="text/csv"
        )
else:
    st.info("Bitte zuerst eine GPX-Datei hochladen.")







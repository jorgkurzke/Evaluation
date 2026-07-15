import streamlit as st
import gpxpy
import gpxpy.gpx
import pandas as pd
from datetime import datetime, timedelta
import math

# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def gpx_to_df(gpx_file):
    gpx = gpxpy.parse(gpx_file)
    points = []

    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                points.append({
                    "time": p.time.replace(tzinfo=None),
                    "lat": p.latitude,
                    "lon": p.longitude,
                    "ele": p.elevation
                })

    df = pd.DataFrame(points)
    df = df.sort_values("time").reset_index(drop=True)

    # Distanz berechnen
    dists = [0.0]
    for i in range(1, len(df)):
        d = haversine(df.loc[i-1, "lat"], df.loc[i-1, "lon"],
                      df.loc[i, "lat"], df.loc[i, "lon"])
        dists.append(d)

    df["dist_m"] = dists
    df["dist_km_cum"] = df["dist_m"].cumsum() / 1000.0
    return df


def interpolate_time_at_distance(df, target_km):
    if target_km <= df["dist_km_cum"].iloc[0]:
        return df["time"].iloc[0]
    if target_km >= df["dist_km_cum"].iloc[-1]:
        return df["time"].iloc[-1]

    before = df[df["dist_km_cum"] <= target_km].iloc[-1]
    after = df[df["dist_km_cum"] >= target_km].iloc[0]

    if before["dist_km_cum"] == after["dist_km_cum"]:
        return before["time"]

    ratio = ((target_km - before["dist_km_cum"]) /
             (after["dist_km_cum"] - before["dist_km_cum"]))
    dt = after["time"] - before["time"]
    return before["time"] + ratio * dt


# ------------------------------------------------------------
# Streamlit App
# ------------------------------------------------------------

st.title("GPS-Track Analyse – Kontrollpunkte & automatische Pausen")

uploaded_file = st.file_uploader("GPX-Datei hochladen", type=["gpx"])

if uploaded_file is not None:
    df = gpx_to_df(uploaded_file)
    st.success(f"Track geladen: {len(df)} Punkte, {df['dist_km_cum'].iloc[-1]:.1f} km")

#Upload Kontrollpunkt
    st.subheader("Kontrollpunkte aus CSV laden")

csv_file = st.file_uploader("CSV-Datei mit Kontrollpunkten (km,name)", type=["csv"], key="csv_controls")

controls = []

# ------------------------------------------------------------
# CSV IMPORT
# ------------------------------------------------------------
if csv_file is not None:
    try:
        df_controls = pd.read_csv(csv_file)

        # Pflichtspalten prüfen
        if "km" not in df_controls.columns or "name" not in df_controls.columns:
            st.error("CSV muss die Spalten 'km' und 'name' enthalten.")
        else:
            for _, row in df_controls.iterrows():
                controls.append({
                    "km": float(row["km"]),
                    "name": str(row["name"])
                })
            st.success(f"{len(controls)} Kontrollpunkte erfolgreich geladen.")
    except Exception as e:
        st.error(f"Fehler beim Lesen der CSV: {e}")

# ------------------------------------------------------------
# MANUELLE EINGABE NUR WENN KEINE CSV GELADEN WURDE
# ------------------------------------------------------------
if len(controls) == 0:
    st.info("Keine CSV geladen – Kontrollpunkte manuell eingeben.")

    num_points = st.number_input("Anzahl Kontrollpunkte", min_value=1, max_value=30, value=3)

    for i in range(num_points):
        col1, col2 = st.columns(2)

        with col1:
            dist = st.number_input(
                f"Distanz Punkt {i+1} (km)",
                min_value=0.0,
                max_value=float(max_dist),
                value=min(float(max_dist), (i+1)*50.0),
                key=f"dist_{i}"
            )

        with col2:
            name = st.text_input(
                f"Name Punkt {i+1}",
                value=f"Punkt {i+1}",
                key=f"name_{i}"
            )

        controls.append({"km": dist, "name": name})
    
    # Startzeit
    default_start = df["time"].iloc[0]
    start_time = st.time_input("Startzeit", default_start.time())
    start_date = st.date_input("Startdatum", default_start.date())
    start_datetime = datetime.combine(start_date, start_time)

    # Kontrollpunkte
    st.subheader("Kontrollpunkte definieren")
    max_dist = df["dist_km_cum"].iloc[-1]

    num_points = st.number_input("Anzahl Kontrollpunkte", min_value=1, max_value=30, value=3)
    controls = []

    for i in range(num_points):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.number_input(
                f"Distanz Punkt {i+1} (km)",
                min_value=0.0,
                max_value=float(max_dist),
                value=min(float(max_dist), (i+1)*50.0),
                key=f"dist_{i}"
            )
        with col2:
            name = st.text_input(
                f"Name Punkt {i+1}",
                value=f"Punkt {i+1}",
                key=f"name_{i}"
            )

        controls.append({"km": dist, "name": name})

    if st.button("Berechnen"):
        controls = sorted(controls, key=lambda x: x["km"])

        results = []
        last_km = 0.0
        current_start = start_datetime

        for i, cp in enumerate(controls):
            cp_km = cp["km"]

            gps_time_at_cp = interpolate_time_at_distance(df, cp_km)
            gps_time_at_last = interpolate_time_at_distance(df, last_km)

            segment_duration = gps_time_at_cp - gps_time_at_last
            segment_hours = segment_duration.total_seconds() / 3600.0
            segment_dist = cp_km - last_km
            avg_speed = segment_dist / segment_hours if segment_hours > 0 else 0.0

            base_offset = gps_time_at_cp - df["time"].iloc[0]
            simulated_arrival = current_start + base_offset

            # Pause = GPS-Zeit – simulierte Zeit
            st.subheader("Kontrollpunkte aus CSV laden")

            csv_file = st.file_uploader("CSV-Datei mit Kontrollpunkten (km,name)", type=["csv"])
            
            controls = []
            
            if csv_file is not None:
                try:
                    df_controls = pd.read_csv(csv_file)
                    if "km" not in df_controls.columns or "name" not in df_controls.columns:
                        st.error("CSV muss die Spalten 'km' und 'name' enthalten.")
                    else:
                        for _, row in df_controls.iterrows():
                            controls.append({"km": float(row["km"]), "name": str(row["name"])})
                        st.success(f"{len(controls)} Kontrollpunkte geladen.")
                except Exception as e:
                    st.error(f"Fehler beim Lesen der CSV: {e}")

            
            pause_td = gps_time_at_cp - simulated_arrival
            if pause_td.total_seconds() < 0:
                pause_td = timedelta(seconds=0)

            arrival_time = simulated_arrival
            departure_time = arrival_time + pause_td

            results.append({
                "Name": cp["name"],
                "km": cp_km,
                "Ankunft": arrival_time,
                "Pause_min": pause_td.total_seconds() / 60.0,
                "Abfahrt": departure_time,
                "Segment_km": segment_dist,
                "Segment_h": segment_hours,
                "Ø-Speed_kmh": avg_speed
            })

            last_km = cp_km
            current_start = departure_time

        res_df = pd.DataFrame(results)
        st.subheader("Ergebnisse")
        st.dataframe(res_df)

else:
    st.info("Bitte eine GPX-Datei hochladen.")


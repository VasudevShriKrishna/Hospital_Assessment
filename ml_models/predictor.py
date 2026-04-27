# ---------------------- hospital prediction helpers -----------------------
import math
import joblib
from django.core.exceptions import ImproperlyConfigured

# Try to import Hospital model (adjust if your app name / model differs)
try:
    from earthquake.models import Hospital  # preferred
except Exception:
    try:
        from hospitals.models import Hospital  # fallback
    except Exception:
        Hospital = None
        # We won't raise here; we handle later and give clear error if model missing.


MODEL_FILE = os.path.join(SAVE_PATH, "earthquake_pipeline_model.pkl")

def haversine_km(lat1, lon1, lat2, lon2):
    """Return distance in kilometers between two points (Haversine)."""
    R = 6371.0  # Earth radius (km)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _make_feature_row(event):
    """
    Construct a single-row DataFrame with the same features and feature-engineering
    used during training. Missing features will be set to NaN or 0 as reasonable.
    event: dict with keys: magnitude, latitude, longitude, optionally nst, gap, dmin, rms,
           horizontal_error, depth_error, mag_error, mag_nst, depth (if known)
    """
    # required keys
    mag = event.get("magnitude", np.nan)
    lat = event.get("latitude", np.nan)
    lon = event.get("longitude", np.nan)

    row = {
        "magnitude": mag,
        "latitude": lat,
        "longitude": lon,
        "nst": event.get("nst", np.nan),
        "gap": event.get("gap", np.nan),
        "dmin": event.get("dmin", np.nan),
        "rms": event.get("rms", np.nan),
        "horizontal_error": event.get("horizontal_error", np.nan),
        "depth_error": event.get("depth_error", np.nan),
        "mag_error": event.get("mag_error", np.nan),
        "mag_nst": event.get("mag_nst", np.nan),
    }

    # engineered features matching training
    row["lat_lon_interaction"] = lat * lon if (not np.isnan(lat) and not np.isnan(lon)) else np.nan
    row["lat_squared"] = lat ** 2 if not np.isnan(lat) else np.nan
    row["lon_squared"] = lon ** 2 if not np.isnan(lon) else np.nan

    return pd.DataFrame([row])


def predict_depth_for_event(event):
    """
    Load trained pipeline and predict depth (in km). Returns predicted_depth_km (float)
    and the underlying log-prediction.
    """
    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(f"Trained model not found at: {MODEL_FILE}")

    pipeline = joblib.load(MODEL_FILE)

    feat_df = _make_feature_row(event)

    # pipeline expects the same feature column order as during training
    pred_log = pipeline.predict(feat_df)[0]
    pred_depth = float(np.expm1(pred_log))
    return pred_depth, pred_log


def predict_affected_hospitals(event, top_n=10, decay_km=50.0, depth_influence=0.01, capacity_weight=0.5):
    """
    Predict and rank hospitals by an impact score.
    - event: dict with keys magnitude, latitude, longitude, optionally other features
    - decay_km: controls how quickly impact decays with distance (smaller -> steeper decay)
    - depth_influence: how strongly depth reduces surface impact (multiplier inside depth factor)
    - capacity_weight: optional weight to boost larger hospitals (0 to 1). If Hospital model
      contains a 'capacity' field, it will be used; else capacity is ignored.
    Returns: pandas.DataFrame with columns ['hospital_id', 'name', 'distance_km', 'capacity',
                                            'impact_score', 'impact_rank']
    """
    if Hospital is None:
        raise ImproperlyConfigured("Hospital model not available. Adjust import or model name.")

    # predict depth for the event
    pred_depth_km, _ = predict_depth_for_event(event)
    mag = float(event.get("magnitude", 0.0))
    epic_lat = float(event.get("latitude"))
    epic_lon = float(event.get("longitude"))

    # load hospitals
    hospitals_qs = Hospital.objects.filter(latitude__isnull=False, longitude__isnull=False).values(
        'id', 'name', 'latitude', 'longitude', 'capacity'
    )

    hospitals = pd.DataFrame(list(hospitals_qs))
    if hospitals.empty:
        raise ValueError("No hospitals found in DB with latitude/longitude.")

    # compute distances
    distances = []
    for _, row in hospitals.iterrows():
        d = haversine_km(epic_lat, epic_lon, float(row['latitude']), float(row['longitude']))
        distances.append(d)
    hospitals['distance_km'] = distances

    # Distance decay factor: exp(-distance / decay_km). nearer -> close to 1; far -> small.
    hospitals['distance_factor'] = np.exp(-hospitals['distance_km'] / float(decay_km))

    # Depth factor: shallower quakes generally produce stronger surface shaking.
    # We use 1 / (1 + depth_influence * depth). Smaller depth_influence -> weaker depth effect.
    depth_factor = 1.0 / (1.0 + depth_influence * pred_depth_km)

    # Capacity factor: if capacity present, normalize it; otherwise default 1.
    if 'capacity' in hospitals.columns and hospitals['capacity'].notna().any():
        capacities = hospitals['capacity'].fillna(0.0)
        # avoid divide-by-zero
        if capacities.max() > 0:
            hospitals['capacity_factor'] = capacities / capacities.max()
        else:
            hospitals['capacity_factor'] = 0.0
    else:
        hospitals['capacity_factor'] = 1.0

    # Basic interpretable impact score:
    # impact = magnitude * distance_factor * depth_factor * (1 + capacity_weight * capacity_factor)
    # capacity_weight in [0,1] scales how much larger hospitals are considered 'more affected' (e.g., exposure).
    hospitals['impact_score_raw'] = (
        mag
        * hospitals['distance_factor']
        * depth_factor
        * (1.0 + float(capacity_weight) * hospitals['capacity_factor'])
    )

    # Normalize the impact score to 0-1 for readability
    max_score = hospitals['impact_score_raw'].max()
    if max_score > 0:
        hospitals['impact_score'] = hospitals['impact_score_raw'] / max_score
    else:
        hospitals['impact_score'] = 0.0

    hospitals = hospitals.sort_values('impact_score', ascending=False).reset_index(drop=True)
    hospitals['impact_rank'] = hospitals.index + 1

    cols = ['id', 'name', 'latitude', 'longitude', 'distance_km', 'capacity', 'impact_score', 'impact_rank']
    # ensure columns exist
    for c in cols:
        if c not in hospitals.columns:
            hospitals[c] = np.nan

    return hospitals[cols].head(top_n)


# ---------------------- example CLI usage -----------------------
if __name__ == "__main__":
    # keep original train flow if script called directly
    train_model()

    # Example prediction (uncomment and adapt for quick local test):
    # sample_event = {
    #     "magnitude": 6.2,
    #     "latitude": 34.05,
    #     "longitude": -118.25,
    #     "nst": 45, "gap": 80, "dmin": 0.02, "rms": 0.9,
    #     "horizontal_error": 0.2, "depth_error": 1.0, "mag_error": 0.05, "mag_nst": 20
    # }
    # try:
    #     top_hospitals = predict_affected_hospitals(sample_event, top_n=5, decay_km=60, depth_influence=0.02)
    #     print(top_hospitals.to_string(index=False))
    # except Exception as e:
    #     print("Prediction example failed:", e)
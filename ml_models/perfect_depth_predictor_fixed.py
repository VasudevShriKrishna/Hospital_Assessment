"""
PERFECT FIXED EARTHQUAKE DEPTH PREDICTOR v2.0
No errors, deterministic, optimized.
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
import random
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from xgboost import XGBRegressor

# Deterministic
random.seed(42)
np.random.seed(42)

# Django
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'earthquake_project.settings')
import django
django.setup()
from earthquake.models import HistoricalEarthquake

SAVE_PATH = r"G:\earthquake_today\earthquake_project\ml_models"
MODEL_FILE = os.path.join(SAVE_PATH, "perfect_depth_model_fixed.pkl")

def train_model():
    print("=" * 80)
    print("🚀 PERFECT FIXED DEPTH PREDICTOR - NO ERRORS")
    print("=" * 80)

    # Data
    earthquakes = HistoricalEarthquake.objects.filter(
        magnitude__isnull=False,
        depth__isnull=False,
        latitude__isnull=False,
        longitude__isnull=False
    ).values('magnitude', 'latitude', 'longitude', 'nst', 'gap', 'dmin', 'rms', 'horizontal_error', 'depth_error', 'mag_error', 'mag_nst', 'time', 'mag_type', 'net', 'status', 'depth')

    df = pd.DataFrame(list(earthquakes))
    print(f"Loaded: {len(df)}")

    # Clean robust
    df = df.dropna(subset=['magnitude', 'latitude', 'longitude', 'depth'])
    impute_cols = ['nst', 'gap', 'dmin', 'rms', 'horizontal_error', 'depth_error', 'mag_error', 'mag_nst']
    df[impute_cols] = df[impute_cols].fillna(0)
    df = df[(df['depth'] >= 0) & (df['depth'] <= 700)]
    print(f"Ready: {len(df)}")

    if len(df) < 100:
        return "Insufficient data"

    # Eng
    df['lat_lon_int'] = df['latitude'] * df['longitude']
    df['lat_sq'] = df['latitude'] ** 2
    df['lon_sq'] = df['longitude'] ** 2
    df['mag_sq'] = df['magnitude'] ** 2

    # Time
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    df['month_sin'] = np.sin(2 * np.pi * df['time'].dt.month/12)
    df['month_cos'] = np.cos(2 * np.pi * df['time'].dt.month/12)
    df['year_norm'] = (df['time'].dt.year - 2000) / 20  # Normalize

    # Cat
    cat_cols = ['mag_type', 'net', 'status']
    df[cat_cols] = df[cat_cols].fillna('unknown')
    encoder = OneHotEncoder(sparse_output=False, drop='first')
    cat_enc = encoder.fit_transform(df[cat_cols])
    cat_names = encoder.get_feature_names_out()
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(cat_enc, columns=cat_names)], axis=1)

    # Target
    df['depth_log'] = np.log1p(df['depth'])

    feature_cols = ['magnitude', 'mag_sq', 'latitude', 'longitude', 'nst', 'gap', 'dmin', 'rms', 'lat_lon_int', 'lat_sq', 'lon_sq', 'month_sin', 'month_cos', 'year_norm'] + list(cat_names)
    X = df[feature_cols].fillna(0)
    y = df['depth_log']

    print(f"Features: {len(feature_cols)}")

    # Split temporal
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False, random_state=42)

    # Perfect model
    pipeline = Pipeline([
        ('scaler', RobustScaler()),
        ('model', XGBRegressor(n_estimators=1500, learning_rate=0.01, max_depth=6, subsample=0.9, colsample_bytree=0.9, reg_alpha=0.1, reg_lambda=0.1, tree_method='hist', random_state=42))
    ])

    pipeline.fit(X_train, y_train)

    # Perf
    y_pred_log = pipeline.predict(X_test)
    y_pred = np.expm1(y_pred_log)
    y_true = np.expm1(y_test)
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    print("\n🎯 PERFECT PERF")
    print(f"R²: {r2:.4f}")
    print(f"MAE: {mae:.2f} km")
    print(f"RMSE: {rmse:.2f} km")

    # Save
    os.makedirs(SAVE_PATH, exist_ok=True)
    joblib.dump(pipeline, MODEL_FILE)
    print(f"✅ Saved: {MODEL_FILE}")

if __name__ == '__main__':
    train_model()


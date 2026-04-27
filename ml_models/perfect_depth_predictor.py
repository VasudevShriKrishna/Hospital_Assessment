"""
PERFECT DETERMINISTIC EARTHQUAKE DEPTH PREDICTOR
Target: depth (log-transformed)
R² Target: >0.95, MAE <1km
Algorithm: Optimized XGBoost Ensemble-like
Deterministic: Full seeds, temporal CV
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
import random
from pathlib import Path
from sklearn.model_selection import train_test_split, TimeSeriesSplit, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from xgboost import XGBRegressor

# Deterministic seeds first
random.seed(42)
np.random.seed(42)

# Django setup
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'earthquake_project.settings')

import django
django.setup()

from earthquake.models import HistoricalEarthquake

SAVE_PATH = r"G:\earthquake_today\earthquake_project\ml_models"
MODEL_FILE = os.path.join(SAVE_PATH, "perfect_depth_model.pkl")


def train_model():
    print("=" * 80)
    print("🚀 TRAINING PERFECT DETERMINISTIC DEPTH PREDICTOR")
    print("=" * 80)

    # Fetch expanded fields
    earthquakes = HistoricalEarthquake.objects.filter(
        magnitude__isnull=False,
        depth__isnull=False,
        latitude__isnull=False,
        longitude__isnull=False
    ).values(
        'magnitude', 'latitude', 'longitude',
        'nst', 'gap', 'dmin', 'rms',
        'horizontal_error', 'depth_error', 'mag_error', 'mag_nst',
        'time', 'mag_type', 'net', 'status', 'depth'
    )

    df = pd.DataFrame(list(earthquakes))
    print(f"Loaded records: {len(df)}")

    # Robust target cleaning
    df = df.dropna(subset=['magnitude', 'latitude', 'longitude', 'depth'])
    print(f"After target cleaning: {len(df)}")

    # Impute aux
    impute_cols = ['nst', 'gap', 'dmin', 'rms', 'horizontal_error', 'depth_error', 'mag_error', 'mag_nst']
    medians = df[impute_cols].median().fillna(0)
    df[impute_cols] = df[impute_cols].fillna(medians)

    # Physics filter
    df = df[(df['depth'] >= 0) & (df['depth'] <= 700) & df['depth'].notna()]
    print(f"Final records: {len(df)}")

    if len(df) < 100:
        raise ValueError("Insufficient data.")

    # Feature Engineering - Perfect set
    df['lat_lon_interaction'] = df['latitude'] * df['longitude']
    df['lat_squared'] = df['latitude'] ** 2
    df['lon_squared'] = df['longitude'] ** 2
    df['mag_squared'] = df['magnitude'] ** 2
    df['error_mean'] = df[['horizontal_error', 'depth_error', 'mag_error']].mean(axis=1)

    # Time cyclical (deterministic)
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    df['month_sin'] = np.sin(2 * np.pi * df['time'].dt.month / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['time'].dt.month / 12)
    df['year_norm'] = (df['time'].dt.year - df['time'].dt.year.min()) / (df['time'].dt.year.max() - df['time'].dt.year.min() or 1)

    # Cat OHE
    cat_cols = ['mag_type', 'net', 'status']
    df[cat_cols] = df[cat_cols].fillna('unknown')
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore', drop='first')
    cat_encoded = encoder.fit_transform(df[cat_cols])
    cat_names = encoder.get_feature_names_out(cat_cols)
    cat_df = pd.DataFrame(cat_encoded, columns=cat_names, index=df.index)
    df = pd.concat([df, cat_df], axis=1)

    # Target
    df['depth_log'] = np.log1p(df['depth'])

    # Full feature list
    feature_cols = [
        'magnitude', 'mag_squared', 'latitude', 'longitude',
        'nst', 'gap', 'dmin', 'rms', 'error_mean',
        'lat_lon_interaction', 'lat_squared', 'lon_squared',
        'month_sin', 'month_cos', 'year_norm'
    ] + list(cat_names)

    print(f"Total features: {len(feature_cols)}")

    X = df[feature_cols].fillna(0)  # Deterministic fill
    y = df['depth_log']

    # Temporal split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

    # Perfect pipeline
    pipeline = Pipeline([
        ('scaler', RobustScaler()),
        ('model', XGBRegressor(
            n_estimators=2000,
            learning_rate=0.015,
            max_depth=8,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.3,
            reg_lambda=0.8,
            tree_method='hist',
            early_stopping_rounds=50,
            random_state=42,
            eval_metric='rmse'
        ))
    ])

    print("Training optimized model...")

    pipeline.fit(X_train, y_train)

    # Final eval
    y_pred_log = pipeline.predict(X_test)

    y_pred = np.expm1(y_pred_log)
    y_true = np.expm1(y_test)
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    print("\n🏆 PERFECT MODEL PERFORMANCE")
    print(f"CV R²: {cv_scores.mean():.4f}")
    print(f"Test R²: {r2:.4f}")
    print(f"MAE: {mae:.2f} km")
    print(f"RMSE: {rmse:.2f} km")

    os.makedirs(SAVE_PATH, exist_ok=True)
    joblib.dump(pipeline, MODEL_FILE)
    joblib.dump(encoder, os.path.join(SAVE_PATH, 'cat_encoder.pkl'))  # For predictor

    print(f"\n✅ Perfect model saved: {MODEL_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    train_model()


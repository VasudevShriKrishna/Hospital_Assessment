"""
HIGH-ACCURACY EARTHQUAKE DEPTH PREDICTOR
Target: depth (log-transformed)
Algorithm: XGBoost
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# Django setup
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'earthquake_project.settings')

import django
django.setup()

from earthquake.models import HistoricalEarthquake
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from xgboost import XGBRegressor

SAVE_PATH = r"G:\earthquake_today\earthquake_project\ml_models"
MODEL_FILE = os.path.join(SAVE_PATH, "earthquake_pipeline_model.pkl")

def train_model():
    print("=" * 70)
    print("🌍 TRAINING ADVANCED DEPTH MODEL")
    print("=" * 70)

    # Fetch required fields only
    earthquakes = HistoricalEarthquake.objects.filter(
        magnitude__isnull=False,
        depth__isnull=False,
        latitude__isnull=False,
        longitude__isnull=False
    ).values(
        'magnitude', 'latitude', 'longitude',
        'nst', 'gap', 'dmin', 'rms',
        'horizontal_error',
        'depth_error',
        'mag_error',
        'mag_nst',
        'depth'
   )
    
    df = pd.DataFrame(list(earthquakes))

    print(f"Loaded records: {len(df)}")

    # Drop NaNs first
    df = df.dropna()
    # Remove invalid depths
    df = df[df['depth'] >= 0]          # No negative depths
    df = df[df['depth'] <= 700]        # Physical Earth limit (~700 km)
    # Remove extreme outliers
    df = df[np.isfinite(df['depth'])]
    print(f"Records after depth cleaning: {len(df)}")

    if len(df) < 100:
        raise ValueError("Not enough valid data after cleaning.")

    # ---------- Feature Engineering ----------
    df['lat_lon_interaction'] = df['latitude'] * df['longitude']
    df['lat_squared'] = df['latitude'] ** 2
    df['lon_squared'] = df['longitude'] ** 2

    # Log-transform depth
    df['depth_log'] = np.log1p(df['depth'])

    feature_cols = [
        'magnitude',
        'latitude',
        'longitude',
        'nst',
        'gap',
        'dmin',
        'rms',
        'horizontal_error',
        'depth_error',
        'mag_error',
        'mag_nst',
        'lat_lon_interaction',
        'lat_squared',
        'lon_squared'
    ]

    X = df[feature_cols]
    y = df['depth_log']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = Pipeline([
        ('scaler', RobustScaler()),
        ('model', XGBRegressor(
            n_estimators=1200,
            learning_rate=0.02,
            max_depth=7,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.5,
            reg_lambda=1.0,
            random_state=42
        ))
    ])

    print("Training model...")
    pipeline.fit(X_train, y_train)

    # Evaluation
    y_pred_log = pipeline.predict(X_test)
    y_pred = np.expm1(y_pred_log)
    y_true = np.expm1(y_test)
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    print("\n📊 MODEL PERFORMANCE")
    print(f"R² Score: {r2:.4f}")
    print(f"MAE (km): {mae:.2f}")
    print(f"RMSE (km): {rmse:.2f}")

    if not os.path.exists(SAVE_PATH):
        os.makedirs(SAVE_PATH)

    joblib.dump(pipeline, MODEL_FILE)

    print(f"\n✅ Model saved to: {MODEL_FILE}")
    print("=" * 70)

if __name__ == "__main__":
    train_model()
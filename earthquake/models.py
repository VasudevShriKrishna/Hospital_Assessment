# hazards/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# If you are on Django < 3.1 and using Postgres, import:
# from django.contrib.postgres.fields import JSONField as JSONField
try:
    JSONField = models.JSONField
except AttributeError:
    # Fallback (older Django)
    from django.contrib.postgres.fields import JSONField  # type: ignore

MAG_TYPE_CHOICES = (
    ("ml", "ML"),
    ("mb", "Mb"),
    ("ms", "Ms"),
    ("mw", "Mw"),
    ("unknown", "Unknown"),
)

BUILDING_TYPE_CHOICES = (
    ("reinforced_concrete", "Reinforced concrete"),
    ("masonry", "Masonry"),
    ("steel", "Steel"),
    ("wood", "Wood"),
    ("other", "Other"),
)

OWNER_TYPE_CHOICES = (
    ("public", "Public"),
    ("private", "Private"),
    ("ngo", "NGO / Non-profit"),
)


class HistoricalEarthquake(models.Model):
    """
    Stores historical earthquake events. Fields map to your CSV columns.
    `latitude` and `longitude` store coordinates as floats.
    """

    event_id = models.CharField(
        max_length=100, unique=True, db_index=True, help_text="Original event id (CSV 'id' column)"
    )
    time = models.DateTimeField(null=True, blank=True, db_index=True)
    place = models.CharField(max_length=255, blank=True, default="")
    # Keep both mag and magnitude names for clarity; store as magnitude in DB column 'mag'
    magnitude = models.FloatField(
        validators=[MinValueValidator(-2.0), MaxValueValidator(10.0)],
        db_column="mag",
        help_text="Magnitude (maps to CSV 'mag')",
    )
    mag_type = models.CharField(max_length=20, choices=MAG_TYPE_CHOICES, default="unknown", blank=True)
    depth = models.FloatField(null=True, blank=True, help_text="Depth in kilometers")
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)

    # Other CSV numeric / string columns (optional)
    nst = models.IntegerField(null=True, blank=True)
    gap = models.FloatField(null=True, blank=True)
    dmin = models.FloatField(null=True, blank=True)
    rms = models.FloatField(null=True, blank=True)
    net = models.CharField(max_length=50, null=True, blank=True)
    updated = models.DateTimeField(null=True, blank=True)
    quake_type = models.CharField(max_length=50, null=True, blank=True, db_column="type")
    horizontal_error = models.FloatField(null=True, blank=True)
    depth_error = models.FloatField(null=True, blank=True)
    mag_error = models.FloatField(null=True, blank=True)
    mag_nst = models.IntegerField(null=True, blank=True, db_column="magNst")
    status = models.CharField(max_length=50, null=True, blank=True)
    location_source = models.CharField(max_length=50, null=True, blank=True)
    mag_source = models.CharField(max_length=50, null=True, blank=True)

    raw = JSONField(null=True, blank=True, help_text="Raw row JSON for provenance / debugging")

    class Meta:
        ordering = ("-time",)
        indexes = [
            models.Index(fields=["time"]),
            models.Index(fields=["magnitude"]),
            models.Index(fields=["event_id"]),
            models.Index(fields=["depth"]),
        ]
        verbose_name = "Historical Earthquake"
        verbose_name_plural = "Historical Earthquakes"

    def __str__(self):
        return f"{self.event_id} | {self.place or 'unknown'} | M{self.magnitude}"

    def distance_to(self, lat, lon):
        """
        Calculate distance in kilometers to a given point using Haversine formula.
        """
        import math
        if self.latitude is None or self.longitude is None:
            return None
        
        R = 6371  # Earth radius in km
        phi1 = math.radians(self.latitude)
        phi2 = math.radians(lat)
        dphi = math.radians(lat - self.latitude)
        dlambda = math.radians(lon - self.longitude)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c


class Hospital(models.Model):
    """
    Hospital entity that we want to assess for seismic hazard.
    Stores structural & operational metadata used for vulnerability scoring.
    """

    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Total beds / capacity")
    critical_beds = models.PositiveIntegerField(null=True, blank=True, help_text="ICU / critical care beds")

    building_type = models.CharField(max_length=30, choices=BUILDING_TYPE_CHOICES, default="other")
    floors = models.PositiveIntegerField(null=True, blank=True)
    year_built = models.PositiveIntegerField(null=True, blank=True)
    retrofit = models.BooleanField(default=False, help_text="Whether seismic retrofit has been applied")
    primary_material = models.CharField(max_length=120, blank=True, help_text="Primary construction material")

    owner_type = models.CharField(max_length=20, choices=OWNER_TYPE_CHOICES, default="public")

    # Optional vulnerability score — computed by your hazard model / manual assessment
    vulnerability_score = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(0.0)], help_text="0 (low) - higher is more vulnerable"
    )

    notes = models.TextField(blank=True)
    last_assessed = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Hospital"
        verbose_name_plural = "Hospitals"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.address[:40] + '...' if self.address and len(self.address) > 40 else self.address})"

    def mark_assessed(self, score: float):
        """
        Helper to set vulnerability score and timestamp.
        """
        self.vulnerability_score = float(score)
        self.last_assessed = timezone.now()
        self.save(update_fields=["vulnerability_score", "last_assessed"])


class MLModelVersion(models.Model):
    """
    Optional: store ML model artifact metadata for reproducibility.
    You can store a FileField pointing to a .pkl or keep file path strings.
    """

    name = models.CharField(max_length=200, help_text="Model name, e.g. 'mag_predictor'")
    version = models.CharField(max_length=50, default="v1")
    file = models.FileField(upload_to="models/", null=True, blank=True, help_text="Trained model artifact (.pkl)")
    trained_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    metrics = JSONField(null=True, blank=True, help_text="Performance metrics (RMSE, R2, etc.)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("name", "version")
        ordering = ("-trained_at", "-created_at")

    def __str__(self):
        return f"{self.name} {self.version}"


class HazardAssessment(models.Model):
    """
    A record of a hazard assessment for a hospital — produced by your ML pipeline or manual process.
    Stores model inputs (features), associated earthquake (optional), and the predicted risk/score.
    """

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="assessments")
    earthquake = models.ForeignKey(
        HistoricalEarthquake, null=True, blank=True, on_delete=models.SET_NULL, related_name="assessments"
    )
    assessed_at = models.DateTimeField(auto_now_add=True)
    model_version = models.ForeignKey(MLModelVersion, null=True, blank=True, on_delete=models.SET_NULL)

    # Predicted continuous risk / score (model output). Use null for not-yet-scored assessments.
    predicted_risk = models.FloatField(null=True, blank=True)

    # Serializing the features used for the prediction so you can reproduce results later
    features = JSONField(null=True, blank=True, help_text="Features fed to the model at prediction time")

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-assessed_at",)

    def __str__(self):
        return f"Assessment {self.pk} | {self.hospital.name} | {self.assessed_at.isoformat()}"

    def apply_prediction(self, score: float):
        """
        Convenience method: set the prediction score and save.
        """
        self.predicted_risk = float(score)
        self.save(update_fields=["predicted_risk"])


# Optional: convenience manager / query helpers (example)
class HistoricalEarthquakeManager(models.Manager):
    def recent(self, days=30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.get_queryset().filter(time__gte=cutoff)


# Attach manager to HistoricalEarthquake if you want:
HistoricalEarthquake.add_to_class("objects", HistoricalEarthquakeManager())

# from django.contrib.gis.db import models

# class HistoricalEarthquake(models.Model):
#     place = models.CharField(max_length=255)
#     magnitude = models.FloatField()
#     depth = models.FloatField(null=True, blank=True) # Added this field
#     location = models.PointField()

#     def __str__(self):
#         return self.place
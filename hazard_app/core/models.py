from django.db import models
# Create your models here.

class Hospital(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.name, self.latitude, self.longitude, self.location
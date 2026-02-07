from django.conf import settings
from django.db import models

import uuid

# Create your models here.

AIRCRAFT_STATUSES = (
        ('AVAILABLE', 'Available'),
        ('MX', 'In Maintenance'),
        ('GROUND', 'Grounded'),
        ('UNAVAILABLE', 'Unavailable'),
)

def random_picture_filename(instance, filename):
    randname = uuid.uuid4().hex
    ext = filename.split('.')[-1]
    return f"aircraft_pictures/{randname}.{ext}"

class Aircraft(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    tail_number = models.CharField(max_length=254, blank=False)
    make = models.CharField(max_length=254, blank=True)
    model = models.CharField(max_length=254, blank=True)
    serial_number = models.CharField(max_length=254, blank=True)
    description = models.TextField(blank=True)
    purchased = models.DateField(blank=True)
    added = models.DateTimeField(auto_now_add=True, editable=False)
    picture = models.ImageField(upload_to=random_picture_filename, blank=True)
    status = models.CharField(max_length=254, blank=False, choices=AIRCRAFT_STATUSES, default="AVAILABLE")
    flight_time = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)

    def __str__(self):
        return f"{self.tail_number} - {self.make} {self.model}"

class AircraftNote(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, related_name='notes', on_delete=models.CASCADE, blank=False)
    added_timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    edited_timestamp = models.DateTimeField(blank=True, null=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    text = models.TextField()

    def __str__(self):
        return f"{self.aircraft.tail_number} - {self.text}"

class AircraftEvent(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, related_name='events', on_delete=models.CASCADE, blank=False)
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    category = models.CharField(max_length=254, blank=False)
    event_name = models.CharField(max_length=254, blank=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.aircraft.tail_number} - {self.event_name}"

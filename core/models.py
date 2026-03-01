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

def make_upload_path(subdir):
    def upload_to(instance, filename):
        ext = filename.rsplit('.', 1)[-1]
        return f"{subdir}/{uuid.uuid4().hex}.{ext}"
    return upload_to

random_picture_filename = make_upload_path("aircraft_pictures")

class Aircraft(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    tail_number = models.CharField(max_length=254, blank=False)
    make = models.CharField(max_length=254, blank=True)
    model = models.CharField(max_length=254, blank=True)
    serial_number = models.CharField(max_length=254, blank=True)
    description = models.TextField(blank=True)
    purchased = models.DateField(blank=True, null=True)
    added = models.DateTimeField(auto_now_add=True, editable=False)
    picture = models.ImageField(upload_to=random_picture_filename, blank=True)
    status = models.CharField(max_length=254, blank=False, choices=AIRCRAFT_STATUSES, default="AVAILABLE")
    tach_time = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    tach_time_offset = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    hobbs_time = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)
    hobbs_time_offset = models.DecimalField(max_digits=8, decimal_places=1, default=0.0)

    def __str__(self):
        return f"{self.tail_number} - {self.make} {self.model}"

class AircraftNote(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, related_name='notes', on_delete=models.CASCADE, blank=False)
    added_timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    edited_timestamp = models.DateTimeField(blank=True, null=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    text = models.TextField()
    public = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.aircraft.tail_number} - {self.text}"

EVENT_CATEGORIES = (
    ('hours', 'Hours Update'),
    ('flight', 'Flight'),
    ('component', 'Component'),
    ('squawk', 'Squawk'),
    ('note', 'Note'),
    ('oil', 'Oil'),
    ('fuel', 'Fuel'),
    ('logbook', 'Logbook'),
    ('ad', 'Airworthiness Directive'),
    ('inspection', 'Inspection'),
    ('document', 'Document'),
    ('aircraft', 'Aircraft'),
    ('role', 'Role'),
    ('major_record', 'Major Repair/Alteration'),
)

class AircraftEvent(models.Model):
    id = models.UUIDField(primary_key=True, blank=False, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, related_name='events', on_delete=models.CASCADE, blank=False)
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    category = models.CharField(max_length=50, blank=False, choices=EVENT_CATEGORIES)
    event_name = models.CharField(max_length=254, blank=False)
    notes = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.aircraft.tail_number} - {self.event_name}"

AIRCRAFT_ROLES = (
    ('owner', 'Owner'),
    ('pilot', 'Pilot'),
)

class AircraftRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, related_name='roles', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='aircraft_roles', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=AIRCRAFT_ROLES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('aircraft', 'user')
        ordering = ['role', 'created_at']

    def __str__(self):
        return f"{self.user} - {self.role} on {self.aircraft.tail_number}"


SHARE_PRIVILEGE_CHOICES = [
    ('status', 'Current Status'),
    ('maintenance', 'Maintenance Detail'),
]


class AircraftShareToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='share_tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    label = models.CharField(max_length=100, blank=True)
    privilege = models.CharField(max_length=20, choices=SHARE_PRIVILEGE_CHOICES, default='status')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, editable=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.aircraft.tail_number} - {self.label or self.privilege} share token"


class InvitationCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    label = models.CharField(max_length=200, help_text="Admin label, e.g. 'Club XYZ Pilots - Spring 2026'")

    # Optional per-user fields — when set, the registration form is pre-filled
    # and the code is effectively single-use for that person
    invited_email = models.EmailField(blank=True)
    invited_name = models.CharField(max_length=200, blank=True)

    # Usage control (null = unlimited)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited uses")
    use_count = models.PositiveIntegerField(default=0, editable=False)

    # Lifecycle
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Leave blank to never expire")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.label

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.max_uses is not None and self.use_count >= self.max_uses:
            return False
        return True


class InvitationCodeAircraftRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation_code = models.ForeignKey(InvitationCode, on_delete=models.CASCADE, related_name='initial_roles')
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=AIRCRAFT_ROLES)

    class Meta:
        unique_together = ('invitation_code', 'aircraft')

    def __str__(self):
        return f"{self.invitation_code.label} → {self.role} on {self.aircraft.tail_number}"


class InvitationCodeRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.ForeignKey(InvitationCode, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('code', 'user')

    def __str__(self):
        return f"{self.user} redeemed '{self.code.label}'"

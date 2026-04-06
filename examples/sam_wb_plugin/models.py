"""Models for the Weight & Balance plugin.

Two models:
  WBConfig       — per-aircraft CG envelope configuration (1:1 with Aircraft)
  WBCalculation  — saved loading scenarios with computed totals
"""

import uuid

from django.db import models


class WBConfig(models.Model):
    """Weight & balance envelope configuration for one aircraft.

    Stores the aircraft's certified CG envelope: empty weight, empty CG,
    maximum gross weight, forward/aft CG limits, and the list of named
    loading stations with their arm distances from the datum.

    One config per aircraft (enforced by OneToOneField).  Owners set this
    up once from the aircraft W&B tab; pilots can read it to run the
    calculator.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    aircraft = models.OneToOneField(
        'core.Aircraft',
        on_delete=models.CASCADE,
        related_name='wb_config',
    )

    # Basic empty weight and CG from the POH / weight-and-balance record.
    empty_weight = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        help_text='Basic empty weight in pounds',
    )
    empty_cg = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text='Empty CG — inches aft of datum',
    )

    # Certified CG envelope limits.
    max_gross_weight = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        help_text='Maximum gross weight in pounds',
    )
    fwd_cg_limit = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text='Forward CG limit — inches aft of datum',
    )
    aft_cg_limit = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text='Aft CG limit — inches aft of datum',
    )

    # Loading stations: list of {"name": str, "arm": float} dicts.
    # Example: [{"name": "Front Seats", "arm": 37.0},
    #           {"name": "Rear Seats",  "arm": 73.0},
    #           {"name": "Baggage",     "arm": 95.0},
    #           {"name": "Fuel (gal)",  "arm": 48.0}]
    stations = models.JSONField(
        default=list,
        help_text='List of {name, arm} station dicts ordered for display',
    )

    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'W&B configuration'

    def __str__(self):
        return f'W&B config — {self.aircraft}'


class WBCalculation(models.Model):
    """A saved weight-and-balance loading scenario.

    Records one complete loading scenario: the weights entered at each
    station, plus the computed gross weight and CG.  The empty weight and
    CG are snapshotted from WBConfig at save time so the record remains
    accurate if the config is later edited (e.g. after a new weight-and-
    balance check).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    aircraft = models.ForeignKey(
        'core.Aircraft',
        on_delete=models.CASCADE,
        related_name='wb_calculations',
    )

    label = models.CharField(
        max_length=200,
        help_text="Short description, e.g. 'Solo cross-country' or 'Full fuel + 3 pax'",
    )

    # Station weights entered by the pilot.
    # List of {"station_name": str, "arm": float, "weight": float} dicts.
    items = models.JSONField(default=list)

    # Snapshot of config values at save time.
    empty_weight = models.DecimalField(max_digits=8, decimal_places=1)
    empty_cg = models.DecimalField(max_digits=7, decimal_places=2)

    # Computed totals (stored so they can be read without re-running the math).
    gross_weight = models.DecimalField(max_digits=8, decimal_places=1)
    gross_moment = models.DecimalField(max_digits=14, decimal_places=2)
    gross_cg = models.DecimalField(max_digits=7, decimal_places=2)
    within_limits = models.BooleanField()

    notes = models.TextField(blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'W&B calculation'
        ordering = ['-calculated_at']

    def __str__(self):
        status = 'OK' if self.within_limits else 'OUT OF LIMITS'
        return f'{self.label} ({self.aircraft}) — {status}'

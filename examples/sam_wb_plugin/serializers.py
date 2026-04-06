"""Serializers for the Weight & Balance plugin."""

from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from .models import WBConfig, WBCalculation

_ARM_MIN = -500
_ARM_MAX = 500
_WEIGHT_MAX = 50000
_MAX_STATIONS = 50


class WBConfigSerializer(serializers.HyperlinkedModelSerializer):
    # HyperlinkedModelSerializer omits `id` from __all__ — include it explicitly
    # so Alpine.js x-for :key="config.id" works (see CLAUDE.md gotcha #2).
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = WBConfig
        fields = [
            'url', 'id', 'aircraft',
            'empty_weight', 'empty_cg',
            'max_gross_weight', 'fwd_cg_limit', 'aft_cg_limit',
            'stations', 'notes',
        ]
        # DRF derives the url field view name from the model name ("wbconfig-detail")
        # but the router registered this viewset with basename "wb-config", giving
        # view name "wb-config-detail".  Specify it explicitly to match the router.
        extra_kwargs = {
            'url': {'view_name': 'wb-config-detail'},
        }

    def validate_stations(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("stations must be a list.")
        if len(value) > _MAX_STATIONS:
            raise serializers.ValidationError(
                f"stations may not contain more than {_MAX_STATIONS} entries."
            )
        for i, station in enumerate(value):
            if not isinstance(station, dict):
                raise serializers.ValidationError(
                    f"stations[{i}] must be an object."
                )
            if not isinstance(station.get('name'), str) or not station['name'].strip():
                raise serializers.ValidationError(
                    f"stations[{i}].name must be a non-empty string."
                )
            arm = station.get('arm')
            if not isinstance(arm, (int, float)) or isinstance(arm, bool):
                raise serializers.ValidationError(
                    f"stations[{i}].arm must be a number."
                )
            if not (_ARM_MIN <= arm <= _ARM_MAX):
                raise serializers.ValidationError(
                    f"stations[{i}].arm must be between {_ARM_MIN} and {_ARM_MAX}."
                )
        return value


class WBCalculationSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.UUIDField(read_only=True)

    # Derived totals are computed server-side on create/update.
    gross_weight = serializers.DecimalField(max_digits=8, decimal_places=1, read_only=True)
    gross_moment = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    gross_cg = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    within_limits = serializers.BooleanField(read_only=True)
    calculated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = WBCalculation
        fields = [
            'url', 'id', 'aircraft', 'label',
            'items', 'empty_weight', 'empty_cg',
            'gross_weight', 'gross_moment', 'gross_cg',
            'within_limits', 'notes', 'calculated_at',
        ]
        read_only_fields = [
            'gross_weight', 'gross_moment', 'gross_cg',
            'within_limits', 'calculated_at',
        ]
        extra_kwargs = {
            'url': {'view_name': 'wb-calculation-detail'},
        }

    def validate_items(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("items must be a list.")
        if len(value) > _MAX_STATIONS:
            raise serializers.ValidationError(
                f"items may not contain more than {_MAX_STATIONS} entries."
            )
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(
                    f"items[{i}] must be an object."
                )
            if not isinstance(item.get('station_name'), str) or not item['station_name'].strip():
                raise serializers.ValidationError(
                    f"items[{i}].station_name must be a non-empty string."
                )
            arm = item.get('arm')
            if not isinstance(arm, (int, float)) or isinstance(arm, bool):
                raise serializers.ValidationError(
                    f"items[{i}].arm must be a number."
                )
            if not (_ARM_MIN <= arm <= _ARM_MAX):
                raise serializers.ValidationError(
                    f"items[{i}].arm must be between {_ARM_MIN} and {_ARM_MAX}."
                )
            weight = item.get('weight')
            if not isinstance(weight, (int, float)) or isinstance(weight, bool):
                raise serializers.ValidationError(
                    f"items[{i}].weight must be a number."
                )
            if not (0 <= weight <= _WEIGHT_MAX):
                raise serializers.ValidationError(
                    f"items[{i}].weight must be between 0 and {_WEIGHT_MAX}."
                )
        return value

    def _compute_totals(self, validated_data):
        """Return computed gross weight, moment, CG, and within_limits.

        The caller merges the returned dict into validated_data before saving.
        """
        items = validated_data.get('items', [])
        empty_weight = Decimal(str(validated_data['empty_weight']))
        empty_cg = Decimal(str(validated_data['empty_cg']))

        payload_weight = Decimal('0')
        payload_moment = Decimal('0')
        for item in items:
            weight = Decimal(str(item.get('weight', 0)))
            arm = Decimal(str(item.get('arm', 0)))
            payload_weight += weight
            payload_moment += weight * arm

        gross_weight = empty_weight + payload_weight
        gross_moment = empty_weight * empty_cg + payload_moment
        gross_cg = (gross_moment / gross_weight) if gross_weight else Decimal('0')

        # Check against the aircraft's configured envelope.
        aircraft = validated_data.get('aircraft')
        within_limits = False
        try:
            cfg = aircraft.wb_config
            within_limits = (
                gross_weight <= Decimal(str(cfg.max_gross_weight))
                and gross_cg >= Decimal(str(cfg.fwd_cg_limit))
                and gross_cg <= Decimal(str(cfg.aft_cg_limit))
            )
        except WBConfig.DoesNotExist:
            pass

        return {
            'gross_weight': gross_weight.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
            'gross_moment': gross_moment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'gross_cg': gross_cg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'within_limits': within_limits,
        }

    def create(self, validated_data):
        validated_data.update(self._compute_totals(validated_data))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # PATCH requests may omit fields — fall back to instance values so
        # _compute_totals always has aircraft, empty_weight, and empty_cg.
        merged = {
            'aircraft': instance.aircraft,
            'empty_weight': instance.empty_weight,
            'empty_cg': instance.empty_cg,
            'items': instance.items,
        }
        merged.update(validated_data)
        validated_data.update(self._compute_totals(merged))
        return super().update(instance, validated_data)

from django.contrib import admin
from .models import Aircraft, AircraftNote, AircraftRole, AircraftShareToken


class AircraftRoleInline(admin.TabularInline):
    model = AircraftRole
    extra = 0


class AircraftAdmin(admin.ModelAdmin):
    inlines = [AircraftRoleInline]
    list_display = ('tail_number', 'make', 'model', 'status', 'flight_time')


admin.site.register(Aircraft, AircraftAdmin)
admin.site.register(AircraftNote)
admin.site.register(AircraftRole)


@admin.register(AircraftShareToken)
class AircraftShareTokenAdmin(admin.ModelAdmin):
    list_display = ['aircraft', 'label', 'privilege', 'expires_at', 'created_at']
    list_filter = ['privilege', 'aircraft']
    readonly_fields = ['id', 'token', 'created_at', 'created_by']

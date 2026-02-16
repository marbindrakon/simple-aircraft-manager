from django.contrib import admin
from .models import Aircraft, AircraftNote, AircraftRole


class AircraftRoleInline(admin.TabularInline):
    model = AircraftRole
    extra = 0


class AircraftAdmin(admin.ModelAdmin):
    inlines = [AircraftRoleInline]
    list_display = ('tail_number', 'make', 'model', 'status', 'flight_time')


admin.site.register(Aircraft, AircraftAdmin)
admin.site.register(AircraftNote)
admin.site.register(AircraftRole)

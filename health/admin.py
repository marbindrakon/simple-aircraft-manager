from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(ComponentType)
admin.site.register(Component)
admin.site.register(DocumentImage)
admin.site.register(LogbookEntry)
admin.site.register(Squawk)
admin.site.register(InspectionType)
admin.site.register(AD)
from .models import MajorRepairAlteration

@admin.register(MajorRepairAlteration)
class MajorRepairAlterationAdmin(admin.ModelAdmin):
    list_display = ('title', 'record_type', 'aircraft', 'date_performed', 'component')
    list_filter = ('record_type', 'aircraft')
    search_fields = ('title', 'description', 'stc_number')
admin.site.register(InspectionRecord)
admin.site.register(ADCompliance)
admin.site.register(ConsumableRecord)

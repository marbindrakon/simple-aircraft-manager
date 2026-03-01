from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Aircraft, AircraftNote, AircraftRole, AircraftShareToken, InvitationCode, InvitationCodeAircraftRole, InvitationCodeRedemption


class AircraftRoleInline(admin.TabularInline):
    model = AircraftRole
    extra = 0


class AircraftAdmin(admin.ModelAdmin):
    inlines = [AircraftRoleInline]
    list_display = ('tail_number', 'make', 'model', 'status', 'tach_time')


admin.site.register(Aircraft, AircraftAdmin)
admin.site.register(AircraftNote)
admin.site.register(AircraftRole)


@admin.register(AircraftShareToken)
class AircraftShareTokenAdmin(admin.ModelAdmin):
    list_display = ['aircraft', 'label', 'privilege', 'expires_at', 'created_at']
    list_filter = ['privilege', 'aircraft']
    readonly_fields = ['id', 'token', 'created_at', 'created_by']


class InvitationCodeAircraftRoleInline(admin.TabularInline):
    model = InvitationCodeAircraftRole
    extra = 0


class InvitationCodeRedemptionInline(admin.TabularInline):
    model = InvitationCodeRedemption
    extra = 0
    readonly_fields = ['user', 'redeemed_at']
    can_delete = False


@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    list_display = ['label', 'invited_email', 'use_count', 'max_uses', 'expires_at', 'is_active', 'get_registration_link']
    list_filter = ['is_active']
    readonly_fields = ['id', 'token', 'use_count', 'created_by', 'created_at', 'get_registration_link']
    inlines = [InvitationCodeAircraftRoleInline, InvitationCodeRedemptionInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Registration URL")
    def get_registration_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse('register', args=[obj.token])
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

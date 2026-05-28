from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Tenant, User, Client, EmissionFactor, IngestionBatch, RawRecord, NormalizedActivity, AuditLog


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'tenant', 'role', 'is_staff']
    list_filter = ['role', 'tenant']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Breathe ESG', {'fields': ('tenant', 'role')}),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'reporting_year', 'timezone']
    list_filter = ['tenant', 'reporting_year']


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ['category', 'subcategory', 'region', 'year', 'value', 'unit', 'source']
    list_filter = ['category', 'region', 'year']
    search_fields = ['category', 'subcategory']


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ['client', 'source_type', 'status', 'total_rows', 'ok_rows', 'warn_rows', 'error_rows', 'ingested_at']
    list_filter = ['source_type', 'status', 'client']
    readonly_fields = ['file_hash']


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ['batch', 'row_index', 'parse_status', 'created_at']
    list_filter = ['parse_status']
    readonly_fields = ['raw_data', 'parse_errors']


@admin.register(NormalizedActivity)
class NormalizedActivityAdmin(admin.ModelAdmin):
    list_display = ['category', 'source_type', 'scope', 'activity_date', 'quantity_value', 'quantity_unit', 'quantity_co2e', 'review_status', 'is_locked']
    list_filter = ['scope', 'source_type', 'review_status', 'category', 'is_locked']
    readonly_fields = ['is_locked', 'reviewed_by', 'reviewed_at']
    search_fields = ['description', 'facility_code']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['activity', 'actor', 'action', 'created_at']
    list_filter = ['action']
    readonly_fields = ['activity', 'actor', 'action', 'diff', 'note', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

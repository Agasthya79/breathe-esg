from rest_framework import serializers
from emissions.models import (
    Client, IngestionBatch, RawRecord,
    NormalizedActivity, AuditLog, EmissionFactor
)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name', 'reporting_year', 'timezone', 'created_at']


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = ['id', 'category', 'subcategory', 'region', 'year', 'value', 'unit', 'source']


class IngestionBatchSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    uploaded_by_email = serializers.CharField(source='uploaded_by.email', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'client', 'client_name', 'source_type', 'uploaded_by',
            'uploaded_by_email', 'file_name', 'file_hash', 'status',
            'total_rows', 'ok_rows', 'warn_rows', 'error_rows',
            'error_summary', 'ingested_at',
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'file_hash', 'status', 'total_rows',
            'ok_rows', 'warn_rows', 'error_rows', 'error_summary', 'ingested_at',
        ]


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'batch', 'row_index', 'raw_data', 'parse_status', 'parse_errors', 'created_at']


class NormalizedActivityListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    emission_factor_value = serializers.DecimalField(
        source='emission_factor.value', max_digits=12, decimal_places=6,
        read_only=True, allow_null=True
    )
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True, allow_null=True)
    parse_status = serializers.CharField(source='raw_record.parse_status', read_only=True, allow_null=True)
    parse_errors = serializers.JSONField(source='raw_record.parse_errors', read_only=True, allow_null=True)

    class Meta:
        model = NormalizedActivity
        fields = [
            'id', 'source_type', 'scope', 'category', 'activity_date',
            'facility_code', 'description', 'quantity_value', 'quantity_unit',
            'quantity_co2e', 'emission_factor_value', 'review_status',
            'reviewed_by_email', 'reviewed_at', 'is_locked', 'is_manual_entry',
            'parse_status', 'parse_errors', 'created_at',
        ]


class NormalizedActivitySerializer(serializers.ModelSerializer):
    emission_factor_detail = EmissionFactorSerializer(source='emission_factor', read_only=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True, allow_null=True)
    raw_record_data = RawRecordSerializer(source='raw_record', read_only=True)
    parse_status = serializers.CharField(source='raw_record.parse_status', read_only=True, allow_null=True)
    parse_errors = serializers.JSONField(source='raw_record.parse_errors', read_only=True, allow_null=True)

    class Meta:
        model = NormalizedActivity
        fields = [
            'id', 'client', 'source_type', 'scope', 'category', 'activity_date',
            'facility_code', 'description', 'quantity_value', 'quantity_unit',
            'quantity_co2e', 'emission_factor', 'emission_factor_detail',
            'is_manual_entry', 'manual_note', 'review_status',
            'reviewed_by', 'reviewed_by_email', 'reviewed_at', 'is_locked',
            'raw_record_data', 'parse_status', 'parse_errors',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'client', 'source_type', 'scope', 'review_status',
            'reviewed_by', 'reviewed_at', 'is_locked', 'created_at', 'updated_at',
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source='actor.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'activity', 'actor', 'actor_email', 'action', 'diff', 'note', 'created_at']

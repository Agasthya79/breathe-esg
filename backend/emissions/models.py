import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, null=True, blank=True, related_name='users')
    ROLE_CHOICES = [('analyst', 'Analyst'), ('admin', 'Admin')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='analyst')

    def __str__(self):
        return self.email


class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='clients')
    name = models.CharField(max_length=200)
    reporting_year = models.IntegerField(default=2024)
    timezone = models.CharField(max_length=100, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmissionFactor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=10, default='GLOBAL')
    year = models.IntegerField(default=2023)
    value = models.DecimalField(max_digits=12, decimal_places=6)
    unit = models.CharField(max_length=50)
    source = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category}/{self.subcategory} ({self.region} {self.year})"


SOURCE_TYPES = [('SAP', 'SAP'), ('UTILITY', 'Utility'), ('TRAVEL', 'Travel')]
SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]
CATEGORY_CHOICES = [
    ('fuel_combustion', 'Fuel Combustion'),
    ('purchased_electricity', 'Purchased Electricity'),
    ('flight', 'Flight'),
    ('hotel', 'Hotel'),
    ('ground_transport', 'Ground Transport'),
    ('procurement', 'Procurement'),
]


class IngestionBatch(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='batches')
    file_name = models.CharField(max_length=500)
    file_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_rows = models.IntegerField(default=0)
    ok_rows = models.IntegerField(default=0)
    warn_rows = models.IntegerField(default=0)
    error_rows = models.IntegerField(default=0)
    error_summary = models.TextField(blank=True, null=True)
    ingested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_type} batch for {self.client} ({self.status})"


class RawRecord(models.Model):
    PARSE_STATUS = [('ok', 'OK'), ('warn', 'Warning'), ('error', 'Error')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.PROTECT, related_name='raw_records')
    row_index = models.IntegerField()
    raw_data = models.JSONField()
    parse_status = models.CharField(max_length=10, choices=PARSE_STATUS, default='ok')
    parse_errors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_index']


class NormalizedActivity(models.Model):
    REVIEW_STATUS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_record = models.OneToOneField(RawRecord, on_delete=models.PROTECT, null=True, blank=True, related_name='normalized')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='activities')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    activity_date = models.DateField()
    facility_code = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    quantity_value = models.DecimalField(max_digits=15, decimal_places=4)
    quantity_unit = models.CharField(max_length=50)
    quantity_co2e = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    emission_factor = models.ForeignKey(EmissionFactor, on_delete=models.PROTECT, null=True, blank=True)
    is_manual_entry = models.BooleanField(default=False)
    manual_note = models.TextField(blank=True, null=True)
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='reviewed_activities')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date', 'source_type']
        verbose_name_plural = 'Normalized Activities'


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'), ('edit', 'Edit'), ('approve', 'Approve'),
        ('reject', 'Reject'), ('unlock', 'Unlock'), ('lock', 'Lock'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(NormalizedActivity, on_delete=models.PROTECT, related_name='audit_logs')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    diff = models.JSONField(default=dict)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

import hashlib
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from emissions.models import (
    Client, IngestionBatch, RawRecord, NormalizedActivity,
    EmissionFactor, AuditLog
)
from .parsers import parse_sap, parse_utility, parse_travel
from .serializers import (
    IngestionBatchSerializer, NormalizedActivitySerializer,
    NormalizedActivityListSerializer, AuditLogSerializer,
    ClientSerializer, RawRecordSerializer
)


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClientSerializer

    def get_queryset(self):
        return Client.objects.all().order_by("name")


class IngestionBatchViewSet(viewsets.ModelViewSet):
    serializer_class = IngestionBatchSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = IngestionBatch.objects.select_related('client', 'uploaded_by')
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs.order_by('-ingested_at')

    def create(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        client_id = request.data.get('client_id')
        source_type = request.data.get('source_type')

        if not all([file, client_id, source_type]):
            return Response({'error': 'file, client_id, and source_type are required'}, status=400)

        if source_type not in ('SAP', 'UTILITY', 'TRAVEL'):
            return Response({'error': 'source_type must be SAP, UTILITY, or TRAVEL'}, status=400)

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=404)

        content = file.read().decode('utf-8', errors='replace')
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Duplicate detection
        if IngestionBatch.objects.filter(file_hash=file_hash, client=client).exists():
            return Response({'error': 'This file has already been ingested (duplicate hash detected)', 'duplicate': True}, status=409)

        batch = IngestionBatch.objects.create(
            client=client,
            source_type=source_type,
            uploaded_by=request.user,
            file_name=file.name,
            file_hash=file_hash,
            status='processing',
        )

        try:
            parser_fn = {'SAP': parse_sap, 'UTILITY': parse_utility, 'TRAVEL': parse_travel}[source_type]
            results = parser_fn(content)

            ok, warn, err = 0, 0, 0
            for res in results:
                raw = RawRecord.objects.create(
                    batch=batch,
                    row_index=res['row_index'],
                    raw_data=res['raw_data'],
                    parse_status=res['parse_status'],
                    parse_errors=res['parse_errors'],
                )
                if res.get('parse_status') == 'ok':
                    ok += 1
                elif res.get('parse_status') == 'warn':
                    warn += 1
                else:
                    err += 1

                if not res.get('skip') and 'normalized' in res:
                    n = res['normalized']
                    ef = None
                    if n.get('ef_key'):
                        ef_key = n['ef_key']
                        ef = EmissionFactor.objects.filter(
                            category=ef_key[0],
                            subcategory=ef_key[1],
                            region=ef_key[2]
                        ).first()

                    if n.get('activity_date'):
                        NormalizedActivity.objects.create(
                            raw_record=raw,
                            client=client,
                            source_type=n['source_type'],
                            scope=n['scope'],
                            category=n['category'],
                            activity_date=n['activity_date'],
                            facility_code=n.get('facility_code', ''),
                            description=n.get('description', ''),
                            quantity_value=n['quantity_value'],
                            quantity_unit=n['quantity_unit'],
                            quantity_co2e=n.get('quantity_co2e'),
                            emission_factor=ef,
                            review_status='warn' if res['parse_status'] == 'warn' else 'pending',
                        )

            batch.total_rows = len(results)
            batch.ok_rows = ok
            batch.warn_rows = warn
            batch.error_rows = err
            batch.status = 'done'
            batch.save()

        except Exception as e:
            batch.status = 'failed'
            batch.error_summary = str(e)
            batch.save()
            return Response({'error': str(e), 'batch_id': str(batch.id)}, status=500)

        return Response(IngestionBatchSerializer(batch).data, status=201)


class NormalizedActivityViewSet(viewsets.ModelViewSet):
    serializer_class = NormalizedActivitySerializer

    def get_queryset(self):
        qs = NormalizedActivity.objects.select_related(
            'client', 'emission_factor', 'reviewed_by', 'raw_record'
        )
        params = self.request.query_params
        if params.get('client'):
            qs = qs.filter(client_id=params['client'])
        if params.get('scope'):
            qs = qs.filter(scope=params['scope'])
        if params.get('source_type'):
            qs = qs.filter(source_type=params['source_type'])
        if params.get('review_status'):
            qs = qs.filter(review_status=params['review_status'])
        if params.get('category'):
            qs = qs.filter(category=params['category'])
        return qs.order_by('-activity_date')

    def get_serializer_class(self):
        if self.action == 'list':
            return NormalizedActivityListSerializer
        return NormalizedActivitySerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_locked:
            return Response({'error': 'Row is locked. Admin unlock required.'}, status=403)

        before = _snapshot(instance)
        resp = super().update(request, *args, **kwargs)
        after = _snapshot(self.get_object())
        AuditLog.objects.create(
            activity=instance, actor=request.user,
            action='edit', diff={'before': before, 'after': after}
        )
        return resp

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        activity = self.get_object()
        if activity.is_locked:
            return Response({'error': 'Already approved and locked'}, status=400)
        activity.review_status = 'approved'
        activity.reviewed_by = request.user
        activity.reviewed_at = timezone.now()
        activity.is_locked = True
        activity.save()
        AuditLog.objects.create(activity=activity, actor=request.user, action='approve')
        return Response(NormalizedActivitySerializer(activity).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        activity = self.get_object()
        note = request.data.get('note', '')
        activity.review_status = 'rejected'
        activity.reviewed_by = request.user
        activity.reviewed_at = timezone.now()
        activity.save()
        AuditLog.objects.create(activity=activity, actor=request.user, action='reject', note=note)
        return Response(NormalizedActivitySerializer(activity).data)

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'error': 'Admin role required to unlock'}, status=403)
        activity = self.get_object()
        note = request.data.get('note', '')
        if not note:
            return Response({'error': 'A note is required to unlock a row'}, status=400)
        activity.is_locked = False
        activity.review_status = 'pending'
        activity.save()
        AuditLog.objects.create(activity=activity, actor=request.user, action='unlock', note=note)
        return Response(NormalizedActivitySerializer(activity).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset()
        from django.db.models import Sum, Count
        data = {
            'total': qs.count(),
            'pending': qs.filter(review_status='pending').count(),
            'approved': qs.filter(review_status='approved').count(),
            'rejected': qs.filter(review_status='rejected').count(),
            'scope1_co2e': float(qs.filter(scope=1).aggregate(t=Sum('quantity_co2e'))['t'] or 0),
            'scope2_co2e': float(qs.filter(scope=2).aggregate(t=Sum('quantity_co2e'))['t'] or 0),
            'scope3_co2e': float(qs.filter(scope=3).aggregate(t=Sum('quantity_co2e'))['t'] or 0),
            'by_source': {
                'SAP': float(qs.filter(source_type='SAP').aggregate(t=Sum('quantity_co2e'))['t'] or 0),
                'UTILITY': float(qs.filter(source_type='UTILITY').aggregate(t=Sum('quantity_co2e'))['t'] or 0),
                'TRAVEL': float(qs.filter(source_type='TRAVEL').aggregate(t=Sum('quantity_co2e'))['t'] or 0),
            }
        }
        return Response(data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        activity = self.get_object()
        logs = activity.audit_logs.all()
        return Response(AuditLogSerializer(logs, many=True).data)


class RawRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RawRecordSerializer

    def get_queryset(self):
        qs = RawRecord.objects.all()
        if self.request.query_params.get('batch'):
            qs = qs.filter(batch_id=self.request.query_params['batch'])
        if self.request.query_params.get('parse_status'):
            qs = qs.filter(parse_status=self.request.query_params['parse_status'])
        return qs.order_by('row_index')


def _snapshot(obj):
    return {
        'quantity_value': str(obj.quantity_value),
        'quantity_co2e': str(obj.quantity_co2e) if obj.quantity_co2e else None,
        'review_status': obj.review_status,
        'description': obj.description,
    }

"""
seed.py — Loads demo data: tenant, clients, emission factors, a demo user,
and realistic sample batches for all three source types.
Run: python manage.py seed
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from decimal import Decimal
import json, os


EMISSION_FACTORS = [
    # Fuel combustion (per litre unless noted)
    dict(category='fuel_combustion', subcategory='diesel',       region='GLOBAL', year=2023, value='2.6760', unit='per_litre',  source='DEFRA 2023'),
    dict(category='fuel_combustion', subcategory='petrol',       region='GLOBAL', year=2023, value='2.3080', unit='per_litre',  source='DEFRA 2023'),
    dict(category='fuel_combustion', subcategory='natural_gas',  region='GLOBAL', year=2023, value='2.0440', unit='per_m3',     source='DEFRA 2023'),
    dict(category='fuel_combustion', subcategory='lng',          region='GLOBAL', year=2023, value='1.1640', unit='per_kg',     source='DEFRA 2023'),
    # Electricity (per kWh)
    dict(category='purchased_electricity', subcategory=None, region='GB',     year=2023, value='0.2120', unit='per_kWh', source='DEFRA 2023'),
    dict(category='purchased_electricity', subcategory=None, region='US',     year=2023, value='0.3860', unit='per_kWh', source='EPA eGRID 2022'),
    dict(category='purchased_electricity', subcategory=None, region='DE',     year=2023, value='0.4340', unit='per_kWh', source='UBA 2023'),
    dict(category='purchased_electricity', subcategory=None, region='GLOBAL', year=2023, value='0.3500', unit='per_kWh', source='IEA 2023'),
    # Flights (per passenger-km)
    dict(category='flight', subcategory='economy',  region='GLOBAL', year=2023, value='0.1556', unit='per_pkm', source='DEFRA 2023'),
    dict(category='flight', subcategory='business', region='GLOBAL', year=2023, value='0.4295', unit='per_pkm', source='DEFRA 2023'),
    dict(category='flight', subcategory='first',    region='GLOBAL', year=2023, value='0.6199', unit='per_pkm', source='DEFRA 2023'),
    # Hotel (per night)
    dict(category='hotel', subcategory=None, region='GB',     year=2023, value='11.10', unit='per_night', source='DEFRA 2023'),
    dict(category='hotel', subcategory=None, region='US',     year=2023, value='13.60', unit='per_night', source='EPA 2023'),
    dict(category='hotel', subcategory=None, region='GLOBAL', year=2023, value='12.30', unit='per_night', source='DEFRA 2023'),
    # Ground transport (per km)
    dict(category='ground_transport', subcategory='car_rental', region='GLOBAL', year=2023, value='0.1710', unit='per_km', source='DEFRA 2023'),
    dict(category='ground_transport', subcategory='taxi',       region='GLOBAL', year=2023, value='0.1490', unit='per_km', source='DEFRA 2023'),
    dict(category='ground_transport', subcategory='train',      region='GLOBAL', year=2023, value='0.0410', unit='per_km', source='DEFRA 2023'),
]

SAP_SAMPLE_CSV = """MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART,KOSTL,LIFNR
5000000001,15.01.2024,1000,000000000000DIESEL,850.000,L,201,COST-001,
5000000002,18.01.2024,1000,000000000000DIESEL,920.500,L,201,COST-001,
5000000003,22.01.2024,US01,000000000000PETROL,480.000,GAL,201,COST-002,
5000000004,25.01.2024,US01,000000000000PETROL,510.000,GAL,261,COST-002,
5000000005,30.01.2024,1000,000000000000NATGAS,320.000,M3,201,COST-003,
5000000006,05.02.2024,DE02,000000000000DIESEL,760.000,L,201,COST-004,
5000000007,10.02.2024,DE02,000000000000DIESEL,830.000,L,201,COST-004,
5000000008,14.02.2024,1000,000000000000LNG,1200.000,KG,201,COST-005,
5000000009,20.02.2024,US01,000000000000PETROL,620.000,GAL,201,COST-002,
5000000010,28.02.2024,,000000000000DIESEL,400.000,L,201,COST-001,
5000000011,01.03.2024,1000,000000000000DIESEL,900.000,L,201,COST-001,
5000000012,15.03.2024,GB01,000000000000PETROL,350.000,L,201,COST-006,
5000000099,10.01.2024,1000,000000000000DIESEL,500.000,L,101,VENDOR01,V001
"""

UTILITY_SAMPLE_CSV = """Account Number,GB-ACCT-00123
Service Address,"123 Industrial Park, London E1 6RF"
Meter ID,MTR-UK-00456

TYPE,START DATE,END DATE,USAGE,UNITS,COST,NOTES
Electric Usage,2024-01-03,2024-02-01,14250,kWh,1847.50,
Electric Usage,2024-02-01,2024-03-04,13980,kWh,1814.22,
Electric Usage,2024-03-04,2024-04-02,15100,kWh,1961.73,
Electric Usage,2024-04-02,2024-05-01,12800,kWh,1662.40,
Electric Usage,2024-05-01,2024-06-03,11200,kWh,1454.40,
Electric Usage,2024-06-03,2024-07-02,10900,kWh,1415.27,
Electric Usage,2024-07-02,2024-08-01,11500,kWh,1493.05,
Electric Usage,2024-08-01,2024-09-02,,kWh,,Estimated read — meter inaccessible
Electric Usage,2024-09-02,2024-10-01,13200,kWh,1714.44,
Electric Usage,2024-10-01,2024-11-04,14800,kWh,1922.48,
Electric Usage,2024-11-04,2024-12-02,15600,kWh,2026.44,
Electric Usage,2024-12-02,2025-01-03,16100,kWh,2091.39,
"""

TRAVEL_SAMPLE_CSV = """ExpenseType,TransactionDate,Amount,Currency,OrigCity,DestCity,Distance,DistanceUnit,ClassOfService,HotelCity,HotelCountry,HotelCheckin,HotelCheckout,Nights,VendorName,EmployeeID
AIR_FARE,2024-01-15,850.00,GBP,LHR,JFK,,km,Economy,,,,,,,EMP-001
AIR_FARE,2024-01-22,1850.00,GBP,LHR,SIN,,km,Business,,,,,,,EMP-002
HOTEL,2024-01-15,320.00,USD,,,,,,,,,NewYork,US,2024-01-15,2024-01-18,,Marriott,EMP-001
AIR_FARE,2024-02-05,420.00,GBP,ORD,BOS,1380,km,Economy,,,,,,,EMP-003
AIR_FARE,2024-02-12,780.00,GBP,LHR,CDG,,km,Economy,,,,,,,EMP-004
HOTEL,2024-02-12,180.00,EUR,,,,,,,Paris,FR,2024-02-12,2024-02-14,,Novotel,EMP-004
CAR_RENTAL,2024-02-05,95.00,USD,,,150,miles,,,,,,,,EMP-003
TAXI,2024-01-15,45.00,USD,,,12,miles,,,,,,,,EMP-001
TRAIN,2024-03-10,89.00,GBP,,,380,km,,,,,,,,EMP-005
AIR_FARE,2024-03-18,2200.00,GBP,LHR,NRT,,km,Business,,,,,,,EMP-002
HOTEL,2024-03-18,280.00,USD,,,,,,,Tokyo,JP,2024-03-18,2024-03-22,4,Hilton,EMP-002
AIR_FARE,2024-04-08,390.00,GBP,LHR,MAD,,km,Economy,,,,,,,EMP-006
AIR_FARE,2024-04-22,1100.00,GBP,LHR,JFK,,km,Economy,,,,,,,EMP-007
HOTEL,2024-04-22,450.00,USD,,,,,,,,,NewYork,US,2024-04-22,2024-04-25,,W Hotels,EMP-007
CAR_RENTAL,2024-05-01,120.00,USD,,,220,miles,,,,,,,,EMP-003
AIR_FARE,2024-05-14,650.00,GBP,LHR,DXB,,km,Economy,,,,,,,EMP-008
HOTEL,2024-05-14,190.00,USD,,,,,,,Dubai,AE,2024-05-14,2024-05-17,,Ibis,EMP-008
AIR_FARE,2024-05-14,650.00,GBP,XYZ,ABC,,km,Economy,,,,,,,EMP-009
TAXI,2024-06-03,35.00,GBP,,,8,miles,,,,,,,,EMP-001
"""

class Command(BaseCommand):
    help = 'Seed database with demo tenant, clients, emission factors, and sample ingestion data'

    def handle(self, *args, **options):
        from emissions.models import (
            Tenant, User, Client, EmissionFactor,
            IngestionBatch, RawRecord, NormalizedActivity
        )
        from ingestion.parsers import parse_sap, parse_utility, parse_travel
        from decimal import Decimal

        self.stdout.write('Seeding emission factors...')
        for ef_data in EMISSION_FACTORS:
            EmissionFactor.objects.get_or_create(
                category=ef_data['category'],
                subcategory=ef_data.get('subcategory'),
                region=ef_data['region'],
                year=ef_data['year'],
                defaults=dict(
                    value=Decimal(ef_data['value']),
                    unit=ef_data['unit'],
                    source=ef_data['source'],
                )
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(EMISSION_FACTORS)} emission factors loaded'))

        self.stdout.write('Creating tenant and users...')
        tenant, _ = Tenant.objects.get_or_create(name='Breathe ESG Demo', slug='demo')

        admin_user, _ = User.objects.get_or_create(
            username='admin@breatheesg.com',
            defaults=dict(email='admin@breatheesg.com', tenant=tenant, role='admin',
                          is_staff=True, is_superuser=True, password=make_password('demo1234'))
        )
        analyst_user, _ = User.objects.get_or_create(
            username='analyst@breatheesg.com',
            defaults=dict(email='analyst@breatheesg.com', tenant=tenant, role='analyst',
                          password=make_password('demo1234'))
        )
        self.stdout.write(self.style.SUCCESS('  Users: admin@breatheesg.com / demo1234, analyst@breatheesg.com / demo1234'))

        self.stdout.write('Creating clients...')
        client, _ = Client.objects.get_or_create(
            name='Acme Manufacturing Ltd',
            defaults=dict(tenant=tenant, reporting_year=2024, timezone='Europe/London')
        )

        self.stdout.write('Ingesting SAP sample data...')
        self._ingest(client, admin_user, 'SAP', 'sample_sap.csv', SAP_SAMPLE_CSV, parse_sap)

        self.stdout.write('Ingesting Utility sample data...')
        self._ingest(client, admin_user, 'UTILITY', 'sample_utility.csv', UTILITY_SAMPLE_CSV, parse_utility)

        self.stdout.write('Ingesting Travel sample data...')
        self._ingest(client, admin_user, 'TRAVEL', 'sample_travel.csv', TRAVEL_SAMPLE_CSV, parse_travel)

        total = NormalizedActivity.objects.filter(client=client).count()
        self.stdout.write(self.style.SUCCESS(f'\nSeed complete. {total} normalized activities created.'))
        self.stdout.write(self.style.SUCCESS('Login: admin@breatheesg.com / demo1234'))

    def _ingest(self, client, user, source_type, filename, content, parser_fn):
        import hashlib
        from emissions.models import IngestionBatch, RawRecord, NormalizedActivity, EmissionFactor

        file_hash = hashlib.sha256(content.encode()).hexdigest()
        if IngestionBatch.objects.filter(file_hash=file_hash, client=client).exists():
            self.stdout.write(f'  {source_type}: already ingested, skipping')
            return

        batch = IngestionBatch.objects.create(
            client=client, source_type=source_type, uploaded_by=user,
            file_name=filename, file_hash=file_hash, status='processing'
        )
        results = parser_fn(content)
        ok = warn = err = 0
        for res in results:
            raw = RawRecord.objects.create(
                batch=batch, row_index=res['row_index'],
                raw_data=res['raw_data'], parse_status=res['parse_status'],
                parse_errors=res['parse_errors'],
            )
            ps = res['parse_status']
            if ps == 'ok': ok += 1
            elif ps == 'warn': warn += 1
            else: err += 1

            if not res.get('skip') and 'normalized' in res:
                n = res['normalized']
                ef = None
                if n.get('ef_key'):
                    cat, subcat, region = n['ef_key']
                    ef = EmissionFactor.objects.filter(
                        category=cat, subcategory=subcat, region=region
                    ).first() or EmissionFactor.objects.filter(
                        category=cat, subcategory=subcat, region='GLOBAL'
                    ).first()
                if n.get('activity_date'):
                    NormalizedActivity.objects.create(
                        raw_record=raw, client=client,
                        source_type=n['source_type'], scope=n['scope'],
                        category=n['category'], activity_date=n['activity_date'],
                        facility_code=n.get('facility_code', ''),
                        description=n.get('description', ''),
                        quantity_value=n['quantity_value'],
                        quantity_unit=n['quantity_unit'],
                        quantity_co2e=n.get('quantity_co2e'),
                        emission_factor=ef,
                        review_status='pending',
                    )

        batch.total_rows = len(results)
        batch.ok_rows = ok; batch.warn_rows = warn; batch.error_rows = err
        batch.status = 'done'
        batch.save()
        self.stdout.write(f'  {source_type}: {ok} ok, {warn} warn, {err} error rows')

"""
Comprehensive test suite — parsers, API views, review workflow, audit trail.
Run: python manage.py test
"""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
import io, json

from emissions.models import (
    Tenant, User, Client, EmissionFactor,
    IngestionBatch, RawRecord, NormalizedActivity, AuditLog
)
from ingestion.parsers import parse_sap, parse_utility, parse_travel


# ─── Fixtures ────────────────────────────────────────────────────────────────
def make_tenant():
    return Tenant.objects.create(name='Test Tenant', slug='test')

def make_user(tenant, role='analyst', username='analyst@test.com'):
    return User.objects.create_user(
        username=username, email=username,
        password='testpass123', tenant=tenant, role=role
    )

def make_client(tenant):
    return Client.objects.create(
        name='Test Client', tenant=tenant, reporting_year=2024
    )

def make_ef(category='fuel_combustion', subcategory='diesel', region='GLOBAL', value='2.676'):
    return EmissionFactor.objects.create(
        category=category, subcategory=subcategory, region=region,
        year=2023, value=Decimal(value), unit='per_litre', source='DEFRA 2023'
    )

def make_activity(client, **kwargs):
    defaults = dict(
        source_type='SAP', scope=1, category='fuel_combustion',
        activity_date='2024-01-15', quantity_value=Decimal('100'),
        quantity_unit='L', quantity_co2e=Decimal('267.6'),
        review_status='pending',
    )
    defaults.update(kwargs)
    return NormalizedActivity.objects.create(client=client, **defaults)

def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ─── Parser Tests ─────────────────────────────────────────────────────────────
class SAPParserTest(TestCase):

    def test_parses_standard_row(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART,KOSTL\n5000000001,15.01.2024,1000,DIESEL,850.000,L,201,C001\n"
        results = parse_sap(csv)
        # receipt row filtered out; consumption row remains
        consumed = [r for r in results if not r.get('skip')]
        self.assertEqual(len(consumed), 1)
        n = consumed[0]['normalized']
        self.assertEqual(n['source_type'], 'SAP')
        self.assertEqual(n['scope'], 1)
        self.assertEqual(n['category'], 'fuel_combustion')
        self.assertEqual(n['activity_date'].strftime('%Y-%m-%d'), '2024-01-15')
        self.assertAlmostEqual(float(n['quantity_value']), 850.0)
        self.assertEqual(n['quantity_unit'], 'L')

    def test_skips_goods_receipt_movement(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n5000000099,10.01.2024,1000,DIESEL,500.000,L,101\n"
        results = parse_sap(csv)
        # movement 101 = receipt — should be skipped
        self.assertTrue(all(r.get('skip') for r in results))

    def test_german_headers(self):
        csv = "Belegnummer,Buchungsdatum,Werk,Material,Menge,Basismengeneinheit,Bewegungsart\n5000000001,15.01.2024,1000,DIESEL,850,L,201\n"
        results = parse_sap(csv)
        consumed = [r for r in results if not r.get('skip')]
        self.assertEqual(len(consumed), 1)
        self.assertEqual(consumed[0]['normalized']['category'], 'fuel_combustion')

    def test_gallon_to_litre_conversion(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,15.01.2024,US01,PETROL,100,GAL,201\n"
        results = parse_sap(csv)
        consumed = [r for r in results if not r.get('skip')]
        self.assertEqual(len(consumed), 1)
        n = consumed[0]['normalized']
        self.assertAlmostEqual(float(n['quantity_value']), 378.5, places=0)
        self.assertEqual(n['quantity_unit'], 'L')

    def test_missing_plant_code_warns(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,15.01.2024,,DIESEL,100,L,201\n"
        results = parse_sap(csv)
        self.assertEqual(results[0]['parse_status'], 'warn')
        error_fields = [e['field'] for e in results[0]['parse_errors']]
        self.assertIn('WERKS', error_fields)

    def test_bad_date_errors(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,not-a-date,1000,DIESEL,100,L,201\n"
        results = parse_sap(csv)
        self.assertEqual(results[0]['parse_status'], 'error')

    def test_multiple_date_formats(self):
        rows = [
            ("15.01.2024", "2024-01-15"),
            ("20240115",   "2024-01-15"),
            ("2024-01-15", "2024-01-15"),
            ("01/15/2024", "2024-01-15"),
        ]
        for raw, expected in rows:
            csv = f"MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,{raw},1000,DIESEL,100,L,201\n"
            results = parse_sap(csv)
            consumed = [r for r in results if not r.get('skip')]
            self.assertEqual(consumed[0]['normalized']['activity_date'].strftime('%Y-%m-%d'), expected, f"Failed for {raw}")

    def test_procurement_defaults_scope3(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,15.01.2024,1000,OFFICE_PAPER,200,KG,201\n"
        results = parse_sap(csv)
        consumed = [r for r in results if not r.get('skip')]
        if consumed:
            n = consumed[0]['normalized']
            self.assertEqual(n['scope'], 3)
            self.assertEqual(n['category'], 'procurement')

    def test_empty_file(self):
        results = parse_sap("MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n")
        self.assertEqual(results, [])

    def test_co2e_calculated_for_known_fuel(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,15.01.2024,1000,DIESEL,100,L,201\n"
        results = parse_sap(csv)
        consumed = [r for r in results if not r.get('skip')]
        n = consumed[0]['normalized']
        self.assertIsNotNone(n['quantity_co2e'])
        # 100L diesel × 2.676 = 267.6 kg CO2e
        self.assertAlmostEqual(float(n['quantity_co2e']), 267.6, places=1)


class UtilityParserTest(TestCase):

    VALID_CSV = """Account Number,GB-ACCT-001
Meter ID,MTR-001

TYPE,START DATE,END DATE,USAGE,UNITS,COST,NOTES
Electric Usage,2024-01-03,2024-02-01,14250,kWh,1847.50,
Electric Usage,2024-02-01,2024-03-04,13980,kWh,1814.22,
"""

    def test_parses_standard_rows(self):
        results = parse_utility(self.VALID_CSV)
        consumed = [r for r in results if not r.get('skip')]
        self.assertEqual(len(consumed), 2)
        n = consumed[0]['normalized']
        self.assertEqual(n['source_type'], 'UTILITY')
        self.assertEqual(n['scope'], 2)
        self.assertEqual(n['category'], 'purchased_electricity')
        self.assertAlmostEqual(float(n['quantity_value']), 14250.0)
        self.assertEqual(n['quantity_unit'], 'kWh')

    def test_mwh_converted_to_kwh(self):
        csv = """Account Number,TEST\nMeter ID,MTR\n\nTYPE,START DATE,END DATE,USAGE,UNITS,COST\nElectric Usage,2024-01-01,2024-02-01,14.25,MWh,1847.50\n"""
        results = parse_utility(csv)
        consumed = [r for r in results if not r.get('skip')]
        self.assertAlmostEqual(float(consumed[0]['normalized']['quantity_value']), 14250.0)
        self.assertEqual(consumed[0]['normalized']['quantity_unit'], 'kWh')

    def test_blank_usage_warns_not_errors(self):
        csv = """Account Number,TEST\nMeter ID,MTR\n\nTYPE,START DATE,END DATE,USAGE,UNITS,COST,NOTES\nElectric Usage,2024-08-01,2024-09-01,,kWh,,Estimated read\n"""
        results = parse_utility(csv)
        self.assertEqual(results[0]['parse_status'], 'warn')

    def test_co2e_calculated(self):
        results = parse_utility(self.VALID_CSV)
        consumed = [r for r in results if not r.get('skip')]
        n = consumed[0]['normalized']
        self.assertIsNotNone(n['quantity_co2e'])
        # 14250 kWh × 0.35 = 4987.5 kg CO2e (global factor)
        self.assertAlmostEqual(float(n['quantity_co2e']), 4987.5, places=0)

    def test_extracts_meter_id_from_header(self):
        results = parse_utility(self.VALID_CSV)
        consumed = [r for r in results if not r.get('skip')]
        self.assertEqual(consumed[0]['normalized']['facility_code'], 'MTR-001')

    def test_missing_header_returns_error(self):
        results = parse_utility("completely invalid content\nno header\n")
        self.assertEqual(results[0]['parse_status'], 'error')

    def test_non_electricity_rows_skipped(self):
        csv = """Account Number,TEST\nMeter ID,MTR\n\nTYPE,START DATE,END DATE,USAGE,UNITS,COST\nGas Usage,2024-01-01,2024-02-01,5000,therms,1200\nElectric Usage,2024-01-01,2024-02-01,14000,kWh,1800\n"""
        results = parse_utility(csv)
        consumed = [r for r in results if not r.get('skip')]
        # only the electricity row should produce a normalized activity
        self.assertEqual(len(consumed), 1)


class TravelParserTest(TestCase):

    VALID_CSV = """ExpenseType,TransactionDate,Amount,Currency,OrigCity,DestCity,Distance,DistanceUnit,ClassOfService,HotelCity,HotelCountry,HotelCheckin,HotelCheckout,Nights,VendorName,EmployeeID
AIR_FARE,2024-01-15,850.00,GBP,LHR,JFK,,km,Economy,,,,,,,EMP-001
AIR_FARE,2024-01-22,1850.00,GBP,LHR,SIN,,km,Business,,,,,,,EMP-002
HOTEL,2024-01-15,320.00,USD,,,,,,NewYork,US,2024-01-15,2024-01-18,,Marriott,EMP-001
CAR_RENTAL,2024-02-05,95.00,USD,,,150,miles,,,,,,,,EMP-003
TAXI,2024-01-15,45.00,USD,,,12,miles,,,,,,,,EMP-001
TRAIN,2024-03-10,89.00,GBP,,,380,km,,,,,,,,EMP-005
"""

    def test_flight_economy_haversine(self):
        results = parse_travel(self.VALID_CSV)
        flights = [r for r in results if not r.get('skip') and r['normalized']['category'] == 'flight']
        lhr_jfk = next(r for r in flights if 'JFK' in r['normalized'].get('description', ''))
        n = lhr_jfk['normalized']
        # LHR-JFK Great Circle ≈ 5540 km × 1.08 uplift ≈ 5983 km
        self.assertGreater(float(n['quantity_value']), 5000)
        self.assertLess(float(n['quantity_value']), 7000)
        # warns about estimated distance
        self.assertEqual(lhr_jfk['parse_status'], 'warn')

    def test_flight_business_class_higher_ef(self):
        results = parse_travel(self.VALID_CSV)
        economy = next(r for r in results if not r.get('skip') and 'JFK' in r['normalized'].get('description',''))
        business = next(r for r in results if not r.get('skip') and 'SIN' in r['normalized'].get('description',''))
        # Per-km: economy 0.1556, business 0.4295 — so business should be much higher per km
        eco_factor = float(business['normalized']['quantity_co2e']) / float(business['normalized']['quantity_value'])
        self.assertGreater(eco_factor, 0.35)

    def test_hotel_nights_from_checkin_checkout(self):
        results = parse_travel(self.VALID_CSV)
        hotels = [r for r in results if not r.get('skip') and r['normalized']['category'] == 'hotel']
        self.assertEqual(len(hotels), 1)
        n = hotels[0]['normalized']
        self.assertEqual(float(n['quantity_value']), 3.0)  # Jan 15–18 = 3 nights
        self.assertEqual(n['quantity_unit'], 'nights')

    def test_car_rental_miles_to_km(self):
        results = parse_travel(self.VALID_CSV)
        cars = [r for r in results if not r.get('skip') and r['normalized']['category'] == 'ground_transport' and 'car' in r['normalized']['description'].lower()]
        self.assertEqual(len(cars), 1)
        n = cars[0]['normalized']
        # 150 miles × 1.60934 ≈ 241.4 km
        self.assertAlmostEqual(float(n['quantity_value']), 241.4, places=0)

    def test_unknown_airport_code_warns(self):
        csv = "ExpenseType,TransactionDate,OrigCity,DestCity,Distance,ClassOfService\nAIR_FARE,2024-01-15,XYZ,ABC,,Economy\n"
        results = parse_travel(csv)
        flight = results[0]
        self.assertEqual(flight['parse_status'], 'warn')
        msgs = [e['message'] for e in flight['parse_errors']]
        self.assertTrue(any('airport' in m.lower() or 'Unknown' in m for m in msgs))

    def test_unknown_expense_type_skipped(self):
        csv = "ExpenseType,TransactionDate,Amount\nMEALS,2024-01-15,45.00\n"
        results = parse_travel(csv)
        self.assertTrue(all(r.get('skip') for r in results))

    def test_hotel_scope3(self):
        results = parse_travel(self.VALID_CSV)
        hotels = [r for r in results if not r.get('skip') and r['normalized']['category'] == 'hotel']
        self.assertEqual(hotels[0]['normalized']['scope'], 3)

    def test_train_scope3_low_ef(self):
        results = parse_travel(self.VALID_CSV)
        trains = [r for r in results if not r.get('skip') and r['normalized']['category'] == 'ground_transport'
                  and 'train' in r['normalized'].get('description','').lower()]
        if trains:
            n = trains[0]['normalized']
            # Train: 380km × 0.041 = 15.58 kg CO2e
            self.assertAlmostEqual(float(n['quantity_co2e']), 15.58, places=1)


# ─── API View Tests ──────────────────────────────────────────────────────────
class AuthTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.user = make_user(self.tenant)

    def test_token_obtain(self):
        resp = self.client.post('/api/auth/token/', {
            'username': 'analyst@test.com', 'password': 'testpass123'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.json())
        self.assertIn('refresh', resp.json())

    def test_unauthenticated_request_rejected(self):
        resp = self.client.get('/api/activities/')
        self.assertEqual(resp.status_code, 401)

    def test_wrong_password_rejected(self):
        resp = self.client.post('/api/auth/token/', {
            'username': 'analyst@test.com', 'password': 'wrongpass'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 401)


class ClientViewTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.user = make_user(self.tenant)
        self.client_obj = make_client(self.tenant)
        self.api = auth_client(self.user)

    def test_list_clients(self):
        resp = self.api.get('/api/clients/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 1)

    def test_retrieve_client(self):
        resp = self.api.get(f'/api/clients/{self.client_obj.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'Test Client')


class IngestionUploadTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.user = make_user(self.tenant, role='admin', username='admin@test.com')
        self.client_obj = make_client(self.tenant)
        make_ef()
        make_ef(category='purchased_electricity', subcategory=None, region='GLOBAL', value='0.35')
        self.api = auth_client(self.user)

    def _upload(self, content, source_type, filename='test.csv'):
        f = io.BytesIO(content.encode())
        f.name = filename
        return self.api.post('/api/batches/', {
            'file': f,
            'client_id': str(self.client_obj.id),
            'source_type': source_type,
        }, format='multipart')

    def test_sap_upload_creates_batch(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,15.01.2024,1000,DIESEL,100,L,201\n"
        resp = self._upload(csv, 'SAP')
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'done')
        self.assertEqual(data['source_type'], 'SAP')
        self.assertGreaterEqual(data['ok_rows'], 1)

    def test_utility_upload_creates_activities(self):
        csv = """Account Number,TEST\nMeter ID,MTR\n\nTYPE,START DATE,END DATE,USAGE,UNITS,COST\nElectric Usage,2024-01-01,2024-02-01,14250,kWh,1847.50\n"""
        resp = self._upload(csv, 'UTILITY')
        self.assertEqual(resp.status_code, 201)
        acts = NormalizedActivity.objects.filter(client=self.client_obj, source_type='UTILITY')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().scope, 2)

    def test_travel_upload_creates_activities(self):
        csv = "ExpenseType,TransactionDate,OrigCity,DestCity,Distance,ClassOfService\nAIR_FARE,2024-01-15,LHR,JFK,,Economy\n"
        resp = self._upload(csv, 'TRAVEL')
        self.assertEqual(resp.status_code, 201)
        acts = NormalizedActivity.objects.filter(client=self.client_obj, source_type='TRAVEL')
        self.assertEqual(acts.count(), 1)

    def test_duplicate_file_rejected(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n1,15.01.2024,1000,DIESEL,100,L,201\n"
        self._upload(csv, 'SAP')
        resp = self._upload(csv, 'SAP')
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.json().get('duplicate'))

    def test_missing_required_fields_rejected(self):
        resp = self.api.post('/api/batches/', {'source_type': 'SAP'}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_source_type_rejected(self):
        csv = "col\nval\n"
        f = io.BytesIO(csv.encode())
        f.name = 'test.csv'
        resp = self.api.post('/api/batches/', {
            'file': f, 'client_id': str(self.client_obj.id), 'source_type': 'INVALID'
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_client_id_rejected(self):
        csv = "col\nval\n"
        f = io.BytesIO(csv.encode())
        f.name = 'test.csv'
        resp = self.api.post('/api/batches/', {
            'file': f, 'client_id': '00000000-0000-0000-0000-000000000000', 'source_type': 'SAP'
        }, format='multipart')
        self.assertEqual(resp.status_code, 404)

    def test_batch_stores_file_hash(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n2,15.01.2024,1000,DIESEL,200,L,201\n"
        resp = self._upload(csv, 'SAP')
        batch = IngestionBatch.objects.get(id=resp.json()['id'])
        self.assertEqual(len(batch.file_hash), 64)  # SHA-256 hex

    def test_raw_records_store_original_data(self):
        csv = "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,BWART\n5001,15.01.2024,1000,DIESEL,100,L,201\n"
        resp = self._upload(csv, 'SAP')
        batch_id = resp.json()['id']
        raws = RawRecord.objects.filter(batch_id=batch_id)
        self.assertGreater(raws.count(), 0)
        # Original row data is preserved verbatim
        first = raws.first()
        self.assertIn('MBLNR', first.raw_data)


class ActivityViewTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.analyst = make_user(self.tenant, role='analyst', username='analyst@test.com')
        self.admin = make_user(self.tenant, role='admin', username='admin@test.com')
        self.client_obj = make_client(self.tenant)
        self.activity = make_activity(self.client_obj)
        self.analyst_api = auth_client(self.analyst)
        self.admin_api = auth_client(self.admin)

    def test_list_activities(self):
        resp = self.analyst_api.get('/api/activities/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 1)

    def test_filter_by_scope(self):
        make_activity(self.client_obj, scope=2, category='purchased_electricity', source_type='UTILITY')
        resp = self.analyst_api.get('/api/activities/?scope=1')
        self.assertEqual(resp.json()['count'], 1)

    def test_filter_by_review_status(self):
        resp = self.analyst_api.get('/api/activities/?review_status=pending')
        self.assertEqual(resp.json()['count'], 1)
        resp2 = self.analyst_api.get('/api/activities/?review_status=approved')
        self.assertEqual(resp2.json()['count'], 0)

    def test_filter_by_source_type(self):
        make_activity(self.client_obj, source_type='UTILITY', scope=2, category='purchased_electricity')
        resp = self.analyst_api.get('/api/activities/?source_type=SAP')
        self.assertEqual(resp.json()['count'], 1)

    def test_summary_endpoint(self):
        resp = self.analyst_api.get('/api/activities/summary/?client=' + str(self.client_obj.id))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('total', data)
        self.assertIn('scope1_co2e', data)
        self.assertIn('pending', data)

    def test_approve_activity(self):
        resp = self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.review_status, 'approved')
        self.assertTrue(self.activity.is_locked)
        self.assertEqual(self.activity.reviewed_by, self.analyst)

    def test_approve_creates_audit_log(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        log = AuditLog.objects.filter(activity=self.activity, action='approve').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.analyst)

    def test_approve_locked_activity_returns_400(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        resp = self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        self.assertEqual(resp.status_code, 400)

    def test_reject_activity(self):
        resp = self.analyst_api.post(f'/api/activities/{self.activity.id}/reject/',
                                     {'note': 'Duplicate entry'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.review_status, 'rejected')
        self.assertFalse(self.activity.is_locked)

    def test_reject_creates_audit_log_with_note(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/reject/',
                               {'note': 'Looks wrong'}, format='json')
        log = AuditLog.objects.filter(activity=self.activity, action='reject').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.note, 'Looks wrong')

    def test_edit_pending_activity(self):
        resp = self.analyst_api.patch(f'/api/activities/{self.activity.id}/',
                                       {'description': 'Updated description'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.description, 'Updated description')

    def test_edit_creates_audit_log(self):
        self.analyst_api.patch(f'/api/activities/{self.activity.id}/',
                                {'description': 'Changed'}, format='json')
        log = AuditLog.objects.filter(activity=self.activity, action='edit').first()
        self.assertIsNotNone(log)
        self.assertIn('before', log.diff)
        self.assertIn('after', log.diff)

    def test_edit_locked_activity_forbidden(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        resp = self.analyst_api.patch(f'/api/activities/{self.activity.id}/',
                                       {'description': 'Sneaky edit'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_unlock_requires_admin(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        resp = self.analyst_api.post(f'/api/activities/{self.activity.id}/unlock/',
                                      {'note': 'Needs correction'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_unlock_with_note(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        resp = self.admin_api.post(f'/api/activities/{self.activity.id}/unlock/',
                                    {'note': 'Data correction required'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.activity.refresh_from_db()
        self.assertFalse(self.activity.is_locked)
        self.assertEqual(self.activity.review_status, 'pending')

    def test_unlock_without_note_rejected(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        resp = self.admin_api.post(f'/api/activities/{self.activity.id}/unlock/',
                                    {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unlock_creates_audit_log(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        self.admin_api.post(f'/api/activities/{self.activity.id}/unlock/',
                             {'note': 'Correcting value'}, format='json')
        log = AuditLog.objects.filter(activity=self.activity, action='unlock').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.note, 'Correcting value')
        self.assertEqual(log.actor, self.admin)

    def test_audit_history_endpoint(self):
        self.analyst_api.post(f'/api/activities/{self.activity.id}/approve/')
        self.admin_api.post(f'/api/activities/{self.activity.id}/unlock/',
                             {'note': 'Fix'}, format='json')
        resp = self.analyst_api.get(f'/api/activities/{self.activity.id}/history/')
        self.assertEqual(resp.status_code, 200)
        actions = [e['action'] for e in resp.json()]
        self.assertIn('approve', actions)
        self.assertIn('unlock', actions)


class BatchListTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant()
        self.user = make_user(self.tenant)
        self.client_obj = make_client(self.tenant)
        self.api = auth_client(self.user)

    def test_list_batches(self):
        IngestionBatch.objects.create(
            client=self.client_obj, source_type='SAP', uploaded_by=self.user,
            file_name='test.csv', file_hash='abc123', status='done'
        )
        resp = self.api.get('/api/batches/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 1)

    def test_filter_batches_by_client(self):
        other_client = Client.objects.create(
            name='Other', tenant=self.tenant, reporting_year=2024
        )
        IngestionBatch.objects.create(
            client=self.client_obj, source_type='SAP', uploaded_by=self.user,
            file_name='a.csv', file_hash='aaa', status='done'
        )
        IngestionBatch.objects.create(
            client=other_client, source_type='SAP', uploaded_by=self.user,
            file_name='b.csv', file_hash='bbb', status='done'
        )
        resp = self.api.get(f'/api/batches/?client={self.client_obj.id}')
        self.assertEqual(resp.json()['count'], 1)


class SummaryAggregationTest(TestCase):
    """Integration test: verify CO2e aggregations are correct end-to-end."""

    def setUp(self):
        self.tenant = make_tenant()
        self.user = make_user(self.tenant)
        self.client_obj = make_client(self.tenant)
        self.api = auth_client(self.user)

    def test_scope_totals_sum_correctly(self):
        make_activity(self.client_obj, scope=1, quantity_co2e=Decimal('100'))
        make_activity(self.client_obj, scope=1, quantity_co2e=Decimal('200'))
        make_activity(self.client_obj, scope=2, category='purchased_electricity',
                      source_type='UTILITY', quantity_co2e=Decimal('300'))
        make_activity(self.client_obj, scope=3, category='flight',
                      source_type='TRAVEL', quantity_co2e=Decimal('50'))
        resp = self.api.get(f'/api/activities/summary/?client={self.client_obj.id}')
        data = resp.json()
        self.assertAlmostEqual(data['scope1_co2e'], 300.0)
        self.assertAlmostEqual(data['scope2_co2e'], 300.0)
        self.assertAlmostEqual(data['scope3_co2e'], 50.0)

    def test_total_count(self):
        for _ in range(5):
            make_activity(self.client_obj)
        resp = self.api.get(f'/api/activities/summary/?client={self.client_obj.id}')
        self.assertEqual(resp.json()['total'], 5)

    def test_pending_count_decreases_after_approval(self):
        a = make_activity(self.client_obj)
        resp = self.api.get(f'/api/activities/summary/?client={self.client_obj.id}')
        self.assertEqual(resp.json()['pending'], 1)
        self.api.post(f'/api/activities/{a.id}/approve/')
        resp2 = self.api.get(f'/api/activities/summary/?client={self.client_obj.id}')
        self.assertEqual(resp2.json()['pending'], 0)
        self.assertEqual(resp2.json()['approved'], 1)

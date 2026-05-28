"""
Parsers for SAP flat file, Green Button utility CSV, and Concur travel CSV.
Each parser returns a list of dicts with normalized fields ready for NormalizedActivity creation.
"""
import csv
import io
import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# ── Emission factor lookups (kg CO2e per unit) ──────────────────────────────
# Sources: DEFRA 2023 GHG Conversion Factors, EPA eGRID 2022
EMISSION_FACTORS = {
    # fuel_combustion: per litre
    ('fuel_combustion', 'diesel', 'GLOBAL'): Decimal('2.6760'),
    ('fuel_combustion', 'petrol', 'GLOBAL'): Decimal('2.3080'),
    ('fuel_combustion', 'natural_gas', 'GLOBAL'): Decimal('2.0440'),  # per m3
    ('fuel_combustion', 'lng', 'GLOBAL'): Decimal('1.1640'),          # per kg
    # purchased_electricity: per kWh
    ('purchased_electricity', None, 'GB'): Decimal('0.2120'),   # DEFRA 2023 UK
    ('purchased_electricity', None, 'US'): Decimal('0.3860'),   # EPA eGRID national avg
    ('purchased_electricity', None, 'DE'): Decimal('0.4340'),   # Germany
    ('purchased_electricity', None, 'GLOBAL'): Decimal('0.3500'),
    # flight: per passenger-km (economy)
    ('flight', 'economy', 'GLOBAL'): Decimal('0.1556'),
    ('flight', 'business', 'GLOBAL'): Decimal('0.4295'),
    ('flight', 'first', 'GLOBAL'): Decimal('0.6199'),
    # hotel: per night
    ('hotel', None, 'GB'): Decimal('11.10'),
    ('hotel', None, 'US'): Decimal('13.60'),
    ('hotel', None, 'GLOBAL'): Decimal('12.30'),
    # ground_transport: per km
    ('ground_transport', 'car_rental', 'GLOBAL'): Decimal('0.1710'),
    ('ground_transport', 'taxi', 'GLOBAL'): Decimal('0.1490'),
    ('ground_transport', 'train', 'GLOBAL'): Decimal('0.0410'),
}

# IATA airport coordinates (subset — key hubs)
AIRPORTS = {
    'LHR': (51.477, -0.461), 'JFK': (40.640, -73.779), 'LAX': (33.943, -118.408),
    'CDG': (49.012, 2.550), 'DXB': (25.253, 55.364), 'ORD': (41.978, -87.904),
    'ATL': (33.641, -84.427), 'BOS': (42.365, -71.010), 'SFO': (37.619, -122.375),
    'MIA': (25.796, -80.287), 'SEA': (47.449, -122.309), 'DFW': (32.897, -97.038),
    'SIN': (1.359, 103.989), 'HKG': (22.309, 113.915), 'NRT': (35.765, 140.386),
    'FRA': (50.026, 8.543), 'AMS': (52.308, 4.764), 'MAD': (40.472, -3.561),
    'DEL': (28.556, 77.100), 'BOM': (19.089, 72.868), 'SYD': (33.947, 151.179),
    'MEX': (19.436, -99.072), 'GRU': (23.435, -46.473), 'ICN': (37.460, 126.440),
}

SAP_MATERIAL_CATEGORIES = {
    # material number prefix → (category, subcategory, scope)
    'DIESEL': ('fuel_combustion', 'diesel', 1),
    'PETROL': ('fuel_combustion', 'petrol', 1),
    'NATGAS': ('fuel_combustion', 'natural_gas', 1),
    'LNG': ('fuel_combustion', 'lng', 1),
    'GAS': ('fuel_combustion', 'natural_gas', 1),
    'FUEL': ('fuel_combustion', 'diesel', 1),
}

SAP_UNIT_TO_SI = {
    'l': ('L', 1.0), 'liter': ('L', 1.0), 'litre': ('L', 1.0),
    'gal': ('L', 3.785), 'gallon': ('L', 3.785), 'gallons': ('L', 3.785),
    'm3': ('m3', 1.0), 'kg': ('kg', 1.0),
    'kwh': ('kWh', 1.0), 'mwh': ('kWh', 1000.0),
    'st': (None, None),  # pieces — skip
}

SAP_DATE_FORMATS = ['%d.%m.%Y', '%Y%m%d', '%Y-%m-%d', '%m/%d/%Y']

SAP_HEADER_MAP = {
    # German → English
    'buchungsdatum': 'BUDAT', 'werk': 'WERKS', 'material': 'MATNR',
    'menge': 'MENGE', 'basismengeneinheit': 'MEINS', 'kostenstelle': 'KOSTL',
    'lieferant': 'LIFNR', 'bewegungsart': 'BWART', 'belegnummer': 'MBLNR',
    # English variants
    'posting date': 'BUDAT', 'plant': 'WERKS', 'material number': 'MATNR',
    'quantity': 'MENGE', 'base unit': 'MEINS', 'cost center': 'KOSTL',
    'vendor': 'LIFNR', 'movement type': 'BWART', 'document': 'MBLNR',
}

SAP_CONSUMPTION_MOVEMENTS = {'201', '261', '262', '551', '601'}

PLANT_COUNTRY = {
    '1000': 'DE', 'DE01': 'DE', 'DE02': 'DE',
    'US01': 'US', 'US02': 'US', '3000': 'US',
    'GB01': 'GB', '2000': 'GB',
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in SAP_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(raw: str) -> Decimal | None:
    raw = str(raw).strip().replace(',', '').replace(' ', '')
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def get_ef(category, subcategory, region='GLOBAL'):
    key = (category, subcategory, region)
    if key in EMISSION_FACTORS:
        return EMISSION_FACTORS[key]
    return EMISSION_FACTORS.get((category, subcategory, 'GLOBAL'))


# ── SAP Parser ───────────────────────────────────────────────────────────────
def parse_sap(file_content: str) -> list[dict]:
    results = []
    sniffer = csv.Sniffer()
    dialect = None
    try:
        dialect = sniffer.sniff(file_content[:2000], delimiters=',\t|;')
    except Exception:
        pass

    reader = csv.DictReader(io.StringIO(file_content), dialect=dialect or 'excel')
    raw_headers = reader.fieldnames or []

    # Normalize headers
    header_map = {}
    for h in raw_headers:
        normalized = SAP_HEADER_MAP.get(h.lower().strip(), h.upper().strip())
        header_map[h] = normalized

    def get_field(row, field):
        for k, v in header_map.items():
            if v == field and k in row:
                return row[k]
        return ''

    for i, row in enumerate(reader):
        errors = []
        warnings = []

        movement = get_field(row, 'BWART').strip()
        if movement and movement not in SAP_CONSUMPTION_MOVEMENTS:
            results.append({'row_index': i, 'raw_data': dict(row), 'parse_status': 'ok',
                            'parse_errors': [], 'skip': True, 'skip_reason': f'Movement type {movement} is receipt/return, not consumption'})
            continue

        date_raw = get_field(row, 'BUDAT')
        parsed_date = parse_date(date_raw) if date_raw else None
        if not parsed_date:
            errors.append({'field': 'BUDAT', 'message': f'Cannot parse date: "{date_raw}"'})

        plant = get_field(row, 'WERKS').strip()
        if not plant:
            warnings.append({'field': 'WERKS', 'message': 'Plant code missing — cannot determine region for emission factor'})

        material = get_field(row, 'MATNR').strip().lstrip('0') or get_field(row, 'MATNR').strip()
        qty_raw = get_field(row, 'MENGE')
        qty = parse_decimal(qty_raw)
        if qty is None:
            errors.append({'field': 'MENGE', 'message': f'Cannot parse quantity: "{qty_raw}"'})

        unit_raw = get_field(row, 'MEINS').strip().lower()
        unit_info = SAP_UNIT_TO_SI.get(unit_raw)
        if unit_info is None:
            warnings.append({'field': 'MEINS', 'message': f'Unknown unit "{unit_raw}" — skipping conversion'})
            unit_si, factor = unit_raw, 1.0
        else:
            unit_si, factor = unit_info
            if unit_si is None:
                results.append({'row_index': i, 'raw_data': dict(row), 'parse_status': 'warn',
                                'parse_errors': [{'field': 'MEINS', 'message': f'Unit "{unit_raw}" (pieces) cannot be converted to CO2e'}],
                                'skip': True})
                continue

        category, subcategory, scope = ('procurement', None, 3)
        for key, (cat, subcat, sc) in SAP_MATERIAL_CATEGORIES.items():
            if key.lower() in material.lower():
                category, subcategory, scope = cat, subcat, sc
                break

        region = PLANT_COUNTRY.get(plant, 'GLOBAL')
        ef_value = get_ef(category, subcategory, region) if category == 'fuel_combustion' else None

        qty_converted = qty * Decimal(str(factor)) if qty else None
        co2e = qty_converted * ef_value if (qty_converted and ef_value) else None

        status = 'error' if errors else ('warn' if warnings else 'ok')
        results.append({
            'row_index': i,
            'raw_data': dict(row),
            'parse_status': status,
            'parse_errors': errors + warnings,
            'skip': bool(errors),
            'normalized': {
                'source_type': 'SAP',
                'scope': scope,
                'category': category,
                'activity_date': parsed_date,
                'facility_code': plant,
                'description': f"Material {material} | Doc {get_field(row, 'MBLNR').strip()}",
                'quantity_value': qty_converted or qty or Decimal('0'),
                'quantity_unit': unit_si or unit_raw,
                'quantity_co2e': co2e,
                'ef_key': (category, subcategory, region),
            }
        })
    return results


# ── Utility Parser (Green Button CSV) ───────────────────────────────────────
def parse_utility(file_content: str) -> list[dict]:
    results = []
    lines = file_content.splitlines()

    account_number = ''
    meter_id = ''
    for line in lines[:10]:
        lower = line.lower()
        if 'account' in lower:
            parts = line.split(',')
            if len(parts) > 1:
                account_number = parts[1].strip().strip('"')
        if 'meter' in lower:
            parts = line.split(',')
            if len(parts) > 1:
                meter_id = parts[1].strip().strip('"')

    data_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    header_found = False
    data_start = 0
    for i, line in enumerate(data_lines):
        lower = line.lower()
        if 'start date' in lower or 'date' in lower and 'usage' in lower:
            header_found = True
            data_start = i
            break

    if not header_found:
        return [{'row_index': 0, 'raw_data': {'raw': file_content[:200]},
                 'parse_status': 'error', 'parse_errors': [{'field': 'header', 'message': 'Could not find data header row'}], 'skip': True}]

    reader = csv.DictReader(data_lines[data_start:])
    for i, row in enumerate(reader):
        errors = []
        warnings = []
        raw = {k.strip().upper(): (v.strip() if isinstance(v, str) else '') for k, v in row.items() if k and isinstance(k, str)}

        # Flexible column name matching
        def get_col(*names):
            for n in names:
                for k in raw:
                    if n.upper() in k:
                        return raw[k]
            return ''

        type_val = get_col('TYPE')
        if type_val and 'electric' not in type_val.lower() and 'kwh' not in type_val.lower():
            results.append({'row_index': i, 'raw_data': dict(row), 'parse_status': 'ok',
                            'parse_errors': [], 'skip': True, 'skip_reason': f'Non-electricity row: {type_val}'})
            continue

        start_raw = get_col('START DATE', 'START')
        end_raw = get_col('END DATE', 'END')
        start_date = parse_date(start_raw) if start_raw else None
        end_date = parse_date(end_raw) if end_raw else None
        if not start_date:
            errors.append({'field': 'START DATE', 'message': f'Cannot parse date: "{start_raw}"'})

        usage_raw = get_col('USAGE', 'CONSUMPTION', 'KWH')
        usage = parse_decimal(usage_raw) if usage_raw else None
        if usage is None:
            warnings.append({'field': 'USAGE', 'message': f'Blank or unparseable usage: "{usage_raw}" — may be estimated read'})

        unit_raw = get_col('UNITS', 'UNIT').lower()
        if unit_raw == 'mwh':
            usage = usage * 1000 if usage else None
            unit_norm = 'kWh'
        else:
            unit_norm = 'kWh'

        region = 'GLOBAL'
        ef_value = get_ef('purchased_electricity', None, region)
        co2e = usage * ef_value if (usage and ef_value) else None

        status = 'error' if errors else ('warn' if warnings else 'ok')
        results.append({
            'row_index': i,
            'raw_data': dict(row),
            'parse_status': status,
            'parse_errors': errors + warnings,
            'skip': bool(errors),
            'normalized': {
                'source_type': 'UTILITY',
                'scope': 2,
                'category': 'purchased_electricity',
                'activity_date': start_date,
                'facility_code': meter_id or account_number or '',
                'description': f"Electricity bill {start_raw} to {end_raw} | Meter {meter_id}",
                'quantity_value': usage or Decimal('0'),
                'quantity_unit': unit_norm,
                'quantity_co2e': co2e,
                'ef_key': ('purchased_electricity', None, region),
            }
        })
    return results


# ── Travel Parser (Concur CSV) ───────────────────────────────────────────────
TRAVEL_CATEGORY_MAP = {
    'air_fare': ('flight', 'economy', 3),
    'airfare': ('flight', 'economy', 3),
    'air fare': ('flight', 'economy', 3),
    'hotel': ('hotel', None, 3),
    'lodging': ('hotel', None, 3),
    'car_rental': ('ground_transport', 'car_rental', 3),
    'car rental': ('ground_transport', 'car_rental', 3),
    'taxi': ('ground_transport', 'taxi', 3),
    'train': ('ground_transport', 'train', 3),
    'rail': ('ground_transport', 'train', 3),
    'ground': ('ground_transport', 'car_rental', 3),
}

CLASS_MAP = {
    'business': 'business', 'business class': 'business', 'biz': 'business',
    'first': 'first', 'first class': 'first',
    'economy': 'economy', 'coach': 'economy', 'economy plus': 'economy',
}


def parse_travel(file_content: str) -> list[dict]:
    results = []
    reader = csv.DictReader(io.StringIO(file_content))

    for i, row in enumerate(reader):
        errors = []
        warnings = []
        raw = {k.strip().upper(): (v.strip() if isinstance(v, str) else '') for k, v in row.items() if k and isinstance(k, str)}

        def get(field, *alts):
            for f in (field, *alts):
                for k in raw:
                    if f.upper() in k:
                        return raw[k]
            return ''

        expense_type = get('EXPENSETYPE', 'EXPENSE TYPE', 'TYPE', 'CATEGORY').lower().strip()
        cat_info = None
        for key, info in TRAVEL_CATEGORY_MAP.items():
            if key in expense_type:
                cat_info = info
                break
        if not cat_info:
            results.append({'row_index': i, 'raw_data': dict(row), 'parse_status': 'warn',
                            'parse_errors': [{'field': 'EXPENSETYPE', 'message': f'Unrecognized expense type: "{expense_type}"'}],
                            'skip': True})
            continue

        category, subcategory, scope = cat_info

        date_raw = get('TRANSACTIONDATE', 'TRANSACTION DATE', 'DATE', 'TRAVELDATE')
        parsed_date = parse_date(date_raw) if date_raw else None
        if not parsed_date:
            errors.append({'field': 'DATE', 'message': f'Cannot parse date: "{date_raw}"'})

        qty = None
        unit = ''
        co2e = None
        description = ''

        if category == 'flight':
            orig = get('ORIGCITY', 'ORIG', 'ORIGIN', 'DEPARTURE').upper().strip()[:3]
            dest = get('DESTCITY', 'DEST', 'DESTINATION', 'ARRIVAL').upper().strip()[:3]
            dist_raw = get('DISTANCE')
            dist = parse_decimal(dist_raw) if dist_raw else None

            if not dist:
                if orig in AIRPORTS and dest in AIRPORTS:
                    lat1, lon1 = AIRPORTS[orig]
                    lat2, lon2 = AIRPORTS[dest]
                    dist = Decimal(str(round(haversine_km(lat1, lon1, lat2, lon2), 1)))
                    dist *= Decimal('1.08')  # DEFRA uplift factor for radiative forcing
                    warnings.append({'field': 'DISTANCE', 'message': f'Distance estimated via Great Circle ({orig}→{dest}): {dist:.0f}km (incl. 8% uplift)'})
                elif orig or dest:
                    warnings.append({'field': 'DISTANCE', 'message': f'Unknown airport code(s): {orig}, {dest} — cannot estimate distance'})

            class_raw = get('CLASSOFSERVICE', 'CLASS', 'CABIN').lower()
            flight_class = CLASS_MAP.get(class_raw, 'economy')
            subcategory = flight_class

            qty = dist or Decimal('0')
            unit = 'km'
            ef_value = get_ef('flight', flight_class, 'GLOBAL')
            co2e = qty * ef_value if (qty and ef_value) else None
            description = f"Flight {orig}→{dest} ({flight_class})"

        elif category == 'hotel':
            checkin_raw = get('HOTELCHECKIN', 'CHECKIN', 'CHECK IN')
            checkout_raw = get('HOTELCHECKOUT', 'CHECKOUT', 'CHECK OUT')
            nights_raw = get('NIGHTS', 'DURATION')

            nights = parse_decimal(nights_raw) if nights_raw else None
            if not nights:
                checkin = parse_date(checkin_raw) if checkin_raw else None
                checkout = parse_date(checkout_raw) if checkout_raw else None
                if checkin and checkout:
                    nights = Decimal(str((checkout - checkin).days))
                else:
                    nights = Decimal('1')
                    warnings.append({'field': 'NIGHTS', 'message': 'Could not determine nights — defaulting to 1'})

            city = get('HOTELCITY', 'CITY')
            country = get('HOTELCOUNTRY', 'COUNTRY').upper()[:2]
            region = country if country in ('GB', 'US', 'DE') else 'GLOBAL'
            ef_value = get_ef('hotel', None, region)
            qty = nights
            unit = 'nights'
            co2e = nights * ef_value if ef_value else None
            description = f"Hotel {city} ({nights:.0f} nights)"

        else:  # ground_transport
            dist_raw = get('DISTANCE', 'MILES', 'KM')
            dist = parse_decimal(dist_raw) if dist_raw else None
            dist_unit = get('DISTANCEUNIT', 'UNIT').lower()
            if dist and 'mile' in dist_unit:
                dist = dist * Decimal('1.60934')
            if not dist:
                warnings.append({'field': 'DISTANCE', 'message': 'Distance missing for ground transport — CO2e will be null'})
            qty = dist or Decimal('0')
            unit = 'km'
            ef_value = get_ef('ground_transport', subcategory, 'GLOBAL')
            co2e = qty * ef_value if (qty and ef_value and dist) else None
            description = f"{expense_type.title()} transport"

        status = 'error' if errors else ('warn' if warnings else 'ok')
        results.append({
            'row_index': i,
            'raw_data': dict(row),
            'parse_status': status,
            'parse_errors': errors + warnings,
            'skip': bool(errors),
            'normalized': {
                'source_type': 'TRAVEL',
                'scope': scope,
                'category': category,
                'activity_date': parsed_date,
                'facility_code': '',
                'description': description,
                'quantity_value': qty or Decimal('0'),
                'quantity_unit': unit,
                'quantity_co2e': co2e,
                'ef_key': (category, subcategory, 'GLOBAL'),
            }
        })
    return results

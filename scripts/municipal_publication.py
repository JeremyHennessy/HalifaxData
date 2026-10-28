"""Strict public projection for reviewed historical municipal observations."""
import hashlib,json,re,datetime
from review_receipts import validate_receipt
TOP={'coverage', 'licenceURL', 'limitations', 'schemaVersion', 'records', 'sourceId', 'sourceURL', 'attribution'}
ROW={'multiplier', 'currencyDisplayMetadata', 'sourceRowId', 'scope', 'unit', 'fiscalYearLabel', 'sourceURL', 'stage', 'municipalityLabel', 'currency', 'id', 'exactAccountingPolicyVerified', 'provenance', 'municipalityType', 'measures'}
MEASURES={'conditional_transfers_from_federal_or_provincial_governments_or_agencies', 'transportation_services', 'total_revenues', 'conditional_transfers_from_other_governments', 'total_expenditures', 'conditional_transfers_from_other_local_governments', 'assessable_property_taxes_net_of_school_board_appropriations_corrections_housing_deficits_', 'extraordinary_or_special_items', 'sales_of_services', 'other_revenue_from_own_sources', 'environmental_health_services', 'environmental_development_services', 'total_financing_and_transfers', 'annual_surplus_deficit_', 'net_property_taxes_and_payments_in_lieu_of_taxes', 'operating_surplus_deficit_before_financing_and_transfers', 'public_health_services', 'recreation_and_cultural_services', 'grants_in_lieu_of_taxes', 'general_government_services', 'protective_services', 'unconditional_transfers_from_other_governments', 'services_provided_to_other_governments'}
COVERAGE={'notes', 'lastYear', 'municipalityTypeYearKeys', 'notCurrent', 'complete', 'recordCount', 'distinctLabels', 'firstYear'}
PROVENANCE={'sourceLocator', 'rawBodySha256', 'captureManifestSha256', 'retrievedAt', 'rowIndex'}
def municipal_files(root):
    folder=root/'data/municipal';path=folder/'records.json'
    if not path.exists():return []
    receipt=validate_receipt(json.loads((folder/'publication-review.json').read_text()),'municipal')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['bundleSha256']:raise ValueError('Municipal review mismatch')
    b=json.loads(path.read_text())
    if set(b)!=TOP or set(b['coverage'])!=COVERAGE or b['schemaVersion']!='municipal-fiscal-observations-v1' or b['coverage']['notCurrent'] is not True or b['coverage']['complete'] is not False:raise ValueError('Invalid municipal coverage')
    ids=set();keys=set()
    for row in b['records']:
        if set(row)!=ROW or set(row['measures'])!=MEASURES or set(row['provenance'])!=PROVENANCE:raise ValueError('Unexpected municipal fields')
        if row['currency'] is not None or row['multiplier'] is not None or row['exactAccountingPolicyVerified'] is not False or row['stage']!='reported_fir_observation' or row['unit']!='source_reported_monetary_unit':raise ValueError('Unverified accounting claim')
        if row['provenance']['captureManifestSha256']!=receipt['captureManifestSha256']:raise ValueError('Capture mismatch')
        key=(row['municipalityLabel'],row['municipalityType'],row['fiscalYearLabel'])
        if row['id'] in ids or key in keys:raise ValueError('Duplicate observation')
        ids.add(row['id']);keys.add(key)
        for measure in row['measures'].values():
            if set(measure)!={'presence','rawValue'}:raise ValueError('Unexpected measure fields')
            if measure['presence']=='missing':
                if measure['rawValue'] is not None:raise ValueError('Missing is not zero')
            elif measure['presence']!='present' or not isinstance(measure['rawValue'],str) or not re.fullmatch(r'-?\d+(?:\.\d+)?',measure['rawValue']):raise ValueError('Invalid exact measure')
    if len(ids)!=b['coverage']['recordCount'] or len(keys)!=b['coverage']['municipalityTypeYearKeys']:raise ValueError('Incomplete municipal coverage')
    return ['data/municipal/records.json','data/municipal/publication-review.json']

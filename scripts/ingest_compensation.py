#!/usr/bin/env python3
"""Extract HRM annual compensation statements into normalized JSON.

Safety properties:
- Never overwrites the checked-in dataset unless every requested source downloads and parses.
- Retains source id and entity on every row.
- Treats threshold disclosure as a disclosure population, not the full HRM workforce.
- Preserves source-reported arithmetic discrepancies instead of silently correcting them.
- Uses a text fallback only when a non-HRM PDF page yields no usable table rows.
"""
from __future__ import annotations
import io, json, re, sys, unicodedata
from pathlib import Path
import requests, pdfplumber

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'data/sources.json'
OUTPUT=ROOT/'data/generated/compensation.json'
UA='HalifaxData/0.1 (+https://github.com/JeremyHennessy/HalifaxData)'
MONEY_RE=r'(?:\d\s+)?\d{1,3}(?:,\d{3})*\.\d{2}'

def money(value):
    if value is None: return 0.0
    s=str(value).replace('$','').replace(',','').replace(' ','').strip()
    if s in {'','-','—','–'}: return 0.0
    s=re.sub(r'[^0-9.()\-]','',s)
    if not s: return 0.0
    if s.startswith('(') and s.endswith(')'): s='-'+s[1:-1]
    try: return round(float(s),2)
    except ValueError: return 0.0

def clean(value):
    return re.sub(r'\s+',' ',str(value or '')).strip()

def person_key(name):
    # Disclosure typography changes across years (for example Åsa → Asa).
    # Fold accents only for the internal longitudinal key; preserve source display text.
    folded=unicodedata.normalize('NFKD',clean(name))
    return ''.join(ch.lower() for ch in folded if ch.isalnum() and not unicodedata.combining(ch))

def entity_for_page(text):
    t=(text or '').lower()
    if 'halifax public librar' in t or 'halifax regional library' in t: return 'Halifax Public Libraries'
    if 'halifax water' in t or 'halifax regional water commission' in t: return 'Halifax Water'
    return 'Halifax Regional Municipality'

def make_record(year,source_id,entity,name,business_unit,position,salary,benefits,total,extraction_method='pdf_table'):
    record={'fiscal_year_end':year,'entity':entity,'name':clean(name),'person_key':person_key(clean(name)),'business_unit':clean(business_unit),'position':clean(position),'wages':money(salary),'benefits':money(benefits),'total':money(total),'source_id':source_id}
    if extraction_method != 'pdf_table':
        record['extraction_method']=extraction_method
    delta=round(record['total']-(record['wages']+record['benefits']),2)
    if abs(delta)>1.05:
        record['source_total_delta']=delta
        record['validation_flags']=['reported_total_mismatch']
    return record

def parse_non_hrm_text(text,entity,year,source_id):
    """Parse non-HRM lines only when table extraction produced no usable rows.

    The 2025 Libraries/Water pages visually contain regular rows but expose a
    collapsed table structure to pdfplumber. Their text layer remains row-wise.
    """
    records=[]
    if entity=='Halifax Public Libraries':
        pattern=re.compile(rf'^(?P<name>.+?)\s+Library\s+(?P<position>.+?)\s+(?P<wages>{MONEY_RE})\s+(?P<benefits>{MONEY_RE}|-)\s+(?P<total>{MONEY_RE})$')
        for raw in text.splitlines():
            line=clean(raw); match=pattern.match(line)
            if not match: continue
            parts=match.group('name').split()
            if len(parts)<2: continue
            # This page publishes First Last while earlier statements publish Last, First.
            # Normalize display order so longitudinal keys remain compatible.
            name=f'{parts[-1]}, {" ".join(parts[:-1])}'
            record=make_record(year,source_id,entity,name,entity,match.group('position'),match.group('wages'),match.group('benefits'),match.group('total'),'pdf_text_fallback')
            if record['total']>=100000: records.append(record)
    elif entity=='Halifax Water':
        pattern=re.compile(rf'^(?P<last>[^,]+),\s+(?P<given>(?:[A-ZÀ-Þ]\.[ ]+)?\S+(?:[ ]+[A-ZÀ-Þ]\.)?)\s+(?P<position>.+?)\s+(?P<wages>{MONEY_RE})\s+(?P<benefits>{MONEY_RE}|-)\s+(?P<total>{MONEY_RE})$')
        for raw in text.splitlines():
            line=clean(raw); match=pattern.match(line)
            if not match: continue
            name=f'{match.group("last")}, {match.group("given")}'
            record=make_record(year,source_id,entity,name,entity,match.group('position'),match.group('wages'),match.group('benefits'),match.group('total'),'pdf_text_fallback')
            if record['total']>=100000: records.append(record)
    return records

def parse_pdf(blob, year, source_id):
    records=[]
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page in pdf.pages:
            text=page.extract_text() or ''
            entity=entity_for_page(text)
            page_records=[]
            for table in page.extract_tables() or []:
                for row in table or []:
                    cells=[clean(c) for c in (row or [])]
                    if len(cells)<4: continue
                    name=cells[0]
                    total=money(cells[-1])
                    if ',' not in name or total < 100000: continue
                    salary=money(cells[-3]); benefits=money(cells[-2])
                    if entity=='Halifax Regional Municipality' and len(cells)>=6:
                        business_unit=cells[1]; position=cells[2]
                    else:
                        business_unit=entity; position=cells[1] if len(cells)>=5 else ''
                    page_records.append(make_record(year,source_id,entity,name,business_unit,position,salary,benefits,total))
            if not page_records and entity!='Halifax Regional Municipality':
                page_records=parse_non_hrm_text(text,entity,year,source_id)
            records.extend(page_records)
    unique={}
    for r in records: unique[(r['fiscal_year_end'],r['entity'],r['person_key'],r['total'])]=r
    return list(unique.values())

def main():
    registry=json.loads(SOURCES.read_text())['sources']
    comp=[s for s in registry if s['id'].startswith('hrm-comp-') and s['status']=='ready']
    all_rows=[]; stats=[]
    session=requests.Session(); session.headers['User-Agent']=UA
    for src in comp:
        year=int(src['id'].rsplit('-',1)[1])
        print(f'Downloading {src["id"]}…', file=sys.stderr)
        r=session.get(src['url'],timeout=60); r.raise_for_status()
        rows=parse_pdf(r.content,year,src['id'])
        hrm_count=sum(x['entity']=='Halifax Regional Municipality' for x in rows)
        if hrm_count < 25:
            raise RuntimeError(f'{src["id"]}: only {hrm_count} HRM rows parsed; refusing to overwrite generated data')
        discrepancy_count=sum('reported_total_mismatch' in x.get('validation_flags',[]) for x in rows)
        stats.append({'source_id':src['id'],'records':len(rows),'hrm_records':hrm_count,'source_arithmetic_discrepancies':discrepancy_count})
        all_rows.extend(rows)
    all_rows.sort(key=lambda r:(r['fiscal_year_end'],r['entity'],r['name']))
    discrepancy_count=sum('reported_total_mismatch' in r.get('validation_flags',[]) for r in all_rows)
    payload={'metadata':{'dataset_status':'automated_full_extraction','min_year':min(r['fiscal_year_end'] for r in all_rows),'max_year':max(r['fiscal_year_end'] for r in all_rows),'disclosure_threshold_cad':100000,'source_stats':stats,'source_arithmetic_discrepancies':discrepancy_count,'note':'Automated extraction from all configured annual HRM compensation statements. Threshold disclosure is not the full workforce. Source-reported arithmetic discrepancies are preserved and explicitly flagged.'},'records':all_rows}
    tmp=OUTPUT.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n'); tmp.replace(OUTPUT)
    print(f'Wrote {len(all_rows)} rows to {OUTPUT} ({discrepancy_count} source arithmetic discrepancies)', file=sys.stderr)
if __name__=='__main__': main()

#!/usr/bin/env python3
"""Temporary Build 003 endpoint diagnostic.

Inspects Socrata derived-view lineage/catalog metadata and eSCRIBE meeting-calendar
HTML so broken derived views can be replaced and Council crawling can be expanded.
No production artifacts are written.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import requests

UA='HalifaxData/0.3 diagnostic (+https://github.com/JeremyHennessy/HalifaxData)'
s=requests.Session(); s.headers['User-Agent']=UA

for view_id in ['thwb-cfp5','k8qq-y6un','kuu2-92bp']:
    url=f'https://data.novascotia.ca/api/views/{view_id}'
    try:
        r=s.get(url,timeout=60); print(f'=== VIEW {view_id} {r.status_code} {r.headers.get("content-type")} bytes={len(r.content)} ===')
        data=r.json()
        keep={k:data.get(k) for k in ['id','name','assetType','rowsUpdatedAt','metadata','query','columns'] if k in data}
        # Keep output bounded while surfacing lineage/query metadata.
        if isinstance(keep.get('columns'),list):
            keep['columns']=[{k:c.get(k) for k in ['id','name','fieldName','dataTypeName']} for c in keep['columns'][:20]]
        print(json.dumps(keep,indent=2,ensure_ascii=False)[:16000])
    except Exception as exc:
        print(f'VIEW ERROR {view_id}: {type(exc).__name__}: {exc}')

queries=[
    'Municipal Fiscal Statistics Operating Fund Total Revenues and Expenditures by Municipality',
    'Uniform Assessment',
]
for q in queries:
    try:
        r=s.get('https://api.us.socrata.com/api/catalog/v1',params={'search_context':'data.novascotia.ca','q':q,'limit':30},timeout=60)
        print(f'=== CATALOG {q!r} {r.status_code} bytes={len(r.content)} ===')
        data=r.json()
        for result in data.get('results',[])[:30]:
            res=result.get('resource') or {}
            print(json.dumps({
                'id':res.get('id'),'name':res.get('name'),'type':res.get('type'),
                'description':(res.get('description') or '')[:220],
                'permalink':res.get('permalink'),
            },ensure_ascii=False))
    except Exception as exc:
        print(f'CATALOG ERROR: {type(exc).__name__}: {exc}')

calendar_urls=[
    'https://pub-halifax.escribemeetings.com/MeetingsCalendarView.aspx?Expanded=Halifax%20Regional%20Council',
    'https://pub-halifax.escribemeetings.com/MeetingsCalendarView.aspx?Expanded=Budget%20Committee',
    'https://pub-halifax.escribemeetings.com/Meetings.aspx',
]
for url in calendar_urls:
    try:
        r=s.get(url,timeout=60); print(f'=== ESCRIBE {url} {r.status_code} {r.url} bytes={len(r.content)} ===')
        text=r.text
        ids=[]
        for match in re.finditer(r'Meeting\.aspx\?[^"\'<>]*?(?:Id|id)=([0-9a-fA-F-]{36})[^"\'<>]*',text):
            mid=match.group(1)
            if mid not in ids: ids.append(mid)
        print(f'meeting_ids={len(ids)} sample={ids[:20]}')
        print('contains GetCalendarMeetings=', 'GetCalendarMeetings' in text)
        for marker in ['Halifax Regional Council','Budget Committee','Past Meetings','Meeting.aspx']:
            print(marker, text.find(marker))
    except Exception as exc:
        print(f'ESCRIBE ERROR: {type(exc).__name__}: {exc}')

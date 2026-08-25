#!/usr/bin/env python3
"""Temporary Build 003 diagnostic for the eSCRIBE meeting calendar contract.

Confirms the calendar POST contract and inspects representative 2025–2026 meeting
objects before the production Council collector is enabled.
"""
from __future__ import annotations

import json
from urllib.parse import quote, urljoin

import requests

BASE='https://pub-halifax.escribemeetings.com/'
UA='HalifaxData/0.3 diagnostic (+https://github.com/JeremyHennessy/HalifaxData)'
s=requests.Session(); s.headers['User-Agent']=UA

filters=['Halifax Regional Council','Budget Committee']
windows=[
    ('2025-01-01T00:00:00-04:00','2026-01-01T00:00:00-04:00'),
    ('2026-01-01T00:00:00-04:00','2027-01-01T00:00:00-04:00'),
]

for expanded in filters:
    calendar_url=urljoin(BASE,'MeetingsCalendarView.aspx?Expanded='+quote(expanded))
    landing=s.get(calendar_url,timeout=60); landing.raise_for_status()
    print(f'LANDING {expanded}: {landing.status_code} bytes={len(landing.content)} cookies={list(s.cookies.keys())}')
    endpoint=urljoin(BASE,'MeetingsCalendarView.aspx/GetCalendarMeetings?Expanded='+quote(expanded))
    for start,end in windows:
        payload={'calendarStartDate':start,'calendarEndDate':end}
        response=s.post(endpoint,json=payload,timeout=60,headers={'Referer':calendar_url,'X-Requested-With':'XMLHttpRequest'})
        print(f'POST {expanded} {start[:4]}: status={response.status_code} content-type={response.headers.get("content-type")} bytes={len(response.content)}')
        if not response.ok:
            print(response.text[:2000])
            continue
        try:
            body=response.json()
        except Exception:
            print(response.text[:4000]); continue
        items=body.get('d',[]) if isinstance(body,dict) else []
        print(f'items={len(items)} type={type(items).__name__}')
        if isinstance(items,str):
            try: items=json.loads(items)
            except Exception: pass
        if isinstance(items,list):
            for item in items[:5]:
                print(json.dumps(item,ensure_ascii=False,default=str)[:5000])
            ids=[]
            for item in items:
                if isinstance(item,dict):
                    mid=item.get('ID') or item.get('Id') or item.get('id')
                    if mid and mid not in ids: ids.append(mid)
            print(f'unique_ids={len(ids)} sample={ids[:10]}')

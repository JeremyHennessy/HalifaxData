#!/usr/bin/env python3
"""Temporary Build 003 diagnostic for the eSCRIBE meeting calendar contract.

The static calendar page exposes only one meeting link even though it contains the
full committee selector. This script finds the dynamic GetCalendarMeetings caller,
prints bounded context, and identifies its request URL/payload parameters without
writing production data.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

import requests

BASE='https://pub-halifax.escribemeetings.com/'
URL=urljoin(BASE,'MeetingsCalendarView.aspx?Expanded=Halifax%20Regional%20Council')
UA='HalifaxData/0.3 diagnostic (+https://github.com/JeremyHennessy/HalifaxData)'
s=requests.Session(); s.headers['User-Agent']=UA


def snippets(text, needle, radius=1800):
    out=[]; pos=0
    low=text.lower(); target=needle.lower()
    while True:
        i=low.find(target,pos)
        if i<0: break
        out.append(text[max(0,i-radius):min(len(text),i+len(needle)+radius)])
        pos=i+len(needle)
    return out

r=s.get(URL,timeout=60); r.raise_for_status(); html=r.text
print(f'PAGE {r.status_code} {r.url} bytes={len(r.content)}')
for needle in ['GetCalendarMeetings','fullCalendar','events:','eventSources','startParam','endParam']:
    hits=snippets(html,needle)
    print(f'INLINE {needle!r} hits={len(hits)}')
    for n,hit in enumerate(hits[:4],1):
        print(f'--- INLINE {needle} #{n} ---')
        print(hit)
        print('--- END ---')

scripts=[]
for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']',html,re.I):
    absolute=urljoin(r.url,src)
    if absolute not in scripts: scripts.append(absolute)
print(f'script_sources={len(scripts)}')
for script_url in scripts:
    try:
        resp=s.get(script_url,timeout=60)
        text=resp.text if resp.ok else ''
        interesting=any(token.lower() in text.lower() for token in ['GetCalendarMeetings','fullCalendar','Meeting.aspx?Id='])
        if not interesting: continue
        print(f'=== SCRIPT {resp.status_code} {script_url} bytes={len(resp.content)} ===')
        for needle in ['GetCalendarMeetings','fullCalendar','Meeting.aspx?Id=']:
            for n,hit in enumerate(snippets(text,needle)[:4],1):
                print(f'--- SCRIPT {needle} #{n} ---')
                print(hit)
                print('--- END ---')
    except Exception as exc:
        print(f'SCRIPT ERROR {script_url}: {type(exc).__name__}: {exc}')

# Also surface ASP.NET static-method-looking endpoints directly from HTML/JS strings.
endpoints=sorted(set(re.findall(r'[A-Za-z0-9_./-]+\.aspx/[A-Za-z0-9_]+',html)))
print('inline_method_endpoints=',endpoints[:100])

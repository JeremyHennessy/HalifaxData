#!/usr/bin/env python3
"""Temporary Build 020 diagnostic for the 2018 audited-statement parser gap.

Read-only: downloads two official HRM 2018 PDF attachments, prints text/image/layout
signals, and writes no production artifact. This diagnostic intentionally exits 0 so
it can gather evidence without turning an unresolved research question into a CI gate.
"""
from __future__ import annotations

import io
import re

import pdfplumber
import requests

import ingest_financial_history as base
from ingest_domains import fetch_pdf

SOURCES = [
    {
        "id": "registered-council",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/regional-council/180731rc1433.pdf",
    },
    {
        "id": "audit-finance-attachment",
        "url": "https://cdn.halifax.ca/sites/default/files/documents/city-hall/standing-committees/180718afsc1211.pdf",
    },
]
KEYWORD_RE = re.compile(r"(consolidated|statement|financial position|operations|cash flow|net financial)", re.I)


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = base.UA
    for src in SOURCES:
        source = {**src, "name": src["id"], "publisher": "Halifax Regional Municipality", "status": "diagnostic"}
        blob = fetch_pdf(session, source)
        print(f"SOURCE {src['id']} bytes={len(blob)}")
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            print(f"pages={len(pdf.pages)}")
            total_chars = 0
            text_pages = 0
            image_pages = 0
            keyword_pages = 0
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text(layout=True) or page.extract_text() or ""
                chars = len(text.strip())
                images = len(page.images or [])
                total_chars += chars
                text_pages += int(chars > 0)
                image_pages += int(images > 0)
                lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
                hits = [line for line in lines if KEYWORD_RE.search(line)]
                family, title = base.statement_context(text)
                if hits or family:
                    keyword_pages += 1
                    print(
                        f"p{page_num}: chars={chars} images={images} family={family!r} "
                        f"title={title!r} hits={hits[:8]!r}"
                    )
                elif page_num <= 3:
                    print(f"p{page_num}: chars={chars} images={images} first_lines={lines[:8]!r}")
            print(
                f"SUMMARY {src['id']}: total_chars={total_chars} text_pages={text_pages} "
                f"image_pages={image_pages} keyword_pages={keyword_pages}"
            )


if __name__ == "__main__":
    main()

"""Exact independent review admission for a bounded optional audit projection."""
import hashlib,json
HASH='9819d900353771f6acae841a960d5e3ce4bfaf62eef60f06ea51ad5b7269b091'
REVIEW_HASH='69d7381a1fc9c58497f60952b7619c6dd29612c3357e5532724e1bc39287cfdc'
SOURCE_HASH='6ea71b5adfb05d2583caef8d73beff541f7c83f64efd7eb5cecdff0e77e5ab11'
def hrm_winter_files(root):
    paths=[root/'data/hrm-winter/records.json',root/'data/hrm-winter/publication-review.json']
    if not paths[0].exists():return []
    if any(not p.is_file() or p.is_symlink() for p in paths):raise ValueError('Winter artifact and independent receipt required')
    if [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]!=[HASH,REVIEW_HASH]:raise ValueError('Exact independently reviewed winter bytes required')
    b,r=[json.loads(p.read_text()) for p in paths]
    if r['status']!='accepted' or r['bundleSha256']!=HASH or r['sourceSha256']!=SOURCE_HASH or b['publication']['allowed'] is not True or b['publication']['reviewId']!=r['evidenceId'] or b['publication']['reviewedOn']!=r['reviewedOn']:raise ValueError('Winter publication review mismatch')
    return [p.relative_to(root).as_posix() for p in paths]

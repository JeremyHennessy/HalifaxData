"""Exact independent review admission for a bounded optional audit projection."""
import hashlib,json
HASH='8ccd3f5b682889544c934ec39c67a8dad71add122f5a79c161e4192bf3f08282'
REVIEW_HASH='ff92bc3468bf56f6ade4e1ffe2f9288edfbedf194ce1f424c28c00f7e7c199ff'
SOURCE_HASH='bbe4378abb2b5ef128f9f2c33762884694e477df0043926d57da8e4a8586c636'
def hrm_facilities_files(root):
    paths=[root/'data/hrm-facilities/records.json',root/'data/hrm-facilities/publication-review.json']
    if not paths[0].exists():return []
    if any(not p.is_file() or p.is_symlink() for p in paths):raise ValueError('Facility artifact and independent receipt required')
    if [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]!=[HASH,REVIEW_HASH]:raise ValueError('Exact independently reviewed facility bytes required')
    b,r=[json.loads(p.read_text()) for p in paths]
    if r['status']!='accepted' or r['bundleSha256']!=HASH or r['sourceSha256']!=SOURCE_HASH or b['publication']['allowed'] is not True or b['publication']['reviewId']!=r['evidenceId'] or b['publication']['reviewedOn']!=r['reviewedOn']:raise ValueError('Facility publication review mismatch')
    return [p.relative_to(root).as_posix() for p in paths]

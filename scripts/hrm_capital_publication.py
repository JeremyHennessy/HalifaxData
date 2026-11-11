"""Exact independent review admission for a bounded optional audit projection."""
import hashlib,json
HASH='a33e4b93da00253b70125f4a34163cffa996a2cad8dacfb514ed6a150b6def7e'
REVIEW_HASH='0dd2938884f98373ffa68aecd5c15a5fe71fa29e90ef653b07ae811c06453b0b'
SOURCE_HASH='c18a7243e04556e25f9e99ae5c5fdfde8bc509663ed3ddfdd726e7c6481912af'
def hrm_capital_files(root):
    paths=[root/'data/hrm-capital/records.json',root/'data/hrm-capital/publication-review.json']
    if not paths[0].exists():return []
    if any(not p.is_file() or p.is_symlink() for p in paths):raise ValueError('Capital artifact and independent receipt required')
    if [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]!=[HASH,REVIEW_HASH]:raise ValueError('Exact independently reviewed capital bytes required')
    b,r=[json.loads(p.read_text()) for p in paths]
    if r['status']!='accepted' or r['bundleSha256']!=HASH or r['sourceSha256']!=SOURCE_HASH or b['publication']['allowed'] is not True or b['publication']['reviewId']!=r['evidenceId'] or b['publication']['reviewedOn']!=r['reviewedOn']:raise ValueError('Capital publication review mismatch')
    return [p.relative_to(root).as_posix() for p in paths]

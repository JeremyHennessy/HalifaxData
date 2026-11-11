"""Exact independent review admission for the historical Transit annual subset."""
import hashlib,json
HASH='bf72517583e3f9bec89fe5a776046df268b877d35a0bae6791f0bc0fcad72fb9'
REVIEW_HASH='fe25249bb223ba7a22cd3997ba0136b28a2088dce98a0c80f849e55c34e263b4'
SOURCE_HASH='2f6df924c46bef304aabe14842ac0ae21f0552f556943ea24b029b7bb8d24542'
def transit_files(root):
    paths=[root/'data/transit/records.json',root/'data/transit/publication-review.json']
    if not paths[0].exists() and not paths[0].is_symlink():return []
    if any(not p.is_file() or p.is_symlink() for p in paths):raise ValueError('Transit artifact and independent receipt required')
    if [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]!=[HASH,REVIEW_HASH]:raise ValueError('Exact independently reviewed Transit bytes required')
    b,r=[json.loads(p.read_text()) for p in paths]
    if r['status']!='accepted' or r['bundleSha256']!=HASH or r['sourceSha256']!=SOURCE_HASH or b['sourceSha256']!=SOURCE_HASH or b['publication']['allowed'] is not True or b['publication']['requiresMatchingIndependentReceipt'] is not True or b['publication']['consequentialAllegation'] is not False or b['publication']['reviewId']!=r['evidenceId'] or b['publication']['reviewedOn']!=r['reviewedOn']:raise ValueError('Transit publication review mismatch')
    return [p.relative_to(root).as_posix() for p in paths]

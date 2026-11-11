"""Admit only exact independently reviewed optional Transit financial context."""
import hashlib,json
from transit_publication import transit_files,HASH as PARENT_HASH,SOURCE_HASH
HASH='b1a7dfb335afe1c0880d993af9273470681a376f4a94c49ad5eb7f45567103b2'
REVIEW_HASH='73533a1d3cd5865591a403e41046b6c29376776fa117e056a8552e4dd47d3c7c'
def transit_finance_files(root):
    paths=[root/'data/transit-finance/context.json',root/'data/transit-finance/publication-review.json']
    if not paths[0].exists() and not paths[0].is_symlink():
        if paths[1].exists() or paths[1].is_symlink():raise ValueError('Transit finance orphan independent receipt')
        return []
    if any(not p.is_file() or p.is_symlink() for p in paths):raise ValueError('Transit finance artifact and independent receipt required')
    if [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]!=[HASH,REVIEW_HASH]:raise ValueError('Exact independently reviewed Transit finance bytes required')
    if not transit_files(root):raise ValueError('Transit finance exact parent required')
    b,r=[json.loads(p.read_text()) for p in paths]
    if r['status']!='accepted' or r['bundleSha256']!=HASH or r['sourceSha256']!=SOURCE_HASH or b['sourceSha256']!=SOURCE_HASH or b['parentSha256']!=PARENT_HASH or b['publication']['allowed'] is not True or b['publication']['requiresMatchingIndependentReceipt'] is not True or b['publication']['consequentialAllegation'] is not False or b['publication']['reviewId']!=r['evidenceId'] or b['publication']['reviewedOn']!=r['reviewedOn']:raise ValueError('Transit finance publication review mismatch')
    return [p.relative_to(root).as_posix() for p in paths]

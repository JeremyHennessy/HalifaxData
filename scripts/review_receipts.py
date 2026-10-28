"""Public review receipts contain only review metadata, never private working notes."""
import re,datetime
BASE={'status','reviewer','reviewedOn','evidenceId','scope','limitations'}
FOUNDATION=BASE|{'bundleSha256','checks'}
TENDER=BASE|{'indexSha256','captureManifestSha256','orderedSourceDigest','fieldNames'}
MUNICIPAL=BASE|{'bundleSha256','captureManifestSha256','metadataSha256','checks'}
SUPPLIER=BASE|{'bundleSha256','captureManifestSha256','orderedSourceDigest','proposalSha256','checks'}
def validate_receipt(receipt,kind):
    if kind not in ('foundation','tender','supplier','municipal','reporting'):raise ValueError('Unknown review scope')
    expected={'foundation':FOUNDATION,'tender':TENDER,'supplier':SUPPLIER,'municipal':MUNICIPAL,'reporting':FOUNDATION}[kind]
    allowed=expected|({'supersedesBundleSha256'} if kind=='foundation' else set())
    if not isinstance(receipt,dict) or not expected.issubset(receipt) or not set(receipt).issubset(allowed):raise ValueError('Unexpected public review receipt fields')
    if receipt['status']!='accepted':raise ValueError('Review not accepted')
    for key in set(receipt)-{'limitations','checks','fieldNames'}:
        if not isinstance(receipt[key],str) or not receipt[key]:raise ValueError('Invalid review metadata')
    for key in ('bundleSha256','indexSha256','captureManifestSha256','orderedSourceDigest','supersedesBundleSha256','proposalSha256','metadataSha256'):
        if key in receipt and not re.fullmatch('[a-f0-9]{64}',receipt[key]):raise ValueError('Invalid review digest')
    for key in ('limitations','checks','fieldNames'):
        if key in receipt and (not isinstance(receipt[key],list) or not all(isinstance(x,str) for x in receipt[key])):raise ValueError('Invalid public review text')
    datetime.date.fromisoformat(receipt['reviewedOn'])
    return receipt

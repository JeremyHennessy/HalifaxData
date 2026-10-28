"""Strict field allowlist for the neutral public foundation, not arbitrary research JSON."""
SCHEMA={
'root':'schemaVersion asOf coverage sources evidenceRecords moneyFacts reportedSymbols investigations relationships',
'root.coverage':'complete fiscalFactCount guideSourceCount notes paymentFacts uniqueGuideURLs',
'root.sources[]':'id title url publisher group jurisdiction geography priority format inventoryId inventoryRow status limitations provenance accessClass investigationUse suggestedCadence',
'root.sources[].status':'registered acquired normalized published monitored',
'root.sources[].provenance':'type workbookSha256 originalVerificationClaim claimIndependentlyRechecked reviewedOn sourceSnapshotHash',
'root.evidenceRecords[]':'id sourceId title url sourceLocator reviewedOn verification sourceSnapshotHash limitations',
'root.moneyFacts[]':'id title entity jurisdiction metric period stage accountingBasis reportingPerimeter measureType rawValue unit currency multiplier evidenceId sourceId sourceLocator interpretation',
'root.moneyFacts[].period':'start end label asOf',
'root.reportedSymbols[]':'id interpretation metric period rawValue sourceId sourceLocator sourceSymbol stage',
'root.investigations[]':'id title question status classification publication summary whyFlagged calculation moneyFactIds evidenceIds confirmedFacts alternativeExplanations missingEvidence nextSteps chronology limitations responses',
'root.investigations[].publication':'allowed reviewId reviewType reviewedOn consequentialAllegation',
'root.investigations[].calculation':'operation inputIds resultRaw unit multiplier',
'root.investigations[].chronology[]':'date label sourceId dateType',
'root.investigations[].responses[]':'contactedByProject sourceId sourceLocator summary type',
'root.relationships[]':'confidence evidenceIds fromFactId id inferredPaymentLink method toFactId type',
}
def validate_public_shape(value,path='root'):
    if isinstance(value,dict):
        if path not in SCHEMA:raise ValueError('Unapproved public object: '+path)
        unknown=set(value)-set(SCHEMA[path].split())
        if unknown:raise ValueError('Unapproved public fields: '+path+' '+','.join(sorted(unknown)))
        for key,child in value.items():validate_public_shape(child,path+'.'+key)
    elif isinstance(value,list):
        for child in value:validate_public_shape(child,path+'[]')
    elif value is not None and not isinstance(value,(str,int,float,bool)):
        raise ValueError('Unsupported public value: '+path)
    return value

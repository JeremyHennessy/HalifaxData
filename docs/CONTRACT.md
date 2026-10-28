# Fresh evidence contract v1

`foundation.json` contains `schemaVersion`, `asOf`, `coverage`, `sources`, `evidenceRecords`, `moneyFacts`, `reportedSymbols`, `investigations`, `relationships`.

- sources: `{id,title,url,publisher,group,jurisdiction,geography,priority,format,inventoryId,inventoryRow,status:{registered,acquired,normalized,published,monitored},limitations[],provenance}`. Guide catalogue entries are references, not working integrations. Supplementary source documents have inventoryId null and do not inflate139 guide count.
- evidenceRecords: `{id,sourceId,title,url,sourceLocator,reviewedOn,verification,sourceSnapshotHash,limitations[]}`. Null binary hash means no retained source binary. Independent primary-text review is not replay-certified acquisition.
- moneyFacts: `{id,title,entity,jurisdiction,metric,period:{start,end,label,asOf},stage,accountingBasis,reportingPerimeter,measureType,rawValue,unit,currency,multiplier,evidenceId,sourceId,sourceLocator,interpretation}`. `rawValue` is decimal string; currency and bases must agree before subtraction. Flow and stock differ. Facts are NOT additive merely because displayed together.
- reportedSymbols: source dash retained as null numeric value, never zero.
- investigations: `{id,title,question,status,classification,publication:{allowed,reviewType,reviewedOn,consequentialAllegation},summary,whyFlagged,calculation:{operation,inputIds,resultRaw,unit,multiplier},moneyFactIds,evidenceIds,confirmedFacts[],alternativeExplanations[],missingEvidence[],nextSteps[],chronology[],limitations[]}`. Public neutral documented comparisons only; private automatic flags cannot pass public gate.
- relationships: explicit link type + reviewed source evidence; no name/amount coincidence joins.

First dataset is reconstructed from original workbook and independent primary-source research, not old application code, schema, UI or data outputs. No old application namespace or continuity requirement.

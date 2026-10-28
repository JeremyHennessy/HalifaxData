"""Static interchange contracts. Runtime admission is the pinned adapter boundary."""
from typing import TypedDict, Literal, NotRequired
Status=Literal['flagged_unreviewed','explained','insufficient_evidence']
class NativeCell(TypedDict, total=False):
    kind: Literal['pdf_table_cell','dataset_cell']
    page: int
    table: str
    row: int | str
    column: str
    rowId: str
    field: str
class Fact(TypedDict):
    id: str
    value: str | None
    sourceFactId: str
    sourceLocator: dict
    nativeCellLocator: NativeCell
    artifactSha256: str
    sourceSnapshotSha256: str
    scopeKey: str
    unit: str
    role: str
    currency: str | None
    financialBasisVerified: bool
    availability: str
    financialBasisId: NotRequired[str]
class Term(TypedDict):
    factId: str
    coefficient: Literal[-1,1]
class Basis(TypedDict):
    scopeKey: str
    unit: str
    nativeArithmeticDeclaration: str
    mappingConfirmed: bool
    componentSetComplete: bool
    financialBasisId: NotRequired[str]
class Rule(TypedDict):
    id: str
    version: Literal[1]
    operation: Literal['linear_identity']
    mode: Literal['source_native_arithmetic','monetary_comparison']
    left: list[Term]
    right: list[Term]
    basis: Basis
    alternatives: list[str]
    missingRecords: list[str]
class Calculation(TypedDict):
    operation: str
    left: str
    right: str
    residual: str
    tolerance: str
    exactEquality: bool
    unit: str
    meaning: str
class Result(TypedDict):
    ruleId: str
    ruleVersion: int
    ruleDeclarationSha256: str
    publicationAllowed: Literal[False]
    consequentialAllegation: Literal[False]
    statusScope: str
    mode: str
    inputFactIds: list[str]
    alternatives: list[str]
    missingRecords: list[str]
    snapshotBindings: list[dict]
    calculation: Calculation | None
    currency: str | None
    monetaryAmountEstablished: bool
    status: Status
    reasons: list[str]
class RunReport(TypedDict):
    schemaVersion: Literal['private-arithmetic-run-v1']
    engineVersion: str
    engineSourceSha256: str
    fixtureSha256: str
    publicationAllowed: Literal[False]
    operation: str
    results: list[Result]
    counts: dict[Status,int]
    limits: list[str]

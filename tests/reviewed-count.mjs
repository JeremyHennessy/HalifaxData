// Explicit release baseline, not inferred from the page under test.
// Update only when a separately reviewed grouped collection is added/removed.
export const REVIEWED_COLLECTION_BASELINE=19;
export const collectionCountPattern=(unavailable=0,sourcePage=false)=>new RegExp(`${REVIEWED_COLLECTION_BASELINE-unavailable} ${sourcePage?'review-bound collections':'reviewed evidence collections'}`);

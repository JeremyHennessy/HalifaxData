# Share an applied evidence view

Every rendered valid route has a compact “Share this view” control below its heading. It exposes a labelled read-only web address that retains the hash route, applied filters, selected record, reading depth and page number where those exist. Top-level transport/cache queries and URL credentials are omitted. Unsaved search-field edits are not applied, and the interface says so.

“Copy link” writes only that address through the browser clipboard API after an explicit click. If the API is missing or refuses the operation, the address is selected for the resident’s own Copy command. “Select link” is always available. No share provider, analytics request, external communication, account or persistent preference is introduced. The control does not read the clipboard.

The panel is an ordinary in-page region, not a modal. Close and Escape return focus to its trigger. It does not modify the URL, route state, evidence requests or browser history. Repeated pending clicks cannot issue duplicate writes; late clipboard completion cannot reopen or announce into a dismissed or replaced view. A browser clipboard operation already initiated by the resident cannot be cancelled by closing the panel.

A view link is not an immutable snapshot. Evidence may change in a later release, so the interface directs residents to the reviewed evidence download and receipt where provided. Sharing never certifies that a collection is currently available, independently verified again or current as of today. Existing unavailable/unknown states remain visible.

Unit tests cover URL boundaries, explicit copy, delayed completion, duplicate prevention, missing/denied API, manual selection and closed/replaced views. Browser journeys cover applied-filter restoration, unsaved edits, keyboard opening and Escape, Close, Back/Forward, failures, pending-copy navigation and responsive layout at 360/768/1440 pixels. Clipboard outcomes in these deterministic tests are controlled, not claims that every device permits automatic copy.

All evidence artifacts, review receipts, source references, collection counts and collector controls remain unchanged. A small Transit grammar fix uses “1 matching evidence row.”

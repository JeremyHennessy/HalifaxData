// Explicit generated-domain lifecycle states for HalifaxData.
// Loaded after app.js so generated-artifact lifecycle is visible without
// changing the established light dashboard layout or analytical semantics.

var HALIFAX_DOMAIN_LIFECYCLE = {};

function normalizeLifecycleStatus(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[ -]+/g, '_');
  if (normalized === 'ok' || normalized === 'ready') return 'ready';
  if (normalized === 'pending_release') return 'pending_release';
  if (normalized === 'validation_pending' || normalized === 'pending_validation') return 'validation_pending';
  if (normalized === 'missing') return 'missing';
  if (normalized === 'error' || normalized === 'failed') return 'error';
  return null;
}

function lifecycleRecord(key) {
  const record = HALIFAX_DOMAIN_LIFECYCLE[key];
  return record && typeof record === 'object' ? record : null;
}

function resolvedGeneratedLifecycle(key) {
  const ds = datasetStatus(key);
  const manifest = lifecycleRecord(key);
  const declared = normalizeLifecycleStatus(manifest?.status);

  // Runtime load failures always win: the live application cannot use an
  // artifact simply because a manifest says it should exist.
  if (ds.status === 'error') {
    return { status: 'error', text: 'Error', tone: 'bad', detail: ds.error || 'Artifact failed to load' };
  }
  if (declared === 'error') {
    return { status: 'error', text: 'Error', tone: 'bad', detail: manifest?.note || 'Artifact validation failed' };
  }
  if (declared === 'validation_pending') {
    return { status: 'validation_pending', text: 'Validation pending', tone: 'warn', detail: manifest?.note || 'Artifact is not release-approved yet' };
  }
  if (declared === 'pending_release') {
    return { status: 'pending_release', text: 'Pending release', tone: 'info', detail: manifest?.note || 'Validated artifact has not been released yet' };
  }
  if (ds.status === 'missing') {
    return { status: 'missing', text: 'Missing', tone: 'muted', detail: 'Generated artifact is not present at the expected path' };
  }
  if (ds.status === 'ready') {
    const rows = getRows(ds.data).length;
    return { status: 'ready', text: `Ready · ${numberFmt.format(rows)} rows`, tone: 'good', detail: manifest?.note || 'Generated artifact loaded successfully' };
  }
  return { status: 'missing', text: 'Missing', tone: 'muted', detail: 'Generated artifact state is unavailable' };
}

// app.js declares generatedStatus as a global function; replacing the binding
// keeps every existing coverage card/domain view on one consistent status model.
generatedStatus = function generatedStatusWithLifecycle(key) {
  return resolvedGeneratedLifecycle(key);
};

function applySignalsLifecycleNotice() {
  if (location.hash.slice(1) !== 'signals') return;
  const pageStack = document.querySelector('#content .page-stack');
  if (!pageStack || pageStack.querySelector('[data-generated-signals-lifecycle]')) return;
  const lifecycle = resolvedGeneratedLifecycle('signals');
  if (lifecycle.status === 'ready') return;
  const notice = document.createElement('div');
  notice.className = 'notice';
  notice.dataset.generatedSignalsLifecycle = lifecycle.status;
  const strong = document.createElement('strong');
  strong.textContent = `Generated signals: ${lifecycle.text}`;
  const span = document.createElement('span');
  span.textContent = lifecycle.detail;
  notice.append(strong, span);
  pageStack.prepend(notice);
}

// The Signals renderer is owned by app.js and may be invoked through its own
// function binding. Observe the rendered content instead of relying on a
// cross-script renderer override; this preserves the existing calculated queue
// and annotates only the lifecycle of the separate generated-signals artifact.
const lifecycleContentRoot = document.querySelector('#content');
if (lifecycleContentRoot) {
  new MutationObserver(() => applySignalsLifecycleNotice()).observe(lifecycleContentRoot, {
    childList: true,
    subtree: true
  });
}
window.addEventListener('hashchange', () => queueMicrotask(applySignalsLifecycleNotice));

fetch('./data/generated/domain_ingestion_status.json', { cache: 'no-store' })
  .then(response => response.ok ? response.json() : null)
  .then(payload => {
    const records = Array.isArray(payload?.records) ? payload.records : [];
    HALIFAX_DOMAIN_LIFECYCLE = Object.fromEntries(
      records
        .filter(record => record && record.domain)
        .map(record => [String(record.domain), record])
    );
    if (typeof state !== 'undefined' && state.compensation && typeof render === 'function') render();
    queueMicrotask(applySignalsLifecycleNotice);
  })
  .catch(() => {
    // The runtime artifact fetch remains authoritative. A missing lifecycle
    // manifest must never make an otherwise valid dataset unavailable.
    queueMicrotask(applySignalsLifecycleNotice);
  });

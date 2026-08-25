/* Explicit Build 005 route dispatch.
 * Core chrome/rendering runs first; only the three Build 005 domain content panes are replaced.
 */
const build005BaseRender = render;
const build005SpendRenderer = renderSpending;
const build005ProcurementRenderer = typeof renderProcurement === 'function' ? renderProcurement : null;
const build005CapitalRenderer = typeof renderCapital === 'function' ? renderCapital : null;
const build005DomainBinder = bindViewEvents;

render = function renderBuild005Routes() {
  build005BaseRender();
  const renderer = state.view === 'spending' ? build005SpendRenderer
    : state.view === 'vendors' ? build005ProcurementRenderer
    : state.view === 'projects' ? build005CapitalRenderer
    : null;
  if (!renderer) return;
  try {
    $('#content').innerHTML = renderer();
    build005DomainBinder();
    const filterbar = $('.filterbar');
    if (filterbar) filterbar.hidden = true;
  } catch (error) {
    console.error('Build 005 domain renderer failed', state.view, error);
    $('#content').innerHTML = `<div class="error-state"><strong>${escapeHtml(state.view)} view failed</strong><p>${escapeHtml(error?.message || String(error))}</p><p>The dashboard will not substitute another domain's content when this renderer fails.</p></div>`;
  }
};

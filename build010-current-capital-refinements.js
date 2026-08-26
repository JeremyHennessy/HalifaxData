/* Build 010 interaction refinement.
 * Bind only controls/cards injected after Build 009's render pass. This avoids
 * double-binding existing investigation cards on unrelated routes.
 */

b10BindEvents = function b10BindEventsRefined() {
  const search = $('#b10-capital-search');
  if (search) search.addEventListener('change', event => {
    state.build010CapitalQuery = event.target.value;
    render();
  });
  const category = $('#b10-capital-category');
  if (category) category.addEventListener('change', event => {
    state.build010CapitalCategory = event.target.value;
    render();
  });
  $$('#content .b10-current-capital [data-build010-project]').forEach(row =>
    row.addEventListener('click', () => b10ShowProject(row.dataset.build010Project))
  );
  $$('#content .b10-current-capital [data-build008-investigation-id]').forEach(element =>
    element.addEventListener('click', () => b8ShowInvestigation(element.dataset.build008InvestigationId))
  );
};

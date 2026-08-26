/* Build 010 live-startup guard.
 * current_capital.json is independently fetched and can arrive before the required
 * compensation/source-registry Promise on a CDN-hosted build. Suppress only those
 * premature renders; the required-data initializer will call render again after
 * both required objects are installed.
 */

const build010RequiredDataRender = render;
render = function renderAfterRequiredBuild010Data() {
  if (!state.compensation || !state.sources) return;
  return build010RequiredDataRender();
};

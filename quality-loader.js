/* Build 005 domain quality loader.
 *
 * This script executes before app.js. It preserves the Build 004 budget path,
 * but prevents newer optional domain artifacts from being downloaded unless
 * data/domain_quality.json explicitly marks the domain as ready.
 *
 * A checked-in JSON file is not, by itself, permission to render analytical
 * facts. If the quality manifest cannot be loaded, new Build 005 domains fail
 * closed and app.js receives a synthetic 404 for those optional artifacts.
 */
(() => {
  const nativeFetch = window.fetch.bind(window);
  const gatedPaths = new Map([
    ['/data/generated/spending.json', 'spending'],
    ['/data/generated/procurement.json', 'procurement'],
    ['/data/generated/capital.json', 'capital'],
    ['/data/generated/financials.json', 'financials'],
    ['/data/generated/council.json', 'council'],
    ['/data/generated/signals.json', 'signals']
  ]);

  const telemetry = {
    manifest_status: 'loading',
    allowed: [],
    blocked: [],
    manifest_error: null
  };
  window.HalifaxDataQualityGate = telemetry;

  const qualityPromise = nativeFetch('./data/domain_quality.json', { cache: 'no-store' })
    .then(response => {
      if (!response.ok) throw new Error(`Domain quality manifest failed to load (${response.status})`);
      return response.json();
    })
    .then(manifest => {
      if (!manifest || typeof manifest !== 'object' || !manifest.domains || typeof manifest.domains !== 'object') {
        throw new Error('Domain quality manifest is missing its domains object');
      }
      telemetry.manifest_status = 'ready';
      return manifest;
    })
    .catch(error => {
      telemetry.manifest_status = 'error';
      telemetry.manifest_error = error instanceof Error ? error.message : String(error);
      throw error;
    });

  window.HalifaxDataQualityPromise = qualityPromise;

  window.fetch = async function qualityGatedFetch(input, init) {
    let url;
    try {
      const raw = input instanceof Request ? input.url : String(input);
      url = new URL(raw, window.location.href);
    } catch {
      return nativeFetch(input, init);
    }

    const match = [...gatedPaths.entries()].find(([suffix]) => url.pathname.endsWith(suffix));
    if (!match) return nativeFetch(input, init);

    const [pathSuffix, domain] = match;
    let manifest;
    try {
      manifest = await qualityPromise;
    } catch {
      telemetry.blocked.push({ domain, path: pathSuffix, reason: 'quality-manifest-unavailable' });
      return new Response('', { status: 404, statusText: 'Blocked by HalifaxData quality gate' });
    }

    const entry = manifest.domains?.[domain];
    if (entry?.status !== 'ready') {
      telemetry.blocked.push({ domain, path: pathSuffix, reason: entry?.status || 'quality-status-missing' });
      return new Response('', { status: 404, statusText: 'Blocked by HalifaxData quality gate' });
    }

    telemetry.allowed.push({ domain, path: pathSuffix, reason: 'quality-status-ready' });
    return nativeFetch(input, init);
  };
})();

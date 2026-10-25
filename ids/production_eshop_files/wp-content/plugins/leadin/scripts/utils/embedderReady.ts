import Raven from '../lib/Raven';

const POLL_INTERVAL_MS = 250;
const DEFAULT_TIMEOUT_MS = 15000;

const EMBEDDER_SCRIPT_SELECTOR = 'script[src*="/integrated-app-embedder/"]';

export function isEmbedderReady() {
  const { IntegratedAppEmbedder, IntegratedAppOptions }: any = window;

  return !!IntegratedAppEmbedder && typeof IntegratedAppOptions === 'function';
}

function getEmbedderDiagnostics() {
  const scriptTag = document.querySelector(
    EMBEDDER_SCRIPT_SELECTOR
  ) as HTMLScriptElement | null;

  return {
    hasScriptTag: !!scriptTag,
    scriptSrc: scriptTag ? scriptTag.src : null,
    readyState: document.readyState,
    hasEmbedder: !!(window as any).IntegratedAppEmbedder,
    typeofOptions: typeof (window as any).IntegratedAppOptions,
  };
}

/**
 * The embedder script is a cross-origin script from js.hubspot.com, and nothing
 * makes the widgets wait for it: they read its globals off `window` the moment a
 * control renders. On sites where an asset pipeline defers it, or where the
 * editor is simply slow, the widget can lose that race and fail permanently even
 * though the script arrives seconds later.
 *
 * Resolves true as soon as the globals appear, or false once the wait is up.
 */
export function whenEmbedderReady(
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): { promise: Promise<boolean>; cancel: () => void } {
  let intervalId: number | undefined;

  const cancel = () => {
    if (intervalId !== undefined) {
      window.clearInterval(intervalId);
      intervalId = undefined;
    }
  };

  const promise = new Promise<boolean>(resolve => {
    if (isEmbedderReady()) {
      console.info('HubSpot plugin - embedder ready immediately');
      resolve(true);
      return;
    }

    const startedAt = Date.now();

    console.info(
      `HubSpot plugin - waiting up to ${timeoutMs}ms for embedder script`,
      getEmbedderDiagnostics()
    );

    intervalId = window.setInterval(() => {
      const waitedMs = Date.now() - startedAt;

      if (isEmbedderReady()) {
        cancel();
        console.info(`HubSpot plugin - embedder ready after ${waitedMs}ms`);
        resolve(true);
      } else if (waitedMs >= timeoutMs) {
        cancel();
        resolve(false);
      }
    }, POLL_INTERVAL_MS);
  });

  return { promise, cancel };
}

/**
 * Reports a give-up so these failures stop being invisible. Until now the widget
 * rendered its error box without telling anyone, so the only signal we had for
 * this whole class of problem came from unrelated admin pages.
 *
 * Uses captureException rather than captureMessage on purpose: Raven is
 * configured with a shouldSendCallback that drops any event whose culprit does
 * not match plugins/leadin/, and captureMessage does not attach a stack trace,
 * so it has no culprit to match on.
 */
export function reportEmbedderUnavailable(waitedMs: number) {
  const diagnostics = getEmbedderDiagnostics();

  console.error(
    `HubSpot plugin - embedder unavailable after ${waitedMs}ms`,
    diagnostics
  );

  Raven.captureException(new Error('Leadin embedder unavailable'), {
    fingerprint: ['EMBEDDER_UNAVAILABLE'],
    extra: { waitedMs, ...diagnostics },
  });
}

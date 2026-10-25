import React, { useEffect, useRef } from 'react';
import UIOverlay from '../UIComponents/UIOverlay';
import {
  formsScript,
  formsScriptPayload,
  hublet as region,
} from '../../constants/leadinConfig';
import PreviewDisabled from '../Common/PreviewDisabled';

export default function PreviewForm({
  portalId,
  formId,
  fullSiteEditor,
  embedVersion,
}: {
  portalId: number;
  formId: string;
  fullSiteEditor?: boolean;
  embedVersion?: string;
}) {
  const isFormV4 = embedVersion === 'v4';

  const inputEl = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (inputEl.current) {
      //@ts-expect-error Hubspot global
      const hbspt = window.parent.hbspt || window.hbspt;
      inputEl.current.innerHTML = '';
      const isQa = formsScriptPayload.includes('qa');
      if (isFormV4) {
        // WP 6.3+ renders the block-editor canvas inside an iframe
        // (iframe[name="editor-canvas"]). The block's DOM lives in that iframe,
        // but our React runs in the top window's JS realm, so the global
        // `document` here is the TOP frame's document, not the iframe's. The v4
        // forms embed script scans its executing context's local `document`
        // (getElementsByClassName('hs-form-frame') + MutationObserver on
        // document.body) and has no programmatic create() API. So both the
        // placeholder and the embed script must live in the IFRAME's document
        // for hydration to happen. Route everything through the placeholder's
        // ownerDocument to target the correct realm.
        const doc = inputEl.current.ownerDocument;

        const container = doc.createElement('div');
        container.classList.add('hs-form-frame');
        container.dataset.region = region;
        container.dataset.formId = formId;
        container.dataset.portalId = portalId.toString();
        container.dataset.env = isQa ? 'qa' : '';
        inputEl.current.appendChild(container);

        // Derive the portal-specific embed URL from the v2 script URL: take its
        // host (origin) so we follow whatever host a PHP filter applies to the
        // v2 URL, and append the v4 embed path. Inject it into the iframe's
        // document so it executes in the iframe window and scans the iframe
        // document where the placeholder is. Running post-mount means doc.body
        // exists, so the script's MutationObserver initializes without the
        // "not a Node" crash seen when it's loaded too early in the iframe
        // head. One copy per iframe window is enough — its MutationObserver
        // hydrates any later placeholders too.
        const v4EmbedUrl = formsScript
          ? `${new URL(formsScript).origin}/forms/embed/${portalId}.js`
          : '';
        const v4AlreadyPresent =
          !v4EmbedUrl || !!doc.querySelector(`script[src="${v4EmbedUrl}"]`);
        if (v4EmbedUrl && !v4AlreadyPresent) {
          const embedScript = doc.createElement('script');
          embedScript.src = v4EmbedUrl;
          embedScript.defer = true;
          doc.body.appendChild(embedScript);
        }
      } else {
        const additionalParams = isQa ? { env: 'qa' } : {};

        hbspt.forms.create({
          portalId,
          formId,
          region,
          target: `#${inputEl.current.id}`,
          ...additionalParams,
        });
      }
    }
  }, [formId, portalId, inputEl, isFormV4]);

  if (fullSiteEditor) {
    return <PreviewDisabled />;
  }

  return <UIOverlay ref={inputEl} id={`hbspt-previewform-${formId}`} />;
}

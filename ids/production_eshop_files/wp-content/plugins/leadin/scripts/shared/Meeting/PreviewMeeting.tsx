import React, { Fragment, useEffect, useRef } from 'react';
import UIOverlay from '../UIComponents/UIOverlay';
import PreviewDisabled from '../Common/PreviewDisabled';
import { meetingsScript } from '../../constants/leadinConfig';

interface IPreviewForm {
  url: string;
  fullSiteEditor?: boolean;
}

type Hbspt = { meetings?: { create: (selector: string) => void } };

function getHbspt(win: Window | null): Hbspt | undefined {
  if (!win) {
    return undefined;
  }
  return ((win as unknown) as { hbspt?: Hbspt }).hbspt;
}

export default function PreviewForm({ url, fullSiteEditor }: IPreviewForm) {
  const inputEl = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = inputEl.current;
    if (!el) {
      return;
    }

    // WP 6.3+ renders the block-editor canvas inside an iframe
    // (iframe[name="editor-canvas"]). The `.meetings-iframe-container` lives in
    // that iframe's document, but `hbspt.meetings.create(selector)` resolves the
    // selector against the document of the realm `hbspt` belongs to. The
    // top-frame hbspt therefore scans the top document and never finds the
    // container, so the preview stays blank. Run the embed in the container's
    // own realm: reuse that realm's hbspt if it is already present, otherwise
    // inject MeetingsEmbedCode into that document and create once it loads.
    // (Mirrors the v4 form block fix.)
    const doc = el.ownerDocument;
    const win = doc.defaultView;

    const create = () => {
      const hbspt =
        getHbspt(win) || getHbspt(window.parent) || getHbspt(window);
      if (hbspt && hbspt.meetings) {
        hbspt.meetings.create('.meetings-iframe-container');
      }
    };

    const realmHbspt = getHbspt(win);
    if (realmHbspt && realmHbspt.meetings) {
      create();
      return;
    }

    const existing = doc.querySelector(`script[src="${meetingsScript}"]`);
    if (existing) {
      existing.addEventListener('load', create);
      return;
    }

    const script = doc.createElement('script');
    script.src = meetingsScript;
    script.defer = true;
    script.addEventListener('load', create);
    doc.body.appendChild(script);
  }, [url]);

  if (fullSiteEditor) {
    return <PreviewDisabled />;
  }

  return (
    <Fragment>
      {url && (
        <UIOverlay
          ref={inputEl}
          className="meetings-iframe-container"
          data-src={`${url}?embed=true`}
        ></UIOverlay>
      )}
    </Fragment>
  );
}

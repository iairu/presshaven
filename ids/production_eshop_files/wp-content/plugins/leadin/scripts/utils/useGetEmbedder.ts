import React from 'react';
import { useEffect, useRef, useState } from 'react';
import { __ } from '@wordpress/i18n';
import { fetchAccessToken } from '../api/wordpressApiClient';
import { getOrCreateBackgroundApp } from './backgroundAppUtils';
import { isRefreshTokenAvailable } from './isRefreshTokenAvailable';
import { reportEmbedderUnavailable, whenEmbedderReady } from './embedderReady';
import ErrorHandler from '../shared/Common/ErrorHandler';

export function useGetEmbedder() {
  const [embedder, setEmbedder] = useState<any>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const cancelWaitRef = useRef<(() => void) | null>(null);
  const mountedRef = useRef(true);

  const loadEmbedder = () => {
    fetchAccessToken()
      .then(
        ({
          accessToken,
          expiresIn,
        }: {
          accessToken: string;
          expiresIn: number;
        }) => {
          if (!mountedRef.current) return;

          const startedAt = Date.now();
          const { promise, cancel } = whenEmbedderReady();

          cancelWaitRef.current = cancel;

          return promise.then(isReady => {
            cancelWaitRef.current = null;

            if (!mountedRef.current) return;

            const app = isReady
              ? getOrCreateBackgroundApp(accessToken, expiresIn)
              : null;

            if (app) {
              console.info('HubSpot plugin - embedder ready, rendering widget');
              setEmbedder(app);
            } else {
              reportEmbedderUnavailable(Date.now() - startedAt);
              setErrorStatus(500);
            }
          });
        }
      )
      .catch((err: any) => {
        if (!mountedRef.current) return;

        console.error(
          'HubSpot plugin - access token request failed',
          (err && err.status) || 'no status'
        );
        setErrorStatus((err && err.status) || 500);
      });
  };

  useEffect(() => {
    if (isRefreshTokenAvailable()) {
      loadEmbedder();
    }

    return () => {
      mountedRef.current = false;
      if (cancelWaitRef.current) {
        cancelWaitRef.current();
        cancelWaitRef.current = null;
      }
    };
  }, []);

  const errorElement =
    errorStatus !== null
      ? React.createElement(ErrorHandler, {
          status: errorStatus,
          resetErrorState: () => {
            setErrorStatus(null);
            loadEmbedder();
          },
          errorInfo: {
            header: __('Unable to load HubSpot', 'leadin'),
            message: __(
              'There was a problem connecting to HubSpot. Please try again.',
              'leadin'
            ),
            action: __('Retry', 'leadin'),
          },
        })
      : null;

  return {
    embedder,
    errorElement,
    isLoading:
      isRefreshTokenAvailable() && embedder === null && errorStatus === null,
  };
}

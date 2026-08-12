import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, predictImage } from "../../lib/api/client";
import type { PredictionResponse } from "../../lib/api/types";

const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const MAX_UPLOAD_BYTES = 12 * 1024 * 1024;

export type ReviewPhase = "empty" | "ready" | "loading" | "result" | "error";

interface ReviewSessionState {
  phase: ReviewPhase;
  file: File | null;
  previewUrl: string | null;
  result: PredictionResponse | null;
  fieldError: string | null;
  requestError: string | null;
}

const INITIAL_STATE: ReviewSessionState = {
  phase: "empty",
  file: null,
  previewUrl: null,
  result: null,
  fieldError: null,
  requestError: null,
};

export function useReviewSession() {
  const [state, setState] = useState<ReviewSessionState>(INITIAL_STATE);
  const previewRef = useRef<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);

  const releasePreview = useCallback(() => {
    if (previewRef.current) {
      URL.revokeObjectURL(previewRef.current);
      previewRef.current = null;
    }
  }, []);

  const cancelRequest = useCallback(() => {
    requestVersion.current += 1;
    requestRef.current?.abort();
    requestRef.current = null;
  }, []);

  const selectFile = useCallback(
    (file: File | null) => {
      cancelRequest();
      releasePreview();
      if (!file) {
        setState(INITIAL_STATE);
        return;
      }
      if (!ALLOWED_TYPES.has(file.type)) {
        setState({
          ...INITIAL_STATE,
          fieldError: "僅接受 PNG、JPEG 或 WebP 影像。",
        });
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setState({
          ...INITIAL_STATE,
          fieldError: "影像大小不可超過 12 MiB。",
        });
        return;
      }
      const previewUrl = URL.createObjectURL(file);
      previewRef.current = previewUrl;
      setState({
        phase: "ready",
        file,
        previewUrl,
        result: null,
        fieldError: null,
        requestError: null,
      });
    },
    [cancelRequest, releasePreview],
  );

  const submitPrediction = useCallback(async () => {
    if (!state.file || state.phase === "loading") {
      return;
    }
    cancelRequest();
    const controller = new AbortController();
    requestRef.current = controller;
    const version = requestVersion.current;
    setState((current) => ({
      ...current,
      phase: "loading",
      result: null,
      requestError: null,
    }));
    try {
      const result = await predictImage(state.file, controller.signal);
      if (requestVersion.current !== version) {
        return;
      }
      requestRef.current = null;
      setState((current) => ({ ...current, phase: "result", result }));
    } catch (error) {
      if (controller.signal.aborted || requestVersion.current !== version) {
        return;
      }
      requestRef.current = null;
      const message =
        error instanceof ApiError && error.message
          ? error.message
          : "分割暫時無法完成，請重新嘗試。";
      setState((current) => ({
        ...current,
        phase: "error",
        result: null,
        requestError: message,
      }));
    }
  }, [cancelRequest, state.file, state.phase]);

  useEffect(
    () => () => {
      requestRef.current?.abort();
      releasePreview();
    },
    [releasePreview],
  );

  return { ...state, selectFile, submitPrediction };
}

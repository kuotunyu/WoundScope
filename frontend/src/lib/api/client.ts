import type { ApiErrorBody, ModelStatus } from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function readApiError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as ApiErrorBody;
    if (payload.detail?.code && payload.detail.message) {
      return new ApiError(payload.detail.code, payload.detail.message, response.status);
    }
  } catch {
    // The public error remains fixed when a response does not match the API schema.
  }
  return new ApiError("REQUEST_FAILED", "WoundScope 服務暫時無法完成要求。", response.status);
}

export async function fetchModelStatus(signal?: AbortSignal): Promise<ModelStatus> {
  try {
    const response = await fetch("/api/model-status", {
      headers: { Accept: "application/json" },
      signal,
    });
    if (!response.ok) {
      throw await readApiError(response);
    }
    return (await response.json()) as ModelStatus;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("NETWORK_ERROR", "無法連線至本機 WoundScope 服務。", 0);
  }
}

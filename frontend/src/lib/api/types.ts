export type RuntimeMode = "showcase" | "local_review";

export interface ModelStatus {
  mode: RuntimeMode;
  model_available: boolean;
  calibration_available: boolean;
  model_label: string;
  model_sha256_prefix: string | null;
  provider: string;
  message: string;
}

export interface ApiErrorBody {
  detail?: {
    code?: string;
    message?: string;
  };
}

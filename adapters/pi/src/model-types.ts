import type { ThinkingLevel } from "@earendil-works/pi-agent-core";

export interface ModelSelection {
  provider: string;
  model: string;
  thinking: ThinkingLevel;
}

export type CollectorRole = "minimax" | "glm-turbo" | "glm-5.2";

export interface CollectorSelection {
  role: CollectorRole;
  model: ModelSelection;
}

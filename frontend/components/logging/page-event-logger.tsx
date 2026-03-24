"use client";

import { useEffect } from "react";

import { logFrontendEvent } from "@/lib/logger";

type PageEventLoggerProps = {
  event: string;
  payload?: Record<string, unknown>;
};

export function PageEventLogger({ event, payload }: PageEventLoggerProps) {
  const serializedPayload = JSON.stringify(payload ?? {});

  useEffect(() => {
    logFrontendEvent(event, payload ?? {});
  }, [event, serializedPayload]);

  return null;
}

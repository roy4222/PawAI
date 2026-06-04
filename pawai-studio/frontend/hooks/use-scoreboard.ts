"use client";

import { useEffect, useState } from "react";

import type { ScoreboardResponse } from "@/contracts/types";
import { getGatewayHttpUrl } from "@/lib/gateway-url";

interface UseScoreboardResult {
  data: ScoreboardResponse | null;
  loading: boolean;
  error: string | null;
}

export function useScoreboard(): UseScoreboardResult {
  const [data, setData] = useState<ScoreboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchScoreboard() {
      try {
        const response = await fetch(`${getGatewayHttpUrl()}/api/scoreboard`);

        if (!response.ok) {
          throw new Error(`Scoreboard request failed: ${response.status}`);
        }

        const scoreboard = (await response.json()) as ScoreboardResponse;

        if (!cancelled) {
          setData(scoreboard);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setData(null);
          setError(err instanceof Error ? err.message : "Failed to load scoreboard");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchScoreboard();

    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error };
}

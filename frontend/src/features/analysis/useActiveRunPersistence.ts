import { useState, useCallback } from "react";

export function useActiveRunPersistence(topicId: string) {
  const storageKey = `activeAnalysisRun_${topicId}`;

  const [activeRunId, setActiveRunIdRaw] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(storageKey);
    } catch {
      return null;
    }
  });

  const setActiveRunId = useCallback(
    (id: string | null) => {
      try {
        if (id) {
          sessionStorage.setItem(storageKey, id);
        } else {
          sessionStorage.removeItem(storageKey);
        }
      } catch {
        // sessionStorage may be unavailable (private browsing, quota, etc.)
      }
      setActiveRunIdRaw(id);
    },
    [storageKey],
  );

  const clearStorage = useCallback(() => {
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      // silent
    }
  }, [storageKey]);

  return { activeRunId, setActiveRunId, clearStorage };
}

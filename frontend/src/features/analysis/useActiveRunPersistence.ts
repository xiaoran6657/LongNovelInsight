import { useState, useEffect, useCallback } from "react";

export function useActiveRunPersistence(topicId: string) {
  const storageKey = `activeAnalysisRun_${topicId}`;

  const [activeRunId, setActiveRunIdRaw] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(storageKey);
    } catch {
      return null;
    }
  });

  // Re-read sessionStorage when topicId (and therefore storageKey) changes.
  // This handles navigation between topics: the new topic's stored run is loaded,
  // and the old topic's run is dropped from React state.
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(storageKey);
      setActiveRunIdRaw(stored);
    } catch {
      setActiveRunIdRaw(null);
    }
  }, [storageKey]);

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

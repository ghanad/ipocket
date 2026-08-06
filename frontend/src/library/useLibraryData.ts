import { useCallback, useEffect, useState } from "react";

import { fetchLibraryItems } from "./api";
import type { LibraryResponse } from "./types";

export function useLibraryData<T>(
  endpoint: string,
  entity: string,
  onPermissionChange: (canEdit: boolean) => void,
) {
  const [items, setItems] = useState<T[]>([]);
  const [metadata, setMetadata] = useState<LibraryResponse<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(
    async (showLoading = true) => {
      if (showLoading) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const response = await fetchLibraryItems<T>(endpoint, entity);
        setItems(response.items);
        setMetadata(response);
        onPermissionChange(response.can_edit);
      } catch {
        setLoadError(`${entity[0].toUpperCase()}${entity.slice(1)} could not be loaded. Please try again.`);
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [endpoint, entity, onPermissionChange],
  );

  useEffect(() => {
    void load();
  }, [load]);

  return { items, metadata, loading, loadError, load };
}

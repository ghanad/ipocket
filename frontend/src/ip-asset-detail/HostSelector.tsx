import { useMemo, useState } from "react";

import type { HostOption } from "./types";

export function HostSelector({
  hosts,
  value,
  onChange,
}: {
  hosts: HostOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  const [query, setQuery] = useState("");
  const visible = useMemo(
    () =>
      hosts.filter((host) =>
        host.name.toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [hosts, query],
  );
  return (
    <label className="field">
      <span>Host</span>
      <input
        className="input host-select-search"
        type="search"
        aria-label="Search hosts"
        placeholder="Search and select host"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <select
        className="select"
        aria-label="Host"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Unassigned</option>
        {visible.map((host) => (
          <option key={host.id} value={host.id}>
            {host.name}
          </option>
        ))}
      </select>
      {visible.length === 0 && (
        <p className="ip-drawer-helper">No matching hosts.</p>
      )}
    </label>
  );
}

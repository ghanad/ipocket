import {
  type FocusEvent,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

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
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedHost = useMemo(
    () => hosts.find((host) => String(host.id) === String(value)),
    [hosts, value],
  );

  const [query, setQuery] = useState(selectedHost ? selectedHost.name : "");

  useEffect(() => {
    if (!isOpen) {
      setQuery(selectedHost ? selectedHost.name : "");
    }
  }, [selectedHost, isOpen]);

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term || (selectedHost && term === selectedHost.name.toLowerCase())) {
      return hosts;
    }
    return hosts.filter((host) =>
      host.name.toLowerCase().includes(term),
    );
  }, [hosts, query, selectedHost]);

  const selectHost = (hostId: string) => {
    onChange(hostId);
    const chosen = hosts.find((h) => String(h.id) === String(hostId));
    setQuery(chosen ? chosen.name : "");
    setIsOpen(false);
  };

  const handleBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (
      event.relatedTarget instanceof Node &&
      containerRef.current?.contains(event.relatedTarget)
    ) {
      return;
    }
    setIsOpen(false);
    setQuery(selectedHost ? selectedHost.name : "");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setIsOpen(false);
      setQuery(selectedHost ? selectedHost.name : "");
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        return;
      }
      if (visible.length > 0) {
        selectHost(String(visible[0].id));
      }
    } else if (event.key === "ArrowDown" && !isOpen) {
      setIsOpen(true);
    }
  };

  return (
    <div className="field" ref={containerRef} onBlur={handleBlur}>
      <span>Host</span>
      <div className="host-select-combobox">
        <input
          ref={inputRef}
          className="input host-select-search"
          type="search"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-label="Search hosts"
          placeholder="Search and select host"
          value={query}
          onFocus={() => {
            setIsOpen(true);
          }}
          onClick={() => {
            setIsOpen(true);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
        />
        <select
          className="host-select-native"
          aria-label="Host"
          value={value}
          onChange={(event) => selectHost(event.target.value)}
          tabIndex={-1}
          aria-hidden="true"
          hidden
        >
          <option value="">{selectedHost ? selectedHost.name : "Unassigned"}</option>
        </select>
        {isOpen && (
          <div className="host-select-dropdown" role="listbox">
            <button
              type="button"
              role="option"
              aria-selected={!value}
              className={`host-select-option ${!value ? "is-selected" : ""}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => selectHost("")}
            >
              Unassigned
            </button>
            {visible.map((host) => {
              const isSelected = String(host.id) === String(value);
              return (
                <button
                  key={host.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`host-select-option ${isSelected ? "is-selected" : ""}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => selectHost(String(host.id))}
                >
                  {host.name}
                </button>
              );
            })}
            {visible.length === 0 && (
              <p className="ip-drawer-helper" style={{ margin: "8px 10px" }}>
                No matching hosts.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

import {
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

interface ExportDropdownProps {
  csvUrl: string;
  jsonUrl: string;
  totalCount?: number;
  onExportStarted?: () => void;
}

function DownloadIcon() {
  return (
    <svg
      className="export-dropdown-icon"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2" />
      <path d="M8 2.5v7m0 0-2.5-2.5M8 9.5l2.5-2.5" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg
      className="export-dropdown-chevron"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m3 4.5 3 3 3-3" />
    </svg>
  );
}

function CsvFileIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 3.5A1.5 1.5 0 0 1 5.5 2h6l5 5v9.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 16.5z" />
      <path d="M11.5 2v5.5H17" />
      <path d="M7 11h6M7 14h6" />
    </svg>
  );
}

function JsonFileIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 3.5A1.5 1.5 0 0 1 5.5 2h6l5 5v9.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 16.5z" />
      <path d="M11.5 2v5.5H17" />
      <path d="M7.5 11c-.5.5-.5 1.5 0 2M12.5 11c.5.5.5 1.5 0 2" />
    </svg>
  );
}

export function ExportDropdown({
  csvUrl,
  jsonUrl,
  totalCount,
  onExportStarted,
}: ExportDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    // @ts-expect-error KeyboardEvent signature compatible
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      // @ts-expect-error KeyboardEvent signature compatible
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen(true);
    }
  }

  function handleSelect() {
    setOpen(false);
    onExportStarted?.();
  }

  return (
    <div className="export-dropdown" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className="btn export-dropdown-trigger"
        aria-label="Export options"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={handleTriggerKeyDown}
      >
        <DownloadIcon />
        <span>Export</span>
        <ChevronDownIcon />
      </button>

      {open && (
        <div
          className="export-dropdown-menu"
          role="menu"
          aria-label="Export formats"
        >
          <div className="export-dropdown-header">
            <span>Export Filtered Assets</span>
            {totalCount !== undefined && (
              <span className="export-dropdown-count">
                {totalCount} {totalCount === 1 ? "asset" : "assets"}
              </span>
            )}
          </div>

          <a
            className="export-dropdown-item"
            href={csvUrl}
            download="ip-assets.csv"
            role="menuitem"
            aria-label="Export as CSV"
            onClick={handleSelect}
          >
            <div className="export-dropdown-item-icon export-icon-csv">
              <CsvFileIcon />
            </div>
            <div className="export-dropdown-item-content">
              <div className="export-dropdown-item-title">
                <span>Export as CSV</span>
                <span className="export-badge">CSV</span>
              </div>
              <span className="export-dropdown-item-desc">
                Tabular format for Excel, Google Sheets, or reporting
              </span>
            </div>
          </a>

          <a
            className="export-dropdown-item"
            href={jsonUrl}
            download="ip-assets.json"
            role="menuitem"
            aria-label="Export as JSON"
            onClick={handleSelect}
          >
            <div className="export-dropdown-item-icon export-icon-json">
              <JsonFileIcon />
            </div>
            <div className="export-dropdown-item-content">
              <div className="export-dropdown-item-title">
                <span>Export as JSON</span>
                <span className="export-badge">JSON</span>
              </div>
              <span className="export-dropdown-item-desc">
                Structured array with full tags and host attributes
              </span>
            </div>
          </a>
        </div>
      )}
    </div>
  );
}

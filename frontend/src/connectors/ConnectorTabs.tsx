import type { ConnectorSchema, ConnectorTab } from "./types";

export function ConnectorTabs({ connectors, active, onSelect }: { connectors: ConnectorSchema[]; active: ConnectorTab; onSelect: (tab: ConnectorTab) => void }) {
  const tabs: Array<{ name: ConnectorTab; label: string }> = [{ name: "overview", label: "Overview" }, ...connectors.map((item) => ({ name: item.name, label: item.display_name }))];
  return <div className="tabs" role="tablist" aria-label="Connector sections" style={{ marginBottom: 16 }}>
    {tabs.map((tab) => <a id={`connector-tab-${tab.name}`} key={tab.name} className={`tab${active === tab.name ? " tab-active" : ""}`} href={`/ui/connectors?tab=${tab.name}`} role="tab" aria-selected={active === tab.name} aria-controls={`connector-panel-${tab.name}`} tabIndex={active === tab.name ? 0 : -1} onClick={(event) => { event.preventDefault(); onSelect(tab.name); }}>{tab.label}</a>)}
  </div>;
}

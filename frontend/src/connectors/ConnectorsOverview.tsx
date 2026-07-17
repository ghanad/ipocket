import type { ConnectorSchema, ConnectorTab } from "./types";

export function ConnectorsOverview({ connectors, onSelect }: { connectors: ConnectorSchema[]; onSelect: (tab: ConnectorTab) => void }) {
  return <section id="connector-panel-overview" role="tabpanel" aria-labelledby="connector-tab-overview" className="card table-card">
    <div className="card-header card-header-padded"><div><h2>Available Connectors</h2><p className="subtitle">Current integration adapters that can prepare import bundles.</p></div></div>
    <div className="table-wrapper"><table className="table table-compact"><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>How to use</th></tr></thead><tbody>
      {connectors.map((connector) => <tr key={connector.name}><td>{connector.display_name}</td><td>{connector.kind}</td><td>Available</td><td>Open the <a className="link" href={`/ui/connectors?tab=${connector.name}`} onClick={(event) => { event.preventDefault(); onSelect(connector.name); }}>{connector.display_name} tab</a> to run dry-run/apply imports.</td></tr>)}
    </tbody></table></div>
  </section>;
}

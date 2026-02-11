# vCenter connector (manual export)

ipocket includes a manual vCenter connector that exports ESXi hosts and VMs into an importable `bundle.json`.

## Why manual

This connector does not run automatically. You run it on demand, then import the generated file from **Data Ops → Import**.

## Install dependencies

The connector uses `pyvmomi`, which is already included in `requirements.txt`.

```bash
pip install -r requirements.txt
```

## Run connector

```bash
python -m app.connectors.vcenter \
  --server vc.example.local \
  --username administrator@vsphere.local \
  --password '<password>' \
  --output ./vcenter-bundle.json
```

Optional flags:

- `--port 443`
- `--insecure` (skip TLS certificate verification)

## Output mapping

The generated bundle uses these rules:

- ESXi hosts:
  - Added to `data.hosts`
  - Their IP assets are exported with `type = OS`
  - Their IP assets are tagged with `esxi`
- Virtual machines:
  - Exported as IP assets with `type = VM`

Records without an IPv4 address are skipped with warnings printed in CLI output.

## Import into ipocket

1. Open **Data Ops → Import**
2. Upload the generated `vcenter-bundle.json` as bundle JSON
3. Run **Dry-run** first
4. Run **Apply** after verifying the summary

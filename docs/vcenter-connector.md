# vCenter connector (manual export)

ipocket includes a manual vCenter connector that exports ESXi hosts and VMs into an importable `bundle.json`.

## Why manual

This connector does not run automatically. You run it on demand, then import the generated file from **Data Ops → Import**.
You can access the same command snippets from the UI at **Connectors → vCenter**.
That UI also supports direct connector execution with `dry-run`/`apply` modes and shows run logs inline.

## Install dependencies

The connector uses `pyvmomi`, which is already included in `requirements.txt`.

```bash
pip install -r requirements.txt
```

## Run connector

### 1) Export file only (manual upload later)

```bash
python -m app.connectors.vcenter \
  --server vc.example.local \
  --username administrator@vsphere.local \
  --password '<password>' \
  --output ./vcenter-bundle.json
```

### 2) Direct dry-run into ipocket API (no manual file import)

```bash
python -m app.connectors.vcenter \
  --server vc.example.local \
  --username administrator@vsphere.local \
  --password '<password>' \
  --mode dry-run \
  --ipocket-url http://127.0.0.1:8000 \
  --token '<ipocket_token>'
```

### 3) Direct apply into ipocket API

```bash
python -m app.connectors.vcenter \
  --server vc.example.local \
  --username administrator@vsphere.local \
  --password '<password>' \
  --mode apply \
  --ipocket-url http://127.0.0.1:8000 \
  --token '<ipocket_token>'
```

Optional flags:

- `--port 443`
- `--insecure` (skip TLS certificate verification for vCenter)
- `--ipocket-insecure` (skip TLS verification for ipocket API)

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

If you used `--mode file`:

1. Open **Data Ops → Import**
2. Upload the generated `vcenter-bundle.json` as bundle JSON
3. Run **Dry-run** first
4. Run **Apply** after verifying the summary

If you used `--mode dry-run` or `--mode apply`, the connector sends the same bundle directly to `/import/bundle` API and prints the import summary in CLI output.

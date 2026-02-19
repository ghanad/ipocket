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

### 2) Direct dry-run into local ipocket DB (no manual file import)

```bash
python -m app.connectors.vcenter \
  --server vc.example.local \
  --username administrator@vsphere.local \
  --password '<password>' \
  --mode dry-run \
  --db-path ./ipocket.db
```

### 3) Direct apply into local ipocket DB

```bash
python -m app.connectors.vcenter \
  --server vc.example.local \
  --username administrator@vsphere.local \
  --password '<password>' \
  --mode apply \
  --db-path ./ipocket.db
```

Optional flags:

- `--port 443`
- `--insecure` (skip TLS certificate verification for vCenter)
## Output mapping

The generated bundle uses these rules:

- ESXi hosts:
  - Added to `data.hosts`
  - Their IP assets are exported with `type = OS`
  - Their IP assets are tagged with `esxi`
- Virtual machines:
  - Exported as IP assets with `type = VM`

Update behavior for existing IPs on apply:
- `type` is always overwritten from vCenter payload (`OS` for ESXi host IPs, `VM` for VM IPs).
- Connector tags are merged into existing tags (`merge_tags=true`) instead of replacing all tags.
- Notes are only set when the existing IP note is empty (`preserve_existing_notes=true` keeps non-empty manual notes).

Records without an IPv4 address are skipped with warnings printed in CLI output.

## Import into ipocket

If you used `--mode file`:

1. Open **Data Ops → Import**
2. Upload the generated `vcenter-bundle.json` as bundle JSON
3. Run **Dry-run** first
4. Run **Apply** after verifying the summary

If you used `--mode dry-run` or `--mode apply`, the connector runs the same bundle through the in-process import pipeline and prints the import summary in CLI output.

For the web UI connector path, ipocket also runs imports in-process with the active request database connection (no loopback HTTP call to its own API).

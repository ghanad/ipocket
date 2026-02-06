# Nmap XML upload

ipocket can import reachable IPs from an Nmap XML export. Nmap runs outside of ipocket; the app only consumes the XML file.

## Run Nmap

Basic host discovery:

```bash
nmap -sn -oX ipocket.xml <CIDR>
```

Optional (probe common ports to improve host discovery):

```bash
nmap -sn -PS80,443 -oX ipocket.xml <CIDR>
```

## Upload in the UI

1) Visit **Upload Nmap XML** in the left navigation.
2) Choose the `ipocket.xml` file from your Nmap run.
3) Check **Dry-run** to preview changes without writing to the database.
4) Submit the form.

## What ipocket does

- Parses only Nmap XML.
- Imports IPv4 addresses for hosts marked `up`.
- Creates missing IP assets as type `OTHER` with a discovery note.

## What ipocket does not do

- Run Nmap or schedule scans.
- Infer project, owner, host, or type from the scan.
- Update existing IP asset fields when an IP is already present.

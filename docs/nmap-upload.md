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

1) Visit **Import** in the left navigation.
2) Scroll to **Upload Nmap XML**.
3) Choose the `ipocket.xml` file from your Nmap run.
4) Check **Dry-run** to preview changes without writing to the database.
5) Submit the form.

## What ipocket does

- Parses only Nmap XML.
- Imports IPv4 addresses for hosts marked `up`.
- Creates missing IP assets with a discovery note.
- If a MAC address vendor is present, ipocket tries to infer the asset type:
  - `VM` for virtualization vendors (e.g., VMware, Microsoft, Xen, VirtualBox, QEMU/KVM, Citrix).
  - `OS` for common server hardware vendors (e.g., Dell, Hewlett Packard/HPE, Supermicro, Lenovo, IBM).
  - Otherwise defaults to `OTHER`.

## What ipocket does not do

- Run Nmap or schedule scans.
- Infer project, owner, or host from the scan.
- Update existing IP asset fields when an IP is already present.

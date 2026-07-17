from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReactPage:
    name: str
    route: str
    root_id: str
    endpoint: str
    entry: str
    legacy_marker: str
    bootstrap_get: str | None = None

    @property
    def bundle(self) -> str:
        return f"/static/react/{self.entry}/{self.entry}.js"


# This is the test-side contract for every primary React page. Route smoke tests,
# Vite entry checks, and generated-bundle checks all consume the same inventory.
REACT_PAGES = (
    ReactPage("About", "/ui/about", "about-root", "/api/ui/about", "about", "Version:", "/api/ui/about"),
    ReactPage("Account Password", "/ui/account/password", "account-password-root", "/api/ui/account/password", "account-password", 'name="current_password"'),
    ReactPage("Audit Log", "/ui/audit-log", "audit-log-root", "/api/ui/audit-log", "audit-log", "<table", "/api/ui/audit-log"),
    ReactPage("Connectors", "/ui/connectors", "connectors-root", "/api/ui/connectors", "connectors", "vcenter_password", "/api/ui/connectors"),
    ReactPage("Data Operations", "/ui/import", "data-ops-root", "/api/ui/data-ops", "data-ops", 'enctype="multipart/form-data"', "/api/ui/data-ops"),
    ReactPage("Host Detail", "/ui/hosts/{host_id}", "host-detail-root", "/api/ui/hosts/{host_id}/detail", "host-detail", "Linked IP assets", "/api/ui/hosts/{host_id}/detail"),
    ReactPage("Hosts", "/ui/hosts", "hosts-root", "/api/ui/hosts", "hosts", "<table", "/api/ui/hosts"),
    ReactPage("IP Asset Detail", "/ui/ip-assets/{asset_id}", "ip-asset-detail-root", "/api/ui/ip-assets/{asset_id}", "ip-asset-detail", "Audit history", "/api/ui/ip-assets/{asset_id}/detail"),
    ReactPage("IP Assets", "/ui/ip-assets", "ip-assets-root", "/api/ui/ip-assets", "ip-assets", "<table", "/api/ui/ip-assets"),
    ReactPage("Library", "/ui/projects", "library-root", "/api/ui/library", "library", 'role="tablist"', "/api/ui/library/projects"),
    ReactPage("Login", "/ui/login", "login-root", "/api/ui/login", "login", 'name="password"'),
    ReactPage("Management", "/ui/management", "management-root", "/api/management/overview", "management", 'class="stats-grid"', "/api/management/overview"),
    ReactPage("Range Addresses", "/ui/ranges/{range_id}/addresses", "range-addresses-root", "/api/ui/ranges/{range_id}/addresses", "range-addresses", "<table", "/api/ui/ranges/{range_id}/addresses"),
    ReactPage("Ranges", "/ui/ranges", "ranges-root", "/api/ui/ranges", "ranges", "<table", "/api/ui/ranges"),
    ReactPage("Users", "/ui/users", "users-root", "/api/ui/users", "users", 'name="username"', "/api/ui/users"),
)

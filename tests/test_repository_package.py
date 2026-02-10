from app import repository


def test_repository_is_package_with_public_api() -> None:
    assert repository.__file__ is not None
    assert repository.__file__.endswith("app/repository/__init__.py")

    expected_exports = [
        "create_ip_asset",
        "update_ip_asset",
        "list_active_ip_assets",
        "create_host",
        "create_ip_range",
        "create_project",
        "create_user",
        "create_audit_log",
        "get_management_summary",
    ]
    for export_name in expected_exports:
        assert hasattr(repository, export_name), f"Missing export: {export_name}"

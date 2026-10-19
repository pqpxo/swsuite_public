## version 2
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Iterable


GROUP_LABELS = {
    "core": "Core",
    "network": "Network",
    "timeline": "Timeline",
    "hardware_specs": "Hardware Specs",
    "storage": "Storage",
    "os": "OS",
    "os_software": "OS / Software",
    "support": "Support",
    "board": "Board",
    "hardware_add_ons": "Hardware Add-ons",
    "device_specs": "Device Specs",
    "management": "Management",
    "power": "Power",
    "optics_sensor": "Optics & Sensor",
    "recording": "Recording",
    "ups_pdu_specs": "UPS / PDU Specs",
    "load_monitoring": "Load Monitoring",
    "battery": "Battery",
    "array_enclosure": "Array / Enclosure",
    "drives_installed": "Drives Installed",
    "hardware": "Hardware",
    "support_assignment": "Support / Assignment",
    "virtual_machine_config": "Virtual Machine Config",
    "services": "Services",
    "cable_adapter_details": "Cable / Adapter Details",
    "condition_storage": "Condition & Storage",
    "device_details": "Device Details",
    "placement": "Placement",
    "automation": "Automation",
    "gaming": "Gaming",
    "smart_streaming": "Smart / Streaming",
    "mobile": "Mobile",
    "monitor_specific": "Monitor-specific",
    "printer_specific": "Printer-specific",
    "connectivity": "Connectivity",
    "common": "Common",
    "physical_host_hardware": "Hardware",
    "physical_host_storage": "Storage",
    "physical_host_networking": "Networking",
    "physical_host_power": "Power",
    "physical_host_location": "Location",
    "physical_host_lifecycle": "Lifecycle",
    "physical_host_maintenance": "Maintenance",
    "physical_host_management": "Management",
    "hypervisor_platform": "Platform",
    "hypervisor_cluster": "Cluster",
    "hypervisor_storage": "Storage",
    "hypervisor_resources": "Resources",
    "hypervisor_guests": "Guests",
    "hypervisor_backup": "Backup",
    "hypervisor_resilience": "Resilience",
    "hypervisor_maintenance": "Maintenance",
    "virtual_machine_identity": "Identity",
    "virtual_machine_resources": "Resources",
    "virtual_machine_storage": "Storage",
    "virtual_machine_networking": "Networking",
    "virtual_machine_boot": "Boot",
    "virtual_machine_backup": "Backup",
    "virtual_machine_maintenance": "Maintenance",
    "virtual_machine_purpose": "Purpose & Dependencies",
    "lxc_container_identity": "Identity",
    "lxc_container_os": "OS",
    "lxc_container_security": "Security",
    "lxc_container_resources": "Resources",
    "lxc_container_storage": "Storage",
    "lxc_container_networking": "Networking",
    "lxc_container_boot": "Boot",
    "lxc_container_backup": "Backup",
    "lxc_container_service": "Service",
    "docker_host_relationship": "Host Relationship",
    "docker_host_docker": "Docker",
    "docker_host_containers": "Containers",
    "docker_host_stacks": "Stacks",
    "docker_host_networking": "Networking",
    "docker_host_updates": "Updates",
    "docker_host_backup": "Backup",
    "docker_host_config": "Configuration",
    "docker_host_health": "Health",
    "docker_host_hardware": "Hardware",
}

SERVER_SUBCATEGORY_PREFIXES = [
    "physical_host",
    "hypervisor",
    "virtual_machine",
    "lxc_container",
    "docker_host",
]


def get_server_group_subcategory(scope: str, group_key: str) -> str | None:
    """Return subcategory slug if this is a servers-scoped subcategory group, else None."""
    if scope != "servers":
        return None
    if group_key == "common":
        return "common"
    for prefix in SERVER_SUBCATEGORY_PREFIXES:
        if group_key == prefix or group_key.startswith(prefix + "_"):
            return prefix
    return None


CATEGORY_NAME_ALIASES = {
    "servers": "servers",
    "server": "servers",
    "raspberry_pi": "raspberry_pi",
    "raspberry pi": "raspberry_pi",
    "single_board_computers": "raspberry_pi",
    "single board computers": "raspberry_pi",
    "network_equipment": "network_equipment",
    "network equipment": "network_equipment",
    "cameras": "cameras",
    "camera": "cameras",
    "power": "power",
    "storage": "storage",
    "laptops": "laptops",
    "laptop": "laptops",
    "lxc_vms": "lxc_vms",
    "lxc & vms": "lxc_vms",
    "lxc_and_vms": "lxc_vms",
    "vms": "lxc_vms",
    "vm": "lxc_vms",
    "cables_adapters": "cables_adapters",
    "cables & adapters": "cables_adapters",
    "iot_devices": "iot_devices",
    "iot devices": "iot_devices",
    "media_gaming": "media_gaming",
    "media & gaming": "media_gaming",
    "mobile_tablets": "mobile_tablets",
    "mobile & tablets": "mobile_tablets",
    "pcs_workstations": "pcs_workstations",
    "pcs & workstations": "pcs_workstations",
    "pcs": "pcs_workstations",
    "peripherals": "peripherals",
}

FULL_WIDTH_FIELD_TYPES = {"textarea"}
FULL_WIDTH_KEYS = {
    "services_running",
    "secondary_drives",
    "ports",
    "drive_inventory",
    "hats_add_on_boards",
    "automations_linked",
}


def slugify_category_name(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def resolve_category_scope(category_name: str | None) -> str:
    slug = slugify_category_name(category_name)
    return CATEGORY_NAME_ALIASES.get(slug, slug)


def parse_scoped_field_name(name: str) -> tuple[str, str, str] | None:
    parts = (name or "").split("__", 2)
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]


def field_is_visible_for_category(field_definition, category_name: str | None) -> bool:
    parsed = parse_scoped_field_name(field_definition.name)
    if not parsed:
        return False

    field_scope, _, _ = parsed
    asset_scope = resolve_category_scope(category_name)

    return field_scope == "universal" or field_scope == asset_scope


def field_is_visible_for_asset(field_definition, asset) -> bool:
    asset_category_name = getattr(getattr(asset, "category", None), "name", None)
    return field_is_visible_for_category(field_definition, asset_category_name)


def _field_display_value(field_definition, raw_value: str | None) -> str:
    raw_value = raw_value or ""
    if field_definition.field_type == "checkbox":
        return "Yes" if raw_value == "1" else "No"
    return raw_value.strip() or "—"


def _field_input_value(field_definition, raw_value: str | None) -> str:
    raw_value = raw_value or ""
    if field_definition.field_type == "checkbox":
        return "1" if raw_value == "1" else "0"
    return raw_value


def _wide_field(field_definition, field_key: str) -> bool:
    return field_definition.field_type in FULL_WIDTH_FIELD_TYPES or field_key in FULL_WIDTH_KEYS


def _group_sort_key(group_key: str) -> tuple[int, str]:
    order = {
        "core": 0,
        "network": 1,
        "timeline": 2,
    }
    return order.get(group_key, 100), group_key


def build_asset_custom_field_groups(asset, field_definitions: Iterable, values_by_field_id: dict[int, str]) -> list[dict]:
    grouped: OrderedDict[str, dict] = OrderedDict()

    asset_subcategory = getattr(asset, "subcategory", None) or ""

    for field in sorted(field_definitions, key=lambda f: (f.sort_order, f.label.lower())):
        if not field_is_visible_for_asset(field, asset):
            continue

        parsed = parse_scoped_field_name(field.name)
        if not parsed:
            continue

        field_scope, group_key, field_key = parsed

        # For server-scoped groups, only include common + the matching subcategory
        server_sub = get_server_group_subcategory(field_scope, group_key)
        if server_sub is not None and server_sub != "common":
            if server_sub != asset_subcategory:
                continue

        if group_key not in grouped:
            grouped[group_key] = {
                "key": group_key,
                "scope": field_scope,
                "label": GROUP_LABELS.get(group_key, group_key.replace("_", " ").title()),
                "fields": [],
            }

        raw_value = values_by_field_id.get(field.id, "") or ""
        grouped[group_key]["fields"].append(
            {
                "id": field.id,
                "name": field.name,
                "label": field.label,
                "field_type": field.field_type,
                "placeholder": field.placeholder,
                "value": _field_display_value(field, raw_value),
                "raw": raw_value,
                "wide": _wide_field(field, field_key),
            }
        )

    return [grouped[key] for key in sorted(grouped.keys(), key=_group_sort_key)]


def build_form_custom_field_groups(category_name: str | None, field_definitions: Iterable, values_by_field_id: dict[int, str]) -> list[dict]:
    grouped: OrderedDict[tuple[str, str], dict] = OrderedDict()

    for field in sorted(field_definitions, key=lambda f: (f.sort_order, f.label.lower())):
        parsed = parse_scoped_field_name(field.name)
        if not parsed:
            continue

        field_scope, group_key, field_key = parsed
        composite_key = (field_scope, group_key)
        visible = field_is_visible_for_category(field, category_name)

        if composite_key not in grouped:
            grouped[composite_key] = {
                "key": group_key,
                "label": GROUP_LABELS.get(group_key, group_key.replace("_", " ").title()),
                "scope": field_scope,
                "visible": visible,
                "server_subcategory": get_server_group_subcategory(field_scope, group_key),
                "fields": [],
            }
        elif visible:
            grouped[composite_key]["visible"] = True

        raw_value = values_by_field_id.get(field.id, "") or ""
        grouped[composite_key]["fields"].append(
            {
                "id": field.id,
                "name": field.name,
                "label": field.label,
                "field_type": field.field_type,
                "placeholder": field.placeholder or "",
                "value": _field_input_value(field, raw_value),
                "wide": _wide_field(field, field_key),
            }
        )

    def _composite_sort_key(item: tuple[tuple[str, str], dict]) -> tuple:
        (scope, group_key), _ = item
        base = _group_sort_key(group_key)
        return (base[0], 0 if scope == "universal" else 1, base[1], scope)

    return [group for _, group in sorted(grouped.items(), key=_composite_sort_key)]


def category_groups_payload(category_name: str | None, field_definitions: Iterable) -> list[dict]:
    payload = []
    for field in sorted(field_definitions, key=lambda f: (f.sort_order, f.label.lower())):
        parsed = parse_scoped_field_name(field.name)
        if not parsed:
            continue

        scope, group_key, field_key = parsed
        payload.append(
            {
                "scope": scope,
                "group_key": group_key,
                "field_key": field_key,
                "name": field.name,
                "visible": field_is_visible_for_category(field, category_name),
            }
        )
    return payload

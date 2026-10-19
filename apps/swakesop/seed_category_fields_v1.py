## version 1
"""
Seed category-scoped custom fields into the existing SQLite database used by the
SWOps app.

This script assumes the existing table:
  custom_field_definition(id, name, label, field_type, placeholder, sort_order)

It does NOT modify templates. It only inserts the definitions using a scoped
naming convention:
  <category_slug>__<group_key>__<field_key>

Examples:
  universal__core__tags
  servers__hardware_specs__cpu_model
  cameras__connectivity__rtsp_stream_url

Usage:
  python seed_category_fields_v1.py /path/to/inventory.db
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCHEMA = {
    "universal": {
        "core": [
            ("tags", "Tags", "text", "Comma-separated, e.g. production, critical, no-backup"),
        ],
    },

    "servers": {
        # ── Common fields (all server types) ─────────────────────────────────
        "common": [
            ("description_purpose", "Description / Purpose", "textarea", "Main Proxmox host for virtualisation"),
            ("mac_address",         "MAC Address",           "text",     "AA:BB:CC:DD:EE:FF"),
            ("operating_system",    "Operating System",      "text",     "Debian 12 / Proxmox VE 8 / Ubuntu 24.04"),
            ("os_version",          "OS Version",            "text",     "12 Bookworm"),
            ("owner_used_by",       "Owner / Used By",       "text",     "Sam / Household / Lab"),
            ("management_url",      "Management URL",        "url",      "https://192.168.1.183:8006"),
            ("ssh_address",         "SSH Address",           "text",     "ssh user@192.168.1.183"),
            ("tags",                "Tags",                  "text",     "proxmox, critical, backup"),
            ("criticality",         "Criticality",           "text",     "Low / Medium / High / Critical"),
            ("backup_status",       "Backup Status",         "text",     "Backed up / Not backed up / Failed / N/A"),
        ],
        # ── Physical Host ─────────────────────────────────────────────────────
        "physical_host_hardware": [
            ("manufacturer",     "Manufacturer",                "text",     "Dell"),
            ("model",            "Model",                       "text",     "PowerEdge T330"),
            ("serial_tag",       "Serial Number / Service Tag", "text",     "ABC1234"),
            ("asset_tag",        "Asset Tag",                   "text",     "SWK-HOST-001"),
            ("cpu_model",        "CPU Model",                   "text",     "Intel Xeon E3-1230 v6"),
            ("cpu_cores_threads","CPU Cores / Threads",         "text",     "4 cores / 8 threads"),
            ("ram_installed",    "RAM Installed",               "text",     "32 GB"),
            ("max_ram",          "Max RAM Supported",           "text",     "64 GB"),
        ],
        "physical_host_storage": [
            ("storage_devices",  "Storage Devices",    "textarea", "2x 1TB SSD, 2x 4TB HDD"),
            ("raid_hba",         "RAID / HBA Details", "text",     "PERC H330, HBA mode"),
            ("boot_disk",        "Boot Disk",          "text",     "256 GB SSD"),
        ],
        "physical_host_networking": [
            ("nics", "NICs", "text", "2x 1GbE, 1x 10GbE"),
        ],
        "physical_host_power": [
            ("psu",         "Power Supply",   "text", "Dual redundant / Single 495W"),
            ("ups_protected","UPS Protected",  "text", "Yes / No"),
            ("power_usage", "Power Usage",    "text", "85W idle"),
        ],
        "physical_host_location": [
            ("rack_unit", "Rack Unit / Position", "text", "U12 / Shelf 2"),
        ],
        "physical_host_lifecycle": [
            ("purchase_date",   "Purchase Date",    "date", ""),
            ("warranty_expiry", "Warranty Expiry",  "date", ""),
        ],
        "physical_host_maintenance": [
            ("firmware_version", "Firmware Version",  "text",     "BIOS 2.18.0"),
            ("noise_notes",      "Noise / Fan Notes", "textarea", "Quiet idle; loud under load"),
        ],
        "physical_host_management": [
            ("ipmi_url", "IPMI / iDRAC / iLO URL", "url", "https://idrac-server.local"),
        ],
        # ── Hypervisor ────────────────────────────────────────────────────────
        "hypervisor_platform": [
            ("type",    "Hypervisor Type",    "text", "Proxmox VE / VMware ESXi / other"),
            ("version", "Hypervisor Version", "text", "Proxmox VE 8.2"),
        ],
        "hypervisor_cluster": [
            ("cluster_name", "Cluster Name", "text", "pve-cluster"),
            ("node_name",    "Node Name",    "text", "pve01"),
        ],
        "hypervisor_storage": [
            ("datastores",     "Datastores / Storage Pools", "textarea", "local-lvm, pbs-backup, nfs-media"),
            ("storage_total",  "Storage Total",              "text",     "2 TB"),
            ("storage_used",   "Storage Used",               "text",     "1.4 TB"),
        ],
        "hypervisor_resources": [
            ("total_cpu",    "Total CPU Cores", "text", "8"),
            ("total_ram",    "Total RAM",       "text", "32 GB"),
            ("allocated_ram","Allocated RAM",   "text", "24 GB"),
        ],
        "hypervisor_guests": [
            ("vm_count",       "VM Count",       "text", "12"),
            ("lxc_count",      "LXC Count",      "text", "8"),
            ("running_guests", "Running Guests", "text", "17"),
        ],
        "hypervisor_backup": [
            ("backup_target",     "Backup Target",      "text", "Proxmox Backup Server"),
            ("last_backup_check", "Last Backup Check",  "text", "Successful"),
        ],
        "hypervisor_resilience": [
            ("ha_enabled", "HA Enabled", "text", "Yes / No"),
        ],
        "hypervisor_maintenance": [
            ("maintenance_mode", "Maintenance Mode", "text", "Yes / No"),
            ("update_status",    "Update Status",    "text", "Up to date / Updates available"),
        ],
        # ── Virtual Machine ───────────────────────────────────────────────────
        "virtual_machine_identity": [
            ("vm_id", "VM ID", "text", "101"),
        ],
        "virtual_machine_resources": [
            ("vcpu_count",   "vCPU Count",    "text", "2"),
            ("ram_allocated","RAM Allocated", "text", "4 GB"),
        ],
        "virtual_machine_storage": [
            ("disk_size",        "Disk Size",        "text", "64 GB"),
            ("disk_used",        "Disk Used",        "text", "32 GB"),
            ("storage_location", "Storage Location", "text", "local-lvm"),
        ],
        "virtual_machine_networking": [
            ("network_bridge_vlan","Network Bridge / VLAN","text",     "vmbr0 / VLAN 20"),
            ("secondary_ips",      "Secondary IPs",        "textarea", "192.168.1.118"),
            ("mac_address",        "MAC Address",          "text",     "AA:BB:CC:DD:EE:FF"),
            ("exposed_services",   "Exposed Services",     "textarea", "8123, 22, 443"),
        ],
        "virtual_machine_boot": [
            ("autostart",   "Autostart",  "text", "Yes / No"),
            ("boot_order",  "Boot Order", "text", "1"),
        ],
        "virtual_machine_backup": [
            ("backup_enabled",     "Backup Enabled",     "text", "Yes / No"),
            ("backup_schedule",    "Backup Schedule",    "text", "Daily 02:00"),
            ("last_backup_status", "Last Backup Status", "text", "Successful / Failed"),
        ],
        "virtual_machine_maintenance": [
            ("snapshot_count", "Snapshot Count", "text", "2"),
        ],
        "virtual_machine_purpose": [
            ("purpose_role", "Purpose / Role", "text",     "Home Assistant"),
            ("dependencies", "Dependencies",   "textarea", "MQTT, PostgreSQL, NFS"),
        ],
        # ── LXC Container ─────────────────────────────────────────────────────
        "lxc_container_identity": [
            ("ct_id", "Container ID / CT ID", "text", "203"),
        ],
        "lxc_container_os": [
            ("template_used", "Template Used", "text", "debian-12-standard"),
        ],
        "lxc_container_security": [
            ("privileged",     "Privileged",     "text",     "Yes / No"),
            ("nesting_enabled","Nesting Enabled", "text",     "Yes / No"),
            ("fuse_enabled",   "FUSE Enabled",   "text",     "Yes / No"),
            ("security_notes", "Security Notes", "textarea", "Privileged due to mount access"),
        ],
        "lxc_container_resources": [
            ("vcpu_count",    "vCPU Count",    "text", "1"),
            ("ram_allocated", "RAM Allocated", "text", "512 MB"),
            ("swap_allocated","Swap Allocated","text", "512 MB"),
        ],
        "lxc_container_storage": [
            ("disk_size",    "Disk Size",    "text",     "8 GB"),
            ("disk_used",    "Disk Used",    "text",     "4.2 GB"),
            ("mount_points", "Mount Points", "textarea", "/mnt/backups, /media"),
        ],
        "lxc_container_networking": [
            ("network_bridge_vlan","Network Bridge / VLAN","text","vmbr0 / VLAN 10"),
            ("mac_address",        "MAC Address",          "text","AA:BB:CC:DD:EE:FF"),
        ],
        "lxc_container_boot": [
            ("autostart", "Autostart", "text", "Yes / No"),
        ],
        "lxc_container_backup": [
            ("backup_enabled",     "Backup Enabled",     "text", "Yes / No"),
            ("last_backup_status", "Last Backup Status", "text", "Successful / Failed"),
        ],
        "lxc_container_service": [
            ("main_service",  "Main Service",  "text",     "AdGuard Home"),
            ("service_ports", "Service Ports", "textarea", "80, 443, 3000"),
            ("update_method", "Update Method", "text",     "apt / manual"),
        ],
        # ── Docker Host ───────────────────────────────────────────────────────
        "docker_host_relationship": [
            ("host_type", "Host Type", "text", "Physical / VM / LXC"),
        ],
        "docker_host_docker": [
            ("docker_version",       "Docker Version",          "text", "27.x"),
            ("compose_version",      "Docker Compose Version",  "text", "v2.x"),
            ("docker_root_path",     "Docker Root Path",        "text", "/var/lib/docker"),
            ("compose_project_path", "Compose Project Path",    "text", "/home/user/docker"),
            ("auto_restart_policy",  "Auto-Restart Policy",     "text", "unless-stopped"),
        ],
        "docker_host_containers": [
            ("container_count",    "Container Count",    "text", "18"),
            ("running_containers", "Running Containers", "text", "17"),
            ("stopped_containers", "Stopped Containers", "text", "1"),
        ],
        "docker_host_stacks": [
            ("main_stacks", "Main Stacks", "textarea", "Plex, Sonarr, Radarr, NPM"),
        ],
        "docker_host_networking": [
            ("exposed_ports", "Exposed Ports",       "textarea", "80, 443, 32400"),
            ("reverse_proxy", "Reverse Proxy Used",  "text",     "Nginx Proxy Manager"),
            ("network_names", "Network Names",       "textarea", "proxy, media, backend"),
        ],
        "docker_host_updates": [
            ("watchtower_enabled", "Watchtower Enabled", "text", "Yes / No"),
            ("last_image_update",  "Last Image Update",  "date", ""),
        ],
        "docker_host_backup": [
            ("backup_method", "Backup Method", "text",     "Duplicati"),
            ("backup_paths",  "Backup Paths",  "textarea", "/home/user/docker/app/config"),
        ],
        "docker_host_config": [
            ("env_file_path", "Environment File Path", "text",     ".env"),
            ("volume_paths",  "Volume Paths",          "textarea", "/home/user/docker/..."),
        ],
        "docker_host_health": [
            ("healthcheck_status", "Healthcheck Status", "text", "Healthy"),
        ],
        "docker_host_hardware": [
            ("gpu_tpu_passthrough", "GPU / TPU Passthrough", "text", "Coral USB"),
        ],
    },
    "raspberry_pi": {
        "board": [
            ("pi_model", "Pi model", "text", "Pi 5 / Pi 4 Model B / Zero 2 W / CM4 / other"),
            ("board_revision", "Board revision", "text", "c03115"),
            ("ram_variant", "RAM variant", "text", "1 GB / 2 GB / 4 GB / 8 GB"),
            ("gpio_header", "GPIO header", "text", "populated / not populated"),
        ],
        "storage": [
            ("boot_media_type", "Boot media type", "text", "SD card / USB SSD / NVMe via HAT"),
            ("boot_media_size", "Boot media size", "text", "64 GB"),
            ("boot_media_brand", "Boot media brand", "text", "SanDisk Endurance"),
        ],
        "os": [
            ("operating_system", "Operating system", "text", "Raspberry Pi OS / DietPi / Ubuntu / Home Assistant OS / other"),
            ("os_version", "OS version", "text", "Bookworm"),
            ("architecture", "Architecture", "text", "64-bit / 32-bit"),
            ("mode", "Mode", "text", "Headless / Desktop"),
        ],
        "hardware_add_ons": [
            ("hats_add_on_boards", "HATs / add-on boards", "textarea", "PoE HAT, RTC module, NVMe base"),
            ("power_source", "Power source", "text", "USB-C PSU / PoE HAT / GPIO pins"),
            ("psu_wattage", "PSU wattage", "text", "27W"),
            ("wifi_in_use", "Wi‑Fi in use", "checkbox", ""),
            ("mac_address", "MAC address", "text", ""),
        ],
    },
    "network_equipment": {
        "device_specs": [
            ("port_count", "Port count", "text", "24"),
            ("port_speed", "Port speed", "text", "1G / 2.5G / 10G / mixed"),
            ("poe_budget_w", "PoE budget (W)", "text", "150"),
            ("uplink_speed", "Uplink speed", "text", "10G SFP+"),
        ],
        "management": [
            ("management_platform", "Management platform", "text", "UniFi / OpenWrt / Omada / pfSense / other"),
            ("firmware_version", "Firmware version", "text", "3.2.7"),
            ("console_access", "Console access", "text", "SSH / Web UI / Telnet / Serial"),
            ("vlan_count", "VLAN count", "text", "6"),
        ],
        "power": [
            ("power_draw_w", "Power draw (W)", "text", "48"),
            ("ups_pdu_port", "UPS / PDU port", "text", ""),
        ],
    },
    "cameras": {
        "optics_sensor": [
            ("resolution", "Resolution", "text", "4K / 8MP / 2MP"),
            ("lens_fov", "Lens FOV", "text", "110° wide"),
            ("night_vision", "Night vision", "text", "IR / colour night vision / none"),
            ("placement", "Placement", "text", "indoor / outdoor / both"),
        ],
        "connectivity": [
            ("connection_type", "Connection type", "text", "PoE wired / Wi‑Fi / 4G LTE"),
            ("nvr_recorder", "NVR / recorder", "text", ""),
            ("rtsp_stream_url", "RTSP stream URL", "url", "rtsp://..."),
        ],
        "recording": [
            ("storage_type", "Storage type", "text", "NVR / SD card / cloud"),
            ("retention_days", "Retention (days)", "text", "30"),
        ],
    },
    "power": {
        "ups_pdu_specs": [
            ("type", "Type", "text", "UPS / PDU / Smart PDU / Surge protector"),
            ("capacity", "Capacity", "text", "1500 VA / 900 W"),
            ("battery_runtime_minutes", "Battery runtime", "text", "30"),
            ("outlet_count", "Outlet count", "text", "8"),
        ],
        "load_monitoring": [
            ("current_load_w", "Current load (W)", "text", "320"),
            ("load_percent", "Load %", "text", "35"),
            ("management_url", "Management URL", "url", "https://"),
        ],
        "battery": [
            ("battery_model", "Battery model", "text", "RBC2"),
            ("last_battery_replaced", "Last battery replaced", "date", ""),
            ("next_replacement_due", "Next replacement due", "date", ""),
        ],
    },
    "storage": {
        "array_enclosure": [
            ("type", "Type", "text", "NAS / DAS / SAN / single drive"),
            ("bay_count", "Bay count", "text", "4"),
            ("raid_level", "RAID level", "text", "RAID 5 / ZFS RAIDZ / none"),
            ("usable_capacity", "Usable capacity", "text", "12 TB"),
            ("os_firmware", "OS / firmware", "text", "TrueNAS / Synology DSM / other"),
            ("connected_to", "Connected to", "text", ""),
        ],
        "drives_installed": [
            ("drive_inventory", "Drive inventory", "textarea", "One line per drive: bay, brand, model, capacity"),
        ],
    },
    "laptops": {
        "hardware": [
            ("cpu", "CPU", "text", "Apple M3 / Intel Core i7-1365U"),
            ("ram_gb", "RAM (GB)", "text", "16"),
            ("storage", "Storage", "text", "512 GB SSD"),
            ("screen_size", "Screen size", "text", '14"'),
            ("battery_health_percent", "Battery health %", "text", "87"),
            ("charger_wattage", "Charger wattage", "text", "67W"),
        ],
        "os": [
            ("operating_system", "Operating system", "text", "macOS / Windows / Linux"),
            ("os_version", "OS version", "text", "Windows 11 24H2"),
        ],
        "support_assignment": [
            ("warranty_expiry", "Warranty expiry", "date", ""),
            ("assigned_to", "Assigned to", "text", ""),
        ],
    },
    "lxc_vms": {
        "virtual_machine_config": [
            ("type", "Type", "text", "LXC container / VM KVM / VM VMware / Docker container"),
            ("hypervisor_host", "Hypervisor host", "text", ""),
            ("vcpus", "vCPUs", "text", "2"),
            ("ram_allocated_gb", "RAM allocated (GB)", "text", "4"),
            ("disk_allocated_gb", "Disk allocated (GB)", "text", "32"),
            ("template_image", "Template / image", "text", "Ubuntu 24.04 LXC template"),
        ],
        "os": [
            ("operating_system", "Operating system", "text", "Debian 12"),
            ("os_version", "OS version", "text", ""),
        ],
        "services": [
            ("services_running", "Services running", "textarea", "Nginx, PostgreSQL, Home Assistant"),
            ("exposed_ports", "Exposed ports", "text", "80, 443, 5432"),
        ],
    },
    "cables_adapters": {
        "cable_adapter_details": [
            ("type", "Type", "text", "Cable / Adapter / Dongle / Extender / Splitter"),
            ("specification", "Specification", "text", "Cat6 / HDMI 2.1 / USB4"),
            ("connector_a", "Connector A", "text", ""),
            ("connector_b", "Connector B", "text", ""),
            ("length", "Length", "text", "1m / 5m / 0.3m"),
            ("colour", "Colour", "text", "black"),
            ("max_data_rate", "Max data rate", "text", "10 Gbps / 48 Gbps"),
            ("max_power_delivery", "Max power delivery", "text", "100W PD"),
        ],
        "condition_storage": [
            ("condition", "Condition", "text", "New / Good / Fair / Damaged"),
            ("storage_location", "Storage location", "text", ""),
            ("quantity", "Quantity", "text", "3"),
        ],
    },
    "iot_devices": {
        "device_details": [
            ("protocol", "Protocol", "text", "Zigbee / Z‑Wave / Matter / Wi‑Fi / Bluetooth / Thread / proprietary"),
            ("hub_controller", "Hub / controller", "text", ""),
            ("device_id", "Device ID", "text", ""),
            ("firmware_version", "Firmware version", "text", "2.1.4"),
        ],
        "power": [
            ("power_type", "Power type", "text", "Mains / Battery / PoE / Solar"),
            ("battery_type", "Battery type", "text", "AA / CR2032 / built-in LiPo"),
            ("battery_level_percent", "Battery level %", "text", "87"),
            ("last_battery_change", "Last battery change", "date", ""),
        ],
        "placement": [
            ("room_zone", "Room / zone", "text", ""),
            ("mounted", "Mounted", "checkbox", ""),
            ("indoor_outdoor", "Indoor / outdoor", "text", "indoor / outdoor / both"),
        ],
        "automation": [
            ("automations_linked", "Automations linked", "textarea", "3 — morning lights"),
            ("dashboard_ui", "Dashboard / UI", "url", "https://"),
        ],
    },
    "media_gaming": {
        "device_details": [
            ("device_type", "Device type", "text", "Games console / Smart speaker / Smart display / Streaming stick / Media server / Set-top box / Other"),
            ("generation", "Generation", "text", "Xbox Series X / Wii U / Google Nest Hub 2nd Gen"),
            ("storage_gb", "Storage (GB)", "text", "512"),
            ("expandable_storage", "Expandable storage", "checkbox", ""),
        ],
        "gaming": [
            ("platform", "Platform", "text", "Xbox / PlayStation / Nintendo / PC / Other"),
            ("backwards_compatibility", "Backwards compat.", "text", ""),
            ("online_subscription", "Online subscription", "text", "Xbox Game Pass Ultimate — 2026-12-01"),
            ("controller_count", "Controller count", "text", "2"),
        ],
        "smart_streaming": [
            ("ecosystem", "Ecosystem", "text", "Google / Amazon / Apple / Other"),
            ("linked_account", "Linked account", "text", ""),
            ("display_size", "Display size", "text", '7"'),
            ("voice_assistant", "Voice assistant", "text", "Google Assistant / Alexa / Siri / none"),
        ],
        "connectivity": [
            ("hdmi_output", "HDMI output", "text", "HDMI 2.1 × 2 / HDMI 2.0 / none"),
            ("audio_output", "Audio output", "text", "HDMI ARC / optical / 3.5mm / built-in only"),
            ("connected_display", "Connected display", "text", ""),
        ],
    },
    "mobile_tablets": {
        "device_details": [
            ("device_type", "Device type", "text", "Smartphone / Tablet / E-reader"),
            ("os", "OS", "text", "iOS / Android / iPadOS / other"),
            ("os_version", "OS version", "text", "Android 15"),
            ("storage_gb", "Storage (GB)", "text", "256"),
            ("screen_size", "Screen size", "text", '6.1"'),
            ("colour", "Colour", "text", "Space Black"),
        ],
        "mobile": [
            ("imei", "IMEI", "text", ""),
            ("carrier", "Carrier", "text", "EE / Vodafone / O2"),
            ("plan_type", "Plan type", "text", "Pay monthly / PAYG / SIM-free"),
            ("plan_expiry", "Plan expiry", "date", ""),
            ("phone_number", "Phone number", "text", ""),
        ],
        "support_assignment": [
            ("warranty_expiry", "Warranty expiry", "date", ""),
            ("assigned_to", "Assigned to", "text", ""),
            ("mdm_enrolled", "MDM enrolled", "checkbox", ""),
            ("mdm_platform", "MDM platform", "text", "Apple Business Manager / Intune"),
        ],
        "battery": [
            ("battery_health_percent", "Battery health %", "text", "91"),
        ],
    },
    "pcs_workstations": {
        "hardware": [
            ("form_factor", "Form factor", "text", "Tower / SFF / Mini PC / All-in-one / Rack-mount"),
            ("cpu", "CPU", "text", "AMD Ryzen 9 7950X / Intel Core i9-13900K"),
            ("cpu_cores", "CPU cores", "text", "16"),
            ("cpu_threads", "CPU threads", "text", "32"),
            ("ram_total_gb", "RAM total (GB)", "text", "64"),
            ("ram_type", "RAM type", "text", "DDR5 6000MHz"),
            ("gpu", "GPU", "text", "NVIDIA RTX 4080 / AMD RX 7900 XT / integrated"),
            ("psu_wattage", "PSU wattage", "text", "850W"),
        ],
        "storage": [
            ("primary_drive", "Primary drive", "text", "2 TB Samsung 990 Pro NVMe"),
            ("secondary_drives", "Secondary drives", "textarea", "4 TB HDD\n1 TB SSD"),
            ("total_storage", "Total storage", "text", "7 TB"),
        ],
        "os_software": [
            ("operating_system", "Operating system", "text", "Windows / Linux / macOS / dual-boot"),
            ("os_version", "OS version", "text", "Windows 11 24H2 / Ubuntu 24.04"),
        ],
        "support_assignment": [
            ("warranty_expiry", "Warranty expiry", "date", ""),
            ("assigned_to", "Assigned to", "text", ""),
            ("remote_access", "Remote access", "text", "RDP / VNC / SSH / none"),
        ],
    },
    "peripherals": {
        "device_details": [
            ("peripheral_type", "Peripheral type", "text", "Monitor / Keyboard / Mouse / Webcam / Microphone / Headset / Printer / Scanner / Drawing tablet / USB hub / KVM switch / DAC / Capture card / Other"),
            ("connection", "Connection", "text", "USB-A / USB-C / Thunderbolt / Bluetooth / 2.4GHz / DisplayPort / HDMI / PCIe / 3.5mm"),
            ("connected_to", "Connected to", "text", ""),
            ("wireless", "Wireless", "checkbox", ""),
        ],
        "monitor_specific": [
            ("screen_size", "Screen size", "text", '27"'),
            ("resolution", "Resolution", "text", "2560x1440 / 4K"),
            ("refresh_rate", "Refresh rate", "text", "144Hz"),
            ("panel_type", "Panel type", "text", "IPS / VA / OLED / TN"),
            ("hdr", "HDR", "checkbox", ""),
            ("ports", "Ports", "textarea", "2x HDMI 2.1\n1x DP 1.4\n4x USB-A"),
        ],
        "printer_specific": [
            ("print_type", "Print type", "text", "Inkjet / Laser / Thermal"),
            ("colour_printing", "Colour", "checkbox", ""),
            ("network_capable", "Network capable", "checkbox", ""),
            ("ink_toner_model", "Ink / toner model", "text", "PG-560XL / TN-2420"),
        ],
        "power": [
            ("powered", "Powered", "text", "Bus-powered / Mains / Battery"),
            ("power_draw_w", "Power draw (W)", "text", "35"),
        ],
    },
}

def ensure_table_exists(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_field_definition (
            id INTEGER PRIMARY KEY,
            name VARCHAR(80) NOT NULL UNIQUE,
            label VARCHAR(120) NOT NULL,
            field_type VARCHAR(20) NOT NULL DEFAULT 'text',
            placeholder VARCHAR(255),
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()

def upsert_field(conn: sqlite3.Connection, name: str, label: str, field_type: str, placeholder: str, sort_order: int) -> None:
    cur = conn.cursor()
    cur.execute("SELECT id FROM custom_field_definition WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE custom_field_definition
            SET label = ?, field_type = ?, placeholder = ?, sort_order = ?
            WHERE name = ?
            """,
            (label, field_type, placeholder, sort_order, name),
        )
    else:
        cur.execute(
            """
            INSERT INTO custom_field_definition(name, label, field_type, placeholder, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, label, field_type, placeholder, sort_order),
        )

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python seed_category_fields_v1.py /path/to/inventory.db")
        return 1

    db_path = Path(sys.argv[1]).expanduser().resolve()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_table_exists(conn)

        sort_order = 1000
        inserted = 0
        for category_slug, groups in SCHEMA.items():
            for group_key, fields in groups.items():
                for field_key, label, field_type, placeholder in fields:
                    name = f"{category_slug}__{group_key}__{field_key}"
                    upsert_field(conn, name, label, field_type, placeholder, sort_order)
                    sort_order += 10
                    inserted += 1

        conn.commit()
        print(f"Seeded or updated {inserted} field definitions in {db_path}")
        print("Naming convention in use:")
        print("  <category_slug>__<group_key>__<field_key>")
        print("Examples:")
        print("  universal__core__tags")
        print("  cameras__connectivity__rtsp_stream_url")
        print("  pcs_workstations__hardware__gpu")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())

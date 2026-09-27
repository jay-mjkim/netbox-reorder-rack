from netbox.plugins import PluginConfig


class NetboxReorderRackConfig(PluginConfig):
    name = "netbox_reorder_rack"
    verbose_name = "NetBox Reorder Rack"
    description = "NetBox plugin to reorder rack layouts."
    version = "1.1.4"
    base_url = "reorder"
    default_settings = {
        # Device custom field (integer, watts) holding a measured peak draw. The
        # capacity lanes/totals show a "peak" column only when this field exists.
        "peak_power_field": "measured_peak_power_w",
    }


config = NetboxReorderRackConfig

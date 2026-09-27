from netbox.plugins import PluginMenuItem

menu_items = (
    PluginMenuItem(
        link="plugins:netbox_reorder_rack:row",
        link_text="Reorder Racks",
        permissions=["dcim.change_device"],
    ),
)

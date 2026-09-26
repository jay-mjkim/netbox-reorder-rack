from netbox.plugins import PluginTemplateExtension


class ReorderButton(PluginTemplateExtension):
    models = ("dcim.rack",)

    def buttons(self):
        return self.render("netbox_reorder_rack/inc/rack_button.html")

    def list_buttons(self):
        # Carries the rack list's current filter (site_id / location_id / id) over
        # to the row view, so "filter the list, then reorder what you see" works.
        return self.render("netbox_reorder_rack/inc/row_list_button.html")


template_extensions = [ReorderButton]

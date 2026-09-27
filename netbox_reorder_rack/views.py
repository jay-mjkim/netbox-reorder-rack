from dcim.models import Device
from dcim.models import DeviceType
from dcim.models import Rack
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.generic import View
from netbox.config import get_config
from utilities.views import register_model_view

from netbox_reorder_rack.capacity import device_meta_map
from netbox_reorder_rack.capacity import peak_available
from netbox_reorder_rack.capacity import rack_capacity


def _attach_meta(units_lists, extra_devices=()):
    """Compute power/weight meta once for every device on the page and hang it on
    each unit dict (``unit["meta"]``) and on the loose devices (``device.meta``)."""
    devices = {}
    for units in units_lists:
        for unit in units:
            if unit.get("device"):
                devices[unit["device"].pk] = unit["device"]
    for device in extra_devices:
        devices[device.pk] = device
    meta = device_meta_map(devices.values())
    for units in units_lists:
        for unit in units:
            if unit.get("device"):
                unit["meta"] = meta[unit["device"].pk]
    for device in extra_devices:
        device.meta = meta[device.pk]


@register_model_view(
    Rack,
    name="reorder",
    path="reorder",
)
class ReorderView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ["dcim.change_device", "dcim.view_device"]
    template_name = "netbox_reorder_rack/rack.html"

    def get(self, request, pk):
        rack = get_object_or_404(Rack, pk=pk)
        # Get the 'view' query parameter from the URL, default to 'images-and-labels' if not provided
        selected_view = request.GET.get("view", "images-and-labels")

        # Now you can use the `selected_view` variable to handle the specific logic
        if selected_view == "images-and-labels":
            # Logic for handling 'Images and Labels' view
            images = True
            labels = True
        elif selected_view == "images-only":
            # Logic for handling 'Images only' view
            images = True
            labels = False
        elif selected_view == "labels-only":
            # Logic for handling 'Labels only' view
            images = False
            labels = True

        # A 0U type (PDU strip, cable manager) is never mounted in a unit, so it
        # has no place on the grid or in the bin.
        non_racked = Device.objects.filter(
            rack=rack, position__isnull=True, parent_bay__isnull=True
        ).exclude(device_type__u_height=0)

        exclude_list = []
        # fix - exclude all child devices:
        for device in non_racked:
            device_type = DeviceType.objects.get(id=device.device_type.id)
            if device_type.subdevice_role == "child":
                exclude_list.append(device.id)

        non_racked_devices = list(non_racked.exclude(pk__in=exclude_list))
        front_units = rack.get_rack_units(expand_devices=False, face="front")
        rear_units = rack.get_rack_units(expand_devices=False, face="rear")
        _attach_meta([front_units, rear_units], non_racked_devices)
        config = get_config()

        base_url = f"{request.scheme}://{request.get_host().rstrip('/')}"

        return render(
            request,
            self.template_name,
            {
                "object": rack,
                "images": images,
                "labels": labels,
                "unit_width": config.RACK_ELEVATION_DEFAULT_UNIT_WIDTH,
                "base_url": base_url,
                "front_units": front_units,
                "rear_units": rear_units,
                "non_racked": non_racked_devices,
                "capacity": rack_capacity(rack),
                "peak_available": peak_available(),
                "basepath": settings.BASE_PATH,
            },
        )


# How many racks one row page will lay out. Each column is ~240px wide, so past this
# the page is all horizontal scroll and the drag targets are off screen anyway.
ROW_MAX_RACKS = 24


class ReorderRowView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Several racks side by side, one face at a time, with drag and drop between them.

    The per-rack view above moves devices within one rack. This one exists for the
    case where a rack is being emptied into its neighbours or a row is being laid
    out from scratch: pick the racks (rack_id=, or every rack of a location_id= /
    site_id=), drag, save once.
    """

    permission_required = ["dcim.change_device", "dcim.view_device"]
    template_name = "netbox_reorder_rack/row.html"

    def get(self, request):
        from dcim.choices import DeviceFaceChoices

        from netbox_reorder_rack.forms import RowSelectForm

        form = RowSelectForm(request.GET)
        params = request.GET
        face = params.get("face") or DeviceFaceChoices.FACE_FRONT
        if face not in (DeviceFaceChoices.FACE_FRONT, DeviceFaceChoices.FACE_REAR):
            face = DeviceFaceChoices.FACE_FRONT
        selected_view = params.get("view", "images-and-labels")
        images = selected_view != "labels-only"
        labels = selected_view != "images-only"

        racks = (
            Rack.objects.restrict(request.user, "view")
            .select_related("site", "location")
            .prefetch_related("powerfeeds")
        )
        # The rack list passes its own filter through (id=); our form uses rack_id=.
        rack_ids = params.getlist("rack_id") or params.getlist("id")
        if rack_ids:
            racks = racks.filter(pk__in=rack_ids)
        elif params.get("location_id"):
            racks = racks.filter(location_id=params["location_id"])
        elif params.get("site_id"):
            racks = racks.filter(site_id=params["site_id"])
        else:
            racks = racks.none()
        racks = list(racks.order_by("site", "location", "name")[: ROW_MAX_RACKS + 1])

        error = None
        if len(racks) > ROW_MAX_RACKS:
            error = f"Too many racks selected; pick at most {ROW_MAX_RACKS}."
            racks = []
        elif len({rack.site_id for rack in racks}) > 1:
            error = "All racks must belong to the same site."
            racks = []

        columns = [
            {
                "rack": rack,
                "units": rack.get_rack_units(expand_devices=False, face=face),
                "capacity": rack_capacity(rack),
            }
            for rack in racks
        ]

        non_racked = (
            Device.objects.restrict(request.user, "view")
            .filter(
                rack__in=racks,
                position__isnull=True,
                parent_bay__isnull=True,
            )
            .exclude(device_type__subdevice_role="child")
            .exclude(device_type__u_height=0)  # 0U types (PDU strips) never mount
            .select_related("device_type", "role", "rack")
            # device_name (dcim.svg.racks.get_device_name) reads this annotation,
            # which get_rack_units adds for mounted devices but nothing adds here.
            .annotate(devicebay_count=Count("devicebays"))
        )
        non_racked = list(non_racked)
        _attach_meta([c["units"] for c in columns], non_racked)

        config = get_config()

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "error": error,
                "columns": columns,
                "face": face,
                "other_face": (
                    DeviceFaceChoices.FACE_REAR
                    if face == DeviceFaceChoices.FACE_FRONT
                    else DeviceFaceChoices.FACE_FRONT
                ),
                "non_racked": non_racked,
                "images": images,
                "labels": labels,
                "selected_view": selected_view,
                "unit_width": config.RACK_ELEVATION_DEFAULT_UNIT_WIDTH,
                "peak_available": peak_available(),
                "basepath": settings.BASE_PATH,
            },
        )

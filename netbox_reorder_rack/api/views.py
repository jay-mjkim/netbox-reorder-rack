import decimal
from collections import namedtuple

from dcim.models import Device
from dcim.models import Rack
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from netbox.api.authentication import TokenPermissions
from rest_framework import serializers
from rest_framework import status
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from utilities.permissions import get_permission_for_model


def get_device_name(device):
    if device.virtual_chassis:
        name = f"{device.virtual_chassis.name}:{device.vc_position}"
    elif device.name:
        name = device.name
    else:
        name = str(device.device_type)

    return name


class ReorderRackSerializer(serializers.Serializer):
    rack_id = serializers.IntegerField()
    front = serializers.ListField(child=serializers.JSONField())
    rear = serializers.ListField(child=serializers.JSONField())
    other = serializers.ListField(child=serializers.JSONField())


class SaveViewSet(viewsets.ViewSet):
    # dcim.change_device is enforced by NetBox's TokenPermissions (PUT -> change), and
    # per device in _check_permission. Django's PermissionRequiredMixin used to sit in
    # front of that and raise, which the API middleware reported as a 500.
    serializer_class = ReorderRackSerializer
    queryset = Device.objects.none()
    schema = None

    def update(self, request, pk):
        rack = get_object_or_404(Rack, pk=pk)
        permission = get_permission_for_model(Device, "change")

        # Validate input using serializer
        serializer = ReorderRackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            changes_made = False  # Flag to track if any changes were made

            with transaction.atomic():
                # Two-phase save: a multi-device reorder can pass through transient
                # overlaps (e.g. swapping two devices). Saving devices one by one with
                # clean() would hit "U already occupied" against a device that has not
                # moved yet and roll back the whole transaction. So:
                #   1) collect every change and check permissions,
                #   2) unrack every device that moves (vacate its old slot),
                #   3) place each device at its new slot and validate with clean().
                changes = []
                changes += self._collect_changes(
                    request, rack, serializer.validated_data["front"], permission
                )
                changes += self._collect_changes(
                    request, rack, serializer.validated_data["rear"], permission
                )
                changes += self._collect_changes(
                    request,
                    rack,
                    serializer.validated_data["other"],
                    permission,
                    is_other=True,
                )
                changes_made = bool(changes)

                # Phase 1: vacate old slots
                for device, _position, _face in changes:
                    device.position = None
                    device.face = ""
                    device.save()

                # Phase 2: place at new slots (validated against final state)
                for device, position, face in changes:
                    if position is None:
                        continue  # moved to "other" (unracked) - already done
                    device.position = position
                    device.face = face
                    device.clean()
                    device.save()

                # If no changes were made, return 304 or a custom response
                if not changes_made:
                    return Response(
                        {"message": "No changes detected."},
                        status=status.HTTP_304_NOT_MODIFIED,
                    )

                return Response(
                    {
                        "message": "Devices reordered successfully",
                        "data": serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )
        except PermissionDenied as e:
            return Response(
                {"message": "Permission denied", "error": str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"message": "Error saving data", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _collect_changes(
        self, request, rack, device_data_list, permission, is_other=False
    ):
        """Return [(device, new_position, new_face)] for devices whose placement changes.

        new_position is None for devices moved to "other" (unracked).
        """
        changes = []

        for device_data in device_data_list:
            device = rack.devices.filter(pk=device_data["id"]).first()
            current_device = get_object_or_404(
                Device.objects.restrict(request.user), pk=device_data["id"]
            )

            if is_other:
                if device.position != device_data["y"]:
                    self._check_permission(request, device, permission)
                    changes.append((device, None, ""))
            else:
                new_position = decimal.Decimal(device_data["y"])
                if (
                    current_device.face != device_data["face"]
                    or device.position != new_position
                ):
                    self._check_permission(request, device, permission)
                    changes.append((device, new_position, device_data["face"]))

        return changes

    def _check_permission(self, request, device, permission):
        """Helper method to check if the user has permission for the device."""
        if not request.user.has_perm(permission, obj=device):
            raise PermissionDenied(
                _(f"You do not have permissions to edit {get_device_name(device)}.")
            )


# A device's destination in the row view: which rack, and position/face within it
# (position None = assigned to that rack but unmounted).
RowMove = namedtuple("RowMove", ("device", "rack", "position", "face"))


class RowItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    rack_id = serializers.IntegerField()
    y = serializers.DecimalField(max_digits=6, decimal_places=1, allow_null=True)
    face = serializers.CharField(allow_blank=True, required=False, default="")


class ReorderRowSerializer(serializers.Serializer):
    items = serializers.ListField(child=RowItemSerializer())


class ChangeOnPostPermissions(TokenPermissions):
    """
    The row save is a POST (a plain list route has no pk to PUT to), but what it
    does is change devices, so ask for dcim.change_device rather than the add
    permission NetBox maps POST to by default.
    """

    perms_map = {
        **TokenPermissions.perms_map,
        "POST": ["%(app_label)s.change_%(model_name)s"],
    }


class SaveRowViewSet(viewsets.ViewSet):
    """
    Save a multi-rack layout: POST /api/plugins/reorder/save-row/

    Same two-phase save as SaveViewSet (vacate every moving device, then place),
    which is what makes a swap between two racks, or a device moving into a unit
    another device is leaving, validate cleanly. On top of that a device may
    change rack; its site and location follow the target rack, as Device.clean()
    requires.
    """

    # Model-level permission comes from permission_classes (DRF, so a miss is a
    # proper 403); the per-device object check is in _check_permission.
    permission_classes = [ChangeOnPostPermissions]
    serializer_class = ReorderRowSerializer
    queryset = Device.objects.none()
    schema = None

    def create(self, request):
        serializer = ReorderRowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["items"]
        permission = get_permission_for_model(Device, "change")

        rack_ids = {item["rack_id"] for item in items}
        racks = {
            rack.pk: rack
            for rack in Rack.objects.restrict(request.user, "view").filter(
                pk__in=rack_ids
            )
        }
        if missing := rack_ids - racks.keys():
            return Response(
                {"message": "Unknown rack", "error": f"rack id(s) {sorted(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len({rack.site_id for rack in racks.values()}) > 1:
            return Response(
                {
                    "message": "Racks span more than one site",
                    "error": "All racks in one save must belong to the same site.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                moves = []
                for item in items:
                    device = get_object_or_404(
                        Device.objects.restrict(request.user), pk=item["id"]
                    )
                    rack = racks[item["rack_id"]]
                    position = item["y"]
                    face = item["face"] if position is not None else ""
                    if (
                        device.rack_id == rack.pk
                        and device.position == position
                        and device.face == face
                    ):
                        continue
                    self._check_permission(request, device, permission)
                    moves.append(RowMove(device, rack, position, face))

                if not moves:
                    return Response(
                        {"message": "No changes detected."},
                        status=status.HTTP_304_NOT_MODIFIED,
                    )

                # Phase 1: vacate old slots
                for move in moves:
                    move.device.position = None
                    move.device.face = ""
                    move.device.save()

                # Phase 2: place at new slots (validated against final state)
                for move in moves:
                    device = move.device
                    device.rack = move.rack
                    device.site = move.rack.site
                    device.location = move.rack.location
                    device.position = move.position
                    device.face = move.face
                    device.clean()
                    device.save()

                return Response(
                    {
                        "message": "Devices reordered successfully",
                        "moved": len(moves),
                    },
                    status=status.HTTP_201_CREATED,
                )
        except PermissionDenied as e:
            return Response(
                {"message": "Permission denied", "error": str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"message": "Error saving data", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _check_permission(self, request, device, permission):
        if not request.user.has_perm(permission, obj=device):
            raise PermissionDenied(
                _(f"You do not have permissions to edit {get_device_name(device)}.")
            )

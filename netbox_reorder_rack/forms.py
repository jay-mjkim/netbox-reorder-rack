from dcim.choices import DeviceFaceChoices
from dcim.models import Location
from dcim.models import Rack
from dcim.models import Site
from django import forms
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.fields import DynamicModelMultipleChoiceField


class RowSelectForm(forms.Form):
    """Pick the racks to lay out side by side. Field names are the query params."""

    site_id = DynamicModelChoiceField(
        queryset=Site.objects.all(), required=False, label="Site"
    )
    location_id = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Location",
        query_params={"site_id": "$site_id"},
    )
    rack_id = DynamicModelMultipleChoiceField(
        queryset=Rack.objects.all(),
        required=False,
        label="Racks",
        query_params={"site_id": "$site_id", "location_id": "$location_id"},
    )
    face = forms.ChoiceField(
        choices=DeviceFaceChoices, initial=DeviceFaceChoices.FACE_FRONT, label="Face"
    )

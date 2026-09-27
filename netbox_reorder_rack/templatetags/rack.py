import hashlib
from functools import lru_cache

from dcim.svg.racks import get_device_name
from django import template
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static
from utilities.html import foreground_color

register = template.Library()


@register.filter()
def rack_unit(value):
    if value % 1 == 0:
        return True
    else:
        return False


@register.filter()
def rack_unit_to_int(value):
    return int(value)


@register.filter()
def calculate_u_position(unit, rack):
    u_height = rack.u_height * 2
    height = int(unit.get("height", 1) * 2)
    unit_id = int(unit["id"] * 2)

    if rack.desc_units:
        return unit_id - 2
    else:
        if height > 1:
            return u_height - unit_id - height + 2
        else:
            return u_height - unit_id


@register.filter()
def mul(value, mul_value):
    return int(value) * mul_value


@register.filter()
def text_color(value):
    return foreground_color(value)


@register.filter()
def device_name(device):
    return get_device_name(device)


@lru_cache(maxsize=None)
def _static_hash(path):
    """Short content hash of a static file, so a rebuilt bundle gets a new URL.

    NetBox's static route is served with a day-long max-age; without a version
    in the URL a browser keeps the previous plugin JS/CSS after an upgrade.
    """
    location = finders.find(path)
    if location is None:
        try:
            location = staticfiles_storage.path(path)
        except NotImplementedError:
            return ""
    try:
        with open(location, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except OSError:
        return ""


@register.simple_tag
def static_v(path):
    url = static(path)
    digest = _static_hash(path)
    return f"{url}?v={digest}" if digest else url

"""
Per-device and per-rack power / weight figures shown on the reorder grids.

Everything comes from NetBox's own model:

* PSU:     the device's PowerPorts. Count = number of PSUs, ``maximum_draw`` =
           the PSU rating. Two or more ports are read as redundant (1+1), so the
           *effective* rating a rack has to feed is one PSU, not the sum.
* peak:    custom field ``measured_peak_power_w`` on the device (optional). A
           device without it is counted as "unmeasured" rather than as zero, so
           a rack total says how many devices it could not account for.
* weight:  ``Device.total_weight`` (device type + modules), in kg.
* rack:    capacity = sum of its PowerFeeds' ``available_power`` (NetBox already
           derates that by the feed's ``max_utilization``); weight limit =
           ``Rack.max_weight``.
"""

from collections import defaultdict

from dcim.models import PowerPort

PEAK_FIELD = "measured_peak_power_w"


def device_meta_map(devices):
    """{device_id: meta} for an iterable of Device instances, in a fixed number of queries."""
    devices = list(devices)
    ports = defaultdict(list)
    for device_id, draw in PowerPort.objects.filter(device__in=devices).values_list(
        "device_id", "maximum_draw"
    ):
        ports[device_id].append(draw)
    return {d.pk: device_meta(d, ports.get(d.pk, [])) for d in devices}


def device_meta(device, port_draws):
    ratings = [w for w in port_draws if w]
    psu_count = len(port_draws)
    psu_w = max(ratings) if ratings else None
    if psu_w is None:
        rated_w = None
    elif psu_count >= 2:
        rated_w = psu_w  # redundant pair: the rack only ever feeds one PSU's worth
    else:
        rated_w = sum(ratings)
    peak_w = (getattr(device, "cf", None) or {}).get(PEAK_FIELD)
    weight_kg = device.total_weight or None
    return {
        "psu_count": psu_count,
        "psu_w": psu_w,
        "psu_label": _psu_label(psu_count, psu_w),
        "rated_w": rated_w,
        "peak_w": peak_w,
        "weight_kg": weight_kg,
    }


def _psu_label(count, watts):
    if not count:
        return ""
    w = f"{watts:,}W" if watts else "?W"
    if count >= 2:
        return f"{count}×{w} ({count - 1}+1)"
    return w


def rack_capacity(rack):
    """Usable power (W) from the rack's feeds, and its weight limit (kg)."""
    capacity_w = sum(feed.available_power or 0 for feed in rack.powerfeeds.all())
    max_weight_kg = None
    if rack._abs_max_weight:
        max_weight_kg = round(rack._abs_max_weight / 1000, 2)
        if max_weight_kg == int(max_weight_kg):
            max_weight_kg = int(max_weight_kg)  # "1000" rather than "1000.0" in the UI
    return {"capacity_w": capacity_w or None, "max_weight_kg": max_weight_kg}

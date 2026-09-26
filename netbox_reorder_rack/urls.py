from django.urls import include
from django.urls import path
from utilities.urls import get_model_urls

from netbox_reorder_rack.views import ReorderRowView
from netbox_reorder_rack.views import ReorderView  # noqa: F401

urlpatterns = (
    path(
        "reorder/<int:pk>/",
        include(get_model_urls("dcim", "rack")),
    ),
    path("row/", ReorderRowView.as_view(), name="row"),
)

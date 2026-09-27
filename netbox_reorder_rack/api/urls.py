from netbox.api.routers import NetBoxRouter

from netbox_reorder_rack.api import views

router = NetBoxRouter()

router.register("save", views.SaveViewSet, basename="reorder")
router.register("save-row", views.SaveRowViewSet, basename="reorder-row")

urlpatterns = router.urls

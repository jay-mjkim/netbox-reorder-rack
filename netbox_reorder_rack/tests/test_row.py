from core.models import ObjectType
from dcim.models import Device
from dcim.models import DeviceRole
from dcim.models import DeviceType
from dcim.models import Location
from dcim.models import Manufacturer
from dcim.models import Rack
from dcim.models import Site
from users.models import ObjectPermission
from utilities.testing import TestCase


class RowTestMixin:
    @classmethod
    def setUpTestData(cls):
        cls.site = Site.objects.create(name="Row Site", slug="row-site")
        cls.other_site = Site.objects.create(name="Other Site", slug="other-site")
        cls.location = Location.objects.create(
            name="Row A", slug="row-a", site=cls.site
        )
        cls.rack1 = Rack.objects.create(
            name="Rack 1", site=cls.site, location=cls.location, u_height=12
        )
        cls.rack2 = Rack.objects.create(
            name="Rack 2", site=cls.site, location=cls.location, u_height=12
        )
        cls.rack3 = Rack.objects.create(name="Rack 3", site=cls.site, u_height=12)
        cls.foreign_rack = Rack.objects.create(
            name="Foreign", site=cls.other_site, u_height=12
        )
        manufacturer = Manufacturer.objects.create(name="Mfr", slug="mfr")
        role = DeviceRole.objects.create(name="Role", slug="role")
        cls.one_u = DeviceType.objects.create(
            manufacturer=manufacturer, model="1U", slug="1u", u_height=1
        )
        cls.two_u = DeviceType.objects.create(
            manufacturer=manufacturer, model="2U", slug="2u", u_height=2
        )
        specs = [
            ("A", cls.one_u, cls.rack1, 1),
            ("B", cls.two_u, cls.rack1, 5),
            ("C", cls.one_u, cls.rack2, 1),
            ("Spare", cls.one_u, cls.rack2, None),
        ]
        for name, device_type, rack, position in specs:
            device = Device(
                name=name,
                device_type=device_type,
                role=role,
                site=rack.site,
                location=rack.location,
                rack=rack,
                position=position,
                face="front" if position else "",
            )
            device.clean()
            device.save()

    def grant(self, *actions):
        perm = ObjectPermission(name="perm", actions=list(actions))
        perm.save()
        perm.users.add(self.user)
        perm.object_types.add(
            ObjectType.objects.get_for_model(Device),
            ObjectType.objects.get_for_model(Rack),
        )

    @staticmethod
    def item(device, rack, position, face="front"):
        return {"id": device.pk, "rack_id": rack.pk, "y": position, "face": face}

    def post(self, items):
        return self.client.post(
            "/api/plugins/reorder/save-row/",
            {"items": items},
            content_type="application/json",
        )


class ReorderRowViewTest(RowTestMixin, TestCase):
    def test_requires_change_permission(self):
        # Django's PermissionRequiredMixin raises; let the client turn it into a 403.
        self.client.raise_request_exception = False
        response = self.client.get(f"/plugins/reorder/row/?rack_id={self.rack1.pk}")
        self.assertHttpStatus(response, 403)

    def test_renders_selected_racks(self):
        self.grant("view", "change")
        response = self.client.get(
            f"/plugins/reorder/row/?rack_id={self.rack1.pk}&rack_id={self.rack2.pk}"
        )
        self.assertHttpStatus(response, 200)
        content = response.content.decode()
        self.assertIn(f'id="grid-rack-{self.rack1.pk}"', content)
        self.assertIn(f'id="grid-rack-{self.rack2.pk}"', content)
        self.assertNotIn(f'id="grid-rack-{self.rack3.pk}"', content)
        # The unmounted device sits in the shared bin, tagged with its rack.
        self.assertIn(f'data-rack-id="{self.rack2.pk}"', content)
        self.assertRegex(content, r">\s*Spare\s*<")

    def test_location_filter_and_list_passthrough_id(self):
        self.grant("view", "change")
        response = self.client.get(
            f"/plugins/reorder/row/?location_id={self.location.pk}"
        )
        content = response.content.decode()
        self.assertIn(f'id="grid-rack-{self.rack1.pk}"', content)
        self.assertNotIn(f'id="grid-rack-{self.rack3.pk}"', content)

        response = self.client.get(f"/plugins/reorder/row/?id={self.rack3.pk}")
        self.assertIn(f'id="grid-rack-{self.rack3.pk}"', response.content.decode())

    def test_mixed_sites_rejected(self):
        self.grant("view", "change")
        response = self.client.get(
            f"/plugins/reorder/row/?rack_id={self.rack1.pk}&rack_id={self.foreign_rack.pk}"
        )
        self.assertHttpStatus(response, 200)
        content = response.content.decode()
        self.assertIn("same site", content)
        self.assertNotIn("grid-rack-", content)


class ReorderRowAPITest(RowTestMixin, TestCase):
    def test_move_between_racks(self):
        self.grant("view", "change")
        a = Device.objects.get(name="A")
        resp = self.post([self.item(a, self.rack2, 3)])
        self.assertHttpStatus(resp, 201)
        a.refresh_from_db()
        self.assertEqual((a.rack, a.position, a.face), (self.rack2, 3, "front"))
        self.assertEqual(a.site, self.site)
        self.assertEqual(a.location, self.location)

    def test_swap_across_racks(self):
        """A and C trade racks and units; neither slot is free until the other moves."""
        self.grant("view", "change")
        a = Device.objects.get(name="A")
        c = Device.objects.get(name="C")
        resp = self.post([self.item(a, self.rack2, 1), self.item(c, self.rack1, 1)])
        self.assertHttpStatus(resp, 201)
        a.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual((a.rack, a.position), (self.rack2, 1))
        self.assertEqual((c.rack, c.position), (self.rack1, 1))

    def test_location_follows_rack(self):
        self.grant("view", "change")
        b = Device.objects.get(name="B")
        resp = self.post([self.item(b, self.rack3, 8)])
        self.assertHttpStatus(resp, 201)
        b.refresh_from_db()
        self.assertEqual(b.rack, self.rack3)
        self.assertIsNone(b.location)

    def test_mount_from_bin_and_unmount(self):
        self.grant("view", "change")
        spare = Device.objects.get(name="Spare")
        c = Device.objects.get(name="C")
        resp = self.post(
            [self.item(spare, self.rack1, 10), self.item(c, self.rack2, None, "")]
        )
        self.assertHttpStatus(resp, 201)
        spare.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual((spare.rack, spare.position), (self.rack1, 10))
        self.assertEqual((c.rack, c.position, c.face), (self.rack2, None, ""))

    def test_overlap_is_rejected_and_rolled_back(self):
        self.grant("view", "change")
        a = Device.objects.get(name="A")
        # B occupies U5-6 in rack 1; a 1U device asking for U6 must fail.
        resp = self.post([self.item(a, self.rack1, 6)])
        self.assertHttpStatus(resp, 500)
        a.refresh_from_db()
        self.assertEqual(a.position, 1)

    def test_no_changes(self):
        self.grant("view", "change")
        a = Device.objects.get(name="A")
        resp = self.post([self.item(a, self.rack1, 1)])
        self.assertHttpStatus(resp, 304)

    def test_unknown_rack_and_mixed_sites(self):
        self.grant("view", "change")
        a = Device.objects.get(name="A")
        c = Device.objects.get(name="C")
        resp = self.post([{"id": a.pk, "rack_id": 999999, "y": 1, "face": "front"}])
        self.assertHttpStatus(resp, 400)
        resp = self.post(
            [self.item(a, self.rack1, 2), self.item(c, self.foreign_rack, 1)]
        )
        self.assertHttpStatus(resp, 400)
        a.refresh_from_db()
        self.assertEqual(a.position, 1)

    def test_change_permission_required(self):
        self.client.raise_request_exception = False
        self.grant("view")
        a = Device.objects.get(name="A")
        resp = self.post([self.item(a, self.rack2, 3)])
        self.assertHttpStatus(resp, 403)
        a.refresh_from_db()
        self.assertEqual(a.rack, self.rack1)

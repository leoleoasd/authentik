"""SCIM Membership tests"""

from django.test import TestCase
from requests_mock import Mocker

from authentik.blueprints.tests import apply_blueprint
from authentik.core.models import Application, Group, User
from authentik.lib.generators import generate_id
from authentik.providers.scim.clients.schema import ServiceProviderConfiguration
from authentik.providers.scim.models import (
    SCIMCompatibilityMode,
    SCIMMapping,
    SCIMProvider,
    SCIMProviderGroup,
)
from authentik.providers.scim.tasks import scim_sync
from authentik.tenants.models import Tenant


class SCIMMembershipTests(TestCase):
    """SCIM Membership tests"""

    provider: SCIMProvider
    app: Application

    def setUp(self) -> None:
        # Delete all users and groups as the mocked HTTP responses only return one ID
        # which will cause errors with multiple users
        User.objects.all().exclude_anonymous().delete()
        Group.objects.all().delete()
        Tenant.objects.update(avatars="none")

    @apply_blueprint("system/providers-scim.yaml")
    def configure(self, **kwargs) -> None:
        """Configure provider"""
        self.provider: SCIMProvider = SCIMProvider.objects.create(
            name=generate_id(),
            url="https://localhost",
            token=generate_id(),
            **kwargs,
        )
        self.app: Application = Application.objects.create(
            name=generate_id(),
            slug=generate_id(),
        )
        self.app.backchannel_providers.add(self.provider)
        self.provider.save()
        self.provider.property_mappings.set(
            [SCIMMapping.objects.get(managed="goauthentik.io/providers/scim/user")]
        )
        self.provider.property_mappings_group.set(
            [SCIMMapping.objects.get(managed="goauthentik.io/providers/scim/group")]
        )

    def test_member_add(self):
        """Test member add"""
        config = ServiceProviderConfiguration.default()

        config.patch.supported = True
        user_scim_id = generate_id()
        group_scim_id = generate_id()
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )

        user = User.objects.create(username=generate_id())

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.post(
                "https://localhost/Users",
                json={
                    "id": user_scim_id,
                },
            )
            mocker.post(
                "https://localhost/Groups",
                json={
                    "id": group_scim_id,
                },
            )

            self.configure()
            scim_sync.send(self.provider.pk)

            self.assertEqual(mocker.call_count, 3)
            self.assertEqual(mocker.request_history[0].method, "GET")
            self.assertEqual(mocker.request_history[1].method, "POST")
            self.assertEqual(mocker.request_history[2].method, "POST")
            self.assertJSONEqual(
                mocker.request_history[1].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "emails": [],
                    "active": True,
                    "externalId": user.uid,
                    "name": {"familyName": " ", "formatted": " ", "givenName": ""},
                    "displayName": "",
                    "userName": user.username,
                },
            )
            self.assertJSONEqual(
                mocker.request_history[2].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                    "externalId": str(group.pk),
                    "displayName": group.name,
                },
            )

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.patch(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            group.users.add(user)
            self.assertEqual(mocker.call_count, 1)
            self.assertEqual(mocker.request_history[0].method, "PATCH")
            self.assertJSONEqual(
                mocker.request_history[0].body,
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [
                        {
                            "op": "add",
                            "path": "members",
                            "value": [{"value": user_scim_id}],
                        }
                    ],
                },
            )

    def test_member_remove(self):
        """Test member remove"""
        config = ServiceProviderConfiguration.default()

        config.patch.supported = True
        user_scim_id = generate_id()
        group_scim_id = generate_id()
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )

        user = User.objects.create(username=generate_id())

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.post(
                "https://localhost/Users",
                json={
                    "id": user_scim_id,
                },
            )
            mocker.post(
                "https://localhost/Groups",
                json={
                    "id": group_scim_id,
                },
            )

            self.configure()
            scim_sync.send(self.provider.pk)

            self.assertEqual(mocker.call_count, 3)
            self.assertEqual(mocker.request_history[0].method, "GET")
            self.assertEqual(mocker.request_history[1].method, "POST")
            self.assertEqual(mocker.request_history[2].method, "POST")
            self.assertJSONEqual(
                mocker.request_history[1].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "active": True,
                    "displayName": "",
                    "emails": [],
                    "externalId": user.uid,
                    "name": {"familyName": " ", "formatted": " ", "givenName": ""},
                    "userName": user.username,
                },
            )
            self.assertJSONEqual(
                mocker.request_history[2].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                    "externalId": str(group.pk),
                    "displayName": group.name,
                },
            )

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.patch(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            group.users.add(user)
            self.assertEqual(mocker.call_count, 1)
            self.assertEqual(mocker.request_history[0].method, "PATCH")
            self.assertJSONEqual(
                mocker.request_history[0].body,
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [
                        {
                            "op": "add",
                            "path": "members",
                            "value": [{"value": user_scim_id}],
                        }
                    ],
                },
            )

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.patch(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            group.users.remove(user)
            self.assertEqual(mocker.call_count, 1)
            self.assertEqual(mocker.request_history[0].method, "PATCH")
            self.assertJSONEqual(
                mocker.request_history[0].body,
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [
                        {
                            "op": "remove",
                            "path": "members",
                            "value": [{"value": user_scim_id}],
                        }
                    ],
                },
            )

    def test_member_add_save(self):
        """Test member add + save"""
        config = ServiceProviderConfiguration.default()

        config.patch.supported = True
        user_scim_id = generate_id()
        group_scim_id = generate_id()
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )

        user = User.objects.create(username=generate_id())

        # Test initial sync of group creation
        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.post(
                "https://localhost/Users",
                json={
                    "id": user_scim_id,
                },
            )
            mocker.post(
                "https://localhost/Groups",
                json={
                    "id": group_scim_id,
                },
            )

            self.configure()
            scim_sync.send(self.provider.pk)

            self.assertEqual(mocker.call_count, 3)
            self.assertEqual(mocker.request_history[0].method, "GET")
            self.assertEqual(mocker.request_history[1].method, "POST")
            self.assertEqual(mocker.request_history[2].method, "POST")
            self.assertJSONEqual(
                mocker.request_history[1].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "emails": [],
                    "active": True,
                    "externalId": user.uid,
                    "name": {"familyName": " ", "formatted": " ", "givenName": ""},
                    "displayName": "",
                    "userName": user.username,
                },
            )
            self.assertJSONEqual(
                mocker.request_history[2].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                    "externalId": str(group.pk),
                    "displayName": group.name,
                },
            )

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.get(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            mocker.patch(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            group.users.add(user)
            group.save()
            self.assertEqual(mocker.call_count, 3)
            self.assertEqual(mocker.request_history[0].method, "PATCH")
            self.assertEqual(mocker.request_history[1].method, "PATCH")
            self.assertEqual(mocker.request_history[2].method, "GET")
            self.assertJSONEqual(
                mocker.request_history[0].body,
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [
                        {
                            "op": "add",
                            "path": "members",
                            "value": [{"value": user_scim_id}],
                        }
                    ],
                },
            )
            self.assertJSONEqual(
                mocker.request_history[1].body,
                {
                    "Operations": [
                        {
                            "op": "replace",
                            "value": {
                                "id": group_scim_id,
                                "displayName": group.name,
                                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                                "externalId": str(group.pk),
                            },
                        }
                    ]
                },
            )

    def test_member_add_save_compat_webex(self):
        """Test member add + save"""
        config = ServiceProviderConfiguration.default()

        config.patch.supported = True
        user_scim_id = generate_id()
        group_scim_id = generate_id()
        uid = generate_id()
        group = Group.objects.create(
            name=uid,
        )

        user = User.objects.create(username=generate_id())

        # Test initial sync of group creation
        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.post(
                "https://localhost/Users",
                json={
                    "id": user_scim_id,
                },
            )
            mocker.post(
                "https://localhost/Groups",
                json={
                    "id": group_scim_id,
                },
            )

            self.configure(compatibility_mode=SCIMCompatibilityMode.WEBEX)
            scim_sync.send(self.provider.pk)

            self.assertEqual(mocker.call_count, 3)
            self.assertEqual(mocker.request_history[0].method, "GET")
            self.assertEqual(mocker.request_history[1].method, "POST")
            self.assertEqual(mocker.request_history[2].method, "POST")
            self.assertJSONEqual(
                mocker.request_history[1].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "emails": [],
                    "active": True,
                    "externalId": user.uid,
                    "name": {"familyName": " ", "formatted": " ", "givenName": ""},
                    "displayName": "",
                    "userName": user.username,
                },
            )
            self.assertJSONEqual(
                mocker.request_history[2].body,
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                    "externalId": str(group.pk),
                    "displayName": group.name,
                },
            )

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.get(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            mocker.patch(
                f"https://localhost/Groups/{group_scim_id}",
                json={},
            )
            group.users.add(user)
            group.save()
            self.assertEqual(mocker.call_count, 3)
            self.assertEqual(mocker.request_history[0].method, "PATCH")
            self.assertEqual(mocker.request_history[1].method, "PATCH")
            self.assertEqual(mocker.request_history[2].method, "GET")
            self.assertJSONEqual(
                mocker.request_history[0].body,
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [
                        {
                            "op": "add",
                            "path": "members",
                            "value": [{"value": user_scim_id, "type": "user"}],
                        }
                    ],
                },
            )
            self.assertJSONEqual(
                mocker.request_history[1].body,
                {
                    "Operations": [
                        {
                            "op": "replace",
                            "value": {
                                "id": group_scim_id,
                                "displayName": group.name,
                                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                                "externalId": str(group.pk),
                            },
                        }
                    ]
                },
            )

    def test_member_add_flatten_to_ancestor(self):
        """Forced flatten: adding a user to a child group also pushes that user as a
        direct member of every ancestor group."""
        config = ServiceProviderConfiguration.default()
        config.patch.supported = True

        parent = Group.objects.create(name=generate_id())
        child = Group.objects.create(name=generate_id())
        child.parents.add(parent)
        user = User.objects.create(username=generate_id())

        user_scim_id = generate_id()
        parent_post_id = generate_id()
        child_post_id = generate_id()

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.post("https://localhost/Users", json={"id": user_scim_id})
            mocker.post(
                "https://localhost/Groups",
                [{"json": {"id": parent_post_id}}, {"json": {"id": child_post_id}}],
            )

            self.configure()
            scim_sync.send(self.provider.pk)

        # Resolve the real SCIM ids regardless of sync order
        parent_id = SCIMProviderGroup.objects.get(provider=self.provider, group=parent).scim_id
        child_id = SCIMProviderGroup.objects.get(provider=self.provider, group=child).scim_id

        with Mocker() as mocker:
            mocker.get(
                "https://localhost/ServiceProviderConfig",
                json=config.model_dump(),
            )
            mocker.patch(f"https://localhost/Groups/{child_id}", json={})
            mocker.patch(f"https://localhost/Groups/{parent_id}", json={})
            # patch_compare_users GETs the ancestor's current state before diffing
            mocker.get(
                f"https://localhost/Groups/{parent_id}",
                json={"displayName": parent.name, "members": []},
            )

            child.users.add(user)

            patched = [r for r in mocker.request_history if r.method == "PATCH"]
            patched_urls = {r.url for r in patched}
            # both the child itself and its ancestor were patched
            self.assertIn(f"https://localhost/Groups/{child_id}", patched_urls)
            self.assertIn(f"https://localhost/Groups/{parent_id}", patched_urls)
            # the ancestor received the user via flattening
            parent_added: set[str] = set()
            for request in patched:
                if not request.url.endswith(f"/Groups/{parent_id}"):
                    continue
                for op in request.json()["Operations"]:
                    for value in op.get("value", []):
                        parent_added.add(value["value"])
            self.assertIn(user_scim_id, parent_added)

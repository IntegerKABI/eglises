from tests.factories import SaaSTestCase


class UserModelTests(SaaSTestCase):
    def test_user_string_representation_returns_username(self):
        user = self.create_user(username="compte-utilisateur")

        self.assertEqual(str(user), "compte-utilisateur")


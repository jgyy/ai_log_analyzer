import unittest

from pydantic import ValidationError

from schemas import UserRoleUpdate


class UserRoleUpdateTests(unittest.TestCase):
    def test_accepts_known_role(self):
        update = UserRoleUpdate(role="sre")
        self.assertEqual(update.role.value, "sre")

    def test_rejects_unknown_role(self):
        with self.assertRaises(ValidationError):
            UserRoleUpdate(role="superadmin")


if __name__ == "__main__":
    unittest.main()

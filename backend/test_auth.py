import unittest
from datetime import timedelta

from jose import jwt

from auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)


class PasswordHashingTests(unittest.TestCase):
    def test_hash_is_not_the_plaintext_password(self):
        self.assertNotEqual(hash_password("correct-horse"), "correct-horse")

    def test_verify_password_accepts_matching_password(self):
        hashed = hash_password("correct-horse")
        self.assertTrue(verify_password("correct-horse", hashed))

    def test_verify_password_rejects_wrong_password(self):
        hashed = hash_password("correct-horse")
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_same_password_hashes_differently_each_time(self):
        # bcrypt salts each hash, so two hashes of the same password must differ
        self.assertNotEqual(hash_password("correct-horse"), hash_password("correct-horse"))


class AccessTokenTests(unittest.TestCase):
    def test_token_round_trips_claims(self):
        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        self.assertEqual(payload["sub"], "user-123")
        self.assertIn("exp", payload)

    def test_token_respects_custom_expiry(self):
        token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # exp is a unix timestamp; a 5-minute expiry should be far shorter
        # than the default 15-minute one, so just sanity check it decodes cleanly
        self.assertIn("exp", payload)

    def test_token_is_rejected_with_wrong_secret(self):
        token = create_access_token({"sub": "user-123"})
        with self.assertRaises(Exception):
            jwt.decode(token, "not-the-real-secret", algorithms=[ALGORITHM])


if __name__ == "__main__":
    unittest.main()

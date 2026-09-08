import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.security import (
    hash_password, verify_password, Role, has_permission,
    TokenConfig, create_access_token, create_refresh_token, decode_token, TokenError,
)


class TestPasswordHashing(unittest.TestCase):
    def test_hash_then_verify_succeeds(self):
        h = hash_password("correct-horse-battery-staple")
        self.assertTrue(verify_password("correct-horse-battery-staple", h))

    def test_wrong_password_fails(self):
        h = hash_password("correct-horse-battery-staple")
        self.assertFalse(verify_password("wrong-password", h))

    def test_hashes_are_salted_differently(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        self.assertNotEqual(h1, h2)
        self.assertTrue(verify_password("same-password", h1))
        self.assertTrue(verify_password("same-password", h2))

    def test_malformed_hash_does_not_crash(self):
        self.assertFalse(verify_password("anything", "not-a-real-hash"))


class TestRBAC(unittest.TestCase):
    def test_admin_can_manage_routes(self):
        self.assertTrue(has_permission(Role.ADMIN, "manage_routes"))

    def test_viewer_cannot_manage_routes(self):
        self.assertFalse(has_permission(Role.VIEWER, "manage_routes"))

    def test_analyst_can_run_backtesting_but_not_manage_users(self):
        self.assertTrue(has_permission(Role.ANALYST, "run_backtesting"))
        self.assertFalse(has_permission(Role.ANALYST, "manage_users"))

    def test_all_roles_can_view_dashboard(self):
        for role in Role:
            self.assertTrue(has_permission(role, "view_dashboard"))

    def test_unknown_permission_raises(self):
        with self.assertRaises(ValueError):
            has_permission(Role.ADMIN, "not_a_real_permission")


class TestJWT(unittest.TestCase):
    def setUp(self):
        self.config = TokenConfig(secret_key="test-secret-do-not-use-in-prod", access_token_expire_minutes=60)

    def test_access_token_roundtrip(self):
        token = create_access_token("analyst@airindex.gov.in", Role.ANALYST, self.config)
        payload = decode_token(token, self.config, expected_type="access")
        self.assertEqual(payload["sub"], "analyst@airindex.gov.in")
        self.assertEqual(payload["role"], "ANALYST")

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token("admin@airindex.gov.in", self.config)
        payload = decode_token(token, self.config, expected_type="refresh")
        self.assertEqual(payload["sub"], "admin@airindex.gov.in")

    def test_wrong_token_type_rejected(self):
        access = create_access_token("u@x.com", Role.VIEWER, self.config)
        with self.assertRaises(TokenError):
            decode_token(access, self.config, expected_type="refresh")

    def test_expired_token_rejected(self):
        short_config = TokenConfig(secret_key="test-secret-do-not-use-in-prod", access_token_expire_minutes=0)
        token = create_access_token("u@x.com", Role.VIEWER, short_config)
        time.sleep(1.2)
        with self.assertRaises(TokenError):
            decode_token(token, short_config, expected_type="access")

    def test_tampered_token_rejected(self):
        token = create_access_token("u@x.com", Role.VIEWER, self.config)
        tampered = token[:-4] + "abcd"
        with self.assertRaises(TokenError):
            decode_token(tampered, self.config)

    def test_wrong_secret_rejected(self):
        token = create_access_token("u@x.com", Role.VIEWER, self.config)
        wrong_config = TokenConfig(secret_key="a-completely-different-secret")
        with self.assertRaises(TokenError):
            decode_token(token, wrong_config)


if __name__ == "__main__":
    unittest.main(verbosity=2)

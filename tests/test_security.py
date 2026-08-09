"""Password hashing, verification and policy."""

import pytest

from src.auth.security import (
    generate_password,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)


class TestHashing:
    def test_hash_is_not_the_plaintext(self):
        password = "CorrectHorseBattery1"
        stored = hash_password(password)
        assert password not in stored
        assert stored.startswith("pbkdf2_sha256$")

    def test_verify_accepts_correct_password(self):
        stored = hash_password("CorrectHorseBattery1")
        assert verify_password("CorrectHorseBattery1", stored) is True

    def test_verify_rejects_wrong_password(self):
        stored = hash_password("CorrectHorseBattery1")
        assert verify_password("correcthorsebattery1", stored) is False
        assert verify_password("", stored) is False

    def test_same_password_hashes_differently(self):
        """A per-hash salt means identical passwords must not collide."""
        assert hash_password("SamePassword1") != hash_password("SamePassword1")

    @pytest.mark.parametrize("stored", [
        "", "not-a-hash", "pbkdf2_sha256$bad", "md5$1$aa$bb",
        "pbkdf2_sha256$notanumber$aa$bb", None,
    ])
    def test_verify_rejects_malformed_hashes_without_raising(self, stored):
        assert verify_password("anything", stored) is False

    def test_hash_rejects_empty_password(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_unicode_passwords_round_trip(self):
        password = "Pässwörd–123✓"
        assert verify_password(password, hash_password(password)) is True


class TestRehash:
    def test_current_hash_does_not_need_rehash(self):
        assert needs_rehash(hash_password("SomePassword1")) is False

    def test_weaker_iteration_count_needs_rehash(self):
        assert needs_rehash(hash_password("SomePassword1", iterations=1000)) is True

    def test_unknown_algorithm_needs_rehash(self):
        assert needs_rehash("md5$1$aa$bb") is True


class TestPasswordPolicy:
    def test_strong_password_passes(self):
        assert validate_password_strength("CorrectHorse1Battery") == []

    @pytest.mark.parametrize("password,expected_fragment", [
        ("Short1A", "at least"),
        ("alllowercase123", "uppercase"),
        ("ALLUPPERCASE123", "lowercase"),
        ("NoDigitsInHereAtAll", "digit"),
    ])
    def test_weak_passwords_are_reported(self, password, expected_fragment):
        problems = validate_password_strength(password)
        assert any(expected_fragment in p for p in problems), problems

    def test_generated_passwords_satisfy_the_policy(self):
        for _ in range(25):
            assert validate_password_strength(generate_password()) == []

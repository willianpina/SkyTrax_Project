from pipelines.fingerprinting import review_fingerprint


def test_review_fingerprint_is_stable() -> None:
    assert review_fingerprint("British Airways", "Great flight") == review_fingerprint(
        " british airways ",
        "great flight",
    )


def test_review_fingerprint_changes_with_content() -> None:
    assert review_fingerprint("British Airways", "Great flight") != review_fingerprint("British Airways", "Bad flight")

import pytest
from multiping import multi_ping, MultiPingError


def test_wrong_timeout() -> None:
    with pytest.raises(MultiPingError):
        multi_ping(['google.com'], 0)


def test_wrong_retry() -> None:
    with pytest.raises(MultiPingError):
        multi_ping(['google.com'], 0.1, retry=10)
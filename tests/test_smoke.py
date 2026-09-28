import gameai
import gameai.common


def test_package_imports() -> None:
    assert gameai.__doc__
    assert gameai.common.__doc__

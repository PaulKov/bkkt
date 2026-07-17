import importlib
import pkgutil


def test_import_all_connectctl_modules() -> None:
    """Страховочный тест на отсутствие битых импортов.

    Цель: ловить случаи, когда в коде остаётся `from x import y`, но y переехал/удалён,
    либо модуль не импортируется из-за синтаксической ошибки.
    """

    import connectctl

    for m in pkgutil.walk_packages(
        connectctl.__path__, prefix=f"{connectctl.__name__}."
    ):
        importlib.import_module(m.name)

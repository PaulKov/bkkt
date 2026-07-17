from __future__ import annotations

from connectctl.aws.glue_catalog import GlueDatabaseSpec, ensure_glue_database


class _FakeClientError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeGlueClient:
    def __init__(self, *, get_result=None, create_result=None):
        self.get_result = get_result
        self.create_result = create_result
        self.calls = []

    def get_database(self, **kwargs):
        self.calls.append(("get_database", kwargs))
        if isinstance(self.get_result, BaseException):
            raise self.get_result
        return self.get_result

    def create_database(self, **kwargs):
        self.calls.append(("create_database", kwargs))
        if isinstance(self.create_result, BaseException):
            raise self.create_result
        return self.create_result


def test_ensure_glue_database_creates_when_missing():
    spec = GlueDatabaseSpec(
        name="db_test",
        location_uri="s3://bucket/warehouse/db_test.db",
        description=None,
    )
    glue = _FakeGlueClient(
        get_result=_FakeClientError("EntityNotFoundException"),
        create_result={},
    )

    created = ensure_glue_database(spec, region="eu-central-1", client=glue)
    assert created is True
    assert glue.calls == [
        ("get_database", {"Name": spec.name}),
        (
            "create_database",
            {
                "DatabaseInput": {
                    "Name": spec.name,
                    "LocationUri": spec.location_uri,
                }
            },
        ),
    ]


def test_ensure_glue_database_noop_when_exists():
    glue = _FakeGlueClient(get_result={"Database": {"Name": "db_test"}})

    spec = GlueDatabaseSpec(
        name="db_test",
        location_uri="s3://bucket/warehouse/db_test.db",
        description=None,
    )

    created = ensure_glue_database(spec, region="eu-central-1", client=glue)
    assert created is False
    assert glue.calls == [("get_database", {"Name": spec.name})]


def test_ensure_glue_database_handles_already_exists_race():
    spec = GlueDatabaseSpec(name="db_test")
    glue = _FakeGlueClient(
        get_result=_FakeClientError("EntityNotFoundException"),
        create_result=_FakeClientError("AlreadyExistsException"),
    )

    created = ensure_glue_database(spec, client=glue)
    assert created is False

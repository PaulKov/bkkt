import json


def test_split_patch_set_and_delete_supports_json_null() -> None:
    from connectctl.cli import _split_patch_set_and_delete

    raw = {
        "errors.deadletterqueue.topic.name": None,
        "tasks.max": 4,
        "transforms": {
            "unwrap": {"type": "io.debezium.transforms.ExtractNewRecordState"}
        },
        "topics": ["a", "b"],
    }

    to_set, to_del = _split_patch_set_and_delete(raw)

    assert "errors.deadletterqueue.topic.name" in set(to_del)
    assert to_set["tasks.max"] == "4"
    assert to_set["transforms"] == json.dumps(raw["transforms"], ensure_ascii=False)
    assert to_set["topics"] == json.dumps(raw["topics"], ensure_ascii=False)


def test_split_patch_set_and_delete_supports_delete_tokens_for_kv_sources() -> None:
    from connectctl.cli import _split_patch_set_and_delete

    raw = {
        "errors.deadletterqueue.topic.name": "__delete__",
        "errors.deadletterqueue.context.headers.enable": "__REMOVE__",
        "tasks.max": "2",
    }

    to_set, to_del = _split_patch_set_and_delete(raw)

    assert set(to_del) == {
        "errors.deadletterqueue.topic.name",
        "errors.deadletterqueue.context.headers.enable",
    }
    assert to_set == {"tasks.max": "2"}

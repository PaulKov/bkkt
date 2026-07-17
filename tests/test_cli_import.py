def test_cli_import_and_parser_builds() -> None:
    # This test is intentionally simple: it makes sure the CLI module is
    # importable (no syntax errors) and the argument parser can be built.
    from connectctl import cli

    parser = cli.build_parser()
    assert parser is not None

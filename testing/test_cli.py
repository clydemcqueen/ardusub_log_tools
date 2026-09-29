import pytest

from ardusub_log_tools import __version__
from ardusub_log_tools.cli.main import create_parser, main


def test_cli_version(capsys):
    parser = create_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_help(capsys):
    parser = create_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "explode" in captured.out
    assert "merge" in captured.out
    assert "timeline" in captured.out
    assert "types" in captured.out


def test_cli_explode_requires_types_or_all():
    parser = create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["explode", "dummy.BIN"])

    args = parser.parse_args(["explode", "--types", "GPS,ATT", "dummy.BIN"])
    assert args.types == "GPS,ATT"
    assert args.paths == ["dummy.BIN"]

    args_all = parser.parse_args(["explode", "--all", "dummy.BIN"])
    assert args_all.all is True


def test_cli_types_run():
    ret = main(["types", "testing/small.tlog"])
    assert ret == 0

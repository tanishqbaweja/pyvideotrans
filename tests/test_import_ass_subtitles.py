from unittest.mock import MagicMock

import pytest

from videotrans.configure.config import app_cfg
from videotrans.mainwin import _actions_base_file
from videotrans.mainwin._actions_base_file import WinActionBaseFileMixin
from videotrans.util._srt_parse import get_subtitle_from_srt

ASS = r"""[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,Tom,0,0,0,,Hello there.
Dialogue: 0,0:00:04.00,0:00:06.20,Default,Ann,0,0,0,,{\i1}How{\i0} are you?
Dialogue: 0,0:00:07.00,0:00:09.00,Default,Tom,0,0,0,,Fine, thanks.
"""


@pytest.fixture(autouse=True)
def no_imported_subtitles(monkeypatch):
    # app_cfg is shared, so each test starts without imported subtitles
    monkeypatch.setattr(app_cfg, "onlyone_importsrtfile", None)
    monkeypatch.setattr(app_cfg, "onlyone_importsrtfile_target", None)


def _import(monkeypatch, tmp_path, srt_type, path):
    # the file chosen in the dialog of the main window's import button
    qt = MagicMock()
    qt.QFileDialog.getOpenFileName.return_value = (
        path.as_posix(),
        "Files(*.srt *.ass)",
    )
    monkeypatch.setattr(_actions_base_file, "QtWidgets", qt)
    temp_root = tmp_path / "tmp"
    temp_root.mkdir()
    monkeypatch.setattr(_actions_base_file, "TEMP_ROOT", temp_root.as_posix())
    # stands in for the window, whose subtitle area shows the imported files
    WinActionBaseFileMixin.import_srtfile(MagicMock(), srt_type)
    if srt_type == "spoken":
        return app_cfg.onlyone_importsrtfile
    return app_cfg.onlyone_importsrtfile_target


def _subtitles(srtfile):
    return [
        (it["start_time"], it["end_time"], it["text"])
        for it in get_subtitle_from_srt(srtfile)
    ]


@pytest.mark.parametrize("name", ["talk.ass", "TALK.ASS"])
def test_target_ass_is_converted_to_srt(monkeypatch, tmp_path, name):
    ass = tmp_path / name
    ass.write_text(ASS, encoding="utf-8")

    imported = _import(monkeypatch, tmp_path, "target", ass)

    # without [Name] tags: speakers are only read from the spoken subtitles,
    # and the target ones are dubbed as they are
    assert _subtitles(imported) == [
        (1000, 3500, "Hello there."),
        (4000, 6200, "How are you?"),
        (7000, 9000, "Fine, thanks."),
    ]


@pytest.mark.parametrize("name", ["talk.ass", "TALK.ASS"])
def test_spoken_ass_keeps_the_speaker_tags(monkeypatch, tmp_path, name):
    ass = tmp_path / name
    ass.write_text(ASS, encoding="utf-8")

    imported = _import(monkeypatch, tmp_path, "spoken", ass)

    # prepare() reads the speakers from these tags and removes them
    assert _subtitles(imported) == [
        (1000, 3500, "[Tom]Hello there."),
        (4000, 6200, "[Ann]How are you?"),
        (7000, 9000, "[Tom]Fine, thanks."),
    ]


@pytest.mark.parametrize("srt_type", ["spoken", "target"])
def test_srt_is_imported_as_it_is(monkeypatch, tmp_path, srt_type):
    srt = tmp_path / "talk.srt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\n[Tom]Hello there.\n", encoding="utf-8"
    )

    assert _import(monkeypatch, tmp_path, srt_type, srt) == srt.as_posix()

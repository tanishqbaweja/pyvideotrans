import codecs

import pytest

from videotrans.configure.config import app_cfg
from videotrans.task.dubbing import DubbingSrt
from videotrans.task.taskcfg import TaskCfgTTS
from videotrans.util._ffmpeg_misc import format_video
from videotrans.util._srt_parse import ass_to_srt, get_subtitle_from_srt

ASS = r"""[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,小明,0,0,0,,大家好。
Dialogue: 0,0:00:04.00,0:00:06.20,Default,小红,0,0,0,,{\i1}你好{\i0}，最近怎么样？
Dialogue: 0,0:00:07.00,0:00:09.00,Default,小明,0,0,0,,很好，谢谢。
"""

# the same file saved as UTF-8 with and without a BOM, as GBK (ANSI on
# Simplified Chinese Windows) and as UTF-16 or UTF-32 with a BOM
FILES = {
    "utf-8": ASS.encode("utf-8"),
    "utf-8-sig": ASS.encode("utf-8-sig"),
    "gbk": ASS.encode("gbk"),
    "utf-16-le": codecs.BOM_UTF16_LE + ASS.encode("utf-16-le"),
    "utf-16-be": codecs.BOM_UTF16_BE + ASS.encode("utf-16-be"),
    "utf-32-le": codecs.BOM_UTF32_LE + ASS.encode("utf-32-le"),
    "utf-32-be": codecs.BOM_UTF32_BE + ASS.encode("utf-32-be"),
}


def _convert(tmp_path, encoding, get_speaker):
    ass = tmp_path / "talk.ass"
    ass.write_bytes(FILES[encoding])
    srt = tmp_path / "talk.srt"
    ass_to_srt(ass.as_posix(), srt.as_posix(), get_speaker)
    return [
        (it["start_time"], it["end_time"], it["text"])
        for it in get_subtitle_from_srt(srt.as_posix())
    ]


@pytest.mark.parametrize("encoding", FILES)
def test_ass_file_is_converted(tmp_path, encoding):
    # with [Name] tags, as the main window converts spoken subtitles and the
    # Multi-Speaker window converts its file
    assert _convert(tmp_path, encoding, True) == [
        (1000, 3500, "[小明]大家好。"),
        (4000, 6200, "[小红]你好，最近怎么样？"),
        (7000, 9000, "[小明]很好，谢谢。"),
    ]
    # without them, as the main window converts target subtitles and the
    # Text-to-Speech window converts its files
    assert _convert(tmp_path, encoding, False) == [
        (1000, 3500, "大家好。"),
        (4000, 6200, "你好，最近怎么样？"),
        (7000, 9000, "很好，谢谢。"),
    ]


@pytest.mark.parametrize("encoding", FILES)
def test_multi_speaker_dubbing_starts(monkeypatch, tmp_path, encoding):
    # print progress messages instead of sending them to the GUI
    monkeypatch.setattr(app_cfg, "exec_mode", "cli")
    # _tts() would send the lines to the TTS channel
    dubbed = []
    monkeypatch.setattr(DubbingSrt, "_tts", lambda self: dubbed.append(self.subs))
    ass = tmp_path / "talk.ass"
    ass.write_bytes(FILES[encoding])
    srt = tmp_path / "talk.srt"
    ass_to_srt(ass.as_posix(), srt.as_posix(), True)
    subs = get_subtitle_from_srt(srt.as_posix())
    # as Start in the Multi-Speaker window creates the task: from the .ass
    # file it imported, with the lines it read from the converted file
    cfg = {
        "target_dir": (tmp_path / "out").as_posix(),
        "cache_folder": (tmp_path / "cache").as_posix(),
    }
    trk = DubbingSrt(
        cfg=TaskCfgTTS(**cfg | format_video(ass.as_posix(), None)),
        subs=subs,
        is_multi_role=True,
    )

    trk.dubbing()

    assert dubbed == [subs]

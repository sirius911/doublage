from doublage.segments import Segment, Transcript
from doublage.subtitles import to_srt, to_vtt

T = Transcript(4000.0, [Segment(0, 1.5, 3.25, "Zim bra", "Ouvrez Zimbra."),
                        Segment(1, 3661.0, 3662.004, "Fin", "Fin."),
                        Segment(2, 3663.0, 3664.0, "", "")])  # phrase vidée : ignorée


def test_srt():
    assert to_srt(T) == ("1\n00:00:01,500 --> 00:00:03,250\nOuvrez Zimbra.\n\n"
                         "2\n01:01:01,000 --> 01:01:02,004\nFin.\n")


def test_vtt():
    assert to_vtt(T) == ("WEBVTT\n\n00:00:01.500 --> 00:00:03.250\nOuvrez Zimbra.\n\n"
                         "01:01:01.000 --> 01:01:02.004\nFin.\n")

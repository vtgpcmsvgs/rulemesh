"""防止浏览器错误页或局部资源失败被文字长度误判为通过。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_browser_evidence import assess


class BrowserEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.page = {"host": "m.youtube.com", "ready": "complete", "textLength": 500,
                     "errorPage": False, "video": [{"readyState": 4, "currentTime": 12, "paused": False, "error": None}]}

    def check(self, page=None, events=None, **kwargs):
        return assess(self.page if page is None else page, events or [], {"m.youtube.com"}, foreground=kwargs.get("foreground", True), require_media=True)

    def test_real_error_page_with_text_is_failed(self):
        page = dict(self.page, host="chromewebdata", errorPage=True, textLength=81)
        self.assertEqual(self.check(page)["state"], "failed")

    def test_document_failure_cannot_pass_with_old_dom(self):
        result = self.check(events=[{"type": "Document", "failed": "net::ERR_CONNECTION_CLOSED", "canceled": False}])
        self.assertTrue(result["document_failed"])
        self.assertFalse(result["passed"])

    def test_resource_error_is_partial_even_when_video_plays(self):
        result = self.check(events=[{"type": "Script", "failed": "net::ERR_QUIC_PROTOCOL_ERROR", "canceled": False}])
        self.assertEqual(result["state"], "partial")

    def test_background_and_unplayed_video_are_unconfirmed(self):
        self.assertEqual(self.check(foreground=False)["state"], "incomplete")
        self.assertEqual(self.check(dict(self.page, video=[]))["state"], "media_unconfirmed")

    def test_playing_media_and_canceled_navigation(self):
        self.assertTrue(self.check(events=[{"type": "Document", "failed": "net::ERR_ABORTED", "canceled": True}])["passed"])


if __name__ == "__main__":
    unittest.main()

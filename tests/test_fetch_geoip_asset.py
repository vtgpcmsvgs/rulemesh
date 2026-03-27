import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import fetch_geoip_asset  # noqa: E402


class ParseSnapshotMappingTests(unittest.TestCase):
    def test_parses_non_comment_key_values(self) -> None:
        mapping = fetch_geoip_asset.parse_snapshot_mapping(
            "# 注释\n"
            "provider: MetaCubeX/meta-rules-dat\n"
            "github_release: https://example.com/country.mmdb\n"
            "\n"
            "rulemesh_release_tag: geoip-country-mmdb\n"
        )

        self.assertEqual(
            mapping,
            {
                "provider": "MetaCubeX/meta-rules-dat",
                "github_release": "https://example.com/country.mmdb",
                "rulemesh_release_tag": "geoip-country-mmdb",
            },
        )

    def test_resolve_download_url_requires_existing_field(self) -> None:
        with self.assertRaises(ValueError):
            fetch_geoip_asset.resolve_download_url({}, "github_release")


class WriteOutputTests(unittest.TestCase):
    def test_write_output_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "nested" / "country.mmdb"

            fetch_geoip_asset.write_output(output_path, b"demo-mmdb")

            self.assertEqual(output_path.read_bytes(), b"demo-mmdb")


class DownloadBinaryTests(unittest.TestCase):
    def test_download_binary_uses_rulemesh_user_agent(self) -> None:
        response = mock.MagicMock()
        response.read.return_value = b"country-mmdb"
        urlopen_result = mock.MagicMock()
        urlopen_result.__enter__.return_value = response
        urlopen_result.__exit__.return_value = None

        with mock.patch(
            "fetch_geoip_asset.urllib.request.urlopen",
            return_value=urlopen_result,
        ) as mocked:
            payload = fetch_geoip_asset.download_binary("https://example.com/country.mmdb")

        self.assertEqual(payload, b"country-mmdb")
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.com/country.mmdb")
        self.assertEqual(request.headers["User-agent"], "rulemesh-upstream-sync/1.0")


class MainTests(unittest.TestCase):
    def test_main_reads_snapshot_and_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot_path = Path(tmp_dir) / "snapshot.yaml"
            snapshot_path.write_text(
                "github_release: https://example.com/country.mmdb\n",
                encoding="utf-8",
            )
            output_path = Path(tmp_dir) / "nested" / "country.mmdb"
            args = mock.Mock(
                output=str(output_path),
                snapshot=str(snapshot_path),
                url_key="github_release",
            )

            with mock.patch("fetch_geoip_asset.parse_args", return_value=args):
                with mock.patch(
                    "fetch_geoip_asset.download_binary",
                    return_value=b"country-mmdb",
                ) as mocked_download:
                    exit_code = fetch_geoip_asset.main()

            self.assertEqual(exit_code, 0)
            self.assertEqual(output_path.read_bytes(), b"country-mmdb")
            mocked_download.assert_called_once_with(
                "https://example.com/country.mmdb"
            )


if __name__ == "__main__":
    unittest.main()

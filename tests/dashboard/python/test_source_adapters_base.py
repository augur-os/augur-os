"""Tests for source_adapters/base.py — FileInfo, ScanManifest, and SourceAdapter."""

import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from source_adapters.base import FileInfo, ScanManifest, SourceAdapter


class TestFileInfo:
    """Tests for the FileInfo dataclass."""

    def test_extension_property(self):
        fi = FileInfo(name="report.PDF", path="report.PDF", size=1024, modified=datetime.now(), file_type="PDF")
        assert fi.extension == "pdf"

    def test_extension_lowercase(self):
        fi = FileInfo(name="data.CSV", path="data.CSV", size=500, modified=datetime.now(), file_type="csv")
        assert fi.extension == "csv"

    def test_directory_flag(self):
        fi = FileInfo(name="subdir", path="subdir", size=0, modified=datetime.now(), file_type="", is_directory=True)
        assert fi.is_directory is True
        assert fi.extension == ""

    def test_children_default_empty(self):
        fi = FileInfo(name="file.txt", path="file.txt", size=10, modified=datetime.now(), file_type="txt")
        assert fi.children == []


class TestScanManifest:
    """Tests for the ScanManifest dataclass."""

    def _make_file(self, name: str, is_dir: bool = False) -> FileInfo:
        ext = name.rsplit(".", 1)[-1] if "." in name and not is_dir else ""
        return FileInfo(name=name, path=name, size=100, modified=datetime.now(), file_type=ext, is_directory=is_dir)

    def test_file_count_excludes_directories(self):
        manifest = ScanManifest(
            source_type="folder",
            source_path="/test",
            files=[
                self._make_file("data.csv"),
                self._make_file("report.pdf"),
                self._make_file("subdir", is_dir=True),
            ],
        )
        assert manifest.file_count == 2

    def test_directory_count(self):
        manifest = ScanManifest(
            source_type="folder",
            source_path="/test",
            files=[
                self._make_file("a.txt"),
                self._make_file("dir1", is_dir=True),
                self._make_file("dir2", is_dir=True),
            ],
        )
        assert manifest.directory_count == 2

    def test_empty_manifest(self):
        manifest = ScanManifest(source_type="folder", source_path="/empty")
        assert manifest.file_count == 0
        assert manifest.directory_count == 0
        assert manifest.total_size == 0

    def test_file_structures_default_empty(self):
        manifest = ScanManifest(source_type="folder", source_path="/test")
        assert manifest.file_structures == {}


class TestSourceAdapter:
    """Tests for the SourceAdapter abstract base class."""

    def test_cannot_instantiate_directly(self):
        try:
            SourceAdapter()
            assert False, "Should not be able to instantiate abstract class"
        except TypeError:
            pass

    def test_subclass_must_implement_methods(self):
        class IncompleteAdapter(SourceAdapter):
            pass

        try:
            IncompleteAdapter()
            assert False, "Should not instantiate without implementing abstract methods"
        except TypeError:
            pass

    def test_complete_subclass(self):
        class TestAdapter(SourceAdapter):
            source_type = "test"

            def scan(self) -> ScanManifest:
                return ScanManifest(source_type="test", source_path="/test")

            def read_file(self, path: str) -> bytes:
                return b"content"

            def list_files(self) -> list[FileInfo]:
                return []

        adapter = TestAdapter()
        assert adapter.source_type == "test"
        manifest = adapter.scan()
        assert manifest.source_type == "test"
        assert adapter.read_file("any") == b"content"
        assert adapter.list_files() == []

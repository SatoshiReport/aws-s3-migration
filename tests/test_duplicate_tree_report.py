import pytest

from duplicate_tree_report import (
    DirectoryIndex,
    find_exact_duplicates,
    find_near_duplicates,
)


def _build_sample_index():
    index = DirectoryIndex()
    # Exact twin directories
    index.add_file("bucket", "dirA/file1.txt", 100, "aaa")
    index.add_file("bucket", "dirA/sub/file2.txt", 200, "bbb")
    index.add_file("bucket", "dirB/file1.txt", 100, "aaa")
    index.add_file("bucket", "dirB/sub/file2.txt", 200, "bbb")
    # Near duplicate pair with minor differences (1% delta)
    for i in range(100):
        checksum = f"h{i}"
        index.add_file("bucket", f"dirD/file_{i}.dat", 10, checksum)
        altered_checksum = checksum
        if i == 0:
            altered_checksum = "DIFF"
        index.add_file("bucket", f"dirE/file_{i}.dat", 10, altered_checksum)
    index.add_file("bucket", "dirE/file_extra.dat", 5, "extra")
    index.finalize()
    return index


def test_find_exact_duplicates_groups_identical_directories():
    index = _build_sample_index()
    clusters = find_exact_duplicates(index)

    match = next(
        (
            cluster
            for cluster in clusters
            if {("bucket", "dirA"), ("bucket", "dirB")}.issubset(
                {node.path for node in cluster.nodes}
            )
        ),
        None,
    )
    assert match is not None
    assert match.nodes[0].total_files == 2
    assert match.nodes[0].total_size == 300


def test_find_near_duplicates_reports_deltas():
    index = _build_sample_index()
    reports = find_near_duplicates(index, tolerance=0.99)

    assert reports, "Expected at least one near-duplicate report"
    target_path = ("bucket", "dirE")
    pair = next(
        (r for r in reports if target_path in (r.primary.path, r.secondary.path)),
        None,
    )
    assert pair is not None
    assert pair.differences["mismatched"] == ["file_0.dat"]
    assert "file_extra.dat" in pair.differences["extra"]
    assert pair.size_delta == 5
    assert pair.file_delta == 1

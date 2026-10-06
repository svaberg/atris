import logging
import subprocess

import pytest

from atris_tools.run_chunks import (
    chunk_label,
    incomplete_entry_numbers,
    main,
    run_chunks,
    select_entries,
    worker_label,
)


def prepare_run(tmp_path, plan=None):
    (tmp_path / "chunks").mkdir()
    if plan is None:
        plan = [
            ("protons", "111111", "222222"),
            ("alphas", "333333", "444444"),
        ]
    (tmp_path / "chunks.txt").write_text(
        "".join("%s %s %s\n" % entry for entry in plan)
    )
    (tmp_path / "phantoms.txt").write_text(
        "0 first 1.0 2.0\n"
        "1 second 3.0 4.0\n"
    )


def test_run_chunks_executes_plan_and_marks_success(tmp_path, monkeypatch):
    prepare_run(tmp_path)
    calls = []

    def fake_run(command, cwd, stdout, stderr, check):
        calls.append((command, cwd, stdout.name, stderr, check))

    monkeypatch.setattr("atris_tools.run_chunks.subprocess.run", fake_run)

    assert run_chunks(tmp_path) == 2
    assert calls == [
        (
            ["AtRIS", "chunks/protons_111111_222222"],
            tmp_path.resolve(),
            str(tmp_path / "chunks/protons_111111_222222.log"),
            subprocess.STDOUT,
            True,
        ),
        (
            ["AtRIS", "chunks/alphas_333333_444444"],
            tmp_path.resolve(),
            str(tmp_path / "chunks/alphas_333333_444444.log"),
            subprocess.STDOUT,
            True,
        ),
    ]
    assert (tmp_path / "chunks/protons_111111_222222.COMPLETE").is_file()
    assert (tmp_path / "chunks/alphas_333333_444444.COMPLETE").is_file()


def test_run_chunks_skips_complete_entries(tmp_path, monkeypatch, caplog):
    prepare_run(tmp_path)
    (tmp_path / "chunks/protons_111111_222222.COMPLETE").touch()
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    with caplog.at_level(logging.DEBUG, logger="atris_tools.run_chunks"):
        assert run_chunks(tmp_path) == 1

    assert calls == [["AtRIS", "chunks/alphas_333333_444444"]]
    assert "Chunk 1/2 complete: chunks/protons_111111_222222" in caplog.text
    assert "Chunk 2/2 starting: chunks/alphas_333333_444444" in caplog.text
    assert "Chunk 2/2 complete" in caplog.text
    messages = [record.getMessage() for record in caplog.records]
    assert messages.index(
        "Chunk 1/2 complete: chunks/protons_111111_222222"
    ) < messages.index("1/2 chunk already processed")
    assert messages.index(
        "1/2 chunk already processed"
    ) < messages.index("Processing remaining 1/2 chunk...")
    assert messages.index(
        "Processing remaining 1/2 chunk..."
    ) < messages.index("Chunk 2/2 starting: chunks/alphas_333333_444444")


def test_run_chunks_can_select_one_plan_entry(tmp_path, monkeypatch):
    prepare_run(tmp_path)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(tmp_path, entry=2) == 1
    assert calls == [["AtRIS", "chunks/alphas_333333_444444"]]
    assert not (tmp_path / "chunks/protons_111111_222222.COMPLETE").exists()


def test_run_chunks_does_not_mark_failed_entry(tmp_path, monkeypatch):
    prepare_run(tmp_path)

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("atris_tools.run_chunks.subprocess.run", fail)

    with pytest.raises(subprocess.CalledProcessError):
        run_chunks(tmp_path, entry=1)

    assert not (tmp_path / "chunks/protons_111111_222222.COMPLETE").exists()


def test_select_entries_assigns_disjoint_round_robin_worker_shards():
    entries = [
        ("protons", "%06i" % number, "%06i" % (number + 100))
        for number in range(1, 8)
    ]

    shards = [
        select_entries(entries, worker_index=index, worker_count=3)
        for index in range(3)
    ]

    assert [[line for line, _ in shard] for shard in shards] == [
        [1, 4, 7],
        [2, 5],
        [3, 6],
    ]
    assert sorted(line for shard in shards for line, _ in shard) == list(range(1, 8))


@pytest.mark.parametrize(
    ("worker_index", "worker_count", "message"),
    [
        (0, 0, "at least 1"),
        (-1, 2, "between 0 and 1"),
        (2, 2, "between 0 and 1"),
    ],
)
def test_select_entries_rejects_invalid_worker_coordinates(
    worker_index, worker_count, message
):
    with pytest.raises(ValueError, match=message):
        select_entries([], worker_index=worker_index, worker_count=worker_count)


def test_run_chunks_executes_only_the_workers_shard(tmp_path, monkeypatch):
    plan = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
        ("alphas", "555555", "666666"),
        ("alphas", "777777", "888888"),
    ]
    prepare_run(tmp_path, plan)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(tmp_path, worker_index=1, worker_count=2) == 2
    assert calls == [
        ["AtRIS", "chunks/protons_333333_444444"],
        ["AtRIS", "chunks/alphas_777777_888888"],
    ]


def test_run_chunks_logs_timed_progress_for_each_chunk(tmp_path, monkeypatch, caplog):
    prepare_run(tmp_path)
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda *args, **kwargs: None,
    )
    times = iter((0, 90, 90, 210))

    with caplog.at_level(logging.DEBUG, logger="atris_tools.run_chunks"):
        assert run_chunks(tmp_path, timer=lambda: next(times)) == 2

    info_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "atris_tools.run_chunks" and record.levelno == logging.INFO
    ]
    assert info_messages == [
        "Starting AtRIS chunked run",
        "Run directory: %s" % tmp_path.resolve(),
        "Chunk plan: %s" % (tmp_path.resolve() / "chunks.txt"),
        "Phantom 1/2: first",
        "Phantom 2/2: second",
        "Processing 2 chunks...",
        "0/2 chunks already processed",
        "Processing remaining 2/2 chunks...",
        "Chunk 1/2 complete in 1.5 min. ETA: 1.5 min",
        "Chunk 2/2 complete in 2.0 min. ETA: 0.0 min",
        "AtRIS chunk run finished",
        "Completed 2 new chunks in 3.5 min",
        "Finished chunks: 2/2",
        "Remaining: 0 chunks",
    ]
    debug_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "atris_tools.run_chunks" and record.levelno == logging.DEBUG
    ]
    assert debug_messages == [
        "Phantom 1/2 counting file: %s" % (tmp_path / "counting_phantom0.txt"),
        "Phantom 1/2 response file: %s" % (tmp_path / "radiation_phantom0.txt"),
        "Phantom 2/2 counting file: %s" % (tmp_path / "counting_phantom1.txt"),
        "Phantom 2/2 response file: %s" % (tmp_path / "radiation_phantom1.txt"),
        "Chunk 1/2 starting: chunks/protons_111111_222222",
        "Chunk 2/2 starting: chunks/alphas_333333_444444",
    ]


def test_run_chunks_logs_resolved_phantom_paths(tmp_path, monkeypatch, caplog):
    prepare_run(tmp_path)
    archive = tmp_path / "archive"
    archive.mkdir()
    response = archive / "first_response.txt"
    counting = archive / "first_counting.txt"
    response.touch()
    counting.touch()
    (tmp_path / "radiation_phantom0.txt").symlink_to(response)
    (tmp_path / "counting_phantom0.txt").symlink_to(counting)
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda *args, **kwargs: None,
    )

    with caplog.at_level(logging.DEBUG, logger="atris_tools.run_chunks"):
        run_chunks(tmp_path, entry=1)

    assert "Phantom 1/2: first" in caplog.messages
    assert "Phantom 1/2 counting file: %s" % counting.resolve() in caplog.messages
    assert "Phantom 1/2 response file: %s" % response.resolve() in caplog.messages


def test_worker_label_is_conditional_and_space_aligned():
    assert worker_label(0, 1) == ""
    assert worker_label(0, 200) == "Worker   1/200"
    assert worker_label(199, 200) == "Worker 200/200"


def test_chunk_label_is_conditional_and_space_aligned():
    assert chunk_label("", 1, 200) == "Chunk   1/200"
    assert (
        chunk_label("Worker   1/200", 1, 200)
        == "Worker   1/200 chunk   1/200"
    )


def test_run_chunks_stops_before_the_job_deadline(tmp_path, monkeypatch, caplog):
    prepare_run(tmp_path)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    with caplog.at_level(logging.INFO, logger="atris_tools.run_chunks"):
        assert run_chunks(
            tmp_path,
            deadline=1000,
            stop_before_end=100,
            clock=lambda: 900,
        ) == 0

    assert calls == []
    assert "wall-time safety window has begun" in caplog.text
    assert "AtRIS chunk run stopped" in caplog.text
    assert "Completed 0 new chunks in 0.0 min" in caplog.text
    assert "Finished chunks: 0/2" in caplog.text
    assert "Remaining: 2 chunks" in caplog.text


def test_main_defaults_to_one_scheduler_neutral_worker(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "sys.argv",
        ["atris-run", str(tmp_path)],
    )
    monkeypatch.setattr(
        "atris_tools.run_chunks.run_chunks",
        lambda *args, **kwargs: calls.append((args, kwargs)) or 0,
    )

    assert main() == 0
    assert calls == [
        (
            (tmp_path,),
            {
                "entry": None,
                "worker_index": 0,
                "worker_count": 1,
                "deadline": None,
                "stop_before_end": 0,
            },
        )
    ]


def test_incomplete_entry_numbers_uses_completion_markers(tmp_path):
    prepare_run(tmp_path)
    (tmp_path / "chunks/protons_111111_222222.COMPLETE").touch()

    assert incomplete_entry_numbers(tmp_path) == [2]


def test_help_separates_chunk_and_logging_options(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["atris-run", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Chunk plan and worker options:" in help_text
    assert "Logging options:" in help_text
    assert help_text.index("--check-complete") < help_text.index("--quiet")
    assert "Examples:" in help_text
    normalized_help = " ".join(help_text.split())
    assert "atris-run runs/earth" in normalized_help
    assert "G4FORCENUMBEROFTHREADS=7" in normalized_help
    assert "--worker-index 2" in normalized_help
    assert "--worker-count 11" in normalized_help
    assert '"$JOB_END_TIME"' in normalized_help
    assert "--stop-before-end 1800" in normalized_help
    assert "--entry 17" in normalized_help
    assert "--check-complete" in normalized_help

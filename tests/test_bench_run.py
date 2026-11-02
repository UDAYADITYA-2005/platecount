import sys
from types import SimpleNamespace

import pytest

import bench.run as bench_run
from platecount.meta.client import MetaClient, RunCost


def run_main(monkeypatch, client: MetaClient, run) -> None:
    monkeypatch.setattr(sys, "argv", ["bench.run"])
    monkeypatch.setattr(bench_run, "MetaClient", SimpleNamespace(from_env=lambda: client))
    monkeypatch.setattr(bench_run, "run", run)
    bench_run.main()


def test_budget_stop_still_prints_the_cost(monkeypatch, capsys):
    client = MetaClient(api_key="k", cost=RunCost(usd=6.0))
    stop = lambda _, c: bench_run.compare_agent(["1"], {}, c)
    with pytest.raises(SystemExit, match="run limit"):
        run_main(monkeypatch, client, stop)
    assert "cost $6.0000" in capsys.readouterr().out


def test_crash_still_prints_the_cost(monkeypatch, capsys):
    def crash(_, c):
        c.cost.usd = 1.5
        raise RuntimeError("sam down")

    with pytest.raises(RuntimeError):
        run_main(monkeypatch, MetaClient(api_key="k"), crash)
    assert "cost $1.5000" in capsys.readouterr().out

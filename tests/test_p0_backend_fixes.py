"""P0 后端修复对应的单元测试。

覆盖：
- 学习数据库默认路径不再落在 /tmp（容器外重启不会丢失样本）；
- LEISU_MOBILE_API_SECRET 可由环境变量覆盖；
- server 守护线程状态读写经过同一把锁；
- sources.close_client() 能优雅关闭模块级 httpx 客户端。
"""
from __future__ import annotations

import asyncio
import importlib
import os
import threading

import httpx


class TestLearningDBDefaultPath:
    def test_default_path_is_under_user_home_not_tmp(self, monkeypatch):
        # 业务期望：本地直接运行 server 时数据不应落在 /tmp，
        # 以免宿主重启清空 /tmp 后丢失全部样本与校准。
        monkeypatch.delenv("FOOTBALL_DATA_LEARNING_DB", raising=False)
        from football_data_mcp import learning_store
        importlib.reload(learning_store)
        path = learning_store.learning_db_path()
        assert not path.startswith("/tmp/"), f"default path should not be in /tmp, got {path}"
        assert path.endswith(".sqlite3")
        # 默认目录应是用户主目录下的隐藏目录，避免污染当前工作目录。
        home = os.path.expanduser("~")
        assert path.startswith(home), f"default path should live under {home}, got {path}"

    def test_explicit_env_var_overrides_default(self, monkeypatch, tmp_path):
        target = tmp_path / "explicit.sqlite3"
        monkeypatch.setenv("FOOTBALL_DATA_LEARNING_DB", str(target))
        from football_data_mcp import learning_store
        importlib.reload(learning_store)
        assert learning_store.learning_db_path() == str(target)


class TestLeisuMobileApiSecret:
    def test_default_secret_is_a_non_empty_string(self, monkeypatch):
        monkeypatch.delenv("LEISU_MOBILE_API_SECRET", raising=False)
        from football_data_mcp import sources
        importlib.reload(sources)
        assert isinstance(sources.LEISU_MOBILE_API_SECRET, str)
        assert sources.LEISU_MOBILE_API_SECRET, "default Leisu secret must not be empty"

    def test_env_var_overrides_secret(self, monkeypatch):
        monkeypatch.setenv("LEISU_MOBILE_API_SECRET", "test-override-secret")
        from football_data_mcp import sources
        importlib.reload(sources)
        assert sources.LEISU_MOBILE_API_SECRET == "test-override-secret"


class TestServerLearningCycleStatusLock:
    def test_record_and_read_status_returns_paired_snapshot(self):
        from football_data_mcp import server
        importlib.reload(server)
        # 初始状态：没有任何 cycle 完成过。
        ts, err = server.learning_cycle_status()
        assert ts is None
        assert err is None

        server._record_learning_cycle_status(finished_at=1234567890.0, error=None)
        ts, err = server.learning_cycle_status()
        assert ts == 1234567890.0
        assert err is None

        server._record_learning_cycle_status(finished_at=1234567990.0, error="boom")
        ts, err = server.learning_cycle_status()
        assert ts == 1234567990.0
        assert err == "boom"

    def test_concurrent_readers_never_see_torn_writes(self):
        # 100 个写者交替写入 (t, err)，100 个读者必须始终读到匹配的对。
        from football_data_mcp import server
        importlib.reload(server)
        stop = threading.Event()
        anomalies: list[tuple[float, str | None]] = []

        def writer() -> None:
            for i in range(2000):
                if i % 2 == 0:
                    server._record_learning_cycle_status(
                        finished_at=float(i), error=None
                    )
                else:
                    server._record_learning_cycle_status(
                        finished_at=float(i), error=f"err-{i}"
                    )
            stop.set()

        def reader() -> None:
            while not stop.is_set():
                ts, err = server.learning_cycle_status()
                if ts is None:
                    continue
                expected_err = None if int(ts) % 2 == 0 else f"err-{int(ts)}"
                if err != expected_err:
                    anomalies.append((ts, err))

        w = threading.Thread(target=writer)
        readers = [threading.Thread(target=reader) for _ in range(4)]
        for r in readers:
            r.start()
        w.start()
        w.join()
        for r in readers:
            r.join(timeout=2.0)
        assert anomalies == [], f"observed {len(anomalies)} torn reads, first: {anomalies[:3]}"


class TestSourcesCloseClient:
    def test_close_client_releases_module_level_client(self):
        from football_data_mcp import sources
        importlib.reload(sources)

        async def scenario() -> tuple[httpx.AsyncClient, bool]:
            client = await sources.get_client()
            assert isinstance(client, httpx.AsyncClient)
            assert sources._CLIENT is client
            await sources.close_client()
            return client, sources._CLIENT is None

        client, cleared = asyncio.run(scenario())
        assert cleared, "close_client must reset module-level _CLIENT"
        assert client.is_closed, "underlying httpx client must be closed"

    def test_close_client_is_safe_when_never_initialized(self):
        from football_data_mcp import sources
        importlib.reload(sources)
        assert sources._CLIENT is None
        # 不应抛异常
        asyncio.run(sources.close_client())
        assert sources._CLIENT is None

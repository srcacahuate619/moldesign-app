"""Desktop SSE progress delivery without Redis."""

from __future__ import annotations

import asyncio

import pytest

from utils.cache import LocalRuntimeStore


@pytest.mark.asyncio
async def test_subscription_replays_then_delivers_only_new_events():
    client = LocalRuntimeStore()
    task_id = "local-event-bus-contract"
    replay_event = {"type": "stage", "stage": "preparing"}
    live_event = {"type": "pipeline_done", "stage": "complete"}

    await client.push_stage_event(task_id, replay_event)
    replay, subscriber = await client.subscribe_stage_events(task_id)
    try:
        assert replay == [replay_event]

        await client.push_stage_event(task_id, live_event)
        assert await asyncio.wait_for(subscriber.get(), timeout=0.2) == live_event
        assert subscriber.empty()
    finally:
        await client.unsubscribe_stage_events(task_id, subscriber)


@pytest.mark.asyncio
async def test_sse_endpoint_streams_live_desktop_events(monkeypatch):
    from api.routers import evaluation
    import utils.cache as cache_module

    client = LocalRuntimeStore()
    monkeypatch.setattr(cache_module, "cache", client)

    class ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    task_id = "sse-live-event"
    await client.push_stage_event(task_id, {"type": "stage", "stage": "queued"})
    response = await evaluation.stream_pipeline_events(task_id, ConnectedRequest())
    stream = response.body_iterator

    first = await anext(stream)
    assert '"stage": "queued"' in first

    next_chunk = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    await client.push_stage_event(task_id, {"type": "pipeline_done", "stage": "complete"})
    second = await asyncio.wait_for(next_chunk, timeout=0.2)
    assert '"pipeline_done"' in second

    with pytest.raises(StopAsyncIteration):
        await anext(stream)

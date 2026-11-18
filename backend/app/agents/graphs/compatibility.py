"""P00 兼容性试验图，不代表 P02 的业务图已实现。"""

import argparse
import json
import os
from typing import TypedDict

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg.rows import dict_row


class ProbeState(TypedDict, total=False):
    request: str
    answer: str
    complete: bool


def human_interrupt(state: ProbeState):
    answer = interrupt({"missing": "product_model", "request": state["request"]})
    return {"answer": answer}


def finalize(state: ProbeState):
    return {"complete": True}


def build_graph(saver: PostgresSaver):
    builder = StateGraph(ProbeState)
    builder.add_node("human_interrupt", human_interrupt)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "human_interrupt")
    builder.add_edge("human_interrupt", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=saver)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["setup", "pause", "resume"])
    parser.add_argument("--thread-id", default="p00-unused")
    args = parser.parse_args()
    # 独占连接同时承载会话锁和 Saver，不做透明重连。
    with psycopg.connect(
        os.environ["AFTERSALES_TEST_DATABASE_URL"],
        autocommit=True, prepare_threshold=0, row_factory=dict_row,
    ) as conn:
        if conn.info.dbname != "aftersales_test":
            raise RuntimeError("兼容性试验只允许使用 aftersales_test 数据库")
        if args.action == "setup":
            conn.execute("CREATE SCHEMA IF NOT EXISTS checkpoints")
        conn.execute("SET search_path TO checkpoints, public")
        saver = PostgresSaver(conn)
        if args.action == "setup":
            saver.setup()
            print(json.dumps({"setup": True}))
            return
        conn.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (args.thread_id,))
        graph = build_graph(saver)
        config = {"configurable": {"thread_id": args.thread_id}}
        value = {"request": "设备型号未知"} if args.action == "pause" else Command(resume="DEMO-01")
        graph.invoke(value, config, durability="sync")
        state = graph.get_state(config)
        print(json.dumps({
            "pid": os.getpid(), "values": state.values, "next": list(state.next),
            "interrupted": any(task.interrupts for task in state.tasks),
            "checkpoint_id": state.config["configurable"]["checkpoint_id"],
        }))


if __name__ == "__main__":
    main()

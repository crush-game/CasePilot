from sqlalchemy.orm import Session

from app.knowledge.index import search
from app.knowledge.schemas import SearchQuery
from app.tools.contracts import ErrorCode, KnowledgeData, KnowledgeRecord
from app.tools.mock import MockAdapter, ToolIssue


class DatabaseKnowledgeAdapter(MockAdapter):
    """复用六工具的执行边界；知识调用实际发布的 BM25，其他工具仍是 Mock。"""

    adapter_name = "knowledge-bm25-v1"

    def __init__(self, context, runtime, engine, client=None):
        super().__init__(context, runtime, client)
        self.engine = engine

    def search_knowledge(self, args):
        with Session(self.engine) as db:
            result = search(db, SearchQuery(query=args.query, product_ref=args.product_ref,
                                           firmware_version=args.firmware_version, region=args.region,
                                           channel=args.channel, as_of=args.as_of))
        data = KnowledgeData(documents=[KnowledgeRecord(record_id=hit.ref, product_ref=args.product_ref or "*",
            firmware_version=args.firmware_version or "*", policy_key=hit.doc_key, text=hit.text,
            citation=hit.model_dump(mode="json")) for hit in result.hits],
            missing_fields=result.missing_fields, retrieval_mode="bm25", index_version=result.index_version)
        refs = [doc.record_id for doc in data.documents]
        if result.missing_fields:
            return data, refs, "needs_human"
        if not refs:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data", data=data)
        return data, refs, "success"

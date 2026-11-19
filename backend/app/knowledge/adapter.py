from sqlalchemy.orm import Session

from app.knowledge.index import search
from app.knowledge.schemas import SearchQuery
from app.tools.contracts import ErrorCode, KnowledgeData, KnowledgeRecord
from app.tools.mock import MockAdapter, ToolIssue


class DatabaseKnowledgeAdapter(MockAdapter):
    """复用六工具的执行边界；知识使用已发布索引，其他工具仍是 Mock。"""

    adapter_name = "knowledge-index-v1"

    def __init__(self, context, runtime, engine, client=None, provider_session=None):
        super().__init__(context, runtime, client)
        self.engine = engine
        self.provider_session = provider_session

    def search_knowledge(self, args):
        with Session(self.engine) as db:
            result = search(db, SearchQuery(query=args.query, product_ref=args.product_ref,
                                           firmware_version=args.firmware_version, region=args.region,
                                           channel=args.channel, as_of=args.as_of, retrieval_mode=args.retrieval_mode,
                                           rerank=args.rerank), self.provider_session)
        data = KnowledgeData(documents=[KnowledgeRecord(record_id=hit.ref, product_ref=args.product_ref or "*",
            firmware_version=args.firmware_version or "*", policy_key=hit.doc_key, text=hit.text,
            citation=hit.model_dump(mode="json")) for hit in result.hits],
            missing_fields=result.missing_fields, retrieval_mode=result.retrieval_mode, index_version=result.index_version,
            embedding_profile_id=str(result.embedding_profile_id) if result.embedding_profile_id else None,
            inference_mode=result.inference_mode, rerank_mode=result.rerank_mode,
            provider_usage=result.provider_usage, retrieval_details=result.retrieval_details)
        refs = [doc.record_id for doc in data.documents]
        if result.missing_fields:
            return data, refs, "needs_human"
        if not refs:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data", data=data)
        return data, refs, "success"

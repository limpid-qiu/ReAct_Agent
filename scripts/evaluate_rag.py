import argparse
import csv
import json
from pathlib import Path

from app.schemas.context import RequestContext
from rag.rag_service import RagSummarizeService


def load_queries(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"评估文件不存在: {path}")

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [
                item["query"] if isinstance(item, dict) else str(item)
                for item in data
            ]
        raise ValueError("JSON 评估文件必须是数组")

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if "query" not in (reader.fieldnames or []):
                raise ValueError("CSV 评估文件必须包含 query 列")
            return [row["query"] for row in reader if row.get("query")]

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_context(args: argparse.Namespace) -> RequestContext:
    return RequestContext(
        request_id=args.request_id,
        user_id=args.user_id,
        tenant_id=args.tenant_id,
        knowledge_base_id=args.knowledge_base_id,
        auth_type="local_eval",
        permissions=["knowledge:read"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="本地 RAG 检索质量评估脚本")
    parser.add_argument("--input", required=True, help="评估问题文件，支持 txt/csv/json")
    parser.add_argument("--output", default=None, help="可选：输出 JSONL 文件路径")
    parser.add_argument("--tenant-id", default="tenant_001")
    parser.add_argument("--user-id", default="eval_user")
    parser.add_argument("--knowledge-base-id", default="default")
    parser.add_argument("--request-id", default="req_local_rag_eval")
    args = parser.parse_args()

    queries = load_queries(Path(args.input))
    context = build_context(args)
    service = RagSummarizeService()

    output_file = None
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_file = output_path.open("w", encoding="utf-8")

    try:
        for index, query in enumerate(queries, start=1):
            result = service.rag_summarize_with_citations(
                query=query,
                context=context,
            )

            record = {
                "index": index,
                "query": query,
                "hit_count": len(result.retrieved_chunks),
                "citations": [
                    citation.model_dump()
                    for citation in result.citations
                ],
                "answer": result.answer,
            }

            print("=" * 80)
            print(f"[{index}] query: {query}")
            print(f"hit_count: {record['hit_count']}")
            print("citations:")
            for citation in record["citations"]:
                print(
                    "- "
                    f"source={citation.get('source')}, "
                    f"page={citation.get('page')}, "
                    f"document_id={citation.get('document_id')}, "
                    f"chunk_id={citation.get('chunk_id')}"
                )
            print("answer:")
            print(result.answer)

            if output_file:
                output_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )
    finally:
        if output_file:
            output_file.close()


if __name__ == "__main__":
    main()

"""LangSmith 유틸리티 함수"""

import os
from typing import Any, Dict, Optional
from langsmith import Client


def get_langsmith_client() -> Optional[Client]:
    """LangSmith 클라이언트 생성"""
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        return None
    
    return Client(
        api_key=api_key,
        api_url=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    )


def log_feedback(
    run_id: str,
    score: float,
    feedback_key: str = "user_score",
    comment: Optional[str] = None
) -> bool:
    """실행 결과에 대한 피드백 기록"""
    client = get_langsmith_client()
    if not client:
        return False
    
    try:
        client.create_feedback(
            run_id=run_id,
            key=feedback_key,
            score=score,
            comment=comment
        )
        return True
    except Exception as e:
        print(f"피드백 기록 실패: {e}")
        return False


def get_run_info(run_id: str) -> Optional[Dict[str, Any]]:
    """실행 정보 조회"""
    client = get_langsmith_client()
    if not client:
        return None
    
    try:
        run = client.read_run(run_id)
        return {
            "id": str(run.id),
            "name": run.name,
            "start_time": run.start_time,
            "end_time": run.end_time,
            "status": run.status,
            "inputs": run.inputs,
            "outputs": run.outputs,
            "error": run.error
        }
    except Exception as e:
        print(f"실행 정보 조회 실패: {e}")
        return None

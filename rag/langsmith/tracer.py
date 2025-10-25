"""LangSmith 추적 및 모니터링"""

import os
from typing import Optional
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager


class LangSmithTracer:
    """LangSmith 추적 설정 및 관리"""
    
    def __init__(self):
        self.enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        self.api_key = os.getenv("LANGCHAIN_API_KEY")
        self.project = os.getenv("LANGCHAIN_PROJECT", "default")
        self.endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        
    def is_enabled(self) -> bool:
        """LangSmith 추적이 활성화되어 있는지 확인"""
        return self.enabled and bool(self.api_key)
    
    def get_callback_manager(self) -> Optional[CallbackManager]:
        """LangSmith 콜백 매니저 반환"""
        if not self.is_enabled():
            return None
            
        tracer = LangChainTracer(project_name=self.project)
        return CallbackManager([tracer])
    
    def get_config(self) -> dict:
        """LangChain 실행 설정 반환"""
        if not self.is_enabled():
            return {}
            
        return {
            "callbacks": self.get_callback_manager(),
            "tags": [self.project],
            "metadata": {
                "project": self.project,
                "environment": os.getenv("ENVIRONMENT", "development")
            }
        }

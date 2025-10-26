# 에이전트 활용에 들어갈 LLM 모델 호출

from dotenv import load_dotenv
load_dotenv(override=True)
from langchain_openai import ChatOpenAI
from rag.core.config import get_config


def get_llm_model():
    """
    생성용 LLM 모델 (답변 생성, 분류 등)
    
    Config에서 GEN_LLM_MODEL과 GEN_LLM_TEMPERATURE를 읽어옴
    기본값: gpt-5-nano, temperature=1.0
    
    Returns:
        ChatOpenAI: 생성용 LLM 모델
    """
    config = get_config()
    llm = ChatOpenAI(
        model_name=config.GEN_LLM_MODEL,
        temperature=config.GEN_LLM_TEMPERATURE,
    )
    return llm


def get_eval_llm_model():
    """
    평가용 LLM 모델 (청크 관련성 평가)
    
    Config에서 EVAL_LLM_MODEL과 EVAL_LLM_TEMPERATURE를 읽어옴
    기본값: gpt-4o, temperature=0.0
    
    Returns:
        ChatOpenAI: 평가용 LLM 모델
    """
    config = get_config()
    llm = ChatOpenAI(
        model_name=config.EVAL_LLM_MODEL,
        temperature=config.EVAL_LLM_TEMPERATURE,
    )
    return llm

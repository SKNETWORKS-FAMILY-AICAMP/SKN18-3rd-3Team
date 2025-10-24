from dotenv import load_dotenv
load_dotenv(override=True)
from langchain_openai import ChatOpenAI

def get_llm_model():
    """환경 변수에 설정된 OpenAI API 키를 사용하여 ChatOpenAI 모델을 생성합니다."""
    llm = ChatOpenAI(
        model_name="gpt-5-nano",
    )
    return llm

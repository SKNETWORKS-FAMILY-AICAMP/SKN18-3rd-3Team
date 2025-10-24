# 상위 디렉토리를 모듈 탐색 경로에 추가
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from LangGraph.LangGraph import compile_langgraph

if __name__ == '__main__':
    graph = compile_langgraph()
    result = graph.invoke(
        {
            'question': 'KB우대저축통장 가입대상 말해줘'
        },
        config={'configurable': {'thread_id': 'local-test'}},
    )

    print('\n--- VectorDB Search 결과 ---')
    contents = result.get('contents') or []
    sources = result.get('sources') or []
    print('contents 샘플:', contents[:2] if contents else '<empty>')
    print('sources 샘플:', sources[:2] if sources else '<empty>')

    print('\n--- Eval 결과 ---')
    print('eval_results:', result.get('eval_results'))
    print('eval_score:', result.get('eval_score'))
    print('generation_strategy:', result.get('generation_strategy'))
    if result.get('web_error'):
        print('web_error:', result['web_error'])

    print('\n--- Final Answer ---')
    print(result.get('final_answer'))

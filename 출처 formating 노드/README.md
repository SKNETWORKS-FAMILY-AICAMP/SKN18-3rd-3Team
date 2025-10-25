# 출처 formating 노드 구현 방식
- 기준: dev => RAG/rag/graph의 build.py, nodes.py 참조
- nodes.py 아래쪽에 append_sources_to_answer 함수 추가
- build.py에서 workflow.add_node("append_sources", nodes.append_sources_to_answer) 추가
- add_edge 부분 수정
- append_sources_to_answer 함수 제작 => 추출.ipynb jupyter 파일을 참조
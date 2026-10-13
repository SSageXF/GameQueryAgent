"""Run with python -m scripts.index_knowledge while the backend is stopped."""
from app.vector_store import build

if __name__ == '__main__':
    result=build()
    print(f"Ready: {result['count']} records, {result['collection']}")

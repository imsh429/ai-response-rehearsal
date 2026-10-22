"""Versioned local Chroma index; explicit embeddings, no implicit model downloads."""
import hashlib
import json
import math
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from .config import DB_PATH, MODE


def corpus_hash(documents):
    canonical = json.dumps(sorted(documents, key=lambda d: d['id']), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


class Embeddings:
    """Provider is injected in tests. Demo vectors only exercise plumbing."""
    def __init__(self):
        self.mode = 'openai' if MODE == 'openai' else 'demo-hash'
        self.model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small') if self.mode == 'openai' else 'hash-ngram-256-v1'
        self.client = None

    def embed(self, texts):
        if self.mode == 'openai':
            if self.client is None:
                from openai import OpenAI
                # The MCP worker owns the overall deadline. Never multiply it
                # with hidden SDK retries before the evaluator even starts.
                self.client = OpenAI(timeout=15, max_retries=0)
            result = self.client.embeddings.create(model=self.model, input=texts)
            vectors = [x.embedding for x in sorted(result.data, key=lambda x: x.index)]
            return vectors, result.usage.model_dump()
        vectors = []
        for text in texts:
            clean = re.sub(r'\s+', '', text.lower())
            vector = [0.0] * 256
            for width in (2, 3):
                for i in range(max(0, len(clean) - width + 1)):
                    digest = hashlib.sha256(clean[i:i+width].encode()).digest()
                    vector[int.from_bytes(digest[:2], 'big') % 256] += 1 if digest[2] % 2 else -1
            norm = math.sqrt(sum(x*x for x in vector)) or 1
            vectors.append([x/norm for x in vector])
        return vectors, None


class PolicyRetriever:
    def __init__(self, path=None, embeddings=None, progress=None):
        self.progress = progress or (lambda stage: None)
        self.progress('chroma_import')
        import chromadb
        from chromadb.config import Settings
        self.embeddings = embeddings or Embeddings()
        self.progress('chroma_init')
        self.client = chromadb.PersistentClient(path=str(path or Path(os.getenv('RAG_DB_PATH', str(DB_PATH.parent/'chroma')))),
                                               settings=Settings(anonymized_telemetry=False))
        self.lock = threading.Lock()
        self._collections = {}
        self._queries = OrderedDict()

    def search(self, documents, query, top_k=4):
        query = query.strip()
        if not query or len(query) > 4000 or not 1 <= top_k <= 8:
            raise ValueError('검색어는 1~4000자, 검색 개수는 1~8이어야 합니다.')
        if not documents or len({d['id'] for d in documents}) != len(documents):
            raise ValueError('정책 문서가 비어 있거나 ID가 중복되었습니다.')
        started = time.perf_counter()
        digest = corpus_hash(documents)
        identity = hashlib.sha256((digest+self.embeddings.mode+self.embeddings.model).encode()).hexdigest()[:24]
        index_usage = None
        with self.lock:
            self.progress('chroma_collection')
            collection = self._collections.get(identity)
            if collection is None:
                collection = self.client.get_or_create_collection('policies-'+identity,
                    embedding_function=None, metadata={'hnsw:space': 'cosine'})
                indexed = set(collection.get(include=[])['ids'])
                missing = [d for d in documents if d['id'] not in indexed]
            else:
                missing = []
            if missing:
                self.progress('document_embeddings')
                vectors, index_usage = self.embeddings.embed([d['title']+'\n'+d['text'] for d in missing])
                self.progress('chroma_upsert')
                collection.upsert(ids=[d['id'] for d in missing], embeddings=vectors,
                    documents=[d['text'] for d in missing], metadatas=[{'title':d['title']} for d in missing])
            self._collections[identity] = collection
        index_ms = round((time.perf_counter()-started)*1000, 2)
        query_started = time.perf_counter()
        # Exact query/model cache only: never reuse a merely similar query.
        cache_key = (self.embeddings.mode, self.embeddings.model, query)
        with self.lock:
            query_cache_hit = cache_key in self._queries
            if query_cache_hit:
                vectors = self._queries.pop(cache_key)
                query_usage = None
            else:
                self.progress('query_embeddings')
                vectors, query_usage = self.embeddings.embed([query])
            self._queries[cache_key] = vectors
            if len(self._queries) > 128:
                self._queries.popitem(last=False)
            self.progress('chroma_query')
            result = collection.query(query_embeddings=vectors, n_results=min(top_k, len(documents)),
                                      include=['documents','metadatas','distances'])
        # Resolve authoritative snapshot text, not independently generated excerpts.
        by_id = {d['id']:d for d in documents}
        hits = [{**by_id[pid], 'distance':round(float(distance), 6)}
                for pid, distance in zip(result['ids'][0], result['distances'][0])]
        return {'query':query, 'hits':hits, 'top_k':top_k, 'corpus_size':len(documents),
                'corpus_hash':digest, 'embedding_mode':self.embeddings.mode, 'embedding_model':self.embeddings.model,
                'index_cache_hit':not bool(missing), 'query_cache_hit':query_cache_hit, 'index_ms':index_ms,
                'query_ms':round((time.perf_counter()-query_started)*1000, 2),
                'elapsed_ms':round((time.perf_counter()-started)*1000, 2),
                'embedding_usage':{'index':index_usage, 'query':query_usage}}


_retriever = None
_creation_lock = threading.Lock()
def get_retriever():
    global _retriever
    with _creation_lock:
        if _retriever is None:
            _retriever = PolicyRetriever()
    return _retriever


def retrieval_query(messages):
    """No oracle policy IDs or scenario labels enter the search query."""
    return '\n'.join(('상담사: ' if m['role']=='user' else '고객: ')+m['content']
                     for m in messages[-6:])[-4000:]

"""Persistent Qdrant retrieval; JSON snapshots are ingestion sources only."""
from . import native_runtime  # Must precede FastEmbed/Qdrant native dependencies.
import hashlib
import atexit
import json
import re
import threading
import uuid
from pathlib import Path
import numpy as np
from functools import lru_cache
from contextlib import closing

from fastembed import TextEmbedding
from huggingface_hub import snapshot_download
from qdrant_client import QdrantClient, models

from .config import ROOT
from .retrieval import Retriever

MODEL = 'BAAI/bge-small-zh-v1.5'
MODEL_REPOSITORY = 'Qdrant/bge-small-zh-v1.5'
MODEL_REVISION = '46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59'
INDEX_VERSION = '2-window-mean'
STORE = ROOT / 'data/vector'
CACHE = ROOT / 'data/models'
SOURCES = [ROOT/'data/knowledge.json', ROOT/'data/wiki/records.json']


def fingerprint():
    h = hashlib.sha256((MODEL+MODEL_REVISION+INDEX_VERSION).encode())
    for path in SOURCES:
        h.update(path.read_bytes())
    return h.hexdigest()


def encoder(local_files_only=False):
    options=dict(repo_id=MODEL_REPOSITORY,revision=MODEL_REVISION,cache_dir=str(CACHE),
                 allow_patterns=['*.json','*.txt','model_optimized.onnx'])
    try:
        path=snapshot_download(**options,local_files_only=True)
        required=['model_optimized.onnx','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json']
        if not all((Path(path)/name).is_file() for name in required):
            raise FileNotFoundError('Incomplete embedding model cache')
    except (FileNotFoundError, OSError):
        if local_files_only:
            raise RuntimeError('嵌入模型缓存缺失，请重新运行 python -m scripts.index_knowledge')
        path=snapshot_download(**options)
    return TextEmbedding(model_name=MODEL, cache_dir=str(CACHE), threads=4, specific_model_path=path,local_files_only=True)


def point_id(record_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'yibao:' + record_id))


def build():
    """Build a new collection, then atomically publish its manifest."""
    STORE.mkdir(parents=True, exist_ok=True)
    rows = sum((json.loads(p.read_text(encoding='utf-8')) for p in SOURCES), [])
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate knowledge IDs')
    digest = fingerprint()
    collection = 'knowledge_' + digest[:16]
    with closing(QdrantClient(path=str(STORE/'qdrant'))) as client:
        old_manifest=STORE/'manifest.json'
        if old_manifest.exists():
            old=json.loads(old_manifest.read_text(encoding='utf-8'))
            if old.get('fingerprint')==digest and client.collection_exists(collection) and client.count(collection,exact=True).count==len(rows):
                return old
        model = encoder()
        if not client.collection_exists(collection):
            client.create_collection(collection, vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE))
        for start in range(0, len(rows), 64):
            batch = rows[start:start+64]
            # Keep every part of a long Chinese passage within the token window.
            texts=[]; spans=[]
            for row in batch:
                begin=len(texts)
                body=row['body'] or row['title']
                texts.extend(row['title'][:60]+'\n'+body[i:i+350] for i in range(0,len(body),300))
                spans.append((begin,len(texts)))
            chunks=list(model.passage_embed(texts,batch_size=16))
            vectors=[]
            for begin,end in spans:
                value=np.mean(chunks[begin:end],axis=0)
                vectors.append(value/max(float(np.linalg.norm(value)),1e-12))
            client.upsert(collection, points=[models.PointStruct(id=point_id(r['id']), vector=v.tolist(), payload=r) for r,v in zip(batch,vectors)])
            print(f'Indexed {min(start+64,len(rows))}/{len(rows)}', flush=True)
        if client.count(collection, exact=True).count != len(rows):
            raise RuntimeError('Incomplete vector index')
    metadata = [{k:v for k,v in r.items() if k != 'body'} for r in rows]
    manifest = {'model':MODEL, 'fingerprint':digest, 'collection':collection, 'count':len(rows),
                'records':metadata, 'pending':[r for r in rows if r.get('claim_type')=='pending']}
    tmp = STORE/'manifest.tmp'
    tmp.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    tmp.replace(STORE/'manifest.json')
    return manifest


class PayloadMap:
    def __init__(self, store): self.store=store
    def get(self, key, default=None):
        with self.store.lock:
            points=self.store.client.retrieve(self.store.collection, ids=[point_id(key)], with_payload=True)
        return points[0].payload if points else default


class VectorRetriever(Retriever):
    def __init__(self, path=STORE, model=None):
        manifest_path=path/'manifest.json'
        if not manifest_path.exists():
            raise RuntimeError('向量索引未建立，请先运行 python -m scripts.index_knowledge')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['model'] != MODEL or manifest['fingerprint'] != fingerprint():
            raise RuntimeError('知识快照或嵌入模型已变化，请运行 python -m scripts.index_knowledge 重建索引')
        self.client=QdrantClient(path=str(path/'qdrant'), force_disable_check_same_thread=True)
        self.collection=manifest['collection']
        if self.client.count(self.collection,exact=True).count != manifest['count']:
            self.client.close()
            raise RuntimeError('向量索引不完整，请重建')
        try:
            self.model=model or encoder(local_files_only=True)
        except Exception:
            self.client.close()
            raise
        self.lock=threading.RLock()
        self.records=manifest['records']
        self.pending_records=manifest['pending']
        self.enhanced=True
        self.by_id=PayloadMap(self)
        self.names=sorted({r['entity'] for r in self.records if r.get('entity')},key=lambda x:(-len(x),x))
        self.context_entities=sorted({r['entity'] for r in self.records if r.get('entity') and r.get('section') in {'hero','equipment','effect','talent','players','summons'}})

    def pending(self, query):
        return Retriever(self.pending_records).pending(query)

    def fetch_many(self, ids):
        if not ids:return []
        with self.lock:
            points=self.client.retrieve(self.collection,ids=[point_id(key) for key in ids],with_payload=True)
        return [p.payload for p in points]

    def search_plan(self, original, plan, k=6):
        mode='钻石狂潮' if '钻石狂潮' in original else '万象大赛' if '万象大赛' in original else plan.mode
        catalog=self.catalog_fast_path(plan,mode)
        if catalog:return catalog
        hero_names={r.get('entity') for r in self.records if r.get('section')=='hero' and r.get('entity')}
        named=sorted((n for n in hero_names if n in original),key=original.index)
        purchase=len(named)>=2 and bool(re.search('怎么买|买谁|买哪个|购买|商店',original))
        coverage=[]
        if purchase:
            # All exact IDs and original fields are in the manifest: avoid repeated
            # full-collection scrolls for each named hero and for the base cost.
            metadata=[r for r in self.records if self.eligible(r,mode,plan.include_history)
                      and (r['id']=='E03' or r.get('entity') in named and r.get('field')=='original')]
            with self.lock:
                points=self.client.retrieve(self.collection,ids=[point_id(r['id']) for r in metadata],with_payload=True)
            exact=[p.payload for p in points]
            coverage=[r for r in exact if r['id']=='E03']
            for name in named:
                matches=sorted((r for r in exact if r.get('entity')==name),key=lambda r:r['id'])
                if matches:coverage.append(matches[0])
            if len(coverage)>=k:
                return coverage[:k]
        # Semantic search needs sentences, not an extra keyword-bag embedding.
        # Bound repeated full scans of the local Qdrant collection to three queries.
        queries=list(dict.fromkeys([original, *plan.queries]))[:3]
        batches=[[hit for hit in self.rank(q,mode,plan.include_history)
                  if self.matches_selection_names(hit[1],plan.selection)] for q in queries if q.strip()]
        selected=[];seen=set()
        for depth in range(k):
            for batch in batches:
                if depth<len(batch):
                    row=batch[depth][1]
                    if row['id'] not in seen:
                        selected.append(row);seen.add(row['id'])
                if len(selected)==k:break
            if len(selected)==k:break
        if not purchase:
            return selected
        result=[];seen=set()
        for row in coverage+selected:
            if row['id'] not in seen:
                result.append(row);seen.add(row['id'])
            if len(result)==k:break
        return result

    @lru_cache(maxsize=256)
    def rank(self, query, mode='万象大赛', include_history=False):
        with self.lock:
            vector=next(self.model.query_embed(query)).tolist()
            must=[models.FieldCondition(key='mode',match=models.MatchAny(any=[mode,'通用'])),
                  models.FieldCondition(key='verification',match=models.MatchAny(any=['official_page_checked','official_data_matched','wiki_snapshot']))]
            exclude=[models.FieldCondition(key='eligible',match=models.MatchValue(value=False)),
                     models.FieldCondition(key='claim_type',match=models.MatchValue(value='pending')),
                     models.FieldCondition(key='field',match=models.MatchAny(any=['profileState','skillEvidence','portraitBoundary','rawBaseStats','imageStatus','sourceNames','combatCategory','temporarilyOffShelf','evidenceLayer']))]
            if not include_history:
                statuses=sorted({r.get('publication_status','') for r in self.records if r.get('publication_status','').startswith('historical')} | {'off_shelf','associated_preview'})
                exclude.append(models.FieldCondition(key='publication_status',match=models.MatchAny(any=statuses)))
            points=self.client.query_points(self.collection,query=vector,query_filter=models.Filter(must=must,must_not=exclude),limit=100,with_payload=True).points
            rows={p.payload['id']:p.payload for p in points}
            scores={p.payload['id']:p.score for p in points}
            # Exact names prevent rare hero names being lost in semantic recall.
            names=[n for n in self.names if n in query]
            names=[n for n in names if not any(n!=other and n in other for other in names)]
            # Base rules have aliases but no entity name. Recall their payloads
            # too, so a long query prefixed with the game's name cannot push a
            # directly matching rule out of the semantic top 100.
            exact_metadata=[r for r in self.records if self.eligible(r,mode,include_history)
                            and (r.get('entity') in names or (not r.get('entity')
                                 and any(a and a in query for a in r.get('aliases',[]))))]
            if exact_metadata:
                ids=[point_id(r['id']) for r in exact_metadata]
                exact=self.client.retrieve(self.collection,ids=ids,with_payload=True)
                rows.update({p.payload['id']:p.payload for p in exact})
            return Retriever(list(rows.values())).rank(query,mode,include_history,semantic_scores=scores)


@lru_cache(maxsize=1)
def get_vector_retriever():
    retriever=VectorRetriever()
    atexit.register(retriever.client.close)
    return retriever

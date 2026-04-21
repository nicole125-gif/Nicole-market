"""
rag_helper.py — 年报向量检索模块
包含：Query Expansion + Hybrid Search(BM25) + Reranking + Injection Filter
"""
from pathlib import Path

_DB_DIR = Path(__file__).parent.parent / "pulse_vectordb"
_embedder = None
_collection = None
_reranker = None
_bm25 = None
_all_texts = None

INJECTION_KEYWORDS = [
   "忽略之前", "ignore previous",
    "你是Claude", "you are Claude", "I am Claude", "我是Claude",
    "不能假扮", "can't fulfill", "cannot fulfill",
    "Anthropic", "由Anthropic", "developed by",
    "I need to clarify", "I appreciate you",
    "我需要澄清", "我理解你的请求", "我注意到",
    "身份澄清", "坦诚地说", "需要说明",
    "我的角色", "我的能力", "我的限制",
    "language model", "大语言模型",
    "作为AI", "作为一个AI", "as an AI",
]


def _init():
    global _embedder, _collection, _reranker, _bm25, _all_texts
    if _collection is not None:
        return
    if not _DB_DIR.exists():
        print("[RAG] 向量数据库不存在，跳过")
        return
    try:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        import chromadb
        import jieba
        from rank_bm25 import BM25Okapi

        _embedder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        _reranker = CrossEncoder("BAAI/bge-reranker-base")

        client = chromadb.PersistentClient(path=str(_DB_DIR))
        _collection = client.get_collection("reports")

        print("[RAG] 构建 BM25 索引...")
        all_results = _collection.get()
        _all_texts = all_results["documents"]
        tokenized = [list(jieba.cut(t)) for t in _all_texts]
        _bm25 = BM25Okapi(tokenized)

        print(f"[RAG] 已加载，共 {_collection.count()} 个文本块，BM25 索引完成")
    except Exception as e:
        print(f"[RAG] 初始化失败，跳过: {e}")


def _expand_query(query: str) -> list:
    expansions = {
        "液冷数据中心": ["AI算力 数据中心冷却 设备投资", "CDU冷板 浸没式液冷 渗透率", "服务器散热 热管理 算力基础设施"],
        "半导体设备":   ["晶圆厂 国产替代 设备采购", "刻蚀机 薄膜沉积 国产化", "北方华创 中微 设备收入"],
        "绿氢电解槽":   ["PEM电解槽 招标 中标", "质子交换膜 制氢设备 投资", "氢能 电解水 产能"],
        "燃料电池":     ["氢燃料电池 重卡 商业化", "FCEV 氢车 示范城市", "燃料电池 补贴 销量"],
        "锂电":         ["动力电池 产线设备 订单", "先导智能 赢合 设备收入", "固态电池 产能 扩产"],
        "生物药":       ["GMP产线 新建 投资", "ADC 多肽 生产设备", "创新药 国内获批 产能"],
        "合成生物":     ["发酵罐 中试 量产", "华恒生物 凯赛生物 扩产", "生物制造 生物基材料"],
        "制药装备":     ["楚天科技 东富龙 订单", "医药FAI 固定资产投资", "GMP 制药设备 招标"],
        "CDMO":         ["药明康德 凯莱英 订单", "TIDES 多肽 GLP-1 产线", "合同研发生产 景气"],
        "质谱":         ["分析仪器 国产替代 采购", "禾信仪器 谱育科技 收入", "质谱 色谱 进口替代"],
        "基因测序":     ["华大智造 测序仪 订单", "因美纳 国产替代", "WGS 基因检测 市场"],
        "IVD":          ["化学发光 国产化 集采", "迈瑞医疗 体外诊断 收入", "POCT 基层医疗 采购"],
        "食品":         ["食品制造 固定资产投资", "预制菜 食品装备 产线", "食品机械 招标 新建"],
        "白酒":         ["白酒 产能 资本支出", "酒类 固定资产投资", "饮料 碳酸 产线 扩产"],
        "PMI":          ["制造业景气 新订单 生产", "官方PMI 财新PMI 荣枯线", "工业生产 扩张 收缩"],
        "M2":           ["货币政策 央行 降准降息", "社会融资 信贷 流动性", "M2增速 宽松 收紧"],
        "固定资产投资":  ["制造业FAI 增速", "规上工业增加值 高技术制造", "工业生产 资本支出 统计局"],
    }
    extras = [query]
    for keyword, variants in expansions.items():
        if keyword in query:
            extras.extend(variants)
            break
    return extras[:4]


def _is_safe(doc: str) -> bool:
    doc_lower = doc.lower()
    for kw in INJECTION_KEYWORDS:
        if kw.lower() in doc_lower:
            return False
    return True


def retrieve(query: str, top_k: int = 3) -> str:
    _init()
    if _collection is None or _embedder is None:
        return ""
    try:
        import jieba

        queries = _expand_query(query)
        print(f"[RAG] 查询扩展: {len(queries)} 个变体")

        all_candidates = []
        seen = set()

        # 1. 向量搜索（多查询）
        for q in queries:
            vector = _embedder.encode(q).tolist()
            results = _collection.query(
                query_embeddings=[vector],
                n_results=10
            )
            for doc in results["documents"][0]:
                key = doc[:50]
                if key not in seen:
                    seen.add(key)
                    all_candidates.append(doc)

        # 2. BM25 关键词搜索
        if _bm25 is not None and _all_texts is not None:
            tokens = list(jieba.cut(query))
            scores = _bm25.get_scores(tokens)
            top_idx = sorted(range(len(scores)),
                           key=lambda i: scores[i], reverse=True)[:15]
            for idx in top_idx:
                doc = _all_texts[idx]
                key = doc[:50]
                if key not in seen and scores[idx] > 0:
                    seen.add(key)
                    all_candidates.append(doc)

        if not all_candidates:
            return ""

        print(f"[RAG] 召回候选: {len(all_candidates)} 条（向量+BM25）")

        # 3. Injection Filter 过滤危险片段
        safe_candidates = [doc for doc in all_candidates if _is_safe(doc)]
        filtered = len(all_candidates) - len(safe_candidates)
        if filtered > 0:
            print(f"[RAG] 过滤疑似注入片段: {filtered} 条")

        if not safe_candidates:
            return ""

        # 4. Reranking 精选 Top K
        if _reranker is not None:
            pairs = [(query, doc) for doc in safe_candidates]
            scores = _reranker.predict(pairs)
            ranked = sorted(zip(safe_candidates, scores),
                          key=lambda x: x[1], reverse=True)
            top_docs = [doc for doc, score in ranked[:top_k]]
        else:
            top_docs = safe_candidates[:top_k]

        context = "\n---\n".join(top_docs)
        return f"\n## 相关年报背景\n{context}\n"

    except Exception as e:
        print(f"[RAG] 检索失败: {e}")
        return ""

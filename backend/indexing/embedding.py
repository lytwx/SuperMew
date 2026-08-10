"""文本向量化服务 - 支持本地 CPU/GPU 加载或远程 HTTP API (如基于 Tailscale 部署的外部 embedding-service)"""
import os
def _create_dense_embedder():
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
    except ImportError as e:
        raise RuntimeError("本地未安装 HuggingFace 依赖，请在 .env 中配置 EMBEDDING_API_URL 使用远程向量服务。") from e


class EmbeddingService:
    """文本向量化服务 - 支持本地模型或远程 API"""

    def __init__(self):
        self._api_url = (os.getenv("EMBEDDING_API_URL") or "").strip()
        self._api_key = (os.getenv("EMBEDDING_API_KEY") or "").strip()
        self._model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        
        # 仅在未配置远程 API 地址时延迟初始化本地 HuggingFace 模型
        if not self._api_url:
            self._embedder = _create_dense_embedder()
        else:
            self._embedder = None

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        # 优先使用远程 HTTP API (例如配合 Tailscale 的本地 embedding-service)
        if self._api_url:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            
            payload = {
                "input": texts,
                "model": self._model_name
            }
            
            try:
                response = requests.post(self._api_url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                res_data = response.json()
                
                # 兼容标准的 OpenAI Embeddings 结构 data: [{"embedding": [...], "index": 0}, ...]
                items = res_data.get("data", [])
                if not items and "embeddings" in res_data:
                    return res_data["embeddings"]
                
                # 按 index 排序保证文本与向量对应
                sorted_items = sorted(items, key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in sorted_items]
            except Exception as e:
                raise Exception(f"远程嵌入模型 API ({self._api_url}) 调用失败: {str(e)}") from e
        
        # 回退使用本地 HuggingFace 模型
        if self._embedder is None:
            self._embedder = _create_dense_embedder()
        try:
            return self._embedder.embed_documents(texts)
        except Exception as e:
            raise Exception(f"本地密集嵌入模型调用失败: {str(e)}") from e


# 全进程唯一实例
embedding_service = EmbeddingService()


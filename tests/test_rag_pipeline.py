"""
端到端 RAG 管道与 Embedding/Rerank 服务测试脚本
使用 .env 中的配置（Embedding API: http://100.99.91.88:8001/v1/embeddings, Rerank Host: http://100.99.91.88:8001）
进行全流程测试：
1. 远程服务连通性（Embedding 1024 维 + Rerank 交叉编码重排）
2. 文本切片 (Hierarchical Level 1/2/3 Parent-Child Chunks)
3. 父级分块存储 (PostgreSQL + Redis) & 叶子分块向量化写入 (Milvus)
4. 混合/向量检索 + Auto-merging + 本地 Reranker 排序与阈值过滤
5. 结果校验与清理
"""
import os
import sys
import io
import time
from pathlib import Path

# 设置 Windows 环境下的控制台 UTF-8 输出防护
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass

# 提前检测关系型数据库连通性（在导入 backend 模块之前）
db_url = os.getenv("DATABASE_URL", "")
if db_url and not db_url.startswith("sqlite"):
    try:
        from sqlalchemy import create_engine, text
        temp_engine = create_engine(db_url)
        with temp_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as _e:
        print(f"⚠️ 校验远程 PostgreSQL 数据库不连通或认证失败 ({_e})")
        print("💡 测试脚本自动切换为 SQLite 本地数据库 (sqlite:///./supermew_test.db)")
        os.environ["DATABASE_URL"] = "sqlite:///./supermew_test.db"

import requests
from backend.infra.database import init_db
from backend.indexing.document_loader import DocumentLoader
from backend.indexing.parent_chunk_store import ParentChunkStore
from backend.indexing.milvus_writer import MilvusWriter
from backend.indexing.milvus_client import get_milvus_store
from backend.indexing.embedding import embedding_service
from backend.rag.utils import retrieve_documents, RERANK_MODEL, RERANK_BINDING_HOST


TEST_FILENAME = "test_supermew_knowledge.md"
TEST_DOCUMENT_TEXT = """# 超级猫咪智能体 (SuperMew) 运维与排障指南

## 一、 系统架构与部署说明
超级猫咪智能体系统基于微服务架构构建，核心知识库包含企业规章、运维标准与智能决策流程。系统使用 Milvus 向量数据库进行向量检索，PostgreSQL 保存关系型元数据与父级 Chunk，Redis 提供高频缓存。密集向量模型采用 BAAI/bge-m3（1024维），重排序模型采用 BAAI/bge-reranker-v2-m3。

## 二、 硬件错误码与应急处置方案
当超级猫咪智能体硬件终端液晶屏或日志出现错误代码时，请参考以下规则进行排障：

### 1. 错误码 E-01 (电源异常)
- **故障原因**：外部电源波动或供电线缆接触不良。
- **处置步骤**：
  1. 检查主控电源指示灯状态。
  2. 拔插电源适配器并重新上电。
  3. 若依然报错，请更换 24V 适配器。

### 2. 错误码 E-02 (过载保护)
- **故障原因**：核心推理算力单元由于突发并发请求导致芯片温度过高，触发硬件过载保护机制。
- **处置步骤**：
  1. 立即暂停新的推理任务输入，保持风扇全速运转冷却 3 分钟。
  2. 检查设备后方散热通道是否被遮挡。
  3. 执行关机重启命令（Hold 住电源按键 5 秒即可触发安全复位）。
  4. 系统将在重启后自动恢复全量服务。

### 3. 错误码 E-03 (网络中断)
- **故障原因**：Tailscale 虚拟网卡连接断开或内网 IP 无法路由。
- **处置步骤**：运行 `tailscale status` 检查 100.99.91.88 节点连通性。

## 三、 客户合同与费用结算规范
1. 租金结算按自然月支付，每月 5 日前完成上月账单核对与对公转账。
2. 超期未支付租金将产生每日 0.05% 的滞纳金。
"""


def log_step(title: str):
    print("\n" + "=" * 60)
    print(f"👉 {title}")
    print("=" * 60)


def test_1_connectivity():
    log_step("步骤 1: 校验远程 Embedding 与 Rerank 服务连通性 (100.99.91.88:8001)")
    
    embedding_api = os.getenv("EMBEDDING_API_URL", "http://100.99.91.88:8001/v1/embeddings")
    rerank_host = os.getenv("RERANK_BINDING_HOST", "http://100.99.91.88:8001")
    
    print(f"🔹 EMBEDDING_API_URL: {embedding_api}")
    print(f"🔹 RERANK_BINDING_HOST: {rerank_host}")
    print(f"🔹 RERANK_MODEL: {RERANK_MODEL}")
    
    # 测试 Embedding
    print("\n[测试] 发送文本到 Embedding 服务...")
    try:
        vecs = embedding_service.get_embeddings(["SuperMew 测试连通性文本", "第二条测试文本"])
        print(f"✅ Embedding 响应成功！返回向量数量: {len(vecs)}, 单个向量维度: {len(vecs[0])}")
        assert len(vecs[0]) == 1024, f"期望维度 1024，实际返回 {len(vecs[0])}"
    except Exception as e:
        print(f"❌ Embedding 服务调用失败: {e}")
        return False

    # 测试 Rerank
    print("\n[测试] 发送请求到 Rerank 服务...")
    rerank_url = rerank_host.rstrip("/") + "/v1/rerank"
    try:
        resp = requests.post(
            rerank_url,
            json={
                "model": RERANK_MODEL,
                "query": "错误码 E-02 如何处理？",
                "documents": [
                    "租金结算按自然月支付，每月 5 日前完成转账。",
                    "错误码 E-02 表示硬件过载保护，请关机后重启。"
                ],
                "top_n": 2,
                "return_documents": True
            },
            timeout=10
        )
        resp.raise_for_status()
        res_data = resp.json()
        print(f"✅ Rerank 响应成功！返回数据: {res_data}")
        items = res_data.get("data") or res_data.get("results") or []
        assert len(items) > 0, "Rerank 返回结果为空"
        top_doc_idx = items[0]["index"]
        print(f"✅ 最相关文档索引 (应为 1): {top_doc_idx}, 相关度得分: {items[0].get('relevance_score')}")
    except Exception as e:
        print(f"❌ Rerank 服务调用失败: {e}")
        return False

    return True


def test_2_chunking():
    log_step("步骤 2: 测试文本多层级分片 (DocumentLoader Level 1 / Level 2 / Level 3)")
    
    loader = DocumentLoader(chunk_size=300, chunk_overlap=50)
    chunks = loader.load_text(TEST_DOCUMENT_TEXT, filename=TEST_FILENAME, doc_type="Markdown")
    
    print(f"✅ 生成分块总数: {len(chunks)}")
    
    l1_chunks = [c for c in chunks if c["chunk_level"] == 1]
    l2_chunks = [c for c in chunks if c["chunk_level"] == 2]
    l3_chunks = [c for c in chunks if c["chunk_level"] == 3]
    
    print(f"  - Level 1 (根父块): {len(l1_chunks)} 个")
    print(f"  - Level 2 (中父块): {len(l2_chunks)} 个")
    print(f"  - Level 3 (叶子块): {len(l3_chunks)} 个")
    
    assert len(l3_chunks) > 0, "Level 3 叶子分块数量不能为 0"
    
    # 示例打印一个 Level 3 分块的元数据
    sample_l3 = l3_chunks[0]
    print("\n示例 Leaf Chunk (Level 3):")
    print(f"  chunk_id: {sample_l3['chunk_id']}")
    print(f"  parent_chunk_id: {sample_l3['parent_chunk_id']}")
    print(f"  root_chunk_id: {sample_l3['root_chunk_id']}")
    print(f"  text 预览: {sample_l3['text'][:60]}...")
    
    return chunks


def test_3_storage(chunks: list[dict]):
    log_step("步骤 3: 测试父级分块 (PostgreSQL/Redis) 与叶子向量块 (Milvus) 写入")
    
    parent_chunks = [c for c in chunks if c["chunk_level"] in (1, 2)]
    leaf_chunks = [c for c in chunks if c["chunk_level"] == 3]
    
    # 1. 写入 ParentChunkStore
    print(f"\n[写入] 正在写入 {len(parent_chunks)} 个父级 Chunk 到 ParentChunkStore...")
    store = ParentChunkStore()
    upserted_count = store.upsert_documents(parent_chunks)
    print(f"✅ ParentChunkStore 写入成功: {upserted_count} 条记录")

    # 2. 写入 MilvusWriter
    print(f"\n[写入] 正在向量化并写入 {len(leaf_chunks)} 个叶子 Chunk 到 Milvus...")
    writer = MilvusWriter()
    writer.write_documents(leaf_chunks, batch_size=10)
    print(f"✅ MilvusWriter 写入成功！")
    
    return parent_chunks, leaf_chunks


def test_4_retrieval_and_rerank():
    log_step("步骤 4: 测试检索全流水线 (向量召回 -> Auto-merging -> Reranker 精排)")
    
    query = "错误码 E-02 如何处理？"
    print(f"🔍 测试查询 Query: '{query}'")
    
    retrieval_result = retrieve_documents(query=query, top_k=5)
    
    docs = retrieval_result.get("docs", [])
    meta = retrieval_result.get("meta", {})
    
    print("\n📊 检索元数据 Trace Meta:")
    for k, v in meta.items():
        print(f"  - {k}: {v}")
        
    print(f"\n🎯 最终精排后返回文档数量: {len(docs)}")
    for i, doc in enumerate(docs, 1):
        print(f"\n--- 文档 #{i} (Score / RerankScore: {doc.get('rerank_score') or doc.get('score')}) ---")
        print(f"Chunk ID: {doc.get('chunk_id')}")
        print(f"Level: {doc.get('chunk_level')}")
        print(f"Merged: {doc.get('merged_from_children', False)}")
        print(f"Text:\n{doc.get('text')[:200]}...")

    assert len(docs) > 0, "检索结果不应为空"
    top_text = docs[0].get("text", "")
    assert "E-02" in top_text or "过载保护" in top_text, "检索顶层文档应准确匹配过载保护/E-02 内容"
    print("\n✅ 检索与重排序逻辑验证完全符合期望！")


def cleanup_test_data():
    log_step("步骤 5: 清理测试产生的临时数据")
    print(f"🧹 清理文件名: {TEST_FILENAME}")
    try:
        # 清理 ParentStore
        store = ParentChunkStore()
        deleted_parents = store.delete_by_filename(TEST_FILENAME)
        print(f"  - 清理 PostgreSQL/Redis/SQLite 父分块: {deleted_parents} 条")
        
        # 清理 Milvus 测试数据
        milvus = get_milvus_store()
        milvus.delete(f'filename == "{TEST_FILENAME}"')
        print(f"  - 清理 Milvus 向量记录 (`filename == \"{TEST_FILENAME}\"`) 完成")
        print("✅ 测试数据清理完毕")
    except Exception as e:
        print(f"⚠️ 清理部分数据时提示: {e}")


def main():
    print("\n🚀 开始超级猫咪智能体 (SuperMew) RAG 管道端到端自动化测试\n")
    
    # 初始化关系型数据库（包含父级 Chunk 表）
    init_db()

    # 步骤 1：服务与数据库连通性
    if not test_1_connectivity():
        print("\n❌ 远程服务连通性检查失败，中断后续测试。请检查 100.99.91.88:8001 服务状态。")
        sys.exit(1)

    # 步骤 2：切片
    chunks = test_2_chunking()
    
    # 步骤 3：入库
    test_3_storage(chunks)
    
    # 步骤 4：检索与重排
    try:
        test_4_retrieval_and_rerank()
    finally:
        # 步骤 5：数据清理
        cleanup_test_data()
        
    print("\n" + "=" * 60)
    print("🎉 🎉 所有 RAG 管道与 Embedding/Rerank 端到端测试项全部成功通过！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

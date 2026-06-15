#!/usr/bin/env python3
"""去除知识库中关于 Qt 的重复文档，保留 qt_creator 项目文件"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings
from src.store.metadata import MetadataStore
from src.store.vector import VectorStore


def main():
    settings = load_settings()
    ms = MetadataStore(settings)
    vs = VectorStore(settings)

    docs = ms.list_documents()
    print(f"当前文档总数: {len(docs)}")
    print(f"当前向量块总数: {vs.count()}")

    # 找出标题中包含 qt 或 Qt 的文档
    qt_docs = [doc for doc in docs if 'qt' in doc['title'].lower() or 'Qt' in doc['title']]
    print(f"\nQt 相关文档数: {len(qt_docs)}")

    # 按来源分组（只处理 qt_creator 目录下的文件）
    from collections import defaultdict
    source_groups = defaultdict(list)
    for doc in qt_docs:
        source = doc['source']
        if 'qt_creator' in source:
            # 对于 qt_creator 下的文件，按文件名（不含路径）分组
            filename = Path(source).name
            source_groups[filename].append(doc)

    # 找出重复的文件
    total_deleted = 0
    total_chunks_deleted = 0

    for filename, group in source_groups.items():
        if len(group) <= 1:
            continue

        # 按块数排序，保留块数最多的版本
        group.sort(key=lambda x: x['chunk_count'], reverse=True)
        keep = group[0]
        to_remove = group[1:]

        print(f"\n文件名: {filename}")
        print(f"  保留: {keep['source']} ({keep['chunk_count']} 块)")

        for doc in to_remove:
            print(f"  删除: {doc['source']} ({doc['chunk_count']} 块)")
            # 删除向量块
            count = vs.delete_by_source(doc['source'])
            # 删除元数据
            ms.delete_document(doc['source'])
            total_deleted += 1
            total_chunks_deleted += count

    print(f"\n{'='*50}")
    print(f"删除重复文档数: {total_deleted}")
    print(f"删除向量块数: {total_chunks_deleted}")

    # 统计剩余文档
    remaining = ms.list_documents()
    print(f"剩余文档数: {len(remaining)}")
    print(f"剩余向量块数: {vs.count()}")

    ms.close()


if __name__ == "__main__":
    main()

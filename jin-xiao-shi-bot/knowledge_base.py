# -*- coding: utf-8 -*-
"""
知识库模块 - 加载和检索金蝶实施手册内容
"""

import os
import re
import logging
from typing import List, Optional


class KnowledgeBase:
    """知识库类，用于加载和管理金蝶实施手册内容"""

    def __init__(self, file_path: str, source_label: str = None):
        """
        初始化知识库

        Args:
            file_path: 知识库文件路径
            source_label: 该知识库所属的产品标签（如"金蝶云星空旗舰版"），
                          用于在多知识库场景下标注内容来源，默认从文件名推断
        """
        self.file_path = file_path
        self.source_label = source_label or self._infer_source_label(file_path)
        self.content = ""
        self.sections = {}
        self._load_content()
        self._parse_sections()

    @staticmethod
    def _infer_source_label(file_path: str) -> str:
        """从文件名推断产品标签，例如"金蝶K3WISE_实施学习手册.md" -> "金蝶K3WISE" """
        name = os.path.splitext(os.path.basename(file_path))[0]
        return name.split('_')[0] if '_' in name else name
    
    def _load_content(self):
        """加载知识库文件内容"""
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
        else:
            raise FileNotFoundError(f"知识库文件不存在: {self.file_path}")
    
    def _parse_sections(self):
        """解析知识库的各个章节"""
        # 按一级标题分割章节
        pattern = r'\n##\s+(.+?)\n'
        parts = re.split(pattern, self.content)
        
        if len(parts) > 1:
            # parts[0] 是标题和前言，parts[1], parts[3], parts[5]... 是章节名
            # parts[2], parts[4], parts[6]... 是章节内容
            self.sections['__header__'] = parts[0]
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    section_name = parts[i].strip()
                    section_content = parts[i + 1].strip()
                    self.sections[section_name] = section_content
        else:
            self.sections['__all__'] = self.content
    
    def get_section(self, section_name: str) -> Optional[str]:
        """
        获取指定章节内容
        
        Args:
            section_name: 章节名称（支持模糊匹配）
        
        Returns:
            章节内容，如果未找到返回 None
        """
        # 精确匹配
        if section_name in self.sections:
            return self.sections[section_name]
        
        # 模糊匹配
        section_name_lower = section_name.lower()
        for key, value in self.sections.items():
            if section_name_lower in key.lower():
                return value
        
        return None
    
    def search(self, query: str, max_chars: int = 8000) -> str:
        """
        搜索与查询相关的内容
        
        Args:
            query: 查询关键词
            max_chars: 最大返回字符数
        
        Returns:
            相关内容片段
        """
        query_lower = query.lower()
        results = []
        
        # 遍历所有章节，查找相关内容
        for section_name, content in self.sections.items():
            if section_name == '__header__':
                continue
            
            # 检查章节名是否包含关键词
            if query_lower in section_name.lower():
                results.append((section_name, content, 100))
                continue
            
            # 检查内容是否包含关键词
            content_lower = content.lower()
            if query_lower in content_lower:
                # 计算关键词出现次数作为相关度
                count = content_lower.count(query_lower)
                # 按段落分割，找到关键词所在的段落
                paragraphs = content.split('\n\n')
                relevant_paragraphs = []
                for para in paragraphs:
                    if query_lower in para.lower():
                        relevant_paragraphs.append(para.strip())
                
                if relevant_paragraphs:
                    results.append((
                        section_name,
                        '\n\n'.join(relevant_paragraphs[:5]),  # 最多取5个段落
                        count
                    ))
        
        # 按相关度排序
        results.sort(key=lambda x: x[2], reverse=True)
        
        # 合并结果
        combined = ""
        for section_name, content, _ in results:
            if len(combined) + len(content) < max_chars:
                combined += f"\n\n=== {section_name} ===\n\n{content}"
        
        if not combined:
            return ""
        
        return combined.strip()
    
    def suggest_sections(self, query: str, top_n: int = 3) -> List[str]:
        """
        当搜索无结果时，推荐最相关的章节标题供用户选择

        Args:
            query: 用户查询
            top_n: 最多返回几个章节标题

        Returns:
            推荐的章节标题列表
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            keywords = re.findall(r'[\w]+', query)

        # 中文没有天然分词，用二字滑动窗口做子串级别的粗匹配
        grams = set()
        for kw in keywords:
            if len(kw) < 2:
                continue
            for i in range(len(kw) - 1):
                grams.add(kw[i:i + 2])

        scored = []
        for section_name, section_content in self.sections.items():
            if section_name in ('__header__', '__all__'):
                continue
            haystack = section_name + section_content
            score = sum(haystack.count(g) for g in grams)
            if score > 0:
                scored.append((section_name, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if scored:
            return [name for name, _ in scored[:top_n]]

        # 完全没有重叠时，返回全部章节标题供用户挑选
        titles = [name for name in self.sections if name not in ('__header__', '__all__')]
        return titles[:top_n]

    def build_context(self, query: str) -> str:
        """
        为查询构建上下文
        
        Args:
            query: 用户问题
        
        Returns:
            包含相关知识库内容的上下文字符串
        """
        # 提取关键词进行搜索
        keywords = self._extract_keywords(query)
        
        relevant_content = []
        for keyword in keywords:
            content = self.search(keyword)
            if content and content not in relevant_content:
                relevant_content.append(content)
        
        if relevant_content:
            return "\n\n---\n\n".join(relevant_content)
        
        # 如果关键词搜索没结果，返回全文（限制长度）
        return self.content[:5000] + "\n\n（以上是知识库中的相关参考内容）"
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        从查询中提取关键词
        
        Args:
            query: 用户查询
        
        Returns:
            关键词列表
        """
        # 停用词
        stop_words = {
            '的', '了', '在', '是', '我', '你', '他', '她', '它',
            '这', '那', '有', '和', '与', '或', '及', '如何', '怎么',
            '什么', '哪个', '怎么', '为什么', '吗', '呢', '吧', '啊',
            '请问', '请教', '麻烦', '一下', '帮忙', '帮助'
        }
        
        # 简单分词（按空格和标点）
        words = re.findall(r'[\w]+', query)
        
        # 过滤停用词，保留长度>=2的词
        keywords = [w for w in words if w not in stop_words and len(w) >= 2]
        
        # 如果关键词太少，直接返回原查询分词
        if len(keywords) < 2:
            keywords = [w for w in words if len(w) >= 2][:5]
        
        return keywords[:5]  # 最多返回5个关键词
    
    def get_full_content(self) -> str:
        """获取完整知识库内容"""
        return self.content


class MultiKnowledgeBase:
    """多知识库聚合类，同时管理多个产品的实施手册，检索时合并结果并标注来源"""

    def __init__(self, knowledge_bases: List[KnowledgeBase]):
        if not knowledge_bases:
            raise ValueError("至少需要一个知识库")
        self.knowledge_bases = knowledge_bases

    @property
    def content(self) -> str:
        """兼容旧接口：拼接全部知识库内容"""
        return "\n\n".join(kb.content for kb in self.knowledge_bases)

    @property
    def sections(self) -> dict:
        """兼容旧接口：合并所有知识库的章节（用于统计章节数等场景）"""
        merged = {}
        for kb in self.knowledge_bases:
            merged.update(kb.sections)
        return merged

    def search(self, query: str, max_chars: int = 8000) -> str:
        """
        在所有知识库中检索，每个知识库的结果标注产品来源，避免跨产品内容混淆

        Args:
            query: 查询关键词
            max_chars: 每个知识库返回的最大字符数

        Returns:
            合并后的检索结果，每段标注来自哪个产品手册
        """
        combined_parts = []
        for kb in self.knowledge_bases:
            result = kb.search(query, max_chars=max_chars)
            if result:
                combined_parts.append(f"【以下内容来自《{kb.source_label}》知识库】\n{result}")

        return "\n\n---\n\n".join(combined_parts)

    def suggest_sections(self, query: str, top_n: int = 3) -> List[str]:
        """
        跨所有知识库推荐相关章节，标题前缀标注所属产品

        Args:
            query: 用户查询
            top_n: 每个知识库最多返回几个章节标题

        Returns:
            带产品前缀的推荐章节标题列表
        """
        suggestions = []
        for kb in self.knowledge_bases:
            for name in kb.suggest_sections(query, top_n=top_n):
                suggestions.append(f"《{kb.source_label}》- {name}")
        return suggestions

    def get_source_labels(self) -> List[str]:
        """返回当前加载的所有知识库产品标签"""
        return [kb.source_label for kb in self.knowledge_bases]


def load_knowledge_base(file_path: str = None) -> KnowledgeBase:
    """
    加载单个知识库的便捷函数

    Args:
        file_path: 知识库文件路径，默认使用配置中的第一个路径

    Returns:
        KnowledgeBase 实例
    """
    if file_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 尝试从 config 获取（优先取多知识库配置的第一项，兼容旧的单路径配置）
        try:
            from config import KNOWLEDGE_BASE_PATHS
            file_path = os.path.join(base_dir, KNOWLEDGE_BASE_PATHS[0])
        except ImportError:
            try:
                from config import KNOWLEDGE_BASE_PATH
                file_path = os.path.join(base_dir, KNOWLEDGE_BASE_PATH)
            except ImportError:
                pass

        # 如果仍未找到，使用默认路径
        if file_path is None or not os.path.exists(file_path):
            possible_paths = [
                "knowledge/金蝶小微产品_客户常见问题集.md",
                os.path.join(os.path.dirname(__file__), "knowledge", "金蝶小微产品_客户常见问题集.md")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    file_path = path
                    break

        if file_path is None or not os.path.exists(file_path):
            raise FileNotFoundError("未找到知识库文件")

    return KnowledgeBase(file_path)


def load_knowledge_bases(file_paths: List[str] = None) -> MultiKnowledgeBase:
    """
    加载多个知识库文件，聚合为 MultiKnowledgeBase

    Args:
        file_paths: 知识库文件路径列表（相对或绝对路径），默认使用配置中的 KNOWLEDGE_BASE_PATHS

    Returns:
        MultiKnowledgeBase 实例
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if file_paths is None:
        try:
            from config import KNOWLEDGE_BASE_PATHS
            file_paths = KNOWLEDGE_BASE_PATHS
        except ImportError:
            try:
                from config import KNOWLEDGE_BASE_PATH
                file_paths = [KNOWLEDGE_BASE_PATH]
            except ImportError:
                file_paths = ["knowledge/金蝶小微产品_客户常见问题集.md"]

    knowledge_bases = []
    missing = []
    for path in file_paths:
        full_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        if os.path.exists(full_path):
            knowledge_bases.append(KnowledgeBase(full_path))
        else:
            missing.append(full_path)

    if missing:
        logging.getLogger(__name__).warning(f"以下知识库文件未找到，已跳过: {missing}")

    if not knowledge_bases:
        raise FileNotFoundError(f"未找到任何知识库文件，尝试的路径: {file_paths}")

    return MultiKnowledgeBase(knowledge_bases)


if __name__ == "__main__":
    # 测试代码
    mkb = load_knowledge_bases()
    print(f"已加载 {len(mkb.knowledge_bases)} 个知识库: {mkb.get_source_labels()}")

    # 测试搜索
    result = mkb.search("采购")
    print(f"\n搜索'采购'返回 {len(result)} 字符")

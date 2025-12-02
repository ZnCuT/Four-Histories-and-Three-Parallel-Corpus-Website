#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量导入工具：支持多种格式的语料批量导入
支持的格式：
1. CSV格式：book,category,chapter,title,wenyan,zh,en
2. Excel格式：同上
3. 单个txt文件：三平行格式
4. 目录批量导入：整个目录的txt文件
"""

import os
import csv
import re
import pandas as pd
from pathlib import Path

RAW_DIR = "data/raw"

# 四史分类配置
BOOK_CATEGORIES = {
    "shiji": {"name": "史记", "categories": {"benji": "本纪", "shijia": "世家", "liezhuan": "列传", "shu": "书", "biao": "表"}},
    "hanshu": {"name": "汉书", "categories": {"benji": "本纪", "biao": "表", "zhi": "志", "liezhuan": "列传"}},
    "houhanshu": {"name": "后汉书", "categories": {"liezhuan": "列传","diji": "帝纪","shu": "书"}},
    "sanguozhi": {"name": "三国志", "categories": {"wei": "魏书", "shu": "蜀书", "wu": "吴书"}}
}

def safe_filename(text, max_length=50):
    """生成安全的文件名"""
    # 去除特殊字符，保留中文、英文、数字
    safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', text)
    return safe[:max_length]

def create_three_parallel_content(wenyan, zh, en):
    """
    创建三平行格式内容
    将三种语言按段落对应组织
    """
    if not any([wenyan, zh, en]):
        return ""
    
    # 分割段落
    w_paragraphs = [p.strip() for p in (wenyan or "").split('\n\n') if p.strip()]
    z_paragraphs = [p.strip() for p in (zh or "").split('\n\n') if p.strip()]
    e_paragraphs = [p.strip() for p in (en or "").split('\n\n') if p.strip()]
    
    # 对齐段落数量
    max_paras = max(len(w_paragraphs), len(z_paragraphs), len(e_paragraphs))
    
    parallel_groups = []
    for i in range(max_paras):
        w = w_paragraphs[i] if i < len(w_paragraphs) else ""
        z = z_paragraphs[i] if i < len(z_paragraphs) else ""
        e = e_paragraphs[i] if i < len(e_paragraphs) else ""
        
        # 组成三平行段落组
        group_lines = []
        if w: group_lines.append(w)
        if z: group_lines.append(z)
        if e: group_lines.append(e)
        
        if group_lines:
            parallel_groups.append('\n'.join(group_lines))
    
    return '\n\n'.join(parallel_groups)

def import_from_csv(csv_path):
    """
    从CSV文件导入语料
    CSV格式：book,category,chapter_num,title,wenyan,zh,en
    """
    print(f"正在从CSV导入: {csv_path}")
    
    imported_count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            book_id = row['book'].strip()
            category_id = row['category'].strip()
            chapter_num = row.get('chapter_num', '').strip()
            title = row['title'].strip()
            wenyan = row.get('wenyan', '').strip()
            zh = row.get('zh', '').strip()
            en = row.get('en', '').strip()
            
            if not all([book_id, category_id, title]):
                print(f"跳过不完整的行: {row}")
                continue
            
            # 验证书籍和分类
            if book_id not in BOOK_CATEGORIES:
                print(f"警告: 未知书籍 {book_id}，将创建默认配置")
                BOOK_CATEGORIES[book_id] = {"name": book_id, "categories": {category_id: category_id}}
            elif category_id not in BOOK_CATEGORIES[book_id]["categories"]:
                print(f"警告: {book_id} 中没有分类 {category_id}，将添加")
                BOOK_CATEGORIES[book_id]["categories"][category_id] = category_id
            
            # 创建目录
            category_dir = os.path.join(RAW_DIR, book_id, category_id)
            os.makedirs(category_dir, exist_ok=True)
            
            # 生成文件名
            if chapter_num:
                filename = f"{chapter_num:0>2}_{safe_filename(title)}.txt"
            else:
                filename = f"{safe_filename(title)}.txt"
            
            # 创建三平行内容
            content = create_three_parallel_content(wenyan, zh, en)
            
            # 写入文件
            file_path = os.path.join(category_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  导入: {book_id}/{category_id}/{filename}")
            imported_count += 1
    
    print(f"CSV导入完成，共导入 {imported_count} 个章节")

def import_from_excel(excel_path):
    """
    从Excel文件导入语料
    Excel格式：book,category,chapter_num,title,wenyan,zh,en
    """
    print(f"正在从Excel导入: {excel_path}")
    
    try:
        df = pd.read_excel(excel_path)
    except ImportError:
        print("错误: 需要安装pandas和openpyxl来处理Excel文件")
        print("运行: pip install pandas openpyxl")
        return
    
    imported_count = 0
    for _, row in df.iterrows():
        book_id = str(row.get('book', '')).strip()
        category_id = str(row.get('category', '')).strip()
        chapter_num = str(row.get('chapter_num', '')).strip()
        title = str(row.get('title', '')).strip()
        wenyan = str(row.get('wenyan', '')).strip()
        zh = str(row.get('zh', '')).strip()
        en = str(row.get('en', '')).strip()
        
        if not all([book_id, category_id, title]):
            print(f"跳过不完整的行: {row.to_dict()}")
            continue
        
        # 验证书籍和分类
        if book_id not in BOOK_CATEGORIES:
            print(f"警告: 未知书籍 {book_id}，将创建默认配置")
            BOOK_CATEGORIES[book_id] = {"name": book_id, "categories": {category_id: category_id}}
        elif category_id not in BOOK_CATEGORIES[book_id]["categories"]:
            print(f"警告: {book_id} 中没有分类 {category_id}，将添加")
            BOOK_CATEGORIES[book_id]["categories"][category_id] = category_id
        
        # 创建目录
        category_dir = os.path.join(RAW_DIR, book_id, category_id)
        os.makedirs(category_dir, exist_ok=True)
        
        # 生成文件名
        if chapter_num and chapter_num != 'nan':
            filename = f"{chapter_num:0>2}_{safe_filename(title)}.txt"
        else:
            filename = f"{safe_filename(title)}.txt"
        
        # 创建三平行内容
        content = create_three_parallel_content(wenyan, zh, en)
        
        # 写入文件
        file_path = os.path.join(category_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  导入: {book_id}/{category_id}/{filename}")
        imported_count += 1
    
    print(f"Excel导入完成，共导入 {imported_count} 个章节")

def import_single_txt(txt_path, book_id, category_id, title=None):
    """
    导入单个三平行格式的txt文件
    """
    if not title:
        title = Path(txt_path).stem
    
    print(f"正在导入单个文件: {txt_path}")
    
    # 验证书籍和分类
    if book_id not in BOOK_CATEGORIES:
        print(f"警告: 未知书籍 {book_id}，将创建默认配置")
        BOOK_CATEGORIES[book_id] = {"name": book_id, "categories": {category_id: category_id}}
    elif category_id not in BOOK_CATEGORIES[book_id]["categories"]:
        print(f"警告: {book_id} 中没有分类 {category_id}，将添加")
        BOOK_CATEGORIES[book_id]["categories"][category_id] = category_id
    
    # 创建目录
    category_dir = os.path.join(RAW_DIR, book_id, category_id)
    os.makedirs(category_dir, exist_ok=True)
    
    # 读取原文件
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 生成文件名
    filename = f"{safe_filename(title)}.txt"
    
    # 写入目标位置
    target_path = os.path.join(category_dir, filename)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  导入: {book_id}/{category_id}/{filename}")

def create_template_csv(output_path="template.csv"):
    """创建CSV模板文件"""
    headers = ['book', 'category', 'chapter_num', 'title', 'wenyan', 'zh', 'en']
    sample_data = [
        ['shiji', 'benji', '1', '五帝本纪', '昔在黄帝...', '从前黄帝...', 'Long ago, the Yellow Emperor...'],
        ['shiji', 'shijia', '1', '吴太伯世家', '吴太伯...', '吴太伯...', 'Wu Taibo...'],
        ['hanshu', 'benji', '1', '高祖本纪', '高祖...', '高祖...', 'Emperor Gaozu...']
    ]
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(sample_data)
    
    print(f"CSV模板已创建: {output_path}")

def validate_data():
    """验证已导入的数据完整性"""
    print("正在验证数据完整性...")
    
    if not os.path.exists(RAW_DIR):
        print(f"数据目录不存在: {RAW_DIR}")
        return
    
    total_chapters = 0
    for book_id in os.listdir(RAW_DIR):
        book_path = os.path.join(RAW_DIR, book_id)
        if not os.path.isdir(book_path):
            continue
        
        print(f"\n{book_id}:")
        book_chapters = 0
        
        for category_id in os.listdir(book_path):
            category_path = os.path.join(book_path, category_id)
            if not os.path.isdir(category_path):
                continue
            
            txt_files = [f for f in os.listdir(category_path) if f.endswith('.txt')]
            chapter_count = len(txt_files)
            book_chapters += chapter_count
            
            print(f"  {category_id}: {chapter_count} 章")
        
        print(f"  总计: {book_chapters} 章")
        total_chapters += book_chapters
    
    print(f"\n数据验证完成，全部语料库共 {total_chapters} 章")

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("批量导入工具使用方法:")
        print("python batch_import.py csv <csv_file>                 # 从CSV导入")
        print("python batch_import.py excel <excel_file>             # 从Excel导入")
        print("python batch_import.py txt <txt_file> <book> <category> [title]  # 导入单个txt")
        print("python batch_import.py template [output.csv]          # 创建CSV模板")
        print("python batch_import.py validate                       # 验证数据")
        return
    
    command = sys.argv[1].lower()
    
    if command == "csv" and len(sys.argv) >= 3:
        import_from_csv(sys.argv[2])
    elif command == "excel" and len(sys.argv) >= 3:
        import_from_excel(sys.argv[2])
    elif command == "txt" and len(sys.argv) >= 5:
        txt_file = sys.argv[2]
        book_id = sys.argv[3]
        category_id = sys.argv[4]
        title = sys.argv[5] if len(sys.argv) > 5 else None
        import_single_txt(txt_file, book_id, category_id, title)
    elif command == "template":
        output = sys.argv[2] if len(sys.argv) >= 3 else "template.csv"
        create_template_csv(output)
    elif command == "validate":
        validate_data()
    else:
        print("无效的命令。请查看使用方法。")

if __name__ == "__main__":
    main()
"""Generate static site into out/ by rendering Flask templates with data from data/raw/.

Usage: python build_static.py
"""
import os
import shutil
import sys
import traceback
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, 'out')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')


def parse_three_parallel_file(file_path):
    """
    解析三平行格式的单个文件
    格式: 文言文\n白话文\n英文\n\n文言文\n白话文\n英文...
    返回: {'wenyan': str, 'zh': str, 'en': str}
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except FileNotFoundError:
        return {'wenyan': '', 'zh': '', 'en': ''}
    
    if not content:
        return {'wenyan': '', 'zh': '', 'en': ''}
    
    # 按双换行分割段落组
    paragraph_groups = content.split('\n\n')
    
    wenyan_parts = []
    zh_parts = []
    en_parts = []
    
    for group in paragraph_groups:
        lines = [line.strip() for line in group.split('\n') if line.strip()]
        
        if len(lines) >= 3:
            # 标准三平行格式
            wenyan_parts.append(lines[0])
            zh_parts.append(lines[1]) 
            en_parts.append(lines[2])
        elif len(lines) == 2:
            # 可能缺少英文
            wenyan_parts.append(lines[0])
            zh_parts.append(lines[1])
            en_parts.append("")
        elif len(lines) == 1:
            # 只有一行，可能是标题或单独内容
            wenyan_parts.append(lines[0])
            zh_parts.append("")
            en_parts.append("")
    
    return {
        'wenyan': '\n\n'.join(wenyan_parts),
        'zh': '\n\n'.join(zh_parts),
        'en': '\n\n'.join(en_parts)
    }

def load_books_from_raw():
    """
    检测并加载数据：优先使用新的三级目录结构，回退到旧格式
    """
    books = []
    if not os.path.isdir(RAW_DIR):
        return books
    
    # 四史的分类配置
    book_configs = {
        "shiji": {"name": "史记", "categories": {"benji": "本纪", "shijia": "世家", "liezhuan": "列传", "shu": "书", "biao": "表"}},
        "hanshu": {"name": "汉书", "categories": {"benji": "本纪", "biao": "表", "zhi": "志", "liezhuan": "列传"}},
        "houhanshu": {"name": "后汉书", "categories": {"liezhuan": "列传","diji": "帝纪","shu": "书"}},
        "sanguozhi": {"name": "三国志", "categories": {"wei": "魏书", "shu": "蜀书", "wu": "吴书"}}
    }
    
    for book_id in sorted(os.listdir(RAW_DIR)):
        book_path = os.path.join(RAW_DIR, book_id)
        if not os.path.isdir(book_path):
            continue
        
        # 检查是否是新的三级结构
        has_categories = any(os.path.isdir(os.path.join(book_path, item)) 
                           for item in os.listdir(book_path) 
                           if not item.endswith('.txt'))
        
        if has_categories:
            # 新的三级结构
            book_config = book_configs.get(book_id, {"name": book_id, "categories": {}})
            book_title = book_config["name"]
            
            categories = []
            for cat_dir in sorted(os.listdir(book_path)):
                cat_path = os.path.join(book_path, cat_dir)
                if not os.path.isdir(cat_path):
                    continue
                
                cat_title = book_config["categories"].get(cat_dir, cat_dir)
                
                # 加载该分类下的章节
                chapters = []
                chapter_files = [f for f in os.listdir(cat_path) if f.endswith('.txt')]
                
                for i, filename in enumerate(sorted(chapter_files)):
                    file_path = os.path.join(cat_path, filename)
                    
                    # 从文件名提取章节标题
                    chapter_title = filename[:-4]  # 去掉.txt后缀
                    # 去掉可能的序号前缀 (如 "01_标题" -> "标题")
                    if '_' in chapter_title:
                        chapter_title = chapter_title.split('_', 1)[1]
                    
                    # 解析三平行内容
                    content = parse_three_parallel_file(file_path)
                    
                    chapters.append({
                        'id': i + 1,
                        'title': chapter_title,
                        'wenyan': content['wenyan'],
                        'zh': content['zh'], 
                        'en': content['en'],
                        'paragraphs': content['paragraphs']  # 新增：语义对齐的段落组
                    })
                
                if chapters:  # 只添加有章节的分类
                    categories.append({
                        'id': cat_dir,
                        'title': cat_title,
                        'chapters': chapters
                    })
            
            if categories:  # 只添加有内容的书籍
                books.append({
                    'id': book_id,
                    'title': book_title,
                    'categories': categories
                })
        
        else:
            # 旧的格式：wenyan.txt, zh.txt, en.txt
            files = {
                'wenyan': os.path.join(book_path, 'wenyan.txt'),
                'zh': os.path.join(book_path, 'zh.txt'),
                'en': os.path.join(book_path, 'en.txt'),
            }
            contents = {}
            for k, p in files.items():
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        contents[k] = f.read()
                except FileNotFoundError:
                    contents[k] = ''
            
            # simple chapter split by lines beginning with '## '
            def parse(text):
                lines = text.splitlines()
                chapters = []
                cur_title = ''
                cur_lines = []
                for line in lines:
                    if line.startswith('## '):
                        if cur_lines or cur_title:
                            chapters.append({'title': cur_title.strip(), 'content': '\n'.join(cur_lines).strip()})
                        cur_title = line[3:].strip()
                        cur_lines = []
                    else:
                        cur_lines.append(line)
                if cur_lines or cur_title:
                    chapters.append({'title': cur_title.strip(), 'content': '\n'.join(cur_lines).strip()})
                if not chapters:
                    return [{'title': '', 'content': text.strip()}]
                return chapters

            ch_w = parse(contents['wenyan'])
            ch_z = parse(contents['zh'])
            ch_e = parse(contents['en'])
            n = min(len(ch_w), len(ch_z), len(ch_e)) if (ch_w and ch_z and ch_e) else max(len(ch_w), len(ch_z), len(ch_e))
            chapters = []
            for i in range(n):
                w = ch_w[i]['content'] if i < len(ch_w) else ''
                z = ch_z[i]['content'] if i < len(ch_z) else ''
                e = ch_e[i]['content'] if i < len(ch_e) else ''
                title = (ch_w[i]['title'] if i < len(ch_w) else '') or (ch_z[i]['title'] if i < len(ch_z) else '') or (ch_e[i]['title'] if i < len(ch_e) else '') or f'第{i+1}章'
                chapters.append({'id': i+1, 'title': title, 'wenyan': w, 'zh': z, 'en': e})
            
            # 对旧格式创建兼容的结构
            books.append({
                'id': book_id, 
                'title': book_id, 
                'categories': [{
                    'id': 'default',
                    'title': '章节',
                    'chapters': chapters
                }]
            })
    
    return books


def render_site(books):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    # copy static
    out_static = os.path.join(OUT_DIR, 'static')
    if os.path.exists(out_static):
        shutil.rmtree(out_static)
    shutil.copytree(STATIC_DIR, out_static)

    # render home
    home_tpl = env.get_template('home.html')
    with open(os.path.join(OUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(home_tpl.render(books=books))

    # load templates
    book_tpl = env.get_template('book.html')
    category_tpl = env.get_template('category.html')
    chapter_tpl = env.get_template('chapter.html')
    
    for book in books:
        # render book page (shows categories)
        book_dir = os.path.join(OUT_DIR, 'book', book['id'])
        os.makedirs(book_dir, exist_ok=True)
        with open(os.path.join(book_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(book_tpl.render(book=book))

        # render each category and its chapters
        for category in book['categories']:
            # render category page (shows chapter list)
            category_dir = os.path.join(book_dir, category['id'])
            os.makedirs(category_dir, exist_ok=True)
            with open(os.path.join(category_dir, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(category_tpl.render(book=book, category=category))

            # render individual chapters
            for i, chapter in enumerate(category['chapters']):
                chapter_dir = os.path.join(category_dir, 'chapter', str(chapter['id']))
                os.makedirs(chapter_dir, exist_ok=True)
                
                # calculate prev/next URLs within the category
                chapters = category['chapters']
                prev_url = None
                next_url = None
                if i > 0:
                    prev_ch = chapters[i - 1]
                    prev_url = f"/book/{book['id']}/{category['id']}/chapter/{prev_ch['id']}/"
                if i < len(chapters) - 1:
                    next_ch = chapters[i + 1]
                    next_url = f"/book/{book['id']}/{category['id']}/chapter/{next_ch['id']}/"
                
                # normalize chapter data for template
                chapter_display = {
                    'id': chapter['id'],
                    'title': chapter.get('title', ''),
                    'wenyan': chapter.get('wenyan', ''),
                    'z': chapter.get('zh', ''),  # template expects 'z' not 'zh'
                    'en': chapter.get('en', ''),
                    'paragraphs': chapter.get('paragraphs', [])  # 新增：段落组
                }
                
                chapter_path = os.path.join(chapter_dir, 'index.html')
                with open(chapter_path, 'w', encoding='utf-8') as f:
                    f.write(chapter_tpl.render(
                        book=book,
                        category=category,
                        chapter=chapter_display,
                        prev_url=prev_url,
                        next_url=next_url
                    ))


def main():
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        print('Python executable:', sys.executable)
        print('Python version:', sys.version)
        books = load_books_from_raw()
        render_site(books)
        print('Static site generated in', OUT_DIR)
    except Exception:
        print('ERROR: build failed, traceback follows:')
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()

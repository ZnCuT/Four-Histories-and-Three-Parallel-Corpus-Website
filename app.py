from flask import Flask, render_template, request, abort, jsonify
import json
import os
import re
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'corpus.json')

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))

# --- New: load raw three-parallel TXT files organized under data/raw/<book_slug>/ ---
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')

# 搜索和高级功能
def highlight_text(text, query):
    """高亮显示搜索关键词"""
    if not query or not text:
        return text
    
    pattern = re.escape(query)
    return re.sub(f'({pattern})', r'<mark>\1</mark>', text, flags=re.IGNORECASE)

def search_in_books(query, search_scope='all', book_filter=None):
    """在所有书籍中搜索内容"""
    results = []
    query_lower = query.lower().strip()
    
    if not query_lower:
        return results
    
    for book in BOOKS:
        if book_filter and book['id'] != book_filter:
            continue
            
        for category in book['categories']:
            for chapter in category['chapters']:
                matches = []
                
                # 搜索标题
                if search_scope in ('all', 'title'):
                    if query_lower in chapter['title'].lower():
                        matches.append({
                            'type': 'title',
                            'content': chapter['title'],
                            'highlight': highlight_text(chapter['title'], query)
                        })
                
                # 搜索内容
                if search_scope in ('all', 'content'):
                    for idx, paragraph in enumerate(chapter.get('paragraphs', [])):
                        for lang, text in [('wenyan', paragraph.get('wenyan', '')), 
                                         ('baihua', paragraph.get('zh', '')), 
                                         ('english', paragraph.get('en', ''))]:
                            if query_lower in text.lower():
                                # 提取上下文
                                context_start = max(0, text.lower().find(query_lower) - 50)
                                context_end = min(len(text), text.lower().find(query_lower) + len(query) + 50)
                                context = text[context_start:context_end]
                                
                                matches.append({
                                    'type': 'content',
                                    'language': lang,
                                    'paragraph_id': idx + 1,
                                    'content': context,
                                    'highlight': highlight_text(context, query),
                                    'full_paragraph': paragraph
                                })
                
                if matches:
                    results.append({
                        'book': book,
                        'category': category, 
                        'chapter': chapter,
                        'matches': matches,
                        'relevance_score': len(matches)
                    })
    
    # 按相关度排序
    results.sort(key=lambda x: x['relevance_score'], reverse=True)
    return results

def get_statistics():
    """获取语料库统计信息"""
    stats = {
        'total_books': 0,
        'total_categories': 0,
        'total_chapters': 0,
        'total_paragraphs': 0,
        'books_detail': []
    }
    
    for book in BOOKS:
        book_stats = {
            'id': book['id'],
            'title': book['title'],
            'categories': len(book['categories']),
            'chapters': 0,
            'paragraphs': 0
        }
        
        for category in book['categories']:
            book_stats['chapters'] += len(category['chapters'])
            for chapter in category['chapters']:
                book_stats['paragraphs'] += len(chapter.get('paragraphs', []))
        
        stats['books_detail'].append(book_stats)
        stats['total_categories'] += book_stats['categories']
        stats['total_chapters'] += book_stats['chapters']
        stats['total_paragraphs'] += book_stats['paragraphs']
    
    stats['total_books'] = len(BOOKS)
    return stats

def parse_chapters_from_text(text):
    """Split text into chapters by lines starting with '## ' (markdown-like).
    Returns list of dicts: [{'title': title, 'content': content}, ...]
    If no chapter markers are found, treat whole file as single chapter with empty title.
    """
    lines = text.splitlines()
    chapters = []
    cur_title = ''
    cur_lines = []
    for line in lines:
        if line.startswith('## '):
            # flush previous
            if cur_lines or cur_title:
                chapters.append({'title': cur_title.strip(), 'content': '\n'.join(cur_lines).strip()})
            cur_title = line[3:].strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    # final flush
    if cur_lines or cur_title:
        chapters.append({'title': cur_title.strip(), 'content': '\n'.join(cur_lines).strip()})
    if not chapters:
        # whole text as single chapter
        return [{'title': '', 'content': text.strip()}]
    return chapters


def parse_three_parallel_file(file_path):
    """
    解析三平行格式的单个文件
    格式: 文言文\n白话文\n英文\n\n文言文\n白话文\n英文...
    返回: {'wenyan': str, 'zh': str, 'en': str, 'paragraphs': [{'wenyan': str, 'zh': str, 'en': str}, ...]}
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except FileNotFoundError:
        return {'wenyan': '', 'zh': '', 'en': '', 'paragraphs': []}
    
    if not content:
        return {'wenyan': '', 'zh': '', 'en': '', 'paragraphs': []}
    
    # 按双换行分割段落组
    paragraph_groups = content.split('\n\n')
    
    wenyan_parts = []
    zh_parts = []
    en_parts = []
    paragraphs = []  # 保持语义对应的段落组
    
    for group in paragraph_groups:
        lines = [line.strip() for line in group.split('\n') if line.strip()]
        
        if len(lines) >= 3:
            # 标准三平行格式
            wenyan = lines[0]
            zh = lines[1]
            en = lines[2]
            
            wenyan_parts.append(wenyan)
            zh_parts.append(zh)
            en_parts.append(en)
            paragraphs.append({'wenyan': wenyan, 'zh': zh, 'en': en})
            
        elif len(lines) == 2:
            # 可能缺少英文
            wenyan = lines[0]
            zh = lines[1]
            en = ""
            
            wenyan_parts.append(wenyan)
            zh_parts.append(zh)
            en_parts.append(en)
            paragraphs.append({'wenyan': wenyan, 'zh': zh, 'en': en})
            
        elif len(lines) == 1:
            # 只有一行，可能是标题或单独内容
            wenyan = lines[0]
            zh = ""
            en = ""
            
            wenyan_parts.append(wenyan)
            zh_parts.append(zh)
            en_parts.append(en)
            paragraphs.append({'wenyan': wenyan, 'zh': zh, 'en': en})
    
    return {
        'wenyan': '\n\n'.join(wenyan_parts),
        'zh': '\n\n'.join(zh_parts),
        'en': '\n\n'.join(en_parts),
        'paragraphs': paragraphs  # 新增：保持语义对应的段落组
    }

def load_books_from_raw():
    """
    扫描新的三级目录结构: data/raw/<book>/<category>/<chapter>.txt
    每个txt文件是三平行格式的单个章节
    返回: [{'id': book_id, 'title': book_title, 'categories': [{'id': cat_id, 'title': cat_title, 'chapters': [...]}]}]
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
        
        # 获取书籍配置
        book_config = book_configs.get(book_id, {"name": book_id, "categories": {}})
        book_title = book_config["name"]
        
        # 加载分类
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
    
    return books


# Load books once at startup (for prototype). Could be reloaded on demand.
BOOKS = load_books_from_raw()



def load_corpus():
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def search_corpus(query):
    if not query:
        return load_corpus()
    q = query.lower()
    results = []
    for entry in load_corpus():
        if q in (entry.get('title', '') or '').lower():
            results.append(entry)
            continue
        for k in ('text_1', 'text_2', 'text_3'):
            if q in (entry.get(k, '') or '').lower():
                results.append(entry)
                break
    return results


@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    selected_history = request.args.get('history', '')
    entries = search_corpus(q)
    if selected_history:
        entries = [e for e in entries if e.get('history') == selected_history]
    histories = sorted({e.get('history', '未分类') for e in load_corpus()})
    # Home: show site intro and book list
    stats = get_statistics()
    return render_template('home.html', books=BOOKS, stats=stats)


@app.route('/book/<book_id>/')
@app.route('/book/<book_id>')
def book_page(book_id):
    """显示书籍的分类列表"""
    for book in BOOKS:
        if book['id'] == book_id:
            return render_template('book.html', book=book, books=BOOKS)
    abort(404)


@app.route('/book/<book_id>/<category_id>/')
@app.route('/book/<book_id>/<category_id>')
def category_page(book_id, category_id):
    """显示分类的章节列表"""
    for book in BOOKS:
        if book['id'] == book_id:
            for category in book['categories']:
                if category['id'] == category_id:
                    return render_template('category.html', book=book, category=category, books=BOOKS)
    abort(404)


@app.route('/book/<book_id>/<category_id>/chapter/<int:chapter_id>/')
@app.route('/book/<book_id>/<category_id>/chapter/<int:chapter_id>')
def chapter_page(book_id, category_id, chapter_id):
    """显示具体章节的三平行内容"""
    for book in BOOKS:
        if book['id'] == book_id:
            for category in book['categories']:
                if category['id'] == category_id:
                    for chapter in category['chapters']:
                        if chapter['id'] == chapter_id:
                            # 计算前后章节链接
                            chapters = category['chapters']
                            chapter_idx = next(i for i, ch in enumerate(chapters) if ch['id'] == chapter_id)
                            
                            prev_url = None
                            next_url = None
                            if chapter_idx > 0:
                                prev_ch = chapters[chapter_idx - 1]
                                prev_url = f"/book/{book_id}/{category_id}/chapter/{prev_ch['id']}/"
                            if chapter_idx < len(chapters) - 1:
                                next_ch = chapters[chapter_idx + 1]
                                next_url = f"/book/{book_id}/{category_id}/chapter/{next_ch['id']}/"
                            
                            # 标准化章节数据格式，兼容模板
                            chapter_display = {
                                'id': chapter['id'], 
                                'title': chapter.get('title', ''), 
                                'wenyan': chapter.get('wenyan', ''), 
                                'z': chapter.get('zh', ''),  # 模板中使用 'z' 
                                'en': chapter.get('en', ''),
                                'paragraphs': chapter.get('paragraphs', [])  # 新增：段落组
                            }
                            
                            return render_template('chapter.html', 
                                                 book=book, 
                                                 category=category,
                                                 chapter=chapter_display, 
                                                 prev_url=prev_url, 
                                                 next_url=next_url,
                                                 books=BOOKS)
    abort(404)


@app.route('/search')
def search_page():
    query = request.args.get('q', '').strip()
    scope = request.args.get('scope', 'all')
    book_filter = request.args.get('book', None)
    
    results = []
    if query:
        results = search_in_books(query, scope, book_filter)
    
    return render_template('search.html', 
                         results=results, 
                         query=query, 
                         scope=scope,
                         book_filter=book_filter,
                         books=BOOKS)

@app.route('/api/search')
def api_search():
    """AJAX搜索API"""
    query = request.args.get('q', '').strip()
    scope = request.args.get('scope', 'all')
    book_filter = request.args.get('book', None)
    
    results = []
    if query:
        results = search_in_books(query, scope, book_filter)
    
    return jsonify({
        'results': results[:20],  # 限制结果数量
        'total': len(results),
        'query': query
    })

@app.route('/api/stats')
def api_stats():
    """API: 获取统计信息"""
    return jsonify(get_statistics())

@app.route('/entry/<entry_id>')
def entry(entry_id):
    for e in load_corpus():
        if str(e.get('id')) == str(entry_id):
            return render_template('entry.html', e=e)
    abort(404)


if __name__ == '__main__':
    # 适配 Vercel 的 PORT 环境变量，默认 fallback 到 5000（本地开发用）
    port = int(os.environ.get('PORT', 5000))
    # 生产环境强制关闭 debug（Vercel 要求）
    app.run(host='0.0.0.0', port=port, debug=False)

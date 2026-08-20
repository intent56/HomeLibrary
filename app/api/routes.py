# api.py

from flask import (Blueprint, 
                   request, 
                   jsonify, 
                   redirect,
                    flash,
                    url_for,)
import requests
import time
from app import db
from app.models.main import Book, Author, Interpreter, Genre, Publisher, Language, Cover, Format, Source, Aggregator
from sqlalchemy import or_
import urllib.parse


api = Blueprint('api', __name__, url_prefix='/api')

# Кэш для результатов поиска
search_cache = {}

@api.route('/sources')
def get_sources():
    """Получить список активных источников"""
    source_type = request.args.get('type', 'books')  # books, authors, interpreters
    sources = Source.query.filter_by(is_active=True).order_by(Source.name).all()
    
    # Фильтруем по типу
    if source_type == 'books':
        sources = [s for s in sources if s.chk_books]
    elif source_type == 'authors':
        sources = [s for s in sources if s.chk_authors]
    elif source_type == 'interpreters':
        sources = [s for s in sources if s.chk_interpreters]
    
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'code': s.code,
        'url': s.url,
        'chk_books': s.chk_books,
        'chk_authors': s.chk_authors,
        'chk_interpreters': s.chk_interpreters
    } for s in sources])

@api.route('/search')
def universal_search():
    """
    Универсальный поиск в интернете
    Параметры:
    - type: 'book', 'author', 'interpreter'
    - source_id: id источника (опционально)
    - query: поисковый запрос
    - isbn: ISBN (для книг)
    """
    search_type = request.args.get('type', 'book')
    source_id = request.args.get('source_id', type=int)
    query = request.args.get('query', '').strip()
    isbn = request.args.get('isbn', '').strip()
    
    if not query and not isbn:
        return jsonify({'error': 'Введите поисковый запрос или ISBN'}), 400
    
    # Получаем источник
    source = None
    if source_id:
        source = Source.query.get(source_id)
        if not source:
            return jsonify({'error': 'Источник не найден'}), 404
        if not source.is_active:
            return jsonify({'error': 'Источник неактивен'}), 400
        
        # Проверяем, подходит ли источник для данного типа поиска
        if search_type == 'book' and not source.chk_books:
            return jsonify({'error': f'Источник "{source.name}" не поддерживает поиск книг'}), 400
        elif search_type == 'author' and not source.chk_authors:
            return jsonify({'error': f'Источник "{source.name}" не поддерживает поиск авторов'}), 400
        elif search_type == 'interpreter' and not source.chk_interpreters:
            return jsonify({'error': f'Источник "{source.name}" не поддерживает поиск переводчиков'}), 400
    
    # Поиск в зависимости от типа
    if search_type == 'book':
        return search_books_universal(query, isbn, source)
    elif search_type == 'author':
        return search_authors_universal(query, source)
    elif search_type == 'interpreter':
        return search_interpreters_universal(query, source)
    else:
        return jsonify({'error': f'Неизвестный тип поиска: {search_type}'}), 400

@api.route('/search_google_books')
def search_google_books():
    """Поиск книги в Google Books по ISBN (прямой вызов)"""
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({'error': 'ISBN не предоставлен'}), 400
    
    return search_google_books_api(None, isbn)

@api.route('/search_google_books_by_title')
def search_google_books_by_title():
    """Поиск книги в Google Books по названию (прямой вызов)"""
    title = request.args.get('title')
    if not title:
        return jsonify({'error': 'Название не предоставлено'}), 400
    
    return search_google_books_api(title, None)

@api.route('/search_open_library')
def search_open_library():
    """Поиск в Open Library API (альтернативный источник)"""
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({'error': 'ISBN не предоставлен'}), 400
    
    return search_open_library_api(None, isbn)

def search_books_universal(query=None, isbn=None, source=None):
    """Универсальный поиск книг"""
    results = []
    
    # Если указан конкретный источник
    if source:
        if source.code == 'google_books' and source.chk_books:
            return search_google_books_api(query, isbn)
        elif source.code == 'open_library' and source.chk_books:
            return search_open_library_api(query, isbn)
        else:
            return jsonify({'error': f'Источник {source.name} не поддерживает поиск книг'}), 400
    
    # Поиск по всем активным источникам, поддерживающим поиск книг
    sources = Source.query.filter_by(is_active=True, chk_books=True).all()
    
    for src in sources:
        try:
            if src.code == 'google_books':
                result = search_google_books_api(query, isbn)
                if result and hasattr(result, 'json'):
                    data = result.json
                    if isinstance(data, list) and data:
                        results.extend([{**item, 'source': src.name} for item in data])
                    elif isinstance(data, dict) and data.get('title'):
                        results.append({**data, 'source': src.name})
            elif src.code == 'open_library':
                result = search_open_library_api(query, isbn)
                if result and hasattr(result, 'json'):
                    data = result.json
                    if isinstance(data, list) and data:
                        results.extend([{**item, 'source': src.name} for item in data])
                    elif isinstance(data, dict) and data.get('title'):
                        results.append({**data, 'source': src.name})
        except Exception as e:
            print(f"Error in {src.name}: {e}")
    
    if not results:
        return jsonify({'error': 'Книги не найдены'}), 404
    
    return jsonify(results)

def search_authors_universal(query, source=None):
    """Универсальный поиск авторов"""
    results = []
    
    # Если указан конкретный источник
    if source:
        if source.code == 'google_books' and source.chk_authors:
            return search_author_google_books(query)
        elif source.code == 'open_library' and source.chk_authors:
            return search_author_open_library(query)
        else:
            return jsonify({'error': f'Источник {source.name} не поддерживает поиск авторов'}), 400
    
    # Поиск по всем активным источникам, поддерживающим поиск авторов
    sources = Source.query.filter_by(is_active=True, chk_authors=True).all()
    
    for src in sources:
        try:
            if src.code == 'google_books':
                result = search_author_google_books(query)
                if result and hasattr(result, 'json'):
                    data = result.json
                    if data:
                        results.extend([{**item, 'source': src.name} for item in data])
            elif src.code == 'open_library':
                result = search_author_open_library(query)
                if result and hasattr(result, 'json'):
                    data = result.json
                    if data:
                        results.extend([{**item, 'source': src.name} for item in data])
        except Exception as e:
            print(f"Error in {src.name}: {e}")
    
    if not results:
        return jsonify({'error': 'Авторы не найдены'}), 404
    
    return jsonify(results)

def search_interpreters_universal(query, source=None):
    """Универсальный поиск переводчиков"""
    results = []
    
    # Если указан конкретный источник
    if source:
        if source.code == 'google_books' and source.chk_interpreters:
            return search_interpreter_google_books(query)
        else:
            return jsonify({'error': f'Источник {source.name} не поддерживает поиск переводчиков'}), 400
    
    # Поиск по всем активным источникам, поддерживающим поиск переводчиков
    sources = Source.query.filter_by(is_active=True, chk_interpreters=True).all()
    
    for src in sources:
        try:
            if src.code == 'google_books':
                result = search_interpreter_google_books(query)
                if result:
                    results.extend([{**item, 'source': src.name} for item in result])
        except Exception as e:
            print(f"Error in {src.name}: {e}")
    
    if not results:
        return jsonify({'error': 'Переводчики не найдены'}), 404
    
    return jsonify(results)

def search_google_books_api(query=None, isbn=None):
    """Поиск в Google Books API"""
    # Проверка кэша
    cache_key = None
    if isbn:
        clean_isbn = isbn.replace('-', '').replace(' ', '')
        cache_key = f'isbn_{clean_isbn}'
        if cache_key in search_cache:
            return jsonify(search_cache[cache_key])
    
    # Добавляем задержку для соблюдения лимитов API
    time.sleep(0.5)
    
    # Формируем запрос
    if isbn:
        clean_isbn = isbn.replace('-', '').replace(' ', '')
        url = f'https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}'
    elif query:
        encoded_title = urllib.parse.quote(query)
        url = f'https://www.googleapis.com/books/v1/volumes?q=intitle:{encoded_title}&maxResults=5'
    else:
        return jsonify({'error': 'Не указан ISBN или название'}), 400
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 429:
            return jsonify({
                'error': 'Превышен лимит запросов к Google Books. Попробуйте позже.'
            }), 429
        
        response.raise_for_status()
        data = response.json()
        
        if data.get('totalItems', 0) == 0:
            return jsonify({'error': 'Книга не найдена'}), 404
        
        # Если это поиск по ISBN (один результат)
        if isbn:
            volume_info = data['items'][0]['volumeInfo']
            book_data = {
                'title': volume_info.get('title'),
                'subtitle': volume_info.get('subtitle'),
                'authors': ', '.join(volume_info.get('authors', [])),
                'publisher': volume_info.get('publisher'),
                'published_date': volume_info.get('publishedDate'),
                'description': volume_info.get('description'),
                'page_count': volume_info.get('pageCount'),
                'categories': ', '.join(volume_info.get('categories', [])),
                'cover_image': volume_info.get('imageLinks', {}).get('thumbnail') if 'imageLinks' in volume_info else None,
                'language': volume_info.get('language'),
                'isbn': clean_isbn
            }
            
            # Сохраняем в кэш
            if cache_key:
                search_cache[cache_key] = book_data
            return jsonify(book_data)
        
        # Если это поиск по названию (список результатов)
        results = []
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            
            # Извлекаем ISBN из идентификаторов
            book_isbn = None
            for identifier in volume_info.get('industryIdentifiers', []):
                if identifier.get('type') == 'ISBN_13':
                    book_isbn = identifier.get('identifier')
                    break
                elif identifier.get('type') == 'ISBN_10' and not book_isbn:
                    book_isbn = identifier.get('identifier')
            
            results.append({
                'title': volume_info.get('title'),
                'subtitle': volume_info.get('subtitle'),
                'authors': ', '.join(volume_info.get('authors', [])),
                'publisher': volume_info.get('publisher'),
                'published_date': volume_info.get('publishedDate'),
                'description': volume_info.get('description'),
                'page_count': volume_info.get('pageCount'),
                'categories': ', '.join(volume_info.get('categories', [])),
                'cover_image': volume_info.get('imageLinks', {}).get('thumbnail') if 'imageLinks' in volume_info else None,
                'language': volume_info.get('language'),
                'isbn': book_isbn
            })
        
        return jsonify(results)
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Превышено время ожидания ответа от Google Books'}), 504
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return jsonify({'error': 'Превышен лимит запросов к Google Books'}), 429
        return jsonify({'error': f'Ошибка HTTP: {str(e)}'}), e.response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Google Books API: {e}")
        return jsonify({'error': 'Не удалось получить данные от Google Books'}), 500

def search_open_library_api(query=None, isbn=None):
    """Поиск в Open Library API"""
    try:
        # Поиск по ISBN
        if isbn:
            clean_isbn = isbn.replace('-', '').replace(' ', '')
            url = f'https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data'
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return jsonify({'error': 'Ошибка запроса к Open Library'}), response.status_code
                
            data = response.json()
            key = f'ISBN:{clean_isbn}'
            if key not in data:
                return jsonify({'error': 'Книга не найдена в Open Library'}), 404
                
            book_data = data[key]
            return jsonify({
                'title': book_data.get('title'),
                'subtitle': book_data.get('subtitle'),
                'authors': ', '.join([a.get('name', '') for a in book_data.get('authors', [])]),
                'publisher': book_data.get('publishers', [{}])[0].get('name') if book_data.get('publishers') else None,
                'published_date': book_data.get('publish_date'),
                'description': book_data.get('notes'),
                'page_count': book_data.get('number_of_pages'),
                'cover_image': f'https://covers.openlibrary.org/b/isbn/{clean_isbn}-M.jpg',
                'isbn': clean_isbn
            })
        
        # Поиск по названию
        elif query:
            encoded_title = urllib.parse.quote(query)
            url = f'https://openlibrary.org/search.json?title={encoded_title}&limit=5'
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return jsonify({'error': 'Ошибка запроса к Open Library'}), response.status_code
                
            data = response.json()
            results = []
            
            for doc in data.get('docs', [])[:5]:
                isbn_list = doc.get('isbn', [])
                book_isbn = isbn_list[0] if isbn_list else None
                author_names = doc.get('author_name', [])
                authors = ', '.join(author_names) if author_names else None
                
                results.append({
                    'title': doc.get('title'),
                    'subtitle': doc.get('subtitle'),
                    'authors': authors,
                    'publisher': doc.get('publisher', [None])[0] if doc.get('publisher') else None,
                    'published_date': str(doc.get('first_publish_year')) if doc.get('first_publish_year') else None,
                    'description': None,
                    'page_count': doc.get('number_of_pages_median'),
                    'cover_image': f'https://covers.openlibrary.org/b/isbn/{book_isbn}-M.jpg' if book_isbn else None,
                    'isbn': book_isbn
                })
            
            if not results:
                return jsonify({'error': 'Книги не найдены в Open Library'}), 404
                
            return jsonify(results)
        
        else:
            return jsonify({'error': 'Не указан ISBN или название'}), 400
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Open Library: {e}")
        return jsonify({'error': 'Не удалось получить данные от Open Library'}), 500

def search_author_google_books(name):
    """Поиск автора в Google Books"""
    try:
        encoded_name = urllib.parse.quote(name)
        url = f'https://www.googleapis.com/books/v1/volumes?q=inauthor:{encoded_name}&maxResults=10'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return jsonify([])
        
        data = response.json()
        authors = []
        seen = set()
        
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            for author_name in volume_info.get('authors', []):
                if author_name not in seen:
                    seen.add(author_name)
                    parts = author_name.split(' ')
                    authors.append({
                        'name': author_name,
                        'lastname': parts[0] if parts else author_name,
                        'firstname': ' '.join(parts[1:]) if len(parts) > 1 else '',
                        'source': 'Google Books',
                        'source_id': 'google_books',
                        'books_count': 0
                    })
        
        return jsonify(authors)
        
    except Exception as e:
        print(f"Ошибка поиска автора в Google Books: {e}")
        return jsonify([])

def search_author_open_library(name):
    """Поиск автора в Open Library"""
    try:
        encoded_name = urllib.parse.quote(name)
        url = f'https://openlibrary.org/search/authors.json?q={encoded_name}&limit=10'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return jsonify([])
        
        data = response.json()
        authors = []
        
        for doc in data.get('docs', []):
            author_name = doc.get('name', '')
            if not author_name:
                continue
            
            parts = author_name.split(' ')
            authors.append({
                'name': author_name,
                'lastname': parts[0] if parts else author_name,
                'firstname': ' '.join(parts[1:]) if len(parts) > 1 else '',
                'source': 'Open Library',
                'source_id': 'open_library',
                'books_count': doc.get('work_count', 0),
                'birth_date': doc.get('birth_date'),
                'death_date': doc.get('death_date'),
                'top_subjects': doc.get('top_subjects', [])[:3] if doc.get('top_subjects') else []
            })
        
        return jsonify(authors)
        
    except Exception as e:
        print(f"Ошибка поиска автора в Open Library: {e}")
        return jsonify([])

def search_interpreter_google_books(name):
    """Поиск переводчика в Google Books"""
    try:
        encoded_name = urllib.parse.quote(name)
        url = f'https://www.googleapis.com/books/v1/volumes?q={encoded_name}&maxResults=10'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        interpreters = []
        seen = set()
        
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            description = volume_info.get('description', '')
            
            if 'перевод' in description.lower() or 'translation' in description.lower():
                words = description.split()
                for i, word in enumerate(words):
                    if word.lower() in ['перевод', 'translation', 'translator', 'переводчик']:
                        if i + 1 < len(words):
                            potential_name = ' '.join(words[i+1:i+4])
                            if potential_name not in seen and len(potential_name) > 3:
                                seen.add(potential_name)
                                parts = potential_name.split(' ')
                                interpreters.append({
                                    'name': potential_name,
                                    'lastname': parts[0] if parts else potential_name,
                                    'firstname': ' '.join(parts[1:]) if len(parts) > 1 else '',
                                    'source': 'Google Books',
                                    'source_id': 'google_books',
                                    'book': volume_info.get('title')
                                })
        
        return interpreters
        
    except Exception as e:
        print(f"Ошибка поиска переводчика в Google Books: {e}")
        return []

@api.route('/autocomplete/authors')
def autocomplete_authors():
    """Автодополнение для поиска авторов"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    authors = Author.query.filter(
        Author.fio.ilike(f'%{query}%')
    ).limit(10).all()
    
    return jsonify([{
        'id': a.id,
        'text': a.fio
    } for a in authors])

@api.route('/autocomplete/publishers')
def autocomplete_publishers():
    """Автодополнение для поиска издателей"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    publishers = Publisher.query.filter(
        Publisher.name.ilike(f'%{query}%')
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'text': p.name
    } for p in publishers])

@api.route('/autocomplete/genres')
def autocomplete_genres():
    """Автодополнение для поиска жанров"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    genres = Genre.query.filter(
        Genre.name.ilike(f'%{query}%')
    ).limit(10).all()
    
    return jsonify([{
        'id': g.id,
        'text': g.name
    } for g in genres])

@api.route('/autocomplete/languages')
def autocomplete_languages():
    """Автодополнение для поиска языков"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    languages = Language.query.filter(
        or_(
            Language.name.ilike(f'%{query}%'),
            Language.code.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': l.id,
        'text': f'{l.name} ({l.code})'
    } for l in languages])

@api.route('/test')
def test():
    """Тестовый маршрут для проверки работы API"""
    return jsonify({
        'status': 'API работает',
        'endpoints': [
            '/api/sources',
            '/api/search',
            '/api/search_google_books',
            '/api/search_google_books_by_title',
            '/api/search_open_library',
            '/api/autocomplete/authors',
            '/api/autocomplete/publishers',
            '/api/autocomplete/genres',
            '/api/autocomplete/languages'
        ]
    })


@api.route('/aggregators')
def get_aggregators():
    """Получить список активных агрегаторов"""
    aggregators = Aggregator.query.filter_by(is_active=True).order_by(Aggregator.name).all()
    return jsonify([{
        'id': a.id,
        'name': a.name,
        'code': a.code,
        'url_template': a.url_template,
        'icon': a.icon or 'bi-box-seam',
        'search_type': a.search_type or 'standard'
    } for a in aggregators])

import io
from datetime import datetime
import requests
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging
import urllib.parse
import base64
from flask import (
    render_template,
    url_for,
    current_app,
    request,
    redirect,
    send_from_directory,
    send_file,
    flash,
    jsonify,
    session,
)
from app.extensions import db
from app.models.main import (
    Book,
    Author,
    Genre,
    Cover,
    Publisher,
    Format,
    Language,
    Interpreter,
    book_genres,
    book_authors,
    book_interpreters,
    book_publishers,
    interpreter_languages,
    Source,
    Aggregator,
)
from app.main.forms import (
    FormAuthor,
    FormInterpreter,
    FormPublisher,
    FormFormat,
    FormGenre,
    FormCover,
    FormLanguage,
    FormBook,
    FormSource,
    FormAggregator,
)
from app.main import bp

from app.main.misc import get_html
from config import Config
# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@bp.route("/")
def init():
    return render_template("initial.html")


@bp.route('/index/')
def index():
    total_books = Book.query.count()

    return render_template('index.html',
                           total_books=total_books)


@bp.route('/book/add', methods=['GET', 'POST'])
def add_book():
    form = FormBook()

    # Заполняем choices для SelectField ПЕРЕД рендерингом
    form.id_cover.choices = [(0, 'Не указан')] + [(
        c.id, f'{c.code} - {c.name}') for c in Cover.query.order_by(Cover.name).all()]
    form.id_language.choices = [(0, 'Не указан')] + [(
        l.id, f'{l.code} - {l.name}') for l in Language.query.order_by(Language.name).all()]
    form.id_format.choices = [
        (0, 'Не указан')] + [(f.id, f'{f.format}') for f in Format.query.order_by(Format.format).all()]

    if form.validate_on_submit():
        try:
            book = Book()
            # Сбрасываем FileField перед populate_obj
            form.cover.data = None
            form.populate_obj(book)

            if book.id_cover == 0:
                book.id_cover = None
            if book.id_format == 0:
                book.id_format = None

            # Обработка загрузки обложки:
            # при добавлении новой книги, если файл не выбран — book.cover = None
            if 'cover' in request.files:
                file = request.files['cover']
                if file and file.filename:
                    book.cover = file.read()
                else:
                    book.cover = None

            db.session.add(book)
            db.session.commit()

            flash('Книга успешно добавлена!', 'success')
            return redirect(url_for('authors.select_authors', book_id=book.id))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении книги: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Неожиданная ошибка: {str(e)}', 'danger')

    return render_template('add_book.html', form=form)


@bp.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    form = FormBook(obj=book)

    # === ЗАПОЛНЯЕМ CHOICES ДЛЯ SELECT-ПОЛЕЙ ПЕРЕД РЕНДЕРИНГОМ ===
    form.id_cover.choices = [(0, 'Не указан')] + [
        (c.id, f'{c.code} - {c.name}')
        for c in Cover.query.order_by(Cover.name).all()
    ]
    form.id_language.choices = [(0, 'Не указан')] + [
        (l.id, f'{l.code} - {l.name}')
        for l in Language.query.order_by(Language.name).all()
    ]
    form.id_format.choices = [(0, 'Не указан')] + [
        (f.id, f'{f.format}')
        for f in Format.query.order_by(Format.format).all()
    ]

    if form.validate_on_submit():
        try:
            current_cover = book.cover           # ← снимок из БД
            form.cover.data = None               # ← защита от FileStorage
            form.populate_obj(book)

            if book.id_cover == 0:
                book.id_cover = None
            if book.id_format == 0:
                book.id_format = None

            new_file = request.files.get('cover')
            if new_file and new_file.filename:
                book.cover = new_file.read()
            else:
                book.cover = current_cover       # ← сохраняем существующую обложку

            db.session.commit()
            flash('Книга успешно обновлена!', 'success')
            return redirect(url_for('main.book_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении книги: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Неожиданная ошибка: {str(e)}', 'danger')

    return render_template('edit_book.html', form=form, book=book)


@bp.route('/books')
def book_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    author_search = request.args.get('author_search', '').strip()
    interpreter_search = request.args.get('interpreter_search', '').strip()
    genre_search = request.args.get('genre_search', '').strip()

    # Всего книг в БД — не зависит от поиска
    total_books = Book.query.count()

    # Базовый запрос
    query = Book.query

    # Поиск по названию
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(Book.name.ilike(search_pattern))

    # Поиск по автору
    if author_search:
        author_pattern = f'%{author_search}%'
        query = query.filter(Book.author_books.any(
            Author.lastname.ilike(author_pattern)))

    # Поиск по переводчику
    if interpreter_search:
        interpreter_pattern = f'%{interpreter_search}%'
        query = query.filter(Book.interpreter_books.any(
            Interpreter.lastname.ilike(interpreter_pattern)))

    # Поиск по жанру
    if genre_search:
        genre_pattern = f'%{genre_search}%'
        query = query.filter(
            Book.genre_books.any(
                Genre.name.ilike(genre_pattern)
            )
        )

    # Сортировка по названию книги
    query = query.order_by(Book.name.asc())

    # Пагинация
    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    context = dict(
        books=pagination.items,
        pagination=pagination,
        total_books=total_books,
        search=search,
        author_search=author_search,
        interpreter_search=interpreter_search,
        genre_search=genre_search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/book_table.html', **context)

    return render_template('book_list.html', **context)


@bp.route('/book/<int:book_id>/delete', methods=['POST'])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    try:
        db.session.delete(book)
        db.session.commit()
        flash('Книга успешно удалена!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении книги: {str(e)}', 'danger')

    # Получаем параметры для возврата на ту же страницу
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')

    return redirect(url_for('main.book_list',
                            page=page,
                            search=search,
                            author_search=author_search,
                            interpreter_search=interpreter_search,
                            genre_search=genre_search))


@bp.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')
    return_page = request.args.get('return_page', page, type=int)

    return render_template('book_detail.html',
                           book=book,
                           page=page,
                           search=search,
                           author_search=author_search,
                           interpreter_search=interpreter_search,
                           genre_search=genre_search,
                           return_page=return_page)


@bp.route('/book/<int:book_id>/view')
def book_view(book_id):
    book = Book.query.get_or_404(book_id)
    # Получаем параметры для возврата
    id = request.args.get('id', 1, type=int)
    page1 = request.args.get('page1', 1, type=int)
    return_search = request.args.get('return_search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_to = request.args.get('return_to', '')

    return render_template('book_detail_view.html',
                           book=book,
                           id=id,
                           page1=page1,
                           return_search=return_search,
                           return_page=return_page,
                           return_to=return_to)


@bp.route('/languages')
def language_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Всего языков в БД — не зависит от поиска
    total_languages = Language.query.count()

    query = Language.query

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            or_(
                Language.name.ilike(search_pattern),
                Language.code.ilike(search_pattern)
            )
        )

    query = query.order_by(Language.name)

    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_LANGUAGE,
        error_out=False
    )

    context = dict(
        languages=pagination.items,
        pagination=pagination,
        total_languages=total_languages,
        search=search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/language_grid.html', **context)

    return render_template('language_list.html', **context)


@bp.route('/language/<int:language_id>/card')
def language_card(language_id):
    language = Language.query.get_or_404(language_id)
    page_books = request.args.get('page_books', 1, type=int)
    page_interpreters = request.args.get('page_interpreters', 1, type=int)

    # Получаем параметры для возврата
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Пагинация для книг на этом языке
    books_query = Book.query.filter_by(
        id_language=language_id).order_by(Book.name.asc())
    pagination_books = books_query.paginate(
        page=page_books,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    # Пагинация для переводчиков с этого языка
    # Используем связь interpreter_langs для получения списка переводчиков
    interpreters_query = language.interpreter_langs
    # Применяем пагинацию к списку, полученному из relationship
    # Для этого используем метод .paginate() на самом запросе, но relationship
    # возвращает список, а не запрос. Поэтому нужно построить запрос заново.
    interpreters_query = Interpreter.query.join(interpreter_languages).filter(
        interpreter_languages.c.id_language == language_id
    ).order_by(Interpreter.fio.asc())

    pagination_interpreters = interpreters_query.paginate(
        page=page_interpreters,
        per_page=Config.ITEMS_PER_PAGE_INTERPRETER,
        error_out=False
    )

    return render_template('language_card.html',
                           language=language,
                           pagination_books=pagination_books,
                           pagination_interpreters=pagination_interpreters,
                           page_books=page_books,
                           page_interpreters=page_interpreters,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/language/<int:language_id>/view')
def language_view(language_id):
    language = Language.query.get_or_404(language_id)
    page_books = request.args.get('page_books', 1, type=int)
    page_interpreters = request.args.get('page_interpreters', 1, type=int)

    # Получаем параметры для возврата
    return_to = request.args.get('return_to')
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Пагинация для книг на этом языке
    books_query = Book.query.filter_by(
        id_language=language_id).order_by(Book.name.asc())
    pagination_books = books_query.paginate(
        page=page_books,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    # Пагинация для переводчиков с этого языка
    # Используем связь interpreter_langs для получения списка переводчиков
    interpreters_query = language.interpreter_langs
    # Применяем пагинацию к списку, полученному из relationship
    # Для этого используем метод .paginate() на самом запросе, но relationship
    # возвращает список, а не запрос. Поэтому нужно построить запрос заново.
    interpreters_query = Interpreter.query.join(interpreter_languages).filter(
        interpreter_languages.c.id_language == language_id
    ).order_by(Interpreter.fio.asc())

    pagination_interpreters = interpreters_query.paginate(
        page=page_interpreters,
        per_page=Config.ITEMS_PER_PAGE_INTERPRETER,
        error_out=False
    )

    return render_template('language_card_view.html',
                           language=language,
                           pagination_books=pagination_books,
                           pagination_interpreters=pagination_interpreters,
                           page_books=page_books,
                           page_interpreters=page_interpreters,
                           search=search,
                           return_page=return_page,
                           return_search=return_search,
                           return_to=return_to)


@bp.route('/language/<int:language_id>/edit', methods=['GET', 'POST'])
def edit_language(language_id):
    language = Language.query.get_or_404(language_id)
    form = FormLanguage(obj=language)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    books_query = Book.query.filter(
        Book.id_language == language_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(language)
            db.session.commit()
            flash('Язык успешно обновлен!', 'success')
            return redirect(url_for('main.language_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении языка: {str(e)}', 'danger')

    return render_template('edit_language.html',
                           form=form,
                           language=language,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/language/<int:language_id>/delete', methods=['POST'])
def delete_language(language_id):
    language = Language.query.get_or_404(language_id)
    try:
        db.session.delete(language)
        db.session.commit()
        flash('Язык успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении языка: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('main.language_list', page=page))


@bp.route('/book/<int:book_id>/languages', methods=['GET'])
def select_languages(book_id):
    book = Book.query.get_or_404(book_id)
    selected_languages = book.language_books
    return render_template('select_languages.html', book=book, selected_languages=selected_languages)


@bp.route('/book/<int:book_id>/languages/add', methods=['POST'])
def add_language_to_book(book_id):
    book = Book.query.get_or_404(book_id)
    language_id = request.form.get('language_id', type=int)

    if language_id:
        language = Language.query.get(language_id)
        if language and language not in book.language_books:
            book.language_books.append(language)
            db.session.commit()
            flash(f'Язык {language.name} добавлен к книге', 'success')

    return redirect(url_for('main.select_languages', book_id=book_id))


@bp.route('/book/<int:book_id>/languages/remove/<int:language_id>', methods=['POST'])
def remove_language_from_book(book_id, language_id):
    book = Book.query.get_or_404(book_id)
    language = Language.query.get_or_404(language_id)

    if language in book.language_books:
        book.language_books.remove(language)
        db.session.commit()
        flash(f'Язык {language.name} удален из книги', 'info')

    return redirect(url_for('main.select_languages', book_id=book_id))


@bp.route('/language/add', methods=['GET', 'POST'])
def add_language():
    form = FormLanguage()

    if form.validate_on_submit():
        try:
            language = Language()
            form.populate_obj(language)

            db.session.add(language)
            db.session.commit()

            flash('Язык успешно добавлен!', 'success')
            # Возврат: в выбор переводчиков для книги — только если book_id валиден
            book_id = request.args.get('book_id', type=int)
            if book_id:
                book = Book.query.get(book_id)
                if book:
                    return redirect(url_for(
                        'main.select_languages', book_id=book_id))
            # Иначе — в общий список языков
            return redirect(url_for('main.language_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении языка: {str(e)}', 'danger')

    return render_template('add_language.html', form=form, book_id=request.args.get('book_id', 0))


@bp.route('/search/languages')
def search_languages():
    query = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', 0, type=int)

    if len(query) < 2:
        return render_template('search_languages.html', languages=[], book_id=book_id)

    languages = Language.query.filter(
        or_(
            Language.name.ilike(f'%{query}%'),
            Language.code.ilike(f'%{query}%')
        )
    ).limit(10).all()

    if request.headers.get('HX-Request'):
        return render_template('search_languages.html', languages=languages, book_id=book_id)
    else:
        return jsonify([{
            'id': l.id,
            'code': l.code,
            'name': l.name
        } for l in languages])


@bp.route('/interpreter/<int:interpreter_id>/languages', methods=['GET'])
def select_interpreter_languages(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    selected_languages = interpreter.lang_interpreters
    return render_template('select_interpreter_languages.html',
                           interpreter=interpreter,
                           selected_languages=selected_languages)


@bp.route('/interpreter/<int:interpreter_id>/languages/add', methods=['POST'])
def add_language_to_interpreter(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    language_id = request.form.get('language_id', type=int)

    if language_id:
        language = Language.query.get(language_id)
        if language and language not in interpreter.lang_interpreters:
            interpreter.lang_interpreters.append(language)
            db.session.commit()
            flash(f'Язык {language.name} добавлен переводчику', 'success')

    return redirect(url_for('main.select_interpreter_languages', interpreter_id=interpreter_id))


@bp.route('/interpreter/<int:interpreter_id>/languages/remove/<int:language_id>', methods=['POST'])
def remove_language_from_interpreter(interpreter_id, language_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    language = Language.query.get_or_404(language_id)

    if language in interpreter.lang_interpreters:
        interpreter.lang_interpreters.remove(language)
        db.session.commit()
        flash(f'Язык {language.name} удален у переводчика', 'info')

    return redirect(url_for('main.select_interpreter_languages', interpreter_id=interpreter_id))


@bp.route('/search/interpreter_languages')
def search_interpreter_languages():
    query = request.args.get('q', '').strip()
    interpreter_id = request.args.get('interpreter_id', 0, type=int)

    if len(query) < 2:
        return render_template('search_interpreter_languages.html', languages=[], interpreter_id=interpreter_id)

    # Исключаем уже добавленные языки
    interpreter = Interpreter.query.get(interpreter_id)
    existing_ids = [
        lang.id for lang in interpreter.lang_interpreters] if interpreter else []

    languages = Language.query.filter(
        or_(
            Language.name.ilike(f'%{query}%'),
            Language.code.ilike(f'%{query}%')
        )
    ).filter(~Language.id.in_(existing_ids)).limit(10).all()

    if request.headers.get('HX-Request'):
        return render_template('search_interpreter_languages.html',
                               languages=languages,
                               interpreter_id=interpreter_id)
    else:
        return jsonify([{
            'id': l.id,
            'code': l.code,
            'name': l.name
        } for l in languages])


@bp.route('/sources')
def source_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Базовый запрос
    query = Source.query

    # Поиск по названию или коду
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            or_(
                Source.name.ilike(search_pattern),
                Source.code.ilike(search_pattern)
            )
        )

    # Сортировка по названию
    query = query.order_by(Source.name)

    # Пагинация
    pagination = query.paginate(
        page=page,
        # Убедитесь, что эта константа определена в config.py
        per_page=Config.ITEMS_PER_PAGE_SOURCE,
        error_out=False
    )

    # Проверяем, является ли запрос HTMX
    if request.headers.get('HX-Request'):
        return render_template('partials/source_table.html',
                               sources=pagination.items,
                               pagination=pagination,
                               total_sources=query.count(),
                               search=search)

    return render_template('source_list.html',
                           sources=pagination.items,
                           pagination=pagination,
                           total_sources=query.count(),
                           search=search)


@bp.route('/source/<int:source_id>/toggle-htmx', methods=['POST'])
def toggle_source_htmx(source_id):
    """HTMX-версия переключения статуса источника"""
    source = Source.query.get_or_404(source_id)
    try:
        source.is_active = not source.is_active
        db.session.commit()

        # Возвращаем только обновленный статус
        if source.is_active:
            return '<span class="badge bg-success">Активен</span>'
        else:
            return '<span class="badge bg-danger">Неактивен</span>'
    except SQLAlchemyError as e:
        db.session.rollback()
        return '<span class="badge bg-danger">Ошибка</span>', 500


@bp.route('/source/<int:source_id>/delete-htmx', methods=['DELETE'])
def delete_source_htmx(source_id):
    """HTMX-версия удаления источника"""
    source = Source.query.get_or_404(source_id)
    try:
        db.session.delete(source)
        db.session.commit()
        return '', 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return f'<div class="alert alert-danger">Ошибка при удалении: {str(e)}</div>', 500


@bp.route('/source/add', methods=['GET', 'POST'])
def add_source():
    form = FormSource()
    if form.validate_on_submit():
        try:
            source = Source()
            form.populate_obj(source)
            source.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.session.add(source)
            db.session.commit()
            flash('Источник успешно добавлен!', 'success')
            return redirect(url_for('main.source_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении источника: {str(e)}', 'danger')

    return render_template('add_source.html', form=form)


@bp.route('/source/<int:source_id>/edit', methods=['GET', 'POST'])
def edit_source(source_id):
    source = Source.query.get_or_404(source_id)
    form = FormSource(obj=source)

    if form.validate_on_submit():
        try:
            form.populate_obj(source)
            db.session.commit()
            flash('Источник успешно обновлен!', 'success')
            return redirect(url_for('main.source_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении источника: {str(e)}', 'danger')

    return render_template('edit_source.html', form=form, source=source)


@bp.route('/init_db')
def init_db():
    """Инициализация справочников"""

    # Добавляем начальные источники
    sources_data = [
        {
            'name': 'Google Books',
            'code': 'google_books',
            'url': 'https://www.googleapis.com/books/v1/',
            'is_active': True,
            'chk_books': True,
            'chk_authors': True,
            'chk_interpreters': True,
            'comment': 'API Google Books для поиска книг, авторов и переводчиков'
        },
        {
            'name': 'Open Library',
            'code': 'open_library',
            'url': 'https://openlibrary.org/',
            'is_active': True,
            'chk_books': True,
            'chk_authors': True,
            'chk_interpreters': False,
            'comment': 'Открытая библиотека для поиска книг и авторов'
        },
        {
            'name': 'WorldCat',
            'code': 'worldcat',
            'url': 'https://www.worldcat.org/',
            'is_active': False,
            'chk_books': True,
            'chk_authors': False,
            'chk_interpreters': False,
            'comment': 'Глобальный каталог библиотек (требуется API-ключ)'
        },
        {
            'name': 'ISBNdb',
            'code': 'isbndb',
            'url': 'https://isbndb.com/',
            'is_active': False,
            'chk_books': True,
            'chk_authors': False,
            'chk_interpreters': False,
            'comment': 'База данных книг по ISBN (требуется API-ключ)'
        }
    ]

    for data in sources_data:
        if not Source.query.filter_by(code=data['code']).first():
            source = Source(
                name=data['name'],
                code=data['code'],
                url=data['url'],
                is_active=data['is_active'],
                chk_books=data['chk_books'],
                chk_authors=data['chk_authors'],
                chk_interpreters=data['chk_interpreters'],
                comment=data['comment'],
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            db.session.add(source)

    # Добавляем начальные агрегаторы
    aggregators_data = [
        {
            'name': 'Ozon',
            'code': 'ozon',
            'url_template': 'https://www.ozon.ru/search/?text={query}',
            'icon': 'bi-bag',
            'search_type': 'standard',
            'comment': 'Маркетплейс Ozon'
        },
        {
            'name': 'Wildberries',
            'code': 'wildberries',
            'url_template': 'https://www.wildberries.ru/catalog/0/search.aspx?search={query}',
            'icon': 'bi-basket',
            'search_type': 'standard',
            'comment': 'Маркетплейс Wildberries'
        },
        {
            'name': 'Лабиринт',
            'code': 'labirint',
            'url_template': 'https://www.labirint.ru/search/{query}/',
            'icon': 'bi-compass',
            'search_type': 'standard',
            'comment': 'Книжный интернет-магазин Лабиринт'
        },
        {
            'name': 'Book24',
            'code': 'book24',
            'url_template': 'https://book24.ru/search/?q={query}',
            'icon': 'bi-book',
            'search_type': 'standard',
            'comment': 'Книжный интернет-магазин Book24'
        },
        {
            'name': 'Alib.ru',
            'code': 'alib_ru',
            'url_template': 'https://www.alib.ru/find3.php4?tfind={query}',
            'icon': 'bi-box-seam',
            'search_type': 'redirect',
            'comment': 'Агрегатор объявлений букинистических магазинов (специальная обработка)'
        }
    ]

    for data in aggregators_data:
        if not Aggregator.query.filter_by(code=data['code']).first():
            aggregator = Aggregator(
                name=data['name'],
                code=data['code'],
                url_template=data['url_template'],
                icon=data['icon'],
                comment=data['comment'],
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        db.session.add(aggregator)

    db.session.commit()
    flash('Справочники успешно инициализированы!', 'success')
    return redirect(url_for('main.index'))


@bp.route('/aggregators')
def aggregator_list():
    # 1. Получаем номер страницы из URL (по умолчанию 1)
    page = request.args.get('page', 1, type=int)

    # 2. Базовый запрос к БД с сортировкой
    query = Aggregator.query.order_by(Aggregator.name.asc())

    # 3. ПАГИНАЦИЯ
    pagination = query.paginate(
        page=page,
        # Сколько записей на одной странице (можно вынести в config)
        per_page=Config.ITEMS_PER_PAGE_AGGREGATOR,
        error_out=False
    )

    # 4. Получаем записи для текущей страницы
    aggregators = pagination.items

    # 7. Если это HTMX-запрос, возвращаем только таблицу
    if request.headers.get('HX-Request'):
        return render_template(
            'partials/aggregator_table.html',
            aggregators=aggregators,
            pagination=pagination,
        )

    # 8. Обычный запрос — отдаём полную страницу
    return render_template(
        'aggregator_list.html',
        aggregators=aggregators,
        pagination=pagination,
        total_aggregators=query.count()
    )


@bp.route('/aggregator/<int:aggregator_id>/toggle', methods=['POST'])
def toggle_aggregator(aggregator_id):
    aggregator = Aggregator.query.get_or_404(aggregator_id)
    try:
        aggregator.is_active = not aggregator.is_active
        db.session.commit()
        status = 'активирован' if aggregator.is_active else 'деактивирован'
        flash(f'Агрегатор {status}!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при изменении статуса агрегатора: {str(e)}', 'danger')

    return redirect(url_for('main.aggregator_list'))


@bp.route('/aggregator/<int:aggregator_id>/toggle-htmx', methods=['POST'])
def toggle_aggregator_htmx(aggregator_id):
    """HTMX-версия переключения статуса"""
    aggregator = Aggregator.query.get_or_404(aggregator_id)
    try:
        aggregator.is_active = not aggregator.is_active
        db.session.commit()

        # Возвращаем только обновленный статус
        if aggregator.is_active:
            return '<span class="badge bg-success">Активен</span>'
        else:
            return '<span class="badge bg-danger">Неактивен</span>'
    except SQLAlchemyError as e:
        db.session.rollback()
        return '<span class="badge bg-danger">Ошибка</span>', 500


@bp.route('/aggregator/<int:aggregator_id>/delete-htmx', methods=['DELETE'])
def delete_aggregator_htmx(aggregator_id):
    """HTMX-версия удаления агрегатора"""
    aggregator = Aggregator.query.get_or_404(aggregator_id)
    try:
        db.session.delete(aggregator)
        db.session.commit()
        # Возвращаем пустой ответ для удаления строки
        return '', 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return f'<div class="alert alert-danger">Ошибка при удалении: {str(e)}</div>', 500


@bp.route('/aggregator/add', methods=['GET', 'POST'])
def add_aggregator():
    form = FormAggregator()
    if form.validate_on_submit():
        try:
            aggregator = Aggregator()
            form.populate_obj(aggregator)
            aggregator.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.session.add(aggregator)
            db.session.commit()
            flash('Агрегатор успешно добавлен!', 'success')
            return redirect(url_for('main.aggregator_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении агрегатора: {str(e)}', 'danger')

    return render_template('add_aggregator.html', form=form)


@bp.route('/aggregator/<int:aggregator_id>/edit', methods=['GET', 'POST'])
def edit_aggregator(aggregator_id):
    aggregator = Aggregator.query.get_or_404(aggregator_id)
    form = FormAggregator(obj=aggregator)

    if form.validate_on_submit():
        try:
            form.populate_obj(aggregator)
            db.session.commit()
            flash('Агрегатор успешно обновлен!', 'success')
            return redirect(url_for('main.aggregator_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении агрегатора: {str(e)}', 'danger')

    return render_template('edit_aggregator.html', form=form, aggregator=aggregator)


@bp.route('/go/alib')
def go_alib():
    """Перенаправление на alib.ru с корректной кодировкой запроса"""
    query = request.args.get('q', '').strip()

    if not query:
        flash('Пожалуйста, введите запрос для поиска на Alib.ru.', 'warning')
        return redirect(url_for('main.add_book'))

    # Перекодируем запрос в Windows-1251
    encoded_query = urllib.parse.quote(query, encoding='windows-1251')
    alib_url = f'https://www.alib.ru/find3.php4?tfind={encoded_query}'

    return redirect(alib_url)


@bp.route('/search/languages_ajax')
def search_languages_ajax():
    """Поиск языков для HTMX и модальных окон (возвращает HTML)"""
    query = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', 0, type=int)

    if len(query) < 2:
        return '<div class="text-muted p-3">Введите минимум 2 символа для поиска.</div>'

    languages = Language.query.filter(
        or_(
            Language.name.ilike(f'%{query}%'),
            Language.code.ilike(f'%{query}%')
        )
    ).limit(10).all()

    if not languages:
        return '<div class="text-muted p-3">Языки не найдены.</div>'

    html = ''.join([
        f'<a href="#" class="list-group-item list-group-item-action" data-id="{lang.id}" data-name="{lang.name}">'
        f'<div class="d-flex w-100 justify-content-between">'
        f'<h6 class="mb-1">{lang.name}</h6>'
        f'<small>{lang.code}</small>'
        f'</div>'
        f'</a>'
        for lang in languages
    ])
    return html



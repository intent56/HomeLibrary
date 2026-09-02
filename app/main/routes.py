import io
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging
import urllib.parse
import base64
from flask import (
    render_template,
    url_for,
    send_from_directory,
    send_file,
    current_app,
    request,
    redirect,
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


@bp.route("/books_poetry/")
def books_poetry():
    page = request.args.get("page", 1, type=int)
    que = Book.query
    que = que.join(Book.genre_books.and_(Genre.name == "Поэзия"))

    books = que.order_by(Book.name).paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE_BOOK"]
    )
    return render_template("books.html", books=books, source=1)


@bp.route("/books_fantastic/")
def books_fantastic():
    page = request.args.get("page", 1, type=int)
    que = Book.query
    que = que.join(Book.genre_books.and_(Genre.name.like("%фантастика%")))

    books = que.order_by(Book.name).paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE_BOOK"]
    )
    return render_template("books.html", books=books, source=2)


@bp.route("/books_dictionary/")
def books_dictionary():
    page = request.args.get("page", 1, type=int)
    que = Book.query
    que = que.join(Book.genre_books.and_(Genre.name.like("Словари%")))

    books = que.order_by(Book.name).paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE_BOOK"]
    )
    return render_template("books.html", books=books, source=3)


@bp.route("/books_children/")
def books_children():
    page = request.args.get("page", 1, type=int)
    que = Book.query
    que = que.join(Book.genre_books.and_(Genre.name.like("Детская%")))

    books = que.order_by(Book.name).paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE_BOOK"]
    )
    return render_template("books.html", books=books, source=4)


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
            form.populate_obj(book)

            if book.id_cover == 0:
                book.id_cover = None
            if book.id_format == 0:
                book.id_format = None

            # === ИСПРАВЛЕННАЯ ОБРАБОТКА ОБЛОЖКИ ===
            # Обработка загрузки обложки
            if 'cover' in request.files:
                file = request.files['cover']
                # Проверяем, что файл выбран и имеет имя
                if file and file.filename:
                    # Читаем содержимое файла в bytes
                    book.cover = file.read()
                else:
                    # Если файл не выбран, явно устанавливаем None
                    book.cover = None

            db.session.add(book)
            db.session.commit()

            flash('Книга успешно добавлена!', 'success')
            return redirect(url_for('main.select_authors', book_id=book.id))
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

    if form.validate_on_submit():
        try:
            form.populate_obj(book)

            if book.id_cover == 0:
                book.id_cover = None
            if book.id_format == 0:
                book.id_format = None

            # === ИСПРАВЛЕННАЯ ОБРАБОТКА ОБЛОЖКИ ===
            # Обработка загрузки новой обложки
            if 'cover' in request.files:
                file = request.files['cover']
                # Проверяем, что файл выбран и имеет имя
                if file and file.filename:
                    # Читаем содержимое файла в bytes
                    book.cover = file.read()
                else:
                    # Если файл не выбран, оставляем существующую обложку
                    # (НЕ устанавливаем None, чтобы не удалять существующую)
                    pass

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


@bp.route('/book/<int:book_id>/authors', methods=['GET'])
def select_authors(book_id):
    book = Book.query.get_or_404(book_id)

    # Получаем исходный список авторов из БД
    original_authors = book.author_books
    original_author_ids = [a.id for a in original_authors]

    # Инициализируем сессионные списки изменений
    session_key = f'book_{book_id}_authors_changes'
    if session_key not in session:
        session[session_key] = {
            'added': [],
            'removed': []
        }

    # Применяем изменения из сессии
    added_ids = session[session_key]['added']
    removed_ids = session[session_key]['removed']

    # Формируем финальный список для отображения
    final_authors = []
    for author in original_authors:
        if author.id not in removed_ids:
            final_authors.append(author)

    # Добавляем новых авторов (временные объекты только для отображения)
    for author_id in added_ids:
        if author_id not in original_author_ids:
            author = Author.query.get(author_id)
            if author and author.id not in removed_ids:
                final_authors.append(author)

    # Проверяем, есть ли реальные изменения
    has_changes = bool(added_ids) or bool(removed_ids)

    return render_template('select_authors.html',
                           book=book,
                           selected_authors=final_authors,
                           original_author_ids=original_author_ids,
                           pending_added=added_ids,
                           pending_removed=removed_ids,
                           has_changes=has_changes)


@bp.route('/book/<int:book_id>/authors/add', methods=['POST'])
def add_author_to_book_session(book_id):
    """Добавляет автора во временный список сессии"""
    book = Book.query.get_or_404(book_id)
    author_id = request.form.get('author_id', type=int)

    if not author_id:
        return jsonify({'error': 'Не указан автор'}), 400

    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': 'Автор не найден'}), 404

    session_key = f'book_{book_id}_authors_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если автор был в списке удаленных, убираем его оттуда
    if author_id in session[session_key]['removed']:
        session[session_key]['removed'].remove(author_id)
    # Иначе добавляем в список добавленных (если еще не добавлен)
    elif author_id not in session[session_key]['added']:
        # Проверяем, не существует ли уже связь в БД
        exists = db.session.query(book_authors).filter_by(
            id_book=book_id,
            id_author=author_id
        ).first() is not None

        if not exists:
            session[session_key]['added'].append(author_id)
        else:
            # Если связь уже есть в БД, ничего не делаем
            return jsonify({'warning': 'Автор уже добавлен к книге'}), 200

    session.modified = True
    return jsonify({'success': True, 'author_id': author_id})


@bp.route('/book/<int:book_id>/authors/remove/<int:author_id>', methods=['POST'])
def remove_author_from_book_session(book_id, author_id):
    """Удаляет автора из временного списка сессии"""
    book = Book.query.get_or_404(book_id)

    session_key = f'book_{book_id}_authors_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если автор был в списке добавленных, просто убираем его оттуда
    if author_id in session[session_key]['added']:
        session[session_key]['added'].remove(author_id)
    else:
        # Иначе добавляем в список удаленных
        if author_id not in session[session_key]['removed']:
            session[session_key]['removed'].append(author_id)

    session.modified = True
    return jsonify({'success': True})


@bp.route('/book/<int:book_id>/authors/save', methods=['POST'])
def save_authors_changes(book_id):
    """Сохраняет все изменения в БД"""
    book = Book.query.get_or_404(book_id)
    session_key = f'book_{book_id}_authors_changes'

    if session_key not in session:
        flash('Нет изменений для сохранения', 'info')
        return redirect(url_for('main.book_list'))

    changes = session[session_key]

    try:
        # Применяем удаления
        for author_id in changes['removed']:
            author = Author.query.get(author_id)
            if author and author in book.author_books:
                book.author_books.remove(author)

        # Применяем добавления
        for author_id in changes['added']:
            # Проверяем, не была ли связь уже создана в БД (на случай параллельных изменений)
            exists = db.session.query(book_authors).filter_by(
                id_book=book_id,
                id_author=author_id
            ).first() is not None

            if not exists:
                author = Author.query.get(author_id)
                if author and author not in book.author_books:
                    book.author_books.append(author)

        db.session.commit()

        # Очищаем сессию
        session.pop(session_key, None)
        session.modified = True

        flash('Изменения успешно сохранены!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении изменений: {str(e)}', 'danger')

    return redirect(url_for('main.book_list'))


@bp.route('/book/<int:book_id>/authors/cancel', methods=['POST'])
def cancel_authors_changes(book_id):
    """Отменяет все изменения"""
    session_key = f'book_{book_id}_authors_changes'
    session.pop(session_key, None)
    session.modified = True
    flash('Изменения отменены', 'info')
    return redirect(url_for('main.book_list'))


@bp.route('/author/add', methods=['GET', 'POST'])
def add_author():
    form = FormAuthor()

    if form.validate_on_submit():
        try:
            author = Author()
            form.populate_obj(author)
            author.fio = f"{author.lastname} {author.firstname or ''} {author.secondname or ''}".strip(
            )

            # Обработка загрузки фото
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    author.photo = file.read()

            db.session.add(author)
            db.session.commit()

            flash('Автор успешно добавлен!', 'success')
            return redirect(url_for('main.select_authors', book_id=request.args.get('book_id', 0)))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении автора: {str(e)}', 'danger')

    return render_template('add_author.html', form=form, book_id=request.args.get('book_id', 0))


@bp.route('/search/authors')
def search_authors():
    query = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', 0, type=int)

    if len(query) < 2:
        # Возвращаем пустой ответ с предложением добавить автора
        return render_template('search_authors.html',
                               authors=[],
                               book_id=book_id)

    authors = Author.query.filter(
        Author.lastname.ilike(f'%{query}%')).limit(10).all()

    if request.headers.get('HX-Request'):
        # Для HTMX запросов возвращаем HTML
        return render_template('search_authors.html',
                               authors=authors,
                               book_id=book_id)
    else:
        # Для обычных запросов возвращаем JSON
        return jsonify([{
            'id': a.id,
            'fio': a.fio,
            'lastname': a.lastname,
            'firstname': a.firstname or ''
        } for a in authors])


@bp.route('/authors')
def author_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Базовый запрос
    query = Author.query

    # Поиск по ФИО
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            Author.lastname.ilike(f'{search_pattern}%')
        )

    # Сортировка по ФИО
    query = query.order_by(Author.fio)

    # Пагинация
    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_AUTHOR,
        error_out=False
    )

    # Проверяем, является ли запрос HTMX
    if request.headers.get('HX-Request'):
        # Возвращаем только сетку авторов и пагинацию
        return render_template('partials/author_grid.html',
                               authors=pagination.items,
                               pagination=pagination,
                               total_authors=query.count(),
                               search=search)

    return render_template('author_list.html',
                           authors=pagination.items,
                           pagination=pagination,
                           total_authors=query.count(),
                           search=search)


@bp.route('/author/<int:author_id>/edit', methods=['GET', 'POST'])
def edit_author(author_id):
    author = Author.query.get_or_404(author_id)
    form = FormAuthor(obj=author)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    books_query = Book.query.join(book_authors).filter(
        book_authors.c.id_author == author_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(author)
            author.fio = f"{author.lastname} {author.firstname or ''} {author.secondname or ''}".strip(
            )

            # Обработка загрузки нового фото
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    author.photo = file.read()

            db.session.commit()
            flash('Автор успешно обновлен!', 'success')
            return redirect(url_for('main.author_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении автора: {str(e)}', 'danger')

    return render_template('edit_author.html',
                           form=form,
                           author=author,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/author/<int:author_id>/delete', methods=['POST'])
def delete_author(author_id):
    author = Author.query.get_or_404(author_id)
    try:
        db.session.delete(author)
        db.session.commit()
        flash('Автор успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении автора: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('main.author_list', page=page))


@bp.route('/books')
def book_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    author_search = request.args.get('author_search', '').strip()
    interpreter_search = request.args.get('interpreter_search', '').strip()
    genre_search = request.args.get('genre_search', '').strip()

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

    if request.headers.get('HX-Request'):
        return render_template('partials/book_table.html',
                               books=pagination.items,
                               pagination=pagination,
                               total_books=query.count(),
                               search=search,
                               author_search=author_search,
                               interpreter_search=interpreter_search,
                               genre_search=genre_search)

    return render_template('book_list.html',
                           books=pagination.items,
                           pagination=pagination,
                           total_books=query.count(),
                           search=search,
                           author_search=author_search,
                           interpreter_search=interpreter_search,
                           genre_search=genre_search)


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


@bp.route('/interpreters')
def interpreter_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Interpreter.query

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(Interpreter.lastname.ilike(search_pattern))

    query = query.order_by(Interpreter.fio)

    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_INTERPRETER,
        error_out=False
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/interpreter_grid.html',
                               interpreters=pagination.items,
                               pagination=pagination,
                               total_interpreters=query.count(),
                               search=search)

    return render_template('interpreter_list.html',
                           interpreters=pagination.items,
                           pagination=pagination,
                           total_interpreters=query.count(),
                           search=search)


@bp.route('/interpreter/<int:interpreter_id>/edit', methods=['GET', 'POST'])
def edit_interpreter(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    form = FormInterpreter(obj=interpreter)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    books_query = Book.query.join(book_interpreters).filter(
        book_interpreters.c.id_interpreter == interpreter_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(interpreter)
            interpreter.fio = f"{interpreter.lastname} {interpreter.firstname or ''} {interpreter.secondname or ''}".strip(
            )

            # Обработка загрузки нового фото
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    interpreter.photo = file.read()

            db.session.commit()
            flash('Переводчик успешно обновлен!', 'success')
            return redirect(url_for('main.interpreter_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении переводчика: {str(e)}', 'danger')

    return render_template('edit_interpreter.html',
                           form=form,
                           interpreter=interpreter,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/interpreter/<int:interpreter_id>/delete', methods=['POST'])
def delete_interpreter(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    try:
        db.session.delete(interpreter)
        db.session.commit()
        flash('Переводчик успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении переводчика: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('main.interpreter_list', page=page))


@bp.route('/interpreter/add', methods=['GET', 'POST'])
def add_interpreter():
    form = FormInterpreter()

    if form.validate_on_submit():
        try:
            interpreter = Interpreter()
            form.populate_obj(interpreter)
            interpreter.fio = f"{interpreter.lastname} {interpreter.firstname or ''} {interpreter.secondname or ''}".strip(
            )

            # Обработка загрузки фото
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    interpreter.photo = file.read()

            db.session.add(interpreter)
            db.session.commit()

            # Добавление языков
            language_ids = request.form.getlist('language_ids')
            if language_ids:
                languages = Language.query.filter(
                    Language.id.in_(language_ids)).all()
                interpreter.lang_interpreters.extend(languages)
                db.session.commit()

            flash('Переводчик успешно добавлен!', 'success')
            return redirect(url_for('main.select_interpreters', book_id=request.args.get('book_id', 0)))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении переводчика: {str(e)}', 'danger')

    languages = Language.query.order_by(Language.name).all()
    return render_template('add_interpreter.html', form=form, book_id=request.args.get('book_id', 0), languages=languages)


@bp.route('/book/<int:book_id>/interpreters', methods=['GET'])
def select_interpreters(book_id):
    """Страница выбора переводчиков для книги."""
    book = Book.query.get_or_404(book_id)

    # Получаем исходный список переводчиков из БД
    original_interpreters = book.interpreter_books
    original_interpreter_ids = [i.id for i in original_interpreters]

    # Инициализируем сессионные списки изменений
    session_key = f'book_{book_id}_interpreters_changes'
    if session_key not in session:
        session[session_key] = {
            'added': [],
            'removed': []
        }

    # Применяем изменения из сессии
    added_ids = session[session_key]['added']
    removed_ids = session[session_key]['removed']

    # Формируем финальный список для отображения
    final_interpreters = []
    for interpreter in original_interpreters:
        if interpreter.id not in removed_ids:
            final_interpreters.append(interpreter)

    # Добавляем новых переводчиков (временные объекты только для отображения)
    for interpreter_id in added_ids:
        if interpreter_id not in original_interpreter_ids:
            interpreter = Interpreter.query.get(interpreter_id)
            if interpreter and interpreter.id not in removed_ids:
                final_interpreters.append(interpreter)

    # Проверяем, есть ли реальные изменения
    has_changes = bool(added_ids) or bool(removed_ids)

    return render_template('select_interpreters.html',
                           book=book,
                           selected_interpreters=final_interpreters,
                           original_interpreter_ids=original_interpreter_ids,
                           pending_added=added_ids,
                           pending_removed=removed_ids,
                           has_changes=has_changes)


@bp.route('/book/<int:book_id>/interpreters/add', methods=['POST'])
def add_interpreter_to_book_session(book_id):
    """Добавляет переводчика во временный список сессии."""
    book = Book.query.get_or_404(book_id)
    interpreter_id = request.form.get('interpreter_id', type=int)

    if not interpreter_id:
        return jsonify({'error': 'Не указан переводчик'}), 400

    interpreter = Interpreter.query.get(interpreter_id)
    if not interpreter:
        return jsonify({'error': 'Переводчик не найден'}), 404

    session_key = f'book_{book_id}_interpreters_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если переводчик был в списке удаленных, убираем его оттуда
    if interpreter_id in session[session_key]['removed']:
        session[session_key]['removed'].remove(interpreter_id)
    # Иначе добавляем в список добавленных (если еще не добавлен)
    elif interpreter_id not in session[session_key]['added']:
        # Проверяем, не существует ли уже связь в БД
        exists = db.session.query(book_interpreters).filter_by(
            id_book=book_id,
            id_interpreter=interpreter_id
        ).first() is not None

        if not exists:
            session[session_key]['added'].append(interpreter_id)
        else:
            # Если связь уже есть в БД, ничего не делаем
            return jsonify({'warning': 'Переводчик уже добавлен к книге'}), 200

    session.modified = True
    return jsonify({'success': True, 'interpreter_id': interpreter_id})


@bp.route('/book/<int:book_id>/interpreters/remove/<int:interpreter_id>', methods=['POST'])
def remove_interpreter_from_book_session(book_id, interpreter_id):
    """Удаляет переводчика из временного списка сессии."""
    book = Book.query.get_or_404(book_id)

    session_key = f'book_{book_id}_interpreters_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если переводчик был в списке добавленных, просто убираем его оттуда
    if interpreter_id in session[session_key]['added']:
        session[session_key]['added'].remove(interpreter_id)
    else:
        # Иначе добавляем в список удаленных
        if interpreter_id not in session[session_key]['removed']:
            session[session_key]['removed'].append(interpreter_id)

    session.modified = True
    return jsonify({'success': True})


@bp.route('/book/<int:book_id>/interpreters/save', methods=['POST'])
def save_interpreters_changes(book_id):
    """Сохраняет все изменения переводчиков в БД."""
    book = Book.query.get_or_404(book_id)
    session_key = f'book_{book_id}_interpreters_changes'

    if session_key not in session:
        flash('Нет изменений для сохранения', 'info')
        return redirect(url_for('main.book_detail', book_id=book_id))

    changes = session[session_key]

    try:
        # Применяем удаления
        for interpreter_id in changes['removed']:
            interpreter = Interpreter.query.get(interpreter_id)
            if interpreter and interpreter in book.interpreter_books:
                book.interpreter_books.remove(interpreter)

        # Применяем добавления
        for interpreter_id in changes['added']:
            # Проверяем, не была ли связь уже создана в БД
            exists = db.session.query(book_interpreters).filter_by(
                id_book=book_id,
                id_interpreter=interpreter_id
            ).first() is not None

            if not exists:
                interpreter = Interpreter.query.get(interpreter_id)
                if interpreter and interpreter not in book.interpreter_books:
                    book.interpreter_books.append(interpreter)

        db.session.commit()

        # Очищаем сессию
        session.pop(session_key, None)
        session.modified = True

        flash('Изменения переводчиков успешно сохранены!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(
            f'Ошибка при сохранении изменений переводчиков: {str(e)}', 'danger')

    return redirect(url_for('main.book_detail', book_id=book_id))


@bp.route('/book/<int:book_id>/interpreters/cancel', methods=['POST'])
def cancel_interpreters_changes(book_id):
    """Отменяет все изменения переводчиков."""
    session_key = f'book_{book_id}_interpreters_changes'
    session.pop(session_key, None)
    session.modified = True
    flash('Изменения переводчиков отменены', 'info')
    return redirect(url_for('main.book_detail', book_id=book_id))


@bp.route('/search/interpreters')
def search_interpreters():
    query = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', 0, type=int)

    if len(query) < 2:
        return render_template('search_interpreters.html', interpreters=[], book_id=book_id)

    interpreters = Interpreter.query.filter(
        Interpreter.lastname.ilike(f'%{query}%')).limit(10).all()

    if request.headers.get('HX-Request'):
        return render_template('search_interpreters.html', interpreters=interpreters, book_id=book_id)
    else:
        return jsonify([{
            'id': i.id,
            'fio': i.fio,
            'lastname': i.lastname,
            'firstname': i.firstname or ''
        } for i in interpreters])


@bp.route('/genres')
def genre_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Genre.query

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(Genre.name.ilike(search_pattern))

    query = query.order_by(Genre.name)

    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_GENRE,
        error_out=False
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/genre_grid.html',
                               genres=pagination.items,
                               pagination=pagination,
                               total_genres=query.count(),
                               search=search)

    return render_template('genre_list.html',
                           genres=pagination.items,
                           pagination=pagination,
                           total_genres=query.count(),
                           search=search)


@bp.route('/genre/<int:genre_id>/edit', methods=['GET', 'POST'])
def edit_genre(genre_id):
    genre = Genre.query.get_or_404(genre_id)
    form = FormGenre(obj=genre)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Получаем книги в этом жанре с пагинацией
    page = request.args.get('page', 1, type=int)
    # Используем связь genre_books для получения книг
    books_query = Book.query.join(book_genres).filter(
        book_genres.c.id_genre == genre_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(genre)
            db.session.commit()
            flash('Жанр успешно обновлен!', 'success')
            return redirect(url_for('main.genre_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении жанра: {str(e)}', 'danger')

    return render_template('edit_genre.html',
                           form=form,
                           genre=genre,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/genre/<int:genre_id>/delete', methods=['POST'])
def delete_genre(genre_id):
    genre = Genre.query.get_or_404(genre_id)
    try:
        db.session.delete(genre)
        db.session.commit()
        flash('Жанр успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении жанра: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('main.genre_list', page=page))


@bp.route('/book/<int:book_id>/genres', methods=['GET'])
def select_genres(book_id):
    """Страница выбора жанров для книги."""
    book = Book.query.get_or_404(book_id)

    # Получаем исходный список жанров из БД
    original_genres = book.genre_books
    original_genre_ids = [g.id for g in original_genres]

    # Инициализируем сессионные списки изменений
    session_key = f'book_{book_id}_genres_changes'
    if session_key not in session:
        session[session_key] = {
            'added': [],
            'removed': []
        }

    # Применяем изменения из сессии
    added_ids = session[session_key]['added']
    removed_ids = session[session_key]['removed']

    # Формируем финальный список для отображения
    final_genres = []
    for genre in original_genres:
        if genre.id not in removed_ids:
            final_genres.append(genre)

    # Добавляем новые жанры (временные объекты только для отображения)
    for genre_id in added_ids:
        if genre_id not in original_genre_ids:
            genre = Genre.query.get(genre_id)
            if genre and genre.id not in removed_ids:
                final_genres.append(genre)

    # Проверяем, есть ли реальные изменения
    has_changes = bool(added_ids) or bool(removed_ids)

    return render_template('select_genres.html',
                           book=book,
                           selected_genres=final_genres,
                           original_genre_ids=original_genre_ids,
                           pending_added=added_ids,
                           pending_removed=removed_ids,
                           has_changes=has_changes)


@bp.route('/book/<int:book_id>/genres/add', methods=['POST'])
def add_genre_to_book_session(book_id):
    """Добавляет жанр во временный список сессии."""
    book = Book.query.get_or_404(book_id)
    genre_id = request.form.get('genre_id', type=int)

    if not genre_id:
        return jsonify({'error': 'Не указан жанр'}), 400

    genre = Genre.query.get(genre_id)
    if not genre:
        return jsonify({'error': 'Жанр не найден'}), 404

    session_key = f'book_{book_id}_genres_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если жанр был в списке удаленных, убираем его оттуда
    if genre_id in session[session_key]['removed']:
        session[session_key]['removed'].remove(genre_id)
    # Иначе добавляем в список добавленных (если еще не добавлен)
    elif genre_id not in session[session_key]['added']:
        # Проверяем, не существует ли уже связь в БД
        exists = db.session.query(book_genres).filter_by(
            id_book=book_id,
            id_genre=genre_id
        ).first() is not None

        if not exists:
            session[session_key]['added'].append(genre_id)
        else:
            # Если связь уже есть в БД, ничего не делаем
            return jsonify({'warning': 'Жанр уже добавлен к книге'}), 200

    session.modified = True
    return jsonify({'success': True, 'genre_id': genre_id})


@bp.route('/book/<int:book_id>/genres/remove/<int:genre_id>', methods=['POST'])
def remove_genre_from_book_session(book_id, genre_id):
    """Удаляет жанр из временного списка сессии."""
    book = Book.query.get_or_404(book_id)

    session_key = f'book_{book_id}_genres_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если жанр был в списке добавленных, просто убираем его оттуда
    if genre_id in session[session_key]['added']:
        session[session_key]['added'].remove(genre_id)
    else:
        # Иначе добавляем в список удаленных
        if genre_id not in session[session_key]['removed']:
            session[session_key]['removed'].append(genre_id)

    session.modified = True
    return jsonify({'success': True})


@bp.route('/book/<int:book_id>/genres/save', methods=['POST'])
def save_genres_changes(book_id):
    """Сохраняет все изменения жанров в БД."""
    book = Book.query.get_or_404(book_id)
    session_key = f'book_{book_id}_genres_changes'

    if session_key not in session:
        flash('Нет изменений для сохранения', 'info')
        return redirect(url_for('main.book_detail', book_id=book_id))

    changes = session[session_key]

    try:
        # Применяем удаления
        for genre_id in changes['removed']:
            genre = Genre.query.get(genre_id)
            if genre and genre in book.genre_books:
                book.genre_books.remove(genre)

        # Применяем добавления
        for genre_id in changes['added']:
            # Проверяем, не была ли связь уже создана в БД
            exists = db.session.query(book_genres).filter_by(
                id_book=book_id,
                id_genre=genre_id
            ).first() is not None

            if not exists:
                genre = Genre.query.get(genre_id)
                if genre and genre not in book.genre_books:
                    book.genre_books.append(genre)

        db.session.commit()

        # Очищаем сессию
        session.pop(session_key, None)
        session.modified = True

        flash('Изменения жанров успешно сохранены!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении изменений жанров: {str(e)}', 'danger')

    return redirect(url_for('main.book_detail', book_id=book_id))


@bp.route('/book/<int:book_id>/genres/cancel', methods=['POST'])
def cancel_genres_changes(book_id):
    """Отменяет все изменения жанров."""
    session_key = f'book_{book_id}_genres_changes'
    session.pop(session_key, None)
    session.modified = True
    flash('Изменения жанров отменены', 'info')
    return redirect(url_for('main.book_detail', book_id=book_id))


@bp.route('/genre/add', methods=['GET', 'POST'])
def add_genre():
    form = FormGenre()

    if form.validate_on_submit():
        try:
            genre = Genre()
            form.populate_obj(genre)

            db.session.add(genre)
            db.session.commit()

            flash('Жанр успешно добавлен!', 'success')
            return redirect(url_for('main.select_genres', book_id=request.args.get('book_id', 0)))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении жанра: {str(e)}', 'danger')

    return render_template('add_genre.html', form=form, book_id=request.args.get('book_id', 0))


@bp.route('/search/genres')
def search_genres():
    query = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', 0, type=int)

    if len(query) < 2:
        return render_template('search_genres.html', genres=[], book_id=book_id)

    genres = Genre.query.filter(
        Genre.name.ilike(f'%{query}%')
    ).limit(10).all()

    if request.headers.get('HX-Request'):
        return render_template('search_genres.html', genres=genres, book_id=book_id)
    else:
        return jsonify([{
            'id': g.id,
            'name': g.name
        } for g in genres])


@bp.route('/publishers')
def publisher_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Publisher.query

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(Publisher.name.ilike(search_pattern))

    query = query.order_by(Publisher.name)

    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_PUBLISHER,
        error_out=False
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/publisher_grid.html',
                               publishers=pagination.items,
                               pagination=pagination,
                               total_publishers=query.count(),
                               search=search)

    return render_template('publisher_list.html',
                           publishers=pagination.items,
                           pagination=pagination,
                           total_publishers=query.count(),
                           search=search)


@bp.route('/publisher/<int:publisher_id>/edit', methods=['GET', 'POST'])
def edit_publisher(publisher_id):
    publisher = Publisher.query.get_or_404(publisher_id)
    form = FormPublisher(obj=publisher)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    books_query = Book.query.join(book_publishers).filter(
        book_publishers.c.id_publisher == publisher_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(publisher)
            db.session.commit()
            flash('Издатель успешно обновлен!', 'success')
            return redirect(url_for('main.publisher_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении издателя: {str(e)}', 'danger')

    return render_template('edit_publisher.html',
                           form=form,
                           publisher=publisher,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/publisher/<int:publisher_id>/delete', methods=['POST'])
def delete_publisher(publisher_id):
    publisher = Publisher.query.get_or_404(publisher_id)
    try:
        db.session.delete(publisher)
        db.session.commit()
        flash('Издатель успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении издателя: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('main.publisher_list', page=page))


@bp.route('/book/<int:book_id>/publishers', methods=['GET'])
def select_publishers(book_id):
    """Страница выбора издателей для книги."""
    book = Book.query.get_or_404(book_id)

    # Получаем исходный список издателей из БД
    original_publishers = book.publisher_books
    original_publisher_ids = [p.id for p in original_publishers]

    # Инициализируем сессионные списки изменений
    session_key = f'book_{book_id}_publishers_changes'
    if session_key not in session:
        session[session_key] = {
            'added': [],
            'removed': []
        }

    # Применяем изменения из сессии
    added_ids = session[session_key]['added']
    removed_ids = session[session_key]['removed']

    # Формируем финальный список для отображения
    final_publishers = []
    for publisher in original_publishers:
        if publisher.id not in removed_ids:
            final_publishers.append(publisher)

    # Добавляем новых издателей (временные объекты только для отображения)
    for publisher_id in added_ids:
        if publisher_id not in original_publisher_ids:
            publisher = Publisher.query.get(publisher_id)
            if publisher and publisher.id not in removed_ids:
                final_publishers.append(publisher)

    # Проверяем, есть ли реальные изменения
    has_changes = bool(added_ids) or bool(removed_ids)

    return render_template('select_publishers.html',
                           book=book,
                           selected_publishers=final_publishers,
                           original_publisher_ids=original_publisher_ids,
                           pending_added=added_ids,
                           pending_removed=removed_ids,
                           has_changes=has_changes)


@bp.route('/book/<int:book_id>/publishers/add', methods=['POST'])
def add_publisher_to_book_session(book_id):
    """Добавляет издателя во временный список сессии."""
    book = Book.query.get_or_404(book_id)
    publisher_id = request.form.get('publisher_id', type=int)

    if not publisher_id:
        return jsonify({'error': 'Не указан издатель'}), 400

    publisher = Publisher.query.get(publisher_id)
    if not publisher:
        return jsonify({'error': 'Издатель не найден'}), 404

    session_key = f'book_{book_id}_publishers_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если издатель был в списке удаленных, убираем его оттуда
    if publisher_id in session[session_key]['removed']:
        session[session_key]['removed'].remove(publisher_id)
    # Иначе добавляем в список добавленных (если еще не добавлен)
    elif publisher_id not in session[session_key]['added']:
        # Проверяем, не существует ли уже связь в БД
        exists = db.session.query(book_publishers).filter_by(
            id_book=book_id,
            id_publisher=publisher_id
        ).first() is not None

        if not exists:
            session[session_key]['added'].append(publisher_id)
        else:
            # Если связь уже есть в БД, ничего не делаем
            return jsonify({'warning': 'Издатель уже добавлен к книге'}), 200

    session.modified = True
    return jsonify({'success': True, 'publisher_id': publisher_id})


@bp.route('/book/<int:book_id>/publishers/remove/<int:publisher_id>', methods=['POST'])
def remove_publisher_from_book_session(book_id, publisher_id):
    """Удаляет издателя из временного списка сессии."""
    book = Book.query.get_or_404(book_id)

    session_key = f'book_{book_id}_publishers_changes'
    if session_key not in session:
        session[session_key] = {'added': [], 'removed': []}

    # Если издатель был в списке добавленных, просто убираем его оттуда
    if publisher_id in session[session_key]['added']:
        session[session_key]['added'].remove(publisher_id)
    else:
        # Иначе добавляем в список удаленных
        if publisher_id not in session[session_key]['removed']:
            session[session_key]['removed'].append(publisher_id)

    session.modified = True
    return jsonify({'success': True})


@bp.route('/book/<int:book_id>/publishers/save', methods=['POST'])
def save_publishers_changes(book_id):
    """Сохраняет все изменения издателей в БД."""
    book = Book.query.get_or_404(book_id)
    session_key = f'book_{book_id}_publishers_changes'

    if session_key not in session:
        flash('Нет изменений для сохранения', 'info')
        return redirect(url_for('main.book_detail', book_id=book_id))

    changes = session[session_key]

    try:
        # Применяем удаления
        for publisher_id in changes['removed']:
            publisher = Publisher.query.get(publisher_id)
            if publisher and publisher in book.publisher_books:
                book.publisher_books.remove(publisher)

        # Применяем добавления
        for publisher_id in changes['added']:
            # Проверяем, не была ли связь уже создана в БД
            exists = db.session.query(book_publishers).filter_by(
                id_book=book_id,
                id_publisher=publisher_id
            ).first() is not None

            if not exists:
                publisher = Publisher.query.get(publisher_id)
                if publisher and publisher not in book.publisher_books:
                    book.publisher_books.append(publisher)

        db.session.commit()

        # Очищаем сессию
        session.pop(session_key, None)
        session.modified = True

        flash('Изменения издателей успешно сохранены!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении изменений издателей: {str(e)}', 'danger')

    return redirect(url_for('main.book_detail', book_id=book_id))


@bp.route('/book/<int:book_id>/publishers/cancel', methods=['POST'])
def cancel_publishers_changes(book_id):
    """Отменяет все изменения издателей."""
    session_key = f'book_{book_id}_publishers_changes'
    session.pop(session_key, None)
    session.modified = True
    flash('Изменения издателей отменены', 'info')
    return redirect(url_for('main.book_detail', book_id=book_id))


@bp.route('/search/publishers')
def search_publishers():
    query = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', 0, type=int)

    if len(query) < 2:
        return render_template('search_publishers.html', publishers=[], book_id=book_id)

    publishers = Publisher.query.filter(
        Publisher.name.ilike(f'%{query}%')
    ).limit(10).all()

    if request.headers.get('HX-Request'):
        return render_template('search_publishers.html', publishers=publishers, book_id=book_id)
    else:
        return jsonify([{
            'id': p.id,
            'name': p.name
        } for p in publishers])


@bp.route('/publisher/add', methods=['GET', 'POST'])
def add_publisher():
    form = FormPublisher()

    if form.validate_on_submit():
        try:
            publisher = Publisher()
            form.populate_obj(publisher)

            db.session.add(publisher)
            db.session.commit()

            flash('Издатель успешно добавлен!', 'success')
            return redirect(url_for('main.select_publishers', book_id=request.args.get('book_id', 0)))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении издателя: {str(e)}', 'danger')

    return render_template('add_publisher.html', form=form, book_id=request.args.get('book_id', 0))


@bp.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')

    return render_template('book_detail.html',
                           book=book,
                           page=page,
                           search=search,
                           author_search=author_search,
                           interpreter_search=interpreter_search,
                           genre_search=genre_search)


@bp.route('/covers')
def cover_list():
    covers = Cover.query.order_by(Cover.name).all()
    total_covers = Cover.query.count()
    total_books_with_covers = sum(len(cover.cvr_books) for cover in covers)
    return render_template('cover_list.html',
                           covers=covers,
                           total_covers=total_covers,
                           total_books_with_covers=total_books_with_covers)


@bp.route('/formats')
def format_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Базовый запрос
    query = Format.query

    # Поиск по названию формата
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            or_(
                Format.format.ilike(search_pattern),
                Format.comment.ilike(search_pattern)
            )
        )

    # Сортировка по названию формата
    query = query.order_by(Format.format)

    # Пагинация
    pagination = query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_FORMAT,
        error_out=False
    )

    # Общая статистика (все форматы без пагинации)
    total_formats = Format.query.count()
    total_books_with_formats = sum(len(f.fmt_books)
                                   for f in Format.query.all())

    if request.headers.get('HX-Request'):
        return render_template('partials/format_table.html',
                               formats=pagination.items,
                               pagination=pagination,
                               total_formats=total_formats,
                               total_books_with_formats=total_books_with_formats,
                               search=search)

    return render_template('format_list.html',
                           formats=pagination.items,
                           pagination=pagination,
                           total_formats=total_formats,
                           total_books_with_formats=total_books_with_formats,
                           search=search)


@bp.route('/languages')
def language_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

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

    if request.headers.get('HX-Request'):
        return render_template('partials/language_grid.html',
                               languages=pagination.items,
                               pagination=pagination,
                               total_languages=query.count(),
                               search=search)

    return render_template('language_list.html',
                           languages=pagination.items,
                           pagination=pagination,
                           total_languages=query.count(),
                           search=search)


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
            return redirect(url_for('main.select_languages', book_id=request.args.get('book_id', 0)))
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


@bp.route('/author/<int:author_id>/card')
def author_card(author_id):
    author = Author.query.get_or_404(author_id)
    page = request.args.get('page', 1, type=int)

    # Получаем параметры для возврата
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Получаем книги автора с пагинацией
    books_query = Book.query.join(book_authors).filter(
        book_authors.c.id_author == author_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('author_card.html',
                           author=author,
                           books=pagination.items,
                           pagination=pagination,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/interpreter/<int:interpreter_id>/card')
def interpreter_card(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    page = request.args.get('page', 1, type=int)

    # Получаем параметры для возврата
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Получаем книги переводчика с пагинацией
    books_query = Book.query.join(book_interpreters).filter(
        book_interpreters.c.id_interpreter == interpreter_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('interpreter_card.html',
                           interpreter=interpreter,
                           books=pagination.items,
                           pagination=pagination,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/interpreter/<int:interpreter_id>/view')
def interpreter_view(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    page = request.args.get('page', 1, type=int)

    books_query = Book.query.join(book_interpreters).filter(
        book_interpreters.c.id_interpreter == interpreter_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('interpreter_card_view.html',
                           interpreter=interpreter,
                           books=pagination.items,
                           pagination=pagination)


@bp.route('/format/<int:format_id>/edit', methods=['GET', 'POST'])
def edit_format(format_id):
    format_item = Format.query.get_or_404(format_id)
    form = FormFormat(obj=format_item)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    books_query = Book.query.filter(
        Book.id_format == format_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(format_item)
            db.session.commit()
            flash('Формат успешно обновлен!', 'success')
            return redirect(url_for('main.format_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении формата: {str(e)}', 'danger')

    return render_template('edit_format.html',
                           form=form,
                           format_item=format_item,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/format/<int:format_id>/delete', methods=['POST'])
def delete_format(format_id):
    format_item = Format.query.get_or_404(format_id)
    try:
        # Проверяем, есть ли книги с этим форматом
        if format_item.fmt_books:
            flash(
                f'Невозможно удалить формат "{format_item.format}", так как он используется в {len(format_item.fmt_books)} книгах!', 'danger')
            return redirect(url_for('main.format_list'))

        db.session.delete(format_item)
        db.session.commit()
        flash('Формат успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении формата: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('main.format_list', page=page))


@bp.route('/cover/<int:cover_id>/edit', methods=['GET', 'POST'])
def edit_cover(cover_id):
    cover = Cover.query.get_or_404(cover_id)
    form = FormCover(obj=cover)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    return_page = request.args.get('return_page', 1, type=int)

    books_query = Book.query.filter(
        Book.id_cover == cover_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    if form.validate_on_submit():
        try:
            form.populate_obj(cover)

            # Проверяем уникальность кода (исключая текущую запись)
            existing = Cover.query.filter(
                Cover.code == cover.code, Cover.id != cover.id).first()
            if existing:
                flash(
                    f'Код "{cover.code}" уже используется другим переплетом!', 'danger')
                return render_template('edit_cover.html',
                                       form=form,
                                       cover=cover,
                                       books=pagination.items,
                                       pagination=pagination,
                                       page=page,
                                       return_page=return_page)

            db.session.commit()
            flash('Тип переплета успешно обновлен!', 'success')
            return redirect(url_for('main.cover_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении типа переплета: {str(e)}', 'danger')

    return render_template('edit_cover.html',
                           form=form,
                           cover=cover,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           return_page=return_page)


@bp.route('/cover/<int:cover_id>/delete', methods=['POST'])
def delete_cover(cover_id):
    cover = Cover.query.get_or_404(cover_id)
    try:
        # Проверяем, есть ли книги с этим переплетом
        if cover.cvr_books:
            flash(
                f'Невозможно удалить тип переплета "{cover.name}", так как он используется в {len(cover.cvr_books)} книгах!', 'danger')
            return redirect(url_for('main.cover_list'))

        db.session.delete(cover)
        db.session.commit()
        flash('Тип переплета успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении типа переплета: {str(e)}', 'danger')

    return redirect(url_for('main.cover_list'))


@bp.route('/format/add', methods=['GET', 'POST'])
def add_format():
    form = FormFormat()

    if form.validate_on_submit():
        try:
            format_item = Format()
            form.populate_obj(format_item)
            db.session.add(format_item)
            db.session.commit()
            flash('Формат успешно добавлен!', 'success')
            return redirect(url_for('main.format_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении формата: {str(e)}', 'danger')

    return render_template('add_format.html', form=form)


@bp.route('/cover/add', methods=['GET', 'POST'])
def add_cover():
    form = FormCover()

    if form.validate_on_submit():
        try:
            cover = Cover()
            form.populate_obj(cover)

            # Проверяем уникальность кода
            existing = Cover.query.filter_by(code=cover.code).first()
            if existing:
                flash(f'Код "{cover.code}" уже существует!', 'danger')
                return render_template('add_cover.html', form=form)

            db.session.add(cover)
            db.session.commit()
            flash('Тип переплета успешно добавлен!', 'success')
            return redirect(url_for('main.cover_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении типа переплета: {str(e)}', 'danger')

    return render_template('add_cover.html', form=form)


@bp.route('/cover/<int:cover_id>/card')
def cover_card(cover_id):
    cover = Cover.query.get_or_404(cover_id)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    return_page = request.args.get('return_page', 1, type=int)

    # Пагинация для книг с этим переплетом
    books_query = Book.query.filter_by(
        id_cover=cover_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_COVER,
        error_out=False
    )

    return render_template('cover_card.html',
                           cover=cover,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           return_page=return_page)


@bp.route('/genre/<int:genre_id>/card')
def genre_card(genre_id):
    genre = Genre.query.get_or_404(genre_id)
    page = request.args.get('page', 1, type=int)

    # Получаем параметры для возврата
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Получаем книги этого жанра через связь many-to-many
    # Используем подзапрос для пагинации
    books_query = Book.query.join(book_genres).filter(
        book_genres.c.id_genre == genre_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('genre_card.html',
                           genre=genre,
                           books=pagination.items,
                           pagination=pagination,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/author/<int:author_id>/view')
def author_view(author_id):
    author = Author.query.get_or_404(author_id)
    page = request.args.get('page', 1, type=int)
    book_id = request.args.get('book_id', type=int)

    # Получаем книги автора с пагинацией
    books_query = Book.query.join(book_authors).filter(
        book_authors.c.id_author == author_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('author_card_view.html',
                           author=author,
                           books=pagination.items,
                           pagination=pagination,
                           book_id=book_id)


@bp.route('/publisher/<int:publisher_id>/view')
def publisher_view(publisher_id):
    publisher = Publisher.query.get_or_404(publisher_id)
    page = request.args.get('page', 1, type=int)

    # Получаем книги издателя с пагинацией
    books_query = Book.query.join(book_publishers).filter(
        book_publishers.c.id_publisher == publisher_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('publisher_card_view.html',
                           publisher=publisher,
                           books=pagination.items,
                           pagination=pagination)


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


@bp.route('/search/formats_ajax')
def search_formats_ajax():
    """Поиск форматов для HTMX и модальных окон (возвращает HTML)"""
    query = request.args.get('q', '').strip()

    if len(query) < 1:
        return '<div class="text-muted p-3">Введите формат для поиска.</div>'

    formats = Format.query.filter(
        Format.format.ilike(f'%{query}%')
    ).limit(10).all()

    if not formats:
        return '<div class="text-muted p-3">Форматы не найдены.</div>'

    html = ''.join([
        f'<a href="#" class="list-group-item list-group-item-action" data-id="{fmt.id}" data-name="{fmt.format}">'
        f'<div class="d-flex w-100 justify-content-between">'
        f'<h6 class="mb-1">{fmt.format}</h6>'
        f'<small>{fmt.height or "?"}x{fmt.width or "?"} мм</small>'
        f'</div>'
        f'</a>'
        for fmt in formats
    ])
    return html

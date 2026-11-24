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
    book_authors,
)
from app.main.forms import (
    FormAuthor,
)
from app.authors import bp

from app.main.misc import get_html
from config import Config


#author_list
#add_author
#edit_author
#delete_author
#select_authors
#search_authors
#add_author_to_book_session
#remove_author_from_book_session
#save_authors_changes
#cancel_authors_changes
#author_card
#author_view


@bp.route('/authors')
def author_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Общее число авторов в БД — не зависит от поиска
    total_authors = Author.query.count()

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

    context = dict(
        authors=pagination.items,
        pagination=pagination,
        total_authors=total_authors,
        search=search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/author_grid.html', **context)

    return render_template('author_list.html', **context)


@bp.route('/author/add', methods=['GET', 'POST'])
def add_author():
    form = FormAuthor()

    if form.validate_on_submit():
        try:
            author = Author()

            # Не даём populate_obj затащить FileStorage в author.photo
            # (photo — LargeBinary, ждёт bytes или None)
            form.photo.data = None
            form.populate_obj(author)

            author.fio = (
                f"{author.lastname} "
                f"{author.firstname or ''} "
                f"{author.secondname or ''}"
            ).strip()

            # Обработка загрузки фото:
            # для новой записи, если файл не выбран — author.photo = None
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    author.photo = file.read()

            db.session.add(author)
            db.session.commit()

            flash('Автор успешно добавлен!', 'success')
            return redirect(
                url_for('authors.select_authors',
                        book_id=request.args.get('book_id', 0))
            )
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении автора: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Неожиданная ошибка: {str(e)}', 'danger')

    return render_template('add_author.html',
                           form=form,
                           book_id=request.args.get('book_id', 0))


@bp.route('/author/<int:author_id>/edit', methods=['GET', 'POST'])
def edit_author(author_id):
    author = Author.query.get_or_404(author_id)
    form = FormAuthor(obj=author)

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
            # 1) Запоминаем текущее фото из БД (bytes или None)
            current_photo = author.photo

            # 2) Не даём populate_obj затащить FileStorage в author.photo
            form.photo.data = None
            form.populate_obj(author)

            author.fio = (
                f"{author.lastname} "
                f"{author.firstname or ''} "
                f"{author.secondname or ''}"
            ).strip()

            # 3) Фото: новый файл — заменяем, иначе — восстанавливаем старое
            new_file = request.files.get('photo')
            if new_file and new_file.filename:
                author.photo = new_file.read()
            else:
                author.photo = current_photo   # ← сохраняем существующее

            db.session.commit()
            flash('Автор успешно обновлен!', 'success')
            return redirect(url_for('authors.author_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении автора: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Неожиданная ошибка: {str(e)}', 'danger')

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
    return redirect(url_for('authors.author_list', page=page))

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
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/author/<int:author_id>/view')
def author_view(author_id):
    author = Author.query.get_or_404(author_id)
    books_page = request.args.get('books_page', 1, type=int)
    book_id = request.args.get('book_id', type=int)
    # Получаем параметры для возврата
    return_to = request.args.get('return_to')
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')
    return_page = request.args.get('return_page', 1, type=int)

    # Получаем книги автора с пагинацией
    books_query = Book.query.join(book_authors).filter(
        book_authors.c.id_author == author_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=books_page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('author_card_view.html',
                           author=author,
                           books=pagination.items,
                           pagination=pagination,
                           book_id=book_id,
                           return_to=return_to,
                           books_page=books_page,
                           search=search,
                           author_search=author_search,
                           interpreter_search=interpreter_search,
                           genre_search=genre_search,
                           return_page=return_page)



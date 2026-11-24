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
    Publisher,
    book_publishers,
)
from app.main.forms import (
    FormPublisher,
)
from app.publishers import bp

from app.main.misc import get_html
from config import Config


#publisher_list
#add_publisher
#edit_publisher
#delete_publisher
#select_publishers
#search_publishers
#add_publisher_to_book_session
#remove_publisher_from_book_session
#save_publishers_changes
#cancel_publishers_changes
#publisher_card
#publisher_view


@bp.route('/publishers')
def publisher_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Всего издателей в БД — не зависит от поиска
    total_publishers = Publisher.query.count()

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
    context = dict(
        publishers=pagination.items,
        pagination=pagination,
        total_publishers=total_publishers,
        search=search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/publisher_grid.html', **context)

    return render_template('publisher_list.html', **context)


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

            book_id = request.args.get('book_id', type=int)
            if book_id:
                book = Book.query.get(book_id)
                if book:
                    return redirect(url_for(
                        'publishers.select_publishers', book_id=book_id))

            # Иначе — в общий список издателей
            return redirect(url_for('publishers.publisher_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении издателя: {str(e)}', 'danger')

    return render_template('add_publisher.html', form=form, book_id=request.args.get('book_id', 0))


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
            return redirect(url_for('publishers.publisher_list'))
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
    return redirect(url_for('publishers.publisher_list', page=page))


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


@bp.route('/publisher/<int:publisher_id>/card')
def publisher_card(publisher_id):
    publisher = Publisher.query.get_or_404(publisher_id)
    page = request.args.get('page', 1, type=int)

    # Получаем параметры для возврата
    search = request.args.get('search', '')
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', '')

    # Получаем книги автора с пагинацией
    books_query = Book.query.join(book_publishers).filter(
        book_publishers.c.id_publisher == publisher_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('publisher_card.html',
                           publisher=publisher,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/publisher/<int:publisher_id>/view')
def publisher_view(publisher_id):
    publisher = Publisher.query.get_or_404(publisher_id)
    books_page = request.args.get('books_page', 1, type=int)
    book_id = request.args.get('book_id', type=int)
    # Получаем параметры для возврата
    return_to = request.args.get('return_to')
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')
    return_page = request.args.get('return_page', 1, type=int)

    # Получаем книги издателя с пагинацией
    books_query = Book.query.join(book_publishers).filter(
        book_publishers.c.id_publisher == publisher_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=books_page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('publisher_card_view.html',
                           publisher=publisher,
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



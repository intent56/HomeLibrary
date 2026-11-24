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
    Genre,
    book_genres,
)
from app.main.forms import (
    FormGenre,
)
from app.genres import bp

from app.main.misc import get_html
from config import Config


#genre_list
#add_genre
#edit_genre
#delete_genre
#select_genres
#search_genres
#add_genre_to_book_session
#remove_genre_from_book_session
#save_genres_changes
#cancel_genres_changes
#genre_card
#genre_view


@bp.route('/genres')
def genre_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Общее число жанров в БД — не зависит от поиска
    total_genres = Genre.query.count()

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

    context = dict(
        genres=pagination.items,
        pagination=pagination,
        total_genres=total_genres,
        search=search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/genre_grid.html', **context)

    return render_template('genre_list.html', **context)


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
            book_id = request.args.get('book_id', type=int)
            if book_id:
                book = Book.query.get(book_id)
                if book:
                    return redirect(url_for(
                        'genres.select_genres', book_id=book_id))

            # Иначе — в общий список жанров
            return redirect(url_for('genres.genre_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении жанра: {str(e)}', 'danger')

    return render_template('add_genre.html', form=form, book_id=request.args.get('book_id', 0))


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
            return redirect(url_for('genres.genre_list'))
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
    return redirect(url_for('genres.genre_list', page=page))


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
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/genre/<int:genre_id>/view')
def genre_view(genre_id):
    genre = Genre.query.get_or_404(genre_id)
    books_page = request.args.get('books_page', 1, type=int)
    book_id = request.args.get('book_id', type=int)

    # Получаем параметры для возврата
    return_to = request.args.get('return_to')
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')
    return_page = request.args.get('return_page', 1, type=int)

    # Получаем книги данного жанра с пагинацией
    books_query = Book.query.join(book_genres).filter(
        book_genres.c.id_genre == genre_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=books_page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('genre_card_view.html',
                           genre=genre,
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



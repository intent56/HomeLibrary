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
    Interpreter,
    Language,
    book_interpreters,
)
from app.main.forms import (
    FormInterpreter,
)
from app.interpreters import bp

from app.main.misc import get_html
from config import Config


#interpreter_list
#add_interpreter
#edit_interpreter
#delete_interpreter
#select_interpreters
#search_interpreters
#add_interpreter_to_book_session
#remove_interpreter_from_book_session
#save_interpreters_changes
#cancel_interpreters_changes
#interpreter_card
#interpreter_view


@bp.route('/interpreters')
def interpreter_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Всего переводчиков в БД — не зависит от поиска
    total_interpreters = Interpreter.query.count()

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

    context = dict(
        interpreters=pagination.items,
        pagination=pagination,
        total_interpreters=total_interpreters,
        search=search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/interpreter_grid.html', **context)

    return render_template('interpreter_list.html', **context)


@bp.route('/interpreter/add', methods=['GET', 'POST'])
def add_interpreter():
    form = FormInterpreter()

    if form.validate_on_submit():
        try:
            interpreter = Interpreter()
            # Сбрасываем FileField перед populate_obj
            form.photo.data = None
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
           # Возврат: в выбор переводчиков для книги — только если book_id валиден
            book_id = request.args.get('book_id', type=int)
            if book_id:
                book = Book.query.get(book_id)
                if book:
                    return redirect(url_for(
                        'interpreters.select_interpreters', book_id=book_id))

            # Иначе — в общий список переводчиков
            return redirect(url_for('interpreters.interpreter_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении переводчика: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Неожиданная ошибка: {str(e)}', 'danger')

    languages = Language.query.order_by(Language.name).all()
    return render_template('add_interpreter.html', form=form,
                           book_id=request.args.get('book_id', 0),
                           languages=languages)


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

    # Все языки из справочника — для вкладки «Языки»
    all_languages = Language.query.order_by(Language.name).all()

    # ID языков, уже связанных с переводчиком — для предустановки чекбоксов
    # при GET-запросе (и для восстановления при ошибке валидации)
    if request.method == 'GET':
        selected_language_ids = {l.id for l in interpreter.lang_interpreters}
    else:
        # При POST берём то, что пришло в форме (если форма не прошла валидацию,
        # нужно показать введённое пользователем, а не из БД)
        selected_language_ids = set(
            request.form.getlist('language_ids', type=int)
        )

    if form.validate_on_submit():
        try:
            # --- Фото: сохраняем текущее, если новый файл не выбран ---
            current_photo = interpreter.photo
            form.photo.data = None
            form.populate_obj(interpreter)

            interpreter.fio = (
                f"{interpreter.lastname} "
                f"{interpreter.firstname or ''} "
                f"{interpreter.secondname or ''}"
            ).strip()

            new_file = request.files.get('photo')
            if new_file and new_file.filename:
                interpreter.photo = new_file.read()
            else:
                interpreter.photo = current_photo

            # --- Языки: синхронизируем связи в этой же транзакции ---
            new_language_ids = set(
                request.form.getlist('language_ids', type=int)
            )
            current_language_ids = {
                l.id for l in interpreter.lang_interpreters}

            # Удаляем отвязанные
            for lang in list(interpreter.lang_interpreters):
                if lang.id not in new_language_ids:
                    interpreter.lang_interpreters.remove(lang)

            # Добавляем новые
            ids_to_add = new_language_ids - current_language_ids
            if ids_to_add:
                languages = Language.query.filter(
                    Language.id.in_(ids_to_add)).all()
                interpreter.lang_interpreters.extend(languages)

            db.session.commit()
            flash('Переводчик успешно обновлен!', 'success')
            return redirect(url_for('interpreters.interpreter_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении переводчика: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Неожиданная ошибка: {str(e)}', 'danger')

    return render_template('edit_interpreter.html',
                           form=form,
                           interpreter=interpreter,
                           books=pagination.items,
                           pagination=pagination,
                           all_languages=all_languages,
                           selected_language_ids=selected_language_ids,
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
    return redirect(url_for('interpreters.interpreter_list', page=page))


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
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/interpreter/<int:interpreter_id>/view')
def interpreter_view(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    books_page = request.args.get('books_page', 1, type=int)
    book_id = request.args.get('book_id', type=int)

    # Получаем параметры для возврата
    return_to = request.args.get('return_to')
    search = request.args.get('search', '')
    author_search = request.args.get('author_search', '')
    interpreter_search = request.args.get('interpreter_search', '')
    genre_search = request.args.get('genre_search', '')
    return_page = request.args.get('return_page', 1, type=int)

    # Получаем книги переводчика с пагинацией
    books_query = Book.query.join(book_interpreters).filter(
        book_interpreters.c.id_interpreter == interpreter_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=books_page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('interpreter_card_view.html',
                           interpreter=interpreter,
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



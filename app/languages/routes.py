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
    Language,
    Interpreter,
    interpreter_languages,
)
from app.main.forms import (
    FormLanguage,
)
from app.languages import bp

from app.main.misc import get_html
from config import Config


#language_list
#add_language
#edit_language
#delete_language
#select_languages
#search_languages
#add_language_to_book
#remove_language_from_book
#language_card
#language_view

#select_interpreter_languages
#search_interpreter_languages
#add_language_to_interpreter
#remove_language_from_interpreter
#search_languages_ajax


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
                        'languages.select_languages', book_id=book_id))
            # Иначе — в общий список языков
            return redirect(url_for('languages.language_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении языка: {str(e)}', 'danger')

    return render_template('add_language.html', form=form, book_id=request.args.get('book_id', 0))


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
            return redirect(url_for('languages.language_list'))
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
    return redirect(url_for('languages.language_list', page=page))


@bp.route('/book/<int:book_id>/languages', methods=['GET'])
def select_languages(book_id):
    book = Book.query.get_or_404(book_id)
    selected_languages = book.language_books
    return render_template('select_languages.html', book=book, selected_languages=selected_languages)


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

    return redirect(url_for('languages.select_languages', book_id=book_id))


@bp.route('/book/<int:book_id>/languages/remove/<int:language_id>', methods=['POST'])
def remove_language_from_book(book_id, language_id):
    book = Book.query.get_or_404(book_id)
    language = Language.query.get_or_404(language_id)

    if language in book.language_books:
        book.language_books.remove(language)
        db.session.commit()
        flash(f'Язык {language.name} удален из книги', 'info')

    return redirect(url_for('languages.select_languages', book_id=book_id))


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


@bp.route('/interpreter/<int:interpreter_id>/languages', methods=['GET'])
def select_interpreter_languages(interpreter_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    selected_languages = interpreter.lang_interpreters
    return render_template('select_interpreter_languages.html',
                           interpreter=interpreter,
                           selected_languages=selected_languages)


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

    return redirect(url_for('languages.select_interpreter_languages', interpreter_id=interpreter_id))


@bp.route('/interpreter/<int:interpreter_id>/languages/remove/<int:language_id>', methods=['POST'])
def remove_language_from_interpreter(interpreter_id, language_id):
    interpreter = Interpreter.query.get_or_404(interpreter_id)
    language = Language.query.get_or_404(language_id)

    if language in interpreter.lang_interpreters:
        interpreter.lang_interpreters.remove(language)
        db.session.commit()
        flash(f'Язык {language.name} удален у переводчика', 'info')

    return redirect(url_for('languages.select_interpreter_languages', interpreter_id=interpreter_id))


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



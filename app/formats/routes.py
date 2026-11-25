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
from app.formats import bp

from app.main.misc import get_html
from config import Config


#cover_list
#add_cover
#edit_cover
#delete_cover
#search_formats_ajax
#cover_card
#cover_view

@bp.route('/formats')
def format_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # Всего переводчиков в БД — не зависит от поиска
    total_formats = Format.query.count()

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

    total_books_with_formats = sum(len(f.fmt_books)
                                   for f in Format.query.all())

    context = dict(
        formats=pagination.items,
        pagination=pagination,
        total_formats=total_formats,
        total_books_with_formats=total_books_with_formats,
        search=search,
    )

    if request.headers.get('HX-Request'):
        return render_template('partials/format_table.html', **context)

    return render_template('format_list.html', **context)


@bp.route('/format/add', methods=['GET', 'POST'])
def add_format():
    form = FormFormat()

    if form.validate_on_submit():
        try:
            format = Format()
            form.populate_obj(format)
            db.session.add(format)
            db.session.commit()
            flash('Формат успешно добавлен!', 'success')
            return redirect(url_for('formats.format_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении формата: {str(e)}', 'danger')

    return render_template('add_format.html', form=form)


@bp.route('/format/<int:format_id>/edit', methods=['GET', 'POST'])
def edit_format(format_id):
    format = Format.query.get_or_404(format_id)
    form = FormFormat(obj=format)

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
            form.populate_obj(format)
            db.session.commit()
            flash('Формат успешно обновлен!', 'success')
            return redirect(url_for('formats.format_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении формата: {str(e)}', 'danger')

    return render_template('edit_format.html',
                           form=form,
                           format=format,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           search=search,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/format/<int:format_id>/delete', methods=['POST'])
def delete_format(format_id):
    format = Format.query.get_or_404(format_id)
    try:
        # Проверяем, есть ли книги с этим форматом
        if format.fmt_books:
            flash(
                f'Невозможно удалить формат "{format.format}", так как он используется в {len(format.fmt_books)} книгах!', 'danger')
            return redirect(url_for('formats.format_list'))

        db.session.delete(format)
        db.session.commit()
        flash('Формат успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении формата: {str(e)}', 'danger')

    page = request.args.get('page', 1, type=int)
    return redirect(url_for('formats.format_list', page=page))


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


@bp.route('/format/<int:format_id>/card')
def format_card(format_id):
    format = Format.query.get_or_404(format_id)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    return_page = request.args.get('return_page', 1, type=int)
    return_search = request.args.get('return_search', 1, type=int)

    # Пагинация для книг с этим переплетом
    books_query = Book.query.filter_by(
        id_format=format_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('format_card.html',
                           format=format,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           return_page=return_page,
                           return_search=return_search)


@bp.route('/format/<int:format_id>/view')
def format_view(format_id):
    format_obj = Format.query.get_or_404(format_id)
    page = request.args.get('page', 1, type=int)
    return_page = request.args.get('return_page', 1, type=int)

    # Пагинация для книг этого формата
    books_query = Book.query.filter_by(
        id_format=format_obj.id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('format_card_view.html',
                           format=format_obj,
                           books=pagination.items,
                           pagination=pagination,
                           return_page=return_page)



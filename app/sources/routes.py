import io
from datetime import datetime
import requests
import time
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
import urllib.parse

from app.sources import bp

from app.main.misc import get_html
from config import Config


#source_list
#add_source
#edit_source
#delete_source
#toggle_source_htmx
#delete_source_htmx

#get_sources
#universal_search
#search_google_books
#search_google_books_by_title
#search_open_library
#search_books_universal
#search_authors_universal
#search_interpreters_universal
#search_google_books_api
#search_open_library_api
#search_author_google_books
#search_author_open_library
#search_interpreter_google_books
#autocomplete_authors
#autocomplete_publishers
#autocomplete_genres
#autocomplete_languages


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



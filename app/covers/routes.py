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
from app.covers import bp

from app.main.misc import get_html
from config import Config


#cover_list
#add_cover
#edit_cover
#delete_cover
#cover_card
#cover_view


@bp.route('/covers')
def cover_list():
    covers = Cover.query.order_by(Cover.name).all()
    total_covers = Cover.query.count()
    total_books_with_covers = sum(len(cover.cvr_books) for cover in covers)
    return render_template('cover_list.html',
                           covers=covers,
                           total_covers=total_covers,
                           total_books_with_covers=total_books_with_covers)


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
            return redirect(url_for('covers.cover_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении типа переплета: {str(e)}', 'danger')

    return render_template('add_cover.html', form=form)


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
            return redirect(url_for('covers.cover_list'))
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
            return redirect(url_for('covers.cover_list'))

        db.session.delete(cover)
        db.session.commit()
        flash('Тип переплета успешно удален!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении типа переплета: {str(e)}', 'danger')

    return redirect(url_for('covers.cover_list'))


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
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('cover_card.html',
                           cover=cover,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           return_page=return_page)


@bp.route('/cover/<int:cover_id>/view')
def cover_view(cover_id):
    cover = Cover.query.get_or_404(cover_id)

    # Получаем параметры для возврата
    page = request.args.get('page', 1, type=int)
    return_page = request.args.get('return_page', 1, type=int)

    # Пагинация для книг с этим переплетом
    books_query = Book.query.filter_by(
        id_cover=cover_id).order_by(Book.name.asc())
    pagination = books_query.paginate(
        page=page,
        per_page=Config.ITEMS_PER_PAGE_BOOK,
        error_out=False
    )

    return render_template('cover_card_view.html',
                           cover=cover,
                           books=pagination.items,
                           pagination=pagination,
                           page=page,
                           return_page=return_page)



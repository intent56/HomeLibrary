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
    Aggregator,
)
from app.main.forms import (
    FormAggregator,
)
from app.aggregators import bp

from app.main.misc import get_html
from config import Config


#aggregator_list
#add_aggregator
#edit_aggregator
#toggle_aggregator
#toggle_aggregator_htmx
#delete_aggregator_htmx


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
            return redirect(url_for('aggregators.aggregator_list'))
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
            return redirect(url_for('aggregators.aggregator_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении агрегатора: {str(e)}', 'danger')

    return render_template('edit_aggregator.html', form=form, aggregator=aggregator)


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

    return redirect(url_for('aggregators.aggregator_list'))


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



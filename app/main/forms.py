from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SubmitField, SelectField, FloatField, HiddenField, BooleanField, FileField
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    URL,
)

from flask_wtf.file import FileAllowed

from app.models.main import (
    Book,
    Author,
    Genre,
    Cover,
    Publisher,
    Format,
    Language,
    Interpreter,
    Source,
)


class FormAuthor(FlaskForm):
    lastname = StringField(
        "Фамилия", validators=[InputRequired(), Length(min=1, max=100)]
    )
    firstname = StringField("Имя")
    secondname = StringField("Отчество")
    ref_author = StringField("Ссылка")
    comment = TextAreaField("Комментарий")
    photo = FileField('Фото автора', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения!')])
    submit = SubmitField("Добавить")

    def validate(self, extra_validators=None):
        if not super().validate():
            return False
        initial_validation = super().validate(extra_validators)
        if not initial_validation:
            return False
        
        # Автоматически формируем ФИО
        fio_parts = [self.lastname.data]
        if self.firstname.data:
            fio_parts.append(self.firstname.data)
        if self.secondname.data:
            fio_parts.append(self.secondname.data)
        self.fio = ' '.join(fio_parts)
        return True


class FormInterpreter(FlaskForm):
    lastname = StringField(
        "Фамилия", validators=[InputRequired(), Length(min=1, max=100)]
    )
    firstname = StringField("Имя")
    secondname = StringField("Отчество")
    ref_interpreter = StringField("Ссылка")
    comment = TextAreaField("Комментарий")
    photo = FileField('Фото переводчика', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Только изображения!')])
    submit = SubmitField("Добавить")

    def validate(self, extra_validators=None):
        if not super().validate():
            return False
        initial_validation = super().validate(extra_validators)
        if not initial_validation:
            return False
            
        # Автоматически формируем ФИО
        fio_parts = [self.lastname.data]
        if self.firstname.data:
            fio_parts.append(self.firstname.data)
        if self.secondname.data:
            fio_parts.append(self.secondname.data)
        self.fio = ' '.join(fio_parts)
        return True


class FormPublisher(FlaskForm):
    name = StringField("Название", validators=[InputRequired(), Length(min=1, max=100)])
    ref_publisher = StringField("Ссылка")
    comment = TextAreaField("Комментарий")
    submit = SubmitField("Добавить")


class FormFormat(FlaskForm):
    format = StringField("Название", validators=[InputRequired(), Length(min=1, max=50)])
    height = IntegerField("Высота", validators=[NumberRange(min=0, max=999)])
    width = IntegerField("Ширина", validators=[NumberRange(min=0, max=999)])
    comment = TextAreaField("Комментарий")
    submit = SubmitField("Добавить")


class FormLanguage(FlaskForm):
    code = StringField("Код", validators=[InputRequired(), Length(min=3, max=3)])
    name = StringField("Название", validators=[InputRequired(), Length(min=1, max=100)])
    comment = TextAreaField("Комментарий")
    submit = SubmitField("Добавить")


class FormCover(FlaskForm):
    code = StringField("Код", validators=[InputRequired(), Length(min=3, max=3)])
    name = StringField("Название", validators=[InputRequired(), Length(min=1, max=100)])
    comment = TextAreaField("Комментарий")
    submit = SubmitField("Добавить")


class FormGenre(FlaskForm):
    name = StringField("Название", validators=[InputRequired(), Length(min=1, max=100)])
    comment = TextAreaField("Комментарий")
    submit = SubmitField("Добавить")


class FormBook(FlaskForm):
    name = StringField(
        "Название", validators=[InputRequired(), Length(min=1, max=100)]
    )
    fullname = TextAreaField('Полное название')
    location = StringField('Местоположение', validators=[DataRequired(), Length(max=100)])
    summary = TextAreaField('Аннотация')
    content = TextAreaField('Содержание')
    seria_global = StringField('Глобальная серия', validators=[Length(max=100)])
    seria_local = StringField('Серия', validators=[Length(max=100)])
    edition = StringField('Издание', validators=[Length(max=100)])
    year_edition = IntegerField('Год издания', validators=[Optional()])
    id_cover = SelectField('Переплет', coerce=int, validators=[Optional()])
    id_format = SelectField('Формат', coerce=int, validators=[Optional()])
    id_language = SelectField('Язык оригинала книги', coerce=int, validators=[Optional()])
    circulation = IntegerField('Тираж', validators=[Optional()])
    pages = IntegerField('Число страниц', validators=[Optional()])
    barcode = StringField('Штрих код', validators=[Length(max=100)])
    isbn = StringField('ISBN', validators=[Length(max=50)])
    price = FloatField('Цена', validators=[Optional()])
    cover = FileField('Обложка книги', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Только изображения!')])
    add_info = TextAreaField('Дополнительная информация')
    authors = HiddenField('Авторы')
    submit = SubmitField('Сохранить книгу')

    
class FormSource(FlaskForm):
    name = StringField('Название источника', validators=[DataRequired(), Length(max=100)])
    code = StringField('Код источника', validators=[DataRequired(), Length(max=50)])
    url = StringField('URL', validators=[Optional(), URL(), Length(max=255)])
    is_active = BooleanField('Активен', default=True)
    chk_books = BooleanField('Поиск книг', default=True)
    chk_authors = BooleanField('Поиск авторов', default=True)
    chk_interpreters = BooleanField('Поиск переводчиков', default=True)
    comment = TextAreaField('Комментарий', validators=[Optional()])
    submit = SubmitField('Сохранить источник')


class FormAggregator(FlaskForm):
    name = StringField('Название агрегатора', validators=[DataRequired(), Length(max=100)])
    code = StringField('Код агрегатора', validators=[DataRequired(), Length(max=50)])
    url_template = StringField('Шаблон URL', validators=[DataRequired(), Length(max=255)])
    icon = StringField('Иконка (Bootstrap)', validators=[Optional(), Length(max=50)])
    is_active = BooleanField('Активен', default=True)
    search_type = SelectField('Тип поиска', choices=[
        ('standard', 'Стандартный (открытие URL)'),
        ('redirect', 'Редирект с перекодировкой')
    ], default='standard')
    comment = TextAreaField('Комментарий', validators=[Optional()])
    submit = SubmitField('Сохранить агрегатор')    
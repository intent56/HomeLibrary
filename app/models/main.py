from typing import List

from sqlalchemy import Integer, String, Numeric, Text, ForeignKey, Column, LargeBinary, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


# book_authors Книги и их авторы
book_authors = db.Table(
    "book_authors",
    Column("id_book", ForeignKey("books.id"), primary_key=True),
    Column("id_author", ForeignKey("authors.id"), primary_key=True),
)


# book_interpreters Книги и их переводчики
book_interpreters = db.Table(
    "book_interpreters",
    Column("id_book", ForeignKey("books.id"), primary_key=True),
    Column("id_interpreter", ForeignKey("interpreters.id"), primary_key=True),
)


# book_genres Книги и их жанры
book_genres = db.Table(
    "book_genres",
    Column("id_book", ForeignKey("books.id"), primary_key=True),
    Column("id_genre", ForeignKey("genres.id"), primary_key=True),
)

# book_publishers Книги и их издатели
book_publishers = db.Table(
    "book_publishers",
    Column("id_book", ForeignKey("books.id"), primary_key=True),
    Column("id_publisher", ForeignKey("publishers.id"), primary_key=True),
)


# interpreter_languages Переводчики и их языки
interpreter_languages = db.Table(
    "interpreter_languages",
    Column("id_interpreter", ForeignKey("interpreters.id"), primary_key=True),
    Column("id_language", ForeignKey("languages.id"), primary_key=True),
)


# publishers Справочник издателей книг
class Publisher(db.Model):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # Название издательства
    ref_publisher: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Ссылка на информацию об издателе
    comment: Mapped[str] = mapped_column(String, nullable=True)  # Комментарий
    about: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)  # Об издателе
    about_mime: Mapped[str] = mapped_column(String, nullable=True)  # mime-type about
    book_publishers: Mapped[List["Book"]] = relationship(
        secondary=book_publishers,
        back_populates="publisher_books",
    )

    def __repr__(self):
        return "Publisher('{0}')".format(self.name)


# formats Справочник форматов книг
class Format(db.Model):
    __tablename__ = "formats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    format: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )  # Код формата
    height: Mapped[int] = mapped_column(Integer, nullable=True)  # Высота страницы
    width: Mapped[int] = mapped_column(Integer, nullable=True)  # Ширина страницы
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # Комментарий
    fmt_books: Mapped[List["Book"]] = relationship(back_populates="fmt")

    def __repr__(self):
        return "Format('{0}')".format(self.format)


# genres Справочник жанров книг
class Genre(db.Model):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # Название жанра
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # Комментарий
    book_genres: Mapped[List["Book"]] = relationship(
        secondary=book_genres,
        back_populates="genre_books",
    )

    def __repr__(self):
        return "Genre('{0}')".format(self.name)


# covers Справочник переплетов книг
class Cover(db.Model):
    __tablename__ = "covers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # Код типа переплета
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # Название типа переплета
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # Комментарий
    cvr_books: Mapped[List["Book"]] = relationship(back_populates="cvr")

    def __repr__(self):
        return "Cover('{0}')".format(self.name)


# languages Справочник языков книг
class Language(db.Model):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # Код языка
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # Название языка
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # Комментарий
    lang_books: Mapped[List["Book"]] = relationship(back_populates="lang")
    interpreter_langs: Mapped[List["Interpreter"]] = relationship(
        secondary=interpreter_languages,
        back_populates="lang_interpreters",
    )

    def __repr__(self):
        return "Language('{0}'.'{1}')".format(self.code, self.name)


# authors Справочник авторов книг
class Author(db.Model):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    lastname: Mapped[str] = mapped_column(String(100), nullable=False)  # Фамилия
    firstname: Mapped[str] = mapped_column(String(100), nullable=True)  # Имя
    secondname: Mapped[str] = mapped_column(String(100), nullable=True)  # Отчество
    fio: Mapped[str] = mapped_column(Text, nullable=False)  # ФИО
    ref_author: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Ссылка на информацию об авторе
    ref_photo: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Ссылка на файл с фото
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # Комментарий
    photo: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    about: Mapped[str] = mapped_column(Text, nullable=True)  # Об авторе
    about_mime: Mapped[str] = mapped_column(String, nullable=True)  # mime-type about
    book_authors: Mapped[List["Book"]] = relationship(
        secondary=book_authors,
        back_populates="author_books",
    )

    def __repr__(self):
        return "Author('{0}','{1}')".format(self.lastname, self.fio)


# interpreters Справочник переводчиков книг
class Interpreter(db.Model):
    __tablename__ = "interpreters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    lastname: Mapped[str] = mapped_column(String(100), nullable=False)  # Фамилия
    firstname: Mapped[str] = mapped_column(String(100), nullable=True)  # Имя
    secondname: Mapped[str] = mapped_column(String(100), nullable=True)  # Отчество
    fio: Mapped[str] = mapped_column(Text, nullable=False)  # ФИО
    ref_interpreter: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Ссылка на информацию о переводчике
    ref_photo: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Ссылка на файл с фото
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # Комментарий
    photo: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    about: Mapped[str] = mapped_column(Text, nullable=True)  # О переводчике
    about_mime: Mapped[str] = mapped_column(String, nullable=True)  # mime-type about
    book_interpreters: Mapped[List["Book"]] = relationship(
        secondary=book_interpreters,
        back_populates="interpreter_books",
    )
    lang_interpreters: Mapped[List["Language"]] = relationship(
        secondary=interpreter_languages,
        back_populates="interpreter_langs",
    )

    def __repr__(self):
        return "Interpreter('{0}','{1}')".format(self.lastname, self.fio)


# books Список книг
class Book(db.Model):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Идентификатор
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Название
    fullname: Mapped[str] = mapped_column(Text, nullable=True)  # Полное название
    location: Mapped[str] = mapped_column(String(100), nullable=False)  # Местоположение
    summary: Mapped[str] = mapped_column(Text, nullable=True)  # Аннотация
    content: Mapped[str] = mapped_column(Text, nullable=True)  # Содержание
    seria_global: Mapped[str] = mapped_column(
        String(100), nullable=True
    )  # Глобальная серия
    seria_local: Mapped[str] = mapped_column(String(100), nullable=True)  # Серия
    edition: Mapped[str] = mapped_column(String(100), nullable=True)  # Издание
    year_edition: Mapped[int] = mapped_column(Integer, nullable=True)  # Год издания
    id_cover: Mapped[int] = mapped_column(
        Integer, ForeignKey(column="covers.id"), nullable=True
    )  # Переплет
    id_format: Mapped[int] = mapped_column(
        Integer, ForeignKey(column="formats.id"), nullable=True
    )  # Формат
    id_language: Mapped[int] = mapped_column(
        Integer, ForeignKey(column="languages.id"), nullable=True
    )  # Язык оригинала книги
    circulation: Mapped[int] = mapped_column(Integer, nullable=True)  # Тираж
    pages: Mapped[int] = mapped_column(Integer, nullable=True)  # Число страниц
    barcode: Mapped[str] = mapped_column(String(100), nullable=True)  # Штрих код
    isbn: Mapped[str] = mapped_column(String(50), nullable=True)  # ISBN
    price: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)  # Цена
    cover_file: Mapped[str] = mapped_column(
        String(100), nullable=True
    )  # Ссылка на файл обложки
    cover: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)  # Файл обложки
    add_info: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Дополнительная информация
    ref_url: Mapped[str] = mapped_column(Text, nullable=True)  # Ссылка на файл описания
    id_trans: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # id файла cvs (вспомогательное поле)
    cvr: Mapped["Cover"] = relationship(
        back_populates="cvr_books"
    )  # Взаимосвязь между книгами и материалом обложек
    fmt: Mapped["Format"] = relationship(
        back_populates="fmt_books"
    )  # Взаимосвязь между книгами и их форматами
    lang: Mapped["Language"] = relationship(
        back_populates="lang_books"
    )  # Взаимосвязь между книгами и языком оригиналов книг
    author_books: Mapped[List["Author"]] = relationship(
        secondary=book_authors,
        back_populates="book_authors",
    )
    interpreter_books: Mapped[List["Interpreter"]] = relationship(
        secondary=book_interpreters,
        back_populates="book_interpreters",
    )
    genre_books: Mapped[List["Genre"]] = relationship(
        secondary=book_genres,
        back_populates="book_genres",
    )
    publisher_books: Mapped[List["Publisher"]] = relationship(
        secondary=book_publishers,
        back_populates="book_publishers",
    )

    def __repr__(self):
        return "Book('{0}','{1}')".format(self.name, self.location)

# Источники информации в Интернете
class Source(db.Model):
    __tablename__ = "sources"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    chk_books: Mapped[bool] = mapped_column(Boolean, default=True)
    chk_authors: Mapped[bool] = mapped_column(Boolean, default=True)
    chk_interpreters: Mapped[bool] = mapped_column(Boolean, default=True)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(20), nullable=True)
    
    def __repr__(self):
        return f"Source('{self.name}','{self.code}')"


class Aggregator(db.Model):
    __tablename__ = "aggregators"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    url_template: Mapped[str] = mapped_column(String(255), nullable=False)  # Шаблон URL с {query}
    icon: Mapped[str] = mapped_column(String(50), nullable=True)  # Иконка Bootstrap
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    search_type: Mapped[str] = mapped_column(String(20), default='standard')  # 'standard' или 'redirect'
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(20), nullable=True)
    
    def __repr__(self):
        return f"Aggregator('{self.name}','{self.code}')"
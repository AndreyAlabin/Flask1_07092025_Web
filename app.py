from flask import Flask, jsonify, request, abort
from random import choice
from http import HTTPStatus
from pathlib import Path
from werkzeug.exceptions import HTTPException
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from flask_migrate import Migrate


class Base(DeclarativeBase):
    pass

BASE_DIR = Path(__file__).parent

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BASE_DIR/"quotes.db"}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.json.ensure_ascii = False

db = SQLAlchemy(model_class=Base)
db.init_app(app)
migrate = Migrate(app, db)

class AuthorModel(db.Model):
    __tablename__ = 'authors'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[int] = mapped_column(String(32), index= True)
    surname: Mapped[str] = mapped_column(String(32), server_default="", index=True)
    quotes: Mapped[list['QuoteModel']] = relationship(back_populates='author', lazy='dynamic', cascade="all, delete-orphan")

    def __init__(self, name, surname=""):
        self.name = name
        self.surname = surname

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "surname": self.surname
        }

class QuoteModel(db.Model):
    __tablename__ = 'quotes'

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('authors.id'))
    text: Mapped[str] = mapped_column(String(255), unique=True)
    rating: Mapped[int] = mapped_column(server_default='1')
    author: Mapped['AuthorModel'] = relationship(back_populates='quotes')

    def __init__(self, author, text, rating=1):
        self.author = author
        self.text  = text
        self.rating = rating

    def to_dict(self):
        return {
            "author": f'id={self.author.id}, {self.author.name} {self.author.surname}',
            "quote": f'id={self.id}, {self.text}',
            "quote rating": self.rating
        }

    def __repr__(self):
        return f'Quote{self.id, self.author}'

def iterate(temp_db):
    temp_quotes = []
    if type(temp_db) == list:
        for quote in temp_db:
            temp_quotes.append(quote.to_dict())
    else:
        temp_quotes.append(temp_db.to_dict())
    return temp_quotes

@app.errorhandler(HTTPException)
def handle_exception(e):
    return jsonify({'Message': e.description}), e.code


""" AUTHORS """

# URL: /authors
@app.get("/authors")
def get_authors():
    """ GET List of Authors """
    authors_db = db.session.scalars(db.select(AuthorModel)).all()
    authors = [author.to_dict() for author in authors_db]
    return jsonify(authors), HTTPStatus.OK

# URL: /authors/1
@app.get("/authors/<int:author_id>")
def author_quotes(author_id: int):
    """ GET Author by ID """
    author = db.get_or_404(AuthorModel, author_id, description=f'Author with id={author_id} not found')
    return jsonify(author.to_dict()), HTTPStatus.OK

# URL: /authors/1/quotes
@app.get("/authors/<int:author_id>/quotes")
def get_quote_by_author_id(author_id: int):
    """GET List of Quotes by Author ID"""
    db.get_or_404(AuthorModel, author_id, description=f"Author with id={author_id} not found")
    quotes_db = db.session.scalars(db.select(QuoteModel).where(QuoteModel.author_id == author_id)).all()
    return jsonify(iterate(quotes_db)), HTTPStatus.OK

# URL: /authors
@app.post("/authors")
def create_author():
    """POST Create new Author"""
    data = request.json

    if not data:
        return abort(HTTPStatus.BAD_REQUEST, "No valid data to update")

    keys = list(set(data.keys()).intersection({'name', 'surname'}))
    if 'name' in keys:
        new_data = {}
        for k in keys:
            new_data[k] = data[k]
    else:
        abort(HTTPStatus.BAD_REQUEST,
              f"Invalid data. Required: <name>, <surname> (optional). Received: {', '.join(data.keys())}.")

    try:
        author = AuthorModel(**new_data)
        db.session.add(author)
        db.session.commit()
    except Exception as e:
        abort(HTTPStatus.SERVICE_UNAVAILABLE, f"Error: {str(e)}")
    return jsonify(author.to_dict()), HTTPStatus.CREATED

# URL: /authors/1/quotes
@app.post("/authors/<int:author_id>/quotes")
def create_quote(author_id: int):
    """Create new Quote by Author ID"""
    data = request.json

    if not data:
        return abort(HTTPStatus.BAD_REQUEST, "No valid data to update")

    author = db.get_or_404(AuthorModel, author_id, description=f"Author with id={author_id} not found")

    keys = list(set(data.keys()).intersection({'text', 'rating'}))

    if 'rating' in keys:
        if (type(data.get('rating')) != int) or (type(data.get('rating')) == int and data.get('rating') not in range(1, 6)):
            abort(HTTPStatus.BAD_REQUEST, 'Rating must be a number between 1 and 5.')

    if 'text' in keys:
        new_data = {}
        for k in keys:
            new_data[k] = data[k]
    else:
        abort(HTTPStatus.BAD_REQUEST,
              f"Invalid data. Required: <text>, <rating> (optional). Received: {', '.join(data.keys())}.")

    try:
        quote = QuoteModel(author, **new_data)
        db.session.add(quote)
        db.session.commit()
    except Exception as e:
        abort(HTTPStatus.SERVICE_UNAVAILABLE, f"Error: {str(e)}.")
    return jsonify(quote.to_dict()), HTTPStatus.CREATED

# URL: /authors/1
@app.put("/authors/<int:author_id>")
def edit_author(author_id: int):
    """PUT Edit Author by ID"""
    data = request.json

    if not data:
        return abort(HTTPStatus.BAD_REQUEST, "No valid data to update")

    author = db.get_or_404(AuthorModel, author_id, description=f"Author with id={author_id} not found")

    keys = list(set(data.keys()).intersection({'name', 'surname'}))
    if keys:
        try:
            for k in keys:
                setattr(author, k, data[k])
            db.session.commit()
            return jsonify(author.to_dict()), HTTPStatus.OK
        except Exception as e:
            db.session.rollback()
            abort(HTTPStatus.SERVICE_UNAVAILABLE, f"Error: {str(e)}")
    else:
        abort(HTTPStatus.BAD_REQUEST,
              f"Invalid data. Required: <name>, <surname>. Received: {', '.join(data.keys())}.")

# URL: /authors/1
@app.delete("/authors/<int:author_id>")
def delete_author(author_id):
    """Delete Author by ID"""
    author = db.get_or_404(AuthorModel, author_id, description=f"Author with id={author_id} not found.")
    db.session.delete(author)
    try:
        db.session.commit()
        return jsonify({"Message": f"Author with id {author_id} was deleted."}), HTTPStatus.OK
    except Exception as e:
        db.session.rollback()
        abort(HTTPStatus.SERVICE_UNAVAILABLE, f"Error: {str(e)}.")


""" QUOTES """

# URL: /quotes
# URL: /quotes/
# URL: /quotes/1
@app.get("/quotes/", defaults={'quotes_id': None})
@app.get("/quotes/<int:quotes_id>")
def get_quote(quotes_id:int):
    """GET List of Quotes | GET Quote by ID"""
    if type(quotes_id)==int:
        quotes_db = db.get_or_404(QuoteModel, quotes_id, description=f"Quote with id={quotes_id} not found")
    else:
        quotes_db = db.session.scalars(db.select(QuoteModel)).all()
    return jsonify(iterate(quotes_db)), HTTPStatus.OK

# URL: /quotes/1
@app.put("/quotes/<int:quote_id>")
def edit_quote(quote_id: int):
    """Edit Quote by ID"""
    data = request.json

    if not data:
        return abort(HTTPStatus.BAD_REQUEST, "No valid data to update")

    quote = db.get_or_404(QuoteModel, quote_id, description=f"Quote with id={quote_id} not found")

    keys = list(set(data.keys()).intersection({'text', 'rating'}))

    if 'rating' in keys:
        if (type(data.get('rating')) != int) or (type(data.get('rating')) == int and data.get('rating') not in range(1, 6)):
            abort(HTTPStatus.BAD_REQUEST, 'Rating must be a number between 1 and 5.')

    if keys:
        try:
            for k in keys:
                setattr(quote, k, data[k])
            db.session.commit()
            return jsonify(quote.to_dict()), HTTPStatus.OK
        except Exception as e:
            db.session.rollback()
            abort(HTTPStatus.SERVICE_UNAVAILABLE, f"Error: {str(e)}")
    else:
        abort(HTTPStatus.BAD_REQUEST,
              f"Invalid data. Required: <name>, <surname>. Received: {', '.join(data.keys())}.")

# URL: /quotes
# URL: /quotes/
# URL: /quotes/1
@app.delete("/quotes/", defaults={'quote_id': None})
@app.delete("/quotes/<int:quote_id>")
def delete_quote(quote_id:int):
    """Delete Quote by ID"""
    if type(quote_id)==int:
        quote = db.get_or_404(entity=QuoteModel, ident=quote_id, description=f"Quote with id={quote_id} not found")
        db.session.delete(quote)
        try:
            db.session.commit()
            return jsonify({"Message": f"Quote with id {quote_id} was deleted."}), HTTPStatus.OK
        except Exception as e:
            db.session.rollback()
            abort(HTTPStatus.SERVICE_UNAVAILABLE, f'Error: {str(e)}')
    else:
        abort(HTTPStatus.BAD_REQUEST, 'The request is empty')


""" OLD """


@app.get("/quotes/count")
def quotes_count():
    quotes_db = db.session.scalars(db.select(QuoteModel)).all()
    return jsonify({'count': len(quotes_db)}), HTTPStatus.OK

@app.get("/quotes/random")
def quotes_random():
    quotes_db = db.session.scalars(db.select(QuoteModel)).all()
    return jsonify((choice(iterate(quotes_db)))) if quotes_db else jsonify({'Message': 'Response is empty.'})

@app.get("/quotes/filter")
def filter_quote():
    data = request.args
    if not list(set(data.keys()).intersection({'name', 'surname', 'text', 'rating'})):
        abort(HTTPStatus.BAD_REQUEST,
              f"Request is empty. Required: name, surname, text, rating. Received: {', '.join(data.keys())}.")

    data_author = dict()
    data_quote = dict()
    for n in ['name', 'surname', 'text', 'rating']:
        if data.get(n):
            match n :
                case 'name' | 'surname' : data_author[n] = data.get(n)
                case 'text' | 'rating' : data_quote[n] = data.get(n)

    quotes_db = []

    if data_author:
        authors_id = db.session.scalars(db.select(AuthorModel.id).filter_by(**data_author)).all()
        if authors_id:
            for a in authors_id:
                data_quote['author_id'] = a
                quotes_db.extend(db.session.scalars(db.select(QuoteModel).filter_by(**data_quote)).all())
    else:
        quotes_db.extend(db.session.scalars(db.select(QuoteModel).filter_by(**data_quote)).all())

    return jsonify(iterate(quotes_db)), HTTPStatus.OK


if __name__ == "__main__":
    app.run(debug=True)

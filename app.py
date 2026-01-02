from flask import Flask, jsonify, request, abort
from random import choice
from http import HTTPStatus
from pathlib import Path
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError, InvalidRequestError
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
# path_to_db = BASE_DIR / "store.db"

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
    name: Mapped[int] = mapped_column(String(32), index= True, unique=True)
    quotes: Mapped[list['QuoteModel']] = relationship(back_populates='author', lazy='dynamic')

    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }

class QuoteModel(db.Model):
    __tablename__ = 'quotes'

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('authors.id'))
    author: Mapped['AuthorModel'] = relationship(back_populates='quotes')
    text: Mapped[str] = mapped_column(String(255))

    def __init__(self, author, text):
        self.author = author
        self.text  = text

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
        }

def iterate(temp_db):
    temp_quotes = []
    for quote in temp_db:
        temp_quotes.append(quote.to_dict())
    return temp_quotes

@app.errorhandler(HTTPException)
def handle_exception(e):
    return jsonify({'Message': e.description}), e.code

# URL: /authors/1/quotes
@app.route("/authors/<int:author_id>/quotes")
def get_author_quotes(author_id:int):
    author = db.session.get(AuthorModel, author_id)
    db.get_or_404(entity=AuthorModel, ident=author_id, description=f"Author with id={author_id} not found")
    return jsonify(author=author.to_dict(), quotes=iterate(author.quotes)), HTTPStatus.OK

@app.route("/quotes/", defaults={'quotes_id': None})
@app.route("/quotes/<int:quotes_id>")
def get_quote(quotes_id:int):
    if quotes_id:
        quotes_db = db.session.scalars(db.select(QuoteModel).where(QuoteModel.id == quotes_id)).all()
        if not quotes_db:
            abort(HTTPStatus.NOT_FOUND, f'Quote with id={quotes_id} not found')
    else:
        quotes_db = db.session.scalars(db.select(QuoteModel)).all()
    return jsonify(iterate(quotes_db)), HTTPStatus.OK

@app.route("/quotes/count")
def quotes_count():
    quotes_db = db.session.scalars(db.select(QuoteModel)).all()
    return jsonify({'count': len(quotes_db)}), HTTPStatus.OK

@app.route("/quotes/random")
def quotes_random():
    quotes_db = db.session.scalars(db.select(QuoteModel)).all()
    return jsonify((choice(iterate(quotes_db)))) if quotes_db else jsonify({'Message': 'Response is empty.'})

@app.route("/quotes", methods=['POST'])
def create_quote():
    data = request.json

    if not data:
        abort(HTTPStatus.BAD_REQUEST, 'No valid data to update')

    auth = data.get("author")
    txt = data.get("text")
    rng = data.get("rating")

    if auth and txt and rng:

        if rng and rng not in range(1, 6):
            abort(HTTPStatus.BAD_REQUEST, 'Rating must be between 1 and 5')

        try:
            with app.app_context():
                new_quote = QuoteModel(auth, txt, rng)
                db.session.add(new_quote)
                db.session.commit()
                quote_id = new_quote.id
            return jsonify({'id': quote_id, 'author': auth, 'text': txt, 'rating': rng}), HTTPStatus.CREATED
        except Exception as e:
            abort(HTTPStatus.BAD_REQUEST, f'{str(e)}')

    abort(HTTPStatus.BAD_REQUEST, f'No valid data to update. Required: author, text, rating. Rating must be between 1 and 5')

@app.route("/quotes/", methods=['DELETE'], defaults={'quote_id': None})
@app.route("/quotes/<int:quote_id>", methods=['DELETE'])
def delete_quote(quote_id:int):
    if quote_id:
        quote = db.get_or_404(entity=QuoteModel, ident=quote_id, description=f"Quote with id={quote_id} not found")
        db.session.delete(quote)
        try:
            db.session.commit()
            return jsonify({"Message": f"Quote with id {quote_id} was deleted."}), HTTPStatus.OK
        except SQLAlchemyError as e:
            db.session.rollback()
            abort(HTTPStatus.SERVICE_UNAVAILABLE, f'{str(e)}')
    else:
        abort(HTTPStatus.BAD_REQUEST, 'The request is empty')


@app.route("/quotes/<int:quote_id>", methods=['PUT'])
def edit_quote(quote_id: int):
    new_data = request.json

    if not new_data:
        abort(HTTPStatus.BAD_REQUEST, 'No valid data to update')

    auth = new_data.get("author")
    txt = new_data.get("text")
    rng = new_data.get("rating")

    if auth or txt or rng in range(1, 6):

        quote = db.get_or_404(entity=QuoteModel, ident=quote_id, description=f"Quote with id={quote_id} not found")

        try:
            for key_as_attr, value in new_data.items():
                setattr(quote, key_as_attr, value)

            db.session.commit()
            return jsonify(quote.to_dict()), HTTPStatus.OK
        except SQLAlchemyError as e:
            db.session.rollback()
            abort(HTTPStatus.SERVICE_UNAVAILABLE, f"Database error: {str(e)}")

    abort(HTTPStatus.BAD_REQUEST, f'No valid data to update. Required: author, text, rating. Rating must be between 1 and 5')


@app.route('/quotes/filter', methods=['GET'])
def filter_quote():
    try:
        quotes_db = db.session.scalars(db.select(QuoteModel).filter_by(**request.args)).all()
    except InvalidRequestError:
        return (
            ('No valid data to filter. Required: author, text, rating.'
                 f'Received: {", ".join(request.args.keys())}'
             ),
            HTTPStatus.BAD_REQUEST,
        )
    return [quote.to_dict() for quote in quotes_db], HTTPStatus.OK


if __name__ == "__main__":
    app.run(debug=True)

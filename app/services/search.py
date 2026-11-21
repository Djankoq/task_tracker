from sqlalchemy import or_


def search_text(statement, term, *columns):
    if term is None:
        return statement
    # Treat %, _ and the escape character as literal user input in ILIKE.
    pattern = "%" + term.replace("/", "//").replace("%", "/%").replace("_", "/_") + "%"
    return statement.where(or_(*(column.ilike(pattern, escape="/") for column in columns)))

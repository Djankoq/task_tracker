from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.exceptions import ValidationError
from app.schemas.common import PageResponse
from app.schemas.pagination import Pagination


ReadModel = TypeVar("ReadModel", bound=BaseModel)


def paginate(
    db: Session, statement: Select, params: Pagination,
    columns: Mapping[str, InstrumentedAttribute[Any]],
    primary_key: InstrumentedAttribute[Any], schema: type[ReadModel],
) -> PageResponse[ReadModel]:
    # Only mapped columns from an explicit allowlist can enter ORDER BY.
    field = getattr(params, "sort_by", "")
    if field not in columns:
        raise ValidationError("Unsupported sort field")
    column = columns[field]
    order = column.desc() if params.sort_order == "desc" else column.asc()
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    # The unique ID makes pages deterministic when several records share a sort value.
    statement = statement.order_by(order, primary_key.asc()).offset(params.offset).limit(params.per_page)
    return PageResponse[schema](
        items=[schema.model_validate(item) for item in db.scalars(statement)],
        total=total, page=params.page, per_page=params.per_page,
        total_pages=(total + params.per_page - 1) // params.per_page,
    )

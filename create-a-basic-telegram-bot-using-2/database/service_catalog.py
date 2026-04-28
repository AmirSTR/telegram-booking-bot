from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Service

ADMIN_SERVICES: Sequence[dict[str, int | str]] = (
    {
        "name": "Стрижка",
        "price": 1500,
        "duration": 60,
    },
    {
        "name": "Окрашивание",
        "price": 3500,
        "duration": 120,
    },
    {
        "name": "Укладка",
        "price": 1000,
        "duration": 45,
    },
)


def seed_services(session: Session) -> None:
    for item in ADMIN_SERVICES:
        service = session.scalar(
            select(Service).where(Service.name == item["name"])
        )

        if service is None:
            session.add(
                Service(
                    name=str(item["name"]),
                    price=int(item["price"]),
                    duration=int(item["duration"]),
                )
            )
            continue

    session.commit()
    session.close()

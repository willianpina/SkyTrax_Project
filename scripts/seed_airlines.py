from __future__ import annotations

from database.models import Airline
from database.session import SessionLocal


AIRLINES = [
    {
        "name": "British Airways",
        "slug": "british-airways",
        "country": "United Kingdom",
        "review_url": "https://www.airlinequality.com/airline-reviews/british-airways/",
    },
    {
        "name": "Lufthansa",
        "slug": "lufthansa",
        "country": "Germany",
        "review_url": "https://www.airlinequality.com/airline-reviews/lufthansa/",
    },
    {
        "name": "Emirates",
        "slug": "emirates",
        "country": "United Arab Emirates",
        "review_url": "https://www.airlinequality.com/airline-reviews/emirates/",
    },
    {
        "name": "LATAM",
        "slug": "latam",
        "country": "Brazil/Chile",
        "review_url": "https://www.airlinequality.com/airline-reviews/latam-airlines/",
    },
]


def main() -> None:
    session = SessionLocal()
    try:
        for payload in AIRLINES:
            existing = session.query(Airline).filter_by(slug=payload["slug"]).first()
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
            else:
                session.add(Airline(**payload))
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.models import Base, Case


def test_case_table_is_registered():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    try:
        Base.metadata.create_all(engine)

        assert "cases" in inspect(engine).get_table_names()

        with Session(engine) as session:
            case = Case(business_name="Demo Business")
            session.add(case)
            session.commit()
            session.refresh(case)

            assert case.id is not None
            assert case.business_name == "Demo Business"
            assert case.status == "created"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
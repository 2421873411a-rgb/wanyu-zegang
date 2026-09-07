from sqlalchemy import Column, DateTime, Integer, Numeric, String, UniqueConstraint

from app.database import Base
from app.utils.time import utcnow_naive


class SalaryData(Base):
    __tablename__ = "salary_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(32), nullable=False)
    employment_type = Column(String(16), nullable=False)
    stage = Column(String(16), nullable=False)
    value_wan = Column(Numeric)
    snapshot_year = Column(String(8), default="2026")
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)

    __table_args__ = (
        UniqueConstraint("city", "employment_type", "stage", "snapshot_year", name="uq_salary"),
    )

    def __repr__(self):
        return f"<SalaryData {self.city} {self.employment_type}>"

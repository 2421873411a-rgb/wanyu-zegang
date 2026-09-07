from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, Numeric, String, Text

from app.database import Base
from app.utils.time import utcnow_naive


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(128), unique=True, nullable=False, index=True)
    cycle = Column(String(8), nullable=False, index=True)
    code = Column(String(32), index=True)
    city = Column(String(32), index=True)
    exam = Column(String(64), index=True)
    unit = Column(String(256))
    zw = Column(String(256))
    zy = Column(Text)
    num = Column(Integer)
    xl = Column(String(64))
    xw = Column(String(64))
    xz = Column(String(64))
    age = Column(String(128))
    bz = Column(Text)
    lb = Column(String(64), index=True)
    title_status = Column(String(32))
    display_title = Column(String(256))
    job_status = Column(String(32), default="active")

    score_observation_status = Column(String(32))
    score_observation_scale_id = Column(String(32))
    score_observation_value = Column(Numeric)
    competition_metric_type = Column(String(32))
    competition_base = Column(Integer)
    competition_source = Column(String(128))
    ratio_comparable = Column(Boolean, default=False)
    source = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    def __repr__(self):
        return f"<Job {self.job_id}>"

from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, DateTime, UniqueConstraint
from app.database import Base


class SalaryData(Base):
    """待遇数据模型"""
    __tablename__ = "salary_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(32), nullable=False)
    employment_type = Column(String(16), nullable=False)  # 公务员/事业编
    stage = Column(String(16), nullable=False)  # 工龄阶段
    value_wan = Column(Numeric)  # 万元/年
    snapshot_year = Column(String(8), default="2026")
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('city', 'employment_type', 'stage', 'snapshot_year', name='uq_salary'),
    )
    
    def __repr__(self):
        return f"<SalaryData {self.city} {self.employment_type}>"

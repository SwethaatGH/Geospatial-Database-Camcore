from sqlalchemy import Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import UserDefinedType

Base = declarative_base()
# Custom type for Raster since we're not using GeoAlchemy2
class Raster(UserDefinedType):
    def get_col_spec(self):
        return "RASTER"
    
    def bind_expression(self, bindvalue):
        return bindvalue
    
    def column_expression(self, col):
        return col

class PrecRaster(Base):
    __tablename__ = "wc_prec_1981-01"
    
    rid = Column(Integer, primary_key=True, index=True)
    rast = Column(Raster)

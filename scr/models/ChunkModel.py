from .BaseDataModel import BaseDataModel
from .db_schems import DataChunk
from .enums.DataBaseEnum import DataBaseEnum
from bson.objectid import ObjectId
from sqlalchemy.future import select
from sqlalchemy import func, delete, update
import math
class ChunkModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls,db_client:object):
        isinstance= cls(db_client)
        return isinstance
    

    async def create_chunk(self, chunk: DataChunk):
        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
        return chunk
             
    async def get_chunk(self, chunk_id: str):
        async with self.db_client() as session:
            async with session.begin():
                query = select(DataChunk).where(DataChunk.chunk_id == chunk_id)
                result = await session.execute(query)
                chunk = result.scalars().one_or_none()
        return chunk
    
    async def insert_many_chunks(self, chunks: list, batch_size: int=100):
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    session.add_all(batch)
            await session.commit()
        return len(chunks)

       
    
    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        async with self.db_client() as session:
            async with session.begin():
                query = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
                result = await session.execute(query)
                await session.commit()
        return result.rowcount

      
    async def get_project_chunks(self,project_id:ObjectId,page_no:int=1,page_size:int=50):
        async with self.db_client() as session:
            stmt=select(DataChunk).where(DataChunk.chunk_project_id==project_id).offset((page_no-1)*page_size).limit(page_size)
            result=await session.execute(stmt)
            records=result.scalars().all()
        return records

    async def get_chunks_by_asset_id(self, asset_id: str):
        async with self.db_client() as session:
            stmt = select(DataChunk).where(DataChunk.chunk_asset_id == asset_id).limit(1)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
        return record

    async def get_total_chunks_count(self,project_id:ObjectId):
        count = 0
        async with self.db_client() as session:
            stmt=select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_project_id==project_id)
            result=await session.execute(stmt)
            count=result.scalar()
        return count

    async def get_unindexed_project_chunks(self, project_id: ObjectId, page_no: int = 1, page_size: int = 50):
        """Get chunks that haven't been indexed yet (is_indexed=False)"""
        async with self.db_client() as session:
            stmt = select(DataChunk).where(
                (DataChunk.chunk_project_id == project_id) & (DataChunk.is_indexed == False)
            ).offset((page_no - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            records = result.scalars().all()
        return records

    async def get_total_unindexed_chunks_count(self, project_id: ObjectId):
        """Get count of chunks that haven't been indexed yet"""
        count = 0
        async with self.db_client() as session:
            stmt = select(func.count(DataChunk.chunk_id)).where(
                (DataChunk.chunk_project_id == project_id) & (DataChunk.is_indexed == False)
            )
            result = await session.execute(stmt)
            count = result.scalar()
        return count

    async def mark_chunks_as_indexed(self, chunk_ids: list):
        """Mark a list of chunks as indexed"""
        async with self.db_client() as session:
            async with session.begin():
                stmt = update(DataChunk).where(DataChunk.chunk_id.in_(chunk_ids)).values(is_indexed=True)
                result = await session.execute(stmt)
            await session.commit()
        return result.rowcount


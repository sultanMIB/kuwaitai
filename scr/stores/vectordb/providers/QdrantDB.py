from qdrant_client import QdrantClient, models
from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
from typing import List
from models.db_schems import RetrievedDocument
import logging
import time
import random
import uuid


class QdrantDB(VectorDBInterface):

    def __init__(self, db_client: str,default_vector_size: int = 786,
                       distance_method: str = None, index_threshold: int=100):
        self.client = None
        self.db_client = db_client
        self.distance_method = None
        self.default_vector_size = default_vector_size

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        self.logger = logging.getLogger('uvicorn')

    async def connect(self):
        self.client = QdrantClient(path=self.db_client)

    async def disconnect(self):
        self.client = None

    async def is_collection_existed(self, collection_name: str) -> bool:
        try:
            self.client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    async def list_all_collection(self) -> List:
        return self.client.get_collections()

    async def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)

    async def delete_collection(self, collection_name: str):
        if self.is_collection_existed(collection_name=collection_name):
            self.logger.info(f"Deleting collection: {collection_name}")
            return self.client.delete_collection(collection_name=collection_name)

    async def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        if do_reset:
            _ = self.delete_collection(collection_name=collection_name)

        if not self.is_collection_existed(collection_name=collection_name):
            self.logger.info(f"Creating new Qdrant collection: {collection_name} with embedding size: {embedding_size}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method,
                ),
            )
            return True
        return False



    async def insert_one(self, collection_name: str, text: str, vector: list, metadata: dict = None, record_id: str = None):
        if not self.is_collection_existed(collection_name=collection_name):
            self.logger.error(f"Cannot insert new record to non-existent collection: {collection_name}")
            return False

        # Generate record_id
        if record_id is None:
            record_id = int(time.time() * 1000000) + random.randint(0, 1000)
        else:
            try:
                record_id = int(record_id)
            except (ValueError, TypeError):
                self.logger.error(f"record_id must be convertible to integer: {record_id}")
                return False

        # Ensure metadata is dict
        if metadata is None:
            metadata = {}

        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=record_id,
                        vector=vector,
                        payload={
                            "text": text,
                            "metadata": metadata,
                        },
                    )
                ],
                # include: True معناه يخلي response يرد بالـ points
                # بس في qdrant غالبًا مش لازم إلا لو عايز تتأكد من الإضافة
                # لو عايز تستخدمها ممكن تبقى:
                # wait=True  (تستنى لحد ما يخلص)
            )
            self.logger.info(f"Inserted record_id={record_id} into '{collection_name}'")
        except Exception as e:
            self.logger.error(f"Error while inserting record: {e}")
            return False

        try:
            total = self.client.count(collection_name=collection_name).count
            self.logger.info(f"Total records in collection '{collection_name}': {total}")
        except Exception as e:
            self.logger.error(f"Error while counting records in collection {collection_name}: {e}")

        return record_id

    




    async def insert_many(
    self,
    collection_name: str,
    texts: list,
    vectors: list,
    metadata: list = None,
    record_ids: list = None,
    batch_size: int = 50
):
        if not self.is_collection_existed(collection_name=collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return False

        if not texts or not vectors or len(texts) != len(vectors):
            self.logger.error("Mismatch between number of texts and vectors, or empty input.")
            return False

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            import time
            import random
            base_id = int(time.time() * 1000000)  # microsecond timestamp
            record_ids = [base_id + i + random.randint(0, 1000) for i in range(len(texts))]
        else:
            try:
                record_ids = [int(id_val) for id_val in record_ids]
            except (ValueError, TypeError) as e:
                self.logger.error(f"All record_ids must be convertible to integers: {e}")
                return False

        total_inserted = 0

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size
            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_ids = record_ids[i:batch_end]

            valid_points = []
            for idx in range(len(batch_texts)):
                vec = batch_vectors[idx]
                if not isinstance(vec, list) or len(vec) == 0:
                    self.logger.warning(f"Skipping record {batch_ids[idx]} due to invalid vector")
                    continue

                point_id = int(batch_ids[idx])
                valid_points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vec,
                        payload={
                            "text": batch_texts[idx],
                            "metadata": batch_metadata[idx],
                        },
                    )
                )

            if not valid_points:
                self.logger.warning(f"Skipping empty batch at index {i}")
                continue

            self.logger.info(f"Inserting batch {i//batch_size + 1}: {len(valid_points)} records")

            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=valid_points,
                )
                total_inserted += len(valid_points)

                # بعد كل batch نعمل count على الـcollection
                count = self.client.count(collection_name=collection_name, exact=True).count
                self.logger.info(f"Collection {collection_name} now has {count} records")

            except Exception as e:
                self.logger.error(f"Error while inserting batch {i}-{batch_end}: {e}")
                return False

        self.logger.info(f"Finished inserting {total_inserted} records into {collection_name}")
        return True



    

    
    async def search_by_vector(self, collection_name: str, vector: list, limit: int):
         results =self.client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit,
        )
         
         if not results or len(results)==0:
             return None
         
         return [
             RetrievedDocument(**{
                 "score":res.score,
                 "text":res.payload["text"]
             })
             
             for res in results
         ]

    async def delete_points(self, collection_name: str, point_ids: list):
        """Delete specific points (vectors) from a collection by their IDs"""
        try:
            if not await self.is_collection_existed(collection_name=collection_name):
                self.logger.warning(f"Collection {collection_name} does not exist")
                return False
            
            # Convert point_ids to integers
            int_ids = [int(pid) for pid in point_ids]
            
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    idxs=int_ids,
                )
            )
            self.logger.info(f"Deleted {len(int_ids)} points from collection {collection_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting points from {collection_name}: {e}")
            return False

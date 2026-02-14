from fastapi import APIRouter,FastAPI, Depends,UploadFile,status,Request
from fastapi.responses import JSONResponse
import os
from helper.config import get_settings, Settings
from controllers import DataController
from controllers import ProjectController
from controllers import ProcessController
from models import ResponseStatus
from .Schemas.data import ProcessRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.AssetsModel import AssetModel
from models.db_schems import Asset,DataChunk
from models.enums.AssetTypeEnums import AssetTypeEnum
from controllers import NLPController
import aiofiles
import logging

logger = logging.getLogger("uvicorn.error")

router_data = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}},
)
@router_data.post("/upload/{project_id}")
async def upload_data(request:Request,file:UploadFile,project_id:int, app_settings: Settings = Depends(get_settings)):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )
    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    data_controller = DataController()

    is_valid, message = await data_controller.validate_file(file=file)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": message})
    
    
    file_path,file_id = data_controller.generate_unique_filename(filename=file.filename, project_id=project_id)

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while chuck := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await out_file.write(chuck)
    except Exception as e:
        logger.error(f"Error while Uploading file: {e}")
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"message": ResponseStatus.FILE_UPLOAD_FAILED.value}
            )
    

    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )


    asset_resource= Asset(
        asset_project_id= project.project_id,
        asset_type= AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path)
    )

    asset_record= await asset_model.create_asset(asset=asset_resource)



    



    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": ResponseStatus.FILE_UPLOAD_SUCCESS.value,
            "file_id": file_id,
            "asset_id": str(asset_record.asset_id),
        },
    )
            
@router_data.post("/process/{project_id}")
async def process_endpoint(request:Request,project_id:int,process_request:ProcessRequest):
    chunk_size = process_request.chunk_size
    chunk_overlap = process_request.chunk_overlap
    do_reset = process_request.do_reset


    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    process_controller=ProcessController(project_id)

    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    project_files_ids = {}
    if process_request.file_id:
        asset_record= await asset_model.get_asset_record(
            asset_project_id=project.project_id,
            asset_name=process_request.file_id
        )
        if asset_record is None:

            return JSONResponse(
            status_code = status.HTTP_400_BAD_REQUEST,
            content={
                "message":ResponseStatus.FILE_ID_ERROR.value
            }
        )
    

        project_files_ids={
            asset_record.asset_id: asset_record.asset_name
        }
    else:
        
        
        project_files = await asset_model.get_all_project_assets(
            asset_project_id= project.project_id,
            asset_type= AssetTypeEnum.FILE.value
        )

        project_files_ids ={
            rec.asset_id : rec.asset_name
            for rec in project_files
        }
    if len(project_files_ids) == 0:
        return JSONResponse(
            status_code = status.HTTP_400_BAD_REQUEST,
            content={
                "message":ResponseStatus.NO_FILES_ERROR.value
            }
        )
    
    no_records=0
    no_files=0

    chunk_model = await ChunkModel.create_instance(
            db_client=request.app.db_client
        )


    if do_reset == 1:
            collection_name= nlp_controller.create_collection_name(project_id=project.project_id)
            _= await request.app.vectordb_client.delete_collection(
                collection_name=collection_name
            )
            _ = await chunk_model.delete_chunks_by_project_id(
                project_id=project.project_id
            )
        

        

    for asset_id,file_id in project_files_ids.items():

        # If chunks for this asset already exist and user didn't request reset, abort to avoid duplicates
        existing_chunks = await chunk_model.get_chunks_by_asset_id(asset_id)
        if existing_chunks and do_reset != 1:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "file_already_processed"},
            )

        file_content = process_controller.get_file_content(file_id=file_id)

        if file_content is None:
            logger.error(f"Error While processing file:{file_id}")
            continue

        file_chunks = process_controller.process_file(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
            

        )
        
        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": ResponseStatus.FILE_PROCESS_FAILED.value
                }
            )
        
        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]

        
        

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files +=1

    return JSONResponse(
        content={
            "signal": ResponseStatus.FILE_PROCESS_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files":no_files
        }
    )


@router_data.get("/assets")
async def get_all_assets(request: Request):
    """Get all asset names from database"""
    try:
        asset_model = await AssetModel.create_instance(
            db_client=request.app.db_client
        )
        assets = await asset_model.get_all_assets()
        
        asset_list = [
            {
                "asset_id": asset.asset_id,
                "asset_name": asset.asset_name,
                "asset_type": asset.asset_type,
                "asset_size": asset.asset_size,
                "asset_project_id": asset.asset_project_id,
                "created_at": asset.created_at.isoformat() if asset.created_at else None,
            }
            for asset in assets
        ]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "success",
                "total_assets": len(asset_list),
                "assets": asset_list,
            },
        )
    except Exception as e:
        logger.error(f"Error fetching assets: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error fetching assets"},
        )


@router_data.delete("/assets/{asset_name}")
async def delete_asset(request: Request, asset_name: str):
    """Delete asset by asset_name (also deletes associated chunks and vectors)"""
    try:
        asset_model = await AssetModel.create_instance(
            db_client=request.app.db_client
        )
        chunk_model = await ChunkModel.create_instance(
            db_client=request.app.db_client
        )
        
        # Check if asset exists first
        from sqlalchemy.future import select
        async with request.app.db_client() as session:
            stmt = select(Asset).where(Asset.asset_name == asset_name)
            result = await session.execute(stmt)
            existing_asset = result.scalar_one_or_none()
        
        if not existing_asset:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": f"Asset '{asset_name}' not found"},
            )
        
        asset_id = existing_asset.asset_id
        project_id = existing_asset.asset_project_id
        
        # Get all chunks for this asset
        async with request.app.db_client() as session:
            stmt = select(DataChunk).where(DataChunk.chunk_asset_id == asset_id)
            result = await session.execute(stmt)
            chunks = result.scalars().all()
        
        # Delete vectors from vector DB collection for this project
        if chunks:
            try:
                nlp_controller = NLPController(
                    vectordb_client=request.app.vectordb_client,
                    generation_client=request.app.generation_client,
                    embedding_client=request.app.embedding_client,
                    template_parser=request.app.template_parser,
                )
                collection_name = nlp_controller.create_collection_name(project_id=project_id)
                
                # Delete chunk vectors from collection
                chunk_ids = [c.chunk_id for c in chunks]
                await request.app.vectordb_client.delete_points(
                    collection_name=collection_name,
                    point_ids=chunk_ids
                )
                logger.info(f"Deleted {len(chunk_ids)} vectors from collection {collection_name}")
            except Exception as e:
                logger.warning(f"Error deleting vectors from vector DB: {e}")
        
        # Delete the asset (cascades to chunks in Postgres)
        deleted_count = await asset_model.delete_asset_by_name(asset_name)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "success",
                "deleted_asset_name": asset_name,
                "deleted_asset_id": asset_id,
                "deleted_chunks_count": len(chunks),
            },
        )
    except Exception as e:
        logger.error(f"Error deleting asset '{asset_name}': {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": f"error deleting asset: {str(e)}"},
        )
    








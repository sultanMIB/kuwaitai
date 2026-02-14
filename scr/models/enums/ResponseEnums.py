from enum import Enum

class ResponseStatus(Enum):
    FILE_VALIDATED_SUCCESS = "file_validate_successfully"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS = "file_upload_success"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    FILE_PROCESS_FAILED = "file_process_failed"
    FILE_PROCESS_SUCCESS = "file_process_success"
    NO_FILES_ERROR ="not_found_files"
    FILE_ID_ERROR = "not_found_files_with_this_id"
    PROJECT_NOT_FOUND_ERORR="project_not_found"
    INSERT_INTO_VECTORDB_ERORR="Erorr while inserting into vector db"
    INSERT_INTO_VECTORDB_SUCCESS= "SUCCESS"
    VECTOR_DB_COLLECTION_RETRIEVED="vector_db_collection_retrieved"
    ERORR_WITH_SEARCH_BY_VECTOR= "Error whil searching by vector"
    SUCCESS_WITH_SEARCH_BY_VECTOR="SUCCESS"
    ERORR_ANSWER="Error while get answer"
    ANSWER_SUCCESS="SUCCESS"
    GREETING_RESPONSE="GREETING_RESPONSE"
    DETAILED_ANSWER="DETAILED_ANSWER"

    


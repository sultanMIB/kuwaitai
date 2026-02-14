from .BaseController import BaseController
from fastapi import UploadFile
from models import ResponseStatus
from .ProjectController import ProjectController
import re
import os

class DataController(BaseController):
    def __init__(self):
        super().__init__()

    async def validate_file(self, file: UploadFile):
        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            return False, ResponseStatus.FILE_TYPE_NOT_SUPPORTED.value
        
        if file.size > self.app_settings.FILE_MAX_SIZE:
            return False, ResponseStatus.FILE_SIZE_EXCEEDED.value
        
        return True, ResponseStatus.FILE_VALIDATED_SUCCESS.value
    def clean_filename(self, filename: str):
        # Remove any special characters except for alphanumeric characters, underscores, and hyphens
        filename = re.sub(r'[^\w.]', '', filename.strip())
        # Replace spaces with underscores
        filename = filename.replace(" ", "_")
       
        return filename
    def generate_unique_filename(self, filename: str,project_id: str):
        random_string = self.generate_random_string()
        project_path = ProjectController().get_project_path(project_id=project_id)
        filename_clean=self.clean_filename(filename=filename)
        new_file_path= os.path.join(project_path, random_string + "_" + filename_clean)
        # Ensure the new file path is unique
        while os.path.exists(new_file_path):
            random_string = self.generate_random_string()
            new_file_path = os.path.join(project_path, random_string + "_" + filename_clean)
        
        return new_file_path , random_string + "_" + filename_clean



        
    
    
        

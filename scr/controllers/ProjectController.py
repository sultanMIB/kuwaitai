from .BaseController import BaseController
from fastapi import UploadFile
import os


class ProjectController(BaseController):
    def __init__(self):
        super().__init__()
    
    def get_project_path(self, project_id: str):
        prject_dir = os.path.join(self.file_dir, str(project_id))
        if not os.path.exists(prject_dir):
            os.makedirs(prject_dir)
        return prject_dir

    
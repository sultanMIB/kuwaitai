from .BaseController import BaseController
from .ProjectController import ProjectController
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models.enums.ProcessingEnum import ProcessingEnums
import os

class ProcessController(BaseController):
    def __init__(self, project_id:str):
        super().__init__()
        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1].lower()
    
    def get_file_loader(self, file_id: str):
        file_extension = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(self.project_path, file_id)
        
        if not os.path.exists(file_path):
            return None

        if file_extension == ProcessingEnums.MARKDOWN.value:
            return UnstructuredMarkdownLoader(file_path)
        elif file_extension == ProcessingEnums.PDF.value:
            return PyMuPDFLoader(file_path)
        elif file_extension == ProcessingEnums.TXT.value:
            return TextLoader(file_path, encoding='utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
    def get_file_content(self, file_id: str):
        loader = self.get_file_loader(file_id)
        if loader :
            documents = loader.load()
            return documents
        return None
    
    def process_file(self, file_content: list,file_id: str,chunk_size: int = 400, chunk_overlap: int = 20):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        file_content_text = [doc.page_content for doc in file_content]
        file_content_metadata = [doc.metadata for doc in file_content]
        chunks = text_splitter.create_documents(file_content_text, file_content_metadata)
        return chunks
        

    
class FileMapper:
    def __init__(self, files: list, project_dir: str) -> None:
        self.id_to_path = {}
        self.path_to_id = {}
        for file in files:
            file_id = int(file["file_id"])
            path = str(file["file_path"]).replace(project_dir+"/", "")
            self.id_to_path[file_id] = path
            self.path_to_id[path] = file_id
    
    def get_file_id(self, path: str) -> int:
        return self.path_to_id[path]
    
    def get_file_path(self, file_id: int) -> str:
        return self.id_to_path[file_id]
